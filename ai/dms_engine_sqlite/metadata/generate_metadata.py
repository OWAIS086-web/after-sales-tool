"""
DMS Metadata Generator

Automatically generates rich metadata for all DMS database tables.

Workflow:
1. Extract schema from SQLite (tables, columns, types, constraints)
2. Detect foreign key relationships
3. Sample data values (categorical columns, examples)
4. Use LLM to generate business descriptions and use cases
5. Create searchable text for vector embeddings
6. Save comprehensive JSON metadata files

Usage:
    python -m ai.dms_engine.metadata.generate_metadata
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import re
from config.llm_config import get_llm_for_component

# Paths
DB_PATH = "data/SazgarDMSDW.sqlite"
OUTPUT_DIR = "data/dms_metadata"


@dataclass
class ColumnMetadata:
    """
    Metadata for a single column.

    Matches structure from: docs/DMS_RAG_PRODUCTION_IMPLEMENTATION_PLAN.md
    Phase 1, Step 2: Column metadata example

    Fields are used for:
    - description: LLM-generated business description
    - sample_values: Shown in SQL generation prompts for LLM to understand data patterns
    - searchable: TRUE for VIN, RO#, IDs (exact match searches)
    - semantic_search: TRUE for text fields like JobRequest, descriptions (semantic queries)
    - filterable: TRUE for WHERE clause fields (dates, status, etc.)
    - aggregatable: TRUE for numeric fields (COUNT, SUM, AVG)
    - foreign_key_ref: Used to generate correct JOINs
    """
    name: str
    type: str
    nullable: bool
    primary_key: bool
    description: str = ""
    sample_values: List[Any] = None
    distinct_count: int = 0
    is_categorical: bool = False
    is_foreign_key: bool = False
    foreign_key_ref: Optional[Dict[str, str]] = None
    searchable: bool = False          # For exact lookups (VIN, RO#, IDs)
    semantic_search: bool = False     # For text search (descriptions, requests)
    filterable: bool = False          # For WHERE clauses (dates, status)
    aggregatable: bool = False        # For COUNT/SUM/AVG (numeric fields)

    def __post_init__(self):
        if self.sample_values is None:
            self.sample_values = []


@dataclass
class TableMetadata:
    """
    Complete metadata for a database table.

    Matches structure from: docs/DMS_RAG_PRODUCTION_IMPLEMENTATION_PLAN.md
    Phase 1, Step 2: TableMetadata JSON example

    This metadata powers:
    1. LAYER 2 (Schema Retrieval): searchable_text → ChromaDB embeddings
    2. LAYER 3 (Context Assembly): columns + FKs + sample_queries → LLM context
    3. LAYER 4 (SQL Generation): sample_queries → few-shot examples
    4. Row-Level Security: row_level_security_column → auto-inject WHERE filters
    """
    table_name: str
    business_name: str = ""           # Human-readable name for UI
    description: str = ""              # Business purpose (2-3 sentences)
    business_domain: str = ""          # service|sales|inventory|customer|finance|inspection|campaign|master_data
    common_use_cases: List[str] = None  # 5-10 specific use cases
    columns: List[ColumnMetadata] = None  # Full column metadata
    foreign_keys: List[Dict[str, Any]] = None  # For JOIN generation
    indexes: List[str] = None          # For query optimization hints
    row_count: int = 0                 # Data volume indicator
    sample_queries: List[Dict[str, str]] = None  # Few-shot examples for LLM
    searchable_text: str = ""          # *** EMBEDDED INTO CHROMADB FOR SCHEMA RETRIEVAL ***
    row_level_security_column: Optional[str] = None  # Usually "DealerId"
    metadata_version: str = "1.0"

    def __post_init__(self):
        if self.common_use_cases is None:
            self.common_use_cases = []
        if self.columns is None:
            self.columns = []
        if self.foreign_keys is None:
            self.foreign_keys = []
        if self.indexes is None:
            self.indexes = []
        if self.sample_queries is None:
            self.sample_queries = []


class DMSMetadataGenerator:
    """Generates comprehensive metadata for DMS database tables."""

    def __init__(self, db_path: str, output_dir: str):
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        # Initialize LLM client for metadata generation
        self.llm = get_llm_for_component("dms_metadata_generator")

        # Table categorization patterns
        self.master_patterns = ['master', 'dealers', 'customer', 'model', 'varient', 'vehicle']
        self.transaction_patterns = ['ro', 'invoice', 'booking', 'estimation', 'payment']
        self.detail_patterns = ['details', 'detail']

    def generate_all_metadata(self, skip_empty: bool = True, min_rows: int = 0, specific_tables: Optional[List[str]] = None):
        """
        Generate metadata for all tables in the database.

        Args:
            skip_empty: Skip tables with 0 rows
            min_rows: Minimum row count to process table
            specific_tables: Optional list of specific table names to process (for testing)
        """
        print(f"\n{'='*80}")
        print(f"DMS METADATA GENERATION PIPELINE")
        print(f"{'='*80}\n")

        # Get all tables
        all_tables = self._get_all_tables()

        # Filter to specific tables if provided
        if specific_tables:
            tables = [t for t in all_tables if t in specific_tables]
            print(f"🎯 Processing {len(tables)} specific table(s): {', '.join(tables)}")
            if len(tables) < len(specific_tables):
                missing = set(specific_tables) - set(tables)
                print(f"⚠️  Warning: Tables not found: {', '.join(missing)}")
        else:
            tables = all_tables
            print(f"📊 Found {len(tables)} tables in database")

        print()

        processed = 0
        skipped = 0

        for table_name in tables:
            print(f"\n{'─'*80}")
            print(f"Processing: {table_name}")
            print(f"{'─'*80}")

            # Get row count
            row_count = self._get_row_count(table_name)
            print(f"  Row count: {row_count:,}")

            # Skip if empty or below threshold
            if skip_empty and row_count == 0:
                print(f"  ⏭️  SKIPPED (empty table)")
                skipped += 1
                continue

            if row_count < min_rows:
                print(f"  ⏭️  SKIPPED (below {min_rows} rows)")
                skipped += 1
                continue

            try:
                # Generate metadata
                metadata = self._generate_table_metadata(table_name, row_count)

                # Save to JSON
                output_file = self.output_dir / f"{table_name}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(asdict(metadata), f, indent=2, default=str)

                print(f"  ✅ SUCCESS - Saved to {output_file.name}")
                processed += 1

            except Exception as e:
                print(f"  ❌ ERROR: {str(e)}")
                skipped += 1
                continue

        # Summary
        print(f"\n{'='*80}")
        print(f"GENERATION COMPLETE")
        print(f"{'='*80}")
        print(f"✅ Processed: {processed} tables")
        print(f"⏭️  Skipped:   {skipped} tables")
        print(f"📁 Output:    {self.output_dir}")
        print(f"{'='*80}\n")

    def _get_all_tables(self) -> List[str]:
        """Get list of all tables in database."""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)
        return [row[0] for row in self.cursor.fetchall()]

    def _get_row_count(self, table_name: str) -> int:
        """Get row count for a table."""
        try:
            self.cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
            return self.cursor.fetchone()[0]
        except Exception:
            return 0

    def _generate_table_metadata(self, table_name: str, row_count: int) -> TableMetadata:
        """Generate complete metadata for a single table."""

        print(f"  🔍 Extracting schema...")
        # 1. Extract basic schema
        schema_info = self._extract_schema(table_name)

        print(f"  🔗 Detecting foreign keys...")
        # 2. Detect foreign keys
        foreign_keys = self._extract_foreign_keys(table_name)

        print(f"  📊 Sampling data...")
        # 3. Enhance columns with sample data
        enhanced_columns = self._enhance_columns_with_samples(
            table_name,
            schema_info['columns'],
            foreign_keys
        )

        print(f"  🤖 Generating business descriptions with LLM...")
        # 4. Generate business context using LLM
        business_context = self._generate_business_context(
            table_name,
            enhanced_columns,
            foreign_keys,
            row_count
        )

        print(f"  ✍️  Applying column descriptions...")
        # 5. Apply column descriptions from LLM to columns
        self._apply_column_descriptions(enhanced_columns, business_context.get('column_descriptions', {}))

        print(f"  📝 Creating searchable text...")
        # 6. Create searchable text for embeddings
        searchable_text = self._create_searchable_text(
            table_name,
            business_context,
            enhanced_columns
        )

        # 7. Detect row-level security column
        rls_column = self._detect_rls_column(enhanced_columns)

        # 8. Assemble metadata
        metadata = TableMetadata(
            table_name=table_name,
            business_name=business_context.get('business_name', table_name),
            description=business_context.get('description', ''),
            business_domain=business_context.get('business_domain', ''),
            common_use_cases=business_context.get('common_use_cases', []),
            columns=enhanced_columns,
            foreign_keys=foreign_keys,
            indexes=schema_info.get('indexes', []),
            row_count=row_count,
            sample_queries=business_context.get('sample_queries', []),
            searchable_text=searchable_text,
            row_level_security_column=rls_column
        )

        return metadata

    def _extract_schema(self, table_name: str) -> Dict[str, Any]:
        """Extract table schema (columns, types, constraints)."""

        # Get column info
        self.cursor.execute(f"PRAGMA table_info([{table_name}])")
        pragma_rows = self.cursor.fetchall()

        columns = []
        for row in pragma_rows:
            col = ColumnMetadata(
                name=row['name'],
                type=row['type'] if row['type'] else 'TEXT',
                nullable=not bool(row['notnull']),
                primary_key=bool(row['pk'])
            )
            columns.append(col)

        # Get indexes
        self.cursor.execute(f"PRAGMA index_list([{table_name}])")
        indexes = [row['name'] for row in self.cursor.fetchall()]

        return {
            'columns': columns,
            'indexes': indexes
        }

    def _extract_foreign_keys(self, table_name: str) -> List[Dict[str, Any]]:
        """Extract foreign key relationships."""

        self.cursor.execute(f"PRAGMA foreign_key_list([{table_name}])")
        fk_rows = self.cursor.fetchall()

        foreign_keys = []
        for row in fk_rows:
            fk = {
                'columns': [row['from']],
                'references': {
                    'table': row['table'],
                    'columns': [row['to']]
                },
                'relationship': 'many-to-one'  # Default assumption
            }
            foreign_keys.append(fk)

        return foreign_keys

    def _enhance_columns_with_samples(
        self,
        table_name: str,
        columns: List[ColumnMetadata],
        foreign_keys: List[Dict[str, Any]]
    ) -> List[ColumnMetadata]:
        """Enhance column metadata with sample values and statistics."""

        fk_column_names = {fk['columns'][0] for fk in foreign_keys}

        for col in columns:
            # Mark as foreign key
            if col.name in fk_column_names:
                col.is_foreign_key = True
                for fk in foreign_keys:
                    if col.name in fk['columns']:
                        col.foreign_key_ref = fk['references']

            # Sample values for categorical/small cardinality columns
            try:
                # Get distinct count
                self.cursor.execute(f"SELECT COUNT(DISTINCT [{col.name}]) FROM [{table_name}]")
                col.distinct_count = self.cursor.fetchone()[0]

                # If low cardinality, get sample values
                if col.distinct_count <= 50:
                    col.is_categorical = True
                    self.cursor.execute(f"""
                        SELECT DISTINCT [{col.name}]
                        FROM [{table_name}]
                        WHERE [{col.name}] IS NOT NULL
                        LIMIT 10
                    """)
                    col.sample_values = [row[0] for row in self.cursor.fetchall()]
                else:
                    # Just get a few examples
                    self.cursor.execute(f"""
                        SELECT [{col.name}]
                        FROM [{table_name}]
                        WHERE [{col.name}] IS NOT NULL
                        LIMIT 5
                    """)
                    col.sample_values = [row[0] for row in self.cursor.fetchall()]

            except Exception:
                col.sample_values = []

            # Determine column capabilities
            col.searchable = self._is_searchable_column(col)
            col.semantic_search = self._is_semantic_searchable(col)
            col.filterable = True  # Most columns can be filtered
            col.aggregatable = self._is_aggregatable(col)

        return columns

    def _is_searchable_column(self, col: ColumnMetadata) -> bool:
        """Determine if column should be indexed for exact search."""
        searchable_patterns = ['id', 'no', 'number', 'code', 'vin', 'phone', 'email', 'name']
        return any(pattern in col.name.lower() for pattern in searchable_patterns)

    def _is_semantic_searchable(self, col: ColumnMetadata) -> bool:
        """Determine if column should be used for semantic search."""
        semantic_patterns = ['description', 'request', 'performed', 'comment', 'note', 'remark']
        return any(pattern in col.name.lower() for pattern in semantic_patterns)

    def _is_aggregatable(self, col: ColumnMetadata) -> bool:
        """Determine if column can be aggregated (COUNT, SUM, AVG)."""
        numeric_types = ['INTEGER', 'REAL', 'NUMERIC', 'DECIMAL', 'FLOAT']
        return any(t in col.type.upper() for t in numeric_types)

    def _apply_column_descriptions(self, columns: List[ColumnMetadata], column_descriptions: Dict[str, str]) -> None:
        """
        Apply LLM-generated column descriptions to column metadata.

        This enriches the metadata with human-readable explanations of what each column
        represents and what data it contains. Critical for SQL generation accuracy.

        Args:
            columns: List of column metadata objects
            column_descriptions: Dict mapping column names to descriptions (from LLM)
        """
        if not column_descriptions:
            print(f"    ⚠️  No column descriptions provided by LLM")
            return

        descriptions_applied = 0
        for col in columns:
            if col.name in column_descriptions:
                col.description = column_descriptions[col.name]
                descriptions_applied += 1

        print(f"    ✓ Applied {descriptions_applied}/{len(columns)} column descriptions")

    def _generate_business_context(
        self,
        table_name: str,
        columns: List[ColumnMetadata],
        foreign_keys: List[Dict[str, Any]],
        row_count: int
    ) -> Dict[str, Any]:
        """Use LLM to generate business-friendly context."""

        # Prepare schema summary for LLM
        schema_summary = self._format_schema_for_llm(table_name, columns, foreign_keys, row_count)

        # System prompt
        system_prompt = """You are a database documentation expert specializing in automotive dealership management systems (DMS).

