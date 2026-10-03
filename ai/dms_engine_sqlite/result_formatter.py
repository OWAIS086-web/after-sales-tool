"""
Result Formatter

Converts SQL results to natural language answers with proper formatting.

Similar to PakWheels pipeline format detection and answer generation.

FEATURES:
=========
1. FORMAT DETECTION: Detect user's preferred format (table, json, list, statistics, chart)
2. RESULT FORMATTING: Format SQL results based on detected format
3. STATISTICS GENERATION: Calculate stats if requested
4. NATURAL LANGUAGE: Convert to conversational answer

Production-Grade Features:
- Handles empty results gracefully
- Supports multiple output formats
- Statistical analysis
- Natural language generation
- Context-aware responses
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
from enum import Enum
import re

from config.llm_config import get_llm_for_component, DMS_ANSWER_TOKEN_LIMITS


# TABLE BUSINESS NAME MAPPING
# Maps technical database table names to natural language business names
# Used for answer transparency layer to show data sources
TABLE_BUSINESS_NAMES = {
    'RoMaster': 'Repair Orders',
    'PDIMaster': 'PDI Reports',
    'PDIDetails': 'PDI Details',
    'PDIQMS': 'PDI Quality Management',
    'PDIQMSDetail': 'PDI Quality Details',
    'CancleWaranty': 'Cancelled Warranties',
    'CSR': 'Customer Service Records',
    'CSIMaster': 'Customer Satisfaction Surveys',
    'DealerRegister': 'Dealership Directory',
    'DealerReport': 'Dealership Reports',
    'Vehicleinf': 'Vehicle Information',
    'Campaigns': 'Service Campaigns',
    'CampaignRpt': 'Campaign Reports',
    'SFSMaster': 'SFS Records',
    'SFSDetails': 'SFS Details',
    'FFSMaster': 'FFS Records',
    # Add lowercase versions for case-insensitive matching
    'romaster': 'Repair Orders',
    'pdimaster': 'PDI Reports',
    'pdidetails': 'PDI Details',
    'pdiqms': 'PDI Quality Management',
    'pdiqmsdetail': 'PDI Quality Details',
    'canclewaranty': 'Cancelled Warranties',
    'csr': 'Customer Service Records',
    'csimaster': 'Customer Satisfaction Surveys',
    'dealerregister': 'Dealership Directory',
    'dealerreport': 'Dealership Reports',
    'vehicleinf': 'Vehicle Information',
    'campaigns': 'Service Campaigns',
    'campaignrpt': 'Campaign Reports',
    'sfsmaster': 'SFS Records',
    'sfsdetails': 'SFS Details',
    'ffsmaster': 'FFS Records',
}


class OutputFormat(Enum):
    """Detected output format preference"""
    TABLE = "table"          # Markdown table
    JSON = "json"            # JSON format
    LIST = "list"            # Bullet list
    STATISTICS = "statistics" # Stats/numbers
    CHART = "chart"          # Chart data
    NATURAL = "natural"      # Natural language (default)


@dataclass
class FormattedResult:
    """
    Formatted query result.

    Contains:
    - raw_data: Original SQL results
    - format: Detected format
    - formatted_text: Formatted output
    - statistics: Calculated statistics (if requested)
    - natural_answer: Natural language answer
    """
    raw_data: List[Dict[str, Any]]
    format: OutputFormat
    formatted_text: str
    statistics: Optional[Dict[str, Any]]
    natural_answer: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'raw_data': self.raw_data,
            'format': self.format.value,
            'formatted_text': self.formatted_text,
            'statistics': self.statistics,
            'natural_answer': self.natural_answer
        }


class ResultFormatter:
    """
    Formats SQL results into natural language answers.

    MENTAL MAP:
    ===========
    1. Detect format preference from query
    2. Format SQL results accordingly
    3. Calculate statistics if needed
    4. Generate natural language answer
    5. Return formatted result

    Similar to PakWheels format detection + answer generation.
    """

    def __init__(self):
        """Initialize Result Formatter"""
        # LLM for format detection
        self.format_detector_llm = get_llm_for_component("dms_format_detector")

        # LLM for answer generation
        self.answer_llm = get_llm_for_component("dms_answer_generation")

        # Token limits from config
        self.token_limits = DMS_ANSWER_TOKEN_LIMITS

        print(f"[ResultFormatter] Initialized")
        print(f"  Token limits: brief={self.token_limits['brief']}, moderate={self.token_limits['moderate']}, detailed={self.token_limits['detailed']}")

    def _extract_table_names_from_sql(self, sql: str) -> List[str]:
        """
        Extract table names from SQL query.

        Uses regex to find table names in FROM and JOIN clauses.

        Args:
            sql: SQL query string

        Returns:
            List of table names found in the query
        """
        table_names = set()

        # Remove comments and normalize whitespace
        sql_clean = re.sub(r'--[^\n]*', '', sql)  # Remove single-line comments
        sql_clean = re.sub(r'/\*.*?\*/', '', sql_clean, flags=re.DOTALL)  # Remove multi-line comments
        sql_clean = re.sub(r'\s+', ' ', sql_clean).strip()  # Normalize whitespace

        # Pattern 1: FROM table_name (with optional alias)
        # Matches: FROM TableName, FROM TableName AS alias, FROM TableName alias
        from_pattern = r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        from_matches = re.findall(from_pattern, sql_clean, re.IGNORECASE)
        table_names.update(from_matches)

        # Pattern 2: JOIN table_name (with optional alias)
        # Matches: JOIN TableName, INNER JOIN TableName, LEFT JOIN TableName, etc.
        join_pattern = r'\b(?:INNER\s+|LEFT\s+|RIGHT\s+|FULL\s+|OUTER\s+|CROSS\s+)?JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        join_matches = re.findall(join_pattern, sql_clean, re.IGNORECASE)
        table_names.update(join_matches)

        # Remove common SQL keywords that might be captured
        sql_keywords = {'SELECT', 'WHERE', 'GROUP', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET', 'AS', 'ON', 'AND', 'OR', 'NOT', 'IN', 'EXISTS', 'BETWEEN', 'LIKE', 'IS', 'NULL', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END'}
        table_names = {name for name in table_names if name.upper() not in sql_keywords}

        return list(table_names)

    def _get_data_sources_text(self, sql: str) -> Optional[str]:
        """
        Generate data sources transparency text from SQL.

        Extracts table names from SQL and maps them to business names.
        Returns natural language description of data sources used.

        Args:
            sql: SQL query string

        Returns:
            Transparency text like "Based on Repair Orders and PDI Reports"
            Returns None if no tables found or can't generate text
        """
        try:
            # Extract table names
            table_names = self._extract_table_names_from_sql(sql)

            if not table_names:
                return None

            # Map to business names
            business_names = []
            for table_name in table_names:
                # Try exact match first
                business_name = TABLE_BUSINESS_NAMES.get(table_name)

                # Try case-insensitive match
                if not business_name:
                    business_name = TABLE_BUSINESS_NAMES.get(table_name.lower())

                # If found, add to list
                if business_name and business_name not in business_names:
                    business_names.append(business_name)

            if not business_names:
                return None

            # Generate natural language text
            if len(business_names) == 1:
                return f"*Based on {business_names[0]}*"
            elif len(business_names) == 2:
                return f"*Based on {business_names[0]} and {business_names[1]}*"
            else:
                # More than 2 tables
                last_name = business_names[-1]
                other_names = ", ".join(business_names[:-1])
                return f"*Based on {other_names}, and {last_name}*"

        except Exception as e:
            print(f"[ResultFormatter] Error generating data sources text: {e}")
            return None

    def format_results(
        self,
        query: str,
        sql_results: List[Dict[str, Any]],
        sql: str,
        tier_used: int,
        metadata: Optional[Dict[str, Any]] = None,
        query_type: Optional[str] = None  # ⭐ NEW: Query type for context-aware formatting
    ) -> FormattedResult:
        """
        Format SQL results into natural language answer.

        WORKFLOW:
        =========
        1. DETECT FORMAT
           - Analyze query for format preferences
           - table, json, list, statistics, chart, natural

        2. FORMAT RESULTS
           - Empty results → "No results found"
           - Table format → Markdown table
           - JSON format → JSON string
           - List format → Bullet list
           - Statistics → Calculate stats
           - Natural → Conversational answer

        3. CALCULATE STATISTICS (if requested)
           - Count, sum, avg, min, max
           - Percentages, ratios

        4. GENERATE NATURAL LANGUAGE ANSWER
           - Use LLM to create conversational response
           - Include formatted data
           - Add insights if available

        Args:
            query: User's original query
            sql_results: SQL query results
            sql: SQL query executed
            tier_used: Which tier was used (1, 2, 3)
            metadata: Optional metadata

        Returns:
            FormattedResult with all formatting
        """
        print(f"\n[ResultFormatter] Formatting results...")
        print(f"  Row count: {len(sql_results)}")
        print(f"  Tier used: {tier_used}")

        # ===================================================================
        # STEP 0: EXTRACT QUERY TYPE (with robust fallback)
        # ===================================================================
        # Priority 1: Use provided query_type parameter
        # Priority 2: Extract from metadata
        # Priority 3: Infer from result structure
        # Priority 4: Fallback to "listing"
        if query_type:
            final_query_type = query_type
            print(f"  Query type (provided): {final_query_type}")

            # ⭐ ENSURE QUERY TYPE IS IN METADATA
            if metadata is None:
                metadata = {}
            metadata['query_type'] = final_query_type

        elif metadata and 'query_type' in metadata:
            final_query_type = metadata['query_type']
            print(f"  Query type (from metadata): {final_query_type}")
        else:
            # Fallback: Infer from result structure
            final_query_type = self._infer_query_type_from_results(sql_results, sql)
            print(f"  Query type (inferred): {final_query_type}")

            # ⭐ ADD INFERRED QUERY TYPE TO METADATA so it gets passed back to pipeline
            if metadata is None:
                metadata = {}
            metadata['query_type'] = final_query_type

        # STEP 1: DETECT FORMAT
        # ---------------------
        format_pref = self._detect_format(query)
        print(f"  Detected format: {format_pref.value}")

        # STEP 2: FORMAT RESULTS
        # ----------------------
        if not sql_results:
            # Empty results
            formatted_text = "No results found for your query."
            statistics = None
            natural_answer = self._generate_empty_result_answer(query, sql, tier_used)

        else:
            # Format based on preference
            if format_pref == OutputFormat.TABLE:
                formatted_text = self._format_as_table(sql_results)
            elif format_pref == OutputFormat.JSON:
                formatted_text = self._format_as_json(sql_results)
            elif format_pref == OutputFormat.LIST:
                formatted_text = self._format_as_list(sql_results)
            elif format_pref == OutputFormat.STATISTICS:
                formatted_text, statistics = self._format_as_statistics(sql_results)
            else:  # NATURAL or CHART
                formatted_text = self._format_as_table(sql_results)  # Default to table

            # STEP 3: CALCULATE STATISTICS (if needed)
            # -----------------------------------------
            if format_pref == OutputFormat.STATISTICS or 'stat' in query.lower() or 'total' in query.lower():
                if format_pref != OutputFormat.STATISTICS:
                    statistics = self._calculate_statistics(sql_results)
            else:
                statistics = None

            # STEP 4: GENERATE NATURAL LANGUAGE ANSWER
            # -----------------------------------------
            natural_answer = self._generate_natural_answer(
                query=query,
                sql_results=sql_results,
                formatted_text=formatted_text,
                statistics=statistics,
                tier_used=tier_used,
                metadata=metadata,
                sql=sql,
                query_type=final_query_type  # ⭐ NEW: Pass query_type for context-aware prompting
            )

        print(f"[ResultFormatter] Formatting complete")

        return FormattedResult(
            raw_data=sql_results,
            format=format_pref,
            formatted_text=formatted_text,
            statistics=statistics,
            natural_answer=natural_answer
        )

    def _infer_query_type_from_results(self, sql_results: List[Dict[str, Any]], sql: str) -> str:
        """
        Infer query type from result structure when not provided (robust fallback).

        This is a FALLBACK method used when query_type is not available from
        the Generation Agent or metadata.

        Logic:
        1. If 1 row with aggregate column names (Total, Count, Avg, Sum, etc.) → "aggregate"
        2. If multiple rows with aggregate column names → "hybrid"
        3. Otherwise → "listing"

        Args:
            sql_results: SQL query results
            sql: SQL query string (for additional hints)

        Returns:
            Inferred query type: "aggregate", "hybrid", or "listing"
        """
        try:
            if not sql_results or len(sql_results) == 0:
                # Empty results - default to listing
                return "listing"

            # Check result structure
            row_count = len(sql_results)
            first_row = sql_results[0]
            column_names = list(first_row.keys()) if first_row else []

            # Aggregate column name patterns
            aggregate_patterns = [
                'total', 'count', 'sum', 'avg', 'average', 'min', 'max',
                'unique', 'distinct', 'rate', 'percentage', 'ratio'
            ]

            # Check if columns have aggregate names
            has_aggregate_cols = any(
                any(pattern in col.lower() for pattern in aggregate_patterns)
                for col in column_names
            )

            # Additional hint from SQL structure
            sql_upper = sql.upper() if sql else ""
            has_group_by_in_sql = 'GROUP BY' in sql_upper

            # INFERENCE LOGIC
            if row_count == 1 and has_aggregate_cols and not has_group_by_in_sql:
                # Single row with aggregate column → likely aggregate query
                print(f"[ResultFormatter] Inferred 'aggregate': 1 row with aggregate columns {column_names}")
                return "aggregate"
            elif row_count > 1 and has_aggregate_cols:
                # Multiple rows with aggregate columns → likely hybrid (grouped)
                print(f"[ResultFormatter] Inferred 'hybrid': {row_count} rows with aggregate columns")
                return "hybrid"
            else:
                # Multiple rows without clear aggregate pattern → listing
                print(f"[ResultFormatter] Inferred 'listing': {row_count} rows, no aggregate pattern")
                return "listing"

        except Exception as e:
            print(f"[ResultFormatter] ERROR inferring query type: {e}")
            return "listing"  # Ultimate fallback

    def _detect_format(self, query: str) -> OutputFormat:
        """
        Detect user's preferred output format using LLM.

        Similar to PakWheels pipeline - uses LLM call instead of regex.

        Args:
            query: User's query

        Returns:
            Detected OutputFormat
        """
        system_prompt = """You are a format detection specialist.

