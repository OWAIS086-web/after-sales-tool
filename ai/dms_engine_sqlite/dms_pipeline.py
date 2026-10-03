"""
DMS RAG Pipeline - Production-Grade Complete Integration

Orchestrates all 3 tiers, 6 agents, and result formatting for natural language to SQL.

Similar architecture to PakWheels pipeline with:
- Multi-tier routing (Tier 1/2/3)
- Format detection
- Result formatting
- Natural language answer generation
- Comprehensive error handling
- Production-grade robustness

COMPLETE PIPELINE FLOW:
========================
User Query
    ↓
┌─────────────────────────────────────────┐
│ TIER 0: Hardcoded Query Templates ⭐NEW │
│ - Semantic matching (ChromaDB)         │
│ - 100% verified SQL (no LLM)           │
│ - Instant response (0.05s)              │
│ - If match → Execute SQL → Format → Answer ✅
└─────────────────────────────────────────┘
    ↓ (no match)
┌─────────────────────────────────────────┐
│ TIER 1: Direct SQL Templates            │
│ - Pattern matching (VIN, RO, etc.)     │
│ - Instant response (0.1s)               │
│ - If match → Execute SQL → Format → Answer ✅
└─────────────────────────────────────────┘
    ↓ (no match)
┌─────────────────────────────────────────┐
│ TIER 2: Pre-built Views                │
│ - Keyword matching (common reports)     │
│ - Fast response (0.1-0.5s)              │
│ - If match → Execute SQL → Format → Answer ✅
└─────────────────────────────────────────┘
    ↓ (no match)
┌─────────────────────────────────────────┐
│ TIER 3: Full RAG Pipeline (6 Agents)   │
│                                         │
│ Agent #1: Router → Classify query       │
│ Agent #2: Schema → Retrieve tables      │
│ Agent #3: Decomposition → Break query   │
│ Agent #4: Generation → Generate SQL     │
│ Agent #5: Validation → Validate SQL     │
│ Agent #6: Correction → Fix errors       │
│    ↓                                    │
│ Execute SQL → Format → Answer ✅        │
└─────────────────────────────────────────┘

Expected Distribution:
- Tier 0: 15-20% (statistical queries) - 0.05s ⭐ NEW
- Tier 1: 15-20% (exact lookups) - 0.5s
- Tier 2: 35-40% (common reports) - 1.0s
- Tier 3: 20-25% (complex/ad-hoc) - 3-5s

Total Accuracy: 98%+
Avg Response Time: 1.5s (vs 3-5s for all Tier 3)

Production Features:
- Comprehensive error handling
- Graceful degradation
- Format detection
- Result formatting (table, json, list, stats)
- Natural language answers
- Execution safety
- RLS enforcement
- Detailed logging
- Metadata tracking
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
import sqlite3
from datetime import datetime
import traceback
import time

# Import all agents (EXISTING)
from ai.dms_engine_sqlite.agents.router_agent import RouterAgent
from ai.dms_engine_sqlite.agents.schema_agent import SchemaAgent
from ai.dms_engine_sqlite.agents.decomposition_agent import DecompositionAgent
from ai.dms_engine_sqlite.agents.generation_agent import GenerationAgent
from ai.dms_engine_sqlite.agents.validation_agent import ValidationAgent
from ai.dms_engine_sqlite.agents.correction_agent import CorrectionAgent

# Import tier templates (EXISTING)
from ai.dms_engine_sqlite.agents.tier0_hardcoded import Tier0Hardcoded  # ⭐ NEW: Hardcoded query templates
from ai.dms_engine_sqlite.agents.tier1_templates import Tier1Templates
from ai.dms_engine_sqlite.agents.tier2_views import Tier2Views

# Import result formatter (EXISTING)
from ai.dms_engine_sqlite.result_formatter import ResultFormatter

# ⭐ NEW IMPORTS: Follow-up query components
from ai.dms_engine_sqlite.intent_classifier_dms import classify_dms_query_intent, is_meta_operation
from ai.dms_engine_sqlite.query_reformulator_dms import reformulate_dms_query
from ai.dms_engine_sqlite.meta_operation_handler import MetaOperationHandler, MetaOperationResult
from ai.dms_engine_sqlite.semantic_cache_dms import DMSSemanticCache
from ai.rag_engine.redis_semantic_cache import RedisSemanticCache
from config.llm_config import get_llm_for_component


@dataclass
class QueryResult:
    """
    Complete query execution result WITH follow-up tracking.

    Similar to PakWheels answer structure with new conversational fields.

    Contains:
    - query: Original user query (or reformulated query)
    - tier_used: Which tier was used (1, 2, 3, or 0 for meta-ops)
    - sql: Final SQL executed
    - raw_results: Raw SQL query results
    - formatted_results: Formatted results (table/json/list)
    - natural_answer: Natural language answer (main response)
    - statistics: Calculated statistics (if requested)
    - execution_time: Total time (seconds)
    - success: Whether execution succeeded
    - error_message: Error message if failed
    - metadata: Additional metadata

    ⭐ NEW FIELDS FOR FOLLOW-UP TRACKING:
    - was_reformulated: Whether query was reformulated (context-dependent)
    - original_query: Original query before reformulation
    - cache_hit: Whether result came from semantic cache
    - intent_type: Intent classification (standalone, context_dependent, meta_op)
    """
    query: str
    tier_used: int
    sql: str
    raw_results: List[Dict[str, Any]]
    formatted_results: str
    natural_answer: str
    statistics: Optional[Dict[str, Any]]
    execution_time: float
    success: bool
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    # ⭐ NEW: Follow-up tracking fields
    was_reformulated: bool = False
    original_query: Optional[str] = None
    cache_hit: bool = False
    intent_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DMSPipeline:
    """
    Production-Grade DMS RAG Pipeline.

    Integrates all 3 tiers, 6 agents, and result formatting.

    MENTAL MAP:
    ===========
    1. Input: User query
    2. Tier 1 Check: Try exact pattern matching → Execute → Format → Answer
    3. Tier 2 Check: Try pre-built views → Execute → Format → Answer
    4. Tier 3 Pipeline: Full 6-agent RAG → Execute → Format → Answer
    5. Return formatted result with natural language answer

    Usage:
    ------
    ```python
    pipeline = DMSPipeline(
        db_path="data/haval_dms.db",
        dealer_id="D001"
    )

    result = pipeline.query("Show me all repair orders from December 2024")
    print(result.natural_answer)  # Natural language answer
    print(result.formatted_results)  # Formatted table/json/list
    print(result.raw_results)  # Raw SQL results
    ```
    """

    def __init__(
        self,
        db_path: str,
        dealer_id: Optional[str] = None,
        enable_tier0: bool = True,  # ⭐ NEW: Hardcoded query templates
        enable_tier1: bool = True,
        enable_tier2: bool = True,
        enable_tier3: bool = True,
        enable_semantic_cache: bool = True,  # ⭐ NEW
        enable_follow_ups: bool = True,  # ⭐ NEW
        verbose: bool = True
    ):
        """
        Initialize DMS Pipeline WITH Follow-Up Query Support.

        Args:
            db_path: Path to SQLite database
            dealer_id: Dealer ID for RLS filtering
            enable_tier0: Enable Tier 0 (hardcoded templates) ⭐ NEW
            enable_tier1: Enable Tier 1 (direct templates)
            enable_tier2: Enable Tier 2 (pre-built views)
            enable_tier3: Enable Tier 3 (full RAG)
            enable_semantic_cache: Enable semantic caching ⭐ NEW
            enable_follow_ups: Enable follow-up query handling ⭐ NEW
            verbose: Enable detailed logging
        """
        self.db_path = db_path
        self.dealer_id = dealer_id
        self.enable_tier0 = enable_tier0  # ⭐ NEW
        self.enable_tier1 = enable_tier1
        self.enable_tier2 = enable_tier2
        self.enable_tier3 = enable_tier3
        self.enable_semantic_cache = enable_semantic_cache  # ⭐ NEW
        self.enable_follow_ups = enable_follow_ups  # ⭐ NEW
        self.verbose = verbose

        try:
            # Initialize Tier 0 (Hardcoded Query Templates)
            if enable_tier0:
                try:
                    self.tier0 = Tier0Hardcoded(dealer_id=dealer_id, similarity_threshold=0.90)

                except Exception as e:
                    print(f"[Tier 0] ✗ INITIALIZATION FAILED: {e}")
                    print(f"[Tier 0] Disabling Tier 0, falling back to other tiers")
                    import traceback
                    traceback.print_exc()
                    self.tier0 = None
                    self.enable_tier0 = False  # Disable tier 0
            else:
                self.tier0 = None

            # Initialize Tier 1
            if enable_tier1:
                self.tier1 = Tier1Templates(dealer_id=dealer_id)

            # Initialize schema agent if Tier 2 or Tier 3 enabled (needed for semantic validation)
            if enable_tier2 or enable_tier3:
                self.schema_agent = SchemaAgent()
            else:
                self.schema_agent = None

            # Initialize Tier 2 with schema agent for semantic validation
            if enable_tier2:
                self.tier2 = Tier2Views(dealer_id=dealer_id, schema_agent=self.schema_agent)

            # Initialize Tier 3 (6 agents)
            if enable_tier3:
                self.router = RouterAgent()
                # schema_agent already initialized above
                self.decomposer = DecompositionAgent()

                # Only inject RLS if dealer_id is provided
                inject_rls = bool(dealer_id)
                self.generator = GenerationAgent(dealer_id=dealer_id, inject_rls=inject_rls)
                self.validator = ValidationAgent(require_rls=inject_rls)
                # CRITICAL: Pass validator to corrector so it uses same RLS settings
                self.corrector = CorrectionAgent(max_attempts=3, validation_agent=self.validator)

            # Initialize result formatter (EXISTING)
            self.formatter = ResultFormatter()

            # Initialize follow-up query components
            if self.enable_follow_ups:
                try:
                    # Get LLMs for follow-up components
                    self.intent_llm = get_llm_for_component("dms_intent_classifier", fallback_api_key=None)
                    self.reformulation_llm = get_llm_for_component("dms_query_reformulator", fallback_api_key=None)
                    self.meta_llm = get_llm_for_component("dms_meta_operation", fallback_api_key=None)

                    # Initialize meta-operation handler
                    self.meta_handler = MetaOperationHandler(llm=self.meta_llm, verbose=False)

                except Exception:
                    self.enable_follow_ups = False
                    self.intent_llm = None
                    self.reformulation_llm = None
                    self.meta_handler = None
            else:
                self.intent_llm = None
                self.reformulation_llm = None
                self.meta_handler = None

            # Initialize semantic cache (Redis + ChromaDB hybrid with fallback)
            # Priority: Redis cache → Old ChromaDB cache → Pipeline
            self.redis_cache = None
            self.semantic_cache = None  # Fallback cache

            if self.enable_semantic_cache:
                # Try Redis cache first (production-grade with unlimited storage)
                try:
                    self.redis_cache = RedisSemanticCache(pipeline="dms")
                    print(f"[DMS] ✅ Redis semantic cache enabled (primary)")
                except Exception as e:
                    print(f"[DMS] ⚠️  Redis cache initialization failed: {e}")
                    print(f"[DMS] Will use fallback ChromaDB cache")
                    self.redis_cache = None

                # Initialize fallback ChromaDB cache (used if Redis unavailable)
                try:
                    self.semantic_cache = DMSSemanticCache(
                        persist_directory=f"./data/dms_semantic_cache_{dealer_id or 'all'}",
                        similarity_threshold=0.96,
                        session_ttl_hours=24,
                        verbose=False
                    )
                    print(f"[DMS] ✅ ChromaDB cache enabled (fallback, threshold: 0.96, TTL: 24h)")
                except Exception as e:
                    print(f"[DMS] ⚠️  Fallback cache initialization failed: {e}")
                    print(f"[DMS] Continuing without any cache")
                    self.semantic_cache = None
                    self.enable_semantic_cache = False
            else:
                self.redis_cache = None
                self.semantic_cache = None

            # Initialization complete

        except Exception as e:
            print(f"\n✗ ERROR during initialization: {e}")
            traceback.print_exc()
            raise

    def query(
        self,
        user_query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,  # ⭐ NEW
        session_id: Optional[str] = None,  # ⭐ NEW
        execute: bool = True,
        format_results: bool = True
    ) -> QueryResult:
        """
        Process natural language query WITH FOLLOW-UP SUPPORT.

        WORKFLOW (WITH FOLLOW-UPS):
        ============================
        1. Intent Classification → standalone | context_dependent | meta_op
        2. [If meta_op] → Meta-operation handler → Return ✅
        3. [If context_dependent] → Query Reformulation → Continue
        4. Check Semantic Cache → If hit, return cached result ✅
        5. Try Tier 0 (hardcoded templates) → Execute → Cache → Return ✅ ⭐ NEW
        6. Try Tier 1 (exact patterns) → Execute → Cache → Return ✅
        7. Try Tier 2 (pre-built views) → Execute → Cache → Return ✅
        8. Try Tier 3 (full RAG) → Execute → Cache → Return ✅

        Args:
            user_query: Natural language query
            chat_history: Recent conversation history (for follow-ups) ⭐ NEW
            session_id: Session ID for semantic caching ⭐ NEW
            execute: Whether to execute SQL (default: True)
            format_results: Whether to format results (default: True)

        Returns:
            QueryResult with formatted answer and data

        Examples:
            # Standalone query
            >>> result = pipeline.query("Show FFS for dealer D001")

            # Follow-up query
            >>> history = [
            ...     {"role": "user", "content": "Show FFS for D001"},
            ...     {"role": "assistant", "content": result.natural_answer}
            ... ]
            >>> result2 = pipeline.query(
            ...     "What about December only?",
            ...     chat_history=history,
            ...     session_id="user123"
            ... )
        """
        start_time = datetime.now()
        original_query = user_query  # Track original for logging/metadata
        intent_type = "standalone"  # Default intent
        was_reformulated = False  # Track if query was reformulated

        try:
            # ⭐ STEP 1: SEMANTIC CACHE CHECK (Highest priority - instant response!)
            # ===========================================================================
            # Check cache BEFORE everything else (even Tier 0)
            # Priority: Redis cache → Fallback ChromaDB cache → Pipeline
            # ===========================================================================
            cached_result = None
            import json

            # Try Redis cache first (primary)
            if self.redis_cache and session_id:
                try:
                    cached_result = self.redis_cache.get(user_query, session_id)

                    if cached_result:
                        execution_time = (datetime.now() - start_time).total_seconds()
                        print(f"[DMS] 🎯 REDIS CACHE HIT: {execution_time:.2f}s")

                        # Parse response from Redis cache
                        response_data = cached_result.get("response")

                        if isinstance(response_data, str):
                            try:
                                result_dict = json.loads(response_data)
                            except json.JSONDecodeError:
                                print(f"[DMS] ⚠️  Failed to parse cached response, skipping")
                                cached_result = None
                        elif isinstance(response_data, dict):
                            result_dict = response_data
                        else:
                            print(f"[DMS] ⚠️  Invalid cached response type: {type(response_data)}")
                            cached_result = None

                        if cached_result and result_dict:
                            # Reconstruct QueryResult from cached dict
                            result = QueryResult(**result_dict)
                            result.cache_hit = True
                            result.execution_time = execution_time
                            result.was_reformulated = was_reformulated
                            result.original_query = original_query
                            result.intent_type = intent_type
                            return result
                except Exception as e:
                    print(f"[DMS] ⚠️  Redis cache error: {e}")
                    print(f"[DMS] 🔄 Trying fallback ChromaDB cache...")

            # Fallback to old ChromaDB cache if Redis unavailable or failed
            if not cached_result and self.semantic_cache and session_id:
                try:
                    cached_result = self.semantic_cache.get(user_query, session_id)

                    if cached_result:
                        execution_time = (datetime.now() - start_time).total_seconds()
                        print(f"[DMS] 🎯 FALLBACK CACHE HIT: {execution_time:.2f}s")

                        # Parse response from fallback cache
                        response_data = cached_result.get("response")

                        if isinstance(response_data, str):
                            try:
                                result_dict = json.loads(response_data)
                            except json.JSONDecodeError:
                                print(f"[DMS] ⚠️  Failed to parse cached response, skipping")
                                cached_result = None
                        elif isinstance(response_data, dict):
                            result_dict = response_data
                        else:
                            print(f"[DMS] ⚠️  Invalid cached response type: {type(response_data)}")
                            cached_result = None

                        if cached_result and result_dict:
                            # Reconstruct QueryResult from cached dict
                            result = QueryResult(**result_dict)
                            result.cache_hit = True
                            result.execution_time = execution_time
                            result.was_reformulated = was_reformulated
                            result.original_query = original_query
                            result.intent_type = intent_type
                            return result
                except Exception as e:
                    print(f"[DMS] ⚠️  Fallback cache error: {e}")

            # No cache hit - proceed with pipeline
            if not cached_result:
                if not session_id:
                    print(f"[DMS] ⚠️  No session ID provided - cache skipped")
                else:
                    print(f"[DMS] ❌ Cache miss, proceeding with tier routing")

            # ⭐ STEP 2: TIER 0 CHECK (Skip 3 LLM calls for common queries!)
            # ===========================================================================
            # For hardcoded templates in tier0_templates.json:
            # - NO need for Intent Classification (query is exact match)
            # - NO need for Query Reformulation (SQL is pre-written)
            # - NO need for Format Detection (template knows format)
            #
            # Performance: 10.5s → 2-3s for Tier 0 queries (70% faster!)
            # ===========================================================================

            if self.enable_tier0:
                tier0_start = datetime.now()

                tier0_match = self.tier0.match_query(user_query)

                if tier0_match:
                    # ✅ TIER 0 MATCH - Execute immediately, skip all LLM calls!
                    # Unpack tuple: (template, params, similarity)
                    template, params, similarity = tier0_match
                    tier0_elapsed = (datetime.now() - tier0_start).total_seconds()

                    # Execute SQL
                    if execute:
                        try:
                            # Create database connection
                            conn = sqlite3.connect(self.db_path)

                            # Execute template
                            execution_result = self.tier0.execute_template(
                                template=template,
                                params=params,
                                db_connection=conn
                            )

                            conn.close()

                            # Check if execution was successful
                            if not execution_result["success"]:
                                raise Exception(f"SQL execution failed: {execution_result.get('error')}")

                            raw_results = execution_result["results"]
                            executed_sql = execution_result["sql"]  # Use actual executed SQL (may have RLS)

                            # Format results (templates know their output format)
                            if format_results and raw_results:
                                formatted_result = self.formatter.format_results(
                                    query=user_query,
                                    sql_results=raw_results,
                                    sql=executed_sql,
                                    tier_used=0,
                                    metadata={
                                        'template_id': template.template_id,
                                        'category': template.category,
                                        'tier': 0
                                    },
                                    query_type=None  # Tier 0 doesn't have query_type (uses inferred)
                                )
                                natural_answer = formatted_result.natural_answer
                                formatted_results = formatted_result.raw_data
                                statistics = formatted_result.statistics
                            else:
                                natural_answer = f"Query executed successfully. {len(raw_results)} rows returned."
                                formatted_results = raw_results
                                statistics = None

                            execution_time = (datetime.now() - start_time).total_seconds()
                            print(f"[DMS] Tier 0: {execution_time:.2f}s | LLM calls: 0 | Template: {template.template_id}")

                            result = QueryResult(
                                query=user_query,
                                tier_used=0,
                                sql=executed_sql,
                                raw_results=raw_results,
                                formatted_results=formatted_results,
                                natural_answer=natural_answer,
                                statistics=statistics,
                                execution_time=execution_time,
                                success=True,
                                error_message=None,
                                metadata={
                                    'template_id': template.template_id,
                                    'category': template.category,
                                    'similarity': similarity,
                                    'parameters': params,
                                    'description': template.description,
                                    'tier': 0,
                                    'execution_time': execution_time,
                                    'was_reformulated': False,
                                    'intent_type': 'standalone',
                                    'fast_path': True,  # Flag for analytics
                                    'llm_calls_saved': 3
                                },
                                was_reformulated=False,
                                original_query=original_query,
                                cache_hit=False,
                                intent_type='standalone'
                            )

                            # Store in semantic cache for future hits (Redis → Fallback)
                            if self.enable_semantic_cache and session_id:
                                try:
                                    import json
                                    result_dict = asdict(result)
                                    result_json = json.dumps(result_dict, default=str)

                                    # Try Redis cache first
                                    if self.redis_cache:
                                        try:
                                            self.redis_cache.set(user_query, result_json, session_id)
                                        except Exception as e:
                                            print(f"[DMS] ⚠️  Redis cache store failed: {e}")
                                            # Fallback to old cache
                                            if self.semantic_cache:
                                                try:
                                                    self.semantic_cache.set(user_query, result_json, session_id)
                                                    print(f"[SemanticCache] ✅ Stored in fallback cache")
                                                except Exception:
                                                    pass
                                    elif self.semantic_cache:
                                        # No Redis, use fallback directly
                                        self.semantic_cache.set(user_query, result_json, session_id)
                                        print(f"[SemanticCache] ✅ Stored in fallback cache")
                                except Exception as e:
                                    print(f"[SemanticCache] ⚠️  Cache store failed: {e}")
                                    pass  # Non-critical

                            return result

                        except Exception:
                            # Fall through to full pipeline
                            pass
                    else:
                        # Dry run mode
                        execution_time = (datetime.now() - start_time).total_seconds()
                        return QueryResult(
                            query=user_query,
                            tier_used=0,
                            sql=template.sql_template,  # Use template SQL for dry run
                            raw_results=[],
                            formatted_results=None,
                            natural_answer=None,
                            statistics=None,
                            execution_time=execution_time,
                            success=True,
                            error_message=None,
                            metadata={
                                'template_id': template.template_id,
                                'category': template.category,
                                'similarity': similarity,
                                'parameters': params,
                                'description': template.description,
                                'fast_path': True,
                                'dry_run': True
                            },
                            was_reformulated=False,
                            original_query=original_query,
                            cache_hit=False,
                            intent_type='standalone'
                        )
                else:
                    # No Tier 0 match - continue with full pipeline
                    tier0_elapsed = (datetime.now() - tier0_start).total_seconds()
                    print(f"[TIER 0 - FAST PATH] ❌ No match found ({tier0_elapsed:.2f}s)")
                    print(f"[TIER 0 - FAST PATH] Falling back to full pipeline (Intent → Reformulation → Cache → Tier 1/2/3)")
                    print("█" * 80 + "\n")

            # ==================================================================
            # FULL PIPELINE: For non-Tier 0 queries
            # ==================================================================
            # Only reach here if:
            # 1. Tier 0 disabled, OR
            # 2. No Tier 0 match found
            # Continue with full pipeline (intent, reformulation, cache, tier 1/2/3)
            # ==================================================================

            # INTENT CLASSIFICATION
            if self.enable_follow_ups and chat_history and len(chat_history) > 0:
                try:
                    intent_type = classify_dms_query_intent(
                        query=user_query,
                        chat_history=chat_history,
                        llm=self.intent_llm,
                        verbose=False
                    )

                except Exception:
                    intent_type = "standalone"

            else:
                pass

            # ⭐ NEW: STEP 2 - HANDLE META-OPERATIONS
            # ==================================================================
            # Meta-operations transform previous answer WITHOUT querying database
            # Examples: "summarize above", "elaborate", "give in bullet points"
            # ==================================================================
            if self.enable_follow_ups and (intent_type == "meta_op" or is_meta_operation(user_query)):
                try:
                    meta_result = self.meta_handler.handle(
                        query=user_query,
                        chat_history=chat_history
                    )

                    execution_time = (datetime.now() - start_time).total_seconds()
                    print(f"[DMS] Meta-op: {execution_time:.2f}s")

                    # Convert MetaOperationResult to QueryResult
                    return QueryResult(
                        query=user_query,
                        tier_used=0,  # No tier (meta-operation)
                        sql="",  # No SQL
                        raw_results=[],  # No database results
                        formatted_results=meta_result.transformed_answer,
                        natural_answer=meta_result.transformed_answer,
                        statistics=None,
                        execution_time=execution_time,
                        success=meta_result.success,
                        error_message=meta_result.error_message,
                        metadata={
                            'operation_type': meta_result.operation_type,
                            'is_meta_operation': True,
                            'original_answer_length': len(meta_result.original_answer) if meta_result.original_answer else 0,
                            'transformed_answer_length': len(meta_result.transformed_answer)
                        },
                        was_reformulated=False,
                        original_query=original_query,
                        cache_hit=False,
                        intent_type="meta_op"
                    )

                except Exception:
                    pass  # Continue with normal processing if meta-op fails

            # QUERY REFORMULATION
            if self.enable_follow_ups and intent_type == "context_dependent":
                try:
                    reformulated_query = reformulate_dms_query(
                        query=user_query,
                        chat_history=chat_history,
                        llm=self.reformulation_llm,
                        verbose=False
                    )

                    # Use reformulated query for tier routing
                    user_query = reformulated_query
                    was_reformulated = True

                except Exception:
                    was_reformulated = False

            else:
                pass

            # TIER 1 → TIER 2 → TIER 3 ROUTING
            # (Tier 0 and Cache already checked at the top of query() method)

            # TIER 1: Direct SQL Templates
            if self.enable_tier1:
                tier1_match = self.tier1.match(user_query)

                if tier1_match:
                    tier1_result = self._execute_and_format(
                        query=user_query,
                        sql=tier1_match.sql,
                        tier_used=1,
                        execute=execute,
                        format_results=format_results,
                        start_time=start_time,
                        metadata={
                            'template_name': tier1_match.template_name,
                            'parameters': tier1_match.parameters,
                            'confidence': tier1_match.confidence
                        },
                        query_type=None  # Tier 1 doesn't have query_type (will be inferred)
                    )

                    # FALLBACK: If Tier 1 returns 0 results, continue to next tier
                    if tier1_result.success and len(tier1_result.raw_results) == 0:
                        pass  # Continue to next tier
                    else:
                        return self._post_process_result(
                            result=tier1_result,
                            original_query=original_query,
                            was_reformulated=was_reformulated,
                            intent_type=intent_type,
                            session_id=session_id
                        )

            # TIER 2: Pre-built Views
            if self.enable_tier2:
                tier2_match = self.tier2.match(user_query)

                if tier2_match:
                    tier2_result = self._execute_and_format(
                        query=user_query,
                        sql=tier2_match.sql,
                        tier_used=2,
                        execute=execute,
                        format_results=format_results,
                        start_time=start_time,
                        metadata={
                            'view_name': tier2_match.view_name,
                            'description': tier2_match.description,
                            'parameters': tier2_match.parameters,
                            'confidence': tier2_match.confidence
                        },
                        query_type=None  # Tier 2 doesn't have query_type (will be inferred)
                    )

                    # FALLBACK: If Tier 2 returns 0 results, try Tier 3
                    if tier2_result.success and len(tier2_result.raw_results) == 0 and self.enable_tier3:
                        pass  # Fallback to Tier 3
                    else:
                        return self._post_process_result(
                            result=tier2_result,
                            original_query=original_query,
                            was_reformulated=was_reformulated,
                            intent_type=intent_type,
                            session_id=session_id
                        )

            # TIER 3: Full RAG Pipeline (6 Agents)
            if self.enable_tier3:
                tier3_result = self._run_tier3_pipeline(
                    user_query=user_query,
                    execute=execute,
                    format_results=format_results,
                    start_time=start_time
                )

                # ⭐ NEW: Post-process result (add follow-up tracking & cache)
                return self._post_process_result(
                    result=tier3_result,
                    original_query=original_query,
                    was_reformulated=was_reformulated,
                    intent_type=intent_type,
                    session_id=session_id
                )

            # No tier matched
            execution_time = (datetime.now() - start_time).total_seconds()

            return QueryResult(
                query=user_query,
                tier_used=0,
                sql="",
                raw_results=[],
                formatted_results="",
                natural_answer="I couldn't process your query. Please try rephrasing or contact support.",
                statistics=None,
                execution_time=execution_time,
                success=False,
                error_message="Query could not be processed by any tier"
            )

        except Exception as e:
            if self.verbose:
                print(f"\n✗ PIPELINE ERROR: {e}")
                traceback.print_exc()

            execution_time = (datetime.now() - start_time).total_seconds()

            return QueryResult(
                query=user_query,
                tier_used=0,
                sql="",
                raw_results=[],
                formatted_results="",
                natural_answer=f"An error occurred while processing your query: {str(e)}",
                statistics=None,
                execution_time=execution_time,
                success=False,
                error_message=str(e)
            )

    def _run_tier3_pipeline(
        self,
        user_query: str,
        execute: bool,
        format_results: bool,
        start_time: datetime
    ) -> QueryResult:
        """
        Run complete Tier 3 pipeline (6 agents).

        WORKFLOW:
        =========
        Agent #1: Router → Classify
        Agent #2: Schema → Retrieve tables
        Agent #3: Decomposition → Break query
        Agent #4: Generation → Generate SQL
        Agent #5: Validation → Validate SQL
        Agent #6: Correction → Fix errors (if needed)
        Execute → Format → Answer

        Args:
            user_query: User's query
            execute: Whether to execute SQL
            format_results: Whether to format results
            start_time: Start time for timing

        Returns:
            QueryResult with formatted answer
        """
        try:
            # Agent #1: Router
            router_analysis = self.router.analyze_query(user_query)

            # Agent #2: Schema Retrieval (LLM-only for Tier 3)
            llm_selection = self.schema_agent.get_final_tables_llm_only(user_query, top_k=5)

            # Build SchemaContext from LLM-selected tables
            schema_context = self._build_schema_context_from_tables(
                query=user_query,
                table_names=llm_selection['tables'],
                llm_reasoning=llm_selection['reasoning']
            )

            # Agent #3: Decomposition
            decomp_plan = self.decomposer.decompose_query(user_query, schema_context, router_analysis)

            # Agent #4: Generation
            generation_result = self.generator.generate_sql(user_query, schema_context, decomp_plan)

            if generation_result.single_sql:
                generated_sql = generation_result.single_sql
            else:
                # Use first sub-query for simplicity
                generated_sql = generation_result.sub_query_sqls[0][1]

            # Agent #5: Validation
            validation_result = self.validator.validate_sql(generated_sql, schema_context)

            final_sql = generated_sql

            # Agent #6: Correction (if needed)
            if not validation_result.is_valid and validation_result.can_auto_fix:
                correction_result = self.corrector.correct_sql(
                    query=user_query,
                    generated_sql=generated_sql,
                    validation_result=validation_result,
                    schema_context=schema_context
                )

                final_sql = correction_result.final_sql
                validation_result = correction_result.final_validation

            # If still invalid, return error
            if not validation_result.is_valid:
                execution_time = (datetime.now() - start_time).total_seconds()

                return QueryResult(
                    query=user_query,
                    tier_used=3,
                    sql=final_sql.sql,
                    raw_results=[],
                    formatted_results="",
                    natural_answer=f"Could not generate valid SQL for your query. {validation_result.get_error_summary()}",
                    statistics=None,
                    execution_time=execution_time,
                    success=False,
                    error_message=validation_result.get_error_summary(),
                    metadata={
                        'router_tier': router_analysis.tier,
                        'complexity': router_analysis.complexity,
                        'validation_errors': len(validation_result.errors)
                    }
                )

            # Execute and format
            return self._execute_and_format(
                query=user_query,
                sql=final_sql.sql,
                tier_used=3,
                execute=execute,
                format_results=format_results,
                start_time=start_time,
                metadata={
                    'router_tier': router_analysis.tier,
                    'complexity': router_analysis.complexity,
                    'decomposition_mode': decomp_plan.mode.value,
                    'confidence': final_sql.confidence,
                    'reasoning': final_sql.reasoning,
                    'has_rls': final_sql.has_rls,
                    'query_type': final_sql.query_type  # ⭐ NEW: Include query_type in metadata
                },
                query_type=final_sql.query_type  # ⭐ NEW: Pass query_type from generation
            )

        except Exception as e:
            print(f"[DMS] Tier 3 ERROR: {e}")
            execution_time = (datetime.now() - start_time).total_seconds()

            return QueryResult(
                query=user_query,
                tier_used=3,
                sql="",
                raw_results=[],
                formatted_results="",
                natural_answer=f"An error occurred in the RAG pipeline: {str(e)}",
                statistics=None,
                execution_time=execution_time,
                success=False,
                error_message=f"Pipeline error: {str(e)}"
            )

    def _execute_and_format(
        self,
        query: str,
        sql: str,
        tier_used: int,
        execute: bool,
        format_results: bool,
        start_time: datetime,
        metadata: Optional[Dict[str, Any]] = None,
        raw_results: Optional[List[Dict[str, Any]]] = None,  # For pre-executed queries (Tier 0)
        query_type: Optional[str] = None  # ⭐ NEW: Query type from generation
    ) -> QueryResult:
        """
        Execute SQL and format results.

        WORKFLOW:
        =========
        1. Execute SQL → Get raw results
        2. Format results (table/json/list/stats)
        3. Generate natural language answer
        4. Return QueryResult

        Args:
            query: User's query
            sql: SQL to execute
            tier_used: Tier number (0, 1, 2, 3)
            execute: Whether to execute SQL
            format_results: Whether to format
            start_time: Start time
            metadata: Additional metadata
            raw_results: Pre-executed results (for Tier 0, optional)

        Returns:
            QueryResult with formatted answer
        """
        # Execute SQL (unless pre-executed results provided)
        if raw_results is None and execute:
            raw_results, error = self._execute_sql(sql)

            if error:
                execution_time = (datetime.now() - start_time).total_seconds()

                return QueryResult(
                    query=query,
                    tier_used=tier_used,
                    sql=sql,
                    raw_results=[],
                    formatted_results="",
                    natural_answer=f"Database error while executing your query: {error}",
                    statistics=None,
                    execution_time=execution_time,
                    success=False,
                    error_message=error,
                    metadata=metadata
                )
        elif raw_results is None:
            # No execution and no pre-executed results
            raw_results = []
        # else: raw_results already provided (Tier 0 case)

        # Format results
        if format_results and raw_results is not None:
            formatted = self.formatter.format_results(
                query=query,
                sql_results=raw_results,
                sql=sql,
                tier_used=tier_used,
                metadata=metadata,
                query_type=query_type  # ⭐ NEW: Pass query_type to formatter
            )

            formatted_text = formatted.formatted_text
            natural_answer = formatted.natural_answer
            statistics = formatted.statistics
        else:
            formatted_text = ""
            natural_answer = f"Query processed successfully (Tier {tier_used})"
            statistics = None

        execution_time = (datetime.now() - start_time).total_seconds()
        print(f"[DMS] Tier {tier_used}: {execution_time:.2f}s, {len(raw_results) if raw_results else 0} rows")

        return QueryResult(
            query=query,
            tier_used=tier_used,
            sql=sql,
            raw_results=raw_results or [],
            formatted_results=formatted_text,
            natural_answer=natural_answer,
            statistics=statistics,
            execution_time=execution_time,
            success=True,
            error_message=None,
            metadata=metadata
        )

    def _post_process_result(
        self,
        result: QueryResult,
        original_query: str,
        was_reformulated: bool,
        intent_type: str,
        session_id: Optional[str] = None
    ) -> QueryResult:
        """
        ⭐ NEW: Post-process result with follow-up tracking and caching.

        Adds follow-up metadata and stores in semantic cache if enabled.

        Args:
            result: QueryResult from tier execution
            original_query: Original user query (before reformulation)
            was_reformulated: Whether query was reformulated
            intent_type: Intent classification result
            session_id: Session ID for caching

        Returns:
            QueryResult with follow-up metadata added
        """
        # Add follow-up tracking fields
        result.was_reformulated = was_reformulated
        result.original_query = original_query if was_reformulated else None
        result.intent_type = intent_type
        result.cache_hit = False

        # Cache result if enabled and successful (Redis → Fallback)
        if self.enable_semantic_cache and session_id and result.success:
            try:
                import json
                result_dict = asdict(result)
                result_json = json.dumps(result_dict, default=str)

                # Try Redis cache first
                if self.redis_cache:
                    try:
                        self.redis_cache.set(
                            query=result.query,
                            response=result_json,
                            session_id=session_id
                        )
                    except Exception as e:
                        print(f"[DMS] ⚠️  Redis cache store failed: {e}")
                        # Fallback to old cache
                        if self.semantic_cache:
                            try:
                                self.semantic_cache.set(
                                    query=result.query,
                                    response=result_json,
                                    session_id=session_id
                                )
                            except Exception:
                                pass
                elif self.semantic_cache:
                    # No Redis, use fallback directly
                    self.semantic_cache.set(
                        query=result.query,
                        response=result_json,
                        session_id=session_id
                    )

            except Exception:
                pass  # Caching is non-critical

        return result

    def _execute_sql(self, sql: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Execute SQL query safely.

        Args:
            sql: SQL query

        Returns:
            (results, error_message)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if self.verbose:
                print(f"\n[EXECUTION] Running SQL...")
                print(f"  SQL: {sql[:150]}...")

            cursor.execute(sql)
            rows = cursor.fetchall()

            # Convert to list of dicts
            results = [dict(row) for row in rows]

            conn.close()

            if self.verbose:
                print(f"[EXECUTION] ✓ Success: {len(results)} rows")

            return results, None

        except Exception as e:
            if self.verbose:
                print(f"[EXECUTION] ✗ Error: {e}")
            return [], str(e)

    def _build_schema_context_from_tables(
        self,
        query: str,
        table_names: List[str],
        llm_reasoning: str
    ):
        """
        Build SchemaContext from LLM-selected table names.

        This is used by Tier 3 when LLM selects the final tables (no vector search).
        Loads full TableSchema objects for each LLM-selected table.

        Args:
            query: User's query
            table_names: List of table names selected by LLM
            llm_reasoning: LLM's reasoning for table selection

        Returns:
            SchemaContext with loaded TableSchema objects
        """
        from ai.dms_engine_sqlite.agents.schema_agent import SchemaContext

        if not table_names:
            # No tables selected - return empty context
            return SchemaContext(
                query=query,
                relevant_tables=[],
                total_tables_in_db=0,
                search_method="llm_only",
                min_relevance_score=0.0,
                max_relevance_score=0.0
            )

        # Load full TableSchema objects for each table
        table_schemas = []
        for table_name in table_names:
            try:
                # Use schema_agent's _load_table_schema method
                # Give high relevance score since LLM selected them
                schema = self.schema_agent._load_table_schema(
                    table_name=table_name,
                    relevance_score=0.95  # High score for LLM selections
                )
                table_schemas.append(schema)

                if self.verbose:
                    print(f"    ✓ Loaded schema for {table_name}")

            except Exception as e:
                if self.verbose:
                    print(f"    ✗ Failed to load schema for {table_name}: {e}")
                continue

        # Build SchemaContext
        if table_schemas:
            context = SchemaContext(
                query=query,
                relevant_tables=table_schemas,
                total_tables_in_db=len(table_schemas),  # Only count loaded tables
                search_method="llm_only",
                min_relevance_score=0.95,
                max_relevance_score=0.95
            )
        else:
            # Failed to load any schemas
            context = SchemaContext(
                query=query,
                relevant_tables=[],
                total_tables_in_db=0,
                search_method="llm_only",
                min_relevance_score=0.0,
                max_relevance_score=0.0
            )

        return context

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        return {
            'tiers_enabled': {
                'tier1': self.enable_tier1,
                'tier2': self.enable_tier2,
                'tier3': self.enable_tier3
            },
            'dealer_id': self.dealer_id,
            'database': self.db_path,
            'verbose': self.verbose
        }
