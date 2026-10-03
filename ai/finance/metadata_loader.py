"""
Metadata Loader Module
Loads and formats DMS table metadata from JSON files for use by the SQL Agent.
"""

import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MetadataLoader:
    """Loads and manages DMS table metadata."""
    
    def __init__(self, metadata_dir: str = "dms_metadata"):
        """
        Initialize the metadata loader.
        
        Args:
            metadata_dir: Directory containing metadata JSON files
        """
        self.metadata_dir = metadata_dir
        self.metadata_cache = {}
        
    def load_all_metadata(self) -> Dict[str, dict]:
        """
        Load all metadata JSON files from the directory.
        
        Returns:
            Dictionary mapping table names to their metadata
        """
        if not os.path.exists(self.metadata_dir):
            logger.warning(f"Metadata directory not found: {self.metadata_dir}")
            return {}
        
        metadata = {}
        json_files = [f for f in os.listdir(self.metadata_dir) if f.endswith('.json')]
        
        for filename in json_files:
            filepath = os.path.join(self.metadata_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    table_meta = json.load(f)
                    table_name = table_meta.get('table_name')
                    if table_name:
                        metadata[table_name] = table_meta
                        # logger.debug(f"Loaded metadata for table: {table_name}")
            except Exception as e:
                logger.error(f"Error loading metadata from {filename}: {e}")
        
        logger.info(f"Loaded metadata for {len(metadata)} tables")
        self.metadata_cache = metadata
        return metadata
    
    def get_table_metadata(self, table_name: str) -> Optional[dict]:
        """
        Get metadata for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Table metadata dictionary or None if not found
        """
        if not self.metadata_cache:
            self.load_all_metadata()
        return self.metadata_cache.get(table_name)
    
    def format_table_context(self, table_name: str) -> str:
        """
        Format table metadata into a human-readable context string.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Formatted context string
        """
        meta = self.get_table_metadata(table_name)
        if not meta:
            return f"No metadata available for table {table_name}"
        
        context = []
        context.append(f"\n### {meta.get('table_name')} ({meta.get('business_name', 'N/A')})")
        context.append(f"**Description**: {meta.get('description', 'N/A')}")
        context.append(f"**Business Domain**: {meta.get('business_domain', 'N/A')}")
        
        # Common use cases
        use_cases = meta.get('common_use_cases', [])
        if use_cases:
            context.append("\n**Common Use Cases**:")
            for i, use_case in enumerate(use_cases, 1):
                context.append(f"{i}. {use_case}")
        
        # Key columns
        columns = meta.get('columns', [])
        if columns:
            context.append("\n**Key Columns**:")
            for col in columns[:10]:  # Limit to first 10 columns to avoid token overload
                col_info = f"- `{col['name']}` ({col['type']}): {col.get('description', 'N/A')}"
                if col.get('is_foreign_key'):
                    col_info += f" [FK: {col.get('foreign_key_ref')}]"
                if col.get('sample_values'):
                    samples = col['sample_values'][:3]
                    col_info += f" Examples: {samples}"
                context.append(col_info)
        
        return "\n".join(context)
    
    def format_all_context(self, table_names: List[str]) -> str:
        """
        Format metadata for multiple tables into a comprehensive context.
        
        Args:
            table_names: List of table names
            
        Returns:
            Formatted context string for all tables
        """
        contexts = []
        contexts.append("# Database Schema Context\n")
        contexts.append("This is a Dealer Management System (DMS) for automotive dealerships.")
        contexts.append("Below is detailed metadata about the tables you can query:\n")
        
        for table_name in table_names:
            table_context = self.format_table_context(table_name)
            contexts.append(table_context)
        
        return "\n".join(contexts)
    
    def get_column_descriptions(self, table_name: str) -> Dict[str, str]:
        """
        Get a mapping of column names to their descriptions.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary mapping column names to descriptions
        """
        meta = self.get_table_metadata(table_name)
        if not meta:
            return {}
        
        descriptions = {}
        for col in meta.get('columns', []):
            col_name = col.get('name')
            col_desc = col.get('description', '')
            if col_name:
                descriptions[col_name] = col_desc
        
        return descriptions
    
    def get_searchable_columns(self, table_name: str) -> List[str]:
        """
        Get list of columns that are marked as searchable.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of searchable column names
        """
        meta = self.get_table_metadata(table_name)
        if not meta:
            return []
        
        searchable = []
        for col in meta.get('columns', []):
            if col.get('searchable', False):
                searchable.append(col['name'])
        
        return searchable
    
    def get_foreign_key_relationships(self) -> Dict[str, List[dict]]:
        """
        Extract foreign key relationships from all tables.
        
        Returns:
            Dictionary mapping table names to their foreign key relationships
        """
        relationships = {}
        
        for table_name, meta in self.metadata_cache.items():
            fks = []
            for col in meta.get('columns', []):
                if col.get('is_foreign_key'):
                    fks.append({
                        'column': col['name'],
                        'references': col.get('foreign_key_ref')
                    })
            if fks:
                relationships[table_name] = fks
        
        return relationships
