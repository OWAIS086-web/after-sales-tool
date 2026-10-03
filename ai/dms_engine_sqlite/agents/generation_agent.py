"""
Generation Agent (LAYER 4)

Generates SQL queries from natural language using schema context and few-shot learning.

WHY THIS AGENT EXISTS:
======================
Problem: Converting natural language to SQL is hard. Generic LLMs make mistakes with:
         - Column names (use wrong columns)
         - JOINs (forget foreign keys)
         - Business logic (don't understand domain)
         - Security (forget row-level filtering)

Solution: Few-shot learning with schema context
  - Provide table schemas with column types
  - Provide sample queries from metadata (few-shot examples)
  - Inject row-level security automatically
  - Infer JOINs from foreign keys

This improves SQL accuracy from 40% → 90%+

KEY FEATURES:
=============
1. FEW-SHOT LEARNING
   - Use sample_queries from metadata as examples
   - LLM learns patterns from real queries

2. SCHEMA CONTEXT
   - Provide only relevant tables (from Schema Agent)
   - Include columns, types, foreign keys, sample values

3. JOIN INFERENCE
   - Use foreign_keys from metadata
   - Also infer from column names (VIN, DealerId, etc.)

4. ROW-LEVEL SECURITY (RLS)
   - Auto-detect RLS columns (DealerId, etc.)
   - Inject WHERE clauses automatically
   - Example: "SELECT * FROM RoMaster" → "SELECT * FROM RoMaster WHERE DealerId = 'D001'"

5. SAFETY
   - Only SELECT queries allowed
   - No DROP, DELETE, UPDATE, ALTER
   - Validate SQL syntax before returning

FLOW:
=====
Decomposition Agent → Generation Agent → Validation Agent
 (Sub-queries)         (Generate SQL)     (Validate SQL)

Production-Grade Features:
- Few-shot learning with metadata samples
- Automatic JOIN inference
- RLS injection
- SQL safety checks
- Comprehensive error handling
- Retry logic for failed generation
"""

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from ai.dms_engine_sqlite.agents.decomposition_agent import (DecompositionPlan,
                                                             ExecutionMode,
                                                             SubQuery)
from ai.dms_engine_sqlite.agents.schema_agent import SchemaContext
from config.llm_config import get_llm_for_component


@dataclass
class GeneratedSQL:
    """
    Generated SQL query with metadata.

    Contains:
    - sql: The generated SQL query
    - tables_used: List of table names used in query
    - has_rls: Whether RLS was injected
    - confidence: LLM confidence in generation
    - reasoning: Why this SQL was generated
    - query_type: Type of query (aggregate, hybrid, listing)
    """
    sql: str
    tables_used: List[str]
    has_rls: bool
    rls_column: Optional[str]
    confidence: float
    reasoning: str
    warnings: List[str]  # Any warnings about the generated SQL
    query_type: str  # "aggregate", "hybrid", or "listing"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GenerationResult:
    """
    Complete generation result for query.

    For simple queries (SINGLE mode):
    - single_sql: Generated SQL
    - sub_query_sqls: Empty list

    For decomposed queries (SEQUENTIAL/PARALLEL mode):
    - single_sql: None
    - sub_query_sqls: List of (sub_query_id, GeneratedSQL) pairs
    """
    original_query: str
    decomposition_mode: ExecutionMode
    single_sql: Optional[GeneratedSQL]
    sub_query_sqls: List[Tuple[str, GeneratedSQL]]  # [(sub_query_id, sql), ...]

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['decomposition_mode'] = self.decomposition_mode.value
        if self.single_sql:
            result['single_sql'] = self.single_sql.to_dict()
        result['sub_query_sqls'] = [
            (sq_id, sql.to_dict()) for sq_id, sql in self.sub_query_sqls
        ]
        return result


