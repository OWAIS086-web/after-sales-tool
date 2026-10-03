# ai/rag_engine/core.py
"""
Core RAG Engine

Main retrieval-augmented generation engine for Haval H6 insights.
Coordinates all RAG components: classification, optimization, retrieval, and response generation.
"""

from __future__ import annotations

import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from ai.enrichment import EnrichmentState
from ai.llm_client import BaseLLMClient
from ai.vector_store import ChromaVectorStore, RetrievedBlock
from config import get_llm_config, get_llm_for_component

from .citation_builder import (build_citations, build_context,
                               build_context_whatsapp_semantic)
# Production conversational memory components
from .intent_classifier import classify_query_intent
from .keyword_extraction_llm import (apply_keyword_filter,
                                     extract_keywords_with_llm)
from .merged_classifier import classify_merged_with_regex_first
from .prompt_builder import (build_non_thinking_prompt, build_thinking_prompt,
                             messages_with_system)
# Import modular functions
from .query_classification import (extract_customer_name,
                                   extract_customer_names_llm,
                                   is_broad_insight_question,
                                   is_statistical_query,
                                   should_include_citations)
from .query_optimizer import format_range
from .query_reformulator import reformulate_query
from .redis_semantic_cache import RedisSemanticCache
from .semantic_cache import SemanticCache

# =============================================================================
# PARALLEL LLM EXECUTION UTILITIES
# =============================================================================

def run_llm_calls_parallel(tasks: Dict[str, Callable], max_workers: int = 3) -> Dict[str, Any]:
    """
    Execute multiple LLM calls in parallel using ThreadPoolExecutor.

    This provides significant speedup for independent LLM operations:
        pass
    - Sequential: task1_time + task2_time + task3_time
    - Parallel: max(task1_time, task2_time, task3_time)

    Args:
        tasks: Dictionary mapping task names to callables
               Example: {
                   "classification": lambda: classify_query_domain(llm, question),
                   "optimization": lambda: optimize_queries(question, store, llm),
               }
        max_workers: Maximum number of parallel threads (default: 3)

    Returns:
        Dictionary mapping task names to their results
        Example: {
            "classification": "in_domain",
            "optimization": [{"query": "...", ...}],
        }

    HOW TO ADD NEW PARALLEL LLM CALLS:
    ===================================
    1. Define your LLM function call as a lambda or function
    2. Add it to the tasks dictionary with a descriptive key
    3. Access the result from the returned dictionary

    Example:
        # Before (sequential - slow):
        classification = classify_query_domain(llm, question)
        optimization = optimize_queries(question, store, llm)
        citation_check = should_include_citations(question, llm)

        # After (parallel - fast):
        results = run_llm_calls_parallel({
            "classification": lambda: classify_query_domain(llm, question),
            "optimization": lambda: optimize_queries(question, store, llm),
            "citation_check": lambda: should_include_citations(question, llm),
        })
        classification = results["classification"]
        optimization = results["optimization"]
        citation_check = results["citation_check"]

    Error Handling:
        - If a task fails, its result will be None
        - Errors are logged but don't stop other tasks
        - Always check if result is None before using
    """
    results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_task = {executor.submit(func): name for name, func in tasks.items()}

        # Collect results as they complete
        for future in as_completed(future_to_task):
            task_name = future_to_task[future]
            try:
                results[task_name] = future.result()
                # print(f"  [OK] [Parallel] {task_name} completed")
            except Exception as e:
                # print(f"  [FAIL] [Parallel] {task_name} failed: {e}")
                results[task_name] = None

    return results


