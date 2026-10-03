"""
Finance Format Detector
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


class FinanceFormatDetector:
    """
    Detects query type and expected response format.
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
                r'total (amount|value|price|revenue)',
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
                r'which (customer|vehicle|dealer)'
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
        
        # Response format indicators
        self.format_indicators = {
            ResponseFormat.SINGLE_VALUE: [
                'how many', 'count', 'total number', 'what is the average',
                'sum of', 'maximum', 'minimum'
            ],
            ResponseFormat.TABLE: [
                'show all', 'list all', 'display', 'give me details',
                'breakdown', 'for each'
            ],
            ResponseFormat.LIST: [
                'names of', 'list of', 'which', 'what are the'
            ],
            ResponseFormat.CHART: [
                'trend', 'over time', 'monthly', 'yearly', 'compare',
                'distribution', 'by month', 'by year'
            ],
            ResponseFormat.SUMMARY: [
                'summarize', 'summary of', 'overview', 'brief'
            ]
        }
    
    def detect(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Detect query type and expected response format.
        
        Args:
            query: User query
            context: Optional context information
            
        Returns:
            Detection results with query type and format
        """
        query_lower = query.lower()
        
        # Detect query type
        query_type = self._detect_query_type(query_lower)
        
        # Detect response format
        response_format = self._detect_response_format(query_lower, query_type)
        
        # Detect aggregation needs
        needs_aggregation = self._needs_aggregation(query_lower)
        
        # Detect sorting/ordering
        sort_info = self._detect_sorting(query_lower)
        
        # Detect filtering
        filter_info = self._detect_filters(query_lower)
        
        # Detect time-based queries
        time_info = self._detect_time_dimension(query_lower)
        
        result = {
            'query_type': query_type.value,
            'response_format': response_format.value,
            'needs_aggregation': needs_aggregation,
            'sort_info': sort_info,
            'filter_info': filter_info,
            'time_info': time_info,
            'complexity': self._calculate_complexity(query_lower),
            'confidence': 0.85
        }
        
        logger.info(f"Format detection: {result}")
        return result
    
    def _detect_query_type(self, query: str) -> QueryType:
        """
        Detect the type of query.
        
        Args:
            query: Query text (lowercased)
            
        Returns:
            QueryType enum
        """
        for query_type, patterns in self.query_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query):
                    return query_type
        
        return QueryType.UNKNOWN
    
    def _detect_response_format(self, query: str, query_type: QueryType) -> ResponseFormat:
        """
        Detect expected response format.
        
        Args:
            query: Query text (lowercased)
            query_type: Detected query type
            
        Returns:
            ResponseFormat enum
        """
        # Score each format based on indicators
        format_scores = {fmt: 0 for fmt in ResponseFormat}
        
        for response_format, indicators in self.format_indicators.items():
            for indicator in indicators:
                if indicator in query:
                    format_scores[response_format] += 1
        
        # Apply query type heuristics
        if query_type == QueryType.COUNT:
            format_scores[ResponseFormat.SINGLE_VALUE] += 2
        elif query_type == QueryType.LIST:
            format_scores[ResponseFormat.TABLE] += 2
        elif query_type == QueryType.AGGREGATE:
            format_scores[ResponseFormat.SINGLE_VALUE] += 1
        elif query_type == QueryType.ANALYTICAL:
            format_scores[ResponseFormat.CHART] += 1
        
        # Get format with highest score
        max_format = max(format_scores.items(), key=lambda x: x[1])
        
        if max_format[1] > 0:
            return max_format[0]
        else:
            return ResponseFormat.DETAILED
    
    def _needs_aggregation(self, query: str) -> bool:
        """
        Check if query needs aggregation.
        
        Args:
            query: Query text (lowercased)
            
        Returns:
            True if aggregation needed
        """
        aggregation_keywords = [
            'total', 'sum', 'average', 'mean', 'count', 'maximum',
            'minimum', 'highest', 'lowest', 'most', 'least'
        ]
        
        return any(keyword in query for keyword in aggregation_keywords)
    
    def _detect_sorting(self, query: str) -> Dict[str, Any]:
        """
        Detect sorting requirements.
        
        Args:
            query: Query text (lowercased)
            
        Returns:
            Sorting information
        """
        sort_keywords = {
            'ascending': ['ascending', 'asc', 'lowest first', 'smallest first', 'oldest first'],
            'descending': ['descending', 'desc', 'highest first', 'largest first', 
                          'most recent', 'latest', 'newest', 'top']
        }
        
        for order, keywords in sort_keywords.items():
            if any(keyword in query for keyword in keywords):
                return {
                    'needs_sorting': True,
                    'order': order,
                    'detected': True
                }
        
        return {
            'needs_sorting': False,
            'order': None,
            'detected': False
        }
    
    def _detect_filters(self, query: str) -> Dict[str, Any]:
        """
        Detect filtering requirements.
        
        Args:
            query: Query text (lowercased)
            
        Returns:
            Filter information
        """
        filter_patterns = {
            'status': r'(active|inactive|pending|completed|cancelled)',
            'comparison': r'(greater than|less than|more than|above|below|between)',
            'equality': r'(equals?|is|are|with)',
            'contains': r'(contains?|includes?|having)'
        }
        
        detected_filters = []
        for filter_type, pattern in filter_patterns.items():
            if re.search(pattern, query):
                detected_filters.append(filter_type)
        
        return {
            'has_filters': len(detected_filters) > 0,
            'filter_types': detected_filters,
            'count': len(detected_filters)
        }
    
    def _detect_time_dimension(self, query: str) -> Dict[str, Any]:
        """
        Detect time-based query components.
        
        Args:
            query: Query text (lowercased)
            
        Returns:
            Time dimension information
        """
        time_patterns = {
            'specific_date': r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}',
            'month': r'(january|february|march|april|may|june|july|august|september|october|november|december)',
            'year': r'\b(19|20)\d{2}\b',
            'relative': r'(today|yesterday|last (week|month|year)|this (week|month|year))',
            'range': r'(between|from .* to|since|until|before|after)'
        }
        
        detected_time = []
        for time_type, pattern in time_patterns.items():
            if re.search(pattern, query):
                detected_time.append(time_type)
        
        return {
            'has_time_dimension': len(detected_time) > 0,
            'time_types': detected_time,
            'needs_date_parsing': 'specific_date' in detected_time or 'relative' in detected_time
        }
    
    def _calculate_complexity(self, query: str) -> str:
        """
        Calculate query complexity.
        
        Args:
            query: Query text (lowercased)
            
        Returns:
            Complexity level: 'simple', 'moderate', 'complex'
        """
        complexity_score = 0
        
        # Length-based
        word_count = len(query.split())
        if word_count > 20:
            complexity_score += 2
        elif word_count > 10:
            complexity_score += 1
        
        # Multiple conditions
        if ' and ' in query:
            complexity_score += query.count(' and ')
        if ' or ' in query:
            complexity_score += query.count(' or ')
        
        # Nested clauses
        if query.count(',') > 2:
            complexity_score += 1
        
        # Aggregations
        if self._needs_aggregation(query):
            complexity_score += 1
        
        # Determine complexity level
        if complexity_score <= 1:
            return 'simple'
        elif complexity_score <= 3:
            return 'moderate'
        else:
            return 'complex'
    
    def get_sql_hints(self, detection_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get SQL generation hints based on format detection.
        
        Args:
            detection_result: Result from detect() method
            
        Returns:
            SQL generation hints
        """
        hints = {
            'select_type': 'SELECT',
            'needs_group_by': False,
            'needs_order_by': False,
            'needs_limit': False,
            'suggested_limit': None
        }
        
        query_type = detection_result['query_type']
        
        # Set SELECT type
        if query_type == 'count':
            hints['select_type'] = 'SELECT COUNT(*)'
        elif query_type == 'aggregate':
            hints['select_type'] = 'SELECT aggregate_function(column)'
            hints['needs_group_by'] = True
        
        # Check sorting
        if detection_result['sort_info']['needs_sorting']:
            hints['needs_order_by'] = True
            hints['order_direction'] = detection_result['sort_info']['order']
        
        # Check if limit needed
        if detection_result['response_format'] in ['list', 'table'] and query_type == 'list':
            hints['needs_limit'] = True
            hints['suggested_limit'] = 100  # Default limit
        
        return hints
