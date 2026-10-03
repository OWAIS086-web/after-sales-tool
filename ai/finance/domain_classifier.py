"""
Finance Domain Classifier
Classifies whether a query is in-domain (finance/DMS related) or out-domain.
Uses regex-first approach to avoid token waste on obvious cases.
"""

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# REGEX PATTERNS FOR FAST CLASSIFICATION (0 tokens, instant)
# =============================================================================

# Small talk patterns - greetings, thanks, chitchat
SMALL_TALK_PATTERNS = [
    # Greetings (English)
    r'^(hi|hello|hey|hiya|howdy|greetings|hola)[\s\.\!\?]*$',
    r'^(hi|hello|hey)\s+(there|everyone|guys|all)[\s\.\!\?]*$',
    r'^good\s*(morning|afternoon|evening|night|day)[\s\.\!\?]*$',
    r'^(yo|sup|whats up|what\'s up)[\s\.\!\?]*$',
    
    # Greetings (Urdu/Arabic)
    r'^(salam|assalam|salaam|asalaam|asalam|as?salamu?\s*(o\s*)?alaikum|aoa|slm)[\s\.\!\?]*$',
    r'^(walaikum|w[a]?alaikum)[\s\.\!\?]*$',
    r'^(ji|jee|g|haan|han)[\s\.\!\?]*$',
    r'^(adaab|aadab)[\s\.\!\?]*$',
    
    # Thanks
    r'^(thanks?|thank\s*you|thx|ty|tysm|thnx|thanx)[\s\.\!\?]*$',
    r'^(thanks?|thank\s*you)\s*(so|very)?\s*(much|a lot)?[\s\.\!\?]*$',
    r'^(shukriya|shukria|meharbani|bohot\s*shukriya)[\s\.\!\?]*$',
    
    # How are you
    r'^how\s*(are|r)\s*(you|u|ya)[\s\.\!\?]*$',
    r'^how\'?s\s*it\s*going[\s\.\!\?]*$',
    r'^(kya|kia|kese|kaise|kaisa)\s*(ho|hai|haal|chal)[\s\.\!\?]*$',
    
    # Goodbye
    r'^(bye|goodbye|good\s*bye|see\s*(you|ya|u)|farewell|later|cya|bbye)[\s\.\!\?]*$',
    r'^(allah\s*hafiz|khuda\s*hafiz|allahhafiz|khudahafiz|take\s*care)[\s\.\!\?]*$',
    
    # Polite fillers
    r'^(ok|okay|k|oky|alright|sure|fine|cool|great|nice|good|perfect)[\s\.\!\?]*$',
    r'^(hmm+|umm+|ah+|oh+|acha+|achha+|haan)[\s\.\!\?]*$',
    r'^(no\s*problem|np|nw|no\s*worries)[\s\.\!\?]*$',
    r'^(you\'?re\s*welcome|welcome|yw)[\s\.\!\?]*$',
]

# Out-of-domain patterns - clearly unrelated topics
OUT_OF_DOMAIN_PATTERNS = [
    # Weather
    r'\b(weather|temperature|forecast|rain|sunny|cloudy|storm|snow)\b',
    
    # Food & recipes (more comprehensive)
    r'\b(recipe|cooking|cook|bake|baking|dish|ingredient|meal|breakfast|lunch|dinner)\b',
    r'\bhow\s+to\s+(cook|bake|make|prepare)\b',
    
    # Entertainment
    r'\b(movie|film|actor|actress|celebrity|song|music|singer|album|concert)\b',
    r'\b(joke|funny|laugh|comedy|meme)\b',
    r'\b(game|gaming|play|video game|xbox|playstation|ps5)\b',
    
    # Sports
    r'\b(cricket|football|soccer|hockey|tennis|match|tournament|player|team score)\b',
    
    # Science/Math (when not finance-related)
    r'\b(theorem|equation|formula|physics|chemistry|biology|atom|molecule)\b',
    r'\b(calculate|solve|equation)\s+(?!.*\b(emi|loan|payment|finance|interest)\b)',
    
    # Politics/Geography
    r'\b(president|prime minister|election|vote|party|politics|minister|government policy)\b',
    r'\b(country|capital|continent|ocean|mountain|river)\b\s+(?!.*\b(dealership|showroom|branch)\b)',
    
    # General knowledge (unrelated to automotive)
    r'\b(history of|invention of|who invented|when was)\b\s+(?!.*\b(car|vehicle|haval|dealership)\b)',
]