Analyze the user's query and determine their preferred output format.

OUTPUT FORMATS:
1. **table or summary** - User wants data in tabular/grid format or summary
   Keywords: "table", "tabular", "summary", "grid", "show in table format", "show in 100 words summary", "identify", "show", "list vehicles", "which vehicles", "which VINs"

2. **json** - User wants raw JSON/API format
   Keywords: "json", "api", "raw data", "export"

3. **list or bullet points** - User wants bullet/numbered list
   Keywords: "list", "bullet points", "enumerate"

4. **statistics** - User wants statistical summary (counts, averages, percentages ONLY)
   Keywords: "statistics", "stats", "breakdown", "totals", "averages", "how many", "count"

5. **chart** - User wants chart/graph data
   Keywords: "chart", "graph", "plot", "visualize", "trend"

6. **natural** - User wants conversational answer (DEFAULT)
   Keywords: No specific format requested, asking questions

RULES:
- If query says "identify", "show", "list" + entities (vehicles/VINs/dealerships) → "table" (user wants to see the actual records)
- If query asks for statistics/numbers/totals/counts ONLY → "statistics"
- If query explicitly mentions a format, return that format
- If query is a simple question → "natural"
- When in doubt → "natural"

RESPOND WITH ONLY ONE WORD: table, json, list, statistics, chart, or natural"""

        user_prompt = f"""Query: "{query}"

