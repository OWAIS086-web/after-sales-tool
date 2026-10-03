# ai/rag_engine/query_classification.py
"""
Query Classification Module

Handles classification and detection of different query types:
- Domain classification (in_domain, out_of_domain, small_talk)
- Query type detection (statistical, broad insight)
- WhatsApp customer name extraction

**OPTIMIZATION**: Uses regex-first classification to save tokens:
- Try regex patterns first (instant, 0 tokens)
- Fallback to LLM only if regex returns None (ambiguous cases)
"""

from __future__ import annotations
from typing import Optional, List, Dict
from ai.llm_client import BaseLLMClient
from ai.rag_engine.regex_classifiers import classify_query_domain_regex


def classify_query_domain(
    llm: BaseLLMClient,
    question: str,
    company_id: str = "haval",
    data_sources: list = None,
    chat_history: Optional[List[Dict[str, str]]] = None,
    return_source: bool = False
) -> str | tuple:
    """
    Classify user query into: 'in_domain', 'out_of_domain', or 'small_talk'.

    **OPTIMIZATION**: Uses regex-first approach to save tokens:
    1. Try regex patterns first (instant, 0 tokens) - covers ~80% of queries
    2. Fallback to LLM only if regex returns None (ambiguous cases)

    **CONTEXT-AWARE**: If chat history shows recent in-domain conversation,
    treat vague follow-ups (like "summarize point 3 above") as in-domain.

    Args:
        llm: LLM client for classification
        question: User query to classify
        company_id: Company identifier (e.g., "haval", "kia", "toyota")
        data_sources: Available data sources (e.g., ["pakwheels", "whatsapp"])
        chat_history: Recent conversation history (last 2-4 messages) for context
        return_source: If True, return (classification, source) tuple

    Returns:
        'in_domain' - Query about company vehicles/services, proceed with RAG
        'out_of_domain' - Unrelated query, refuse immediately
        'small_talk' - Greeting/thanks, respond politely

        If return_source=True, returns (classification, source) where source is "regex" or "llm"
    """
    # =========================================================================
    # OPTIMIZATION: Try regex first (0 tokens)
    # =========================================================================
    mode = "auto"
    if data_sources:
        if "pakwheels" in data_sources or "Pakwheels" in data_sources:
            mode = "pakwheels"
        elif "whatsapp" in data_sources or "Whatsapp" in data_sources:
            mode = "whatsapp"

    regex_result = classify_query_domain_regex(
        question=question,
        company_id=company_id,
        mode=mode
    )

    # If regex found a clear answer, use it (instant, saves ~110 tokens)
    if regex_result is not None:
        print(f"  [Domain Classification] REGEX HIT -> {regex_result.upper()} (0 tokens)")
        if return_source:
            return regex_result, "regex"
        return regex_result

    print(f"  [Domain Classification] Regex returned None -> LLM fallback")

    # =========================================================================
    # LLM FALLBACK: For ambiguous cases that regex couldn't handle
    # =========================================================================
    from config import get_company_config

    # Get company configuration
    try:
        company_config = get_company_config(company_id)
        company_name = company_config.full_name
        variants = company_config.variants if hasattr(company_config, 'variants') and company_config.variants else []
        # print(f"  [Domain Classification] Company: {company_name}")  # Verbose
    except Exception as e:
        # print(f"  [Domain Classification] Error getting company config: {e}")  # Verbose
        company_name = company_id.title()
        variants = []

    # Build data source context
    if data_sources is None:
        data_sources = []

    sources_context = ""
    if "pakwheels" in data_sources or "Pakwheels" in data_sources:
        sources_context += "\n   • Forum discussions (owner experiences, reviews, complaints)"
    if "whatsapp" in data_sources or "Whatsapp" in data_sources:
        sources_context += "\n   • WhatsApp customer service conversations (bookings, delivery, support)"

    # Build variant examples
    variant_examples = ", ".join(variants[:5]) if variants else "various models"

    # Build history context (last 2 messages only - just enough for follow-up detection)
    history_context = ""
    if chat_history and len(chat_history) > 0:
        recent = chat_history[-2:]  # Last 2 messages (1 round)
        history_lines = []
        for msg in recent:
            role = msg.get("role", "").capitalize()
            content = msg.get("content", "")[:100]  # Truncate to 100 chars
            history_lines.append(f"{role}: {content}")
        history_context = f"""

**RECENT CONVERSATION**:
{chr(10).join(history_lines)}

**CONTEXT-AWARE RULES** (for follow-up questions):
- If PREVIOUS messages were about {company_name} or automotive topics:
  → AND current query uses reference terms ("above", "point", "it", "that", "summarize", "tell me more") or it feels like he/she is referring to previous chat
  → THEN classify as **in_domain** ✅ (it's a follow-up to an in-domain conversation)

- If PREVIOUS messages were out-of-domain:
  → AND current query is unrelated to {company_name}
  → THEN classify as **out_of_domain** ❌

**Examples**:
Previous: "Haval H6 problems on the forum" [in_domain]
Current: "Summarize point 3 above" → **in_domain** ✅ (follow-up)

Previous: "Haval H6 price" [in_domain]
Current: "What's the weather in Karachi?" → **out_of_domain** ❌ (topic switch)
"""

    classification_prompt = f"""You are a query classifier for a {company_name} customer support chatbot in Pakistan.

Classify this user query into ONE category:

CATEGORIES:
1. "in_domain" - Questions about:
   • **{company_name} vehicles** ({variant_examples})
   • **Customer issues**: complaints, problems, concerns, breakdowns
   • **Service & Support**: delivery, warranty, dealership, after-sales, booking
   • **Vehicle features**: specifications, performance, fuel economy, build quality
   • **Comparisons**: vs other brands (Toyota, Honda, Suzuki, etc.)
   • **Owner experiences**: reviews, ownership costs, reliability, resale value
   • **Data questions**: "what problems do people face?", "common issues", "date span of data"{sources_context}
   • **Follow-up questions**: If recent conversation was about {company_name}, treat vague follow-ups as in_domain

2. "out_of_domain" - Unrelated topics:
   • Essays, homework, creative writing
   • Entertainment, movies, sports
   • General knowledge (history, science, geography)
   • Cooking, recipes, health tips
   • Other car brands WITHOUT comparison to {company_name}

3. "small_talk" - Greetings, thanks, casual conversation:
   • "Hello", "Hi", "Thank you", "Thanks"
   • "How are you?", "Good morning"

**CRITICAL RULES**:
- If query mentions **{company_name}** → in_domain
- If query mentions **ANY vehicle brand** (Kia, Toyota, Haval, Honda, Suzuki) → in_domain
- If query mentions **WhatsApp, Reddit, forum, chat, or specific person's name** → in_domain
- If query about **automotive topics** → in_domain
- If recent conversation was in_domain AND current query has reference terms → in_domain{history_context}

USER QUERY: "{question}"

Respond with ONLY ONE WORD (lowercase): in_domain, out_of_domain, or small_talk"""

    messages = [{"role": "user", "content": classification_prompt}]

    try:
        response = llm.generate(messages, max_tokens=10, temperature=0.0)
        classification = response.content.strip().lower()

        # print(f"  [Domain Classification] Query: '{question[:50]}...' → {classification.upper()}")  # Verbose

        if classification in ['in_domain', 'out_of_domain', 'small_talk']:
            if return_source:
                return classification, "llm"
            return classification
        if return_source:
            return 'in_domain', "llm"
        return 'in_domain'  # Safe fallback
    except Exception as e:
        # print(f"  [Domain Classification] Error: {e} → Defaulting to IN_DOMAIN")  # Verbose
        if return_source:
            return 'in_domain', "llm"
        return 'in_domain'  # Avoid blocking legitimate queries


