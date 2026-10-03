"""
Supply Chain Main Module
Entry point for supply chain pipeline operations.
"""

import logging
import os
import sys
from typing import Any, Dict, Optional

# Add SupplyChain directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from domain_classifier import SupplyChainDomainClassifier
from format_detector import SupplyChainFormatDetector
from query_reformulator import SupplyChainQueryReformulator
from supplychain_pipeline import SupplyChainPipeline, get_supplychain_pipeline

logger = logging.getLogger(__name__)


class SupplyChainManager:
    """
    Main manager for supply chain operations.
    Coordinates domain classification, query reformulation, and pipeline execution.
    """
    
    def __init__(self, db_path: str = None, config: Dict = None):
        """
        Initialize the Supply Chain Manager.
        
        Args:
            db_path: Path to the database file
            config: Configuration dictionary
        """
        self.db_path = db_path or "data/haval_supply_chain.db"
        self.config = config
        
        # Initialize components
        self.pipeline = None
        self.domain_classifier = SupplyChainDomainClassifier()
        self.query_reformulator = SupplyChainQueryReformulator()
        self.format_detector = SupplyChainFormatDetector()
        
    def initialize(self):
        """Initialize the pipeline."""
        if self.pipeline is None:
            self.pipeline = get_supplychain_pipeline(db_path=self.db_path)
            self.pipeline.initialize()
            logger.info("Supply Chain Manager initialized")
    
    def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        Process a user query through the complete pipeline.
        
        Args:
            user_query: User's natural language query
            
        Returns:
            Dict with results and metadata
        """
        if self.pipeline is None:
            self.initialize()
        
        # Step 1: Domain classification
        domain_result = self.domain_classifier.classify(user_query)
        
        if not domain_result['is_in_domain']:
            return {
                'success': False,
                'answer': "This query is out of scope. Please ask about supply chain data: suppliers, parts, purchase orders, inventory, or shipments.",
                'domain_classification': domain_result,
                'error': 'out_of_domain'
            }
        
        # Step 2: Query reformulation
        reformulation_result = self.query_reformulator.reformulate(user_query)
        query_to_execute = reformulation_result['reformulated_query'] or user_query
        
        # Step 3: Format detection
        format_info = self.format_detector.detect(user_query)
        
        # Step 4: Execute query
        try:
            pipeline_result = self.pipeline.query(user_query, query_to_execute)
            
            return {
                'success': pipeline_result['success'],
                'answer': pipeline_result['answer'],
                'sql': pipeline_result.get('sql'),
                'original_query': user_query,
                'reformulated_query': query_to_execute if reformulation_result['is_changed'] else None,
                'domain_classification': domain_result,
                'format_info': format_info,
                'reformulation_changes': reformulation_result.get('changes', [])
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                'success': False,
                'answer': f"Error processing your query: {str(e)}",
                'error': str(e),
                'original_query': user_query
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics from domain classifier."""
        return self.domain_classifier.get_stats()


# Singleton instance
_manager = None


def get_manager(db_path: str = None) -> SupplyChainManager:
    """
    Get or create the Supply Chain Manager singleton.
    
    Args:
        db_path: Optional database path
        
    Returns:
        SupplyChainManager instance
    """
    global _manager
    
    if _manager is None:
        _manager = SupplyChainManager(db_path=db_path)
    
    return _manager


if __name__ == "__main__":
    # Test the supply chain manager
    manager = get_manager()
    manager.initialize()
    
    # Test queries
    test_queries = [
        "How many suppliers do we have?",
        "Show me top 5 suppliers by spend",
        "Which parts are low stock?",
        "List all late deliveries",
        "What's the average lead time for powertrain parts?"
    ]
    
    print("Testing Supply Chain Manager:")
    print("=" * 70)
    
    for query in test_queries:
        print(f"\n🔍 Query: {query}")
        result = manager.process_query(query)
        print(f"✅ Answer: {result['answer'][:200]}")
        if result.get('sql'):
            print(f"📊 SQL: {result['sql'][:100]}...")
    
    print("\n" + "=" * 70)
    print("Stats:", manager.get_stats())
