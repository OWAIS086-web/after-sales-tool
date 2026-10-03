"""
Finance Pipeline
Integrates the SQL Agent with the finance mode for database queries.
"""

import logging
import os
import sys
from typing import Any, Dict, Optional

# Use absolute imports to avoid module name collision with SupplyChain
from ai.finance.db_manager import DatabaseManager
from ai.finance.sql_agent import SQLAgent

logger = logging.getLogger(__name__)


class FinancePipeline:
    """
    Finance query pipeline using SQL Agent for database queries.
    """
    
    def __init__(self, db_path: str = None, config: Dict = None):
        """
        Initialize the Finance Pipeline.
        
        Args:
            db_path: Path to the database file (overrides config)
            config: Configuration dict from central config.yml (finance section)
        """
        self.db_path = db_path
        self.config = config
        self.db_manager = None
        self.sql_agent = None
        self._initialized = False
        
    def initialize(self):
        """Initialize the finance pipeline components."""
        if self._initialized:
            return
            
        try:
            # Use config from central config.yml
            if not self.config:
                # Fallback: load from config_loader
                from config.config_loader import get_config
                central_config = get_config()
                self.config = central_config.get('finance', {})
            
            logger.info("Loading finance config from central config.yml")
            
            # Prepare database config
            db_config = self.config.get('database', {})
            if self.db_path:
                db_config['path'] = self.db_path
                logger.info(f"Using database: {self.db_path}")
            
            # Initialize database manager
            logger.info("Initializing finance database manager...")
            self.db_manager = DatabaseManager(db_config)
            
            # Test database connection
            if not self.db_manager.test_connection():
                raise RuntimeError("Failed to connect to finance database")
            
            # Prepare langchain config
            langchain_config = {
                'llm': self.config.get('llm', {}),
                'agent': self.config.get('agent', {}),
                'toolkit': self.config.get('toolkit', {}),
            }
            
            # Initialize SQL agent
            logger.info("Initializing finance SQL agent...")
            self.sql_agent = SQLAgent(self.db_manager, langchain_config)
            self.sql_agent.initialize()
            
            self._initialized = True
            logger.info("Finance pipeline initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize finance pipeline: {e}")
            raise
    
    def query(self, user_query: str, reformulated_query: str = None) -> Dict[str, Any]:
        """
        Execute a finance query against the database.
        
        Args:
            user_query: Original user query
            reformulated_query: Reformulated query (if available)
            
        Returns:
            Dict with query results and metadata
        """
        if not self._initialized:
            self.initialize()
        
        # Use reformulated query if available, otherwise use original
        query_to_execute = reformulated_query or user_query
        
        try:
            logger.info(f"Executing finance query: {query_to_execute[:100]}")
            
            # Execute query through SQL agent
            result = self.sql_agent.query(query_to_execute)
            
            # Extract answer and metadata
            answer = result.get('output', '')
            intermediate_steps = result.get('intermediate_steps') or []
            
            # Extract SQL query if available
            sql_query = None
            for step in intermediate_steps:
                if len(step) > 0 and hasattr(step[0], 'tool'):
                    if step[0].tool == 'sql_db_query':
                        sql_query = step[0].tool_input
                        break
            
            return {
                'success': True,
                'answer': answer,
                'sql': sql_query,
                'original_query': user_query,
                'reformulated_query': reformulated_query,
                'intermediate_steps': len(intermediate_steps),
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Finance query failed: {e}")
            
            return {
                'success': False,
                'answer': f"Sorry, I couldn't process your finance query. Error: {str(e)}",
                'sql': None,
                'original_query': user_query,
                'reformulated_query': reformulated_query,
                'error': str(e)
            }
    
    def get_available_tables(self) -> list:
        """Get list of available database tables."""
        if not self._initialized:
            self.initialize()
        
        try:
            return self.sql_agent.get_available_tables()
        except Exception as e:
            logger.error(f"Failed to get tables: {e}")
            return []
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            if not self._initialized:
                self.initialize()
            return self.db_manager.test_connection()
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


# Singleton instance
_finance_pipeline = None


def get_finance_pipeline(db_path: str = None) -> FinancePipeline:
    """
    Get or create the finance pipeline singleton.
    
    Args:
        db_path: Optional database path
        
    Returns:
        FinancePipeline instance
    """
    global _finance_pipeline
    
    if _finance_pipeline is None:
        _finance_pipeline = FinancePipeline(db_path=db_path)
    
    return _finance_pipeline
