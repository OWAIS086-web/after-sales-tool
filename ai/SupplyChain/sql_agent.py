"""
SQL Agent Module (Supply Chain)
Implements the LangChain SQL Agent for natural language supply chain database queries.
Uses centralized config from config/llm_config.py (xAI provider only).
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_community.agent_toolkits import (SQLDatabaseToolkit,
                                                create_sql_agent)
from langchain_community.utilities import SQLDatabase

logger = logging.getLogger(__name__)

class SQLAgent:
    """LangChain SQL Agent for natural language supply chain database interactions."""
    
    def __init__(self, db_manager, config: dict):
        """
        Initialize the SQL Agent.
        Args:
            db_manager: DatabaseManager instance
            config: LangChain configuration dictionary
        """
        self.db_manager = db_manager
        self.config = config
        self.agent = None
        self.llm = None
        self.toolkit = None
        self.sql_database = None
    
    def _initialize_llm(self):
        """Initialize the Language Model from centralized config (xAI only)."""
        llm_config = self.config.get('llm', {})
        provider = llm_config.get('provider', 'xai').lower()

        if provider == 'xai':
            import os
            from langchain_openai import ChatOpenAI
            from config.llm_config import get_llm_config
            supplychain_sql_config = get_llm_config('supplychain_sql_agent')
            api_key_env = supplychain_sql_config.api_key_env or 'XAI_API_KEY'
            api_key = os.getenv(api_key_env)
            if not api_key:
                raise ValueError(f"{api_key_env} not found in environment. Ensure root .env is loaded.")
            llm_config = self.config.get('langchain', {}).get('llm', {})
            request_timeout = llm_config.get('request_timeout', 60)
            max_retries = llm_config.get('max_retries', 3)
            self.llm = ChatOpenAI(
                model=supplychain_sql_config.model_name,
                temperature=supplychain_sql_config.temperature,
                max_tokens=supplychain_sql_config.max_tokens,
                api_key=api_key,
                base_url="https://api.x.ai/v1",
                timeout=request_timeout,
                max_retries=max_retries
            )
            logger.info(f"Initialized xAI LLM: {supplychain_sql_config.model_name} (config: supplychain_sql_agent, timeout={request_timeout}s)")
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}. Supply Chain mode only supports 'xai'.")
    
    def _initialize_database(self):
        """Initialize the SQL Database wrapper for LangChain."""
        engine = self.db_manager.connect()
        filtered_tables = self.db_manager.get_filtered_tables()
        toolkit_config = self.config.get('toolkit', {})
        sample_rows = toolkit_config.get('sample_rows_in_table_info', 3)
        custom_table_info = self._load_supplychain_metadata(filtered_tables)
        self.sql_database = SQLDatabase(
            engine=engine,
            include_tables=filtered_tables,
            sample_rows_in_table_info=sample_rows,
            custom_table_info=custom_table_info
        )
        logger.info(f"Initialized SQL Database with {len(filtered_tables)} tables")
    
    def _load_supplychain_metadata(self, table_names: list) -> dict:
        """Load Supply Chain table metadata from JSON files (token-optimized)."""
        import os
        from ai.SupplyChain.metadata_loader import MetadataLoader
        metadata_folder = self.config.get('metadata', {}).get('folder', 'dms_metadata')
        if not os.path.isabs(metadata_folder):
            sc_dir = os.path.dirname(os.path.abspath(__file__))
            metadata_folder = os.path.join(sc_dir, metadata_folder)
        loader = MetadataLoader(metadata_dir=metadata_folder)
        metadata = loader.load_all_metadata()
        if not metadata:
            logger.warning("No Supply Chain metadata found, using default schema info")
            return None
        custom_info = {}
        for table_name in table_names:
            if table_name in metadata:
                table_meta = metadata[table_name]
                context_parts = []
                context_parts.append(f"{table_meta.get('business_name', table_name)}: {table_meta.get('description', '')[:200]}")
                use_cases = table_meta.get('common_use_cases', [])
                if use_cases:
                    context_parts.append(f"Use: {use_cases[0]}")
                columns = table_meta.get('columns', [])
                key_cols = []
                for col in columns:
                    if col.get('primary_key') or col.get('is_foreign_key') or (col.get('searchable') and len(key_cols) < 5):
                        key_cols.append(f"{col['name']}({col['type']})")
                    if len(key_cols) >= 8:
                        break
                if key_cols:
                    context_parts.append(f"Cols: {', '.join(key_cols)}")
                custom_info[table_name] = ". ".join(context_parts)
                logger.debug(f"Loaded minimal metadata for {table_name}")
        logger.info(f"Loaded compact Supply Chain metadata for {len(custom_info)} tables")
        return custom_info if custom_info else None
    
    def _initialize_toolkit(self):
        """Initialize the SQL Database Toolkit."""
        toolkit_config = self.config.get('toolkit', {})
        self.toolkit = SQLDatabaseToolkit(
            db=self.sql_database,
            llm=self.llm
        )
        logger.info("Initialized SQL Database Toolkit")
    
    def initialize(self):
        """Initialize all components of the SQL Agent."""
        logger.info("Initializing SQL Agent...")
        self._initialize_llm()
        self._initialize_database()
        self._initialize_toolkit()
        agent_config = self.config.get('agent', {})
        agent_type = agent_config.get('type', 'openai-tools')
        max_iterations = 10
        verbose = agent_config.get('verbose', True)
        available_tables = self.db_manager.get_filtered_tables()
        try:
            import os
            from ai.SupplyChain.metadata_loader import MetadataLoader
            metadata_folder = self.config.get('metadata', {}).get('folder', 'dms_metadata')
            if not os.path.isabs(metadata_folder):
                sc_dir = os.path.dirname(os.path.abspath(__file__))
                metadata_folder = os.path.join(sc_dir, metadata_folder)
            loader = MetadataLoader(metadata_dir=metadata_folder)
            metadata = loader.load_all_metadata()
        except Exception as e:
            logger.warning(f"Could not load metadata for system prompt: {e}")
            metadata = {}
        table_lines = []
        for t in available_tables:
            desc = metadata.get(t, {}).get('description', '')
            columns = metadata.get(t, {}).get('columns', [])
            col_names = ', '.join([col['name'] for col in columns]) if columns else ''
            table_lines.append(f"- {t}: {desc} Columns: [{col_names}]")
        system_prompt = (
            "You are an EXPERT SQL assistant for the HAVAL SUPPLY CHAIN DATABASE (Automobile company operations in Pakistan).\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "🎯 YOUR MISSION: Generate accurate SQL → Execute → Return clear answers\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            "DATABASE CONTEXT (SUPPLY CHAIN ONLY - NO FINANCE):\n"
            "- 503 ORDERS records (Purchase orders, supplier tracking, delivery status)\n"
            "- 334 INVENTORY records (Parts, stock levels, warehouse locations)\n"
            "- 454 SHIPMENTS records (In-transit, customs, delivery timelines)\n"
            "- 20 SUPPLIERS records (China + Pakistan, tier breakdown)\n"
            "- 20 CONTRACTS records (Supplier agreements, expiry dates)\n"
            "- Coverage: 2024-2026 fiscal years\n"
            "- Geographic: Pakistan (Sindh, Punjab, KPK, ICT) + China (Shanghai, Guangzhou)\n"
            "- Warehouses: Karachi, Lahore, Islamabad, Shanghai, Guangzhou\n\n"
            "WORKFLOW (FAST & ACCURATE):\n"
            "1️⃣ UNDERSTAND: Read query → Identify intent (ignore typos)\n"
            "2️⃣ VERIFY: Check table metadata below → Find EXACT column names\n"
            "3️⃣ WRITE SQL: Use verified columns → Add LIMIT if needed\n"
            "4️⃣ EXECUTE: Run sql_db_query ONCE (minimize iterations)\n"
            "5️⃣ ANSWER: Format results clearly with context\n\n"
            "TYPO TOLERANCE (CRITICAL):\n"
            "✓ 'supplir' → supplier | 'inventry' → inventory | 'shpment' → shipment\n"
            "✓ 'ordr' → order | 'contrct' → contract | 'warehous' → warehouse\n"
            "✓ Focus on USER INTENT, not perfect spelling\n\n"
            "TABLES AVAILABLE:\n"
            f"{chr(10).join(table_lines)}\n\n"
        )
        system_prompt += (
            "═══════════════════════════════════════════════════════════════\n"
            "🔧 SQL GENERATION RULES (FOLLOW STRICTLY)\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            "COLUMN VERIFICATION:\n"
            "• ALWAYS use EXACT column names from metadata above\n"
            "• Check Columns: [...] list for each table before writing SQL\n"
            "• NEVER guess column names\n"
            "• Common columns:\n"
            "  - ORDERS: OrderID, OrderDate, SupplierID, PartID, Quantity, Status, DeliveryDate\n"
            "  - INVENTORY: PartID, PartName, StockLevel, Warehouse, LastUpdated\n"
            "  - SHIPMENTS: ShipmentID, OrderID, Status, DepartureDate, ArrivalDate, CustomsStatus\n"
            "  - SUPPLIERS: SupplierID, SupplierName, Country, Tier, ContractID\n"
            "  - CONTRACTS: ContractID, SupplierID, StartDate, EndDate, Terms\n\n"
            "DATABASE-SPECIFIC:\n"
            "• SQLite syntax: Use STRFTIME('%Y', date) for year, STRFTIME('%m', date) for month\n"
            "• Case-insensitive search: Use LOWER(column) LIKE LOWER('%value%')\n"
            "• Warehouses: Karachi, Lahore, Islamabad, Shanghai, Guangzhou\n"
            "• Currency: All amounts in PKR (Pakistani Rupees)\n"
            "• Quarters: Q1, Q2, Q3, Q4 | Fiscal Years: 2024, 2025, 2026\n\n"
            "QUERY OPTIMIZATION:\n"
            "• Add LIMIT 10 for single-record queries (e.g., 'show supplier X')\n"
            "• Add LIMIT 20 for list queries (e.g., 'list all orders')\n"
            "• Use COUNT(*) first if asked 'how many'\n"
            "• For aggregates (AVG, SUM, MAX), no LIMIT needed\n"
            "• For JOINs: Use table aliases\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "📊 ANSWER FORMATTING (USER-FRIENDLY)\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            "AGGREGATES (COUNT, SUM, AVG):\n"
            "✓ Direct answer: 'There are 45 orders pending delivery.'\n"
            "✓ With context: 'Average delivery time: 7.3 days across 120 shipments.'\n"
            "✓ Multiple stats: '• Total Orders: 503\n• Delivered: 452\n• Avg Lead Time: 6.2 days'\n\n"
            "SINGLE RECORD:\n"
            "✓ Structured format with labels:\n"
            "  Order Date: 2025-12-15\n"
            "  Supplier: Chongqing Jinyu\n"
            "  Part: HVL-BOD-00078\n"
            "  Quantity: 120\n"
            "  Status: Delivered\n"
            "  Delivery Date: 2025-12-22\n\n"
            "MULTIPLE RECORDS (≤10):\n"
            "✓ Numbered list with key fields:\n"
            "  1. Karachi Main Hub - HVL-ELE-00043 - 0 units\n"
            "  2. Islamabad Central - HVL-ELE-00045 - 2 units\n"
            "  [Continue for all records]\n\n"
            "LARGE RESULTS (>20):\n"
            "✓ Show summary + first 10:\n"
            "  'Found 45 orders from China suppliers. Showing first 10:'\n"
            "  [List 10 records]\n"
            "  'Use filters to narrow down results.'\n\n"
            "NO RESULTS:\n"
            "✓ Clear statement: 'No shipments found in transit.'\n"
            "✓ Suggest alternatives: 'Try: Karachi warehouse (18 shipments) or Lahore (12 shipments)'\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "🚫 OUT OF SCOPE - REJECT IMMEDIATELY\n"
            "═══════════════════════════════════════════════════════════════\n"
            "If query about: weather, recipes, sports, politics, entertainment, general knowledge\n"
            "→ Respond: 'OUT_OF_DOMAIN - Ask about orders, suppliers, inventory, shipments, or contracts for Haval Pakistan.'\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "📝 AGENT FORMAT (LANGCHAIN REQUIRED)\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            "Thought: [Understand query, verify columns]\n"
            "Action: sql_db_query\n"
            "Action Input: SELECT ... (your SQL)\n"
            "Observation: [Query results]\n"
            "Thought: [Interpret results]\n"
            "Final Answer: [Formatted response to user]\n\n"
            "⚠️ NEVER include 'Action:' after 'Final Answer:' - that signals completion!\n\n"
        )
        # Supply Chain-specific few-shot examples
        few_shot_example = (
            "═══════════════════════════════════════════════════════════════\n"
            "💡 FEW-SHOT EXAMPLES (LEARN THE PATTERN)\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            "EXAMPLE 1 - Aggregate Query (Average Delivery Time):\n"
            "Q: What's the average delivery time for shipments?\n"
            "Thought: Need to calculate average delivery time. SHIPMENTS table has DepartureDate and ArrivalDate columns.\n"
            "Action: sql_db_query\n"
            "Action Input: SELECT AVG(JULIANDAY(ArrivalDate) - JULIANDAY(DepartureDate)) as AvgDeliveryTime, COUNT(*) as TotalShipments FROM SHIPMENTS WHERE Status='Delivered'\n"
            "Observation: [(6.2, 452)]\n"
            "Thought: Average delivery time is 6.2 days across 452 shipments.\n"
            "Final Answer: Average delivery time for shipments: 6.2 days (based on 452 delivered shipments).\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "EXAMPLE 2 - Inventory Stock (Single Record):\n"
            "Q: Show me inventory for HVL-ELE-00043 in Karachi\n"
            "Thought: Need inventory data. INVENTORY table has PartID, StockLevel, Warehouse columns.\n"
            "Action: sql_db_query\n"
            "Action Input: SELECT PartID, PartName, StockLevel, Warehouse FROM INVENTORY WHERE PartID='HVL-ELE-00043' AND Warehouse='Karachi Main Hub'\n"
            "Observation: [('HVL-ELE-00043', 'Electronic Module', 0, 'Karachi Main Hub')]\n"
            "Thought: Got inventory for HVL-ELE-00043 in Karachi.\n"
            "Final Answer:\n"
            "Part: HVL-ELE-00043\n"
            "Warehouse: Karachi Main Hub\n"
            "Stock Level: 0 units\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "EXAMPLE 3 - Supplier Breakdown:\n"
            "Q: List all China Tier 1 suppliers\n"
            "Thought: Need supplier data. SUPPLIERS table has Country and Tier columns.\n"
            "Action: sql_db_query\n"
            "Action Input: SELECT SupplierName, Country, Tier FROM SUPPLIERS WHERE Country='China' AND Tier='Tier 1'\n"
            "Observation: [('CATL Battery', 'China', 'Tier 1'), ('Great Wall Motors Powertrain', 'China', 'Tier 1')]\n"
            "Thought: Got China Tier 1 suppliers.\n"
            "Final Answer:\n"
            "1. CATL Battery (China, Tier 1)\n"
            "2. Great Wall Motors Powertrain (China, Tier 1)\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "EXAMPLE 4 - Out of Scope:\n"
            "Q: What's the weather in Lahore?\n"
            "Final Answer: OUT_OF_DOMAIN - Ask about orders, suppliers, inventory, shipments, or contracts for Haval Pakistan.\n\n"
        )
        system_prompt = few_shot_example + system_prompt
        from langchain_core.prompts import ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("system", "Available tools: {tools}\nTool names: {tool_names}"),
            ("human", "{input}\n{agent_scratchpad}")
        ])
        self.agent = create_sql_agent(
            llm=self.llm,
            toolkit=self.toolkit,
            agent_type=agent_type,
            verbose=verbose,
            max_iterations=max_iterations,
            handle_parsing_errors=True,
            prefix=system_prompt
        )
        logger.info("SQL Agent initialized successfully")
    
    def _preprocess_query(self, question: str) -> str:
        """
        Preprocess query to fix common typos, expand abbreviations, and improve clarity.
        Handles: typos, abbreviations, misspellings, grammar shortcuts
        """
        import re
        typo_map = {
            r'\bsupplir\b': 'supplier',
            r'\binventry\b': 'inventory',
            r'\bshpment\b': 'shipment',
            r'\bordr\b': 'order',
            r'\bcontrct\b': 'contract',
            r'\bwarehous\b': 'warehouse',
            r'\bpart\b': 'part',
            r'\bqty\b': 'quantity',
            r'\bhow\s+many\b': 'count of',
            r'\blist\s+all\s+': 'list all ',
            r'\bfind\s+all\s+': 'find all ',
            r'\bget\s+all\s+': 'get all ',
            r'\bchina\b': 'China',
            r'\bpakistan\b': 'Pakistan',
            r'\bkarachi\b': 'Karachi',
            r'\blahore\b': 'Lahore',
            r'\bislamabad\b': 'Islamabad',
            r'\bguangzhou\b': 'Guangzhou',
            r'\bshanghai\b': 'Shanghai',
        }
        cleaned = question
        for pattern, replacement in typo_map.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    def query(self, question: str) -> Dict[str, Any]:
        """
        Process a natural language query using the SQL Agent.
        """
        if self.agent is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        preprocessed_question = self._preprocess_query(question)
        if preprocessed_question != question:
            logger.info(f"Query preprocessed: '{question}' -> '{preprocessed_question}'")
        logger.info(f"Processing query: {preprocessed_question}")
        try:
            agent_config = self.config.get('agent', {})
            return_intermediate = agent_config.get('return_intermediate_steps', True)
            max_execution_time = agent_config.get('max_execution_time', 120)
            config = {"return_only_outputs": not return_intermediate}
            if max_execution_time:
                config["max_execution_time"] = max_execution_time
            result = self.agent.invoke(
                {"input": preprocessed_question},
                **config
            )
            logger.info("Query processed successfully")
            return {
                'success': True,
                'output': result.get('output', ''),
                'intermediate_steps': result.get('intermediate_steps', []) if return_intermediate else None
            }
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                'success': False,
                'error': str(e),
                'output': None
            }
    
    def get_table_info(self) -> str:
        """
        Get information about all tables available to the agent.
        """
        if self.sql_database is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.sql_database.get_table_info()
    
    def get_available_tables(self) -> List[str]:
        """
        Get list of tables available to the agent.
        """
        if self.sql_database is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.sql_database.get_usable_table_names()
    
    def execute_sql(self, sql_query: str) -> Any:
        """
        Execute a raw SQL query (for testing purposes).
        """
        if self.sql_database is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        logger.info(f"Executing SQL: {sql_query}")
        return self.sql_database.run(sql_query)