# Finance/automotive keywords for positive matching
FINANCE_AUTOMOTIVE_KEYWORDS = [
    # Automobile finance terms (CEO-focused)
    r'\b(revenue|profit|profitability|margin|operating margin)\b',
    r'\b(sales|sale|selling|sold|transaction|transactions)\b',
    r'\b(expense|expenses|cost|costs|spending|budget)\b',
    r'\b(quarter|quarterly|q1|q2|q3|q4|fiscal year|annual)\b',
    
    # Vehicle terms
    r'\b(vehicle|car|cars|auto|automobile|suv|sedan|inventory|stock)\b',
    r'\b(haval|h6|jolion|gwm|model|variant|trim)\b',
    r'\b(vin|chassis|color|colour|manufacturing|import)\b',
    
    # Dealer network terms
    r'\b(dealer|dealers|dealership|showroom|branch|network)\b',
    r'\b(target|performance|achievement|commission|turnover)\b',
    r'\b(region|regional|sindh|punjab|kpk|ict|karachi|lahore)\b',
    
    # Database/query patterns
    r'\b(how\s*many|show\s*me|list|count|total|average|sum|find)\b',
    r'\b(get|fetch|search|filter|by|from|where|select)\b',
]


class FinanceDomainClassifier:
    """
    Classifies queries as in-domain (finance/DMS) or out-domain.
    Uses regex-first optimization to avoid LLM tokens on obvious cases.
    
    Strategy:
    1. Check for small talk/chitchat (regex) -> SMALL_TALK
    2. Check for explicit out-of-domain topics (regex) -> OUT_OF_DOMAIN
    3. Check for finance/automotive keywords (regex) -> IN_DOMAIN
    4. Ambiguous cases -> LLM fallback
    
    Token Savings: ~110 tokens per regex hit (~70-80% of queries)
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize the domain classifier.
        
        Args:
            llm_client: Optional LLM client for complex classification
        """
        self.llm_client = llm_client
        self.stats = {
            'total_queries': 0,
            'regex_hits': 0,
            'llm_fallbacks': 0
        }
        
    def classify(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Classify if query is in-domain or out-domain using regex-first approach.
        
        Args:
            query: User query
            context: Optional context information
            
        Returns:
            Dict with classification results including:
            - is_in_domain: bool
            - confidence: float
            - reason: str
            - domain: str ('finance_dms', 'out_of_domain', 'small_talk')
            - method: str ('regex' or 'llm')
        """
        self.stats['total_queries'] += 1
        query_lower = query.lower().strip()
        
        # =====================================================================
        # PHASE 1: REGEX-FIRST CLASSIFICATION (0 tokens, instant)
        # =====================================================================
        
        # STEP 1: Check for small talk (highest priority)
        if self._is_small_talk(query_lower):
            self.stats['regex_hits'] += 1
            result = {
                'is_in_domain': False,
                'confidence': 0.95,
                'reason': 'Greeting/chitchat detected via regex',
                'domain': 'small_talk',
                'method': 'regex',
                'in_domain_score': 0,
                'out_domain_score': 0,
                'has_db_pattern': False
            }
            logger.info(f"[REGEX HIT] Domain classification: {result}")
            return result
        
        # STEP 2: Check for explicit out-of-domain topics
        if self._is_out_of_domain(query_lower):
            self.stats['regex_hits'] += 1
            result = {
                'is_in_domain': False,
                'confidence': 0.90,
                'reason': 'Out-of-domain topic detected via regex (weather/entertainment/etc)',
                'domain': 'out_of_domain',
                'method': 'regex',
                'in_domain_score': 0,
                'out_domain_score': 1,
                'has_db_pattern': False
            }
            logger.info(f"[REGEX HIT] Domain classification: {result}")
            return result
        
        # STEP 3: Check for finance/automotive keywords
        if self._is_finance_automotive(query_lower):
            self.stats['regex_hits'] += 1
            result = {
                'is_in_domain': True,
                'confidence': 0.85,
                'reason': 'Finance/automotive keywords detected via regex',
                'domain': 'finance_dms',
                'method': 'regex',
                'in_domain_score': 1,
                'out_domain_score': 0,
                'has_db_pattern': self._has_db_pattern(query_lower)
            }
            logger.info(f"[REGEX HIT] Domain classification: {result}")
            return result
        
        # =====================================================================
        # PHASE 2: AMBIGUOUS - LLM FALLBACK
        # =====================================================================
        
        logger.info("[REGEX MISS] Ambiguous query, falling back to LLM or keyword scoring")
        self.stats['llm_fallbacks'] += 1
        
        # If LLM available, use it for complex cases
        if self.llm_client:
            return self._llm_classify(query, context)
        
        # Otherwise, use simple keyword scoring
        return self._keyword_classify(query_lower)
    
    def _is_small_talk(self, query_lower: str) -> bool:
        """Check if query matches small talk patterns."""
        for pattern in SMALL_TALK_PATTERNS:
            if re.match(pattern, query_lower, re.IGNORECASE):
                return True
        return False
    
    def _is_out_of_domain(self, query_lower: str) -> bool:
        """Check if query matches out-of-domain patterns."""
        # Only return True if no finance/automotive context present
        has_finance_context = self._is_finance_automotive(query_lower)
        if has_finance_context:
            return False
        
        for pattern in OUT_OF_DOMAIN_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return True
        return False
    
    def _is_finance_automotive(self, query_lower: str) -> bool:
        """Check if query contains finance or automotive keywords."""
        for pattern in FINANCE_AUTOMOTIVE_KEYWORDS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return True
        return False
    
    def _has_db_pattern(self, query_lower: str) -> bool:
        """Check if query has database query patterns."""
        db_patterns = [
            r'how\s*many',
            r'show\s*(me\s*)?(all\s*)?',
            r'list\s*(all\s*)?(the\s*)?',
            r'count\s*(of\s*)?(the\s*)?',
            r'total\s*(number\s*of\s*)?',
            r'find\s*(all\s*)?',
            r'get\s*(all\s*)?(the\s*)?',
            r'fetch',
            r'what\s*is\s*the\s*(average|total|count)',
        ]
        return any(re.search(pattern, query_lower) for pattern in db_patterns)
    
    def _keyword_classify(self, query_lower: str) -> Dict[str, Any]:
        """Fallback keyword-based classification when LLM not available."""
        # Legacy keyword lists for fallback
        in_domain_keywords = [
            'finance', 'loan', 'payment', 'installment', 'down payment',
            'interest', 'rate', 'credit', 'financing', 'lease', 'balloon',
            'tenure', 'emi', 'monthly payment', 'insurance', 'markup',
            'customer', 'dealer', 'dealership', 'vehicle', 'car', 'sale',
            'inventory', 'stock', 'booking', 'delivery', 'test drive',
            'show', 'list', 'count', 'total', 'average', 'sum', 'find'
        ]
        
        out_domain_keywords = [
            'weather', 'recipe', 'joke', 'story', 'poem', 'game',
            'movie', 'song', 'celebrity', 'sports', 'politics'
        ]
        
        in_domain_score = sum(1 for kw in in_domain_keywords if kw in query_lower)
        out_domain_score = sum(1 for kw in out_domain_keywords if kw in query_lower)
        has_db_pattern = self._has_db_pattern(query_lower)
        
        if out_domain_score > in_domain_score and out_domain_score > 0:
            is_in_domain = False
            confidence = min(0.75, 0.5 + (out_domain_score * 0.1))
            reason = "Query contains out-domain keywords"
        elif in_domain_score > 0 or has_db_pattern:
            is_in_domain = True
            confidence = min(0.80, 0.6 + (in_domain_score * 0.1))
            reason = "Query contains finance/DMS keywords or database patterns"
        else:
            is_in_domain = True
            confidence = 0.5
            reason = "Ambiguous query, defaulting to in-domain"
        
        return {
            'is_in_domain': is_in_domain,
            'confidence': confidence,
            'reason': reason,
            'domain': 'finance_dms' if is_in_domain else 'out_of_domain',
            'method': 'keyword_fallback',
            'in_domain_score': in_domain_score,
            'out_domain_score': out_domain_score,
            'has_db_pattern': has_db_pattern
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get classification statistics."""
        if self.stats['total_queries'] > 0:
            regex_hit_rate = (self.stats['regex_hits'] / self.stats['total_queries']) * 100
        else:
            regex_hit_rate = 0.0
        
        return {
            **self.stats,
            'regex_hit_rate': f"{regex_hit_rate:.1f}%",
            'estimated_tokens_saved': self.stats['regex_hits'] * 110  # ~110 tokens per regex hit
        }
    
    def _llm_classify(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Use LLM for complex domain classification.
        
        Args:
            query: User query
            context: Optional context
            
        Returns:
            Classification result
        """
        messages = [
            {"role": "system", "content": "You are a strict domain classifier for automobile company finance database queries. Respond with only 'IN_DOMAIN' or 'OUT_DOMAIN'. Reject any query not related to automobile/finance data."},
            {"role": "user", "content": f"""Classify if the following query is related to the HAVAL AUTOMOBILE FINANCE DATABASE (vehicle sales, dealer performance, inventory, revenue/expenses).

Query: "{query}"

Respond with:
- "IN_DOMAIN" - ONLY if the query asks about: vehicle sales, dealer performance, inventory management, revenue, expenses, profitability, quarters, regions, or database queries about Haval automobile operations.
- "OUT_DOMAIN" - If the query is about: weather, recipes, entertainment, sports, politics, general knowledge, greetings, chitchat, customer loans, bank accounts, or ANY topic unrelated to the automobile finance database.

IMPORTANT: If the question is NOT about automobile finance database data, respond 'OUT_DOMAIN' - do NOT try to answer it.

Classification:"""}
        ]

        try:
            response = self.llm_client.generate(
                messages=messages,
                max_tokens=50,
                temperature=0.1
            )
            
            # Extract text from LLMResponse object
            if hasattr(response, 'content'):
                response_text = response.content.strip().upper()
            elif hasattr(response, 'text'):
                response_text = response.text.strip().upper()
            else:
                response_text = str(response).strip().upper()
            
            is_in_domain = "IN_DOMAIN" in response_text or "IN-DOMAIN" in response_text
            
            return {
                'is_in_domain': is_in_domain,
                'confidence': 0.85,
                'reason': f"LLM classification: {response_text}",
                'domain': 'finance_dms' if is_in_domain else 'out_of_domain',
                'llm_response': response_text
            }
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return {
                'is_in_domain': True,
                'confidence': 0.5,
                'reason': f"LLM classification failed, defaulting to in-domain",
                'domain': 'finance_dms',
                'error': str(e)
            }
    
    def should_process(self, query: str, threshold: float = 0.6) -> bool:
        """
        Quick check if query should be processed by finance system.
        
        Args:
            query: User query
            threshold: Confidence threshold
            
        Returns:
            True if should process, False otherwise
        """
        result = self.classify(query)
        return result['is_in_domain'] and result['confidence'] >= threshold