def is_broad_insight_question(question: str) -> bool:
    """
    Detect generic insight questions about patterns/trends.

    Examples: "what problems are there", "what are people saying"
    """
    q = question.lower()
    keywords = [
        "what problems", "what issues", "what concerns",
        "common problems", "common issues", "common complaints",
        "main problems", "main issues", "typical problems",
        "what are people saying", "what are owners saying",
        "what do owners think", "overall feedback",
        "general feedback", "pros and cons",
    ]
    return any(k in q for k in keywords)


def is_statistical_query(question: str) -> bool:
    """
    Detect if query requires statistical analysis (counting, aggregation).
    Statistical queries need higher top_k.

    Examples: "How many brake issues?", "Top 10 problems"
    """
    q = question.lower()
    keywords = [
        "how many", "count", "number of", "total",
        "statistics", "stat", "distribution", "breakdown",
        "top ", "most common", "frequency",
        "percentage", "ratio", "comparison", "vs ", "versus",
    ]
    return any(k in q for k in keywords)


def should_include_citations(question: str, llm: BaseLLMClient) -> bool:
    """
    Detect if query requires citations/references in the response.

    Uses LLM to determine if the user is asking for:
    - Specific examples/lists with details (needs citations) ✅
    - Statistics/metrics/advice/synthesis (no citations needed) ❌

    Examples NEEDING citations (wants specific examples):
    - "What are the top 10 complaints?" ✅ (wants list with details)
    - "Show me customer feedback about brakes" ✅ (wants to read actual feedback)
    - "Give me examples of issues owners face" ✅ (explicitly wants examples)

    Examples NOT needing citations (wants metrics or synthesis):
    - "What are average daily messages about H6?" ❌ (wants metric/number)
    - "How many total conversations are there?" ❌ (wants count)
    - "What percentage complain about brakes?" ❌ (wants statistic)
    - "Summarize the above in 250 words" ❌ (wants synthesis)
    - "Give me advice on handling complaints" ❌ (wants advice)
    - "What insights can you provide?" ❌ (wants analysis)

    Args:
        question: User query
        llm: LLM client for classification

    Returns:
        True if citations should be included, False otherwise
    """
    classification_prompt = f"""You are analyzing whether a user query requires citations/references in the response.

Focus on the PRIMARY INTENT of the query, not just keywords.

Classify this query into ONE category:

1. "needs_citations" - Query wants to SEE/REVIEW SPECIFIC EXAMPLES of raw data or customer feedback:
   • "What are the top 10 problems?" → User wants to SEE the actual list with examples
   • "Show me customer complaints/ discussions about X" → User wants to READ actual complaints/ discussion of a specific topic
   • "What issues do owners report?" → User wants to SEE specific issue descriptions
   • "Give me examples of brake complaints" → User explicitly wants EXAMPLES
   • "Show me feedback/ discussion about engine transmission issues" → User wants to READ actual feedback on that specific topic
   • **KEY**: User wants to see SPECIFIC ITEMS, EXAMPLES, or LIST OF THINGS with details

2. "no_citations" - Query wants METRICS/STATISTICS/SUMMARIES/ADVICE (NOT specific examples):

   a) STATISTICAL/QUANTITATIVE queries (just need numbers, not examples):
      • "What are average daily messages about H6?" → User wants METRIC (a number), not message examples
      • "How many conversations are there?" → User wants COUNT (a number), not conversation list
      • "What's the total number of messages?" → User wants AGGREGATE STAT, not message details
      • "What percentage of users complain about X?" → User wants PERCENTAGE, not complaint examples

   b) SYNTHESIS/ADVICE queries (interpretation, not data):
      • "Summarize the above in X words" → User wants SYNTHESIS, not sources
      • "Give me advice on handling complaints" → User wants ADVICE, not data retrieval
      • "What after sales advice can you give based on sentiments?" → User wants RECOMMENDATIONS
      • "What should we do based on feedback?" → User wants ACTION ITEMS
      • "Explain what this data means" → User wants INTERPRETATION
      • "What insights can you provide?" → User wants ANALYSIS, not data dump

   c) REPORT/DOCUMENT creation (formatted output, not raw data):
      • "Write a report about customer satisfaction" → User wants DOCUMENT, not data citations
      • "Create a summary of Q4 feedback" → User wants FORMATTED SUMMARY

**CRITICAL DECISION RULES**:

1. **METRIC/STAT QUERIES** → no_citations
   - If the answer is primarily A NUMBER, COUNT, PERCENTAGE, or AGGREGATE STATISTIC → no_citations
   - Keywords: "how many", "total number", "average", "count", "percentage", "rate"
   - User wants: **Single number or summary stats**, NOT a list of examples

2. **EXAMPLE/LIST QUERIES** → needs_citations
   - If the answer requires showing SPECIFIC EXAMPLES, ITEMS, or LIST OF THINGS → needs_citations
   - Keywords: "show me", "what are the top", "give me examples", "list the problems", "what issues"
   - User wants: **Actual data points with details**, NOT just aggregated numbers

3. **ADVICE/SYNTHESIS QUERIES** → no_citations
   - If the answer is RECOMMENDATIONS, ADVICE, INTERPRETATION → no_citations
   - Keywords: "advice", "recommend", "should we", "how to", "insights", "based on"
   - User wants: **Guidance or synthesis**, NOT raw data

**EXAMPLES WITH EXPLANATIONS**:

✅ no_citations (METRICS):
- "What are average daily messages?" → Wants NUMBER (e.g., "23.5 messages/day"), not message list
- "How many conversations exist?" → Wants COUNT (e.g., "1,245 conversations"), not conversation details
- "Total messages about H6?" → Wants AGGREGATE (e.g., "3,402 messages"), not message examples

❌ needs_citations (EXAMPLES):
- "What are the top 10 problems?" → Wants ACTUAL LIST with problem descriptions
- "Show me brake complaints" → Wants to READ actual complaint text
- "What issues do owners report?" → Wants SPECIFIC ISSUES with examples

✅ no_citations (ADVICE/SYNTHESIS):
- "What should we do about the problems?" → Wants ACTION ADVICE
- "Give me insights from the data" → Wants ANALYSIS, not data dump
- "Summarize feedback in 200 words" → Wants SYNTHESIZED SUMMARY

USER QUERY: "{question}"

Respond with ONLY ONE WORD (lowercase): needs_citations or no_citations"""

    messages = [{"role": "user", "content": classification_prompt}]

    try:
        response = llm.generate(messages, max_tokens=10, temperature=0.0)
        classification = response.content.strip().lower()

        # print(f"  [Citation Check] Query: '{question[:50]}...' → {classification.upper()}")  # Verbose

        if classification == "no_citations":
            return False
        return True  # Default to including citations for safety
    except Exception as e:
        # print(f"  [Citation Check] Error: {e} → Defaulting to INCLUDE citations")  # Verbose
        return True  # Safe fallback - include citations if unsure


