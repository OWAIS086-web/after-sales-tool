"""
Schema Agent (LAYER 2)

Performs semantic schema retrieval using ChromaDB vector search.

WHY THIS AGENT EXISTS:
======================
Problem: Database has 158 tables. Which tables should we query?
Solution: Use semantic search to find top-K most relevant tables.

Example:
- Query: "Average H6 repair cost in Lahore"
- Vector search finds: RoMaster (0.37), Vehicleinf (0.28), Dealers (0.22)
- Returns: Full metadata (columns, FKs, sample_queries) for these 3 tables

This narrows the search space from 158 tables → 3-5 relevant tables!

FLOW:
=====
Router Agent → Schema Agent → Decomposition/Generation Agent
  (Tier 3)    (Find tables)     (Generate SQL)

Production-Grade Features:
- Semantic search using all-MiniLM-L6-v2 embeddings
- Domain filtering (service, sales, inspection, etc.)
- Relevance threshold filtering (min similarity score)
- Deduplication of tables
- Fallback metadata loading
- Comprehensive error handling
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from ai.dms_engine_sqlite.metadata.index_metadata import DMSMetadataVectorStore
from ai.dms_engine_sqlite.agents.router_agent import QueryAnalysis


@dataclass
class TableSchema:
    """
    Complete schema for a single table.

    Contains everything needed for SQL generation:
    - Column names, types, sample values
    - Foreign key relationships
    - Sample SQL queries (for few-shot learning)
    - Business descriptions
    - Row-level security column
    """
    table_name: str
    business_name: str
    description: str
    business_domain: str
    columns: List[Dict[str, Any]]
    foreign_keys: List[Dict[str, Any]]
    sample_queries: List[Dict[str, str]]
    row_count: int
    row_level_security_column: Optional[str]
    relevance_score: float  # Similarity score from vector search

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return asdict(self)


@dataclass
class SchemaContext:
    """
    Complete schema context for SQL generation.

    Contains all relevant tables and their metadata.
    Passed to Decomposition/Generation agents.
    """
    query: str
    relevant_tables: List[TableSchema]
    total_tables_in_db: int
    search_method: str  # "semantic_search" or "domain_filter"
    min_relevance_score: float
    max_relevance_score: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        result = asdict(self)
        result['relevant_tables'] = [t.to_dict() for t in self.relevant_tables]
        return result


class SchemaAgent:
    """
    Schema Agent - LAYER 2 of DMS RAG Pipeline

    Retrieves relevant table schemas using semantic search.

    MENTAL MAP:
    ===========
    1. Input: Query + Router analysis
    2. Semantic search: Query ChromaDB for top-K similar tables
    3. Load metadata: Get full schema from PKL/JSON
    4. Filter: Apply relevance threshold, deduplicate
    5. Output: SchemaContext with all relevant table metadata

    Accuracy Target: 85% (Schema Retrieval)
    - Top-3 tables should include all tables needed for query
    - False positives are OK (Generation Agent filters)
    - False negatives are BAD (missing tables = wrong SQL)

    Production Features:
    - Automatic fallback if ChromaDB fails
    - Domain-based filtering for focused searches
    - Relevance score thresholding
    - Comprehensive error messages
    """

    def __init__(
        self,
        vector_store: Optional[DMSMetadataVectorStore] = None,
        metadata_dir: str = "data/dms_metadata",
        min_relevance_threshold: float = 0.15,  # Minimum similarity score
        default_top_k: int = 5  # Default number of tables to retrieve
    ):
        """
        Initialize Schema Agent.

        Args:
            vector_store: Pre-initialized DMSMetadataVectorStore (optional)
            metadata_dir: Directory with JSON metadata files (fallback)
            min_relevance_threshold: Minimum similarity score for table inclusion
            default_top_k: Default number of tables to retrieve
        """
        # VECTOR STORE INITIALIZATION
        # ----------------------------
        # Use provided vector store or create new one
        if vector_store:
            self.vector_store = vector_store
        else:
            self.vector_store = DMSMetadataVectorStore(
                persist_path='data/chroma_dms_haval',
                collection_name='dms_haval_metadata',
                company='haval'
            )

        self.metadata_dir = Path(metadata_dir)
        self.min_relevance_threshold = min_relevance_threshold
        self.default_top_k = default_top_k

        print(f"[SchemaAgent] Initialized")
        print(f"  Vector store: {self.vector_store.collection.count()} tables indexed")
        print(f"  Metadata dir: {self.metadata_dir}")
        print(f"  Min relevance: {self.min_relevance_threshold}")
        print(f"  Default top-K: {self.default_top_k}")

    def retrieve_schema(
        self,
        query: str,
        router_analysis: Optional[QueryAnalysis] = None,
        top_k: Optional[int] = None,
        domain_filter: Optional[str] = None,
        min_relevance: Optional[float] = None
    ) -> SchemaContext:
        """
        Retrieve relevant table schemas for query.

        WORKFLOW:
        =========
        1. SEMANTIC SEARCH
           - Embed query using all-MiniLM-L6-v2
           - Search ChromaDB for top-K similar tables
           - Get relevance scores (cosine similarity)

        2. FILTER
           - Remove tables below relevance threshold
           - Apply domain filter if specified
           - Deduplicate tables

        3. LOAD METADATA
           - Load full metadata from PKL/JSON
           - Include: columns, FKs, sample_queries, descriptions

        4. RETURN CONTEXT
           - Package as SchemaContext for next agent

        Args:
            query: User's natural language query
            router_analysis: Optional routing analysis from Router Agent
            top_k: Number of tables to retrieve (default: self.default_top_k)
            domain_filter: Optional domain filter (service, sales, inspection, etc.)
            min_relevance: Optional minimum relevance score (default: self.min_relevance_threshold)

        Returns:
            SchemaContext with relevant tables and metadata

        Raises:
            ValueError: If query is empty or vector store fails
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        # Use defaults if not provided
        top_k = top_k or self.default_top_k
        min_relevance = min_relevance or self.min_relevance_threshold

        # STEP 1: SEMANTIC SEARCH
        # ------------------------
        # Query ChromaDB for similar tables
        # print(f"\n[SchemaAgent] Semantic search for: '{query}'")
        # print(f"  Top-K: {top_k}")
        # print(f"  Min relevance: {min_relevance}")
        # if domain_filter:
        #     print(f"  Domain filter: {domain_filter}")

        try:
            # Query vector store
            similar_tables = self.vector_store.query_similar_tables(
                query=query,
                top_k=top_k * 2,  # Get 2x tables, filter later
                domain_filter=domain_filter
            )

            if not similar_tables:
                # print(f"[SchemaAgent] WARNING: No tables found for query")
                return self._create_empty_context(query)

            # print(f"[SchemaAgent] Found {len(similar_tables)} candidates")

        except Exception as e:
            # print(f"[SchemaAgent] ERROR: Vector search failed: {e}")
            # Fallback: return empty context
            return self._create_empty_context(query)

        # STEP 2: FILTER BY RELEVANCE
        # ----------------------------
        # Remove tables below threshold
        filtered_tables = [
            t for t in similar_tables
            if t['relevance_score'] >= min_relevance
        ]

        if not filtered_tables:
            # print(f"[SchemaAgent] WARNING: No tables above relevance threshold {min_relevance}")
            return self._create_empty_context(query)

        # Limit to top_k
        filtered_tables = filtered_tables[:top_k]

        # print(f"[SchemaAgent] After filtering: {len(filtered_tables)} tables")
        # for t in filtered_tables:
        #     print(f"  - {t['table_name']}: {t['relevance_score']:.4f}")

        # STEP 3: LOAD FULL METADATA
        # ---------------------------
        # Load complete schema from PKL or JSON
        table_schemas = []
        for table_info in filtered_tables:
            try:
                schema = self._load_table_schema(
                    table_name=table_info['table_name'],
                    relevance_score=table_info['relevance_score']
                )
                table_schemas.append(schema)
            except Exception as e:
                # print(f"[SchemaAgent] WARNING: Failed to load metadata for {table_info['table_name']}: {e}")
                continue

        if not table_schemas:
            print(f"[SchemaAgent] ERROR: Failed to load metadata for any tables")
            return self._create_empty_context(query)

        # STEP 4: CREATE CONTEXT
        # -----------------------
        relevance_scores = [t.relevance_score for t in table_schemas]
        context = SchemaContext(
            query=query,
            relevant_tables=table_schemas,
            total_tables_in_db=self.vector_store.collection.count(),
            search_method="semantic_search" if not domain_filter else "domain_filter",
            min_relevance_score=min(relevance_scores),
            max_relevance_score=max(relevance_scores)
        )

        print(f"[SchemaAgent] SUCCESS: Schema context ready:")
        print(f"  Tables: {len(table_schemas)}")
        print(f"  Relevance range: {context.min_relevance_score:.4f} - {context.max_relevance_score:.4f}")

        return context

    def _load_table_schema(self, table_name: str, relevance_score: float) -> TableSchema:
        """
        Load complete table metadata from PKL or JSON.

        FALLBACK STRATEGY:
        ==================
        1. Try loading from vector_store._metadata_by_table (PKL)
        2. If fails, load from JSON file in metadata_dir
        3. If fails, raise error

        Args:
            table_name: Name of table to load
            relevance_score: Relevance score from vector search

        Returns:
            TableSchema with complete metadata

        Raises:
            FileNotFoundError: If metadata not found
        """
        # TRY PKL FIRST
        # --------------
        # Fastest option if PKL is loaded
        if table_name in self.vector_store._metadata_by_table:
            metadata = self.vector_store._metadata_by_table[table_name]

            return TableSchema(
                table_name=metadata.table_name,
                business_name=metadata.business_name,
                description=metadata.description,
                business_domain=metadata.business_domain,
                columns=[asdict(col) for col in metadata.columns],
                foreign_keys=metadata.foreign_keys,
                sample_queries=metadata.sample_queries,
                row_count=metadata.row_count,
                row_level_security_column=metadata.row_level_security_column,
                relevance_score=relevance_score
            )

        # FALLBACK: LOAD FROM JSON
        # -------------------------
        json_file = self.metadata_dir / f"{table_name}.json"
        if not json_file.exists():
            raise FileNotFoundError(f"Metadata not found for table: {table_name}")

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return TableSchema(
            table_name=data['table_name'],
            business_name=data.get('business_name', table_name),
            description=data.get('description', ''),
            business_domain=data.get('business_domain', 'unknown'),
            columns=data.get('columns', []),
            foreign_keys=data.get('foreign_keys', []),
            sample_queries=data.get('sample_queries', []),
            row_count=data.get('row_count', 0),
            row_level_security_column=data.get('row_level_security_column'),
            relevance_score=relevance_score
        )

    def _create_empty_context(self, query: str) -> SchemaContext:
        """Create empty context when no tables found"""
        return SchemaContext(
            query=query,
            relevant_tables=[],
            total_tables_in_db=self.vector_store.collection.count(),
            search_method="semantic_search",
            min_relevance_score=0.0,
            max_relevance_score=0.0
        )

    def get_table_by_name(self, table_name: str) -> Optional[TableSchema]:
        """
        Get specific table schema by name (for Tier 1 queries).

        Args:
            table_name: Exact table name

        Returns:
            TableSchema or None if not found
        """
        try:
            return self._load_table_schema(table_name, relevance_score=1.0)
        except Exception as e:
            print(f"[SchemaAgent] WARNING: Table '{table_name}' not found: {e}")
            return None

    def get_relevant_tables(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Get top-K relevant tables using LLM hints + vector search.

        This method combines:
        1. LLM-based table hint extraction (domain keyword → table mapping)
        2. Vector similarity search (semantic matching)
        3. Hard priority: LLM hints first, then vector results

        Used by Tier2Views for semantic validation.

        Args:
            query: User's natural language query
            top_k: Number of tables to return

        Returns:
            List of dicts with 'table_name' and 'relevance_score'
            Example: [{'table_name': 'FFSMaster', 'relevance_score': 0.95}, ...]
        """
        try:
            # print(f"\n[SchemaAgent] ==================== TABLE RETRIEVAL ====================")
            # print(f"[SchemaAgent] Query: '{query}'")
            # print(f"[SchemaAgent] Requested top-K: {top_k}")

            # STEP 1: Load all table metadata for LLM prompt
            all_tables_metadata = self._load_all_table_metadata()
            # print(f"[SchemaAgent] Loaded {len(all_tables_metadata)} table metadata files")

            # STEP 2: Extract table hints using LLM (domain keywords → tables)
            # print(f"[SchemaAgent] STEP 1: Calling LLM for table hint extraction...")
            llm_hints = self._extract_table_hints(query, all_tables_metadata)
            # print(f"[SchemaAgent] ✓ LLM extracted hints: {llm_hints}")

            # STEP 3: Vector similarity search
            # print(f"[SchemaAgent] STEP 2: Running vector similarity search (top-{top_k * 2})...")
            schema_context = self.retrieve_schema(query, top_k=top_k * 2)  # Get more candidates
            vector_tables = [
                {'table_name': t.table_name, 'relevance_score': t.relevance_score}
                for t in schema_context.relevant_tables
            ]
            # print(f"[SchemaAgent] ✓ Vector search found {len(vector_tables)} candidates:")
            # for i, vt in enumerate(vector_tables[:5], 1):
            #     print(f"    {i}. {vt['table_name']:<20} (score: {vt['relevance_score']:.4f})")

            # STEP 4: HARD PRIORITY - LLM hints first, then vector results
            # print(f"[SchemaAgent] STEP 3: Applying HARD PRIORITY boosting...")
            final_results = []

            # Add LLM hints first with high scores
            for hint in llm_hints:
                # Check if hint is in vector results
                vector_match = next((v for v in vector_tables if v['table_name'] == hint), None)
                if vector_match:
                    # Use vector score if available, boost by +0.3
                    boosted_score = min(vector_match['relevance_score'] + 0.3, 1.0)
                    final_results.append({'table_name': hint, 'relevance_score': boosted_score})
                    # print(f"    ✓ Boosted '{hint}': {vector_match['relevance_score']:.4f} → {boosted_score:.4f} (+0.3)")
                else:
                    # Not in vector results, but LLM suggested it - give high score anyway
                    final_results.append({'table_name': hint, 'relevance_score': 0.85})
                    # print(f"    ✓ Added '{hint}': 0.85 (LLM hint, not in vector results)")

            # Add remaining vector results (not in LLM hints)
            for v in vector_tables:
                if v['table_name'] not in llm_hints:
                    final_results.append(v)

            # Log final top-K results
            # print(f"[SchemaAgent] FINAL TOP-{top_k} RESULTS (after boosting):")
            # for i, result in enumerate(final_results[:top_k], 1):
            #     is_llm_hint = result['table_name'] in llm_hints
            #     marker = "🎯 LLM" if is_llm_hint else "   VEC"
            #     print(f"    {i}. [{marker}] {result['table_name']:<20} (score: {result['relevance_score']:.4f})")
            # print(f"[SchemaAgent] ========================================================\n")

            # Return top-K
            return final_results[:top_k]

        except Exception as e:
            print(f"\n[SchemaAgent] ✗ ERROR: get_relevant_tables failed: {e}")
            import traceback
            print(f"[SchemaAgent] Traceback: {traceback.format_exc()}")
            print(f"[SchemaAgent] ⚠ Falling back to vector-only search (no LLM hints)")
            # Fallback: Just use vector search
            schema_context = self.retrieve_schema(query, top_k=top_k)
            fallback_results = [
                {'table_name': t.table_name, 'relevance_score': t.relevance_score}
                for t in schema_context.relevant_tables
            ]
            print(f"[SchemaAgent] Fallback results (top-{top_k}):")
            for i, result in enumerate(fallback_results[:top_k], 1):
                print(f"    {i}. [VEC] {result['table_name']:<20} (score: {result['relevance_score']:.4f})")
            print(f"[SchemaAgent] ========================================================\n")
            return fallback_results

    def _load_all_table_metadata(self) -> List[Dict[str, str]]:
        """
        Load all table metadata from JSON files.

        Returns:
            List of dicts with table_name, business_name, description
            Example: [
                {
                    'table_name': 'FFSMaster',
                    'business_name': 'First Free Service Records',
                    'description': 'This table stores...'
                },
                ...
            ]
        """
        metadata_list = []

        # Iterate all JSON files in metadata directory
        for json_file in self.metadata_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    metadata_list.append({
                        'table_name': data.get('table_name', ''),
                        'business_name': data.get('business_name', ''),
                        'description': data.get('description', '')
                    })
            except Exception as e:
                print(f"[SchemaAgent] WARNING: Failed to load {json_file.name}: {e}")
                continue

        return metadata_list

    def get_final_tables_llm_only(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        **TIER 3 ONLY**: Use pure LLM to select FINAL tables for query (no vector search).

        This method replaces the hybrid approach (LLM hints + vector search) with a single
        LLM call that selects the EXACT tables needed to answer the query.

        WHY LLM-ONLY FOR TIER 3:
        ========================
        - LLM understands semantic context better than vector embeddings
        - Avoids wrong tables being added by vector search (e.g., CancleWaranty for "warranty")
        - Simpler architecture: single source of truth
        - More deterministic: Generation Agent receives only correct tables (no choice)
        - Same/lower cost: 1 LLM call (no vector overhead)

        Args:
            query: User's natural language query
            top_k: Maximum number of tables to return (for safety)

        Returns:
            Dict with:
                - tables: List[str] - Table names to use
                - reasoning: str - Why these tables were chosen
                - query_type: str - "single-table" or "multi-table"
                - confidence: float - LLM confidence (0.0-1.0)

            Example:
                {
                    "tables": ["RoMaster", "DealerRegister"],
                    "reasoning": "RoMaster has warranty complaints, DealerRegister for dealer names",
                    "query_type": "multi-table",
                    "confidence": 0.95
                }
        """
        try:
            print(f"\n[SchemaAgent] ==================== TIER 3 LLM TABLE SELECTION ====================")
            print(f"[SchemaAgent] Query: '{query}'")
            print(f"[SchemaAgent] Method: PURE LLM (no vector search)")

            # STEP 1: Load all table metadata for LLM prompt
            all_tables_metadata = self._load_all_table_metadata()
            print(f"[SchemaAgent] STEP 1: Loaded {len(all_tables_metadata)} table metadata files")

            # STEP 2: Call LLM for FINAL table selection (not just hints)
            print(f"[SchemaAgent] STEP 2: Calling LLM for FINAL table selection...")
            result = self._extract_final_tables_llm(query, all_tables_metadata, top_k)

            print(f"[SchemaAgent] ✓ LLM FINAL SELECTION:")
            print(f"    Tables selected: {result['tables']}")
            print(f"    Query type: {result['query_type']}")
            print(f"    Confidence: {result['confidence']:.2f}")
            print(f"    Reasoning: {result['reasoning']}")
            print(f"[SchemaAgent] =====================================================================\n")

            return result

        except Exception as e:
            print(f"\n[SchemaAgent] ✗ ERROR: get_final_tables_llm_only failed: {e}")
            import traceback
            print(f"[SchemaAgent] Traceback: {traceback.format_exc()}")
            print(f"[SchemaAgent] ⚠ Returning empty result")
            print(f"[SchemaAgent] =====================================================================\n")
            return {
                "tables": [],
                "reasoning": f"Error: {str(e)}",
                "query_type": "unknown",
                "confidence": 0.0
            }

    def _extract_final_tables_llm(self, query: str, all_tables_metadata: List[Dict[str, str]], top_k: int = 5) -> Dict[str, Any]:
        """
        Use LLM to select FINAL tables for query (Tier 3 only).

        This is different from _extract_table_hints() which returns hints for boosting.
        This method returns the FINAL table selection with reasoning and confidence.

        Args:
            query: User's natural language query
            all_tables_metadata: List of all available tables with descriptions
            top_k: Maximum tables to return

        Returns:
            Dict with tables, reasoning, query_type, confidence
        """
        from config.llm_config import get_llm_for_component

        # Build table catalog for LLM
        table_catalog = "\n".join([
            f"- {t['table_name']} ({t['business_name']}): {t['description'][:150]}..."
            for t in all_tables_metadata
        ])

        prompt = f"""You are an expert database analyst for an automotive DMS system.

Your task: Select the EXACT tables needed to answer this query.

Query: {query}

Available Tables:
{table_catalog}

CRITICAL DOMAIN KEYWORD MAPPINGS:
==================================
- "warranty complaints", "warranty claims", "repair orders", "RO", "service", "complaints" -> RoMaster (NOT CancleWaranty)
- "FFS", "first free service", "free service" -> FFSMaster
- "SFS", "second free service" -> SFSMaster
- "PDI", "inspection", "pre-delivery inspection" -> PDIMaster
- "campaign", "service campaign" -> CampaignRpt
- "dealership", "dealer" (ONLY for dealer directory/contact info like address, phone, email) -> DealerRegister
- "vehicle" (for vehicle info) -> Vehicleinf
- "CSI", "customer satisfaction" -> CSIMaster

⚠️ CRITICAL - DEALERSHIP NAME COLUMNS:
======================================
Many tables ALREADY HAVE dealer name columns! Check BEFORE adding DealerRegister:
- FFSMaster has "DealershipName" column (45 distinct dealers) → NO need for DealerRegister!
- SFSMaster has "DealershipName" column → NO need for DealerRegister!
- RoMaster has dealer info directly → NO need for DealerRegister for basic queries!

ONLY use DealerRegister when:
1. Query asks for dealer contact info (phone, email, address) not available in other tables
2. Query explicitly mentions "dealer directory" or "dealer registration"

For queries like "top dealerships by X", "which dealer has most Y", "group by dealership":
→ Use the main table's DealershipName/dealer column directly
→ DO NOT join with DealerRegister (unnecessary, causes data loss/confusion)

RULES FOR TABLE SELECTION:
===========================
1. SINGLE-TABLE QUERY: If query can be answered from ONE table, return ONLY that table
2. MULTI-TABLE QUERY: If query needs JOIN (e.g., "by dealership", "with vehicle info"), return ALL tables needed
3. BE MINIMAL: Only return tables that are REQUIRED (not "nice to have")
4. BE PRECISE: Use domain knowledge to choose correct table (e.g., RoMaster for "warranty", NOT CancleWaranty)

FEW-SHOT EXAMPLES:
==================

Example 1 - SINGLE TABLE:
Query: "Which VINs have most FFS?"
Response: {{"tables": ["FFSMaster"], "reasoning": "FFS data is in FFSMaster table. No JOIN needed - can count VINs directly from FFSMaster.", "query_type": "single-table", "confidence": 0.95}}

Example 2 - SINGLE TABLE (dealership already in table):
Query: "Show warranty complaints by dealership"
Response: {{"tables": ["RoMaster"], "reasoning": "RoMaster contains warranty complaints AND dealer info. Can group by dealer directly from RoMaster. DealerRegister NOT needed.", "query_type": "single-table", "confidence": 0.95}}

Example 3 - SINGLE TABLE (dealership name in FFSMaster):
Query: "Which dealerships perform the most first free services?"
Response: {{"tables": ["FFSMaster"], "reasoning": "FFSMaster contains FFS records AND has DealershipName column with 45 distinct dealers. Can count and group by DealershipName directly. DealerRegister NOT needed.", "query_type": "single-table", "confidence": 0.95}}

Example 4 - THREE TABLES (COMPLEX JOIN):
Query: "Identify VINs where FFS resulted in a follow-up repair order"
Response: {{"tables": ["FFSMaster", "RoMaster", "Vehicleinf"], "reasoning": "FFSMaster for FFS records, RoMaster for repair orders, need to JOIN on VIN. Vehicleinf may be needed to link VINs correctly.", "query_type": "multi-table", "confidence": 0.90}}

Example 5 - SINGLE TABLE (tricky - "warranty" keyword):
Query: "How many warranty claims were made?"
Response: {{"tables": ["RoMaster"], "reasoning": "Warranty claims are repair orders in RoMaster (JobRequest/Status indicate warranty). CancleWaranty only has CANCELLED claims, not all claims.", "query_type": "single-table", "confidence": 0.90}}

Example 6 - SINGLE TABLE:
Query: "Show campaign reports for H6 models"
Response: {{"tables": ["CampaignRpt"], "reasoning": "Campaign data with model filtering can be done from CampaignRpt alone (has Model column).", "query_type": "single-table", "confidence": 0.95}}

Example 7 - TWO TABLES (DealerRegister ACTUALLY needed):
Query: "What is the contact information for all dealerships?"
Response: {{"tables": ["DealerRegister"], "reasoning": "DealerRegister contains dealer directory info like phone, email, address. This is when DealerRegister IS needed.", "query_type": "single-table", "confidence": 0.95}}

Now analyze the query above and return ONLY valid JSON (no markdown, no code blocks):
{{"tables": ["TableName1", "TableName2"], "reasoning": "why these specific tables", "query_type": "single-table or multi-table", "confidence": 0.90}}"""

        # Call LLM
        print(f"  [LLM] Calling Grok-3-Fast for FINAL table selection...")
        llm = get_llm_for_component("dms_table_hints")
        response = llm.generate([
            {"role": "user", "content": prompt}
        ])

        # Parse response
        response_text = response.content.strip()
        print(f"  [LLM] Raw response: {response_text}")

        # Extract JSON from response (with robust parsing)
        from ai.utils.json_parser import parse_llm_json
        import re

        result = parse_llm_json(response_text, fallback={"tables": [], "reasoning": "Parse failed", "query_type": "unknown", "confidence": 0.0})
        print(f"  [LLM] Parsed JSON: {result}")

        # Validate table names exist
        valid_table_names = {t['table_name'] for t in all_tables_metadata}
        original_tables = result.get('tables', [])
        validated_tables = [t for t in original_tables if t in valid_table_names]

        if len(validated_tables) < len(original_tables):
            invalid_tables = [t for t in original_tables if t not in valid_table_names]
            print(f"  [LLM] ⚠ Warning: Filtered out invalid tables: {invalid_tables}")

        # Limit to top_k for safety
        if len(validated_tables) > top_k:
            print(f"  [LLM] ⚠ Warning: LLM returned {len(validated_tables)} tables, limiting to {top_k}")
            validated_tables = validated_tables[:top_k]

        result['tables'] = validated_tables
        print(f"  [LLM] ✓ Final validated tables: {validated_tables}")

        return result

    def _extract_table_hints(self, query: str, all_tables_metadata: List[Dict[str, str]]) -> List[str]:
        """
        **TIER 2 ONLY**: Use LLM to extract probable table names for boosting (hints only).

        This is used by Tier 2 for semantic validation (CHECK 4A/4B).
        For Tier 3, use get_final_tables_llm_only() instead.

        Args:
            query: User's natural language query
            all_tables_metadata: List of all available tables with descriptions

        Returns:
            List of table names (2-3 most relevant)
            Example: ['FFSMaster', 'DealerRegister']
        """
        try:
            from config.llm_config import get_llm_for_component

            # Build table catalog for LLM
            table_catalog = "\n".join([
                f"- {t['table_name']} ({t['business_name']}): {t['description'][:150]}..."
                for t in all_tables_metadata
            ])

            prompt = f"""Analyze this database query and identify which tables are most likely relevant.

Query: {query}

Available Tables:
{table_catalog}

IMPORTANT DOMAIN KEYWORD MAPPINGS:
- "FFS", "first free service", "free service" -> FFSMaster
- "SFS", "second free service" -> SFSMaster
- "PDI", "inspection", "pre-delivery inspection" -> PDIMaster
- "repair order", "RO", "complaint", "warranty claim", "warranty" -> RoMaster
- "campaign", "service campaign" -> CampaignRpt
- "dealership", "dealer" (for dealer info) -> DealerRegister
- "vehicle" (for vehicle info) -> Vehicleinf
- "CSI", "customer satisfaction" -> CSIMaster

Return ONLY the 2-3 most relevant table names as a JSON array based on domain keywords.
If multiple tables needed (e.g., "FFS resulted in repair order"), include ALL relevant tables.

Example 1: "Which dealerships perform the most first free services?"
Response: ["FFSMaster", "DealerRegister"]

Example 2: "Identify VINs where FFS resulted in a follow-up repair order"
Response: ["FFSMaster", "RoMaster"]

Example 3: "Show warranty complaints by dealership"
Response: ["RoMaster", "DealerRegister"]

Now analyze the query above and return ONLY a JSON array like ["TableName1", "TableName2"]:"""

            # Use integrated LLM client (Grok-3-Fast)
            # print(f"  [LLM] Calling Grok-3-Fast for table hint extraction...")
            llm = get_llm_for_component("dms_table_hints")
            response = llm.generate([
                {"role": "user", "content": prompt}
            ])

            # Parse response
            response_text = response.content.strip()
            # print(f"  [LLM] Raw response: {response_text[:150]}..." if len(response_text) > 150 else f"  [LLM] Raw response: {response_text}")

            # Extract JSON array from response
            import re
            json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if json_match:
                hints = json.loads(json_match.group(0))
                # print(f"  [LLM] Parsed JSON: {hints}")

                # Validate table names exist
                valid_table_names = {t['table_name'] for t in all_tables_metadata}
                hints = [h for h in hints if h in valid_table_names]

                if len(hints) < len(json.loads(json_match.group(0))):
                    invalid_hints = [h for h in json.loads(json_match.group(0)) if h not in valid_table_names]
                    # print(f"  [LLM] Warning: Filtered out invalid tables: {invalid_hints}")

                # print(f"  [LLM] ✓ Final hints: {hints[:3]}")
                return hints[:3]  # Max 3 hints
            else:
                # print(f"  [LLM] WARNING: LLM response not JSON: {response_text}")
                return []

        except Exception as e:
            # print(f"  [LLM] ✗ ERROR: Table hint extraction failed: {e}")
            # import traceback
            # print(f"  [LLM] Traceback: {traceback.format_exc()}")
            return []  # Return empty hints on failure