Preferred format:"""

        try:
            response = self.format_detector_llm.generate(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                max_tokens=10
            )

            detected = response.content.strip().lower()

            # Map to enum
            format_map = {
                'table': OutputFormat.TABLE,
                'json': OutputFormat.JSON,
                'list': OutputFormat.LIST,
                'statistics': OutputFormat.STATISTICS,
                'chart': OutputFormat.CHART,
                'natural': OutputFormat.NATURAL
            }

            return format_map.get(detected, OutputFormat.NATURAL)

        except Exception as e:
            print(f"[ResultFormatter] ERROR in format detection: {e}")
            # Fallback to natural
            return OutputFormat.NATURAL

    def _format_as_table(self, results: List[Dict[str, Any]]) -> str:
        """Format results as markdown table"""
        if not results:
            return "No data to display."

        # Get columns from first row
        columns = list(results[0].keys())

        # Build markdown table
        header = "| " + " | ".join(columns) + " |"
        separator = "|" + "|".join([" --- " for _ in columns]) + "|"

        rows = []
        for row in results[:50]:  # Limit to 50 rows
            row_values = [str(row.get(col, "")) for col in columns]
            rows.append("| " + " | ".join(row_values) + " |")

        table = "\n".join([header, separator] + rows)

        if len(results) > 50:
            table += f"\n\n*Showing first 50 of {len(results)} rows*"

        return table

    def _format_as_json(self, results: List[Dict[str, Any]]) -> str:
        """Format results as JSON"""
        return json.dumps(results, indent=2, default=str)

    def _format_as_list(self, results: List[Dict[str, Any]]) -> str:
        """Format results as bullet list"""
        if not results:
            return "No items to list."

        # Get primary column (first non-id column)
        columns = list(results[0].keys())
        primary_col = next((col for col in columns if 'id' not in col.lower()), columns[0])

        lines = []
        for i, row in enumerate(results[:50], 1):
            value = row.get(primary_col, "")
            # Include other key columns
            extras = [f"{k}: {v}" for k, v in row.items() if k != primary_col and v]
            if extras:
                lines.append(f"{i}. **{value}** ({', '.join(extras[:3])})")
            else:
                lines.append(f"{i}. {value}")

        if len(results) > 50:
            lines.append(f"\n*Showing first 50 of {len(results)} items*")

        return "\n".join(lines)

    def _format_as_statistics(self, results: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
        """Format results with statistics"""
        stats = self._calculate_statistics(results)

        # Build statistics text
        lines = ["📊 **Statistics:**\n"]
        lines.append(f"- **Total Records**: {stats['total_count']}")

        if stats['numeric_columns']:
            lines.append(f"\n**Numeric Summaries:**")
            for col, col_stats in stats['numeric_columns'].items():
                lines.append(f"\n  **{col}**:")
                lines.append(f"  - Sum: {col_stats['sum']:,.2f}")
                lines.append(f"  - Average: {col_stats['avg']:,.2f}")
                lines.append(f"  - Min: {col_stats['min']:,.2f}")
                lines.append(f"  - Max: {col_stats['max']:,.2f}")

        if stats['categorical_columns']:
            lines.append(f"\n**Categorical Summaries:**")
            for col, counts in list(stats['categorical_columns'].items())[:3]:
                lines.append(f"\n  **{col}** (Top 5):")
                for value, count in list(counts.items())[:5]:
                    lines.append(f"  - {value}: {count}")

        return "\n".join(lines), stats

    def _calculate_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics from results"""
        if not results:
            return {'total_count': 0, 'numeric_columns': {}, 'categorical_columns': {}}

        stats = {
            'total_count': len(results),
            'numeric_columns': {},
            'categorical_columns': {}
        }

        # Get columns
        columns = list(results[0].keys())

        for col in columns:
            # Check if numeric
            values = [row.get(col) for row in results if row.get(col) is not None]

            if not values:
                continue

            # Try numeric stats
            try:
                numeric_values = [float(v) for v in values if isinstance(v, (int, float))]

                if numeric_values:
                    stats['numeric_columns'][col] = {
                        'sum': sum(numeric_values),
                        'avg': sum(numeric_values) / len(numeric_values),
                        'min': min(numeric_values),
                        'max': max(numeric_values),
                        'count': len(numeric_values)
                    }
                    continue
            except (ValueError, TypeError):
                pass

            # Categorical stats
            value_counts = {}
            for v in values:
                v_str = str(v)
                value_counts[v_str] = value_counts.get(v_str, 0) + 1

            # Sort by count
            sorted_counts = dict(sorted(value_counts.items(), key=lambda x: x[1], reverse=True))
            stats['categorical_columns'][col] = sorted_counts

        return stats

    def _generate_natural_answer(
        self,
        query: str,
        sql_results: List[Dict[str, Any]],
        formatted_text: str,
        statistics: Optional[Dict[str, Any]],
        tier_used: int,
        metadata: Optional[Dict[str, Any]],
        sql: str = "",
        query_type: str = "listing"  # ⭐ NEW: Query type for context-aware prompting
    ) -> str:
        """
        Generate natural language answer using LLM with dynamic detail level.

        ADAPTIVE DETAIL LEVELS:
        - Simple queries (1-10 results) → Brief answer
        - Analysis queries (stats/trends) → Detailed insights
        - Large results (>50 rows) → Summary with key stats
        - Lookups (VIN, RO) → Direct factual answer

        TRANSPARENCY LAYER:
        - Automatically extracts table names from SQL
        - Maps them to business names
        - Appends "Based on [data sources]" to answer

        Args:
            query: User's query
            sql_results: SQL results
            formatted_text: Formatted data
            statistics: Calculated statistics
            tier_used: Tier used (1, 2, 3)
            metadata: Additional metadata
            sql: SQL query executed (for transparency)

        Returns:
            Natural language answer with transparency suffix
        """
        # STEP 1: DETERMINE QUERY TYPE & DETAIL LEVEL
        # --------------------------------------------
        query_type_from_classifier = self._classify_query_type(query)
        detail_level = self._determine_detail_level(sql_results, statistics, query_type_from_classifier)

        # STEP 2: BUILD CONTEXT
        # ---------------------
        context_parts = []

        # Add formatted data (adaptive based on size)
        if len(sql_results) <= 10:
            # Small result set - include all data
            context_parts.append(f"**Query Results:**\n{formatted_text}")
        else:
            # Large result set - include sample + stats
            sample_data = self._format_as_table(sql_results[:10])
            context_parts.append(f"**Sample Results (first 10 of {len(sql_results)}):**\n{sample_data}")

        # Add statistics if available
        if statistics:
            stats_text = f"\n**Statistics:**\n"
            stats_text += f"- Total records: {statistics['total_count']}\n"

            if statistics['numeric_columns']:
                for col, col_stats in list(statistics['numeric_columns'].items())[:3]:
                    stats_text += f"- {col}: Sum={col_stats['sum']:,.0f}, Avg={col_stats['avg']:,.2f}\n"

            context_parts.append(stats_text)

        context = "\n\n".join(context_parts)

        # STEP 3: BUILD DYNAMIC SYSTEM PROMPT
        # ------------------------------------
        # Use the query_type from SQL generation (more reliable than old classifier)
        system_prompt = self._build_adaptive_system_prompt(query_type_from_classifier=query_type_from_classifier, detail_level=detail_level, sql_query_type=query_type)

        # STEP 4: GENERATE ANSWER
        # -----------------------
        user_prompt = f"""**User Question:** {query}

**Data Retrieved:**
{context}

Provide a clear, conversational answer to the user's question based on this data:"""

        try:
            response = self.answer_llm.generate(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=self._get_max_tokens(detail_level)
            )

            natural_answer = response.content.strip()

        except Exception as e:
            print(f"[ResultFormatter] ERROR generating answer: {e}")
            # Fallback to formatted text
            natural_answer = f"Here are the results for your query:\n\n{formatted_text}"

        # STEP 5: ADD TRANSPARENCY SUFFIX
        # --------------------------------
        # Add data sources transparency to show which tables were used
        if sql:
            data_sources_text = self._get_data_sources_text(sql)
            if data_sources_text:
                natural_answer = f"{natural_answer}\n\n{data_sources_text}"

        return natural_answer

    def _classify_query_type(self, query: str) -> str:
        """
        Classify query type to determine answer style.

        Types:
        - lookup: Simple entity lookup (VIN, RO number)
        - count: Counting/totals
        - analysis: Trends, patterns, insights
        - comparison: Comparing entities
        - list: List of items

        Args:
            query: User's query

        Returns:
            Query type
        """
        query_lower = query.lower()

        # Lookup queries
        if any(kw in query_lower for kw in ['show', 'find', 'get', 'history of', 'details of']):
            return 'lookup'

        # Count/total queries
        if any(kw in query_lower for kw in ['how many', 'count', 'total', 'number of']):
            return 'count'

        # Analysis queries
        if any(kw in query_lower for kw in ['trend', 'pattern', 'analysis', 'insight', 'top', 'bottom', 'most', 'least', 'average']):
            return 'analysis'

        # Comparison queries
        if any(kw in query_lower for kw in ['compare', 'vs', 'versus', 'difference', 'between']):
            return 'comparison'

        # List queries
        if any(kw in query_lower for kw in ['list', 'all', 'show me']):
            return 'list'

        return 'general'

    def _determine_detail_level(
        self,
        sql_results: List[Dict[str, Any]],
        statistics: Optional[Dict[str, Any]],
        query_type: str
    ) -> str:
        """
        Determine detail level for answer.

        Levels:
        - brief: 1-2 sentences, direct answer
        - moderate: 3-5 sentences, some context
        - detailed: 5+ sentences, insights, trends

        Args:
            sql_results: SQL results
            statistics: Statistics
            query_type: Query type

        Returns:
            Detail level
        """
        result_count = len(sql_results)

        # Simple lookups → Brief
        if query_type == 'lookup' and result_count <= 5:
            return 'brief'

        # Counts → Brief
        if query_type == 'count':
            return 'brief'

        # Analysis/comparison → Detailed
        if query_type in ['analysis', 'comparison']:
            return 'detailed'

        # Large results → Detailed summary
        if result_count > 50:
            return 'detailed'

        # Statistics present → Detailed
        if statistics and statistics.get('numeric_columns'):
            return 'detailed'

        # Default → Moderate
        return 'moderate'

    def _build_adaptive_system_prompt(self, query_type_from_classifier: str, detail_level: str, sql_query_type: str = "listing") -> str:
        """
        Build system prompt adapted to query type and detail level.

        Args:
            query_type_from_classifier: Old classifier query type (lookup, count, analysis, etc.)
            detail_level: Detail level (brief, moderate, detailed)
            sql_query_type: Query type from SQL structure (aggregate, hybrid, listing) - THIS IS THE PRIORITY

        Returns:
            System prompt
        """
        # Use SQL query type as primary classifier
        query_type = sql_query_type

        base_prompt = """You are an expert data analyst for Haval automotive dealership management system.

Your job: Convert SQL query results into clear, conversational answers.

CORE RULES:
===========
1. **Be Conversational**: Write like talking to a business manager
2. **Use Numbers**: Include specific counts, totals, averages
3. **Format Nicely**: Use markdown (bold, lists, etc.)
4. **No Fluff**: Don't say "According to the data..." or "Based on the results..."
5. **Direct Answers**: Start with the answer, then add details

⚠️ CRITICAL - READ DATA ACCURATELY (MOST IMPORTANT):
====================================================
**YOU MUST READ THE RAW SQL RESULTS EXACTLY AS PROVIDED. DO NOT HALLUCINATE OR MISREAD DATA.**

1. **Row 1 is THE ANSWER**: If query asks "which dealership has most X?", Row 1 contains the answer
   - ❌ WRONG: "I don't have the specific name tied to this figure"
   - ✅ RIGHT: Read Row 1's DealerName field directly

2. **DO NOT SWAP VALUES**: Read column names carefully
   - If Row 1 shows: {'DealerName': 'HBGujranwalaMotors', 'PDICount': 2715}
   - ❌ WRONG: "HavalCentralMotors has 2,715 PDI reports"
   - ✅ RIGHT: "HBGujranwalaMotors has 2,715 PDI reports"

3. **COUNT QUERIES**: If raw results show COUNT(*) or aggregate, USE THAT NUMBER DIRECTLY
   - If query is "how many X?" and result shows {'TotalX': 5000}
   - ❌ WRONG: Counting rows returned or summing aggregates
   - ✅ RIGHT: "There are 5,000 X"

4. **GROUPED RESULTS**: If SQL has GROUP BY, results show TOP N, not the total
   - If 10 rows returned with LIMIT 10, don't say "total is X"
   - ✅ RIGHT: "Top 10 dealerships are..." or sum clearly states it's from top 10

5. **READ EVERY FIELD CAREFULLY**:
   - Look at the exact column names in raw results
   - Match values to the correct entities
   - Don't confuse dealers, customers, or VINs

⚠️ CRITICAL - TEMPORAL FILTERING ACCURACY (PREVENT DATE HALLUCINATION):
=======================================================================
**BEFORE MENTIONING ANY TIME PERIOD IN YOUR ANSWER, CHECK IF SQL ACTUALLY FILTERED BY THAT PERIOD.**

**THE PROBLEM:**
User asks "Total campaigns in September 2025" → SQL has NO date filter → Returns ALL campaigns ever
→ ❌ You say "11,881 campaigns in September 2025" (HALLUCINATION!)
→ ✅ You should say "11,881 campaigns across all time"

**HOW TO CHECK SQL FOR TEMPORAL FILTERS:**
Look in the WHERE clause for ANY of these patterns:
- Year filter: `strftime('%Y', Date) = '2025'` or `Year = 2025`
- Month filter: `strftime('%Y-%m', Date) = '2025-09'` or `Month = 9 AND Year = 2025`
- Date range: `Date BETWEEN '2025-01-01' AND '2025-12-31'`
- Date comparison: `Date >= '2025-01-01'` or `Date > date('now', '-1 year')`
- Relative periods: `strftime('%Y', Date) = strftime('%Y', 'now')` (this year)
- Week/Quarter: Any strftime or date arithmetic

**IF NO TEMPORAL FILTER FOUND:**
- SQL only has: `WHERE 1=1` or `WHERE JobRequest LIKE '%warranty%'` or `WHERE DealerName IS NOT NULL`
- → This means ALL TIME / ENTIRE DATABASE
- → Say "across all time" or "in total" or "historically" - DO NOT mention specific years/months from the query!

**EXAMPLES:**

Example 1 - NO DATE FILTER (Hallucination):
Query: "Total warranty claims"
SQL: `SELECT COUNT(*) FROM RoMaster WHERE JobRequest LIKE '%warranty%'`
Result: {'TotalClaims': 1364}
❌ WRONG: "There are 1,364 warranty claims in 2025"
✅ RIGHT: "There are 1,364 warranty claims across all time"

Example 2 - HAS YEAR FILTER (Correct):
Query: "Total warranty claims in 2025"
SQL: `SELECT COUNT(*) FROM RoMaster WHERE JobRequest LIKE '%warranty%' AND strftime('%Y', Date) = '2025'`
Result: {'TotalClaims': 850}
✅ RIGHT: "There are 850 warranty claims in 2025"

Example 3 - HAS MONTH FILTER (Correct):
Query: "Campaigns in September 2025"
SQL: `SELECT COUNT(*) FROM CampaignRpt WHERE strftime('%Y-%m', RDate) = '2025-09'`
Result: {'TotalCampaigns': 920}
✅ RIGHT: "There are 920 campaigns in September 2025"

Example 4 - NO DATE FILTER but query mentions month (Hallucination):
Query: "show me the count of all PDI reports"
SQL: `SELECT * FROM PDIMaster WHERE Status LIKE '%objection%'`
Result: 50 rows
❌ WRONG: "50 PDI reports with objections from January 2025"
✅ RIGHT: "50 PDI reports with objections across all time"

Example 5 - Relative period filter (Correct):
Query: "Repair orders this year"
SQL: `SELECT COUNT(*) FROM RoMaster WHERE strftime('%Y', Date) = strftime('%Y', 'now')`
Result: {'TotalOrders': 2500}
✅ RIGHT: "There are 2,500 repair orders this year (2026)"

**RULE: When in doubt, check the SQL WHERE clause. If no temporal filter → say "all time".**

⚠️ CRITICAL - QUERY TYPE-SPECIFIC INSTRUCTIONS:
=================================================
**THIS QUERY IS TYPE: {query_type}**

"""

        # ===================================================================
        # QUERY TYPE-SPECIFIC INSTRUCTIONS (HIGHEST PRIORITY)
        # ===================================================================
        if query_type == "aggregate":
            base_prompt += """
🔴 AGGREGATE QUERY - CRITICAL RULES:
====================================
The SQL returned a SINGLE ROW with AGGREGATE VALUE(S).

**ROW 1 IS THE ANSWER:**
- The result contains 1 row with column(s) like: Total, Count, UniqueVINs, Average, Sum, etc.
- DO NOT count the number of rows (there's only 1 row)
- READ THE COLUMN VALUES from that single row

**EXAMPLES:**

Example 1 - Simple count:
Query: "How many repair orders?"
Result: [{'TotalOrders': 12345}]  ← ONE ROW
❌ WRONG: "I found 1 repair order"
✅ RIGHT: "There are 12,345 repair orders in the database"

Example 2 - Distinct count:
Query: "What are the total unique VIN numbers in RO Master?"
Result: [{'UniqueVINs': 28896}]  ← ONE ROW
❌ WRONG: "I found 1 unique VIN"
❌ WRONG: "Based on the sample, there are approximately 28,896 VINs"
✅ RIGHT: "There are 28,896 unique VINs in the RO Master table"

Example 3 - Multiple aggregates:
Query: "Total campaigns and average success rate"
Result: [{'TotalCampaigns': 1200, 'AvgSuccessRate': 92.5}]  ← ONE ROW
❌ WRONG: "I found 1 campaign"
✅ RIGHT: "There are 1,200 campaigns with an average success rate of 92.5%"

Example 4 - Zero count:
Query: "How many warranty claims in 2030?"
Result: [{'TotalClaims': 0}]  ← ONE ROW
✅ RIGHT: "There are 0 warranty claims in 2030 (future date - no records yet)"

**IF YOU SEE 1 ROW WITH AGGREGATE COLUMNS → READ THE VALUES, DON'T COUNT THE ROWS**
"""
        elif query_type == "hybrid":
            base_prompt += """
🟡 HYBRID QUERY (GROUPED AGGREGATES) - CRITICAL RULES:
======================================================
The SQL returned MULTIPLE ROWS with GROUP + AGGREGATE columns.

**EACH ROW = ONE GROUP:**
- Each row represents a category/group (dealer, month, model, etc.)
- Each row has group identifier + aggregate value(s)
- Row count = number of groups (NOT total entities)

**RANKING QUERIES:**
- If SQL has "ORDER BY ... DESC LIMIT 10" → these are "TOP 10"
- Even if query said "which dealership" (singular), we show top 10 for comparison

**EXAMPLES:**

Example 1 - Dealership ranking:
Query: "Which dealership has most repairs?"
Result: [
  {'DealerName': 'HB Gujranwala', 'RepairCount': 2715},
  {'DealerName': 'Haval Central', 'RepairCount': 1850},
  ...10 rows total
]
✅ RIGHT: "Top 10 dealerships by repair count:
1. HB Gujranwala Motors - 2,715 repairs
2. Haval Central Motors - 1,850 repairs
..."

Example 2 - Monthly trend:
Query: "Show repair trends by month"
Result: [
  {'Month': '2024-01', 'Total': 1200},
  {'Month': '2024-02', 'Total': 1350},
  ...12 rows (one per month)
]
✅ RIGHT: "Monthly repair order trends:
- January 2024: 1,200 orders
- February 2024: 1,350 orders (↑12.5%)
..."

**READ EACH ROW'S GROUP AND AGGREGATE VALUES. SHOW ALL GROUPS.**
"""
        else:  # listing
            base_prompt += """
🟢 LISTING QUERY - CRITICAL RULES:
===================================
The SQL returned ACTUAL ENTITY ROWS (not aggregates).

**EACH ROW = ONE ENTITY:**
- These are actual records from the database
- Row count = number of entities found
- Show identifying information (VIN, customer name, date, etc.)

**SAMPLING:**
- If many rows (>50), you may see "Showing first 50 of 1,245"
- Acknowledge this in your answer

**EXAMPLES:**

Example 1 - VIN history:
Query: "Show repair history for VIN NF9FF6A58N2000096"
Result: [
  {'RoNo': 'RO-001', 'Date': '2024-12-15', 'Issue': 'Oil change'},
  {'RoNo': 'RO-045', 'Date': '2024-10-20', 'Issue': 'Tire replacement'},
  ...8 rows total
]
✅ RIGHT: "Found 8 repair orders for VIN NF9FF6A58N2000096:
1. December 15, 2024 (RO-001): Oil change
2. October 20, 2024 (RO-045): Tire replacement
..."

Example 2 - List with sampling:
Query: "Show all repair orders in December"
Result: 1,245 rows (sample of 50 shown)
✅ RIGHT: "Found 1,245 repair orders in December 2024. Here are the first 50:
[Shows table]
*Showing first 50 of 1,245 orders*"

**SHOW THE ACTUAL ENTITY DETAILS. IF MANY ROWS, ACKNOWLEDGE SAMPLING.**
"""

        # Add detail-specific instructions
        if detail_level == 'brief':
            base_prompt += """DETAIL LEVEL: BRIEF
==================
- 1-2 sentences maximum
- Direct factual answer only
- No additional insights unless critical
- Just answer the question

Example:
User: "How many repair orders?"
Answer: "There are **1,245 repair orders** in the database."
"""

        elif detail_level == 'moderate':
            base_prompt += """DETAIL LEVEL: MODERATE
=====================
- 3-5 sentences
- Direct answer + some key details
- Mention top 1-2 insights if obvious
- Keep it focused

Example:
User: "Show repair orders from December"
Answer: "There are **1,245 repair orders** from December 2024.

**Key Details:**
- Total revenue: PKR 2.5M
- Average cost: PKR 2,000
- Top dealership: Haval Central (350 orders)"
"""

        else:  # detailed
            base_prompt += """DETAIL LEVEL: DETAILED
=====================
- 5-8 sentences
- Direct answer + comprehensive details
- Highlight patterns, trends, anomalies
- Add business insights
- Compare if relevant data exists

**TREND ANALYSIS (CRITICAL):**
- If data contains time-based columns (Date, Month, Year, strftime output), ALWAYS analyze temporal patterns
- Calculate changes between periods (month-over-month, year-over-year)
- Identify which entities are increasing, declining, or stable
- Use actual data to determine trends, don't make assumptions
- Example: If data shows CSI scores for multiple months → Compare scores across months to find declining dealerships

Example:
User: "Analyze repair trends"
Answer: "There are **1,245 repair orders** in December 2024, showing a **15% increase** from November.

**Key Trends:**
- Engine repairs increased 25% (45% of all orders)
- Average repair cost up by PKR 200 to PKR 2,000
- Haval Central led with 350 orders (28% of total)

**Insights:**
- The spike in engine repairs correlates with H6 model deliveries in October-November
- Customer satisfaction remained high at 4.2/5 despite higher volumes
- Weekend service requests doubled, indicating customer preference shift"
"""

        # Add old classifier query-type hints (secondary context)
        if query_type_from_classifier == 'lookup':
            base_prompt += "\n**Context: Lookup Query** - Present facts clearly. If multiple items, use bullet list.\n"
        elif query_type_from_classifier == 'analysis':
            base_prompt += "\n**Context: Analysis Query** - Focus on insights, patterns, and trends. Explain what the numbers mean.\n"
        elif query_type_from_classifier == 'comparison':
            base_prompt += "\n**Context: Comparison Query** - Clearly show differences. Use percentages and ratios.\n"
        elif query_type_from_classifier == 'count':
            base_prompt += "\n**Context: Count Query** - Give the number prominently. Add context only if detail level allows.\n"

        return base_prompt

    def _get_max_tokens(self, detail_level: str) -> int:
        """Get max tokens based on detail level from config"""
        return self.token_limits.get(detail_level, self.token_limits['moderate'])

    def _generate_empty_result_answer(self, query: str, sql: str, tier_used: int) -> str:
        """Generate answer for empty results"""
        return f"""No results found for your query.

**Possible reasons:**
- The specified filters didn't match any records
- The time period has no data
- The combination of criteria is too restrictive

Try:
- Broadening your search criteria
- Checking different time periods
- Verifying entity names (VIN, dealer, etc.)"""
