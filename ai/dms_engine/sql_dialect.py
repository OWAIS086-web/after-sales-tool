"""
SQL Dialect Helper
Converts SQLite SQL to MSSQL SQL automatically

Handles:
- Date functions (strftime → FORMAT)
- String functions (|| → +, SUBSTR → SUBSTRING)
- LIMIT → TOP
- GROUP_CONCAT → STRING_AGG
"""

import re
from typing import Dict, Any


class SQLDialect:
    """SQL dialect converter for SQLite ↔ MSSQL"""

    @staticmethod
    def convert_to_mssql(sqlite_sql: str) -> str:
        """
        Convert SQLite SQL to MSSQL SQL.

        Handles common patterns automatically.
        """
        sql = sqlite_sql

        # 1. Date functions: strftime('%Y-%m', Date) → FORMAT(Date, 'yyyy-MM')
        sql = re.sub(
            r"strftime\('%Y-%m',\s*(\w+)\)",
            r"FORMAT(\1, 'yyyy-MM')",
            sql
        )
        sql = re.sub(
            r"strftime\('%Y',\s*(\w+)\)",
            r"YEAR(\1)",
            sql
        )
        sql = re.sub(
            r"strftime\('%m',\s*(\w+)\)",
            r"MONTH(\1)",
            sql
        )

        # 2. Date arithmetic patterns
        # date('now', '-7 days') → DATEADD(DAY, -7, GETDATE())
        sql = re.sub(
            r"date\('now',\s*'([+-]\d+)\s+days?'\)",
            lambda m: f"DATEADD(DAY, {m.group(1)}, GETDATE())",
            sql
        )

        # date('now', '-6 months') → DATEADD(MONTH, -6, GETDATE())
        sql = re.sub(
            r"date\('now',\s*'([+-]\d+)\s+months?'\)",
            lambda m: f"DATEADD(MONTH, {m.group(1)}, GETDATE())",
            sql
        )

        # date('now') → CAST(GETDATE() AS DATE)
        sql = re.sub(r"date\('now'\)", "CAST(GETDATE() AS DATE)", sql)

        # strftime('%Y', 'now') → YEAR(GETDATE())
        sql = re.sub(r"strftime\('%Y',\s*'now'\)", "YEAR(GETDATE())", sql)

        # strftime('%Y-%m', 'now') → FORMAT(GETDATE(), 'yyyy-MM')
        sql = re.sub(r"strftime\('%Y-%m',\s*'now'\)", "FORMAT(GETDATE(), 'yyyy-MM')", sql)

        # 3. julianday() → DATEDIFF
        sql = re.sub(
            r"julianday\((\w+)\)\s*-\s*julianday\((\w+)\)",
            r"DATEDIFF(DAY, \2, \1)",
            sql
        )

        # 4. String concatenation: || → +
        sql = re.sub(r"\|\|", "+", sql)

        # 5. SUBSTR → SUBSTRING
        sql = re.sub(r"\bSUBSTR\(", "SUBSTRING(", sql)

        # 6. GROUP_CONCAT → STRING_AGG
        sql = re.sub(
            r"GROUP_CONCAT\(DISTINCT\s+(\w+)\)",
            r"STRING_AGG(\1, ',')",
            sql
        )
        sql = re.sub(
            r"GROUP_CONCAT\((\w+)\)",
            r"STRING_AGG(\1, ',')",
            sql
        )

        # 7. LIMIT N → TOP N (only if ORDER BY exists)
        # Pattern: SELECT ... ORDER BY ... LIMIT N
        if "ORDER BY" in sql and "LIMIT" in sql:
            sql = re.sub(
                r"(SELECT\s+)(.*?)(\s+FROM.*?ORDER BY.*?)\s+LIMIT\s+(\d+)",
                r"\1TOP \4 \2\3",
                sql,
                flags=re.DOTALL
            )

        # 8. CAST AS TEXT → CAST AS VARCHAR(MAX)
        sql = re.sub(r"CAST\((.*?)\s+AS\s+TEXT\)", r"CAST(\1 AS VARCHAR(MAX))", sql)

        return sql

    @staticmethod
    def get_current_date_sql(provider: str) -> str:
        """Get current date SQL for provider"""
        if provider == "sqlite":
            return "date('now')"
        elif provider == "mssql":
            return "CAST(GETDATE() AS DATE)"
        return "CURRENT_DATE"

    @staticmethod
    def get_limit_clause(provider: str, limit: int, offset: int = 0) -> str:
        """Get LIMIT/TOP clause for provider"""
        if provider == "sqlite":
            if offset > 0:
                return f"LIMIT {limit} OFFSET {offset}"
            return f"LIMIT {limit}"
        elif provider == "mssql":
            if offset > 0:
                return f"OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"
            return f"TOP {limit}"
        return f"LIMIT {limit}"