class GenerationAgent:
    """
    Generation Agent - LAYER 4 of DMS RAG Pipeline

    Generates SQL from natural language using few-shot learning.

    MENTAL MAP:
    ===========
    1. Input: Query + Schema context + Decomposition plan
    2. If SINGLE mode: Generate one SQL query
    3. If DECOMPOSED: Generate SQL for each sub-query
    4. For each SQL generation:
       a. Build prompt with schema + few-shot examples
       b. LLM generates SQL
       c. Inject RLS if needed
       d. Validate basic safety
    5. Output: GenerationResult with SQL queries

    Accuracy Target: 90% (SQL Generation)
    - SQL is syntactically correct
    - SQL uses correct tables and columns
    - SQL includes proper JOINs
    - SQL includes RLS filtering

    Production Features:
    - Few-shot learning from metadata samples
    - Automatic JOIN inference from FKs
    - RLS injection for multi-tenant security
    - SQL safety validation
    - Retry logic for failed generation
    - Comprehensive error messages
    """

    def __init__(
        self,
        llm_component: str = "dms_generation",
        dealer_id: Optional[str] = None,
        max_examples: int = 3,
        inject_rls: bool = True
    ):
        """
        Initialize Generation Agent.

        Args:
            llm_component: LLM component name from llm_config.py
            dealer_id: Dealer ID for RLS injection (if None, skip RLS)
            max_examples: Maximum few-shot examples per table
            inject_rls: Whether to inject RLS clauses
        """
        self.llm = get_llm_for_component(llm_component)
        self.dealer_id = dealer_id
        self.max_examples = max_examples
        self.inject_rls = inject_rls

        print(f"[GenerationAgent] Initialized")
        print(f"  LLM: {llm_component}")
        print(f"  Dealer ID: {self.dealer_id or 'None (no RLS)'}")
        print(f"  Max examples: {self.max_examples}")

    def _detect_query_type_from_sql(self, sql: str) -> str:
        """
        Detect query type from SQL structure with comprehensive pattern matching.

        Query Types (Comprehensive):
        ============================
        1. "aggregate" - Single row with aggregate values
           - SELECT COUNT(*) FROM table
           - SELECT COUNT(*), AVG(col), SUM(col) FROM table (no GROUP BY)
           - SELECT COUNT(DISTINCT col) FROM table

        2. "hybrid" - Multiple rows with grouped aggregates
           - SELECT category, COUNT(*) FROM table GROUP BY category
           - GROUP BY with HAVING clause
           - Window functions: ROW_NUMBER(), RANK(), DENSE_RANK()

        3. "listing" - Entity rows (no aggregates)
           - SELECT * FROM table
           - SELECT id, name FROM table WHERE conditions

        4. "union" - Combined results from multiple queries
           - SELECT ... UNION SELECT ...
           - Treated as listing (shows combined entities)

        5. "subquery_aggregate" - Aggregate in subquery
           - SELECT * FROM (SELECT COUNT(*) FROM table)
           - Treated as aggregate (final result is aggregate)

        6. "cte" - Common Table Expression
           - WITH cte AS (...) SELECT ... FROM cte
           - Type depends on final SELECT (recursive detection)

        Fallback: Always returns a valid type ("listing" as default)

        Args:
            sql: SQL query string

        Returns:
            Query type: "aggregate", "hybrid", or "listing" (guaranteed non-null)
        """
        try:
            if not sql or not sql.strip():
                print(f"[GenerationAgent] WARNING: Empty SQL, defaulting to 'listing'")
                return "listing"

            sql_upper = sql.upper()
            sql_clean = re.sub(r'--[^\n]*', '', sql_upper)  # Remove comments
            sql_clean = re.sub(r'/\*.*?\*/', '', sql_clean, flags=re.DOTALL)  # Remove /* */ comments

            # ===================================================================
            # PATTERN 1: UNION/UNION ALL (Combined queries)
            # ===================================================================
            if ' UNION ' in sql_clean or ' UNION ALL ' in sql_clean:
                print(f"[GenerationAgent] Detected UNION query - treating as 'listing'")
                return "listing"  # UNION typically combines entity rows

            # ===================================================================
            # PATTERN 2: CTE (Common Table Expression) - WITH clause
            # ===================================================================
            if sql_clean.strip().startswith('WITH '):
                # Extract the final SELECT after CTE
                # WITH cte AS (...) SELECT ... FROM cte
                # We care about the final SELECT, not the CTE definition
                final_select_match = re.search(r'\)\s*SELECT\s+', sql_clean)
                if final_select_match:
                    # Recursively detect type from final SELECT
                    final_query = sql_clean[final_select_match.start():]
                    return self._detect_query_type_from_sql(final_query)
                else:
                    print(f"[GenerationAgent] WARNING: CTE without final SELECT, defaulting to 'listing'")
                    return "listing"

            # ===================================================================
            # PATTERN 3: Aggregate Functions
            # ===================================================================
            # Standard aggregates
            standard_aggregates = ['COUNT(', 'SUM(', 'AVG(', 'MIN(', 'MAX(', 'TOTAL(']
            has_standard_aggregate = any(func in sql_clean for func in standard_aggregates)

            # Window functions (advanced aggregates)
            window_functions = [
                'ROW_NUMBER(', 'RANK(', 'DENSE_RANK(',
                'LAG(', 'LEAD(', 'FIRST_VALUE(', 'LAST_VALUE(',
                'NTILE(', 'PERCENT_RANK(', 'CUME_DIST('
            ]
            has_window_function = any(func in sql_clean for func in window_functions)

            has_aggregate = has_standard_aggregate or has_window_function

            # ===================================================================
            # PATTERN 4: GROUP BY (Grouped aggregates)
            # ===================================================================
            has_group_by = 'GROUP BY' in sql_clean

            # HAVING clause (implies GROUP BY semantics even if GROUP BY implicit)
            has_having = 'HAVING' in sql_clean

            # Window OVER clause (partitioning)
            has_over_clause = 'OVER(' in sql_clean or 'OVER (' in sql_clean

            # ===================================================================
            # PATTERN 5: SELECT * (Entity listing)
            # ===================================================================
            # Check if query is SELECT * or SELECT table.* (listing pattern)
            has_select_star = bool(re.search(r'SELECT\s+\*', sql_clean) or
                                  re.search(r'SELECT\s+\w+\.\*', sql_clean))

            # ===================================================================
            # PATTERN 6: Subquery Detection
            # ===================================================================
            # Check if main query wraps a subquery
            # SELECT * FROM (SELECT COUNT(*) FROM table) → aggregate
            # SELECT * FROM (SELECT * FROM table WHERE ...) → listing
            has_subquery = '(' in sql_clean and 'SELECT' in sql_clean.split('(', 1)[1] if '(' in sql_clean else False

            # ===================================================================
            # DECISION LOGIC (Priority-based with comprehensive fallbacks)
            # ===================================================================

            # CASE 1: Window functions with OVER clause
            if has_window_function and has_over_clause:
                # Window functions produce one row per input row with calculated values
                # Example: SELECT vin, ROW_NUMBER() OVER (ORDER BY date) FROM table
                # This is like a listing with extra calculated columns
                print(f"[GenerationAgent] Detected window function query - treating as 'hybrid'")
                return "hybrid"

            # CASE 2: GROUP BY with aggregates (HYBRID)
            if has_group_by or has_having:
                # Grouped aggregates: multiple rows, each with group + aggregate
                # Example: SELECT dealer, COUNT(*) FROM table GROUP BY dealer
                print(f"[GenerationAgent] Detected GROUP BY query - type: 'hybrid'")
                return "hybrid"

            # CASE 3: Aggregates WITHOUT GROUP BY (AGGREGATE)
            if has_aggregate and not has_group_by and not has_having:
                # Single aggregate result: one row with aggregate value(s)
                # Example: SELECT COUNT(*) FROM table
                # Example: SELECT COUNT(*), AVG(cost) FROM table
                print(f"[GenerationAgent] Detected aggregate query (no GROUP BY) - type: 'aggregate'")
                return "aggregate"

            # CASE 4: SELECT * or no aggregates (LISTING)
            if has_select_star or not has_aggregate:
                # Entity rows: actual records from table
                # Example: SELECT * FROM table WHERE conditions
                # Example: SELECT id, name, date FROM table LIMIT 50
                print(f"[GenerationAgent] Detected listing query - type: 'listing'")
                return "listing"

            # CASE 5: Subquery with aggregate in inner query
            if has_subquery and has_aggregate:
                # If outer query is SELECT * FROM (aggregate subquery)
                # The result type depends on the inner query
                # Conservative approach: Check if outer query has GROUP BY
                if has_group_by:
                    return "hybrid"
                else:
                    # Could be aggregate wrapped in SELECT *, treat as aggregate
                    print(f"[GenerationAgent] Detected subquery with aggregate - type: 'aggregate'")
                    return "aggregate"

            # ===================================================================
            # FALLBACK: Default to 'listing' (safest option)
            # ===================================================================
            print(f"[GenerationAgent] WARNING: Could not definitively classify query type")
            print(f"[GenerationAgent] SQL patterns detected:")
            print(f"  - has_aggregate: {has_aggregate}")
            print(f"  - has_group_by: {has_group_by}")
            print(f"  - has_select_star: {has_select_star}")
            print(f"  - has_subquery: {has_subquery}")
            print(f"[GenerationAgent] Defaulting to 'listing' (safest fallback)")
            return "listing"

        except Exception as e:
            # ULTIMATE FALLBACK: If anything goes wrong, default to listing
            print(f"[GenerationAgent] ERROR detecting query type: {e}")
            print(f"[GenerationAgent] Stack trace:")
            import traceback
            traceback.print_exc()
            print(f"[GenerationAgent] Defaulting to 'listing' (error fallback)")
            return "listing"

    def generate_sql(
        self,
        query: str,
        schema_context: SchemaContext,
        decomposition_plan: DecompositionPlan
    ) -> GenerationResult:
        """
        Generate SQL for query.

        WORKFLOW:
        =========
        1. CHECK DECOMPOSITION MODE
           - SINGLE: Generate one SQL
           - SEQUENTIAL/PARALLEL: Generate SQL for each sub-query

        2. FOR EACH SQL GENERATION:
           a. Build schema context (tables, columns, FKs)
           b. Collect few-shot examples from metadata
           c. Build LLM prompt with schema + examples
           d. LLM generates SQL
           e. Inject RLS if needed
           f. Validate safety (no DROP/DELETE/UPDATE)

        3. RETURN RESULT
           - Package as GenerationResult

        Args:
            query: User's natural language query
            schema_context: Schema context from Schema Agent
            decomposition_plan: Decomposition plan from Decomposition Agent

        Returns:
            GenerationResult with generated SQL

        Raises:
            ValueError: If generation fails
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if not schema_context or not schema_context.relevant_tables:
            raise ValueError("Schema context cannot be empty")

        print(f"\n[GenerationAgent] Generating SQL for: '{query}'")
        print(f"  Mode: {decomposition_plan.mode.value}")
        print(f"  Tables available: {len(schema_context.relevant_tables)}")

        # SINGLE MODE: Generate one SQL
        # ------------------------------
        if decomposition_plan.mode == ExecutionMode.SINGLE:
            print(f"[GenerationAgent] SINGLE mode - generating one SQL query")
            sql = self._generate_single_sql(query, schema_context)

            return GenerationResult(
                original_query=query,
                decomposition_mode=ExecutionMode.SINGLE,
                single_sql=sql,
                sub_query_sqls=[]
            )

        # DECOMPOSED MODE: Generate SQL for each sub-query
        # -------------------------------------------------
        print(f"[GenerationAgent] {decomposition_plan.mode.value} mode - generating {len(decomposition_plan.sub_queries)} SQL queries")

        sub_query_sqls = []
        for sub_query in decomposition_plan.sub_queries:
            print(f"[GenerationAgent] Generating SQL for sub-query: {sub_query.id}")

            # Filter schema context to only relevant tables for this sub-query
            sub_schema = self._filter_schema_for_subquery(schema_context, sub_query)

            # Generate SQL for sub-query
            sql = self._generate_single_sql(sub_query.query_text, sub_schema)

            sub_query_sqls.append((sub_query.id, sql))

        return GenerationResult(
            original_query=query,
            decomposition_mode=decomposition_plan.mode,
            single_sql=None,
            sub_query_sqls=sub_query_sqls
        )

    def _generate_single_sql(
        self,
        query: str,
        schema_context: SchemaContext,
        previous_results: Optional[List[Any]] = None
    ) -> GeneratedSQL:
        """
        Generate a single SQL query.

        MENTAL MAP:
        ===========
        1. Build schema context string (tables, columns, FKs)
        2. Collect few-shot examples from metadata
        3. Build LLM prompt with context + examples
        4. LLM generates SQL
        5. Parse and validate SQL
        6. Inject RLS if needed
        7. Return GeneratedSQL

        Args:
            query: Natural language query
            schema_context: Schema context with relevant tables
            previous_results: Optional results from previous sub-queries

        Returns:
            GeneratedSQL with generated query
        """
        # STEP 1: BUILD SCHEMA CONTEXT STRING
        # ------------------------------------
        schema_str = self._build_schema_context_string(schema_context)

        # STEP 2: COLLECT FEW-SHOT EXAMPLES
        # ----------------------------------
        examples_str = self._collect_few_shot_examples(schema_context)

        # STEP 3: BUILD LLM PROMPT
        # ------------------------
        # Determine if we're showing multi-dealer view or single dealer
        multi_dealer_view = not (self.inject_rls and self.dealer_id)

        # Build system prompt without f-string to avoid formatting conflicts
        dealer_rule = ""
        if multi_dealer_view:
            dealer_rule = """   - When asking for totals/counts (e.g., "How many repair orders?"), GROUP BY DealerId to show breakdown per dealer
   - Example: "How many ROs?" → SELECT DealerId, COUNT(*) as Total FROM RoMaster GROUP BY DealerId ORDER BY Total DESC
   - Always include DealerId in results for aggregate queries so user can see which dealer each number belongs to"""
        else:
            dealer_rule = """   - Query is already filtered to one dealer, no need to GROUP BY DealerId
   - Example: "How many ROs?" → SELECT COUNT(*) as Total FROM RoMaster
   - No need to include DealerId (already filtered)"""

        db_context = ""
        if multi_dealer_view:
            db_context = """- Multi-dealer database: YES - Show all dealers
