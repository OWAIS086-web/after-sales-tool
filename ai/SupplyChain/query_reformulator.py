"""
Supply Chain Query Reformulator
Reformulates user queries for better SQL generation and understanding.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SupplyChainQueryReformulator:
    """
    Reformulates queries to be more suitable for SQL generation in supply chain context.
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize the query reformulator.
        
        Args:
            llm_client: Optional LLM client for complex reformulation
        """
        self.llm_client = llm_client
        
        # Common abbreviations and their expansions
        self.abbreviations = {
            'po': 'purchase order',
            'sku': 'part number',
            'otd': 'on time delivery',
            'qa': 'quality assurance',
            'qc': 'quality control',
            'wh': 'warehouse',
            'inv': 'inventory',
            'qty': 'quantity',
            'amt': 'amount',
            'no': 'number',
        }
        
        # Typo corrections
        self.typo_corrections = {
            'supplyer': 'supplier',
            'supplyers': 'suppliers',
            'shipmnt': 'shipment',
            'shipmnts': 'shipments',
            'inventry': 'inventory',
            'inventroy': 'inventory',
            'warehous': 'warehouse',
            'warehose': 'warehouse',
            'delivry': 'delivery',
            'deliveries': 'deliveries',
            'ammount': 'amount',
            'amnt': 'amount',
        }
        
        # Query patterns that need reformulation
        self.reformulation_patterns = [
            # Fix common typos
            (r'\bsupplyer\b', 'supplier'),
            (r'\bsupplyers\b', 'suppliers'),
            (r'\binventry\b', 'inventory'),
            (r'\bwarehous\b', 'warehouse'),
            
            # Vague references
            (r'\bit\b', 'the part'),
            (r'\bthey\b', 'the suppliers'),
            (r'\bthem\b', 'the items'),
            
            # Informal language
            (r'\bgonna\b', 'going to'),
            (r'\bwanna\b', 'want to'),
            (r'\bgimme\b', 'give me'),
            
            # Common mistakes
            (r'\bhow much suppliers\b', 'how many suppliers'),
            (r'\bhow much parts\b', 'how many parts'),
        ]
    
    def reformulate(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Reformulate the query for better processing.
        
        Args:
            query: Original user query
            context: Optional context (previous queries, domain info, etc.)
            
        Returns:
            Dict containing reformulated query and metadata
        """
        original_query = query
        reformed = query
        changes = []
        
        # 1. Expand abbreviations
        for abbr, expansion in self.abbreviations.items():
            pattern = r'\b' + re.escape(abbr) + r'\b'
            if re.search(pattern, reformed, re.IGNORECASE):
                reformed = re.sub(pattern, expansion, reformed, flags=re.IGNORECASE)
                changes.append(f"Expanded '{abbr}' to '{expansion}'")
        
        # 2. Fix typos
        for typo, correction in self.typo_corrections.items():
            pattern = r'\b' + re.escape(typo) + r'\b'
            if re.search(pattern, reformed, re.IGNORECASE):
                reformed = re.sub(pattern, correction, reformed, flags=re.IGNORECASE)
                changes.append(f"Corrected '{typo}' to '{correction}'")
        
        # 3. Apply reformulation patterns
        for pattern, replacement in self.reformulation_patterns:
            if re.search(pattern, reformed, re.IGNORECASE):
                reformed = re.sub(pattern, replacement, reformed, flags=re.IGNORECASE)
                changes.append(f"Applied pattern fix")
        
        # 4. Clean up extra spaces
        reformed = re.sub(r'\s+', ' ', reformed).strip()
        
        is_changed = reformed != original_query
        
        return {
            'original_query': original_query,
            'reformulated_query': reformed if is_changed else None,
            'is_changed': is_changed,
            'changes': changes if changes else [],
            'confidence': 0.9 if is_changed else 1.0
        }
    
    def get_intent(self, query: str) -> Dict[str, Any]:
        """
        Extract the intent from the query.
        
        Args:
            query: User query
            
        Returns:
            Dict with intent information
        """
        query_lower = query.lower()
        
        # Identify main entities
        entities = {
            'supplier': bool(re.search(r'\bsupplier', query_lower)),
            'part': bool(re.search(r'\bpart|component', query_lower)),
            'order': bool(re.search(r'\border|purchase', query_lower)),
            'inventory': bool(re.search(r'\binventory|stock', query_lower)),
            'shipment': bool(re.search(r'\bshipment|delivery', query_lower)),
        }
        
        # Identify action
        if re.search(r'\bcount|how many|number of', query_lower):
            action = 'count'
        elif re.search(r'\blist|show|display', query_lower):
            action = 'list'
        elif re.search(r'\baverage|mean|sum|total', query_lower):
            action = 'aggregate'
        elif re.search(r'\bfind|search|locate', query_lower):
            action = 'search'
        else:
            action = 'unknown'
        
        return {
            'action': action,
            'entities': entities,
            'main_entity': max(entities.items(), key=lambda x: x[1])[0] if any(entities.values()) else None
        }
