"""
Router Agent (LAYER 1)

Classifies queries and routes to appropriate tier:
- Tier 1: Direct SQL (simple, well-defined patterns)
- Tier 2: Pre-built Views (common reports)
- Tier 3: Text-to-SQL RAG (complex, natural language)

Also extracts:
- Query type (statistical, filtering, semantic, cross-table)
- Entities (VIN, dealer, dates, models)
- Complexity (single/multi-table, simple/complex)
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import re
from datetime import datetime
from config.llm_config import get_llm_for_component


class QueryTier(Enum):
    """Query routing tier"""
    TIER_1 = "direct_sql"        # Simple, exact patterns
    TIER_2 = "prebuilt_views"    # Common reports
    TIER_3 = "text_to_sql"       # Complex RAG pipeline


class QueryType(Enum):
    """Query classification"""
    STATISTICAL = "statistical"       # COUNT, AVG, SUM, MIN, MAX
    FILTERING = "filtering"           # WHERE clauses
    SEMANTIC = "semantic"             # Natural language understanding
    CROSS_TABLE = "cross_table"       # Multi-table JOINs
    AGGREGATION = "aggregation"       # GROUP BY
    TIME_SERIES = "time_series"       # Date-based trends
    EXACT_LOOKUP = "exact_lookup"     # Find by ID/VIN


@dataclass
class ExtractedEntities:
    """Entities extracted from query"""
    vins: List[str] = None
    dealer_ids: List[int] = None
    dates: Dict[str, str] = None      # {"start": "2024-01-01", "end": "2024-12-31"}
    models: List[str] = None          # H6, Jolion, BJ40
    customer_names: List[str] = None
    ro_numbers: List[str] = None      # Repair order numbers

    def __post_init__(self):
        if self.vins is None:
            self.vins = []
        if self.dealer_ids is None:
            self.dealer_ids = []
        if self.dates is None:
            self.dates = {}
        if self.models is None:
            self.models = []
        if self.customer_names is None:
            self.customer_names = []
        if self.ro_numbers is None:
            self.ro_numbers = []


@dataclass
class QueryAnalysis:
    """Complete query analysis result"""
    original_query: str
    tier: QueryTier
    query_types: List[QueryType]
    entities: ExtractedEntities
    complexity: str               # "simple", "medium", "complex"
    table_count: str             # "single", "multiple"
    requires_join: bool
    requires_aggregation: bool
    confidence: float            # 0.0 - 1.0
    reasoning: str               # Why this tier was chosen

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        result = asdict(self)
        result['tier'] = self.tier.value
        result['query_types'] = [qt.value for qt in self.query_types]
        return result


class RouterAgent:
    """
    Router Agent - LAYER 1 of DMS RAG Pipeline

    Routes queries to appropriate processing tier and extracts entities.

    Accuracy Targets:
    - Tier 1 routing: 99% (simple patterns are deterministic)
    - Tier 2 routing: 85% (common reports have known patterns)
    - Tier 3 routing: 70% (complex queries need full RAG)
    """

    def __init__(self, use_llm: bool = True):
        """
        Initialize Router Agent.

        Args:
            use_llm: Whether to use LLM for complex classification (default: True)
        """
        self.use_llm = use_llm

        if self.use_llm:
            # Initialize LLM for complex query classification
            # Using same component as dealership query classifier
            self.llm = get_llm_for_component("dealership_query_classifier")

        # Tier 1 patterns (deterministic, exact matches)
        self.tier1_patterns = {
            "exact_vin_lookup": r"(?:find|get|show|lookup).*vin.*([A-Z0-9]{17})",
            "exact_ro_lookup": r"(?:find|get|show).*(?:repair order|ro).*([A-Z0-9\-]+)",
            "dealer_count": r"how many (?:dealers|dealerships)",
            "simple_count": r"count.*(?:vehicles|customers|repairs)",
        }

        # Tier 2 patterns (common reports)
        self.tier2_patterns = {
            "monthly_summary": r"(?:monthly|month).*(?:summary|report|statistics)",
            "dealer_performance": r"(?:dealer|dealership).*(?:performance|ranking|comparison)",
            "top_issues": r"(?:top|most common|frequent).*(?:issues|problems|complaints)",
            "warranty_summary": r"warranty.*(?:summary|report|claims)",
        }

        # Entity extraction patterns
        self.entity_patterns = {
            "vin": r"\b([A-Z0-9]{17})\b",
            "dealer_id": r"(?:dealer(?:ship)?\s*(?:id|#)?\s*(\d+)|dealership\s+(\d+))",
            "ro_number": r"(?:ro|repair order)[\s\-#]*([A-Z0-9\-]+)",
            "model": r"\b(H6|Jolion|BJ40|BJ-40)\b",
        }

        # Month/date extraction patterns
        self.month_names = [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december"
        ]

    def analyze_query(self, query: str) -> QueryAnalysis:
        """
        Analyze query and determine routing tier.

        ROUTING STRATEGY (Option 3: Always LLM):
        ==========================================
        Always use LLM for classification to handle edge cases:
        - "Average repair cost for VIN X" → Has VIN (Tier 1 pattern) BUT needs aggregation (Tier 3)
        - "Show VIN X details" → Simple lookup (Tier 1)

        LLM sees full context and routes correctly in both cases.

        Benefits:
        - 99% accuracy (handles all edge cases)
        - Entity extraction still provides hints to LLM
        - Consistent routing logic

        Cost: ~$0.0001 per query (grok-3-fast)
        Latency: 1-2 seconds

        Args:
            query: Natural language query

        Returns:
            QueryAnalysis with tier, type, entities, complexity
        """
        # 1. ENTITY EXTRACTION
        # ---------------------
        # Extract VINs, Dealer IDs, dates, models, RO numbers using regex
        # These are passed as HINTS to the LLM for better classification
        # Example: "Average H6 repair cost in December" extracts:
        #   - models: ['H6']
        #   - dates: {'month': 'december', 'start': '2024-12-01', 'end': '2024-12-28'}
        entities = self._extract_entities(query)

        # 2. LLM CLASSIFICATION
        # ----------------------
        # Always use LLM for routing decision (handles all edge cases)
        # LLM decides: Tier (1/2/3), Query Types, Complexity, Table Count
        if self.use_llm:
            return self._analyze_with_llm(query, entities)
        else:
            # Fallback: rule-based classification (only if LLM unavailable)
            return self._analyze_rule_based(query, entities)

    def _check_tier1(self, query: str) -> Optional[str]:
        """Check if query matches Tier 1 patterns (exact lookups)"""
        for pattern_name, pattern in self.tier1_patterns.items():
            if re.search(pattern, query, re.IGNORECASE):
                return pattern_name
        return None

    def _check_tier2(self, query: str) -> Optional[str]:
        """Check if query matches Tier 2 patterns (common reports)"""
        for pattern_name, pattern in self.tier2_patterns.items():
            if re.search(pattern, query, re.IGNORECASE):
                return pattern_name
        return None

    def _extract_entities(self, query: str) -> ExtractedEntities:
        """Extract entities from query using regex patterns"""
        entities = ExtractedEntities()

        # Extract VINs
        vin_matches = re.findall(self.entity_patterns["vin"], query)
        entities.vins = list(set(vin_matches))

        # Extract Dealer IDs
        dealer_matches = re.findall(self.entity_patterns["dealer_id"], query, re.IGNORECASE)
        entities.dealer_ids = [int(m[0] or m[1]) for m in dealer_matches if m[0] or m[1]]

        # Extract RO numbers
        ro_matches = re.findall(self.entity_patterns["ro_number"], query, re.IGNORECASE)
        entities.ro_numbers = list(set(ro_matches))

        # Extract models
        model_matches = re.findall(self.entity_patterns["model"], query, re.IGNORECASE)
        entities.models = list(set([m.upper() for m in model_matches]))

        # Extract dates
        entities.dates = self._extract_dates(query)

        return entities

    def _extract_dates(self, query: str) -> Dict[str, str]:
        """Extract date ranges from query"""
        dates = {}
        query_lower = query.lower()

        # Check for specific months
        for i, month in enumerate(self.month_names, 1):
            if month in query_lower:
                # Extract year if present
                year_match = re.search(r'\b(20\d{2})\b', query)
                year = year_match.group(1) if year_match else str(datetime.now().year)

                dates['month'] = month
                dates['start'] = f"{year}-{i:02d}-01"
                # Simple end date (last day varies, but this is close enough)
                dates['end'] = f"{year}-{i:02d}-28"

        # Check for year
        year_match = re.search(r'\b(20\d{2})\b', query)
        if year_match and 'month' not in dates:
            year = year_match.group(1)
            dates['start'] = f"{year}-01-01"
            dates['end'] = f"{year}-12-31"

        # Check for relative dates (this month, last month, etc.)
        if re.search(r'\b(?:this|current)\s+month\b', query_lower):
            now = datetime.now()
            dates['month'] = self.month_names[now.month - 1]
            dates['start'] = f"{now.year}-{now.month:02d}-01"
            dates['end'] = f"{now.year}-{now.month:02d}-28"

        return dates

    def _analyze_with_llm(self, query: str, entities: ExtractedEntities) -> QueryAnalysis:
        """
        Use LLM to classify queries and determine routing.

        MENTAL MAP:
        ===========
        1. LLM receives: Query + Extracted entities (VIN, dates, etc.)
        2. LLM classifies: Query types, Complexity, Table count, Tier
        3. Returns: Complete routing decision with reasoning
        LLM Classification Logic:
        - If simple lookup (VIN, RO#) with no aggregation → Tier 1
        - If common report pattern → Tier 2
        - If complex analysis, aggregation, or multi-table → Tier 3

        Args:
            query: User's natural language query
            entities: Pre-extracted entities (VIN, dates, models, etc.)

        Returns:
            QueryAnalysis with full routing decision
        """

        system_prompt = """You are a query classification expert for automotive dealership databases.

Your job: Analyze queries and determine the best routing tier.

TIER DECISION RULES:
- Tier 1 (Direct SQL): Simple exact lookups by VIN/RO# with NO aggregation/comparison
  Example: "Show VIN X details" → Tier 1
  Example: "Average repair cost for VIN X" → Tier 3 (has aggregation!)

- Tier 2 (Pre-built Views): Common standard reports
  Example: "Monthly summary", "Dealer performance", "Warranty report" → Tier 2

- Tier 3 (Text-to-SQL RAG): Everything else (complex, custom, analytical)
  Example: "Compare H6 vs Jolion repair costs" → Tier 3
  Example: "Customer satisfaction by dealer" → Tier 3

Classify queries into these types:
- STATISTICAL: Queries with COUNT, AVG, SUM, MIN, MAX
- FILTERING: Queries with WHERE conditions
- SEMANTIC: Natural language understanding needed
- CROSS_TABLE: Requires joining multiple tables
- AGGREGATION: GROUP BY operations
- TIME_SERIES: Date-based trends or comparisons
- EXACT_LOOKUP: Find specific record by ID/VIN

Also determine:
- Complexity: simple (1 table, 1 condition) | medium (2 tables, 2-3 conditions) | complex (3+ tables, complex logic)
- Table count: single | multiple
- Requires JOIN: true/false
- Requires aggregation: true/false
- Tier: 1 (direct_sql) | 2 (prebuilt_views) | 3 (text_to_sql)

Respond ONLY with valid JSON in this format:
{
  "tier": 3,
  "query_types": ["STATISTICAL", "FILTERING"],
  "complexity": "medium",
  "table_count": "multiple",
  "requires_join": true,
  "requires_aggregation": true,
  "confidence": 0.85,
  "reasoning": "Query asks for average repair cost grouped by model, requiring RoMaster table with aggregation"
}"""

        user_prompt = f"""Classify this query:

Query: "{query}"

Extracted entities:
- VINs: {entities.vins}
- Dealer IDs: {entities.dealer_ids}
- Models: {entities.models}
- Dates: {entities.dates}
- RO Numbers: {entities.ro_numbers}

Provide classification JSON:"""

        try:
            # CALL LLM
            # ---------
            # Using grok-3-fast for classification (~$0.0001 per query, 1-2 sec)
            response = self.llm.generate(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,  # Deterministic classification (no randomness)
                max_tokens=200   # Enough for classification JSON
            )

            # PARSE LLM RESPONSE
            # -------------------
            # LLM returns JSON with tier, query_types, complexity, etc.
            # Example: {"tier": 3, "query_types": ["STATISTICAL"], ...}
            from ai.utils.json_parser import parse_llm_json

            content = response.content.strip()

            # Parse JSON robustly (handles control characters, malformed JSON)
            classification = parse_llm_json(
                response=content,
                fallback={"tier": 3, "query_type": "complex", "confidence": 0.5, "reasoning": "Parse failed, using Tier 3 fallback"},
                strict=False
            )

            # MAP TIER NUMBER TO ENUM
            # ------------------------
            # LLM returns tier as integer (1, 2, or 3)
            # Map to QueryTier enum: 1 → TIER_1, 2 → TIER_2, 3 → TIER_3
            tier_map = {
                1: QueryTier.TIER_1,
                2: QueryTier.TIER_2,
                3: QueryTier.TIER_3
            }
            tier = tier_map.get(classification.get('tier', 3), QueryTier.TIER_3)

            # Convert query type strings to enums
            # Example: ["STATISTICAL", "FILTERING"] → [QueryType.STATISTICAL, QueryType.FILTERING]
            query_types = [QueryType(qt.lower()) for qt in classification['query_types']]

            # RETURN COMPLETE ANALYSIS
            # -------------------------
            return QueryAnalysis(
                original_query=query,
                tier=tier,  # Now using LLM's tier decision
                query_types=query_types,
                entities=entities,
                complexity=classification['complexity'],
                table_count=classification['table_count'],
                requires_join=classification['requires_join'],
                requires_aggregation=classification['requires_aggregation'],
                confidence=classification['confidence'],
                reasoning=classification['reasoning']
            )

        except Exception as e:
            print(f"[RouterAgent] LLM classification error: {e}")
            # Fallback to rule-based
            return self._analyze_rule_based(query, entities)

    def _analyze_rule_based(self, query: str, entities: ExtractedEntities) -> QueryAnalysis:
        """Rule-based classification fallback (no LLM)"""
        query_lower = query.lower()
        query_types = []

        # Detect query types
        if any(word in query_lower for word in ['count', 'how many', 'number of']):
            query_types.append(QueryType.STATISTICAL)

        if any(word in query_lower for word in ['average', 'avg', 'mean', 'sum', 'total']):
            query_types.append(QueryType.STATISTICAL)
            query_types.append(QueryType.AGGREGATION)

        if any(word in query_lower for word in ['compare', 'versus', 'vs', 'difference between']):
            query_types.append(QueryType.CROSS_TABLE)

        if entities.dates:
            query_types.append(QueryType.TIME_SERIES)

        if not query_types:
            query_types.append(QueryType.SEMANTIC)

        # Determine complexity
        complexity = "simple"
        if len(query_types) > 2 or any(qt == QueryType.CROSS_TABLE for qt in query_types):
            complexity = "complex"
        elif len(query_types) == 2:
            complexity = "medium"

        # Table count
        table_count = "multiple" if QueryType.CROSS_TABLE in query_types else "single"

        return QueryAnalysis(
            original_query=query,
            tier=QueryTier.TIER_3,
            query_types=query_types,
            entities=entities,
            complexity=complexity,
            table_count=table_count,
            requires_join=(table_count == "multiple"),
            requires_aggregation=(QueryType.AGGREGATION in query_types),
            confidence=0.60,  # Lower confidence for rule-based
            reasoning="Tier 3: Rule-based classification (LLM not available or failed)"
        )

    def get_routing_decision(self, analysis: QueryAnalysis) -> Dict[str, Any]:
        """
        Get routing decision based on analysis.

        Returns dict with next steps for downstream agents.
        """
        if analysis.tier == QueryTier.TIER_1:
            return {
                "route": "direct_sql",
                "next_agent": None,
                "action": "execute_direct_sql",
                "sql_template": self._get_tier1_sql_template(analysis)
            }

        elif analysis.tier == QueryTier.TIER_2:
            return {
                "route": "prebuilt_view",
                "next_agent": None,
                "action": "execute_view",
                "view_name": self._get_tier2_view_name(analysis)
            }

        else:  # Tier 3
            return {
                "route": "text_to_sql_rag",
                "next_agent": "schema_agent",
                "action": "start_rag_pipeline",
                "use_schema_retrieval": True,
                "use_decomposition": (analysis.complexity == "complex"),
                "use_few_shot": True
            }

    def _get_tier1_sql_template(self, analysis: QueryAnalysis) -> str:
        """Generate SQL template for Tier 1 queries"""
        if analysis.entities.vins:
            vin = analysis.entities.vins[0]
            return f"SELECT * FROM RoMaster WHERE VINNO = '{vin}'"

        if analysis.entities.ro_numbers:
            ro = analysis.entities.ro_numbers[0]
            return f"SELECT * FROM RoMaster WHERE RoNo = '{ro}'"

        return "-- No template available"

    def _get_tier2_view_name(self, analysis: QueryAnalysis) -> str:
        """Get pre-built view name for Tier 2 queries"""
        # These views would be created in Phase 3
        reasoning_lower = analysis.reasoning.lower()

        if "monthly" in reasoning_lower:
            return "monthly_summary_view"
        elif "dealer performance" in reasoning_lower:
            return "dealer_performance_view"
        elif "warranty" in reasoning_lower:
            return "warranty_summary_view"
        else:
            return "general_report_view"
