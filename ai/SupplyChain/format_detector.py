"""
Supply Chain Format Detector
Detects the expected format and type of query/response.
"""

import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of queries."""
    COUNT = "count"
    LIST = "list"
    AGGREGATE = "aggregate"
    SEARCH = "search"
    COMPARISON = "comparison"
    ANALYTICAL = "analytical"
    UNKNOWN = "unknown"


class ResponseFormat(Enum):
    """Expected response formats."""
    SINGLE_VALUE = "single_value"
    TABLE = "table"
    LIST = "list"
    CHART = "chart"
    SUMMARY = "summary"
    DETAILED = "detailed"


class SupplyChainFormatDetector:
    """
    Detects query type and expected response format for supply chain queries.
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize the format detector.
        
        Args:
            llm_client: Optional LLM client for complex detection
        """
        self.llm_client = llm_client
        
        # Query type patterns
        self.query_patterns = {
            QueryType.COUNT: [
                r'how many',
                r'count (of |the )?',
                r'number of',
                r'total (number of |count of |)',
                r'how much'
            ],
            QueryType.LIST: [
                r'show (me |all |the )?',
                r'list (all |the |)',
                r'display (all |the |)',
                r'get (all |the |)',
                r'fetch (all |the |)',
                r'give me (all |the |)'
            ],
            QueryType.AGGREGATE: [
                r'average',
                r'mean',
                r'sum of',
                r'total (amount|value|cost|spend)',
                r'maximum',
                r'minimum',
                r'highest',
                r'lowest'
            ],
            QueryType.SEARCH: [
                r'find (all |the |)',
                r'search for',
                r'look for',
                r'where is',
                r'which (supplier|part|shipment)'
            ],
            QueryType.COMPARISON: [
                r'compare',
                r'difference between',
                r'vs\.?',
                r'versus',
                r'better than',
                r'more than',
                r'less than'
            ],
            QueryType.ANALYTICAL: [
                r'analyze',
                r'analysis of',
                r'trend',
                r'pattern',
                r'insight',
                r'breakdown',
                r'distribution'
            ]
        }
    
    def detect(self, query: str) -> Dict[str, Any]:
        """
        Detect query type and expected format.
        
        Args:
            query: User query
            
        Returns:
            Dict with type and format information
        """
        query_lower = query.lower().strip()
        
        # Detect query type
        detected_type = QueryType.UNKNOWN
        for query_type, patterns in self.query_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    detected_type = query_type
                    break
            if detected_type != QueryType.UNKNOWN:
                break
        
        # Infer expected response format based on query type
        if detected_type == QueryType.COUNT:
            response_format = ResponseFormat.SINGLE_VALUE
        elif detected_type == QueryType.LIST:
            response_format = ResponseFormat.LIST
        elif detected_type == QueryType.AGGREGATE:
            response_format = ResponseFormat.SINGLE_VALUE
        elif detected_type == QueryType.COMPARISON:
            response_format = ResponseFormat.TABLE
        elif detected_type == QueryType.ANALYTICAL:
            response_format = ResponseFormat.DETAILED
        else:
            response_format = ResponseFormat.SUMMARY
        
        return {
            'query_type': detected_type.value,
            'response_format': response_format.value,
            'confidence': 0.85 if detected_type != QueryType.UNKNOWN else 0.5
        }
