"""
Finance Query Reformulator
Reformulates user queries for better SQL generation and understanding.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FinanceQueryReformulator:
    """
    Reformulates queries to be more suitable for SQL generation.
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
            'emi': 'monthly installment',
            'dp': 'down payment',
            'apr': 'annual percentage rate',
            'ltv': 'loan to value',
            'csi': 'customer satisfaction index',
            'pdi': 'pre delivery inspection',
            'dms': 'dealer management system',
            'crm': 'customer relationship management',
            'vip': 'very important person',
            'suv': 'sport utility vehicle',
            # Common shortcuts
            'cust': 'customer',
            'acct': 'account',
            'txn': 'transaction',
            'amt': 'amount',
            'qty': 'quantity',
            'no': 'number',
        }
        
        # Typo corrections - common misspellings
        self.typo_corrections = {
            'customres': 'customers',
            'custmers': 'customers',
            'outstandng': 'outstanding',
            'oustanding': 'outstanding',
            'paymnts': 'payments',
            'paymnt': 'payment',
            'transction': 'transaction',
            'transacton': 'transaction',
            'ammount': 'amount',
            'amnt': 'amount',
            'greter': 'greater',
            'grater': 'greater',
            'vehical': 'vehicle',
            'vehcle': 'vehicle',
        }
        
        # Query patterns that need reformulation
        self.reformulation_patterns = [
            # Fix common typos in phrases
            (r'\bg\s+mor\b', 'greater'),
            (r'\bhav\s+', 'have '),
            (r'\bwher\s+', 'where '),
            
            # Vague references
            (r'\bit\b', 'the vehicle'),
            (r'\bthey\b', 'the customers'),
            (r'\bthem\b', 'the records'),
            
            # Informal language
            (r'\bgonna\b', 'going to'),
            (r'\bwanna\b', 'want to'),
            (r'\bgimme\b', 'give me'),
            (r'\bshowing me\b', 'show'),
            
            # Common mistakes
            (r'\bhow much customers\b', 'how many customers'),
            (r'\bhow much vehicles\b', 'how many vehicles'),
            (r'\bname of customers?\b', 'customer names'),
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
        reformulated = query.lower().strip()
        
        changes = []
        
        # Step 1: Fix common typos first
        for typo, correction in self.typo_corrections.items():
            pattern = r'\b' + typo + r'\b'
            if re.search(pattern, reformulated, re.IGNORECASE):
                reformulated = re.sub(pattern, correction, reformulated, flags=re.IGNORECASE)
                changes.append(f"Fixed typo '{typo}' to '{correction}'")
        
        # Step 2: Expand abbreviations
        for abbr, expansion in self.abbreviations.items():
            pattern = r'\b' + abbr + r'\b'
            if re.search(pattern, reformulated, re.IGNORECASE):
                reformulated = re.sub(pattern, expansion, reformulated, flags=re.IGNORECASE)
                changes.append(f"Expanded '{abbr}' to '{expansion}'")
        
        # Step 3: Apply pattern-based reformulations
        for pattern, replacement in self.reformulation_patterns:
            if re.search(pattern, reformulated, re.IGNORECASE):
                reformulated = re.sub(pattern, replacement, reformulated, flags=re.IGNORECASE)
                changes.append(f"Replaced pattern '{pattern}' with '{replacement}'")
        
        # Step 4: Handle context references
        if context and 'previous_query' in context:
            reformulated = self._handle_context_references(reformulated, context)
            if reformulated != query.lower():
                changes.append("Added context from previous query")
        
        # Step 5: Normalize spacing and punctuation
        reformulated = re.sub(r'\s+', ' ', reformulated).strip()
        reformulated = re.sub(r'\s+([?.!,])', r'\1', reformulated)
        
        # Step 6: Use LLM for complex reformulation if available (optional)
        if self.llm_client and self._needs_llm_reformulation(reformulated):
            llm_result = self._llm_reformulate(reformulated, context)
            if llm_result['success']:
                reformulated = llm_result['reformulated']
                changes.extend(llm_result['changes'])
        
        # Capitalize first letter
        reformulated = reformulated[0].upper() + reformulated[1:] if reformulated else reformulated
        
        result = {
            'original_query': original_query,
            'reformulated_query': reformulated,
            'changes': changes,
            'changed': reformulated.lower() != original_query.lower(),
            'confidence': self._calculate_confidence(changes)
        }
        
        if result['changed']:
            logger.info(f"Query reformulated: '{original_query}' -> '{reformulated}'")
        
        return result
    
    def _handle_context_references(self, query: str, context: Dict[str, Any]) -> str:
        """
        Handle references to previous queries or context.
        
        Args:
            query: Current query
            context: Context information
            
        Returns:
            Reformulated query with context
        """
        # If query is very short and seems to reference previous context
        context_keywords = ['also', 'too', 'same', 'those', 'these', 'that', 'what about']
        
        if any(keyword in query for keyword in context_keywords):
            previous = context.get('previous_query', '')
            if previous:
                # Extract main entity from previous query
                # This is a simple approach; can be enhanced
                return f"{query} (related to: {previous})"
        
        return query
    
    def _needs_llm_reformulation(self, query: str) -> bool:
        """
        Check if query needs LLM-based reformulation.
        
        Args:
            query: Query to check
            
        Returns:
            True if LLM reformulation recommended
        """
        # Complex queries that might benefit from LLM
        indicators = [
            len(query.split()) > 15,  # Long query
            '?' in query and len([w for w in query.split() if len(w) > 5]) > 5,  # Complex question
            ' and ' in query and ' or ' in query,  # Multiple conditions
            query.count(',') > 2,  # Multiple clauses
        ]
        
        return any(indicators)
    
    def _llm_reformulate(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Use LLM to reformulate complex queries.
        
        Args:
            query: Query to reformulate
            context: Optional context
            
        Returns:
            Reformulation result
        """
        prompt = f"""
Reformulate the following query to be more precise and suitable for database querying.
Make it clear, specific, and remove any ambiguity.

Original Query: "{query}"

Reformulated Query (make it clear and specific):"""

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                max_tokens=150,
                temperature=0.3
            )
            
            reformulated = response.strip()
            
            return {
                'success': True,
                'reformulated': reformulated,
                'changes': ['LLM-based reformulation applied']
            }
        except Exception as e:
            logger.error(f"LLM reformulation failed: {e}")
            return {
                'success': False,
                'reformulated': query,
                'changes': [],
                'error': str(e)
            }
    
    def _calculate_confidence(self, changes: List[str]) -> float:
        """
        Calculate confidence score for reformulation.
        
        Args:
            changes: List of changes made
            
        Returns:
            Confidence score (0-1)
        """
        if not changes:
            return 1.0  # No changes needed, high confidence
        
        # More changes might indicate uncertainty
        base_confidence = 0.8
        penalty_per_change = 0.05
        
        confidence = base_confidence - (len(changes) * penalty_per_change)
        return max(0.5, min(1.0, confidence))
    
    def batch_reformulate(self, queries: List[str], context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Reformulate multiple queries.
        
        Args:
            queries: List of queries to reformulate
            context: Optional shared context
            
        Returns:
            List of reformulation results
        """
        return [self.reformulate(query, context) for query in queries]