Your task is to analyze database table schemas and generate comprehensive, business-friendly metadata.

Guidelines:
- Use clear, non-technical language for business users
- Focus on practical use cases and business value
- Be specific about what data this table contains
- Identify relationships to business processes
- Generate realistic SQL query examples
- Consider multi-dealership context (row-level security)

Respond ONLY with valid JSON."""

        # User prompt
        user_prompt = f"""Analyze this DMS database table and generate business metadata:

{schema_summary}

Generate comprehensive metadata in this EXACT JSON format:
{{
  "business_name": "Human-readable table name (2-4 words)",
  "description": "Detailed description of what this table stores and its business purpose (2-3 sentences)",
  "business_domain": "Primary domain: service|sales|inventory|customer|finance|inspection|campaign|master_data",
  "common_use_cases": [
    "Specific use case 1 (e.g., 'Find all repair orders for a specific VIN')",
    "Specific use case 2",
    "Specific use case 3",
    "Specific use case 4",
    "Specific use case 5"
  ],
  "column_descriptions": {{
    "ColumnName1": "What this column represents + what it contains. Example: 'RFrom': 'Reporting entity (submitted by). Contains dealer names, SazgarCarPlant, etc.'",
    "ColumnName2": "Another description with data content info",
    "...": "Include ALL columns - be especially detailed for non-obvious column names"
  }},
  "sample_queries": [
    {{
      "question": "Natural language question users might ask",
      "sql": "SELECT ... FROM {table_name} WHERE ...",
      "description": "What this query returns"
    }},
    {{
      "question": "Another common question",
      "sql": "SELECT COUNT(*) FROM {table_name} ...",
      "description": "Statistical query example"
    }},
    {{
      "question": "Cross-table question (if has FKs)",
      "sql": "SELECT ... FROM {table_name} JOIN ... WHERE ...",
      "description": "Join query example"
    }}
  ]
}}