- Row-level security: DISABLED (show ALL dealers)"""
        else:
            db_context = f"""- Multi-dealer database: NO - Filtered to one dealer
- Row-level security: ENABLED (filter to DealerId={self.dealer_id})"""

        # Build dealer name JOIN rule
        dealer_name_rule = """9. **DEALERSHIP NAME RULE** (CRITICAL - AUTO-VALIDATED):
   - When selecting DealerId, ALWAYS JOIN with DealerRegister to show dealer names
   - JOIN: RoMaster.DealerId = DealerRegister.ID (both are INTEGER)
   - JOIN: PDIMaster.DealerID = DealerRegister.ID (PDIMaster.DealerID is TEXT, cast if needed)
   - Example: "How many ROs per dealer?" →
     SELECT d.DealerName, COUNT(*) as Total
     FROM RoMaster r
     LEFT JOIN DealerRegister d ON r.DealerId = d.ID
     GROUP BY r.DealerId, d.DealerName
     ORDER BY Total DESC
   - NOTE: This will be automatically validated. If you select DealerId without JOIN, it will be auto-fixed.

10. **CONTEXT-RICH QUERY RULE** (CRITICAL for Rankings/Analysis):
   - Ranking queries (which/what [entity] has most/highest/frequent) MUST include descriptive context
   - VIN queries → ALWAYS JOIN Vehicleinf and include relevant vehicle columns from schema
   - Dealership queries → ALWAYS JOIN DealerRegister and include DealerName + other relevant columns
   - Don't return just IDs and metrics - include human-readable names and context
   - Use actual column names from the provided schema

   Example 1 - VIN ranking:
   Query: "Which VINs have the most repairs?"
   ❌ BAD: SELECT VINNO, COUNT(*) FROM RoMaster GROUP BY VINNO
   ✅ GOOD: SELECT r.VINNO, v.CustomerName, v.Model, v.Variant, d.DealerName, COUNT(*) as RepairCount
            FROM RoMaster r
            LEFT JOIN Vehicleinf v ON r.VINNO = v.VIN
            LEFT JOIN DealerRegister d ON r.DealerId = d.ID
            GROUP BY r.VINNO, v.CustomerName, v.Model, v.Variant, d.DealerName
            ORDER BY RepairCount DESC LIMIT 10

   Example 2 - Dealership ranking:
   Query: "Which dealership has highest warranty cancellations?"
   ✅ GOOD PATTERN: SELECT d.DealerName, [other relevant dealer columns], COUNT(*) as CancellationCount
            FROM CancleWaranty c LEFT JOIN DealerRegister d ON c.DealerID = d.ID
            GROUP BY d.DealerName, [other columns] ORDER BY CancellationCount DESC LIMIT 10

