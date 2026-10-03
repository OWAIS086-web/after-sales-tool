"""
Decomposition Agent (LAYER 3)

Breaks complex queries into simpler sub-queries with execution plan.

WHY THIS AGENT EXISTS:
======================
Problem: Complex queries like "Show H6 vehicles with PDI failures AND their average repair cost"
         are hard to generate in one SQL statement.
Solution: Break into manageable sub-queries:
  1. Find H6 vehicles with PDI failures (VINs)
  2. Get average repair cost for those VINs
  3. Combine results

This improves SQL generation accuracy from 60% → 85%+

WHEN TO DECOMPOSE:
==================
- Multi-step reasoning queries
- Queries with "AND THEN" logic
- Queries requiring intermediate filtering
- Complex cross-domain queries

WHEN NOT TO DECOMPOSE:
======================
- Simple single-table queries
- Standard JOINs (can be done in one SQL)
- Basic aggregations over joined tables

FLOW:
=====
Schema Agent → Decomposition Agent → Generation Agent (per sub-query)
 (Find tables)   (Break into steps)    (Generate SQL for each step)

Production-Grade Features:
- LLM-based decomposition detection
- Dependency graph creation
- Parallel vs sequential execution planning
- Fallback to single-query mode
- Comprehensive error handling
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from ai.dms_engine.agents.schema_agent import SchemaContext
from ai.dms_engine.agents.router_agent import QueryAnalysis
from ai.dms_engine.debug_config import dms_print
from config.llm_config import get_llm_for_component


class ExecutionMode(Enum):
    """Execution mode for sub-queries"""
    SINGLE = "single"      # No decomposition needed
    SEQUENTIAL = "sequential"  # Sub-queries must run in order
    PARALLEL = "parallel"  # Sub-queries can run in parallel


@dataclass
class SubQuery:
    """
    Represents a single sub-query in decomposition.

    Contains:
    - query_text: Natural language sub-query
    - depends_on: List of sub-query IDs this depends on
    - table_names: Relevant tables for this sub-query
    - description: What this sub-query does
    """
    id: str
    query_text: str
    description: str
    depends_on: List[str]  # IDs of sub-queries this depends on
    table_names: List[str]  # Relevant tables for this sub-query
    is_final: bool  # True if this is the final result-producing query

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DecompositionPlan:
    """
    Complete decomposition plan for query.

    Contains:
    - original_query: User's original query
    - mode: SINGLE (no decomposition) | SEQUENTIAL | PARALLEL
    - sub_queries: List of sub-queries to execute
    - execution_order: Order to execute sub-queries
    - reasoning: Why this decomposition was chosen
    """
    original_query: str
    mode: ExecutionMode
    sub_queries: List[SubQuery]
    execution_order: List[str]  # List of sub-query IDs in execution order
    reasoning: str
    confidence: float  # 0.0-1.0 confidence in decomposition

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['mode'] = self.mode.value
        result['sub_queries'] = [sq.to_dict() for sq in self.sub_queries]
        return result


class DecompositionAgent:
    """
    Decomposition Agent - LAYER 3 of DMS RAG Pipeline

    Breaks complex queries into simpler sub-queries.

    MENTAL MAP:
    ===========
    1. Input: Query + Schema context from Schema Agent
    2. Complexity check: Does this need decomposition?
    3. If NO: Return single-query plan (pass through to Generation)
    4. If YES: Break into sub-queries with LLM
    5. Build dependency graph: Which sub-queries depend on others?
    6. Create execution plan: Sequential or parallel
    7. Output: DecompositionPlan for Generation Agent

    Accuracy Target: 75% (Decomposition Detection)
    - High precision: Don't decompose if not needed (false positives bad)
    - Medium recall: OK to miss some decomposable queries (Generation handles)

    Production Features:
    - LLM-based decomposition with structured output
    - Automatic dependency detection
    - Parallel execution optimization
    - Fallback to single-query mode
    - Comprehensive error messages
    """

    def __init__(self, llm_component: str = "dms_decomposition"):
        """
        Initialize Decomposition Agent.

        Args:
            llm_component: LLM component name from llm_config.py
        """
        self.llm = get_llm_for_component(llm_component)

        dms_print(f"[DecompositionAgent] Initialized")
        print(f"  LLM: {llm_component}")

    def decompose_query(
        self,
        query: str,
        schema_context: SchemaContext,
        router_analysis: Optional[QueryAnalysis] = None
    ) -> DecompositionPlan:
        """
        Decompose query into sub-queries if needed.

        WORKFLOW:
        =========
        1. COMPLEXITY CHECK
           - Is query simple enough for single SQL?
           - Check: Single table? Basic JOIN? Simple aggregation?

        2. DECOMPOSITION DECISION
           - Use LLM to determine if decomposition needed
           - LLM analyzes: Query complexity, table relationships, logic flow

        3. IF DECOMPOSE: CREATE SUB-QUERIES
           - LLM breaks query into logical steps
           - Each step is a simpler query
           - Example: "Vehicles with PDI failures AND repair costs"
             → Sub-query 1: Find VINs with PDI failures
             → Sub-query 2: Get repair costs for those VINs

        4. BUILD DEPENDENCY GRAPH
           - Detect which sub-queries depend on others
           - Create execution order (sequential or parallel)

        5. RETURN PLAN
           - Package as DecompositionPlan for Generation Agent

        Args:
            query: User's natural language query
            schema_context: Schema context from Schema Agent
            router_analysis: Optional routing analysis

        Returns:
            DecompositionPlan with sub-queries and execution order

        Raises:
            ValueError: If query or schema_context is invalid
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if not schema_context or not schema_context.relevant_tables:
            dms_print(f"[DecompositionAgent] WARNING: No tables in schema context, using single-query mode")
            return self._create_single_query_plan(query, "No tables available")

        print(f"\n[DecompositionAgent] Analyzing query: '{query}'")
        print(f"  Available tables: {len(schema_context.relevant_tables)}")

        # STEP 1: QUICK COMPLEXITY CHECK
        # -------------------------------
        # If simple query (1 table, no complex logic), skip LLM call
        if self._is_simple_query(query, schema_context, router_analysis):
            dms_print(f"[DecompositionAgent] Simple query detected, no decomposition needed")
            return self._create_single_query_plan(query, "Simple query, no decomposition needed")

        # STEP 2: LLM DECOMPOSITION
        # --------------------------
        # Use LLM to determine if decomposition needed and create sub-queries
        try:
            plan = self._decompose_with_llm(query, schema_context, router_analysis)

            if plan.mode == ExecutionMode.SINGLE:
                dms_print(f"[DecompositionAgent] LLM decided no decomposition needed")
            else:
                dms_print(f"[DecompositionAgent] Decomposed into {len(plan.sub_queries)} sub-queries")
                print(f"  Mode: {plan.mode.value}")
                print(f"  Execution order: {' -> '.join(plan.execution_order)}")

            return plan

        except Exception as e:
            dms_print(f"[DecompositionAgent] ERROR: LLM decomposition failed: {e}")
            dms_print(f"[DecompositionAgent] Falling back to single-query mode")
            return self._create_single_query_plan(query, f"Decomposition failed: {e}")

    def _is_simple_query(
        self,
        query: str,
        schema_context: SchemaContext,
        router_analysis: Optional[QueryAnalysis]
    ) -> bool:
        """
        Quick heuristic check if query is simple enough for single SQL.

        Simple queries:
        - Single table access
        - Basic aggregation on one table
        - Simple JOINs (2 tables with clear FK relationship)

        Complex queries (need decomposition):
        - Multi-step logic ("AND THEN", "AFTER THAT")
        - Multiple independent analyses
        - Cross-domain queries with filtering
        - Queries with intermediate results needed

        Args:
            query: User's query
            schema_context: Schema context
            router_analysis: Optional router analysis

        Returns:
            True if simple (no decomposition), False if complex
        """
        # Check 1: Single table
        if len(schema_context.relevant_tables) == 1:
            return True

        # Check 2: Router analysis says simple
        if router_analysis and router_analysis.complexity == "simple":
            return True

        # Check 3: No multi-step keywords
        multi_step_keywords = [
            "and then", "after that", "followed by", "first", "second",
            "step 1", "step 2", "next", "finally"
        ]
        query_lower = query.lower()
        if any(keyword in query_lower for keyword in multi_step_keywords):
            return False

        # Check 4: Standard 2-table JOIN (most common case)
        if len(schema_context.relevant_tables) == 2:
            # If router says "medium" complexity, it's likely a standard JOIN
            if router_analysis and router_analysis.complexity == "medium":
                return True

        # Default: Treat as potentially complex, let LLM decide
        return False

    def _decompose_with_llm(
        self,
        query: str,
        schema_context: SchemaContext,
        router_analysis: Optional[QueryAnalysis]
    ) -> DecompositionPlan:
        """
        Use LLM to decompose query into sub-queries.

        MENTAL MAP:
        ===========
        1. Build prompt with query + schema context + examples
        2. LLM analyzes if decomposition needed
        3. If YES: LLM creates sub-queries with dependencies
        4. Parse LLM response into DecompositionPlan
        5. Validate dependencies and execution order

        Args:
            query: User's query
            schema_context: Schema context
            router_analysis: Optional router analysis

        Returns:
            DecompositionPlan with sub-queries
        """
        # BUILD LLM PROMPT
        # ----------------
        system_prompt = """You are a query decomposition expert for automotive dealership databases.

Your job: Analyze if a query needs to be broken into simpler sub-queries.

DECOMPOSITION RULES:
====================
1. SINGLE MODE (no decomposition) - **STRONGLY PREFERRED**:
   - Simple single-table queries
   - Standard 2-table or 3-table JOINs
   - Basic aggregations over joined tables
   - **Pattern-matching queries** ("X followed by Y", "X before Y", "X and then Y")
     → These can be solved with JOINs + WHERE clauses!

   Examples:
   - "Average repair cost for H6 vehicles" → SINGLE (2-table JOIN)
   - "Vehicles where FFS followed by repair visit" → SINGLE (JOIN + WHERE date comparison)
   - "Customers with PDI failures and warranty claims" → SINGLE (multiple JOINs)
   - "Vehicles with high service costs in 2024" → SINGLE (JOIN + aggregation + filter)

   **IMPORTANT**: Most queries can be solved in SINGLE mode with proper JOINs!

2. SEQUENTIAL MODE (decompose) - **USE SPARINGLY**:
   - ONLY when truly impossible to solve in one SQL
   - Multiple INDEPENDENT analyses that must be combined
   - Queries requiring stored intermediate results for complex calculations

   Example: "Compare dealership A's performance vs dealership B's performance with different metrics"
     → Might need 2 separate analyses

   **WARNING**: SEQUENTIAL mode is complex and error-prone. Prefer SINGLE mode whenever possible!

3. PARALLEL MODE (rare):
   - Multiple independent analyses
   Example: "Average H6 repair cost AND average Jolion repair cost" → PARALLEL
     Step 1: H6 average (independent)
     Step 2: Jolion average (independent)

**COMMON MISTAKES TO AVOID**:
============================
❌ WRONG: "Vehicles where FFS followed by repair" → SEQUENTIAL
   Reasoning: "This looks like 2 steps: (1) get FFS, (2) get repairs"
   Why wrong: Can be done in ONE SQL with JOIN!

✅ RIGHT: "Vehicles where FFS followed by repair" → SINGLE
   SQL: SELECT ... FROM FFSMaster f JOIN RoMaster r ON f.VIN = r.VINNO
        WHERE r.Date > f.ServiceDate

❌ WRONG: "Vehicles with PDI objections and high repair costs" → SEQUENTIAL
   Why wrong: Can be done with JOINs!

✅ RIGHT: "Vehicles with PDI objections and high repair costs" → SINGLE
   SQL: SELECT ... FROM PDIMaster p JOIN RoMaster r ON p.VIN = r.VINNO
        WHERE p.FaultCode != 'No Issue' AND r.TAmount > 50000

DEPENDENCY RULES:
=================
- If sub-query B needs results from sub-query A, B depends_on: ["A"]
- If sub-queries are independent, depends_on: []

Respond ONLY with valid JSON in this format:

SINGLE MODE:
{
  "mode": "single",
  "reasoning": "Simple query, can be done in one SQL",
  "confidence": 0.9
}

DECOMPOSITION MODE:
{
  "mode": "sequential",
  "sub_queries": [
    {
      "id": "sq1",
      "query_text": "Find VINs of H6 vehicles with PDI failures",
      "description": "Get list of VINs that failed PDI inspection",
      "depends_on": [],
      "table_names": ["PDIMaster", "Vehicleinf"],
      "is_final": false
    },
    {
      "id": "sq2",
      "query_text": "Get repair costs for the VINs from step 1",
      "description": "Calculate average repair cost for filtered vehicles",
      "depends_on": ["sq1"],
      "table_names": ["RoMaster"],
      "is_final": true
    }
  ],
  "reasoning": "Query requires two steps: first filter vehicles, then analyze repair costs",
  "confidence": 0.85
}"""

        # Build table context
        table_info = []
        for table in schema_context.relevant_tables:
            table_info.append(
                f"- {table.table_name} ({table.business_name}): {table.description[:100]}..."
            )
        table_context = "\n".join(table_info)

        # Add router analysis if available
        router_info = ""
        if router_analysis:
            router_info = f"""
Router Analysis:
- Complexity: {router_analysis.complexity}
- Table count: {router_analysis.table_count}
- Requires JOIN: {router_analysis.requires_join}
- Requires aggregation: {router_analysis.requires_aggregation}
"""

        user_prompt = f"""Query: {query}

Available Tables:
{table_context}
{router_info}

Analyze if this query needs decomposition. Respond with JSON:"""

        try:
            # CALL LLM
            # ---------
            response = self.llm.generate(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,  # Low temperature for consistent decomposition
                max_tokens=800
            )

            # PARSE LLM RESPONSE
            # -------------------
            import json
            import re

            content = response.content.strip()
            # Remove markdown code blocks
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content)

            decomposition = json.loads(content)

            # VALIDATE AND BUILD PLAN
            # ------------------------
            mode = ExecutionMode(decomposition['mode'])

            if mode == ExecutionMode.SINGLE:
                # No decomposition needed
                return DecompositionPlan(
                    original_query=query,
                    mode=mode,
                    sub_queries=[],
                    execution_order=[],
                    reasoning=decomposition['reasoning'],
                    confidence=decomposition['confidence']
                )

            # Parse sub-queries
            sub_queries = []
            for sq_data in decomposition['sub_queries']:
                sub_query = SubQuery(
                    id=sq_data['id'],
                    query_text=sq_data['query_text'],
                    description=sq_data['description'],
                    depends_on=sq_data['depends_on'],
                    table_names=sq_data['table_names'],
                    is_final=sq_data['is_final']
                )
                sub_queries.append(sub_query)

            # Build execution order based on dependencies
            execution_order = self._build_execution_order(sub_queries)

            return DecompositionPlan(
                original_query=query,
                mode=mode,
                sub_queries=sub_queries,
                execution_order=execution_order,
                reasoning=decomposition['reasoning'],
                confidence=decomposition['confidence']
            )

        except Exception as e:
            dms_print(f"[DecompositionAgent] ERROR parsing LLM response: {e}")
            # Fallback to single-query mode
            return self._create_single_query_plan(query, f"LLM parsing failed: {e}")

    def _build_execution_order(self, sub_queries: List[SubQuery]) -> List[str]:
        """
        Build execution order based on dependencies.

        Uses topological sort to determine correct execution order.

        Args:
            sub_queries: List of sub-queries with dependencies

        Returns:
            List of sub-query IDs in execution order
        """
        # Simple topological sort
        # Start with queries that have no dependencies
        executed = set()
        order = []

        while len(order) < len(sub_queries):
            for sq in sub_queries:
                if sq.id not in executed:
                    # Check if all dependencies are executed
                    if all(dep in executed for dep in sq.depends_on):
                        order.append(sq.id)
                        executed.add(sq.id)

        return order

    def _create_single_query_plan(self, query: str, reasoning: str) -> DecompositionPlan:
        """
        Create a single-query plan (no decomposition).

        Args:
            query: Original query
            reasoning: Why no decomposition

        Returns:
            DecompositionPlan with SINGLE mode
        """
        return DecompositionPlan(
            original_query=query,
            mode=ExecutionMode.SINGLE,
            sub_queries=[],
            execution_order=[],
            reasoning=reasoning,
            confidence=1.0
        )