class RAGEngine:
    """
    Retrieval-Augmented Generation engine for multi-company automotive forum data.

    Features:
    - Dual vector stores (Forum + WhatsApp conversations)
    - Query optimization with sub-query decomposition
    - Time-window and metadata filtering
    - Thinking vs non-thinking response modes
    - Customer-specific WhatsApp conversation retrieval
    """

    def __init__(
        self,
        pakwheels_store: ChromaVectorStore,
        whatsapp_store: ChromaVectorStore,
        llm: BaseLLMClient,
        reddit_store: Optional[ChromaVectorStore] = None,
        lucid_store: Optional[ChromaVectorStore] = None,
        reddit_lucid_store: Optional[ChromaVectorStore] = None,
        k: int = 5,
        state: Optional[EnrichmentState] = None,
        max_block_chars: int = 2048,
        company_id: str = "haval",
        enable_semantic_cache: bool = True,
    ):
        """
        Initialize RAG engine with vector stores and LLM client.

        Args:
            pakwheels_store: Vector store for PakWheels forum data
            whatsapp_store: Vector store for WhatsApp conversations
            llm: LLM client implementing BaseLLMClient interface
            reddit_store: Vector store for Reddit discussions (optional)
            lucid_store: Vector store for Lucid Forum discussions (optional)
            reddit_lucid_store: Vector store for Reddit Lucid discussions (optional, for Lucid company)
            k: Default top-k for retrieval
            state: Enrichment state with known variants/tags
            max_block_chars: Maximum characters per context block
            company_id: Company identifier (e.g., "haval", "kia") for URLs and prompts
            enable_semantic_cache: Enable semantic caching for repeated queries (default: True)
        """
        # Store all vector stores in a dictionary for easy lookup
        self.vector_stores = {}
        
        # Only add stores that are not None
        if pakwheels_store is not None:
            self.vector_stores["pakwheels"] = pakwheels_store
        
        if whatsapp_store is not None:
            self.vector_stores["whatsapp"] = whatsapp_store
        
        # Add Reddit store if provided
        if reddit_store is not None:
            self.vector_stores["reddit"] = reddit_store
        
        # Add Lucid store if provided
        if lucid_store is not None:
            self.vector_stores["lucid"] = lucid_store
        
        # Add Reddit Lucid store if provided (for Lucid company)
        if reddit_lucid_store is not None:
            self.vector_stores["reddit_lucid"] = reddit_lucid_store
        self.llm = llm
        self.k = k
        self.state = state or EnrichmentState()
        self.max_block_chars = max_block_chars
        self.company_id = company_id

        # Initialize semantic cache (Redis + ChromaDB hybrid with fallback)
        # Priority: Redis cache → Old ChromaDB cache → Pipeline
        self.redis_cache = None
        self.semantic_cache = None  # Fallback cache

        if enable_semantic_cache:
            # Try Redis cache first (production-grade with unlimited storage)
            try:
                self.redis_cache = RedisSemanticCache(pipeline="rag")
                # print(f"[RAG] OK Redis semantic cache enabled (primary)")
            except Exception as e:
                # print(f"[RAG] WARNING: Redis cache initialization failed: {e}")
                # print(f"[RAG] Will use fallback ChromaDB cache")
                self.redis_cache = None

            # Initialize fallback ChromaDB cache (used if Redis unavailable)
            try:
                self.semantic_cache = SemanticCache(
                    persist_directory=f"./data/semantic_cache_{company_id}",
                    similarity_threshold=0.96,
                    session_ttl_hours=24
                )
                # print(f"[RAG] OK ChromaDB cache enabled (fallback, threshold: 0.96, TTL: 24h)")
            except Exception as e:
                # print(f"[RAG] WARNING: Fallback cache initialization failed: {e}")
                # print(f"[RAG] Continuing without any cache")
                self.semantic_cache = None

        # Get company configuration for URLs and names
        try:
            from config import get_company_config
            self.company_config = get_company_config(company_id)
        except Exception as e:
            # print(f"[RAG] Warning: Could not load company config for {company_id}: {e}")
            self.company_config = None

        # Load and cache date spans from pkl files (verbose on first load)
        self.date_spans = self._load_date_spans_from_pkl(company_id, verbose=True)

    def _load_date_spans_from_pkl(self, company_id: str, verbose: bool = True) -> Dict[str, Tuple[Optional[datetime], Optional[datetime]]]:
        """
        Load date spans from pkl files for both PakWheels and WhatsApp data.

        Args:
            company_id: Company identifier to load data for
            verbose: If True, print detailed logs. If False, only log errors.

        Returns:
            Dictionary with "pakwheels" and "whatsapp" keys, each containing (min_date, max_date) tuple
        """
        import os
        import pickle
        from datetime import datetime

        from config import get_company_config

        config = get_company_config(company_id)
        date_spans = {}

        # Load PakWheels date span
        if config.has_pakwheels and os.path.exists(config.pakwheels_blocks_file):
            try:
                with open(config.pakwheels_blocks_file, 'rb') as f:
                    pakwheels_blocks = pickle.load(f)

                dates = []
                for block_id, block in pakwheels_blocks.items():
                    # ConversationBlock has start_datetime, not date
                    if hasattr(block, 'start_datetime') and block.start_datetime:
                        dates.append(block.start_datetime)
                    elif hasattr(block, 'date') and block.date:
                        dates.append(block.date)

                if dates:
                    date_spans["pakwheels"] = (min(dates), max(dates))
                    if verbose:
                        pass
                        # print(f"[DateSpan] PakWheels: {len(dates)} blocks with dates (range: {min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')})")
                else:
                    date_spans["pakwheels"] = (None, None)
                    if verbose:
                        pass
                        # print(f"[DateSpan] PakWheels: No dates found in blocks")
            except Exception as e:
                # print(f"[DateSpan] Error loading PakWheels dates: {e}")
                date_spans["pakwheels"] = (None, None)
        else:
            date_spans["pakwheels"] = (None, None)
            if verbose:
                if not config.has_pakwheels:
                    pass
                    # print(f"[DateSpan] PakWheels not available for {company_id}")
                else:
                    # print(f"[DateSpan] PakWheels pkl file not found: {config.pakwheels_blocks_file}")
                    pass

        # Load WhatsApp date span
        if config.has_whatsapp and config.whatsapp_blocks_file and os.path.exists(config.whatsapp_blocks_file):
            try:
                with open(config.whatsapp_blocks_file, 'rb') as f:
                    whatsapp_blocks = pickle.load(f)

                dates = []
                for block_id, block in whatsapp_blocks.items():
                    # ConversationBlock has start_datetime, not date
                    if hasattr(block, 'start_datetime') and block.start_datetime:
                        dates.append(block.start_datetime)
                    elif hasattr(block, 'date') and block.date:
                        dates.append(block.date)

                if dates:
                    date_spans["whatsapp"] = (min(dates), max(dates))
                    if verbose:
                        pass
                        # print(f"[DateSpan] WhatsApp: {len(dates)} blocks with dates (range: {min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')})")
                else:
                    date_spans["whatsapp"] = (None, None)
                    if verbose:
                        pass
                        # print(f"[DateSpan] WhatsApp: No dates found in blocks")
            except Exception as e:
                # print(f"[DateSpan] Error loading WhatsApp dates: {e}")
                date_spans["whatsapp"] = (None, None)
        else:
            date_spans["whatsapp"] = (None, None)
            if verbose:
                if not config.has_whatsapp:
                    pass
                    # print(f"[DateSpan] WhatsApp not available for {company_id}")
                elif not config.whatsapp_blocks_file:
                    pass
                    # print(f"[DateSpan] WhatsApp pkl file path not configured for {company_id}")
                else:
                    # print(f"[DateSpan] WhatsApp pkl file not found: {config.whatsapp_blocks_file}")
                    pass

        # Load Reddit date span
        if hasattr(config, 'has_reddit') and config.has_reddit and config.reddit_blocks_file and os.path.exists(config.reddit_blocks_file):
            try:
                with open(config.reddit_blocks_file, 'rb') as f:
                    reddit_blocks = pickle.load(f)

                dates = []
                for block_id, block in reddit_blocks.items():
                    # ConversationBlock has start_datetime, not date
                    if hasattr(block, 'start_datetime') and block.start_datetime:
                        dates.append(block.start_datetime)
                    elif hasattr(block, 'date') and block.date:
                        dates.append(block.date)

                if dates:
                    date_spans["reddit"] = (min(dates), max(dates))
                    if verbose:
                        pass
                        # print(f"[DateSpan] Reddit: {len(dates)} blocks with dates (range: {min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')})")
                else:
                    date_spans["reddit"] = (None, None)
                    if verbose:
                        pass
                        # print(f"[DateSpan] Reddit: No dates found in blocks")
            except Exception as e:
                # print(f"[DateSpan] Error loading Reddit dates: {e}")
                date_spans["reddit"] = (None, None)
        else:
            date_spans["reddit"] = (None, None)
            # Don't log missing Reddit - it's optional and usually not configured

        # Load Lucid date span
        if hasattr(config, 'has_lucid') and config.has_lucid and hasattr(config, 'lucid_blocks_file') and config.lucid_blocks_file and os.path.exists(config.lucid_blocks_file):
            try:
                with open(config.lucid_blocks_file, 'rb') as f:
                    lucid_blocks = pickle.load(f)

                dates = []
                for block_id, block in lucid_blocks.items():
                    # ConversationBlock has start_datetime, not date
                    if hasattr(block, 'start_datetime') and block.start_datetime:
                        dates.append(block.start_datetime)
                    elif hasattr(block, 'date') and block.date:
                        dates.append(block.date)

                if dates:
                    date_spans["lucid"] = (min(dates), max(dates))
                    if verbose:
                        pass
                        # print(f"[DateSpan] Lucid Forum: {len(dates)} blocks with dates (range: {min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')})")
                else:
                    date_spans["lucid"] = (None, None)
                    if verbose:
                        pass
                        # print(f"[DateSpan] Lucid Forum: No dates found in blocks")
            except Exception as e:
                # print(f"[DateSpan] Error loading Lucid dates: {e}")
                date_spans["lucid"] = (None, None)
        else:
            date_spans["lucid"] = (None, None)
            # Don't log missing Lucid - it's optional and usually not configured

        # Load Reddit Lucid date span
        if hasattr(config, 'has_lucid') and config.has_lucid and hasattr(config, 'reddit_lucid_blocks_file') and config.reddit_lucid_blocks_file and os.path.exists(config.reddit_lucid_blocks_file):
            try:
                with open(config.reddit_lucid_blocks_file, 'rb') as f:
                    reddit_lucid_blocks = pickle.load(f)

                dates = []
                for block_id, block in reddit_lucid_blocks.items():
                    # ConversationBlock has start_datetime, not date
                    if hasattr(block, 'start_datetime') and block.start_datetime:
                        dates.append(block.start_datetime)
                    elif hasattr(block, 'date') and block.date:
                        dates.append(block.date)

                if dates:
                    date_spans["reddit_lucid"] = (min(dates), max(dates))
                    if verbose:
                        pass
                        # print(f"[DateSpan] Reddit Lucid: {len(dates)} blocks with dates (range: {min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')})")
                else:
                    date_spans["reddit_lucid"] = (None, None)
                    if verbose:
                        pass
                        # print(f"[DateSpan] Reddit Lucid: No dates found in blocks")
            except Exception as e:
                # print(f"[DateSpan] Error loading Reddit Lucid dates: {e}")
                date_spans["reddit_lucid"] = (None, None)
        else:
            date_spans["reddit_lucid"] = (None, None)
            # Don't log missing Reddit Lucid - it's optional and usually not configured

        return date_spans

    def _build_date_metadata_context(self) -> str:
        """
        Build date availability metadata to inject into system prompt.

        Provides LLM with exact date spans for PakWheels, WhatsApp, and Reddit data
        to ensure consistent, accurate answers to date span queries.

        Returns:
            Formatted string with exact date spans for all data sources
        """
        company_name = self.company_config.full_name if self.company_config else "Haval H6"
        lines = ["\n### CRITICAL DATA AVAILABILITY INFORMATION"]
        lines.append(f"The following data is available for {company_name}:")
        lines.append("")

        # PakWheels dates
        pw_start, pw_end = self.date_spans.get("pakwheels", (None, None))
        if pw_start and pw_end:
            pw_start_fmt = pw_start.strftime("%B %d, %Y")
            pw_end_fmt = pw_end.strftime("%B %d, %Y")
            lines.append(f"- **Forum data**: {pw_start_fmt} to {pw_end_fmt}")

        # WhatsApp dates
        wa_start, wa_end = self.date_spans.get("whatsapp", (None, None))
        if wa_start and wa_end:
            wa_start_fmt = wa_start.strftime("%B %d, %Y")
            wa_end_fmt = wa_end.strftime("%B %d, %Y")
            lines.append(f"- **WhatsApp conversations**: {wa_start_fmt} to {wa_end_fmt}")

        # Reddit dates
        reddit_start, reddit_end = self.date_spans.get("reddit", (None, None))
        if reddit_start and reddit_end:
            reddit_start_fmt = reddit_start.strftime("%B %d, %Y")
            reddit_end_fmt = reddit_end.strftime("%B %d, %Y")
            lines.append(f"- **Reddit discussions**: {reddit_start_fmt} to {reddit_end_fmt}")

        # Lucid Forum dates
        lucid_start, lucid_end = self.date_spans.get("lucid", (None, None))
        if lucid_start and lucid_end:
            lucid_start_fmt = lucid_start.strftime("%B %d, %Y")
            lucid_end_fmt = lucid_end.strftime("%B %d, %Y")
            lines.append(f"- **Lucid Forum discussions**: {lucid_start_fmt} to {lucid_end_fmt}")

        # Reddit Lucid dates
        reddit_lucid_start, reddit_lucid_end = self.date_spans.get("reddit_lucid", (None, None))
        if reddit_lucid_start and reddit_lucid_end:
            reddit_lucid_start_fmt = reddit_lucid_start.strftime("%B %d, %Y")
            reddit_lucid_end_fmt = reddit_lucid_end.strftime("%B %d, %Y")
            lines.append(f"- **Reddit Lucid discussions**: {reddit_lucid_start_fmt} to {reddit_lucid_end_fmt}")

        lines.append("")
        lines.append("**CRITICAL INSTRUCTIONS:**")
        lines.append("1. When asked about date spans, time ranges, data coverage, earliest/latest dates, or any temporal information, ALWAYS use the EXACT dates listed above.")
        lines.append("2. Do NOT infer, estimate, or approximate dates. Use only the dates provided above.")
        lines.append("3. Format dates as shown above: 'Month DD, YYYY to Month DD, YYYY'")
        lines.append("4. These dates are retrieved directly from the database and are 100% accurate.")
        lines.append("")

        return "\n".join(lines)

    def refresh_date_spans(self):
        """
        Refresh date spans after new data is added.

        Should be called after pipeline completes to update with latest data.
        Uses silent mode to avoid duplicate logging.
        """
        self.date_spans = self._load_date_spans_from_pkl(self.company_id, verbose=False)

    def _parse_block_into_messages(self, block) -> List[Dict[str, Any]]:
        """
        Parse a ConversationBlock into individual messages.

        Converts root_post + replies into a list of message dicts with:
        - username: Who sent the message
        - text: Message content
        - timestamp: When it was sent
        - is_customer: True if from customer, False if from bot

        Args:
            block: ConversationBlock object

        Returns:
            List of message dicts in chronological order
        """
        messages = []

        # Add root post
        messages.append({
            'username': block.root_post.username,
            'text': block.root_post.text,
            'timestamp': block.root_post.created_at,
            'is_customer': True,  # Root post is always from customer
        })

        # Add all replies
        for reply in block.replies:
            messages.append({
                'username': reply.username,
                'text': reply.text,
                'timestamp': reply.created_at,
                'is_customer': reply.username.lower() != 'bot',  # Bot messages vs customer
            })

        # Sort by timestamp to ensure chronological order
        messages.sort(key=lambda m: m['timestamp'])

        return messages

    def _filter_messages_by_relevance(
        self,
        messages: List[Dict[str, Any]],
        query: str,
        block_tags: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Filter messages to only show those relevant to the query.

        Uses keyword matching + enrichment tags to determine relevance.
        Always preserves first and last message for context.

        Args:
            messages: List of message dicts
            query: User's search query
            block_tags: Enrichment tags from the block

        Returns:
            Filtered list of relevant messages
        """
        if not query or len(messages) <= 5:
            return messages  # Show all if query is empty or few messages

        # Extract keywords from query (excluding generic words and stopwords)
        stopwords = {
            'show', 'tell', 'what', 'which', 'where', 'when', 'customer', 'customers',
            'chat', 'chats', 'conversation', 'conversations', 'message', 'messages',
            'about', 'from', 'with', 'have', 'there', 'their', 'this', 'that',
            'these', 'those', 'some', 'any', 'many', 'much',
            'issue', 'issues', 'problem', 'problems',
            'related', 'regarding', 'concerning'
        }
        query_keywords = [
            word.rstrip('?.,!') for word in query.lower().split()
            if len(word) > 3 and word.rstrip('?.,!') not in stopwords
        ]

        # Also check block tags for relevance
        relevant_tags = [tag for tag in block_tags if any(kw in tag for kw in query_keywords)]

        # If no specific keywords and no tag match, show all messages
        if not query_keywords and not relevant_tags:
            return messages

        # Filter messages by keyword relevance
        relevant_messages = []
        for msg in messages:
            msg_text_lower = msg['text'].lower()

            # Check if message contains any query keywords
            is_relevant = any(keyword in msg_text_lower for keyword in query_keywords)

            # Or if message is from customer (customer messages are important)
            is_customer_message = msg['is_customer']

            if is_relevant or is_customer_message:
                relevant_messages.append(msg)

        # Always include first and last message for context
        result = []
        if messages and messages[0] not in relevant_messages:
            result.append(messages[0])

        result.extend(relevant_messages)

        if messages and messages[-1] not in relevant_messages and messages[-1] not in result:
            result.append(messages[-1])

        # If we filtered too aggressively (< 3 messages), return more context
        if len(result) < 3 and len(messages) > 3:
            return messages

        return result

    def _get_whatsapp_messages_by_customer(
        self,
        customer_name: str,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve WhatsApp messages for a specific customer from the vector store.
        Falls back to direct database search if vector store doesn't have the customer.

        Args:
            customer_name: Customer name to search for
            query: User's original query (for relevance filtering)

        Returns:
            List of message dicts with individual messages
        """
        # First try vector store search (existing logic)
        vector_messages = self._get_whatsapp_messages_from_vector_store(customer_name, query)
        
        if vector_messages:
            # print(f"[RAG] Found {len(vector_messages)} messages in vector store for '{customer_name}'")
            return vector_messages
        
        # Fallback: Search directly in database (like old project)
        # print(f"[RAG] No messages in vector store, trying database search for '{customer_name}'")
        return self._get_whatsapp_messages_from_database(customer_name, query)

    def _get_whatsapp_messages_from_vector_store(
        self,
        customer_name: str,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for WhatsApp messages in the vector store (original logic)
        """
        # Get WhatsApp vector store
        whatsapp_store = self.vector_stores.get("whatsapp")
        if not whatsapp_store:
            # print(f"[RAG] WhatsApp vector store not found")
            return []

        try:
            # Search for customer name in vector store blocks (case-insensitive, partial match)
            matching_blocks = []
            customer_name_lower = customer_name.lower()

            for block_id, block in whatsapp_store.blocks_by_id.items():
                if hasattr(block, 'root_post') and hasattr(block.root_post, 'username'):
                    username = block.root_post.username.lower()
                    # Match if customer_name is a substring of username (case-insensitive)
                    if customer_name_lower in username:
                        matching_blocks.append(block)

            # print(f"[RAG] Found {len(matching_blocks)} blocks matching customer '{customer_name}' in vector store")

            if not matching_blocks:
                return []

            # Parse blocks into individual messages
            all_messages = []
            for block in matching_blocks:
                # Parse block into individual messages
                parsed_messages = self._parse_block_into_messages(block)

                # Get block metadata for filtering
                block_tags = getattr(block, 'aggregated_tags', [])

                # Filter messages by relevance if query has specific keywords
                if query:
                    filtered_messages = self._filter_messages_by_relevance(
                        parsed_messages,
                        query,
                        block_tags
                    )
                else:
                    filtered_messages = parsed_messages

                # Convert to expected format
                customer_username = block.root_post.username
                phone = getattr(block, 'phone_number', 'N/A')

                for msg in filtered_messages:
                    all_messages.append({
                        'customer_name': customer_username,
                        'country_code': '',
                        'contact_number': phone,
                        'message_type': 'conversation',
                        'message': msg['text'],  # Individual message text (not truncated!)
                        'timestamp': str(msg['timestamp']),
                        'imported_at': str(msg['timestamp']),
                        'username': msg['username'],  # Who sent this message
                    })

            print(f"[RAG] Retrieved {len(all_messages)} individual messages for customer '{customer_name}'")
            if query:
                pass
                # print(f"[RAG] Applied query-based filtering for: '{query[:50]}...'")

            return all_messages

        except Exception as e:
            # print(f"[RAG] Error retrieving WhatsApp messages from vector store for '{customer_name}': {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_whatsapp_messages_from_database(
        self,
        customer_name: str,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fallback: Search for WhatsApp messages directly in database (like old project)
        """
        try:
            import urllib.parse

            from models import get_db_connection
            
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Try exact match first (like old project)
            cur.execute("""
                SELECT customer_name, message, message_type, timestamp, 
                       country_code, contact_number, imported_at
                FROM whatsapp_messages 
                WHERE customer_name = ?
                ORDER BY timestamp DESC
                LIMIT 50
            """, (customer_name,))
            messages = cur.fetchall()
            
            # If no exact match, try partial match
            if not messages:
                cur.execute("""
                    SELECT customer_name, message, message_type, timestamp,
                           country_code, contact_number, imported_at
                    FROM whatsapp_messages 
                    WHERE LOWER(customer_name) LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT 50
                """, (f"%{customer_name.lower()}%",))
                messages = cur.fetchall()
            
            # If still no match, try URL decoding
            if not messages:
                decoded_customer = urllib.parse.unquote(customer_name)
                if decoded_customer != customer_name:
                    cur.execute("""
                        SELECT customer_name, message, message_type, timestamp,
                               country_code, contact_number, imported_at
                        FROM whatsapp_messages 
                        WHERE customer_name = ? OR LOWER(customer_name) LIKE ?
                        ORDER BY timestamp DESC
                        LIMIT 50
                    """, (decoded_customer, f"%{decoded_customer.lower()}%"))
                    messages = cur.fetchall()
            
            conn.close()
            
            # Convert to expected format
            all_messages = []
            for msg in messages:
                all_messages.append({
                    'customer_name': msg[0],
                    'message': msg[1],
                    'message_type': msg[2],
                    'timestamp': msg[3],
                    'country_code': msg[4] or '',
                    'contact_number': msg[5] or '',
                    'imported_at': msg[6],
                    'username': msg[0],  # Use customer name as username
                })
            
            # print(f"[RAG] Database search found {len(all_messages)} messages for '{customer_name}'")
            return all_messages
            
        except Exception as e:
            # print(f"[RAG] Error retrieving WhatsApp messages from database for '{customer_name}': {e}")
            import traceback
            traceback.print_exc()
            return []

    def _handle_whatsapp_customer_query(
        self,
        question: str,
        customer_name: str,
        history: Optional[List[Dict[str, str]]],
        thinking_mode: bool
    ) -> str:
        """
        Handle WhatsApp queries for a specific customer name.

        Retrieves messages directly from database and formats response.

        Args:
            question: User's question
            customer_name: Extracted customer name
            history: Chat history
            thinking_mode: Whether to use thinking mode

        Returns:
            Formatted response about customer's conversation
        """
        print(f"[RAG] Handling WhatsApp customer query for: '{customer_name}'")
        print(f"[RAG] Original query: '{question}'")
        print(f"[RAG] Thinking mode: {thinking_mode}")

        # Get messages for the specific customer (with smart filtering based on query)
        messages = self._get_whatsapp_messages_by_customer(customer_name, query=question)
        print(f"[RAG] Retrieved {len(messages)} messages for customer '{customer_name}'")

        if not messages:
            # Enhanced error message with debugging info
            debug_info = ""
            try:
                from models import get_db_connection
                conn = get_db_connection()
                cur = conn.cursor()
                
                # Get total WhatsApp messages count
                cur.execute("SELECT COUNT(*) FROM whatsapp_messages")
                total_count = cur.fetchone()[0]
                
                # Get sample customer names for suggestions
                cur.execute("SELECT DISTINCT customer_name FROM whatsapp_messages ORDER BY customer_name LIMIT 10")
                sample_customers = [row[0] for row in cur.fetchall()]
                
                conn.close()
                
                debug_info = f"\n\n**Debug Info:**\n• Total WhatsApp messages in database: {total_count}\n• Sample customer names: {', '.join(sample_customers[:5])}"
                if len(sample_customers) > 5:
                    debug_info += f" (and {len(sample_customers) - 5} more)"
                    
            except Exception as e:
                debug_info = f"\n\n**Debug Info:** Error accessing database: {str(e)}"
            
            return f"I couldn't find any WhatsApp messages for '{customer_name}'. Please check the spelling or try a different name.{debug_info}\n\nTip: Try searching for partial names or check the customer list in the WhatsApp view."

        # Format messages for the LLM
        context_parts = []
        for idx, msg in enumerate(messages, 1):
            msg_type = msg.get('message_type', 'unknown')
            emoji = "❗" if msg_type == "complaint" else "❓"
            contact = f"+{msg.get('country_code', '')}{msg.get('contact_number', '')}"

            context_parts.append(
                f"[WA-{idx}] {emoji} **{msg.get('customer_name', 'Unknown')}** ({msg_type})\n"
                f"   Message: {msg.get('message', 'N/A')}\n"
                f"   Contact: {contact}\n"
                f"   Time: {msg.get('timestamp', 'N/A')}\n"
            )

        context = "\n".join(context_parts)
        print(f"[RAG] Context length: {len(context)} characters")
        print(f"[RAG] Context preview: {context[:200]}...")

        # Build system prompt for customer-specific query
        system_prompt = f"""You are an AI assistant analyzing WhatsApp messages for a specific customer: {customer_name}.

**Customer: {customer_name}**
**Total Messages: {len(messages)}**

**Messages Context:**
{context}

**Instructions:**
- Focus ONLY on messages from {customer_name}
- Provide a clear summary of their conversation history
- Identify any complaints, queries, or issues they raised
- Include timestamps and message types in your analysis
- When referencing messages, cite them as [WA-1], [WA-2], etc.
- Be empathetic and professional in your response
- **IMPORTANT**: You MUST include ALL {len(messages)} messages in your references section
- **MANDATORY**: Show every single message with its citation, timestamp, and content

**Answer Format:**
Structure your response with:
1. Customer overview (name, contact, message count)
2. Conversation summary
3. Key issues or queries raised
4. Timeline of interactions (chronological order)
5. **MANDATORY References section**: List ALL {len(messages)} messages with full details

**References Section Format (MANDATORY):**
You MUST include ALL messages in this exact format:

---
### 📋 References

**[WA-1]** [USER] {customer_name} | [PHONE] Contact | [TAG] Message Type | [TIME] Timestamp
[MSG] *"Full message content here"*

**[WA-2]** [USER] {customer_name} | [PHONE] Contact | [TAG] Message Type | [TIME] Timestamp
[MSG] *"Full message content here"*

[Continue for ALL {len(messages)} messages]

---

**CRITICAL**:
- Do not summarize or skip any messages. Show every single one with its full content.
- Do NOT generate charts or visualizations for individual customer queries
- Focus on providing a comprehensive text-based analysis and complete message listing

Answer the user's question about {customer_name}'s WhatsApp conversation."""

        # Build messages for LLM
        messages_for_llm = [{"role": "system", "content": system_prompt}]
        if history:
            messages_for_llm.extend(history)
        messages_for_llm.append({"role": "user", "content": question})

        # Get temperature and max_tokens from mode-specific config
        config_component = "answer_generation_thinking" if thinking_mode else "answer_generation_non_thinking"
        answer_config = get_llm_config(config_component)
        llm_temperature = answer_config.temperature
        llm_max_tokens = answer_config.max_tokens
        print(f"  > Using {config_component}: temp={llm_temperature}, max_tokens={llm_max_tokens}")

        # Generate response (use config-based tokens for comprehensive customer analysis)
        resp = self.llm.generate(
            messages_for_llm,
            top_k=1,
            max_tokens=llm_max_tokens,
            temperature=llm_temperature,
        )

        answer_text = (resp.content or "").strip()

        if not answer_text:
            return f"I found {len(messages)} messages for {customer_name} but couldn't generate a summary. Please try rephrasing your question."

        return answer_text

    def _handle_whatsapp_multi_customer_query(
        self,
        question: str,
        customer_names: List[str],
        history: Optional[List[Dict[str, str]]],
        thinking_mode: bool
    ) -> str:
        """
        Handle WhatsApp queries for MULTIPLE customers.

        Examples:
        - "Compare Ali and Ahmed's conversations"
        - "Show me Ali, Ahmed, and Fatima's chats"
        - "What did Ali and Ahmed say about brakes?"

        Args:
            question: User's question
            customer_names: List of customer names
            history: Chat history
            thinking_mode: Whether to use thinking mode

        Returns:
            Formatted comparative analysis of multiple customers
        """
        print(f"[RAG] Handling WhatsApp MULTI-customer query for: {customer_names}")
        print(f"[RAG] Original query: '{question}'")

        # Get messages for ALL customers (with smart filtering based on query)
        all_customer_data = []
        for customer_name in customer_names:
            messages = self._get_whatsapp_messages_by_customer(customer_name, query=question)
            all_customer_data.append({
                "customer_name": customer_name,
                "messages": messages,
                "message_count": len(messages)
            })
            print(f"[RAG] Retrieved {len(messages)} messages for '{customer_name}'")

        # Check if any customer has no messages
        customers_with_no_messages = [d["customer_name"] for d in all_customer_data if d["message_count"] == 0]
        if len(customers_with_no_messages) == len(customer_names):
            return f"I couldn't find messages for any of these customers: {', '.join(customer_names)}. Please check the names and try again."

        # Build combined context with clear customer separation
        combined_context = []
        for data in all_customer_data:
            if data["message_count"] > 0:
                combined_context.append(f"\n{'='*60}")
                combined_context.append(f"CUSTOMER: {data['customer_name']}")
                combined_context.append(f"MESSAGE COUNT: {data['message_count']}")
                combined_context.append(f"{'='*60}\n")

                for msg in data["messages"]:
                    combined_context.append(
                        f"[{msg['timestamp']}] {msg['customer_name']}: {msg['message']}"
                    )

        combined_context_text = "\n".join(combined_context)

        # Build system prompt for multi-customer comparison
        company_name = self.company_config.full_name if self.company_config else "Haval H6"
        system_prompt = f"""You are the **{company_name} WhatsApp Conversation Analyst**.

**TASK**: Analyze and compare conversations from MULTIPLE customers.

**CUSTOMERS**: {', '.join([d['customer_name'] for d in all_customer_data if d['message_count'] > 0])}

**YOUR RESPONSE SHOULD**:
1. **Compare and contrast** the customers' conversations
2. **Highlight similarities** (common issues, sentiments, patterns)
3. **Highlight differences** (unique concerns, different experiences)
4. **Provide customer-specific insights** for each person
5. **Organize clearly** with customer names as sections

**RESPONSE FORMAT**:

## [STATS] Overview
Brief summary of all {len(customer_names)} customers and their conversations.

## 🔍 Individual Customer Summaries

### [USER] [Customer 1 Name]
- **Message Count**: X messages
- **Key Topics**: [Topics discussed]
- **Sentiment**: [Positive/Negative/Mixed]
- **Main Concerns**: [List]

### [USER] [Customer 2 Name]
- **Message Count**: X messages
- **Key Topics**: [Topics discussed]
- **Sentiment**: [Positive/Negative/Mixed]
- **Main Concerns**: [List]

[Continue for all customers...]

## [RETRY] Comparative Analysis
- **Common Issues**: What all customers mentioned
- **Unique Concerns**: What only specific customers mentioned
- **Sentiment Comparison**: How sentiments differ
- **Timeline Patterns**: Any timing differences

---
### 📋 References (MANDATORY)

You MUST include ALL messages for ALL customers in this exact format:
    pass

**[Customer 1 Name]'s Messages:**

**[WA-1]** [USER] [Customer Name] | [PHONE] [Contact] | [TAG] [Message Type] | [TIME] [Timestamp]
[MSG] *"[Full message content]"*

**[WA-2]** [USER] [Customer Name] | [PHONE] [Contact] | [TAG] [Message Type] | [TIME] [Timestamp]
[MSG] *"[Full message content]"*

[Continue for ALL messages from Customer 1...]

**[Customer 2 Name]'s Messages:**

**[WA-N]** [USER] [Customer Name] | [PHONE] [Contact] | [TAG] [Message Type] | [TIME] [Timestamp]
[MSG] *"[Full message content]"*

[Continue for ALL customers and ALL their messages...]

**CRITICAL**:
- Group messages by customer name
- Include EVERY SINGLE message (do not summarize or skip)
- Use sequential numbering across all customers ([WA-1], [WA-2], etc.)
- Show full message content in quotes

**CONVERSATION DATA**:
{combined_context_text}

**USER QUESTION**: "{question}"

Provide your comparative analysis with ALL messages referenced at the end:"""

        # Build messages for LLM
        messages_for_llm = [{"role": "system", "content": system_prompt}]
        if history:
            messages_for_llm.extend(history)
        messages_for_llm.append({"role": "user", "content": question})

        # Get temperature and max_tokens from mode-specific config
        config_component = "answer_generation_thinking" if thinking_mode else "answer_generation_non_thinking"
        answer_config = get_llm_config(config_component)
        llm_temperature = answer_config.temperature
        llm_max_tokens = answer_config.max_tokens
        print(f"  > Using {config_component}: temp={llm_temperature}, max_tokens={llm_max_tokens}")

        # Generate response
        resp = self.llm.generate(
            messages_for_llm,
            top_k=1,
            max_tokens=llm_max_tokens,
            temperature=llm_temperature,
        )

        answer_text = (resp.content or "").strip()

        if not answer_text:
            return f"I found conversations for {len([d for d in all_customer_data if d['message_count'] > 0])} customers but couldn't generate a comparison. Please try rephrasing your question."

        return answer_text

    def _fallback_answer(
        self,
        question: str,
        retrieved: List[RetrievedBlock],
    ) -> str:
        """
        Generate simple grounded answer when LLM returns nothing.

        Used when LLM hits safety/token limits.

        Args:
            question: User's question
            retrieved: Retrieved blocks

        Returns:
            Simple answer with citations
        """
        if not retrieved:
            # Dynamic fallback message based on company
            if self.company_id == "lucid":
                return (
                    "I couldn't retrieve enough Lucid Forum context to answer this "
                    "question."
                )
            else:
                return (
                    "I couldn't retrieve enough forum context to answer this "
                    "question."
                )

        lines: List[str] = [
            "The language model didn't return a full answer (likely due to "
            "length or safety limits), but from the forum context "
            "we can see the following points:"
        ]

        for rb in retrieved[:3]:
            b = rb.block

            if getattr(b, "summary", None):
                snippet = b.summary.strip()
            else:
                body_lines = [
                    ln
                    for ln in b.flattened_text.splitlines()
                    if ln.strip() and not ln.startswith("[BLOCK_ID=")
                ]
                # Strip simple "[user @ date]" header-style lines
                body_lines = [
                    ln
                    for ln in body_lines
                    if not (ln.startswith("[") and "@" in ln and "]" in ln)
                ]

                snippet = body_lines[0] if body_lines else b.flattened_text[:200]
                snippet = snippet.strip()
                if len(snippet) > 200:
                    snippet = snippet[:200] + "..."

            lines.append(f"- {snippet}")

        # Add references
        lines.append(build_citations(retrieved))
        return "\n".join(lines)

    def answer(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        thinking_mode: bool = False,
        source: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> str:
        """
        Main RAG entry point with conversational memory support.
        """
        try:
            return self._answer_impl(question, history, thinking_mode, source, session_id, user_id)
        except Exception as e:
            # Re-raise without notification (only API errors should be notified)
            raise
    
    def _answer_impl(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        thinking_mode: bool = False,
        source: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> str:
        """
        Main RAG entry point with conversational memory support.
        
        1. Check semantic cache for instant responses
        2. Classify query intent (context-dependent vs standalone)
        3. Reformulate query if context-dependent
        4. Classify query domain (in_domain, out_of_domain, small_talk)
        5. Optimize query into sub-queries with time windows and filters
        6. Retrieve relevant blocks from vector store
        7. Build system prompt with context
        8. Generate response with LLM
        9. Store response in semantic cache
        10. Append citations (if thinking mode)

        Args:
            question: User's query
            history: Chat history for context (last 4 messages recommended)
            thinking_mode: If True, return full analysis with charts/citations/suggestions.
                          If False, return clean statistics only (no emojis, no citations).
            source: Data source filter ("pakwheels" or "whatsapp")
            session_id: Session ID for semantic caching (optional but recommended)
            user_id: User ID for token tracking (optional)

        Returns:
            Generated answer with optional citations
        """
        # =============================================================================
        # TIMING TRACKING
        # =============================================================================
        total_start = time.time()

        # =============================================================================
        # DEBUG: Print vector_stores dictionary at the very start
        # =============================================================================
        # print(f"\n{'='*80}")
        # print(f"[DEBUG] RAG ENGINE INITIALIZATION CHECK")
        # print(f"{'='*80}")
        # print(f"self.vector_stores keys: {list(self.vector_stores.keys())}")
        for store_name, store_obj in self.vector_stores.items():
            if store_obj:
                num_blocks = len(store_obj.blocks_by_id) if hasattr(store_obj, 'blocks_by_id') else 0
                # print(f"  - {store_name}: {type(store_obj).__name__} with {num_blocks} blocks")
            else:
                pass
                # print(f"  - {store_name}: None")
        # print(f"{'='*80}\n")
        # =============================================================================

        # Clean logging - only essential info
        company_name = self.company_config.full_name if self.company_config else "Haval H6 (default)"
        mode_label = "Thinking" if thinking_mode else "Non-Thinking"
        # Determine source display - if source is None, check if we're in multi-source mode
        source_display = source if source else "multi-source"
        # print(f"\n{'='*70}")
        print(f"[RAG] Query: '{question[:60]}...'")
        print(f"[RAG] Mode: {mode_label} | Source: {source_display} | Company: {company_name}")
        if session_id:
            pass
            # print(f"[RAG] Session: {session_id[:8]}... | Cache: {'Enabled' if self.semantic_cache else 'Disabled'}")
        # print(f"{'='*70}")

        # =============================================================================
        # STEP 1: SEMANTIC CACHE CHECK (Zero-cost instant responses)
        # Priority: Redis cache → Fallback ChromaDB cache → Pipeline
        # =============================================================================
        cached_result = None

        # Try Redis cache first (primary)
        if self.redis_cache and session_id:
            cache_start = time.time()
            try:
                cached_result = self.redis_cache.get(question, session_id=session_id)
                cache_time = time.time() - cache_start

                if cached_result:
                    print(f"[RAG] 🎯 REDIS CACHE HIT! ({cache_time:.3f}s)")
                    return cached_result['response']
            except Exception as e:
                pass
                # print(f"[RAG] [WARNING]  Redis cache error: {e}")
                # print(f"[RAG] [RETRY] Trying fallback ChromaDB cache...")

        # Fallback to old ChromaDB cache if Redis unavailable or failed
        if not cached_result and self.semantic_cache and session_id:
            cache_start = time.time()
            try:
                cached_result = self.semantic_cache.get(question, session_id=session_id)
                cache_time = time.time() - cache_start

                if cached_result:
                    similarity = cached_result.get('similarity', 0)
                    original_q = cached_result.get('original_query', '')

                    print(f"[RAG] 🎯 FALLBACK CACHE HIT! (similarity: {similarity:.3f}, {cache_time:.3f}s)")
                    # print(f"[RAG] Original: '{original_q[:60]}...'")
                    # print(f"[RAG] Returning cached response (zero LLM cost)")

                    return cached_result['response']
            except Exception as e:
                pass
                # print(f"[RAG] [WARNING]  Fallback cache error: {e}")

        # No cache hit - proceed with pipeline
        if not cached_result:
            if not session_id:
                pass
                # print(f"[RAG] [WARNING]  No session ID provided - cache skipped")
            else:
                pass
                print(f"[RAG] [FAIL] Cache miss, proceeding with full RAG pipeline")

        # =============================================================================
        # MULTI-SOURCE RETRIEVAL: Query ALL available vector stores
        # =============================================================================
        # If source is specified, use only that store
        # If source is None or "all", query ALL available stores and combine results
        use_multi_source = (source is None or source == "all")
        
        if use_multi_source:
            # Get all active stores (those with indexed data)
            active_stores = {
                name: store for name, store in self.vector_stores.items()
                if store and hasattr(store, 'blocks_by_id') and len(store.blocks_by_id) > 0
            }
            print(f"[RAG] MULTI-SOURCE MODE: Querying {len(active_stores)} stores for {company_name}")
        else:
            # Single source mode (backward compatibility)
            store_key = source
            
            vector_store = self.vector_stores.get(store_key, self.vector_stores.get("pakwheels"))
            active_stores = {store_key or "pakwheels": vector_store} if vector_store else {}
            print(f"[RAG] SINGLE-SOURCE MODE: Querying {store_key or 'pakwheels'} for {company_name}")

        # =============================================================================
        # DEBUG: Print available vector stores
        # =============================================================================
        # print(f"\n{'='*80}")
        # print(f"[DEBUG] VECTOR STORE CONFIGURATION")
        # print(f"{'='*80}")
        print(f"Requested source: {source or 'all (multi-source)'}")
        print(f"Mode: {'MULTI-SOURCE' if use_multi_source else 'SINGLE-SOURCE'}")
        # print(f"Available vector stores: {list(self.vector_stores.keys())}")
        for store_name, store_obj in self.vector_stores.items():
            if store_obj:
                num_blocks = len(store_obj.blocks_by_id) if hasattr(store_obj, 'blocks_by_id') else 0
                is_active = store_name in active_stores
                status = "[OK] ACTIVE" if is_active else "[AVAILABLE]"
                # print(f"  - {store_name}: {num_blocks} blocks indexed ({status})")
            else:
                pass
                # print(f"  - {store_name}: Not initialized")
        # print(f"Active stores: {list(active_stores.keys())}")
        # print(f"{'='*80}\n")

        # Check if any vector stores are available
        if not active_stores:
            if use_multi_source:
                return f"No data sources have been indexed for {company_name} yet. Please index data from Forum, WhatsApp, or Reddit first."
            else:
                if source == "whatsapp":
                    source_label = "WhatsApp"
                elif source and "reddit" in source.lower():
                    source_label = "Reddit"
                else:
                    source_label = "Forum"
                return f"No {source_label} data has been indexed for {company_name} yet. Please index the data first or try a different data source."

        # NOTE: Date span queries are handled by LLM using metadata injected in system prompt
        # This is more robust than regex detection and handles all natural language variations

        # WhatsApp name filtering: Check if user is asking for specific customer(s)
        # Priority: LLM extraction (robust) → Regex fallback (backup)
        # Only extract names if querying WhatsApp source specifically
        customer_names = []
        query_type = None
        has_whatsapp_store = "whatsapp" in active_stores
        
        if source == "whatsapp" and has_whatsapp_store:
            try:
                # PRIMARY: LLM-based extraction (handles multi-customer, complex cases)
                extraction_llm = get_llm_for_component("query_classification", fallback_api_key=None)
                customer_names, query_type = extract_customer_names_llm(question, extraction_llm)

                if customer_names:
                    pass
                    # print(f"[RAG] LLM extraction: {len(customer_names)} customer(s) - {query_type}")
            except Exception as e:
                # print(f"[RAG] LLM extraction failed: {e}, falling back to regex")
                # FALLBACK: Regex-based extraction (simple, reliable backup)
                from .query_classification import extract_customer_name
                regex_name = extract_customer_name(question)
                if regex_name:
                    customer_names = [regex_name]
                    query_type = "SINGLE"
                    # print(f"[RAG] Regex fallback: 1 customer - SINGLE")

        # =============================================================================
        # MERGED CLASSIFIER: Domain + Format + Optimization in ONE LLM call
        # =============================================================================
        # Strategy:
        # 1. REGEX FIRST (instant, 0 tokens) - handles ~80% of domain classification
        # 2. If regex returns in_domain -> merged LLM for format + optimization only
        # 3. If regex returns out_of_domain/small_talk -> skip LLM entirely
        # 4. If regex returns None (ambiguous) -> full merged LLM (domain + format + optimization)

        available_sources = []
        if self.vector_stores.get("pakwheels"):
            available_sources.append("pakwheels")
        if self.vector_stores.get("whatsapp"):
            available_sources.append("whatsapp")
        if self.vector_stores.get("reddit"):
            available_sources.append("reddit")

        classification_start = time.time()
        classification_llm = get_llm_for_component("merged_classifier", fallback_api_key=None)

        # Run merged classifier (regex first, then LLM if needed)
        merged_result = classify_merged_with_regex_first(
            question=question,
            llm=classification_llm,
            company_id=self.company_id,
            source=source or "forum",
            data_sources=available_sources,
            chat_history=history
        )

        classification = merged_result["domain"]
        domain_source = merged_result["domain_source"]
        user_format_instruction = merged_result["format_instruction"]
        optimised_queries = merged_result["search_queries"]

        classification_time = time.time() - classification_start
        print(f"[RAG] Merged classifier: {classification.upper()} via {domain_source} ({classification_time:.2f}s)")

        # Get company name for responses
        company_name = self.company_config.full_name if self.company_config else self.company_id.title()

        # Handle small-talk immediately (no retrieval needed)
        if classification == 'small_talk':
            return f"Hello! How can I help you with {company_name}  Enterprise AI today?"

        # Handle out-of-domain immediately (no retrieval needed)
        if classification == 'out_of_domain':
            # Dynamic source label based on company and source
            if self.company_id == "lucid":
                source_label = "Lucid Forum discussions"
            elif source == "whatsapp":
                source_label = "WhatsApp customer interactions"
            elif source and "reddit" in source.lower():
                source_label = "Reddit discussions"
            else:
                source_label = "forum discussions"
            return (
                f"I'm here to help with {company_name} Enterprise AI from {source_label}. "
                f"I can analyze owner experiences, issues, and discussions about {company_name} vehicles. "
                f"Please ask about {company_name}-related topics!"
            )

        # If we reach here, query is in_domain - proceed with normal RAG flow

        # Special handling for WhatsApp customer-specific queries
        if source == "whatsapp" and query_type in ["SINGLE", "MULTI"]:
            if query_type == "SINGLE":
                # Single customer query
                # print(f"[RAG] Routing to single customer handler: '{customer_names[0]}'")
                return self._handle_whatsapp_customer_query(question, customer_names[0], history, thinking_mode)
            elif query_type == "MULTI":
                # Multi-customer query
                # print(f"[RAG] Routing to multi-customer handler: {customer_names}")
                return self._handle_whatsapp_multi_customer_query(question, customer_names, history, thinking_mode)
        # elif source == "whatsapp":
            pass
        #     print(f"[RAG] Using general WhatsApp RAG")  # Verbose

        # =============================================================================
        # DYNAMIC CONTEXTUAL ANCHORING - Intelligent Context Selection
        # =============================================================================
        # Instead of always using last 4 messages, use LLM to select relevant context
        selected_history = history  # Default: use full history
        context_type = None

        if history and len(history) > 0:
            from .context_selector import select_relevant_context

            try:
                # Use lightweight LLM for context selection
                context_selector_llm = get_llm_for_component("query_classification", fallback_api_key=None)

                context_selection = select_relevant_context(
                    query=question,
                    chat_history=history,
                    llm=context_selector_llm,
                    max_history_to_analyze=10
                )

                # Use selected messages instead of full history
                selected_history = context_selection["selected_messages"]
                context_type = context_selection["context_type"]

                print(f"[RAG] 🎯 Dynamic Context: Selected {context_selection['window_size']} message(s) ({context_type})")  # Verbose

            except Exception as e:
                print(f"[RAG] [WARNING] Context selection failed: {e}, using full history")
                selected_history = history

        # Convert search_queries from merged classifier to optimised format
        # Merged classifier now returns dicts with query + time windows
        is_broad = is_broad_insight_question(question)
        optimised = []
        for query_dict in optimised_queries:
            # Parse time windows if provided
            from .query_optimizer import parse_iso_or_none
            start_dt = parse_iso_or_none(query_dict.get("start_datetime"))
            end_dt = parse_iso_or_none(query_dict.get("end_datetime"))

            optimised.append({
                "query": query_dict.get("query", question),
                "start_dt": start_dt,
                "end_dt": end_dt,
                "variant_filter": None,  # Not extracted by merged classifier yet
                "sentiment_filter": None,
                "tags_filter": None,
            })

        # Log format detection
        if user_format_instruction:
            pass
            # print(f"[RAG] 🎯 User format detected: '{user_format_instruction}'")

        # Track original query for logging
        original_query = question

        # =============================================================================
        # PARALLEL LLM EXECUTION - Intent Classification & Citation Detection (Optional)
        # =============================================================================
        # NOTE: Domain, Format, and Optimization are already handled by merged classifier above
        parallel_start = time.time()

        # Build parallel task dictionary for remaining tasks
        parallel_tasks = {}

        # Prepare LLM clients only if needed
        if selected_history and len(selected_history) > 0:
            intent_llm = get_llm_for_component("query_classification", fallback_api_key=None)
            parallel_tasks["intent_classification"] = lambda: classify_query_intent(
                question, selected_history, intent_llm
            )

        # Add citation check and keyword extraction ONLY if thinking mode is enabled
        if thinking_mode:
            citation_llm = get_llm_for_component("query_classification", fallback_api_key=None)
            keyword_llm = get_llm_for_component("query_classification", fallback_api_key=None)

            parallel_tasks["citation_check"] = lambda: should_include_citations(question, citation_llm)
            parallel_tasks["keyword_extraction"] = lambda: extract_keywords_with_llm(
                question, keyword_llm, max_keywords=5, include_synonyms=True
            )

        # Execute parallel tasks if any
        if parallel_tasks:
            parallel_results = run_llm_calls_parallel(parallel_tasks)

            intent_classification = parallel_results.get("intent_classification", "standalone")
            needs_citations = parallel_results.get("citation_check", True)
            keyword_extraction_result = parallel_results.get("keyword_extraction", None)
        else:
            # No parallel tasks needed
            intent_classification = "standalone"
            needs_citations = True
            keyword_extraction_result = None

        parallel_time = time.time() - parallel_start

        # =============================================================================
        # STEP 2: QUERY REFORMULATION (if context-dependent)
        # =============================================================================
        # OPTIMIZATION: Skip reformulation for special context types
        if context_type in ["TOPIC_SWITCH", "NEW_TOPIC", "META_OP"]:
            print(f"[RAG] ⏭️ Skipping reformulation ({context_type})")
            if context_type in ["TOPIC_SWITCH", "NEW_TOPIC"]:
                intent_classification = "standalone"  # No context needed
            # For META_OP: Keep intent as context_dependent (we need compressed context),
            # but skip reformulation block (we use original query as-is)

        # Use selected_history from Dynamic Contextual Anchoring
        # CRITICAL: Skip reformulation for META_OP (operate on previous answer, not fetch new data)
        if intent_classification == "context_dependent" and selected_history and context_type != "META_OP":
            reformulation_start = time.time()
            # Use dedicated query_reformulation LLM (GPT-4o-mini for better context understanding)
            reformulator_llm = get_llm_for_component("query_reformulation", fallback_api_key=None)

            try:
                reformulated_query = reformulate_query(
                    question,
                    selected_history,
                    reformulator_llm,
                    company_name=company_name
                )

                # Update optimised queries to use reformulated query
                for item in optimised:
                    item["query"] = reformulated_query

                reformulation_time = time.time() - reformulation_start
                # print(f"[RAG] [RETRY] Query reformulated ({reformulation_time:.3f}s)")
                # print(f"[RAG]   Original: '{original_query}'")
                # print(f"[RAG]   Reformulated: '{reformulated_query}'")

                # Use reformulated query for all downstream operations
                question = reformulated_query

                # =============================================================================
                # CRITICAL: Extract names and keywords from REFORMULATED query
                # This ensures customer names mentioned in compressed context are captured
                # BUT: Skip for META_OP (user wants to operate on previous answer, not fetch new data)
                # =============================================================================
                # print(f"[RAG] 🔍 Extracting entities from reformulated query...")

                # 1. Extract customer names from reformulated query (WhatsApp only)
                # IMPORTANT: Skip if context_type is META_OP (summarize above, elaborate, etc.)
                if source == "whatsapp" and context_type != "META_OP":
                    try:
                        extraction_llm = get_llm_for_component("query_classification", fallback_api_key=None)
                        reformulated_names, reformulated_query_type = extract_customer_names_llm(
                            reformulated_query, extraction_llm
                        )

                        if reformulated_names:
                            print(f"[RAG] [OK] Found {len(reformulated_names)} customer name(s) in reformulated query:")
                            # print(f"[RAG]   Names: {reformulated_names}")
                            # print(f"[RAG]   Query type: {reformulated_query_type}")

                            # Update customer_names and query_type with reformulated results
                            # This ensures filtering works correctly
                            customer_names = reformulated_names
                            query_type = reformulated_query_type

                            # IMPORTANT: If we found names, route to WhatsApp customer handlers
                            if query_type in ["SINGLE", "MULTI"]:
                                pass
                                # print(f"[RAG] 🔀 Routing to WhatsApp customer handler with reformulated names")
                        else:
                            pass
                            # print(f"[RAG] No customer names found in reformulated query")

                    except Exception as e:
                        pass
                        # print(f"[RAG] Warning: Name extraction on reformulated query failed: {e}")
                elif source == "whatsapp" and context_type == "META_OP":
                    pass
                    print(f"[RAG] ⏭️ Skipping name extraction (META_OP: user wants to transform previous answer)")

                # 2. Extract keywords from reformulated query (thinking mode only)
                if thinking_mode:
                    try:
                        keyword_llm = get_llm_for_component("query_classification", fallback_api_key=None)
                        reformulated_keywords = extract_keywords_with_llm(
                            reformulated_query, keyword_llm, max_keywords=5, include_synonyms=True
                        )

                        if reformulated_keywords:
                            print(f"[RAG] [OK] Keywords from reformulated query: {reformulated_keywords}")

                            # Merge with original keywords (if any)
                            if keyword_extraction_result:
                                # Both are dicts with 'keywords', 'sentiment_filter', 'synonyms'
                                # Merge keyword lists, remove duplicates
                                original_kw = keyword_extraction_result.get('keywords', [])
                                reformulated_kw = reformulated_keywords.get('keywords', [])
                                combined_kw = list(set(original_kw + reformulated_kw))

                                # Merge synonyms
                                original_syn = keyword_extraction_result.get('synonyms', [])
                                reformulated_syn = reformulated_keywords.get('synonyms', [])
                                combined_syn = list(set(original_syn + reformulated_syn))

                                # Keep original sentiment filter (reformulated is likely same topic)
                                sentiment = keyword_extraction_result.get('sentiment_filter')

                                keyword_extraction_result = {
                                    'keywords': combined_kw,
                                    'sentiment_filter': sentiment,
                                    'synonyms': combined_syn
                                }
                                # print(f"[RAG] 🔀 Merged keywords: {combined_kw}")
                            else:
                                # Use reformulated keywords only
                                keyword_extraction_result = reformulated_keywords
                        else:
                            pass
                            # print(f"[RAG] No keywords extracted from reformulated query")

                    except Exception as e:
                        pass
                        # print(f"[RAG] Warning: Keyword extraction on reformulated query failed: {e}")

                # =============================================================================
                # ROUTING CHECKPOINT: If reformulated query revealed customer names, route now
                # =============================================================================
                if source == "whatsapp" and query_type in ["SINGLE", "MULTI"]:
                    # print(f"[RAG] 🔀 REFORMULATED query contains customer names, routing to WhatsApp handler")
                    if query_type == "SINGLE":
                        return self._handle_whatsapp_customer_query(question, customer_names[0], history, thinking_mode)
                    elif query_type == "MULTI":
                        return self._handle_whatsapp_multi_customer_query(question, customer_names, history, thinking_mode)

            except Exception as e:
                pass
                print(f"[RAG] Warning: Query reformulation failed: {e}, using original query")
        elif intent_classification == "standalone":
            pass
            print(f"[RAG] [OK] Standalone query (no reformulation needed)")

        # Log parallel execution results with timing
        if thinking_mode:
            citation_status = "NEEDS_CITATIONS" if needs_citations else "NO_CITATIONS"
            tasks_run = ["Optimization", "Intent Classification" if history else None, "Citation check", "Keyword extraction"]
            tasks_run = [t for t in tasks_run if t]
            print(f"[RAG] Parallel tasks: {' + '.join(tasks_run)} → {citation_status} ({parallel_time:.2f}s)")
        else:
            tasks_run = ["Optimization", "Intent Classification" if history else None]
            tasks_run = [t for t in tasks_run if t]
            print(f"[RAG] Parallel tasks: {' + '.join(tasks_run)} ({parallel_time:.2f}s)")

        all_retrieved: Dict[str, RetrievedBlock] = {}
        no_hits_msgs: List[str] = []

        # Dynamic top_k based on thinking_mode, query type, and time window
        is_statistical = is_statistical_query(question)

        if thinking_mode:
            # THINKING MODE: Higher top_k for detailed analysis
            if is_statistical:
                per_query_k = 500  # Get ALL data for accurate statistics
            else:
                per_query_k = 20   # Get diverse examples for context
        else:
            # NON-THINKING MODE: Focused retrieval
            if is_statistical:
                # Dynamic top_k based on time window size
                if 'last week' in question.lower() or 'yesterday' in question.lower():
                    per_query_k = 100  # Short time window
                elif 'last month' in question.lower() or 'this month' in question.lower():
                    per_query_k = 200  # Medium time window
                elif 'last year' in question.lower() or 'in 20' in question.lower():
                    per_query_k = 500  # Long time window, need all data
                else:
                    per_query_k = 300  # Default for statistical without time constraint
            else:
                per_query_k = 5    # Contextual queries need fewer examples

        # =============================================================================
        # DEBUG: Print retrieval configuration
        # =============================================================================
        # print(f"\n{'='*80}")
        # print(f"[DEBUG] RETRIEVAL CONFIGURATION")
        # print(f"{'='*80}")
        print(f"Thinking mode: {thinking_mode}")
        print(f"Is statistical query: {is_statistical}")
        # print(f"Per-query top_k: {per_query_k}")
        # print(f"Number of optimized queries: {len(optimised)}")
        print(f"Active stores to query: {list(active_stores.keys())}")
        if use_multi_source:
            # In multi-source mode, distribute top_k across stores
            per_store_k = max(5, per_query_k // len(active_stores)) if len(active_stores) > 1 else per_query_k
            # print(f"Per-store top_k: {per_store_k} (total target: {per_query_k})")
        else:
            per_store_k = per_query_k
            # print(f"Single-store top_k: {per_store_k}")
        # print(f"{'='*80}\n")

        # 2) Retrieve per optimized sub-query from ALL active stores
        for idx, item in enumerate(optimised, 1):
            q_text = (item.get("query") or "").strip()
            if not q_text:
                continue

            start_dt: Optional[datetime] = item.get("start_dt")
            end_dt: Optional[datetime] = item.get("end_dt")
            variant_filter = item.get("variant_filter")
            sentiment_filter = item.get("sentiment_filter")
            tags_filter = item.get("tags_filter")

            # =============================================================================
            # DEBUG: Print sub-query details
            # =============================================================================
            print(f"\n[DEBUG] Sub-query {idx}/{len(optimised)}:")
            print(f"  Query: {q_text}")
            print(f"  Time window: {start_dt} to {end_dt}")
            print(f"  Filters: variants={variant_filter}, sentiment={sentiment_filter}, tags={tags_filter}")

            # Query ALL active stores for this sub-query
            sub_query_results = []
            for store_name, vector_store in active_stores.items():
                print(f"\n  Querying {store_name} store...")
                
                retrieved = vector_store.query(
                    q_text,
                    top_k=per_store_k,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    variants=variant_filter,
                    sentiments=sentiment_filter,
                    tags=tags_filter,
                )

                # =============================================================================
                # FIX: Set source_type on blocks if missing (for backward compatibility)
                # =============================================================================
                for rb in retrieved:
                    if not hasattr(rb.block, 'source_type') or rb.block.source_type is None:
                        rb.block.source_type = store_name
                        # print(f"    [FIX] Set source_type={store_name} for block {rb.block.block_id}")

                # =============================================================================
                # DEBUG: Print retrieval results for this store
                # =============================================================================
                print(f"    Retrieved: {len(retrieved)} blocks from {store_name}")
                if retrieved:
                    print(f"    Top 3 blocks from {store_name}:")
                    for i, rb in enumerate(retrieved[:3], 1):
                        block_source = getattr(rb.block, 'source_type', store_name)
                        block_id = getattr(rb.block, 'block_id', 'N/A')
                        print(f"      {i}. Score: {rb.score:.4f}, Source: {block_source}, ID: {block_id}")
                
                sub_query_results.extend(retrieved)

            # Combine results from all stores for this sub-query
            print(f"\n  Total retrieved from ALL stores: {len(sub_query_results)} blocks")

            # If we explicitly had a time window and/or filters and got no hits,
            # surface that to the LLM so it doesn't fabricate.
            had_window = bool(start_dt or end_dt)
            had_filters = bool(variant_filter or sentiment_filter or tags_filter)

            if not sub_query_results and (had_window or had_filters):
                rng = format_range(start_dt, end_dt)
                filter_bits: List[str] = []
                if variant_filter:
                    filter_bits.append(f"variants={variant_filter}")
                if sentiment_filter:
                    filter_bits.append(f"sentiments={sentiment_filter}")
                if tags_filter:
                    filter_bits.append(f"tags={tags_filter}")
                filter_text = "; ".join(filter_bits) if filter_bits else "no extra filters"

                no_hits_msgs.append(
                    f"For sub-query '{q_text}' in the time window {rng} with {filter_text}, "
                    "no matching posts were found across any data source."
                )
                continue

            # Merge results, keeping highest score per block ID
            for rb in sub_query_results:
                bid = rb.block.block_id
                if bid not in all_retrieved or rb.score > all_retrieved[bid].score:
                    all_retrieved[bid] = rb

        retrieved_list = sorted(all_retrieved.values(), key=lambda r: r.score, reverse=True)

        # =============================================================================
        # DEBUG: Print retrieved chunks with source distribution
        # =============================================================================
        # print(f"\n{'='*80}")
        print(f"[DEBUG] RETRIEVED CHUNKS - Total: {len(retrieved_list)}")
        
        # Calculate source distribution
        source_counts = {}
        for rb in retrieved_list:
            source_type = getattr(rb.block, 'source_type', 'unknown')
            source_counts[source_type] = source_counts.get(source_type, 0) + 1
        
        print(f"[DEBUG] Source Distribution:")
        for source_name, count in sorted(source_counts.items()):
            percentage = (count / len(retrieved_list) * 100) if retrieved_list else 0
            # print(f"  - {source_name}: {count} blocks ({percentage:.1f}%)")
        # print(f"{'='*80}")
        
        # Show top 10 chunks
        for idx, rb in enumerate(retrieved_list[:10], 1):
            block = rb.block
            score = rb.score
            
            # Extract source information
            source_type = getattr(block, 'source_type', 'unknown')
            block_id = getattr(block, 'block_id', 'N/A')
            
            # Get text preview
            text_preview = ""
            if hasattr(block, 'root_post') and hasattr(block.root_post, 'cleaned_text'):
                text_preview = block.root_post.cleaned_text[:150]
            elif hasattr(block, 'text'):
                text_preview = block.text[:150]
            
            # print(f"\nChunk {idx}:")
            # print(f"  Score: {score:.4f}")
            print(f"  Source: {source_type}")
            # print(f"  Block ID: {block_id}")
            # print(f"  Text Preview: {text_preview}...")
        
        if len(retrieved_list) > 10:
            pass
            print(f"\n... and {len(retrieved_list) - 10} more chunks")
        # print(f"{'='*80}\n")

        if not retrieved_list:
            if no_hits_msgs:
                # Only filtered sub-queries, and all came back empty
                return (
                    "I couldn't find any forum posts in the requested time period(s) "
                    "or with the requested filters for this question.\n\n"
                    + "\n".join(f"- {m}" for m in no_hits_msgs)
                )
            return (
                "I don't have enough forum data to answer this question."
            )

        # 3) Check similarity strength to warn about weak context
        max_score = max(rb.score for rb in retrieved_list)
        low_similarity_flag = max_score < 0.55  # simple heuristic

        # 3.5) Build context with customer grouping for WhatsApp SEMANTIC queries
        # Use WhatsApp-specific context ONLY when:
        # - Explicitly querying WhatsApp source (not multi-source)
        # - This is a semantic query (SINGLE/MULTI customer queries are routed earlier)
        is_whatsapp_semantic = (source == "whatsapp" and not use_multi_source)

        if is_whatsapp_semantic:
            print(f"[RAG] Using customer-grouped context for WhatsApp semantic query")
            context_text = build_context_whatsapp_semantic(retrieved_list, self.max_block_chars)
        else:
            if use_multi_source:
                pass
                print(f"[RAG] Using standard multi-source context")
            else:
                pass
                print(f"[RAG] Using standard single-source context")
            context_text = build_context(retrieved_list, self.max_block_chars)

        # =============================================================================
        # DEBUG: Print combined context
        # =============================================================================
        # print(f"\n{'='*80}")
        print(f"[DEBUG] COMBINED CONTEXT - Length: {len(context_text)} chars")
        # print(f"{'='*80}")
        if use_multi_source:
            pass
            print(f"Context Type: Multi-Source (Standard)")
        elif is_whatsapp_semantic:
            pass
            print(f"Context Type: WhatsApp Semantic (Customer-Grouped)")
        else:
            pass
            print(f"Context Type: Single-Source (Standard)")
        print(f"\nFirst 1000 characters of context:")
        print(context_text[:1000])
        # print(f"\n... [truncated] ...")
        print(f"\nLast 500 characters of context:")
        print(context_text[-500:])
        # print(f"{'='*80}\n")

        # 4) Build retrieval notes section for the system prompt
        retrieval_notes_lines: List[str] = []

        # Only include "no hits" messages if we have SOME results
        if no_hits_msgs and retrieved_list:
            retrieval_notes_lines.append(
                "Note: Some sub-queries didn't find matches, but the context below contains "
                "related discussions that may help answer the question."
            )

        if low_similarity_flag:
            retrieval_notes_lines.append(
                "The retrieved blocks have only weak semantic similarity to the "
                "current question. If they do not seem clearly relevant, say that "
                "the forum does not directly cover this topic instead of inventing details."
            )

        # Track which sources returned data vs no data (multi-source mode)
        if use_multi_source:
            sources_with_data = set()
            sources_without_data = set()
            
            # Determine which sources have data in retrieved_list
            for rb in retrieved_list:
                source_type = getattr(rb.block, 'source_type', 'unknown')
                sources_with_data.add(source_type)
            
            # Find sources that were queried but returned nothing
            for store_name in active_stores.keys():
                if store_name not in sources_with_data:
                    sources_without_data.add(store_name)
            
            # Add note about missing sources
            if sources_without_data:
                source_labels = {
                    'pakwheels': 'Forum',
                    'whatsapp': 'WhatsApp customer interactions',
                    'reddit': 'Reddit discussions',
                    'reddit_lucid': 'Reddit discussions'
                }
                missing_sources = [source_labels.get(s, s) for s in sources_without_data]
                missing_text = ', '.join(missing_sources)
                
                retrieval_notes_lines.append(
                    f"IMPORTANT: No relevant data was found in {missing_text} for this query. "
                    f"You MUST explicitly mention in your answer that these sources had no data. "
                    f"For example: 'Note: No relevant discussions were found in {missing_text} regarding this topic.'"
                )
                # print(f"[RAG] [WARNING]  Sources without data: {missing_sources}")

        if retrieval_notes_lines:
            retrieval_notes_text = "\n- " + "\n- ".join(retrieval_notes_lines)
        else:
            retrieval_notes_text = "None."

        # 5) Detect source from retrieved blocks for prompt customization
        # In multi-source mode, determine actual source from retrieved blocks
        if use_multi_source:
            # Multi-source: Check what sources are actually in the retrieved blocks
            is_whatsapp_data = False
            effective_source = "all"  # Will be used in prompts
            print(f"[RAG] Multi-source mode: Context includes data from {list(active_stores.keys())}")
        else:
            # Single-source: Use the specified source
            is_whatsapp_data = (source and source.lower() == "whatsapp")
            effective_source = source or "forum"

        # 6) System prompt: Use appropriate prompt based on thinking_mode
        # Get company name for prompts (defaults to "Haval H6" for backward compatibility)
        company_name = self.company_config.full_name if self.company_config else "Haval H6"

        # Build source distribution summary for multi-source formatting
        source_distribution_info = None
        if use_multi_source and source_counts:
            # Create a summary of which sources have data
            source_labels = {
                'pakwheels': 'Forum',
                'whatsapp': 'WhatsApp Customer Interactions',
                'reddit': 'Reddit Discussions',
                'reddit_lucid': 'Reddit Discussions'
            }
            sources_with_blocks = [source_labels.get(s, s) for s in source_counts.keys() if s != 'unknown']
            if sources_with_blocks:
                source_distribution_info = {
                    'sources': sources_with_blocks,
                    'counts': source_counts
                }

        if thinking_mode:
            print(f"  > Using THINKING PROMPT (full analysis) for {company_name}")  # Verbose
            system_prompt = build_thinking_prompt(
                context_text, retrieval_notes_text, is_broad, is_whatsapp_data,
                company_name, needs_citations, user_format_instruction, effective_source,
                source_distribution_info
            )
        else:
            print(f"  > Using NON-THINKING PROMPT (clean stats) for {company_name}")  # Verbose
            system_prompt = build_non_thinking_prompt(
                context_text, retrieval_notes_text, is_broad, is_whatsapp_data,
                company_name, user_format_instruction, effective_source,
                source_distribution_info
            )

        # Inject date availability metadata into system prompt
        date_metadata = self._build_date_metadata_context()
        system_prompt = f"{system_prompt}\n\n{date_metadata}"
        # print(f"  > Date metadata injected")  # Verbose

        # 7) Build messages and call the LLM
        messages = messages_with_system(system_prompt, question, history)

        # =============================================================================
        # DEBUG: Print what's being passed to the LLM
        # =============================================================================
        # print(f"\n{'='*80}")
        print(f"[DEBUG] FINAL PROMPT BEING SENT TO LLM")
        # print(f"{'='*80}")
        # print(f"Number of messages: {len(messages)}")
        for idx, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            content_preview = content[:500] if len(content) > 500 else content
            # print(f"\nMessage {idx + 1} - Role: {role}")
            # print(f"Content length: {len(content)} chars")
            # print(f"Content preview:")
            # print(content_preview)
            if len(content) > 500:
                pass
                # print(f"... [truncated, full length: {len(content)} chars] ...")
                # print(f"\nLast 300 chars:")
                # print(content[-300:])
        # print(f"{'='*80}\n")

        # Get temperature and max_tokens from mode-specific config
        # This allows easy customization via config file without code changes
        config_component = "answer_generation_thinking" if thinking_mode else "answer_generation_non_thinking"
        answer_config = get_llm_config(config_component)
        llm_temperature = answer_config.temperature
        llm_max_tokens = answer_config.max_tokens

        print(f"[RAG] Using {config_component}: temp={llm_temperature}, max_tokens={llm_max_tokens}")

        # FINAL ANSWER GENERATION
        answer_start = time.time()
        resp = self.llm.generate(
            messages,
            max_tokens=llm_max_tokens,
            temperature=llm_temperature,
            user_id=user_id,
            company_id=self.company_id,
            operation='Chat Query - RAG'
        )
        answer_text = (resp.content or "").strip()
        answer_time = time.time() - answer_start
        print(f"[RAG] Final answer generated ({answer_time:.2f}s)")

        if not answer_text:
            answer_text = self._fallback_answer(question, retrieved_list)

        # 8) Append references (citations) at the very end
        # ONLY if thinking_mode is enabled and not a refusal response
        refusal_phrases = [
            "I'm here to help with Haval H6",
            "Please ask about Haval-related topics",
            "Hello! How can I help you"
        ]

        is_refusal = any(phrase in answer_text for phrase in refusal_phrases)

        # Only append citations and references if thinking mode is ON AND query needs citations
        if thinking_mode and not is_refusal and needs_citations:
            print(f"  > Building citations (thinking mode ON, not refusal)")
            print(f"     Retrieved blocks: {len(retrieved_list)}")

            # SAFETY NET: Filter citations by time window
            time_constraints = [(item.get("start_dt"), item.get("end_dt")) for item in optimised]

            # If ANY sub-query had time constraints, apply them to citations
            start_dts = [s for s, e in time_constraints if s]
            end_dts = [e for s, e in time_constraints if e]

            citation_start_dt = min(start_dts) if start_dts else None
            citation_end_dt = max(end_dts) if end_dts else None

            # DEBUG: Log extracted time constraints
            print(f"     [DEBUG] Extracted time window: {citation_start_dt} to {citation_end_dt}")

            # Filter retrieved_list by time window
            if citation_start_dt or citation_end_dt:
                time_filtered_blocks = []
                for rb in retrieved_list:
                    b_start = getattr(rb.block, "start_datetime", None)
                    b_end = getattr(rb.block, "end_datetime", None)

                    # Normalize timezones for comparison
                    if b_start and b_start.tzinfo is None:
                        b_start = b_start.replace(tzinfo=ZoneInfo("Asia/Karachi"))
                    elif b_start and citation_start_dt and b_start.tzinfo != citation_start_dt.tzinfo:
                        b_start = b_start.astimezone(ZoneInfo("Asia/Karachi"))

                    if b_end and b_end.tzinfo is None:
                        b_end = b_end.replace(tzinfo=ZoneInfo("Asia/Karachi"))
                    elif b_end and citation_start_dt and b_end.tzinfo != citation_start_dt.tzinfo:
                        b_end = b_end.astimezone(ZoneInfo("Asia/Karachi"))

                    # Skip blocks outside time window
                    if citation_end_dt and b_start and b_start > citation_end_dt:
                        continue
                    if citation_start_dt and b_end and b_end < citation_start_dt:
                        continue

                    time_filtered_blocks.append(rb)

                print(f"     Time filtering: {len(retrieved_list)} → {len(time_filtered_blocks)} blocks")
                citation_blocks = time_filtered_blocks
            else:
                print(f"     No time constraints, using all {len(retrieved_list)} blocks")
                citation_blocks = retrieved_list

            # LLM-BASED KEYWORD FILTERING: Robust handling of edge cases
            # Uses LLM-extracted keywords + synonyms + sentiment filter
            citation_threshold = 0.4  # Default threshold

            if keyword_extraction_result:
                # Extract keyword data from LLM result
                keywords = keyword_extraction_result.get('keywords', [])
                synonyms = keyword_extraction_result.get('synonyms', [])
                sentiment_filter = keyword_extraction_result.get('sentiment_filter')

                # print(f"     [LLM Keyword Extraction]")
                # print(f"       Keywords: {keywords}")
                if synonyms:
                    pass
                    # print(f"       Synonyms: {synonyms}")
                if sentiment_filter:
                    pass
                    # print(f"       Sentiment: {sentiment_filter}")

                # Apply keyword filtering using LLM-extracted keywords
                if keywords or synonyms or sentiment_filter:
                    relevant_blocks = apply_keyword_filter(
                        citation_blocks,
                        keywords=keywords,
                        synonyms=synonyms,
                        sentiment_filter=sentiment_filter
                    )

                    if relevant_blocks:
                        # print(f"     Filtered citations by LLM keywords: {len(citation_blocks)} → {len(relevant_blocks)} blocks")
                        # DEBUG: Show which customers/posts are in filtered blocks
                        if is_whatsapp_semantic:
                            filtered_customers = [rb.block.root_post.username for rb in relevant_blocks[:5]]
                            # print(f"     DEBUG: Top 5 filtered customers: {filtered_customers}")
                        citation_blocks = relevant_blocks
                        # Lower threshold for keyword-filtered blocks (keyword match is already a strong signal)
                        citation_threshold = 0.1
                        print(f"     Using similarity threshold: 0.1 (keyword-filtered blocks)")
                    else:
                        print(f"     No keyword-matching blocks found, using all retrieved blocks")
                        # Use standard threshold for semantic-only filtering
                        citation_threshold = 0.4
                        print(f"     Using similarity threshold: 0.4 (thinking mode - comprehensive analysis)")
                else:
                    # No keywords extracted (broad query like "What are the main issues?")
                    print(f"     No specific keywords extracted, using semantic-only filtering")
                    citation_threshold = 0.4
                    print(f"     Using similarity threshold: 0.4 (thinking mode - comprehensive analysis)")
            else:
                # Fallback if keyword extraction failed or wasn't run
                print(f"     Keyword extraction not available, using semantic-only filtering")
                citation_threshold = 0.4
                print(f"     Using similarity threshold: 0.4 (thinking mode - comprehensive analysis)")

            # Get company-specific base URL for citations
            if self.company_id == "lucid":
                # For Lucid, use Lucid Forum base URL
                lucid_base_url = "https://lucidowners.com"
                pakwheels_base_url = None
            else:
                pakwheels_base_url = self.company_config.pakwheels_url if self.company_config else "https://www.pakwheels.com/forums/t/haval-h6-dedicated-discussion-owner-fan-club-thread/2198325"
                lucid_base_url = "https://lucidowners.com"

            # Dynamic max_refs based on how many relevant blocks we have
            max_refs_dynamic = min(len(citation_blocks), 20) if citation_blocks else 10
            # print(f"     Max refs (dynamic): {max_refs_dynamic}")

            refs = build_citations(
                citation_blocks,
                max_refs=max_refs_dynamic,
                similarity_threshold=citation_threshold,
                citation_start_dt=citation_start_dt,
                citation_end_dt=citation_end_dt,
                pakwheels_base_url=pakwheels_base_url,
                lucid_base_url=lucid_base_url
            )

            # Fallback: If no citations pass threshold, show top 5 anyway
            if not refs and citation_blocks:
                print(f"     No citations with threshold 0.4, showing top 5 anyway (thinking mode)")
                # DEBUG: Show which customers are being used in fallback
                fallback_customers = [rb.block.root_post.username for rb in citation_blocks[:5]]
                fallback_scores = [rb.score for rb in citation_blocks[:5]]
                # print(f"     DEBUG: Fallback customers: {fallback_customers}")
                # print(f"     DEBUG: Fallback scores: {fallback_scores}")
                refs = build_citations(
                    citation_blocks,
                    max_refs=5,
                    similarity_threshold=0.0,
                    citation_start_dt=citation_start_dt,
                    citation_end_dt=citation_end_dt,
                    pakwheels_base_url=pakwheels_base_url,
                    lucid_base_url=lucid_base_url
                )

            if refs:
                # print(f"     Citations generated: YES ({len(refs)} chars)")
                answer_with_refs = answer_text.rstrip() + refs

                # Store in cache before returning (try Redis first, then fallback)
                if session_id:
                    cache_metadata = {
                        "source": source or "forum",
                        "thinking_mode": thinking_mode,
                    }

                    # Try Redis cache first
                    if self.redis_cache:
                        try:
                            self.redis_cache.set(
                                query=original_query,
                                response=answer_with_refs,
                                session_id=session_id,
                                cache_type="session",
                                metadata=cache_metadata
                            )
                        except Exception as e:
                            # print(f"[RAG] [WARNING]  Redis cache store failed: {e}")

                            # Fallback to old cache
                            if self.semantic_cache:
                                try:
                                    self.semantic_cache.set(
                                        query=original_query,
                                        response=answer_with_refs,
                                        session_id=session_id,
                                        cache_type="session",
                                        metadata=cache_metadata
                                    )
                                    print(f"[RAG] [SAVE] Stored in fallback cache")
                                except Exception as e2:
                                    pass
                                    # print(f"[RAG] [WARNING]  Fallback cache store failed: {e2}")
                    elif self.semantic_cache:
                        # No Redis cache, use fallback directly
                        try:
                            self.semantic_cache.set(
                                query=original_query,
                                response=answer_with_refs,
                                session_id=session_id,
                                cache_type="session",
                                metadata=cache_metadata
                            )
                            print(f"[RAG] [SAVE] Stored in fallback cache")
                        except Exception as e:
                            pass
                            # print(f"[RAG] [WARNING]  Cache store failed: {e}")

                return answer_with_refs
            # else:
            #     print(f"     Citations generated: NO (no retrieved blocks)")  # Verbose
        # else:
        #     if not thinking_mode:
            pass
        #         print(f"  > Skipping citations (thinking mode OFF)")  # Verbose
        #     elif is_refusal:
            pass
        #         print(f"  > Skipping citations (refusal response)")  # Verbose

        # =============================================================================
        # STEP 3: STORE RESPONSE IN SEMANTIC CACHE (Redis → Fallback)
        # =============================================================================
        if session_id and answer_text:
            cache_metadata = {
                "source": source or "forum",
                "thinking_mode": thinking_mode,
            }

            # Try Redis cache first
            if self.redis_cache:
                try:
                    self.redis_cache.set(
                        query=original_query,
                        response=answer_text,
                        session_id=session_id,
                        cache_type="session",
                        metadata=cache_metadata
                    )
                except Exception as e:
                    # print(f"[RAG] [WARNING]  Redis cache store failed: {e}")

                    # Fallback to old cache
                    if self.semantic_cache:
                        try:
                            self.semantic_cache.set(
                                query=original_query,
                                response=answer_text,
                                session_id=session_id,
                                cache_type="session",
                                metadata=cache_metadata
                            )
                            print(f"[RAG] [SAVE] Stored in fallback cache (session: {session_id[:8]}...)")
                        except Exception as e2:
                            pass
                            # print(f"[RAG] [WARNING]  Fallback cache store failed: {e2}")
            elif self.semantic_cache:
                # No Redis cache, use fallback directly
                try:
                    self.semantic_cache.set(
                        query=original_query,
                        response=answer_text,
                        session_id=session_id,
                        cache_type="session",
                        metadata=cache_metadata
                    )
                    print(f"[RAG] [SAVE] Stored in fallback cache (session: {session_id[:8]}...)")
                except Exception as e:
                    pass
                    # print(f"[RAG] [WARNING]  Cache store failed: {e}")

        # =============================================================================
        # TOTAL TIME SUMMARY
        # =============================================================================
        total_time = time.time() - total_start
        # print(f"{'='*70}")
        # print(f"[RAG] TOTAL TIME: {total_time:.2f}s")
        print(f"  - Merged classifier (domain+format+optim): {classification_time:.2f}s")
        if parallel_time > 0:
            pass
            # print(f"  - Optional tasks (intent+citations): {parallel_time:.2f}s")
        print(f"  - Final answer generation: {answer_time:.2f}s")
        # print(f"{'='*70}\n")

        return answer_text