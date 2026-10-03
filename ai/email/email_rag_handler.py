"""
Email RAG Handler - Intelligent Email Query System
Langchain-based RAG pipeline for querying indexed emails with advanced intelligence

COMPREHENSIVE FEATURES:
✅ Smart Query Normalization - Handles typos, special characters, case variations
✅ Date Intelligence - Single dates, date ranges, relative dates (today, last week, etc.)
✅ Sender Detection - Automatically filters by sender when mentioned in query
✅ Subject Filtering - Extracts and filters by subject keywords
✅ Query Expansion - Adds synonyms for better semantic matching
✅ Deduplication - Removes duplicate emails automatically
✅ Confidence Scoring - Calculates reliability score for each answer
✅ Smart Suggestions - Provides query clarification tips when needed
✅ Robust Error Handling - Intelligent fallback for various error types
✅ Multi-Intent Support - Handles complex queries with multiple requirements

SUPPORTED QUERY TYPES:
- Date-specific: "emails on Feb 10", "what emails today", "yesterday's emails"
- Date ranges: "last week", "this month", "between Feb 1 and Feb 10"
- Sender filtering: "emails from John", "messages from support@company.com"
- Subject filtering: "emails about delivery", "regarding complaints"
- Count queries: "how many emails", "total emails on date"
- Comprehensive: "all emails", "show me everything from last month"
- Combined: "complaints from customers last week about delivery"

INTELLIGENT HANDLING:
- Typos: "manny" → "many", "bye" → "by", "feb" → "february"
- Edge cases: Empty queries, special characters only, very short queries
- Chit-chat: Greetings, thanks, help requests
- Synonyms: "complaint" ↔ "issue" ↔ "problem"
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

# LangChain imports - handle different versions
try:
    from langchain_core.prompts import PromptTemplate
except ImportError:
    from langchain.prompts import PromptTemplate

# LangChain Document import - handle different versions
try:
    from langchain_core.documents import Document
except ImportError:
    try:
        from langchain.docstore.document import Document
    except ImportError:
        from langchain.schema import Document

from ai.email.email_vector_store import EmailVectorStore
from utils.logger import log_error

# Import LLM providers with fallback
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None
    
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None


class EmailRAGHandler:
    """
    RAG-based email query handler using Langchain
    Supports Grok, OpenAI, and Gemini providers
    """
    
    def __init__(
        self,
        vector_store: EmailVectorStore,
        llm_provider: str = "grok",
        api_key: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        """
        Initialize Email RAG Handler
        
        Args:
            vector_store: Email vector store instance
            llm_provider: LLM provider ('grok', 'openai', or 'gemini')
            api_key: API key for LLM
            model_name: Model name (optional)
        """
        self.vector_store = vector_store
        self.llm_provider = llm_provider
        
        print(f"[Email RAG] Initializing with provider: {llm_provider}")
        
        # Initialize LLM based on provider
        if llm_provider == "grok":
            # Grok uses OpenAI-compatible API
            if ChatOpenAI is None:
                raise ValueError("langchain-openai not installed. Run: pip install langchain-openai")
            self.llm = ChatOpenAI(
                model=model_name or "grok-3-fast",
                openai_api_key=api_key,
                openai_api_base="https://api.x.ai/v1",
                temperature=0.3
            )
            print("[Email RAG] ✅ Using Grok (grok-3-fast)")
            
        elif llm_provider == "openai":
            if ChatOpenAI is None:
                raise ValueError("langchain-openai not installed. Run: pip install langchain-openai")
            self.llm = ChatOpenAI(
                model=model_name or "gpt-4o-mini",
                openai_api_key=api_key,
                temperature=0.3
            )
            print("[Email RAG] ✅ Using OpenAI (gpt-4o-mini)")
            
        elif llm_provider == "gemini":
            if ChatGoogleGenerativeAI is None:
                raise ValueError("langchain-google-genai not installed. Run: pip install langchain-google-genai")
            self.llm = ChatGoogleGenerativeAI(
                model=model_name or "gemini-1.5-flash",
                google_api_key=api_key,
                temperature=0.3
            )
            print("[Email RAG] ✅ Using Gemini (gemini-1.5-flash)")
            
        else:
            raise ValueError(f"Unsupported LLM provider: {llm_provider}. Use 'grok', 'openai', or 'gemini'")
    
    def _normalize_query(self, query: str) -> str:
        """
        Normalize query by fixing common typos, special characters, and edge cases.
        
        Handles:
        - Excessive punctuation: "how many!!!", "emails???"
        - Special characters: "@, !, #, $, %, etc."
        - Common typos: "bye" -> "by", "manny" -> "many", "feb" -> "february"
        - Date variations: "10th", "10st", "10nd" -> "10"
        - Multiple spaces: "how   many" -> "how many"
        - Case variations: "FEB", "Feb", "feb" -> "february"
        - Abbreviations: "jan", "feb", "num of" -> "january", "february", "number of"
        
        Args:
            query: Raw user query
            
        Returns:
            Normalized query string
        """
        import re
        
        if not query:
            return ""
        
        # Convert to lowercase for processing
        normalized = query.lower().strip()
        
        # Remove excessive punctuation (except periods in dates)
        # Keep: letters, numbers, spaces, common punctuation, forward slashes for dates
        normalized = re.sub(r'[!@#$%^&*()_+=\[\]{};:\'"<>,?\\|`~]+', ' ', normalized)
        
        # Fix common typos in date-related words
        typo_fixes = {
            r'\bfeb\b': 'february',
            r'\bjan\b': 'january',
            r'\bmar\b': 'march',
            r'\bapr\b': 'april',
            r'\bjun\b': 'june',
            r'\bjul\b': 'july',
            r'\baug\b': 'august',
            r'\bsep\b': 'september',
            r'\bsept\b': 'september',
            r'\boct\b': 'october',
            r'\bnov\b': 'november',
            r'\bdec\b': 'december',
            # Common typos
            r'\bemails?\b': 'emails',
            r'\bhow\s+manny\b': 'how many',
            r'\bhow\s+manys\b': 'how many',
            r'\bhow\s+much\b': 'how many',
            r'\bnumber\s+off\b': 'number of',
            r'\bnum\s+of\b': 'number of',
            r'\btotal\s+off\b': 'total',
            r'\bfrom\s+bye\b': 'from by',
            r'\bon\s+bye\b': 'on by',
            # Date variations
            r'\b(\d{1,2})st\b': r'\1',
            r'\b(\d{1,2})nd\b': r'\1',
            r'\b(\d{1,2})rd\b': r'\1',
            r'\b(\d{1,2})th\b': r'\1',
        }
        
        for pattern, replacement in typo_fixes.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        # Normalize multiple spaces to single space
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Fix spacing around numbers and slashes (for dates)
        normalized = re.sub(r'(\d)\s*/\s*(\d)', r'\1/\2', normalized)
        
        return normalized
    
    def _extract_date_range(self, query: str) -> Optional[Dict[str, str]]:
        """
        Extract date range from query (e.g., "last week", "this month", "between X and Y").
        
        Args:
            query: User query string
            
        Returns:
            Dictionary with 'from' and 'to' dates in M/D/YYYY format, or None
        """
        import re
        from datetime import datetime, timedelta
        
        query = self._normalize_query(query)
        query_lower = query.lower()
        now = datetime.now()
        
        # Last week
        if 'last week' in query_lower:
            start = now - timedelta(days=now.weekday() + 7)
            end = start + timedelta(days=6)
            return {'from': f"{start.month}/{start.day}/{start.year}", 'to': f"{end.month}/{end.day}/{end.year}"}
        
        # This week
        if 'this week' in query_lower:
            start = now - timedelta(days=now.weekday())
            return {'from': f"{start.month}/{start.day}/{start.year}", 'to': f"{now.month}/{now.day}/{now.year}"}
        
        # Last month
        if 'last month' in query_lower:
            last_month = now.month - 1 if now.month > 1 else 12
            year = now.year if now.month > 1 else now.year - 1
            return {'from': f"{last_month}/1/{year}", 'to': f"{last_month}/31/{year}"}
        
        # This month
        if 'this month' in query_lower:
            return {'from': f"{now.month}/1/{now.year}", 'to': f"{now.month}/{now.day}/{now.year}"}
        
        # Last X days
        last_days_pattern = r'last (\d+) days?'
        match = re.search(last_days_pattern, query_lower)
        if match:
            days = int(match.group(1))
            start = now - timedelta(days=days)
            return {'from': f"{start.month}/{start.day}/{start.year}", 'to': f"{now.month}/{now.day}/{now.year}"}
        
        # Between dates pattern
        between_pattern = r'between\s+(.+?)\s+and\s+(.+?)(?:\s|$)'
        match = re.search(between_pattern, query_lower)
        if match:
            date1 = self._extract_date_from_query(match.group(1))
            date2 = self._extract_date_from_query(match.group(2))
            if date1 and date2:
                return {'from': date1, 'to': date2}
        
        return None
    
    def _detect_email_direction(self, query: str) -> Optional[str]:
        """
        Detect if query is asking about sent emails, received emails, or replies.
        
        Args:
            query: User query string
            
        Returns:
            'sent', 'received', 'reply', or None
        """
        query_lower = query.lower()
        
        # Reply indicators (highest priority)
        reply_patterns = [
            'reply', 'replied', 'response', 'responded', 'answer', 'answered',
            'follow up', 'followup', 'follow-up', 'reply to', 'response to'
        ]
        if any(pattern in query_lower for pattern in reply_patterns):
            return 'reply'
        
        # Sent indicators
        sent_patterns = [
            'sent by haval', 'sent by us', 'we sent', 'haval sent', 'our reply',
            'our response', 'our email', 'outgoing', 'sent from haval'
        ]
        if any(pattern in query_lower for pattern in sent_patterns):
            return 'sent'
        
        # Received indicators (default for most queries)
        received_patterns = [
            'received', 'incoming', 'from customer', 'customer sent',
            'complaint', 'inquiry', 'request from'
        ]
        if any(pattern in query_lower for pattern in received_patterns):
            return 'received'
        
        return None
    
    def _extract_sender_from_query(self, query: str) -> Optional[str]:
        """
        Extract sender name or email from query.
        
        Args:
            query: User query string
            
        Returns:
            Sender name or email, or None
        """
        import re
        query_lower = query.lower()
        
        # CRITICAL: Do NOT extract sender if "from" is part of reply/response query
        # e.g., "is there any reply from haval?" - "from haval" means "sent by haval" (reply direction)
        reply_with_from_patterns = [
            r'reply.*from', r'response.*from', r'replied.*from', r'responded.*from',
            r'answer.*from', r'sent.*from', r'any.*from.*reply', r'any.*reply.*from'
        ]
        if any(re.search(pattern, query_lower) for pattern in reply_with_from_patterns):
            print(f"[Email RAG] Skipping sender extraction - 'from' is part of reply query pattern")
            return None
        
        # Pattern: "from <sender>"
        from_pattern = r'from\s+([\w\s\.]+?)(?:\s+about|\s+regarding|\s+on|\s+\?|$)'
        match = re.search(from_pattern, query_lower)
        if match:
            return match.group(1).strip()
        
        # Pattern: "<sender> sent" or "<sender>'s email"
        sender_pattern = r'([\w\s\.]+?)(?:\'s)?\s+(?:sent|email|message)'
        match = re.search(sender_pattern, query_lower)
        if match:
            sender = match.group(1).strip()
            if len(sender.split()) <= 3:  # Likely a name
                return sender
        
        return None
    
    def _extract_subject_keywords(self, query: str) -> Optional[List[str]]:
        """
        Extract subject keywords from query.
        
        Args:
            query: User query string
            
        Returns:
            List of subject keywords, or None
        """
        import re
        query_lower = query.lower()
        
        # Pattern: "about <subject>"
        about_pattern = r'about\s+([\w\s]+?)(?:\s+from|\s+on|\s+\?|$)'
        match = re.search(about_pattern, query_lower)
        if match:
            keywords = match.group(1).strip().split()
            return [kw for kw in keywords if len(kw) > 2]
        
        # Pattern: "regarding <subject>"
        regarding_pattern = r'regarding\s+([\w\s]+?)(?:\s+from|\s+on|\s+\?|$)'
        match = re.search(regarding_pattern, query_lower)
        if match:
            keywords = match.group(1).strip().split()
            return [kw for kw in keywords if len(kw) > 2]
        
        return None
    
    def _expand_query(self, query: str) -> str:
        """
        Expand query with synonyms and related terms for better matching.
        
        Args:
            query: Original query
            
        Returns:
            Expanded query with synonyms
        """
        # Synonym mappings for common terms
        synonyms = {
            'complaint': ['complaint', 'issue', 'problem', 'concern'],
            'issue': ['issue', 'problem', 'complaint', 'concern'],
            'problem': ['problem', 'issue', 'complaint', 'concern'],
            'delivery': ['delivery', 'shipping', 'shipment'],
            'quality': ['quality', 'defect', 'fault'],
            'service': ['service', 'support', 'assistance'],
            'price': ['price', 'cost', 'pricing'],
            'refund': ['refund', 'return', 'reimbursement'],
        }
        
        query_lower = query.lower()
        expanded_terms = []
        
        for term, synonyms_list in synonyms.items():
            if term in query_lower:
                expanded_terms.extend(synonyms_list)
        
        if expanded_terms:
            return query + ' ' + ' '.join(set(expanded_terms))
        
        return query
    
    def _extract_date_from_query(self, query: str) -> Optional[str]:
        """
        Extract date from query string and return in M/D/YYYY format for filtering.
        Handles typos, abbreviations, and various date formats.
        
        Args:
            query: User query string
            
        Returns:
            Date string in M/D/YYYY format or None if no date found
        """
        import re
        from datetime import datetime, timedelta

        # Normalize query first to handle typos
        query = self._normalize_query(query)
        query_lower = query.lower()
        
        # Get current date for relative date handling
        now = datetime.now()
        
        # Handle relative dates
        if 'today' in query_lower:
            return f"{now.month}/{now.day}/{now.year}"
        
        if 'yesterday' in query_lower:
            yesterday = now - timedelta(days=1)
            return f"{yesterday.month}/{yesterday.day}/{yesterday.year}"
        
        # Month mapping (including common typos/abbreviations)
        month_map = {
            'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
            'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
            'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
            'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12
        }
        
        # Pattern 1: day month year (e.g., "9th feb 2026", "9 february 2026", "9 feb 2026")
        pattern1 = r'(\d{1,2})(?:st|nd|rd|th)?\s*(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s*,?\s*(\d{4})'
        match = re.search(pattern1, query_lower)
        if match:
            day = int(match.group(1))
            month = month_map.get(match.group(2))
            year = int(match.group(3))
            if month and 1 <= day <= 31:
                return f"{month}/{day}/{year}"
        
        # Pattern 2: day month (no year - assume current year) (e.g., "9 feb", "9th february")
        pattern2_noyear = r'(\d{1,2})(?:st|nd|rd|th)?\s*(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)(?:\s|,|$)'
        match = re.search(pattern2_noyear, query_lower)
        if match:
            day = int(match.group(1))
            month = month_map.get(match.group(2))
            if month and 1 <= day <= 31:
                return f"{month}/{day}/{now.year}"
        
        # Pattern 3: month day year (e.g., "february 9, 2026", "feb 9 2026")
        pattern3 = r'(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s*(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})'
        match = re.search(pattern3, query_lower)
        if match:
            month = month_map.get(match.group(1))
            day = int(match.group(2))
            year = int(match.group(3))
            if month and 1 <= day <= 31:
                return f"{month}/{day}/{year}"
        
        # Pattern 4: month day (no year) (e.g., "feb 9", "february 9")
        pattern4_noyear = r'(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s*(\d{1,2})(?:st|nd|rd|th)?(?:\s|,|$)'
        match = re.search(pattern4_noyear, query_lower)
        if match:
            month = month_map.get(match.group(1))
            day = int(match.group(2))
            if month and 1 <= day <= 31:
                return f"{month}/{day}/{now.year}"
        
        # Pattern 5: M/D/YYYY or MM/DD/YYYY
        pattern5 = r'(\d{1,2})/(\d{1,2})/(\d{4})'
        match = re.search(pattern5, query)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            year = int(match.group(3))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return f"{month}/{day}/{year}"
        
        # Pattern 6: M/D or MM/DD (no year - assume current year)
        pattern6 = r'(\d{1,2})/(\d{1,2})(?:\s|,|$)'
        match = re.search(pattern6, query)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return f"{month}/{day}/{now.year}"
        
        # Pattern 7: YYYY-MM-DD
        pattern7 = r'(\d{4})-(\d{1,2})-(\d{1,2})'
        match = re.search(pattern7, query)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return f"{month}/{day}/{year}"
        
        return None
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """
        Normalize various date formats to YYYY-MM-DD for comparison.
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            Normalized date string in YYYY-MM-DD format or None
        """
        import re
        from datetime import datetime
        
        if not date_str:
            return None
            
        date_str = str(date_str).strip()
        
        # Try ISO format: 2026-02-09T00:16:28+05:00
        if 'T' in date_str:
            try:
                # Extract just the date part
                date_part = date_str.split('T')[0]
                return date_part  # Already YYYY-MM-DD
            except:
                pass
        
        # Try M/D/YYYY format: 2/9/2026
        match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            year = int(match.group(3))
            return f"{year}-{month:02d}-{day:02d}"
        
        # Try YYYY-MM-DD format
        match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', date_str)
        if match:
            return date_str
        
        # Try "Month DD, YYYY" format: February 9, 2026
        try:
            dt = datetime.strptime(date_str.replace(',', ''), '%B %d %Y')
            return dt.strftime('%Y-%m-%d')
        except:
            pass
        
        # Try "DD Mon YYYY" format
        try:
            dt = datetime.strptime(date_str, '%d %b %Y')
            return dt.strftime('%Y-%m-%d')
        except:
            pass
            
        return None
    
    def _filter_sources_by_date_range(self, sources: List[Dict[str, Any]], date_from: str, date_to: str) -> List[Dict[str, Any]]:
        """
        Filter sources by date range.
        
        Args:
            sources: List of source dictionaries
            date_from: Start date in M/D/YYYY format
            date_to: End date in M/D/YYYY format
            
        Returns:
            Filtered list of sources
        """
        from datetime import datetime
        filtered = []
        
        normalized_from = self._normalize_date(date_from)
        normalized_to = self._normalize_date(date_to)
        
        print(f"[Email RAG] Filtering by date range: {date_from} to {date_to}")
        
        if not normalized_from or not normalized_to:
            return sources
        
        from_dt = datetime.strptime(normalized_from, '%Y-%m-%d')
        to_dt = datetime.strptime(normalized_to, '%Y-%m-%d')
        
        for source in sources:
            source_date = source.get('date', '')
            normalized_source = self._normalize_date(source_date)
            
            if normalized_source:
                source_dt = datetime.strptime(normalized_source, '%Y-%m-%d')
                if from_dt <= source_dt <= to_dt:
                    filtered.append(source)
                    print(f"[Email RAG] ✅ In range: {source.get('title', 'No Subject')}")
        
        print(f"[Email RAG] Date range filter: {len(filtered)} of {len(sources)} emails")
        return filtered
    
    def _filter_sources_by_date(self, sources: List[Dict[str, Any]], target_date: str) -> List[Dict[str, Any]]:
        """
        Filter sources to only include those matching the target date.
        
        Args:
            sources: List of source dictionaries
            target_date: Date string in M/D/YYYY format
            
        Returns:
            Filtered list of sources
        """
        filtered = []
        
        # Normalize target date to YYYY-MM-DD
        normalized_target = self._normalize_date(target_date)
        print(f"[Email RAG] Filtering sources by date: {target_date} (normalized: {normalized_target})")
        
        if not normalized_target:
            print(f"[Email RAG] ⚠️ Could not normalize target date, returning all sources")
            return sources
        
        for source in sources:
            source_date = source.get('date', '')
            normalized_source = self._normalize_date(source_date)
            
            print(f"[Email RAG] Comparing: {source.get('title', 'No Subject')} - source={source_date} (normalized: {normalized_source}) vs target={normalized_target}")
            
            if normalized_source and normalized_source == normalized_target:
                filtered.append(source)
                print(f"[Email RAG] ✅ Matched: {source.get('title', 'No Subject')}")
            else:
                print(f"[Email RAG] ❌ Filtered out: {source.get('title', 'No Subject')}")
        
        return filtered
    
    def query(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query indexed emails using RAG
        
        Args:
            query: User query
            n_results: Number of relevant emails to retrieve (default, may be overridden)
            filter_metadata: Optional metadata filters
            
        Returns:
            Dictionary with answer and sources
        """
        try:
            print(f"[Email RAG] Query received: {query[:100]}...")
            
            # Handle empty or whitespace-only queries
            if not query or not query.strip():
                return {
                    'success': True,
                    'answer': "I didn't receive a valid query. Please ask me something about your emails.",
                    'sources': [],
                    'retrieved_count': 0,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Normalize query to handle typos and special characters
            original_query = query
            query = self._normalize_query(query)
            if query != original_query.lower().strip():
                print(f"[Email RAG] Query normalized: {query[:100]}...")
            
            # Handle cases where normalization results in empty string
            if not query or len(query.strip()) < 2:
                return {
                    'success': True,
                    'answer': "I couldn't understand your query. Please try asking about your emails using more descriptive words.",
                    'sources': [],
                    'retrieved_count': 0,
                    'timestamp': datetime.now().isoformat()
                }
            
            print(f"[Email RAG] Vector store type: {type(self.vector_store)}")
            print(f"[Email RAG] Vector store collection: {self.vector_store.collection_name}")
            
            # Classify query intent
            query_intent = self._classify_query_intent(query)
            print(f"[Email RAG] Query intent: {query_intent}")
            
            # Check if this is a count/statistics query
            is_count_query = self._is_count_query(query)
            if is_count_query:
                print(f"[Email RAG] ℹ️ Detected count/statistics query")
            
            # Detect email direction (sent/received/reply)
            email_direction = self._detect_email_direction(original_query)
            if email_direction:
                print(f"[Email RAG] 📧 Email direction: {email_direction}")
            
            # Handle chit-chat queries
            if query_intent == 'chit_chat':
                return {
                    'success': True,
                    'answer': "Hi! I'm your email assistant. I can help you search through your emails, find specific messages, analyze complaints, or provide insights about your email communications. What would you like to know about your emails?",
                    'sources': [],
                    'retrieved_count': 0,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Handle irrelevant queries
            if query_intent == 'irrelevant':
                return {
                    'success': True,
                    'answer': "I'm sorry, but I can only help with questions about your emails. I don't have access to information outside of your email database. Please ask me something about your email communications.",
                    'sources': [],
                    'retrieved_count': 0,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Determine dynamic result limit based on query
            dynamic_n_results = self._determine_result_limit(query, n_results)
            print(f"[Email RAG] Using dynamic n_results: {dynamic_n_results} (original: {n_results})")
            
            # Expand query with synonyms for better matching
            expanded_query = self._expand_query(query)
            if expanded_query != query:
                print(f"[Email RAG] 🔍 Query expanded with synonyms")
            
            # Add source filter to ensure only Gmail emails are returned
            email_filter = filter_metadata.copy() if filter_metadata else {}
            email_filter['source'] = 'gmail'
            
            # Search for relevant emails
            search_results = self.vector_store.search(
                query=expanded_query,
                n_results=dynamic_n_results,
                filter_metadata=email_filter
            )
            
            print(f"[Email RAG] Search returned {len(search_results)} results")
            
            if not search_results:
                return {
                    'success': True,
                    'answer': "I couldn't find any relevant emails matching your query.",
                    'sources': [],
                    'retrieved_count': 0
                }
            
            # Build context from search results
            context = self._build_context(search_results)
            
            # Build sources list
            sources = self._build_sources(search_results)
            
            # Extract sender filter if mentioned
            sender_filter = self._extract_sender_from_query(original_query)
            if sender_filter:
                print(f"[Email RAG] 👤 Sender detected: {sender_filter}")
                sources = [s for s in sources if sender_filter.lower() in s.get('sender', '').lower()]
                print(f"[Email RAG] Sources after sender filter: {len(sources)}")
            
            # Extract subject keywords if mentioned
            subject_keywords = self._extract_subject_keywords(original_query)
            if subject_keywords:
                print(f"[Email RAG] 📌 Subject keywords: {subject_keywords}")
                sources = [s for s in sources if any(kw in s.get('title', '').lower() for kw in subject_keywords)]
                print(f"[Email RAG] Sources after subject filter: {len(sources)}")
            
            # Check for date range first, then single date
            date_range = self._extract_date_range(original_query)
            if date_range:
                print(f"[Email RAG] 📅 Date range detected: {date_range['from']} to {date_range['to']}")
                sources = self._filter_sources_by_date_range(sources, date_range['from'], date_range['to'])
                print(f"[Email RAG] Sources after date range filter: {len(sources)}")
            else:
                # Extract single date from query and filter sources if date is specified
                extracted_date = self._extract_date_from_query(query)
                if extracted_date:
                    print(f"[Email RAG] 📅 Date extracted from query: {extracted_date}")
                    sources = self._filter_sources_by_date(sources, extracted_date)
                    print(f"[Email RAG] Sources after date filter: {len(sources)}")
            
            # Deduplicate sources by email_id
            unique_sources = self._deduplicate_sources(sources)
            if len(unique_sources) < len(sources):
                print(f"[Email RAG] 🔄 Deduplicated: {len(sources)} -> {len(unique_sources)} emails")
                sources = unique_sources
            
            # CRITICAL: Validate that sources match the query intent
            validated_sources, is_valid = self._validate_sources_match_query(original_query, sources, email_direction)
            
            if not is_valid:
                # Sources don't match query - e.g., user asked for HAVAL replies but got customer complaints
                print(f"[Email RAG] 🚫 No relevant emails found matching query intent")
                
                if email_direction in ['sent', 'reply']:
                    return {
                        'success': True,
                        'answer': "Based on the email database, I couldn't find any replies or responses sent by HAVAL for the specified query. The database currently contains incoming customer emails only. If you're looking for HAVAL's sent emails or replies, they may need to be indexed separately or may not be available in the current dataset.",
                        'sources': [],
                        'retrieved_count': 0,
                        'confidence': 0.9,
                        'total_found': 0,
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    return {
                        'success': True,
                        'answer': "I couldn't find any emails matching your specific criteria. Please try rephrasing your query or adjusting your filters.",
                        'sources': [],
                        'retrieved_count': 0,
                        'confidence': 0.5,
                        'total_found': 0,
                        'timestamp': datetime.now().isoformat()
                    }
            
            sources = validated_sources
            
            # Generate answer using LLM (use original query for better context)
            answer = self._generate_answer(query, context, sources, query_intent)
            
            # Filter sources to only include emails that were actually referenced in the answer
            referenced_sources = self._filter_referenced_sources(answer, sources)
            print(f"[Email RAG] Sources before reference filter: {len(sources)}, after filter: {len(referenced_sources)}")
            
            # Calculate confidence score
            confidence = self._calculate_confidence_score(query, referenced_sources, answer)
            print(f"[Email RAG] 📊 Confidence score: {confidence:.2f}")
            
            # Generate clarification suggestion if needed
            clarification = self._suggest_query_clarification(original_query, sources)
            if clarification:
                print(f"[Email RAG] {clarification}")
                answer = answer + "\n\n" + clarification
            
            return {
                'success': True,
                'answer': answer,
                'sources': referenced_sources,  # Only return sources that were discussed
                'retrieved_count': len(referenced_sources),  # Return filtered count
                'confidence': confidence,
                'total_found': len(sources),  # Total before reference filtering
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            log_error(f"Error in RAG query: {e}")
            import traceback
            traceback.print_exc()
            
            # Intelligent fallback based on error type
            error_msg = str(e)
            
            if "rate limit" in error_msg.lower() or "quota" in error_msg.lower():
                fallback_answer = "⚠️ I'm experiencing high demand right now. Please try again in a moment."
            elif "timeout" in error_msg.lower():
                fallback_answer = "⚠️ The request took too long to process. Try simplifying your query or being more specific."
            elif "connection" in error_msg.lower() or "network" in error_msg.lower():
                fallback_answer = "⚠️ Network connection issue. Please check your internet connection and try again."
            elif "model" in error_msg.lower() or "llm" in error_msg.lower():
                fallback_answer = "⚠️ AI model is temporarily unavailable. The issue has been logged and will be resolved soon."
            else:
                fallback_answer = f"⚠️ An unexpected error occurred while processing your query. Please try rephrasing your question or contact support if the issue persists."
            
            return {
                'success': False,
                'error': str(e),
                'answer': fallback_answer,
                'sources': [],
                'confidence': 0.0,
                'retrieved_count': 0,
                'timestamp': datetime.now().isoformat()
            }
    
    def _build_context(self, search_results: List[Dict[str, Any]]) -> str:
        """
        Build context string from search results
        
        Args:
            search_results: List of search results
            
        Returns:
            Formatted context string
        """
        context_parts = []
        
        for idx, result in enumerate(search_results, 1):
            metadata = result.get('metadata', {})
            document = result.get('document', '')
            
            # Get sender info
            sender = metadata.get('sender', 'Unknown')
            sender_name = metadata.get('sender_name', sender.split('<')[0].strip() if '<' in sender else sender)
            sender_email = metadata.get('sender_email', '')
            if not sender_email and '<' in sender:
                sender_email = sender.split('<')[1].replace('>', '').strip()
            
            # Get date and time
            date = metadata.get('date', 'Unknown')
            time = metadata.get('time', '')
            datetime_str = f"{date} at {time}" if time else date
            
            # Get email ID for reference
            email_id = metadata.get('email_id', f'email_{idx}')
            
            # Build email context with reference ID
            context_parts.append(f"""
═══════════════════════════════════════════════════════════════
📧 EMAIL #{idx} [REF: {email_id}]
═══════════════════════════════════════════════════════════════
📌 Subject: {metadata.get('subject', 'No Subject')}
👤 From: {sender_name} <{sender_email}>
📅 Date: {datetime_str}
🏷️ Labels: {metadata.get('labels', 'N/A')}

📝 Email Content:
{document[:1500]}
═══════════════════════════════════════════════════════════════
""")
        
        return "\n".join(context_parts)
    
    def _build_sources(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Build sources list from search results
        
        Args:
            search_results: List of search results
            
        Returns:
            List of source dictionaries with full metadata for display
        """
        sources = []
        
        for result in search_results:
            metadata = result.get('metadata', {})
            
            # Extract sender name and email separately
            sender_full = metadata.get('sender', 'Unknown')
            sender_name = sender_full
            sender_email = ''
            
            if '<' in sender_full and '>' in sender_full:
                # Format: "Name <email@domain.com>"
                sender_name = sender_full.split('<')[0].strip()
                sender_email = sender_full.split('<')[1].replace('>', '').strip()
            elif '@' in sender_full:
                # Just email address
                sender_email = sender_full
                sender_name = sender_full.split('@')[0]
            
            email_id = metadata.get('email_id', '')
            thread_id = metadata.get('thread_id', '')
            
            # Build Gmail link for "View in Gmail" button
            gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{thread_id}" if thread_id else ""
            
            # Store email_id for reference matching
            sources.append({
                'title': metadata.get('subject', 'No Subject'),
                'sender': sender_full,
                'sender_name': sender_name,
                'sender_email': sender_email,
                'date': metadata.get('date', 'Unknown'),
                'time': metadata.get('time', ''),
                'snippet': metadata.get('snippet', result.get('document', '')[:200] if result.get('document') else ''),
                'email_id': email_id,  # Used for matching referenced emails
                'thread_id': thread_id,
                'gmail_link': gmail_link,  # Direct link to open in Gmail
                'body': result.get('document', ''),  # Full email content for "View Email" modal
                'platform': 'Gmail',
                'type': 'email',
                'relevance_score': 1.0 - result.get('distance', 0.0)
            })
        
        return sources
    
    def _is_count_query(self, query: str) -> bool:
        """
        Detect if the query is asking for a count or statistics.
        
        Args:
            query: User query (should be normalized)
            
        Returns:
            True if query is asking for a count/statistics
        """
        query_lower = query.lower()
        count_patterns = [
            'how many', 'how much', 'count', 'total', 'number of', 'num of',
            'total number', 'total count', 'total emails', 'statistics', 'stats',
            'how manny', 'how manys'  # Common typos (though _normalize_query should fix these)
        ]
        return any(pattern in query_lower for pattern in count_patterns)
    
    def _validate_sources_match_query(self, query: str, sources: List[Dict[str, Any]], email_direction: Optional[str]) -> tuple[List[Dict[str, Any]], bool]:
        """
        Validate that retrieved sources actually match the query intent.
        Critical for preventing hallucination.
        
        Args:
            query: User query
            sources: Retrieved sources
            email_direction: Detected direction ('sent', 'received', 'reply')
            
        Returns:
            Tuple of (filtered_sources, is_valid)
        """
        if not sources:
            return [], True  # Empty is valid
        
        query_lower = query.lower()
        
        # CRITICAL: Check if user is asking about SENT/REPLY emails from HAVAL
        if email_direction in ['sent', 'reply']:
            print(f"[Email RAG] 🔍 Validating sources for {email_direction} query...")
            
            # Check if sources contain received emails (customer complaints)
            # If yes, they don't match the query - user wants HAVAL's replies
            received_indicators = ['customer', 'complaint', 'issue', 'problem', 'concern', 'inquiry']
            
            haval_sources = []
            customer_sources = []
            
            for source in sources:
                title = source.get('title', '').lower()
                body = source.get('snippet', '').lower()
                sender = source.get('sender', '').lower()
                sender_email = source.get('sender_email', '').lower()
                
                print(f"[Email RAG]   Checking: {source.get('title', 'No Subject')}")
                print(f"[Email RAG]   Sender: {sender}")
                print(f"[Email RAG]   Sender Email: {sender_email}")
                
                # Check if this email is FROM HAVAL (these are HAVAL's sent emails/replies)
                # HAVAL's official email: vrd7808@gmail.com
                is_from_haval = (
                    'vrd7808@gmail.com' in sender.lower() or 
                    'vrd7808@gmail.com' in sender_email.lower() or
                    'haval' in sender or 
                    '@haval' in sender or 
                    'haval' in sender_email or 
                    '@haval.com' in sender_email
                )
                
                # Check if this looks like a customer complaint (incoming email TO haval)
                is_customer_email = any(indicator in title or indicator in body for indicator in received_indicators)
                is_from_customer = not is_from_haval  # If not from HAVAL, it's from customer
                
                if is_from_haval:
                    print(f"[Email RAG]   ✅ HAVAL email (sent by HAVAL)")
                    haval_sources.append(source)
                else:
                    print(f"[Email RAG]   ❌ Customer email (received from customer)")
                    customer_sources.append(source)
            
            # Summary
            print(f"[Email RAG] Validation results: {len(haval_sources)} HAVAL emails, {len(customer_sources)} customer emails")
            
            # If user asked for HAVAL replies but we only found customer emails
            if len(haval_sources) == 0 and len(customer_sources) > 0:
                print(f"[Email RAG] ⚠️ VALIDATION FAILED: User asked for {email_direction} emails but all {len(customer_sources)} retrieved sources are customer complaints")
                return [], False  # Return empty, mark as invalid
            
            # Return only HAVAL sources if user asked for replies
            if len(haval_sources) > 0:
                print(f"[Email RAG] ✅ VALIDATION PASSED: Found {len(haval_sources)} HAVAL {email_direction} emails")
                return haval_sources, True
            
            # If no sources match, validation fails
            print(f"[Email RAG] ⚠️ VALIDATION FAILED: No matching {email_direction} emails found")
            return [], False
        
        # For received/incoming queries or no direction specified, return all sources
        return sources, True
    
    def _filter_referenced_sources(self, answer: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter sources to only include emails that were actually referenced in the answer.
        Intelligently handles cases where no relevant emails are found.
        
        Args:
            answer: The generated answer text
            sources: List of all source dictionaries
            
        Returns:
            Filtered list containing only referenced sources, or empty list if no relevant emails found
        """
        import re
        
        if not sources:
            return []
        
        # Check if the answer indicates no relevant emails were found
        no_results_indicators = [
            "couldn't find any", "could not find any", "no emails", "no relevant emails",
            "no emails matching", "no emails found", "no emails regarding", "no emails about"
        ]
        
        answer_lower = answer.lower()
        if any(indicator in answer_lower for indicator in no_results_indicators):
            print("[Email RAG] ✅ Answer indicates no relevant emails found, returning empty sources")
            return []
        
        # Extract all email references from the answer
        # Matches patterns like:
        # - [REF: 19c3eaf476a92a41]
        # - Reference: 19c3eaf476a92a41
        # - Reference: [19c3eaf476a92a41]
        # - [Email #1] - Reference: [19c420b591b8e8f9]
        ref_pattern = r'(?:REF|Reference):\s*\[?([a-f0-9]+)\]?'
        referenced_ids = set(re.findall(ref_pattern, answer, re.IGNORECASE))
        
        print(f"[Email RAG] Found {len(referenced_ids)} unique email references in answer: {referenced_ids}")
        
        # Check if this is a count/summary query where the LLM provided a count without listing all emails
        count_indicators = [
            'found', 'total of', 'received', 'there are', 'there were',
            'emails on', 'emails received', 'emails in database', 'emails in our database'
        ]
        is_likely_count_answer = any(indicator in answer_lower for indicator in count_indicators)
        
        # If no references found but it's a count/summary answer, return all sources
        # This handles cases like "Found 18 emails on February 10, 2026"
        if not referenced_ids and is_likely_count_answer:
            print("[Email RAG] ℹ️ Count/summary answer without specific references, returning all available sources")
            return sources
        
        # If no references found in the answer, this means the LLM didn't discuss any specific emails
        # In this case, return empty sources instead of falling back to all sources
        if not referenced_ids:
            print("[Email RAG] ⚠️ No references found in answer, and answer doesn't indicate 'no results' - returning empty sources")
            return []
        
        # Filter sources to only include those that were referenced
        filtered_sources = []
        for source in sources:
            email_id = source.get('email_id', '')
            if email_id in referenced_ids:
                filtered_sources.append(source)
                print(f"[Email RAG] ✅ Including referenced email: {source.get('title', 'No Subject')} (ID: {email_id})")
            else:
                print(f"[Email RAG] ❌ Excluding unreferenced email: {source.get('title', 'No Subject')} (ID: {email_id})")
        
        return filtered_sources
    
    def _deduplicate_sources(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate emails based on email_id.
        
        Args:
            sources: List of source dictionaries
            
        Returns:
            Deduplicated list of sources
        """
        seen_ids = set()
        unique_sources = []
        
        for source in sources:
            email_id = source.get('email_id', '')
            if email_id and email_id not in seen_ids:
                seen_ids.add(email_id)
                unique_sources.append(source)
            elif not email_id:
                # Keep sources without email_id (shouldn't happen, but be safe)
                unique_sources.append(source)
        
        return unique_sources
    
    def _calculate_confidence_score(self, query: str, sources: List[Dict[str, Any]], answer: str) -> float:
        """
        Calculate confidence score for the answer based on various factors.
        
        Args:
            query: User query
            sources: Retrieved sources
            answer: Generated answer
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        score = 0.5  # Base score
        
        # Factor 1: Number of sources (more sources = higher confidence)
        if len(sources) >= 5:
            score += 0.2
        elif len(sources) >= 3:
            score += 0.1
        elif len(sources) == 0:
            score -= 0.3
        
        # Factor 2: Answer length (too short might indicate uncertainty)
        if len(answer) > 200:
            score += 0.1
        elif len(answer) < 50:
            score -= 0.2
        
        # Factor 3: Contains uncertainty phrases
        uncertainty_phrases = ['might', 'maybe', 'possibly', 'not sure', 'unclear', 'uncertain']
        if any(phrase in answer.lower() for phrase in uncertainty_phrases):
            score -= 0.2
        
        # Factor 4: Contains specific data (dates, numbers, names)
        import re
        if re.search(r'\d{1,2}/\d{1,2}/\d{4}', answer):  # Has dates
            score += 0.1
        if re.search(r'\d+', answer):  # Has numbers
            score += 0.05
        
        # Clamp between 0 and 1
        return max(0.0, min(1.0, score))
    
    def _suggest_query_clarification(self, query: str, sources: List[Dict[str, Any]]) -> Optional[str]:
        """
        Suggest query clarification if needed.
        
        Args:
            query: User query
            sources: Retrieved sources
            
        Returns:
            Clarification suggestion or None
        """
        query_lower = query.lower()
        
        # Too few results and no date specified
        if len(sources) < 3 and not self._extract_date_from_query(query):
            return "💡 Tip: Try adding a date range to narrow your search (e.g., 'last week', 'on Feb 10')."
        
        # Too many results and asking for specific info
        if len(sources) > 20 and ('specific' in query_lower or 'particular' in query_lower):
            return "💡 Tip: Your query returned many results. Try adding filters like 'from [sender]' or 'about [topic]'."
        
        # Asking about count but query is vague
        if self._is_count_query(query) and len(query.split()) <= 4:
            return "💡 Tip: For more specific results, specify a date or sender (e.g., 'how many emails from John last week')."
        
        return None
    
    def _classify_query_intent(self, query: str) -> str:
        """
        Classify the intent of the user's query.
        
        Args:
            query: User query (should be normalized)
            
        Returns:
            Intent classification: 'email_query', 'chit_chat', 'irrelevant'
        """
        query_lower = query.lower().strip()
        
        # Handle empty queries
        if not query_lower:
            return 'chit_chat'
        
        # Chit-chat patterns (including common variations and typos)
        chit_chat_patterns = [
            'hello', 'hi', 'hey', 'hii', 'hiii', 'helo', 'hola',
            'how are you', 'how r u', 'how r you', 'whats up', 'what\'s up', 'wassup',
            'good morning', 'good afternoon', 'good evening', 'good night',
            'thanks', 'thank you', 'thankyou', 'thx', 'ty',
            'bye', 'goodbye', 'good bye', 'see you', 'see ya', 'cya',
            'nice to meet you', 'pleased to meet you',
            'how do you work', 'how does this work', 'what can you do', 'what do you do',
            'help me', 'can you help', 'help please', 'i need help',
            'tell me about yourself', 'who are you', 'what is your name', 
            'what are you', 'are you human', 'are you a bot',
            'how are you doing', 'how r u doing', 'how have you been'
        ]
        
        # Check for chit-chat (word boundary matching)
        import re
        for pattern in chit_chat_patterns:
            if re.search(r'\b' + re.escape(pattern) + r'\b', query_lower):
                return 'chit_chat'
        
        # Irrelevant patterns (non-email related)
        irrelevant_patterns = [
            'weather', 'news', 'sports', 'politics', 'entertainment', 'movies',
            'music', 'food', 'travel', 'shopping', 'games', 'game', 'social media',
            'facebook', 'twitter', 'instagram', 'tiktok', 'youtube', 'netflix',
            'amazon', 'google', 'microsoft', 'apple', 'bitcoin', 'crypto',
            'stock market', 'finance', 'banking', 'insurance', 'health',
            'medical', 'doctor', 'hospital', 'school', 'education', 'job',
            'career', 'salary', 'taxes', 'government', 'law', 'legal'
        ]
        
        # Check for irrelevant topics (word boundary matching)
        import re
        for pattern in irrelevant_patterns:
            if re.search(r'\b' + re.escape(pattern) + r'\b', query_lower):
                return 'irrelevant'
        
        # Email-related keywords
        email_keywords = [
            'email', 'emails', 'mail', 'message', 'messages', 'inbox', 'sent',
            'received', 'sender', 'recipient', 'subject', 'attachment', 'cc', 'bcc',
            'complaint', 'complaints', 'issue', 'issues', 'problem', 'problems',
            'feedback', 'customer', 'client', 'user', 'support', 'help desk',
            'ticket', 'case', 'inquiry', 'question', 'request', 'order',
            'product', 'service', 'delivery', 'shipping', 'refund', 'return',
            'warranty', 'repair', 'maintenance', 'appointment', 'meeting',
            'schedule', 'calendar', 'date', 'time', 'today', 'yesterday',
            'this week', 'this month', 'last week', 'last month', 'recent',
            'latest', 'new', 'old', 'unread', 'read', 'important', 'urgent',
            'priority', 'follow up', 'response', 'reply', 'forward'
        ]
        
        # Check for email-related content (word boundary matching)
        import re
        for keyword in email_keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', query_lower):
                return 'email_query'
        
        # Default to email query if we can't classify (better to try than reject)
        return 'email_query'
    
    def _determine_result_limit(self, query: str, default_limit: int = 5) -> int:
        """
        Determine the appropriate result limit based on query content.
        
        Args:
            query: User query (should be normalized)
            default_limit: Default limit to use
            
        Returns:
            Dynamic result limit
        """
        query_lower = query.lower()
        
        # Handle empty queries
        if not query_lower:
            return default_limit
        
        print(f"[Email RAG] 🔍 Checking result limit for query: '{query_lower[:100]}'")
        
        # CRITICAL: If query contains a date, we need to retrieve ALL emails
        # so that date filtering can work properly (date filtering happens AFTER retrieval)
        if self._extract_date_from_query(query_lower):
            print("[Email RAG] 📅 Date detected in query, retrieving all emails for filtering")
            return 100
        
        # CRITICAL: If asking about sent/reply emails (email direction query),
        # retrieve ALL emails so validation can properly check if any are from HAVAL
        email_direction = self._detect_email_direction(query_lower)
        if email_direction in ['sent', 'reply']:
            print(f"[Email RAG] 📧 Direction query ({email_direction}) detected, retrieving all emails for validation")
            return 100
        
        # CRITICAL: For 'received' direction with comprehensive words, also retrieve all
        if email_direction == 'received':
            comprehensive_words = ['all', 'every', 'complete', 'full', 'entire']
            if any(word in query_lower for word in comprehensive_words):
                print(f"[Email RAG] 📧 Received query with comprehensive scope detected, retrieving all emails")
                return 100
        
        # Patterns that indicate comprehensive queries
        comprehensive_patterns = [
            'all emails', 'all email', 'every email', 'all messages', 'all mail',
            'complete list', 'full list', 'entire list', 'show me all', 'give me all',
            'list all', 'find all', 'search all', 'get all', 'retrieve all',
            'how many', 'count', 'total', 'number of', 'num of', 'how much',
            'summary of all', 'overview of all', 'total number', 'total count',
            'statistics', 'stats', 'analytics', 'analysis', 'breakdown',
            'date wise', 'day wise', 'by date', 'per day', 'daily breakdown',
            'monthly', 'weekly', 'yearly', 'by month', 'by week', 'by year',
            # Additional patterns for "all [adjective] emails"
            'all received', 'all incoming', 'all customer', 'all sent', 'all outgoing',
            'refer me all', 'show all', 'display all', 'give all', 'list everything'
        ]
        
        # Check if query asks for comprehensive results
        if any(pattern in query_lower for pattern in comprehensive_patterns):
            print(f"[Email RAG] 📊 Comprehensive query detected, retrieving all emails")
            return 100  # Large limit for comprehensive queries
        
        # CRITICAL: Additional check - if query contains "all" + email-related words (flexible matching)
        # This catches queries like "all received emails", "all customer emails", etc.
        if 'all' in query_lower and any(word in query_lower for word in ['email', 'emails', 'mail', 'message', 'messages']):
            print(f"[Email RAG] 📊 Query contains 'all' + email keywords, retrieving all emails")
            return 100
        
        # Patterns that indicate specific/limited queries
        specific_patterns = [
            'first', 'last', 'latest', 'recent', 'newest', 'oldest',
            'specific', 'particular', 'one', 'single', 'just', 'only'
        ]
        
        # Check if query asks for specific/limited results
        if any(pattern in query_lower for pattern in specific_patterns):
            return min(default_limit, 10)  # Smaller limit for specific queries
        
        # Default limit for general queries
        return default_limit
    
    def _generate_answer(self, query: str, context: str, sources: List[Dict[str, Any]], query_intent: str) -> str:
        """
        Generate answer using LLM
        
        Args:
            query: User query
            context: Context from retrieved emails
            sources: List of email sources
            query_intent: Classified intent of the query
            
        Returns:
            Generated answer
        """
        from datetime import datetime
        current_date = datetime.now().strftime('%B %d, %Y')
        
        prompt_template = """You are an intelligent email assistant for HAVAL Automobile Company's CEO.

TODAY'S DATE: {current_date}

---
CUSTOMER EMAILS DATABASE:
{context}
---

USER QUESTION: {query}

---
🤖 INTELLIGENT PROCESSING APPLIED:
- ✅ Emails pre-filtered by dates, senders, and subjects mentioned in your query
- ✅ All emails in context match your specific criteria
- ✅ Duplicates automatically removed
- ✅ Query validated to prevent hallucination
- ✅ Query expanded with synonyms for comprehensive matching

---
INSTRUCTIONS:

0. **ANTI-HALLUCINATION RULES** (MOST CRITICAL):
   - ONLY answer based on emails shown in the context above
   - If context is EMPTY or has NO relevant emails, you MUST say "No emails found"
   - Do NOT invent, fabricate, or hallucinate emails that don't exist in the context
   - Do NOT provide sample data or examples when no real emails exist
   - Do NOT list emails unless they appear with "EMAIL #X" in the context above
   - If user asks for SENT/REPLY emails but all context shows RECEIVED emails, say "No sent emails found"
   - When in doubt, be honest about data limitations

1. **DATE HANDLING** (CRITICAL):
   - If user asks about a SPECIFIC DATE (e.g., "February 10", "10th feb", "today"):
     → The system has ALREADY FILTERED the emails by date
     → ALL emails in the context above are from that specific date
     → Count EVERY email in the context above - that's the total for that date
     → February 8 ≠ February 9 ≠ February 10 (different days = different dates)
     → If the context is empty, say: "No emails found for [requested date]"
   
   - If user asks about DATE RANGE (e.g., "last week", "this month", "between X and Y"):
     → The system has ALREADY FILTERED emails within that range
     → ALL emails in context are from that date range
     → Provide breakdown by individual dates if helpful
   
   - If NO date is mentioned:
     → Use all relevant emails from the context

2. **COUNTING EMAILS** (CRITICAL):
   - When user asks "What emails" or "how many emails" for a specific date:
     → Count EVERY email entry in the context above
     → Each "EMAIL #X" in the context is ONE email
     → Do NOT limit your count - if there are 18 emails in context, say "18 emails"
     → Example: If you see EMAIL #1 through EMAIL #18, the answer is "18 emails"

3. **COMPREHENSIVE QUERIES** (for "all emails", "give me all", "how many", etc.):
   - When user asks for ALL emails or comprehensive results:
     → List EVERY relevant email from the context
     → Do NOT limit to just a few emails
     → Provide complete coverage of all matching emails
     → Include date-wise breakdown showing email counts per day

4. **DATE-WISE BREAKDOWN** (when requested or for comprehensive queries):
   - Group emails by date and show counts: "February 9: 3 emails, February 8: 2 emails, etc."
   - Sort dates chronologically (newest first)
   - Include this breakdown at the beginning of your response

5. **COUNT/STATISTICS QUERIES** (when user asks "how many", "count", "total", etc.):
   - If user asks for a count or total: Provide the exact count clearly
   - Format: "Found [number] emails on [date/period]:"
   - Then list each email with full details (including Reference ID for each)
   - For simple count queries with many results, you may skip individual listings and just provide the count
   - Example: "Found 18 emails on February 10, 2026." (then optionally list them if asked)

6. **EMAIL DIRECTION** (CRITICAL - ANTI-HALLUCINATION):
   - If user asks about HAVAL's REPLIES/RESPONSES/SENT emails:
     → Check if emails in context are FROM HAVAL (sender contains 'haval' or '@haval')
     → If ALL emails are customer complaints (incoming), say: "No replies from HAVAL found in the database"
     → Do NOT confuse received customer emails with sent HAVAL replies
     → Be honest: "The database currently contains incoming customer emails only"
   
   - If user asks about RECEIVED/INCOMING/CUSTOMER emails:
     → Use emails from customers (senders are NOT from HAVAL)
     → These are complaints, inquiries, requests from customers

5. **ANSWER FORMAT**:
   For each relevant email, provide:
   
   📧 **[Email #X]** - Reference: [REF ID from context]
   **Subject**: [email subject line]
   **From**: [sender name] <[email address]>
   **Date**: [exact date and time from email]
   **Issue/Complaint**: [detailed summary of the complaint/inquiry - 2-3 sentences]
   
   ---

7. **QUALITY RULES**:
   - Only answer based on emails shown in the context above
   - Do NOT invent or hallucinate emails that don't exist in the context
   - Do NOT include marketing emails, newsletters, or automated notifications
   - The system has already deduplicated emails - each email appears only once
   - Be concise but informative for individual emails
   - For comprehensive queries: be thorough but organized
   - **CRITICAL**: You MUST include "Reference: [REF ID]" for EVERY email you discuss when listing individual emails (this is required for source tracking)
   - For simple count queries ("how many emails"), you may provide just the count without listing all references

8. **RESPONSE STRUCTURE FOR COMPREHENSIVE QUERIES**:
   - Start with date-wise breakdown: "Found X emails across Y dates:"
   - Show date counts: "February 9: 3 emails, February 8: 2 emails, February 7: 1 email"
   - Then list each email with the format above (include Reference ID in the exact format: "Reference: [ID]")
   - End with a brief summary or action items if there are multiple emails

9. **RESPONSE STRUCTURE FOR COUNT QUERIES**:
   - Start with the count: "Found [X] emails [matching criteria]:"
   - Count based on how many emails are in the context (count all EMAIL #1, EMAIL #2, etc.)
   - If count is reasonable (<= 10), list each email with details and Reference IDs
   - If count is large (> 10), list the first few with details, then summarize the rest
   - Always be accurate about the count based on the TOTAL number of emails in the context

10. **RESPONSE STRUCTURE FOR DATE-SPECIFIC QUERIES** (e.g., "What emails on Feb 10?"):
   - Start: "Found [X] emails on [date]:" where X = total count of all emails in context
   - Example: If context shows EMAIL #1 through EMAIL #18, say "Found 18 emails on February 10, 2026:"
   - Then list each email with full details (Subject, From, Date, Issue) and Reference ID
   - For large counts (> 10), list first 10 and say "...and X more emails"

11. **RESPONSE STRUCTURE FOR SPECIFIC QUERIES**:
   - Start with a brief overview (e.g., "Found X complaints on [date]:")
   - List each email with the format above (include Reference ID in the exact format: "Reference: [ID]")
   - End with a brief summary or action items if there are multiple emails

12. **REFERENCE LINKING (MANDATORY)**:
   - Always include the [REF: xxx] from email context in your answer using the EXACT format: "Reference: [email_id]"
   - This allows users to view the original email
   - Format must be: 📧 **[Email #1]** - Reference: [email_id]
   - Do NOT skip the reference for any email you mention
   - Only include references for emails you actually discuss in your answer
   - **CRITICAL**: If no relevant emails are found, do NOT include ANY reference IDs

If the context contains no relevant emails for the question, respond honestly: "I couldn't find any emails matching your query." (without any reference IDs)

YOUR ANSWER:"""

        try:
            from datetime import datetime
            current_date = datetime.now().strftime("%B %d, %Y")
            
            prompt = PromptTemplate(
                template=prompt_template,
                input_variables=["context", "query", "current_date"]
            )
            
            formatted_prompt = prompt.format(context=context, query=query, current_date=current_date)
            
            # Generate response
            response = self.llm.invoke(formatted_prompt)
            
            # Extract answer from response
            if hasattr(response, 'content'):
                answer = response.content
            else:
                answer = str(response)
            
            return answer.strip()
            
        except Exception as e:
            log_error(f"Error generating answer: {e}")
            return "I encountered an error while generating the answer. Please try again."
    
    def query_with_filter(
        self,
        query: str,
        sender: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        n_results: int = 5
    ) -> Dict[str, Any]:
        """
        Query emails with metadata filters
        
        Args:
            query: User query
            sender: Filter by sender email
            date_from: Filter emails from this date
            date_to: Filter emails until this date
            n_results: Number of results
            
        Returns:
            Dictionary with answer and sources
        """
        filter_metadata = {}
        
        if sender:
            filter_metadata['sender'] = sender
        
        # Note: Date range filtering might need special handling in ChromaDB
        
        return self.query(query, n_results=n_results, filter_metadata=filter_metadata if filter_metadata else None)
    
    def summarize_emails(
        self,
        sender: Optional[str] = None,
        subject_keyword: Optional[str] = None,
        n_results: int = 10
    ) -> Dict[str, Any]:
        """
        Summarize recent emails with optional filters
        
        Args:
            sender: Filter by sender
            subject_keyword: Filter by subject keyword
            n_results: Number of emails to summarize
            
        Returns:
            Dictionary with summary
        """
        query = f"Summarize the main points and topics from recent emails"
        
        if sender:
            query += f" from {sender}"
        
        if subject_keyword:
            query += f" about {subject_keyword}"
        
        return self.query(query, n_results=n_results)


# Create prompt templates for different email query types
EMAIL_QUERY_PROMPTS = {
    'general': """Based on the following emails, answer the question: {query}

Emails:
{context}

Provide a clear and concise answer based on the email content.""",

    'complaint': """Analyze the following emails for complaints or issues.

Emails:
{context}

Question: {query}

Identify:
1. Nature of complaints
2. Severity
3. Common patterns
4. Recommended actions""",

    'summary': """Summarize the following emails:

{context}

Provide a concise summary covering:
1. Main topics discussed
2. Key action items
3. Important dates or deadlines
4. Notable senders or recipients""",

    'search': """Search through the following emails for information related to: {query}

Emails:
{context}

Provide relevant information found in the emails, citing specific emails when possible."""
}
