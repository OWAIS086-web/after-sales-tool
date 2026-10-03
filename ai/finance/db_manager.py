"""
Database Manager Module
Handles database connections and operations for the SQL Agent.
"""

import logging
import os
from typing import List, Optional

from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and provides utilities for table inspection."""
    
    def __init__(self, config: dict):
        """
        Initialize the DatabaseManager.
        
        Args:
            config: Database configuration dictionary
        """
        self.config = config
        self.engine: Optional[Engine] = None
        self._connection_string = None
        
    def _build_connection_string(self) -> str:
        """Build database connection string based on configuration."""
        db_type = self.config.get('type', 'sqlite').lower()
        
        if db_type == 'sqlite':
            db_path = self.config.get('path', 'database.db')
            # Make path absolute if it's relative
            if not os.path.isabs(db_path):
                # Assume db is in same directory as this file
                base_dir = os.path.dirname(os.path.abspath(__file__))
                db_path = os.path.join(base_dir, db_path)
            return f"sqlite:///{db_path}"
        
        elif db_type == 'postgresql':
            host = self.config.get('host', 'localhost')
            port = self.config.get('port', 5432)
            database = self.config.get('database')
            username = self.config.get('username')
            password = self.config.get('password')
            return f"postgresql://{username}:{password}@{host}:{port}/{database}"
        
        elif db_type == 'mysql':
            host = self.config.get('host', 'localhost')
            port = self.config.get('port', 3306)
            database = self.config.get('database')
            username = self.config.get('username')
            password = self.config.get('password')
            return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
        
        elif db_type == 'mssql':
            host = self.config.get('host', 'localhost')
            port = self.config.get('port', 1433)
            database = self.config.get('database')
            username = self.config.get('username')
            password = self.config.get('password')
            driver = self.config.get('driver', 'ODBC Driver 17 for SQL Server')
            return f"mssql+pyodbc://{username}:{password}@{host}:{port}/{database}?driver={driver}"
        
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    def connect(self) -> Engine:
        """
        Create and return a database engine.
        
        Returns:
            SQLAlchemy Engine object
        """
        if self.engine is None:
            self._connection_string = self._build_connection_string()
            logger.info(f"Connecting to database: {self.config.get('type')}")
            self.engine = create_engine(
                self._connection_string,
                echo=False,
                pool_pre_ping=True
            )
            logger.info("Database connection established successfully")
        return self.engine
    
    def get_all_tables(self) -> List[str]:
        """
        Get a list of all table names in the database.
        
        Returns:
            List of table names
        """
        if self.engine is None:
            self.connect()
        
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        logger.info(f"Found {len(tables)} tables in database")
        return tables
    
    def get_filtered_tables(self) -> List[str]:
        """
        Get filtered list of tables based on included/excluded configuration.
        
        Returns:
            List of table names to be used by the agent
        """
        all_tables = self.get_all_tables()
        included_tables = self.config.get('included_tables', [])
        excluded_tables = self.config.get('excluded_tables', [])
        table_name_pattern = self.config.get('table_name_pattern', '')
        
        # If included_tables is specified, use only those
        if included_tables:
            filtered_tables = [t for t in all_tables if t in included_tables]
            logger.info(f"Using {len(filtered_tables)} included tables")
        else:
            # Otherwise, use all tables except excluded ones
            filtered_tables = [t for t in all_tables if t not in excluded_tables]
            logger.info(f"Using {len(filtered_tables)} tables (excluded {len(excluded_tables)})")
        
        # Apply name pattern filter if specified
        if table_name_pattern:
            filtered_tables = [t for t in filtered_tables if table_name_pattern.lower() in t.lower()]
            logger.info(f"Filtered to {len(filtered_tables)} tables containing '{table_name_pattern}'")
        
        return filtered_tables
    
    def get_table_info(self, table_name: str) -> dict:
        """
        Get detailed information about a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary containing table information
        """
        if self.engine is None:
            self.connect()
        
        inspector = inspect(self.engine)
        columns = inspector.get_columns(table_name)
        primary_keys = inspector.get_pk_constraint(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)
        
        return {
            'name': table_name,
            'columns': columns,
            'primary_keys': primary_keys,
            'foreign_keys': foreign_keys
        }
    
    def execute_query(self, query: str) -> list:
        """
        Execute a SQL query and return results.
        
        Args:
            query: SQL query string
            
        Returns:
            List of result rows
        """
        if self.engine is None:
            self.connect()
        
        with self.engine.connect() as connection:
            result = connection.execute(text(query))
            return result.fetchall()
    
    def test_connection(self) -> bool:
        """
        Test if the database connection is working.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            if self.engine is None:
                self.connect()
            
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def close(self):
        """Close the database connection."""
        if self.engine:
            self.engine.dispose()
            self.engine = None
            logger.info("Database connection closed")