def extract_customer_name(question: str) -> Optional[str]:
    """
    BULLETPROOF customer name extraction for WhatsApp queries.

    Handles ANY natural language style:
    - "Show me Luqman's chat"
    - "What did Ahmed say"
    - "Show me the summary of chat with Luqman"
    - "Between Luqman and Haval" (extracts Luqman, ignores Haval)
    - "Show me Mrs. Fatima Khan's chat" (preserves full name with title)
    - "Ali123" (preserves exact name as stored in DB)

    Returns:
        Extracted customer name (preserves original format from query) or None
    """
    import re

    q = question.lower().strip()

    # Terms that are NEVER customer names
    ignored_terms = {
        'haval', 'gwm', 'sazgar', 'tank', 'ora', 'poer', 'he', 'phev', 'jolion', 'ice',
        'pakwheels', 'pakistan', 'karachi', 'lahore', 'islamabad',
        'whatsapp', 'whats app', 'wa', 'bot', 'ai', 'system', 'database', 'app',
        'after sales', 'sales', 'service', 'support', 'agent', 'admin', 'manager',
        'representative', 'customer service', 'dealer', 'dealership', 'company',
        'customer', 'user', 'person', 'someone', 'anyone', 'everyone', 'nobody'
    }

    chat_words = r'(?:conversation|chat|messages?|talk|history|logs?|details|transcripts?|summary|summaries)'

    # Comprehensive patterns (ordered by priority)
    patterns = [
        # Nested: "summary of chat with Luqman"
        rf'{chat_words}\s+(?:of|with)\s+{chat_words}\s+(?:of|with|from|about)\s+([a-zA-Z][a-zA-Z0-9\s]+)',
        rf'{chat_words}\s+(?:of|from)\s+([a-zA-Z][a-zA-Z0-9\s]+?)\'s\s+{chat_words}',
        # Dual: "between Luqman and Haval"
        r'(?:between|with)\s+([a-zA-Z0-9\s]+?)\s+(?:and|&)\s+([a-zA-Z0-9\s]+)',
        rf'([a-zA-Z0-9\s]+?)\s+(?:and|&)\s+([a-zA-Z0-9\s]+?)\s+{chat_words}',
        # Possessive: "Luqman's chat"
        rf'([a-zA-Z][a-zA-Z0-9\s]+?)\'s\s+{chat_words}',
        rf'([a-zA-Z][a-zA-Z0-9\s]{1,20}?)\'s(?:\s|$)',
        # Actions: "what did Luqman say"
        r'what\s+did\s+([a-zA-Z0-9\s]+?)\s+(?:say|tell|ask|write)',
        r'did\s+([a-zA-Z][a-zA-Z0-9\s]+?)\s+(?:say|tell|ask|write|mention)',
        r'(?:can|could|will)\s+you\s+(?:show|tell)\s+(?:me\s+)?(?:what\s+)?([a-zA-Z][a-zA-Z0-9\s]+?)\s+(?:said|told|wrote)',
        # Generic: "chat with Luqman"
        rf'{chat_words}\s+(?:of|with|from|about|for)\s+([a-zA-Z][a-zA-Z0-9\s]+)',
        # Commands: "show me Luqman"
        rf'(?:show|give|get|pull|find|search|fetch|retrieve)\s+(?:me\s+)?(?:all\s+)?(?:the\s+)?(?:full\s+)?(?:complete\s+)?{chat_words}?\s+(?:of\s+)?{chat_words}?\s+(?:of|with|from|about|for)\s+([a-zA-Z][a-zA-Z0-9\s]+)',
        rf'(?:show|give|get|pull|find|search|fetch|retrieve)\s+(?:me\s+)?(?:the\s+)?([a-zA-Z][a-zA-Z0-9\s]+?)(?:\s+{chat_words}|\s*$)',
        # "tell me about Luqman"
        r'(?:tell|talk)\s+(?:me\s+)?about\s+([a-zA-Z][a-zA-Z0-9\s]+)',
        r'(?:information|info|data|details)\s+(?:on|about|for)\s+([a-zA-Z][a-zA-Z0-9\s]+)',
        # "I want to see Luqman"
        rf'(?:i\s+)?(?:want|need|would like)\s+(?:to\s+)?(?:see|know|view|check)\s+(?:what\s+)?([a-zA-Z][a-zA-Z0-9\s]+?)(?:\s+{chat_words}|\s+said|\s*$)',
        # Direct: "Luqman conversation"
        rf'([a-zA-Z][a-zA-Z0-9\s]{1,15}?)\s+{chat_words}',
    ]

    candidates = []

    # Execute pattern matching
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            candidates.extend([g.strip() for g in match.groups() if g])
            if len(match.groups()) > 1:
                break

    # Filter and validate
    for candidate in candidates:
        clean_cand = candidate.lower()

        # Remove "and Haval", "with Mrs Waqas" -> keep the name part, not the chat word
        # Chat words that might appear before the name
        chat_word_list = ['conversation', 'chat', 'message', 'messages', 'talk', 'history',
                         'log', 'logs', 'detail', 'details', 'transcript', 'transcripts',
                         'summary', 'summaries']

        for splitter in [' and ', ' & ', ' with ', ' about ', ' for ']:
            if splitter in clean_cand:
                parts = clean_cand.split(splitter)
                # If first part is a chat word, take second part (e.g., "conversation with Mrs Waqas" -> "Mrs Waqas")
                if parts[0].strip() in chat_word_list:
                    clean_cand = parts[1].strip() if len(parts) > 1 else parts[0]
                    candidate = candidate.split(splitter)[1].strip() if len(candidate.split(splitter)) > 1 else candidate.split(splitter)[0]
                else:
                    # Otherwise take first part (e.g., "Ahmed and Haval" -> "Ahmed")
                    clean_cand = parts[0].strip()
                    candidate = candidate.split(splitter)[0].strip()
                break

        # Check ignore list
        is_ignored = any(term in clean_cand for term in ignored_terms)
        if not is_ignored:
            for word in clean_cand.split():
                if word in ignored_terms:
                    is_ignored = True
                    break

        if is_ignored or clean_cand in {'me', 'us', 'him', 'her', 'them', 'the', 'all', 'any'}:
            continue

        if len(clean_cand) >= 2:
            return ' '.join(word.capitalize() for word in candidate.split())

    return None


