"""
SQL Agent Module
Implements the LangChain SQL Agent for natural language database queries.
Uses centralized config from config/llm_config.py (xAI provider only).
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_community.agent_toolkits import (SQLDatabaseToolkit,
                                                create_sql_agent)
from langchain_community.utilities import SQLDatabase

logger = logging.getLogger(__name__)


class SQLAgent:
    """LangChain SQL Agent for natural language database interactions."""
    
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

        # Initialize LLM based on provider (only xAI supported for finance)
        if provider == 'xai':
            import os

            from langchain_openai import ChatOpenAI

            from config.llm_config import get_llm_config

            # Get xAI config from centralized llm_config.py
            finance_sql_config = get_llm_config('finance_sql_agent')
            
            # Get API key from centralized config's api_key_env
            api_key_env = finance_sql_config.api_key_env or 'XAI_API_KEY'
            api_key = os.getenv(api_key_env)
            
            if not api_key:
                raise ValueError(f"{api_key_env} not found in environment. Ensure root .env is loaded.")
            
            # Get rate limit and timeout settings from YAML config
            llm_config = self.config.get('langchain', {}).get('llm', {})
            request_timeout = llm_config.get('request_timeout', 60)
            max_retries = llm_config.get('max_retries', 3)
            
            self.llm = ChatOpenAI(
                model=finance_sql_config.model_name,
                temperature=finance_sql_config.temperature,
                max_tokens=finance_sql_config.max_tokens,
                api_key=api_key,
                base_url="https://api.x.ai/v1",
                timeout=request_timeout,
                max_retries=max_retries
            )
            logger.info(f"Initialized xAI LLM: {finance_sql_config.model_name} (config: finance_sql_agent, timeout={request_timeout}s)")
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}. Finance mode only supports 'xai'.")
    
    def _initialize_database(self):
        """Initialize the SQL Database wrapper for LangChain."""
        engine = self.db_manager.connect()
        filtered_tables = self.db_manager.get_filtered_tables()
        
        toolkit_config = self.config.get('toolkit', {})
        sample_rows = toolkit_config.get('sample_rows_in_table_info', 3)
        
        # Load DMS metadata
        custom_table_info = self._load_dms_metadata(filtered_tables)
        
        self.sql_database = SQLDatabase(
            engine=engine,
            include_tables=filtered_tables,
            sample_rows_in_table_info=sample_rows,
            custom_table_info=custom_table_info
        )
        
        logger.info(f"Initialized SQL Database with {len(filtered_tables)} tables")
    
    def _load_dms_metadata(self, table_names: list) -> dict:
        """Load DMS table metadata from JSON files (token-optimized)."""
        import os

        from ai.finance.metadata_loader import MetadataLoader

        # Get metadata folder from config, default to 'dms_metadata'
        metadata_folder = self.config.get('metadata', {}).get('folder', 'dms_metadata')
        # Make path absolute if it's relative
        if not os.path.isabs(metadata_folder):
            finance_dir = os.path.dirname(os.path.abspath(__file__))
            metadata_folder = os.path.join(finance_dir, metadata_folder)
        loader = MetadataLoader(metadata_dir=metadata_folder)
        metadata = loader.load_all_metadata()
        
        if not metadata:
            logger.warning("No DMS metadata found, using default schema info")
            return None
        
        # Create minimal custom table info for each table (token-efficient)
        custom_info = {}
        for table_name in table_names:
            if table_name in metadata:
                table_meta = metadata[table_name]
                
                # Only include essential info to save tokens
                context_parts = []
                context_parts.append(f"{table_meta.get('business_name', table_name)}: {table_meta.get('description', '')[:200]}")
                
                # Only top 2 use cases (most important)
                use_cases = table_meta.get('common_use_cases', [])
                if use_cases:
                    context_parts.append(f"Use: {use_cases[0]}")
                
                # Only key columns (primary keys, foreign keys, and first 5 searchable)
                columns = table_meta.get('columns', [])
                key_cols = []
                for col in columns:
                    if col.get('primary_key') or col.get('is_foreign_key') or (col.get('searchable') and len(key_cols) < 5):
                        key_cols.append(f"{col['name']}({col['type']})")
                    if len(key_cols) >= 8:  # Max 8 columns
                        break
                
                if key_cols:
                    context_parts.append(f"Cols: {', '.join(key_cols)}")
                
                custom_info[table_name] = ". ".join(context_parts)
                # logger.debug(f"Loaded minimal metadata for {table_name}")
        
        logger.info(f"Loaded compact DMS metadata for {len(custom_info)} tables")
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
        
        # Initialize components
        self._initialize_llm()
        self._initialize_database()
        self._initialize_toolkit()
        
        # Create the agent with a strong system prompt and optimized config
        agent_config = self.config.get('agent', {})
        agent_type = agent_config.get('type', 'openai-tools')
        max_iterations = 10  # Increased for more reasoning steps
        verbose = agent_config.get('verbose', True)

        # Build a strong system prompt using metadata and explicit table/column names
        available_tables = self.db_manager.get_filtered_tables()
        try:
            import os

            from ai.finance.metadata_loader import MetadataLoader

            # Get metadata folder from config
            metadata_folder = self.config.get('metadata', {}).get('folder', 'dms_metadata')
            # Make path absolute if it's relative
            if not os.path.isabs(metadata_folder):
                finance_dir = os.path.dirname(os.path.abspath(__file__))
                metadata_folder = os.path.join(finance_dir, metadata_folder)
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
            "You are an EXPERT SQL assistant for the HAVAL CEO FINANCE DATABASE (Automobile company operations in Pakistan).\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "🎯 YOUR MISSION: Generate accurate SQL → Execute → Return clear answers\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            "DATABASE CONTEXT (AUTOMOBILE COMPANY ONLY - NO BANKING):\n"
            "- 200 VEHICLE_SALES records (Sales transactions, profitability tracking)\n"
            "- 120 DEALER_PERFORMANCE records (Monthly dealer metrics, targets, commissions)\n"
            "- 300 INVENTORY_STOCK records (Vehicle inventory, aging, VIN tracking)\n"
            "- 864 REVENUE_EXPENSES records (Complete P&L statements)\n"
            "- Coverage: 2024-2026 fiscal years\n"
            "- Geographic: Pakistan (Sindh, Punjab, KPK, ICT)\n"
            "- Models: Haval H6 (5 variants), Haval Jolion (3 variants)\n\n"
            "WORKFLOW (FAST & ACCURATE):\n"
            "1️⃣ UNDERSTAND: Read query → Identify intent (ignore typos)\n"
            "2️⃣ VERIFY: Check table metadata below → Find EXACT column names\n"
            "3️⃣ WRITE SQL: Use verified columns → Add LIMIT if needed\n"
            "4️⃣ EXECUTE: Run sql_db_query ONCE (minimize iterations)\n"
            "5️⃣ ANSWER: Format results clearly with context\n\n"
            "TYPO TOLERANCE (CRITICAL):\n"
            "✓ 'vehicl' → vehicle | 'invntory' → inventory | 'reveue' → revenue\n"
            "✓ 'g mor than' → greater than | 'proffit' → profit | 'mor than' → more than\n"
            "✓ 'haval h6' → H6 | 'delear' → dealer | 'inventry' → inventory\n"
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
            "  - VEHICLE_SALES: SaleID, SaleDate, VehicleModel, VehicleVariant, SalePrice, GrossProfit, ProfitMarginPercent, DealerRegion, Quarter\n"
            "  - DEALER_PERFORMANCE: DealerID, DealerName, MonthYear, TotalSales, TotalRevenue, InventoryTurnoverRatio, TargetAchievementPercent\n"
            "  - INVENTORY_STOCK: VIN, VehicleModel, Status, DaysInInventory, AgeCategory, CostPrice, DealerLocation\n"
            "  - REVENUE_EXPENSES: TransactionDate, Category, Type, Amount, Department, Quarter, FiscalYear\n\n"
            "DATABASE-SPECIFIC:\n"
            "• SQLite syntax: Use STRFTIME('%Y', date) for year, STRFTIME('%m', date) for month\n"
            "• Case-insensitive search: Use LOWER(column) LIKE LOWER('%value%')\n"
            "• Vehicle models: 'Haval H6' (variants: 1.5T Comfort, 1.5T Luxury, 2.0T Premium, 1.5T HEV, PHEV)\n"
            "• Vehicle models: 'Haval Jolion' (variants: Comfort, Luxury, Premium)\n"
            "• Regions: Sindh, Punjab, KPK, ICT (Islamabad Capital Territory)\n"
            "• Cities: Karachi, Lahore, Islamabad, Rawalpindi, Faisalabad, Multan, Peshawar\n"
            "• Currency: All amounts in PKR (Pakistani Rupees)\n"
            "• Quarters: Q1, Q2, Q3, Q4 | Fiscal Years: 2024, 2025, 2026\n\n"
            "QUERY OPTIMIZATION:\n"
            "• Add LIMIT 10 for single-record queries (e.g., 'show customer X')\n"
            "• Add LIMIT 20 for list queries (e.g., 'list all loans')\n"
            "• Use COUNT(*) first if asked 'how many'\n"
            "• For aggregates (AVG, SUM, MAX), no LIMIT needed\n"
            "• For JOINs: Use table aliases (c for Customers, l for Loans, etc.)\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "📊 ANSWER FORMATTING (USER-FRIENDLY)\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            "AGGREGATES (COUNT, SUM, AVG):\n"
            "✓ Direct answer: 'There are 45 Haval H6 sales in Q4 2025.'\n"
            "✓ With context: 'Average profit margin: 15.3% across 200 sales.'\n"
            "✓ Multiple stats: '• Total Revenue: Rs 1.2B\\n• Units Sold: 200\\n• Avg Sale Price: Rs 6M'\n\n"
            "SINGLE RECORD:\n"
            "✓ Structured format with labels:\n"
            "  Sale Date: 2025-12-15\n"
            "  Model: Haval H6 2.0T Premium\n"
            "  Sale Price: Rs 10,158,617\n"
            "  Dealer: Haval Karachi Central (Sindh)\n"
            "  Profit Margin: 15.35%\n\n"
            "MULTIPLE RECORDS (≤10):\n"
            "✓ Numbered list with key fields:\n"
            "  1. Haval Karachi Central - Rs 95M revenue - 22 units\n"
            "  2. Haval Lahore DHA - Rs 87M revenue - 18 units\n"
            "  [Continue for all records]\n\n"
            "LARGE RESULTS (>20):\n"
            "✓ Show summary + first 10:\n"
            "  'Found 45 customers from Punjab. Showing first 10:'\n"
            "  [List 10 records]\n"
            "  'Use filters to narrow down results.'\n\n"
            "NO RESULTS:\n"
            "✓ Clear statement: 'No customers found with income > 200,000 in Quetta.'\n"
            "✓ Suggest alternatives: 'Try: Karachi (18 customers) or Lahore (12 customers)'\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "🚫 OUT OF SCOPE - REJECT IMMEDIATELY\n"
            "═══════════════════════════════════════════════════════════════\n"
            "If query about: weather, recipes, sports, politics, entertainment, general knowledge\n"
            "→ Respond: 'OUT_OF_DOMAIN - Ask about vehicle sales, dealer performance, inventory, or revenue/expenses for Haval Pakistan.'\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "📝 AGENT FORMAT (LANGCHAIN REQUIRED)\n"
            "═══════════════════════════════════════════════════════════════\n"
            "Thought: [Understand query, verify columns]\n"
            "Action: sql_db_query\n"
            "Action Input: SELECT ... (your SQL)\n"
            "Observation: [Query results]\n"
            "Thought: [Interpret results]\n"
            "Final Answer: [Formatted response to user]\n\n"
            "⚠️ NEVER include 'Action:' after 'Final Answer:' - that signals completion!\n\n"
        )
        
        # Finance-specific few-shot examples
        few_shot_example = (
            "═══════════════════════════════════════════════════════════════\n"
            "💡 FEW-SHOT EXAMPLES (LEARN THE PATTERN)\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            "EXAMPLE 1 - Aggregate Query (Average Profit Margin):\n"
            "Q: What's the average profit margin for H6 sales?\n"
            "Thought: Need to calculate average profit margin for H6 vehicles. VEHICLE_SALES table has VehicleModel and ProfitMarginPercent columns.\n"
            "Action: sql_db_query\n"
            "Action Input: SELECT AVG(ProfitMarginPercent) as AvgMargin, COUNT(*) as TotalSales FROM VEHICLE_SALES WHERE VehicleModel LIKE '%H6%'\n"
            "Observation: [(15.34, 120)]\n"
            "Thought: Average profit margin is 15.34% across 120 H6 sales.\n"
            "Final Answer: Average profit margin for Haval H6: 15.34% (based on 120 sales transactions).\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "EXAMPLE 2 - Dealer Performance (Single Record):\n"
            "Q: Show me Haval Karachi Central dealer performance\n"
            "Thought: Need dealer performance data. DEALER_PERFORMANCE table has DealerName, TotalRevenue, TotalSales, TargetAchievementPercent.\n"
            "Action: sql_db_query\n"
            "Action Input: SELECT DealerName, MonthYear, TotalSales, TotalRevenue, TargetAchievementPercent, CustomerSatisfactionScore FROM DEALER_PERFORMANCE WHERE DealerName='Haval Karachi Central' ORDER BY MonthYear DESC LIMIT 1\n"
            "Observation: [('Haval Karachi Central', '2025-12', 22, 95487654, 110.5, 8.7)]\n"
            "Thought: Got latest performance for Karachi dealer.\n"
            "Final Answer:\n"
            "Dealer: Haval Karachi Central\n"
            "Month: December 2025\n"
            "Total Sales: 22 units\n"
            "Revenue: Rs 95.5M\n"
            "Target Achievement: 110.5%\n"
            "Customer Satisfaction: 8.7/10\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "EXAMPLE 3 - Quarter-by-Quarter Revenue:\n"
            "Q: Show quarterly revenue for 2025\n"
            "Thought: Need revenue by quarter. Use VEHICLE_SALES table with Quarter and FiscalYear, sum SalePrice.\n"
            "Action: sql_db_query\n"
            "Action Input: SELECT Quarter, SUM(SalePrice) as Revenue, COUNT(*) as Units FROM VEHICLE_SALES WHERE FiscalYear = 2025 GROUP BY Quarter ORDER BY CASE Quarter WHEN 'Q1' THEN 1 WHEN 'Q2' THEN 2 WHEN 'Q3' THEN 3 WHEN 'Q4' THEN 4 END\n"
            "Observation: [('Q1', 305478923, 48), ('Q2', 298765432, 46), ('Q3', 312456789, 51), ('Q4', 289234567, 45)]\n"
            "Thought: Got quarterly breakdown for 2025.\n"
            "Final Answer: 2025 Quarterly Revenue:\n\n"
            "Q1: Rs 305.5M (48 units)\n"
            "Q2: Rs 298.8M (46 units)\n"
            "Q3: Rs 312.5M (51 units)\n"
            "Q4: Rs 289.2M (45 units)\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "EXAMPLE 4 - Aging Inventory:\n"
            "Q: How many vehicles aging over 90 days?\n"
            "Thought: Query INVENTORY_STOCK table for Status='Available' and DaysInInventory > 90.\n"
            "Action: sql_db_query\n"
            "Action Input: SELECT COUNT(*) as AgingUnits, SUM(CostPrice) as CapitalTiedUp FROM INVENTORY_STOCK WHERE Status = 'Available' AND DaysInInventory > 90\n"
            "Observation: [(12, 87654321)]\n"
            "Thought: 12 units aging over 90 days worth Rs 87.7M.\n"
            "Final Answer: 12 vehicles aging over 90 days, representing Rs 87.7M in tied-up capital. Recommend pricing action to move aging stock.\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "EXAMPLE 5 - Out of Scope:\n"
            "Q: What's the weather in Lahore?\n"
            "Final Answer: OUT_OF_DOMAIN - Ask about vehicle sales, dealer performance, inventory, or revenue/expenses for Haval Pakistan.\n\n"
        )
        system_prompt = few_shot_example + system_prompt
        
        # Use a custom prompt template for all providers
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
        
        Args:
            question: Raw user query
            
        Returns:
            Cleaned and expanded query
        """
        import re

        # Comprehensive typo corrections and expansions
        typo_map = {
            # Common typing mistakes
            r'\bg\s+mor\b': 'more',
            r'\bwher\s': 'where ',
            r'\bwhre\b': 'where',
            r'\bthan\s+\d': 'than ',  # Keep space after 'than' before numbers
            
            # Comparisons and operators
            r'\bgreter\b': 'greater',
            r'\bgrater\b': 'greater',
            r'\bgreatr\b': 'greater',
            r'\blesss\b': 'less',
            r'\blesser\b': 'less',
            r'\bequl\b': 'equal',
            r'\beqal\b': 'equal',
            
            # Entity names (customers, accounts, etc.)
            r'\bcustomres\b': 'customers',
            r'\bcustmers\b': 'customers',
            r'\bcustomer\s+name\b': 'customer name',
            r'\baccont\b': 'account',
            r'\baccout\b': 'account',
            r'\baccounts?\s+no\b': 'account number',
            r'\bacount\b': 'account',
            
            # Financial terms
            r'\bloan\s+ammount\b': 'loan amount',
            r'\bloan\s+amnt\b': 'loan amount',
            r'\boutstandng\b': 'outstanding',
            r'\boustanding\b': 'outstanding',
            r'\boutstandin\b': 'outstanding',
            r'\bpaymnts\b': 'payments',
            r'\bpayment\s': 'payment ',
            r'\bpaymnt\b': 'payment',
            r'\btransction\b': 'transaction',
            r'\btransacton\b': 'transaction',
            r'\binvestmnt\b': 'investment',
            r'\binvestment\b': 'investment',
            
            # Verbs and actions
            r'\bhav\b': 'have',
            r'\bhve\b': 'have',
            r'\bshwo\b': 'show',
            r'\bshw\b': 'show',
            r'\blist\s+all\s+': 'list all ',
            r'\bfind\s+all\s+': 'find all ',
            r'\bget\s+all\s+': 'get all ',
            
            # Vehicle terms
            r'\bhaval\s+h6\b': 'Haval H6',
            r'\bhaval\s+h\s*6\b': 'Haval H6',
            r'\bh6\b': 'H6',
            r'\bjolion\b': 'Jolion',
            r'\bvehcle\b': 'vehicle',
            r'\bvehical\b': 'vehicle',
            
            # Common abbreviations - expand for clarity
            r'\bcust\b': 'customer',
            r'\bacct\b': 'account',
            r'\btxn\b': 'transaction',
            r'\bamt\b': 'amount',
            r'\bqty\b': 'quantity',
            r'\bno\.?\s+of\b': 'number of',
            r'\bhow\s+many\b': 'count of',
            
            # Grammar fixes
            r'\bname\s+of\s+customers?\b': 'customer names',
            r'\blist\s+of\s+customers?\b': 'customers list',
        }
        
        cleaned = question
        for pattern, replacement in typo_map.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        
        # Remove extra spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def query(self, question: str) -> Dict[str, Any]:
        """
        Process a natural language query using the SQL Agent.
        
        Args:
            question: Natural language question
        
        Returns:
            Dictionary containing the answer and metadata
        """
        if self.agent is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        # Preprocess query to fix common typos
        preprocessed_question = self._preprocess_query(question)
        if preprocessed_question != question:
            logger.info(f"Query preprocessed: '{question}' -> '{preprocessed_question}'")
        
        logger.info(f"Processing query: {preprocessed_question}")
        
        try:
            agent_config = self.config.get('agent', {})
            return_intermediate = agent_config.get('return_intermediate_steps', True)
            max_execution_time = agent_config.get('max_execution_time', 120)
            
            # Add timeout configuration
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
        
        Returns:
            String containing table information
        """
        if self.sql_database is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        return self.sql_database.get_table_info()
    
    def get_available_tables(self) -> List[str]:
        """
        Get list of tables available to the agent.
        
        Returns:
            List of table names
        """
        if self.sql_database is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        return self.sql_database.get_usable_table_names()
    
    def execute_sql(self, sql_query: str) -> Any:
        """
        Execute a raw SQL query (for testing purposes).
        
        Args:
            sql_query: SQL query string
            
        Returns:
            Query results
        """
        if self.sql_database is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        logger.info(f"Executing SQL: {sql_query}")
        return self.sql_database.run(sql_query)