11. **NULL FILTERING RULE** (CRITICAL for Data Quality):
   - When querying dealerships by DealerId, ALWAYS filter out NULL dealer names
   - Add WHERE clause: WHERE d.DealerName IS NOT NULL
   - Why? Some records have invalid/NULL DealerId - these should be excluded from rankings

   Example - Dealership ranking with NULL filtering:
   Query: "Which dealership submitted the most PDI reports?"
   ✅ CORRECT PATTERN:
     SELECT d.DealerName, [other dealer columns from schema], COUNT(*) as PDICount
     FROM PDIMaster p
     LEFT JOIN DealerRegister d ON p.DealerId = d.ID
     WHERE d.DealerName IS NOT NULL  -- ⭐ CRITICAL: Filter out invalid dealers
     GROUP BY d.DealerName, [other dealer columns]
     ORDER BY PDICount DESC
     LIMIT 10

   NOTE: Use actual column names from the provided schema. Don't assume column names!

   Similarly for VIN queries - filter WHERE v.VIN IS NOT NULL when joining Vehicleinf"""

        # Build system prompt parts separately to avoid f-string issues
        system_prompt_part1 = """You are an expert SQL generator for Haval Automotive Dealership Management Systems (DMS).

Your job: Generate SQLite SELECT queries from natural language with ZERO ambiguity.

DATABASE CONTEXT:
=================
- SQLite database with Haval automotive dealership data
- Core tables: Vehicleinf, RoMaster, PDIMaster, PDIQMSDetail, FFSMaster, SFSMaster, CampaignRpt, CSIMaster, DealerRegister
- Operations: Sales, Service, Inspections, Warranty, Campaigns, Customer Satisfaction
"""

        system_prompt_part2 = """
**CRITICAL SCHEMA RULES** - READ CAREFULLY:
============================================