IMPORTANT:
- **COLUMN DESCRIPTIONS (CRITICAL)**: Describe EVERY column, especially non-intuitive names
  - For each column, explain: (1) What it represents, (2) What data it contains
  - Example: "RFrom": "Reporting entity (who submitted this). Contains dealer names like HavalCentralMotors, SazgarCarPlant, etc."
  - Example: "VINNO": "Vehicle identification number. 17-character alphanumeric VIN for unique vehicle tracking."
  - Example: "DealerID": "Dealer identifier (foreign key to DealerRegister). Integer ID mapping to dealer names."
  - Be VERY detailed for abbreviated/unclear column names (RFrom, VINNO, FFS, PDI, CSI, etc.)

- Generate 3-5 realistic SQL queries that users would actually ask
- Include WHERE clauses with realistic filters using column descriptions
- For tables with DealerId, mention row-level security in use cases
- Be specific about business processes (repair orders, invoices, inspections, etc.)
- Use actual column names from the schema above

Generate the JSON now:"""

        try:
            # Call LLM (prompt is positional argument, not keyword)
            response = self.llm.generate(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Low temperature for consistent metadata
                max_tokens=1500
            )

            # Parse JSON response
            content = response.content.strip()

            # Remove markdown code blocks if present
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content)

            metadata = json.loads(content)
            return metadata

        except json.JSONDecodeError as e:
            print(f"    ⚠️  JSON parse error: {e}")
            print(f"    Raw response: {response.content[:200]}...")
            # Return minimal metadata
            return {
                "business_name": table_name,
                "description": f"Database table: {table_name}",
                "business_domain": self._infer_domain(table_name),
                "common_use_cases": [f"Query {table_name} data"],
                "sample_queries": []
            }
        except Exception as e:
            print(f"    ⚠️  LLM error: {e}")
            return {
                "business_name": table_name,
                "description": f"Database table: {table_name}",
                "business_domain": self._infer_domain(table_name),
                "common_use_cases": [],
                "sample_queries": []
            }

    def _format_schema_for_llm(
        self,
        table_name: str,
        columns: List[ColumnMetadata],
        foreign_keys: List[Dict[str, Any]],
        row_count: int
    ) -> str:
        """Format schema information for LLM prompt."""

        lines = [
            f"TABLE: {table_name}",
            f"ROW COUNT: {row_count:,}",
            f"",
            "COLUMNS:"
        ]

        for col in columns:
            col_info = f"  - {col.name} ({col.type})"
            if col.primary_key:
                col_info += " [PRIMARY KEY]"
            if col.is_foreign_key and col.foreign_key_ref:
                col_info += f" [FK → {col.foreign_key_ref['table']}.{col.foreign_key_ref['columns'][0]}]"
            if col.sample_values:
                samples = [str(v)[:30] for v in col.sample_values[:3]]
                col_info += f" | Samples: {', '.join(samples)}"
            lines.append(col_info)

        if foreign_keys:
            lines.append("")
            lines.append("FOREIGN KEY RELATIONSHIPS:")
            for fk in foreign_keys:
                lines.append(f"  - {fk['columns'][0]} → {fk['references']['table']}.{fk['references']['columns'][0]}")

        return "\n".join(lines)

    def _infer_domain(self, table_name: str) -> str:
        """Infer business domain from table name."""
        name_lower = table_name.lower()

        if any(p in name_lower for p in ['ro', 'repair', 'service', 'maintenance']):
            return 'service'
        elif any(p in name_lower for p in ['invoice', 'payment', 'booking', 'sale']):
            return 'sales'
        elif any(p in name_lower for p in ['vehicle', 'inventory', 'stock']):
            return 'inventory'
        elif any(p in name_lower for p in ['customer', 'client']):
            return 'customer'
        elif any(p in name_lower for p in ['pdi', 'ffs', 'sfs', 'inspection']):
            return 'inspection'
        elif any(p in name_lower for p in ['campaign', 'recall']):
            return 'campaign'
        elif any(p in name_lower for p in ['dealer', 'model', 'make', 'master']):
            return 'master_data'
        else:
            return 'other'

    def _create_searchable_text(
        self,
        table_name: str,
        business_context: Dict[str, Any],
        columns: List[ColumnMetadata]
    ) -> str:
        """
        Create searchable text for vector embeddings.

        This field will be embedded into ChromaDB for semantic schema retrieval.
        When user asks a query, we search this text to find top-K relevant tables.

        Format matches: docs/DMS_RAG_PRODUCTION_IMPLEMENTATION_PLAN.md
        Phase 1, Step 2: "searchable_text" example
        """

        parts = [
            f"{table_name} is the {business_context.get('business_name', table_name)} table",
            f"containing {business_context.get('description', 'database records')}",
            f"Use it for {', '.join(business_context.get('common_use_cases', ['querying data'])[:3])}",
        ]

        # Add key column information for better matching
        key_columns = [c.name for c in columns if c.primary_key or c.is_foreign_key or c.searchable]
        if key_columns:
            parts.append(f"Key columns: {', '.join(key_columns[:10])}")

        # Add foreign key relationships for join queries
        fk_refs = [c.foreign_key_ref for c in columns if c.is_foreign_key and c.foreign_key_ref]
        if fk_refs:
            fk_text = ', '.join([f"{ref['table']}" for ref in fk_refs[:3]])
            parts.append(f"Links to {fk_text}")

        # Add domain for filtering
        parts.append(f"Domain: {business_context.get('business_domain', 'other')}")

        return ". ".join(parts) + "."

    def _detect_rls_column(self, columns: List[ColumnMetadata]) -> Optional[str]:
        """Detect row-level security column (usually DealerId)."""
        rls_patterns = ['dealerid', 'dealer_id']
        for col in columns:
            if col.name.lower() in rls_patterns:
                return col.name
        return None

    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate DMS table metadata')
    parser.add_argument('--db', default=DB_PATH, help='Database path')
    parser.add_argument('--output', default=OUTPUT_DIR, help='Output directory')
    parser.add_argument('--skip-empty', action='store_true', default=True, help='Skip empty tables')
    parser.add_argument('--min-rows', type=int, default=0, help='Minimum rows to process')
    parser.add_argument('--tables', nargs='+', help='Specific table name(s) to process (for testing). Example: --tables RoMaster Vehicleinf')

    args = parser.parse_args()

    generator = DMSMetadataGenerator(args.db, args.output)
    try:
        generator.generate_all_metadata(
            skip_empty=args.skip_empty,
            min_rows=args.min_rows,
            specific_tables=args.tables
        )
    finally:
        generator.close()


if __name__ == '__main__':
    main()