def match_customer_name_in_db(
    extracted_name: str,
    db_customer_names: List[str],
    threshold: float = 0.85
) -> Optional[str]:
    """
    Match extracted customer name against actual DB names with fuzzy matching.

    Handles title variations and exact matches:
    - "Mrs. Fatima Khan" matches "Fatima Khan" (DB)
    - "Ali Hassan" matches "Mr. Ali Hassan" (DB)
    - "Ali123" matches "Ali123" (exact)

    Args:
        extracted_name: Name extracted from user query
        db_customer_names: List of all unique customer names from vector DB
        threshold: Minimum similarity score (default: 0.85 = 85%)

    Returns:
        Best matching DB name or None if no good match
    """
    import re
    from difflib import SequenceMatcher

    def normalize_for_comparison(name: str) -> str:
        """Remove titles and normalize for comparison"""
        # Remove common titles
        normalized = re.sub(
            r'\b(mr|mrs|ms|miss|dr|prof|sir|madam)\.?\s*',
            '',
            name,
            flags=re.IGNORECASE
        )
        # Normalize whitespace
        normalized = ' '.join(normalized.split())
        return normalized.lower().strip()

    extracted_norm = normalize_for_comparison(extracted_name)

    best_match = None
    best_score = 0.0

    for db_name in db_customer_names:
        # 1. Exact match (case-insensitive, preserves DB format)
        if extracted_name.lower() == db_name.lower():
            return db_name  # Perfect match, return immediately

        # 2. Normalized match (ignoring titles)
        db_norm = normalize_for_comparison(db_name)

        if extracted_norm == db_norm:
            return db_name  # Title-invariant exact match

        # 3. Fuzzy matching
        # Check if extracted is substring of DB name
        if extracted_norm in db_norm:
            score = 0.9
        # Check if DB name is substring of extracted
        elif db_norm in extracted_norm:
            score = 0.85
        # Character-level similarity
        else:
            score = SequenceMatcher(None, extracted_norm, db_norm).ratio()

        if score > best_score:
            best_score = score
            best_match = db_name

    # Return best match if above threshold
    if best_score >= threshold:
        return best_match

    return None


