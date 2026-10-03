"""
Database Adapter for DMS Pipeline
Supports both SQLite (dev) and MSSQL (production)

Usage:
    adapter = DatabaseAdapter(config)
    results = adapter.execute_query("SELECT * FROM RoMaster WHERE DealerId = ?", [101])
"""

import sqlite3
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import pyodbc
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus


@dataclass
class DatabaseConfig:
    """Database configuration"""
    provider: str  # "sqlite" or "mssql"

    # SQLite config
    sqlite_path: Optional[str] = None

    # MSSQL config
    mssql_server: Optional[str] = None
    mssql_database: Optional[str] = None
    mssql_username: Optional[str] = None
    mssql_password: Optional[str] = None
    mssql_port: int = 1433
    mssql_driver: str = "ODBC Driver 17 for SQL Server"
    mssql_trusted_connection: bool = False  # Windows Auth


class DatabaseAdapter:
    """
    Unified database adapter for SQLite and MSSQL.

    Handles:
    - Connection management
    - Query execution (dialect-agnostic)
    - Transaction management
    - Schema introspection
    """

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.provider = config.provider

        if self.provider == "sqlite":
            self.conn = sqlite3.connect(config.sqlite_path)
            self.conn.row_factory = sqlite3.Row

        elif self.provider == "mssql":
            # Build connection string
            # Use just server name for local connections (named pipes)
            # Use server,port for remote TCP connections
            if config.mssql_port and config.mssql_server not in ['localhost', '(local)', '.']:
                server_str = f"{config.mssql_server},{config.mssql_port}"
            else:
                server_str = config.mssql_server

            conn_str = (
                f"DRIVER={{{config.mssql_driver}}};"
                f"SERVER={server_str};"
                f"DATABASE={config.mssql_database};"
            )

            if config.mssql_trusted_connection:
                conn_str += "Trusted_Connection=yes;"
            else:
                conn_str += f"UID={config.mssql_username};PWD={config.mssql_password};"

            self.conn = pyodbc.connect(conn_str)

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def execute_query(self, sql: str, params: Optional[List] = None) -> List[Dict[str, Any]]:
        """
        Execute SELECT query and return results as list of dicts.

        Handles parameterized queries for both SQLite (?) and MSSQL (?).
        """
        cursor = self.conn.cursor()

        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        # Fetch results
        rows = cursor.fetchall()

        # Convert to dict
        if self.provider == "sqlite":
            # sqlite3.Row is dict-like
            results = [dict(row) for row in rows]
        else:
            # pyodbc rows need column names
            columns = [column[0] for column in cursor.description]
            results = [dict(zip(columns, row)) for row in rows]

        return results

    def execute_non_query(self, sql: str, params: Optional[List] = None) -> int:
        """Execute INSERT/UPDATE/DELETE and return affected row count"""
        cursor = self.conn.cursor()

        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        self.conn.commit()
        return cursor.rowcount

    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get table schema (columns, types, etc.)
        Abstracts PRAGMA vs INFORMATION_SCHEMA
        """
        if self.provider == "sqlite":
            cursor = self.conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            rows = cursor.fetchall()

            return [
                {
                    "name": row[1],
                    "type": row[2],
                    "nullable": not row[3],
                    "primary_key": bool(row[5])
                }
                for row in rows
            ]

        elif self.provider == "mssql":
            sql = """
                SELECT
                    COLUMN_NAME as name,
                    DATA_TYPE as type,
                    IS_NULLABLE as nullable,
                    COLUMNPROPERTY(OBJECT_ID(TABLE_SCHEMA + '.' + TABLE_NAME), COLUMN_NAME, 'IsIdentity') as primary_key
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
            """
            cursor = self.conn.cursor()
            cursor.execute(sql, [table_name])
            columns = [column[0] for column in cursor.description]

            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_all_tables(self) -> List[str]:
        """Get list of all tables in database"""
        if self.provider == "sqlite":
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            return [row[0] for row in cursor.fetchall()]

        elif self.provider == "mssql":
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
            """)
            return [row[0] for row in cursor.fetchall()]

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