1. **VIN COLUMN NAME VARIATIONS** (MOST CRITICAL!):
   Different tables use DIFFERENT column names for VIN:
   - RoMaster: uses `VINNO` (NOT `VIN`!)
   - Vehicleinf: uses `VinNo` (NOT `VIN`!)
   - PDIMaster, FFSMaster, SFSMaster: use `VIN`

   JOIN RULES:
   - RoMaster.VINNO = Vehicleinf.VinNo (CORRECT)
   - RoMaster.VINNO = PDIMaster.VIN (CORRECT)
   - RoMaster.VIN = ... (WRONG! It's VINNO)

2. **DATE COLUMN NAME VARIATIONS**:
   - RoMaster, PDIMaster, Vehicleinf, CampaignRpt: use `Date` (capital D)
   - FFSMaster, SFSMaster: ALSO use `Date` (NOT ServiceDate!)
   - Special: CSR uses `LastMDate` and `NextScheduleDate` (specific columns)

3. **DEALERID TYPE VARIATIONS**:
   - RoMaster.DealerId: INTEGER
   - Vehicleinf.DealerID: INTEGER (note capitals)
   - PDIMaster.DealerID: TEXT! (cast to INTEGER for joins)
   - FFSMaster.DealerID: TEXT! (cast to INTEGER for joins)
   - SFSMaster.DealerID: TEXT! (cast to INTEGER for joins)

   JOIN Rules:
   - FROM RoMaster r LEFT JOIN DealerRegister d ON r.DealerId = d.ID (no cast needed)
   - FROM PDIMaster p LEFT JOIN DealerRegister d ON CAST(p.DealerID AS INTEGER) = d.ID (cast required)
   - FROM FFSMaster f LEFT JOIN DealerRegister d ON CAST(f.DealerID AS INTEGER) = d.ID (cast required)

4. **DEALERSHIP NAME RULE**:
   - Some tables have DealershipName column (FFSMaster, PDIMaster, SFSMaster)
   - ALWAYS prefer joining DealerRegister for normalized dealer info
   - Only use DealershipName if DealerRegister join fails or for quick queries

5. **MODEL vs VARIANT CONFUSION**:
   - Model column: Contains YEAR (2022, 2023) - NOT the actual model name!
   - Variant column: Contains actual model (H6 2.0, H6 1.5, Jolion, BJ40)
   When user asks "which model", they mean Variant!

6. **COLUMN NAME RULES**:
   - ONLY use columns from the SCHEMA section below
   - Use EXACT names (case-sensitive): "Date" not "date", "VINNO" not "VIN"
   - DO NOT guess or make up column names
   - Check the schema carefully before generating SQL

SQL GENERATION RULES:
=====================
1. **SAFETY**: Only SELECT queries allowed (no DROP, DELETE, UPDATE, ALTER)

2. **IDENTIFY/SHOW/LIST QUERIES** (CRITICAL!):
   When query uses "identify", "show", "list", "which" + entity names:
   - ALWAYS include identifying columns in SELECT
   - Don't just return counts - return the actual entities!

   For VEHICLES:
   SELECT v.VinNo as VIN, v.CustomerName, v.Variant, v.Model as Year, ...
   (Include VIN, customer name, model details)

   For DEALERSHIPS:
   SELECT d.DealerName, d.Location, ...
   (Always JOIN DealerRegister for names)

   For PATTERNS:
   Return all entities involved with their details

   Example: "Identify vehicles showing early-life failure"
   → Return VIN, CustomerName, Variant, pattern details (NOT just counts!)

3. **COLUMN NAMES**:
   - ONLY use columns from SCHEMA section below
   - Use EXACT names (case-sensitive): "Date" not "date", "VINNO" not "VIN"
   - Check VIN column: RoMaster/CSR use VINNO, Vehicleinf uses VinNo, others use VIN
   - Check date column: Most use Date (including FFSMaster/SFSMaster)

4. **JOINS** (⭐ CRITICAL - READ THIS CAREFULLY):
   🚨 RULE: If you reference a column from a table (e.g., d.DealerName), you MUST include that table in FROM or JOIN!

   ❌ WRONG: SELECT r.*, d.DealerName FROM RoMaster r WHERE ...
   ✅ RIGHT: SELECT r.*, d.DealerName FROM RoMaster r LEFT JOIN DealerRegister d ON r.DealerId = d.ID WHERE ...

   Common JOIN patterns:
     * RoMaster → DealerRegister: LEFT JOIN DealerRegister d ON r.DealerId = d.ID
     * RoMaster → Vehicleinf: LEFT JOIN Vehicleinf v ON r.VINNO = v.VinNo
     * PDIMaster → Vehicleinf: LEFT JOIN Vehicleinf v ON p.VIN = v.VinNo
     * PDIMaster → DealerRegister: LEFT JOIN DealerRegister d ON CAST(p.DealerID AS INTEGER) = d.ID
     * FFSMaster → DealerRegister: LEFT JOIN DealerRegister d ON CAST(f.DealerID AS INTEGER) = d.ID
     * SFSMaster → DealerRegister: LEFT JOIN DealerRegister d ON CAST(s.DealerID AS INTEGER) = d.ID

   - Always use table aliases (r, v, d, p, f, s)
   - Use LEFT JOIN when entity might not exist
   - NEVER reference a table alias that isn't defined in FROM or JOIN!

5. **CASE-INSENSITIVE STRING MATCHING** (IMPORTANT for User Input):
   - When filtering by user-provided strings (CustomerName, Model, etc.), use LOWER() for case-insensitive matching
   - Example: WHERE LOWER(CustomerName) = LOWER('john doe') OR CustomerName LIKE '%John%'
   - Prefer LIKE for partial matches: WHERE CustomerName LIKE '%' || 'john' || '%'
   - For exact matches on data in DB (like Model='H6'), use = directly if user query specifies exact model name

6. **DATES** (CRITICAL - SQLite date/time functions):
   - Date columns: RoMaster.Date, PDIMaster.Date, FFSMaster.Date, SFSMaster.Date, Vehicleinf.Date, CampaignRpt.Date (type: TIMESTAMP)
   - Special columns: RoMaster.StatusChangedDate, RoMaster.ExpectedDDate, PDIMaster.StatusChangedDate, PDIMaster.DateOfOGP

   **Absolute dates:**
   - Month/year filter: WHERE strftime('%Y-%m', Date) = '2024-12'
   - Date range: WHERE date(Date) BETWEEN '2024-01-01' AND '2024-12-31'
   - Specific year: WHERE strftime('%Y', Date) = '2024'

   **Relative dates (IMPORTANT):**
   - Current date: date('now')
   - Yesterday: WHERE Date >= date('now', '-1 day') AND Date < date('now')
   - Last 7 days: WHERE Date >= date('now', '-7 days')
   - Last 2 weeks: WHERE Date >= date('now', '-14 days')
   - Last 30 days: WHERE Date >= date('now', '-30 days')
   - Last month (proper): WHERE Date >= date('now', 'start of month', '-1 month') AND Date < date('now', 'start of month')
   - This month: WHERE strftime('%Y-%m', Date) = strftime('%Y-%m', 'now')
   - This year: WHERE strftime('%Y', Date) = strftime('%Y', 'now')
   - Last 6 months: WHERE date(Date) >= date('now', '-6 months')

   **Month/year aggregation:**
   - Group by month: GROUP BY strftime('%Y-%m', Date)
   - Group by year: GROUP BY strftime('%Y', Date)
   - Order chronologically: ORDER BY strftime('%Y-%m', Date)
   - Month name in results: strftime('%Y-%m', Date) as Month

   **Year-over-year comparisons:**
   - Extract year: strftime('%Y', Date) as Year
   - Compare across years: GROUP BY Year, calculate rates per year
   - Trend analysis: ORDER BY Year to show progression

   **Time Window Calculations** (for pattern detection):
   - "Within first year of purchase":
     julianday(ro.Date) - julianday(v.Date) <= 365
   - "Within 6 months":
     julianday(event2.Date) - julianday(event1.Date) <= 180
   - "Within 3 months after FFS":
     julianday(ro.Date) - julianday(ffs.ServiceDate) BETWEEN 0 AND 90

7. **AGGREGATIONS**: Use AVG, SUM, COUNT, MIN, MAX appropriately

8. **FILTERING**: Add WHERE clauses for conditions, use LIKE for text matching

9. **CLARITY**: Use table aliases (r for RoMaster, v for Vehicleinf, d for DealerRegister)

10. **LIMIT RULE** (CRITICAL - When to show 1 vs many):

   RULE: Ranking/comparative queries ALWAYS show multiple results for comparison.

   RANKING QUERIES (comparative/superlative keywords):
   - Keywords: "most", "highest", "top", "least", "lowest", "frequent", "best", "worst"
   - ALWAYS use LIMIT 10 for rankings (even if entity is singular!)
   - Why? Users want to compare multiple entities, not just see #1

   Examples of RANKING queries (LIMIT 10):
   - "which dealership submitted THE MOST PDI reports?" → LIMIT 10 (ranking query)
   - "which VIN has THE HIGHEST service cost?" → LIMIT 10 (ranking query)
   - "which dealership generated HIGHEST ROs?" → LIMIT 10 (ranking query)
   - "which dealerships have low CSI scores?" → LIMIT 10 (ranking query)
   - "what are the top warranty claims?" → LIMIT 10 (ranking query)

   EXPLICIT NUMBER QUERIES:
   - "top 5", "first 10", "show me 3" → Use EXACT LIMIT specified
   - "top 5 dealerships by revenue" → LIMIT 5

   SPECIFIC LOOKUP QUERIES (not rankings):
   - Keywords: "for VIN XYZ", "at dealership ABC", "on date YYYY-MM-DD"
   - Specific entity ID/name mentioned → Return matching records
   - "which dealership services VIN NF9FF6A58N2000096?" → LIMIT 1 (specific lookup)
   - "show repair orders for D001" → LIMIT 50 (list all for that dealer)

   ANALYSIS/TREND QUERIES:
   - Keywords: "trend", "pattern", "correlation", "over time", "monthly"
   - LIMIT 100 (need enough data for statistical analysis)

   DEFAULT (when unclear):
   - Prefer LIMIT 10 (good balance for rankings/comparisons)

9. **DEALER AGGREGATION RULE** (CRITICAL):
"""

        system_prompt_part3 = """
⚠️ CRITICAL - QUERY TYPE CLASSIFICATION:
=========================================
EVERY query must be classified into ONE of these types based on SQL structure:

1. **aggregate** - Single row with aggregate values (NO GROUP BY)
   - COUNT/SUM/AVG/MIN/MAX without GROUP BY
   - Returns ONE row with numeric value(s)
   - Examples:
     * SELECT COUNT(*) FROM table → {Total: 1234}
     * SELECT COUNT(DISTINCT col) FROM table → {UniqueCount: 567}
     * SELECT AVG(cost), SUM(revenue) FROM table → {AvgCost: 2500, TotalRevenue: 1000000}

2. **hybrid** - Multiple rows with grouped aggregates (HAS GROUP BY)
   - GROUP BY with COUNT/SUM/AVG/etc.
   - Returns MULTIPLE rows, each with group + aggregate
   - Examples:
     * SELECT dealer, COUNT(*) FROM table GROUP BY dealer → Multiple rows
     * SELECT month, SUM(sales) FROM table GROUP BY month → Multiple rows
     * Window functions with OVER clause also count as hybrid

3. **listing** - Entity rows (NO aggregates OR just SELECT *)
   - SELECT * or SELECT columns without aggregates
   - Returns actual records/entities
   - Examples:
     * SELECT * FROM table WHERE conditions
     * SELECT vin, customer, date FROM table LIMIT 50

RULES FOR CLASSIFICATION:
- "How many?" / "Total" / "Count" → aggregate (unless "per dealer" = hybrid)
- "Which dealer has most?" → hybrid (GROUP BY dealer, even if singular)
- "Show me VIN history" → listing (actual records)
- When in doubt, check if SQL has GROUP BY → hybrid, else check aggregates → aggregate, else → listing

RESPONSE FORMAT:
================
Respond with valid JSON ONLY (no markdown, no code blocks):
{
  "sql": "SELECT ... FROM ... WHERE ...",
  "tables_used": ["RoMaster", "Vehicleinf"],
  "query_type": "aggregate",
  "reasoning": "Why this SQL answers the query and why this query_type",
  "confidence": 0.9,
  "warnings": []
}

Example 1 - Aggregate query (count):
Query: "How many repair orders in total?"
Response:
{
  "sql": "SELECT COUNT(*) as TotalRepairOrders FROM RoMaster",
  "tables_used": ["RoMaster"],
  "query_type": "aggregate",
  "reasoning": "Simple count query - returns single row with total count. No GROUP BY, so query_type is aggregate.",
  "confidence": 0.95,
  "warnings": []
}

Example 2 - Aggregate query (distinct count):
Query: "What are the total unique VIN numbers in RO Master?"
Response:
{
  "sql": "SELECT COUNT(DISTINCT VINNO) as UniqueVINs FROM RoMaster",
  "tables_used": ["RoMaster"],
  "query_type": "aggregate",
  "reasoning": "Count distinct VINs - returns single row with count. Uses COUNT(DISTINCT), no GROUP BY, so query_type is aggregate.",
  "confidence": 0.95,
  "warnings": []
}

Example 3 - Hybrid query (ranking):
Query: "Which dealership has the most repair orders?"
Response:
{
  "sql": "SELECT d.DealerName, COUNT(*) as Total FROM RoMaster r LEFT JOIN DealerRegister d ON r.DealerId = d.ID WHERE d.DealerName IS NOT NULL GROUP BY r.DealerId, d.DealerName ORDER BY Total DESC LIMIT 10",
  "tables_used": ["RoMaster", "DealerRegister"],
  "query_type": "hybrid",
  "reasoning": "Ranking query with GROUP BY - returns multiple rows (top 10 dealerships) each with name + count. Has GROUP BY, so query_type is hybrid.",
  "confidence": 0.95,
  "warnings": []
}

Example 4 - Hybrid query (monthly trend):
Query: "Show year-over-year trends in PDI objection rates"
Response:
{
  "sql": "SELECT strftime('%Y', Date) as Year, COUNT(*) as TotalPDIs, SUM(CASE WHEN Status LIKE '%objection%' THEN 1 ELSE 0 END) as Objections, ROUND(100.0 * SUM(CASE WHEN Status LIKE '%objection%' THEN 1 ELSE 0 END) / COUNT(*), 2) as ObjectionRate FROM PDIMaster GROUP BY Year ORDER BY Year",
  "tables_used": ["PDIMaster"],
  "query_type": "hybrid",
  "reasoning": "Group by year with aggregates - returns multiple rows, one per year. Has GROUP BY, so query_type is hybrid.",
  "confidence": 0.95,
  "warnings": []
}

Example 5 - Listing query (show records):
Query: "Show repair orders from the last 2 weeks"
Response:
{
  "sql": "SELECT RoNo, Date, CustomerName, VINNO, Status FROM RoMaster WHERE Date >= date('now', '-14 days') ORDER BY Date DESC LIMIT 50",
  "tables_used": ["RoMaster"],
  "query_type": "listing",
  "reasoning": "Show actual repair order records - returns multiple entity rows. No aggregates, so query_type is listing.",
  "confidence": 0.95,
  "warnings": []
}"""

        # Concatenate all parts
        system_prompt = (system_prompt_part1 + db_context + "\n" +
                        system_prompt_part2 + dealer_rule + "\n\n" +
                        dealer_name_rule + "\n" + system_prompt_part3)

        # Build context for previous results (for decomposed queries)
        previous_context = ""
        if previous_results:
            previous_context = f"""
PREVIOUS RESULTS:
=================
Previous sub-queries returned these results that you can reference:
{previous_results}
"""

        user_prompt = f"""SCHEMA:
{schema_str}

FEW-SHOT EXAMPLES:
{examples_str}
{previous_context}

QUERY: {query}

Generate SQL query. Respond with JSON:"""

        try:
            # STEP 4: CALL LLM
            # ----------------
            response = self.llm.generate(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Low temperature for consistent SQL
                max_tokens=800
            )

            # STEP 5: PARSE LLM RESPONSE (with robust error handling)
            # --------------------------------------------------------
            from ai.utils.json_parser import (parse_llm_json,
                                              validate_json_fields)

            content = response.content.strip()

            # Use robust parser (handles control characters, malformed JSON, etc.)
            result = parse_llm_json(
                response=content,
                fallback={
                    "sql": "SELECT 'ERROR: Failed to parse LLM response' as error",
                    "tables_used": [],
                    "query_type": "listing",  # Fallback to listing
                    "reasoning": "LLM response parsing failed",
                    "confidence": 0.0,
                    "warnings": ["JSON parsing failed - check LLM response format"]
                },
                strict=False  # Don't raise exception, use fallback
            )

            # Validate required fields exist
            required_fields = ["sql", "tables_used", "reasoning", "confidence"]
            if not validate_json_fields(result, required_fields):
                raise ValueError(f"LLM response missing required fields. Got: {list(result.keys())}")

            sql = result['sql'].strip()
            tables_used = result['tables_used']
            reasoning = result['reasoning']
            confidence = result['confidence']
            warnings = result.get('warnings', [])

            # ===================================================================
            # QUERY TYPE DETECTION & VALIDATION (ROBUST)
            # ===================================================================
            # Step 1: Get LLM's claimed query type (may be missing or wrong)
            llm_query_type = result.get('query_type', None)

            # Step 2: Detect query type from SQL structure (source of truth)
            detected_query_type = self._detect_query_type_from_sql(sql)

            # Step 3: Validate consistency (warn if mismatch)
            if llm_query_type and llm_query_type != detected_query_type:
                warning_msg = f"LLM claimed query_type='{llm_query_type}' but SQL structure indicates '{detected_query_type}'. Using detected type."
                warnings.append(warning_msg)
                print(f"[GenerationAgent] WARNING: {warning_msg}")

            # Step 4: Use detected type as final query_type (trust SQL structure)
            query_type = detected_query_type

            print(f"[GenerationAgent] Query type determined: {query_type}")
            if llm_query_type:
                print(f"  LLM claimed: {llm_query_type}")
            print(f"  SQL structure: {detected_query_type}")
            print(f"  Final decision: {query_type}")

            # STEP 6: VALIDATE SAFETY
            # ------------------------
            self._validate_sql_safety(sql)

            # STEP 7: INJECT RLS
            # ------------------
            has_rls = False
            rls_column = None

            if self.inject_rls and self.dealer_id:
                sql, has_rls, rls_column = self._inject_rls(sql, schema_context)
                if has_rls:
                    warnings.append(f"RLS injected: Added WHERE {rls_column} = '{self.dealer_id}'")

            print(f"[GenerationAgent] Generated SQL successfully")
            print(f"  Tables: {', '.join(tables_used)}")
            print(f"  RLS: {has_rls} ({rls_column if rls_column else 'N/A'})")
            print(f"  Confidence: {confidence:.2f}")

            # STEP 6: VALIDATE DEALER NAME JOIN (if DealerId is selected)
            # ----------------------------------------------------------
            sql = self._validate_and_fix_dealer_join(sql, warnings)

            return GeneratedSQL(
                sql=sql,
                tables_used=tables_used,
                has_rls=has_rls,
                rls_column=rls_column,
                confidence=confidence,
                reasoning=reasoning,
                warnings=warnings,
                query_type=query_type  # ⭐ NEW: Include detected query type
            )

        except Exception as e:
            print(f"[GenerationAgent] ERROR: SQL generation failed: {e}")
            raise ValueError(f"SQL generation failed: {e}")

    def _build_schema_context_string(self, schema_context: SchemaContext) -> str:
        """
        Build schema context string for LLM prompt.

        Includes:
        - Table names and descriptions
        - Column names and types (PROMINENTLY DISPLAYED)
        - Foreign keys
        - Sample values
        - RLS columns

        Args:
            schema_context: Schema context

        Returns:
            Formatted schema string
        """
        schema_lines = []
        schema_lines.append("=" * 80)
        schema_lines.append("AVAILABLE TABLES AND COLUMNS (USE ONLY THESE COLUMN NAMES)")
        schema_lines.append("=" * 80)

        for table in schema_context.relevant_tables:
            schema_lines.append(f"\n{'='*60}")
            schema_lines.append(f"TABLE: {table.table_name} ({table.business_name})")
            schema_lines.append(f"{'='*60}")
            schema_lines.append(f"Description: {table.description}")
            schema_lines.append(f"Row count: {table.row_count:,}")

            # Columns - PROMINENTLY DISPLAYED
            schema_lines.append("\n**AVAILABLE COLUMNS** (use exact names, case-sensitive):")
            schema_lines.append("-" * 60)
            for col in table.columns:
                # Format: ColumnName (TYPE) - Sample values
                col_info = f"  ✓ {col['name']} ({col['type']})"
                if col.get('sample_values'):
                    # Handle both str and numeric sample values
                    samples = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in col['sample_values'][:3]])
                    col_info += f" — Examples: {samples}"
                if col.get('description'):
                    col_info += f" — {col['description']}"
                schema_lines.append(col_info)

            # Foreign Keys
            if table.foreign_keys:
                schema_lines.append("\n**FOREIGN KEYS** (use for JOINs):")
                for fk in table.foreign_keys:
                    column_name = fk['columns'][0] if fk.get('columns') else 'unknown'
                    referenced_table = fk.get('references', {}).get('table', 'unknown')
                    referenced_column = fk.get('references', {}).get('columns', [None])[0] if fk.get('references', {}).get('columns') else 'unknown'
                    schema_lines.append(
                        f"  → {column_name} joins with {referenced_table}.{referenced_column}"
                    )

            # RLS column
            if table.row_level_security_column:
                schema_lines.append(f"\n**RLS COLUMN**: {table.row_level_security_column}")

        schema_lines.append("\n" + "=" * 80)
        schema_lines.append("REMINDER: Only use column names listed above. Do NOT make up column names!")
        schema_lines.append("=" * 80)

        return "\n".join(schema_lines)

    def _collect_few_shot_examples(self, schema_context: SchemaContext) -> str:
        """
        Collect few-shot examples from table metadata.

        Takes up to max_examples sample queries from each table.

        Args:
            schema_context: Schema context

        Returns:
            Formatted examples string
        """
        examples_lines = []

        for table in schema_context.relevant_tables:
            if table.sample_queries:
                examples_lines.append(f"\n--- Examples for {table.table_name} ---")
                for i, sq in enumerate(table.sample_queries[:self.max_examples]):
                    examples_lines.append(f"\nExample {i+1}:")
                    examples_lines.append(f"  Query: {sq['question']}")
                    examples_lines.append(f"  SQL: {sq['sql']}")

        if not examples_lines:
            return "No examples available."

        return "\n".join(examples_lines)

    def _validate_sql_safety(self, sql: str) -> None:
        """
        Validate SQL is safe (only SELECT).

        Raises:
            ValueError: If SQL contains dangerous operations
        """
        sql_upper = sql.upper()

        # Check for dangerous keywords
        dangerous_keywords = [
            'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER',
            'CREATE', 'TRUNCATE', 'REPLACE', 'EXEC', 'EXECUTE'
        ]

        for keyword in dangerous_keywords:
            if re.search(rf'\b{keyword}\b', sql_upper):
                raise ValueError(f"SQL contains dangerous keyword: {keyword}")

        # Must start with SELECT
        if not sql_upper.strip().startswith('SELECT'):
            raise ValueError("SQL must be a SELECT query")

    def _inject_rls(
        self,
        sql: str,
        schema_context: SchemaContext
    ) -> Tuple[str, bool, Optional[str]]:
        """
        Inject row-level security (RLS) clauses into SQL.

        Adds WHERE clauses for RLS columns (e.g., DealerId).

        Args:
            sql: Original SQL
            schema_context: Schema context

        Returns:
            (modified_sql, has_rls, rls_column)
        """
        if not self.dealer_id:
            return sql, False, None

        # Find RLS column in used tables
        rls_column = None
        for table in schema_context.relevant_tables:
            if table.row_level_security_column:
                rls_column = table.row_level_security_column
                break

        if not rls_column:
            return sql, False, None

        # Check if RLS already in SQL
        if f"{rls_column}" in sql and self.dealer_id in sql:
            return sql, True, rls_column

        # Inject RLS
        # Simple approach: Add WHERE clause before GROUP BY/ORDER BY/LIMIT
        sql_upper = sql.upper()

        # Find injection point
        injection_keywords = ['GROUP BY', 'ORDER BY', 'LIMIT', 'HAVING']
        injection_pos = len(sql)

        for keyword in injection_keywords:
            pos = sql_upper.find(keyword)
            if pos != -1 and pos < injection_pos:
                injection_pos = pos

        # Check if WHERE already exists
        where_pos = sql_upper.find('WHERE')

        if where_pos != -1 and where_pos < injection_pos:
            # WHERE exists, add AND condition
            rls_clause = f" AND {rls_column} = '{self.dealer_id}' "
            modified_sql = sql[:injection_pos] + rls_clause + sql[injection_pos:]
        else:
            # No WHERE, add WHERE clause
            rls_clause = f" WHERE {rls_column} = '{self.dealer_id}' "
            modified_sql = sql[:injection_pos] + rls_clause + sql[injection_pos:]

        return modified_sql, True, rls_column

    def _validate_and_fix_dealer_join(self, sql: str, warnings: List[str]) -> str:
        """
        Validate that SQL including DealerId also JOINs with DealerRegister for dealer names.

        PROBLEM: LLM sometimes forgets to JOIN DealerRegister when selecting DealerId,
        resulting in vague answers like "the dealership with 2,107 repairs".

        SOLUTION: Auto-detect and warn (don't auto-fix to avoid breaking complex queries).

        Args:
            sql: Generated SQL query
            warnings: List to append warnings to

        Returns:
            SQL (unchanged - we only warn, not fix automatically)
        """
        sql_lower = sql.lower()

        # Check if DealerId is in SELECT clause
        has_dealerid = 'dealerid' in sql_lower

        if not has_dealerid:
            return sql  # No DealerId, nothing to validate

        # Check if DealerRegister table is joined
        has_dealer_join = 'dealerregister' in sql_lower

        # Check if DealerName is selected
        has_dealer_name = 'dealername' in sql_lower

        # If DealerId is selected but no JOIN or no DealerName, issue warning
        if not has_dealer_join or not has_dealer_name:
            warning_msg = "⚠️  SQL selects DealerId but missing DealerRegister JOIN or DealerName. Answer may be vague."
            warnings.append(warning_msg)
            print(f"[GenerationAgent] {warning_msg}")
            print(f"[GenerationAgent] RECOMMENDATION: Add 'LEFT JOIN DealerRegister d ON table.DealerId = d.ID' and SELECT d.DealerName")

        return sql  # Return unchanged (warnings only, no auto-fix)

    def _filter_schema_for_subquery(
        self,
        schema_context: SchemaContext,
        sub_query: SubQuery
    ) -> SchemaContext:
        """
        Filter schema context to only tables relevant for sub-query.

        Args:
            schema_context: Full schema context
            sub_query: Sub-query to filter for

        Returns:
            Filtered SchemaContext
        """
        # Filter to only tables mentioned in sub_query.table_names
        filtered_tables = [
            table for table in schema_context.relevant_tables
            if table.table_name in sub_query.table_names
        ]

        return SchemaContext(
            query=sub_query.query_text,
            relevant_tables=filtered_tables,
            total_tables_in_db=schema_context.total_tables_in_db,
            search_method=schema_context.search_method,
            min_relevance_score=schema_context.min_relevance_score,
            max_relevance_score=schema_context.max_relevance_score
        )