def extract_customer_names_llm(
    question: str,
    llm: BaseLLMClient,
    db_customer_names: Optional[List[str]] = None
) -> tuple:
    """
    LLM-based customer name extraction with multi-customer support.

    Handles ALL edge cases:
    - Single: "Show me Ali's chat" → (["Ali"], "SINGLE")
    - Multi: "Compare Ali and Ahmed" → (["Ali", "Ahmed"], "MULTI")
    - Multi with commas: "Show Ali, Ahmed, and Fatima" → (["Ali", "Ahmed", "Fatima"], "MULTI")
    - With titles: "Mrs. Fatima Khan" → (["Mrs. Fatima Khan"], "SINGLE")
    - With numbers: "Ali123" → (["Ali123"], "SINGLE")
    - Semantic: "Who complained about brakes?" → ([], "SEMANTIC")

    Args:
        question: User query
        llm: LLM client for extraction
        db_customer_names: List of all customer names from DB (optional, for validation)

    Returns:
        Tuple of (names: List[str], query_type: str)

        query_type:
        - "SINGLE": 1 customer name
        - "MULTI": 2+ customer names
        - "SEMANTIC": No specific names
        - "NONE": Not a WhatsApp query at all
    """
    import re

    # Build context about available names if DB provided
    db_context = ""
    if db_customer_names and len(db_customer_names) > 0:
        # Show sample of DB names to help LLM
        sample_names = db_customer_names[:15]  # First 15 names as examples
        db_context = f"\n\n**AVAILABLE CUSTOMER NAMES IN DATABASE** (for reference):\n{', '.join(sample_names)}"
        if len(db_customer_names) > 15:
            db_context += f"\n... and {len(db_customer_names) - 15} more"

    extraction_prompt = f"""You are a customer name extractor for a WhatsApp conversation database.

**TASK**: Extract ALL real customer/person names mentioned in the query.

**RULES**:
1. Extract FULL names as written (preserve "Ali Hassan", "Mrs. Fatima Khan", "Ali123")
2. Extract ALL names if multiple customers mentioned:
   - "Ali and Ahmed" → Extract BOTH
   - "Compare Ali, Ahmed, and Fatima" → Extract ALL THREE
3. Preserve format:
   - Keep titles: "Mrs. Fatima Khan" → "Mrs. Fatima Khan"
   - Keep numbers: "Ali123" → "Ali123"
   - Keep full names: "Ali Hassan" → "Ali Hassan"

**IGNORE** (NOT customer names):
- Company/brands: Haval, GWM, Toyota, Kia, Tank, Jolion, etc.
- Cities: Karachi, Lahore, Islamabad, etc.
- Generic terms: customer, user, person, agent, etc.
- Pronouns: me, him, her, them, etc.

**SEMANTIC QUERIES** (no specific names):
If query is like "who complained about X?" or "customers who said Y", respond with "SEMANTIC"
{db_context}

**USER QUERY**: "{question}"

**YOUR RESPONSE FORMAT**:
If names found, list them (one per line, exact format from query):
Ali Hassan
Ahmed Khan
Mrs. Fatima

If NO specific names (semantic query), respond with:
SEMANTIC

If query is NOT about WhatsApp conversations, respond with:
NONE

**Examples**:

Query: "Show me Ali's chat"
Response:
Ali

Query: "Compare Ali and Ahmed's conversations"
Response:
Ali
Ahmed

Query: "Show Ali, Ahmed, and Mrs. Fatima Khan"
Response:
Ali
Ahmed
Mrs. Fatima Khan

Query: "Who complained about brakes?"
Response:
SEMANTIC

Query: "What is Haval H6 price?"
Response:
NONE

Now extract names:"""

    messages = [{"role": "user", "content": extraction_prompt}]

    try:
        response = llm.generate(messages, max_tokens=200, temperature=0.0)
        content = response.content.strip()

        # Handle special cases
        if content.upper() == "SEMANTIC":
            return [], "SEMANTIC"

        if content.upper() == "NONE":
            return [], "NONE"

        # Parse line-by-line
        names = []
        for line in content.split('\n'):
            name = line.strip()
            # Remove numbering/bullets
            name = re.sub(r'^[\d\.\-\*\•]\s*', '', name)
            name = name.strip()

            # Validate
            if name and len(name) >= 2:
                # Ignore special keywords
                if name.upper() not in ["SEMANTIC", "NONE", "NULL", "N/A", "NAMES", "RESPONSE"]:
                    names.append(name)

        # Classify query type
        if len(names) == 0:
            query_type = "SEMANTIC"
        elif len(names) == 1:
            query_type = "SINGLE"
        else:
            query_type = "MULTI"

        return names, query_type

    except Exception as e:
        print(f"[Name Extraction] LLM extraction failed: {e}")
        # Fallback to regex
        regex_name = extract_customer_name(question)
        if regex_name:
            return [regex_name], "SINGLE"
        return [], "SEMANTIC"
