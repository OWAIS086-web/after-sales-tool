"""
Intent Classification Module

Classifies queries as "context-dependent" or "standalone" to determine
if query reformulation with chat history is needed.

Designed to run in parallel with query optimization for zero latency overhead.

**OPTIMIZATION**: Uses regex-first classification to save tokens:
- Try regex patterns first (instant, 0 tokens) - covers ~70% of queries
- Fallback to LLM only if regex returns None (ambiguous cases)
"""

from __future__ import annotations
from typing import List, Dict, Optional
from ai.llm_client import BaseLLMClient
from ai.rag_engine.regex_classifiers import classify_query_intent_regex


def classify_query_intent(
    query: str,
    chat_history: Optional[List[Dict[str, str]]],
    llm: BaseLLMClient
) -> str:
    """
    Classify if query needs chat history context for understanding.

    **OPTIMIZATION**: Uses regex-first approach to save tokens:
    1. Try regex patterns first (instant, 0 tokens) - covers ~70% of queries
    2. Fallback to LLM only if regex returns None (ambiguous cases)

    Args:
        query: User's current query
        chat_history: List of recent messages [{"role": "user/assistant", "content": "..."}]
        llm: LLM client for classification

    Returns:
        "STANDALONE", "CONTEXT_DEPENDENT", "META_OP", or "TOPIC_SWITCH"
        (Note: Regex returns uppercase, converted to lowercase for compatibility)

    Examples:
        Standalone:
        - "Haval H6 price in Pakistan" → STANDALONE
        - "Show me listings in Karachi" → STANDALONE
        - "Does Jolion have a sunroof?" → STANDALONE

        Context-dependent:
        - "What about white ones?" → CONTEXT_DEPENDENT
        - "Anything in Lahore?" → CONTEXT_DEPENDENT
        - "Does it have a sunroof?" → CONTEXT_DEPENDENT

        Meta-operations:
        - "Summarize the above" → META_OP
        - "Translate this to urdu" → META_OP
    """
    # =========================================================================
    # OPTIMIZATION: Try regex first (0 tokens)
    # =========================================================================
    has_history = chat_history is not None and len(chat_history) > 0

    regex_result = classify_query_intent_regex(
        question=query,
        has_history=has_history
    )

    # If regex found a clear answer, use it (instant, saves ~500 tokens)
    if regex_result is not None:
        # Convert to lowercase for compatibility with existing code
        result_lower = regex_result.lower()

        # Map regex results to expected values
        # Regex returns: META_OP, STANDALONE, CONTEXT_DEPENDENT, TOPIC_SWITCH
        # Expected: standalone, context_dependent
        if result_lower == "meta_op":
            print(f"  [Intent Classification] REGEX HIT -> META_OP (skipping reformulation, 0 tokens)")
            return "standalone"
        elif result_lower == "topic_switch":
            print(f"  [Intent Classification] REGEX HIT -> TOPIC_SWITCH (new topic, 0 tokens)")
            return "standalone"
        elif result_lower == "standalone":
            print(f"  [Intent Classification] REGEX HIT -> STANDALONE (0 tokens)")
            return "standalone"
        elif result_lower == "context_dependent":
            print(f"  [Intent Classification] REGEX HIT -> CONTEXT_DEPENDENT (needs reformulation, 0 tokens)")
            return "context_dependent"

    print(f"  [Intent Classification] Regex returned None -> LLM fallback")

    # =========================================================================
    # LLM FALLBACK: For ambiguous cases that regex couldn't handle
    # =========================================================================
    # If no chat history, query is always standalone
    if not chat_history or len(chat_history) == 0:
        return "standalone"

    # Build context summary from chat history (with smart compression)
    # Get compression LLM from config if available
    compression_llm = None
    try:
        from config.llm_config import get_llm_for_component
        compression_llm = get_llm_for_component("context_compression", fallback_api_key=None)
    except Exception as e:
        print(f"[IntentClassifier] Warning: Could not load compression LLM: {e}")
        print(f"[IntentClassifier] Falling back to simple truncation")

    history_summary = _build_history_summary(
        chat_history=chat_history,
        current_query=query,
        compression_llm=compression_llm
    )

    # Classification prompt
    classification_prompt = f"""You are a robust intent classifier determining if a query can be understood WITHOUT chat history.

**CORE PRINCIPLE** (Apply this universally):
═══════════════════════════════════════════════════════════════════════════
If a NEW person (who hasn't seen the conversation) reads this query, would they understand WHAT is being asked?

→ YES, they understand WHAT is being asked = "standalone"
→ NO, they need context to know WHAT is being asked = "context_dependent"
═══════════════════════════════════════════════════════════════════════════

**THE DECISIVE TEST**:
Ask yourself: "If this was the FIRST message in a brand new conversation, would it make sense?"

Examples of applying this test:
• "What are the prices being quoted to the customers?" → YES, makes sense as first message = standalone ✅
• "What about the price?" → NO, price of WHAT? = context_dependent ❌
• "How is the market responding?" → YES, makes sense as first message = standalone ✅
• "How is it responding?" → NO, WHAT is "it"? = context_dependent ❌

**ROBUSTNESS RULES** (Handle ANY query):

1. **Referential vs General**:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Referential (needs context):
   • Pronouns that POINT: "it", "that", "this", "those", "them", "ones"
   • Missing subject: "And the price?" (price of WHAT?)
   • Incomplete: "What about Karachi?" (about WHAT?)

   General (standalone):
   • General entities: "the customers", "the market", "the dealers", "the product"
   • Politeness: "me", "you", "I", "we"
   • Complete questions about general topics
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2. **The "New Person" Test** (Most Important):
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Imagine someone new joins the conversation and ONLY sees this query.

   Can they understand what topic/subject is being asked about?
   • YES → standalone (even if missing specifics, the TOPIC is clear)
   • NO → context_dependent (cannot identify the topic without history)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3. **General Nouns vs Pronouns**:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   "the [noun]" where noun is a general entity = standalone ✅
   • "the customers", "the dealers", "the market", "the team"
   • These are GENERAL references, not specific to previous messages

   Pronoun without clear referent = context_dependent ❌
   • "it", "that", "those", "them", "the one"
   • These MUST point to something mentioned before
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4. **Distinguishing Patterns**:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   STANDALONE (self-contained):
   • "What are [topic] [details]?" → Clear topic, even if general
   • "How are [general entity] [verb]ing?" → General entity specified
   • "Show me [specific thing]" → Thing is named/described

   CONTEXT_DEPENDENT (needs history):
   • "What about [pronoun]?" → Pronoun without referent
   • "And [incomplete phrase]?" → Missing subject/context
   • "[pronoun] [verb]?" → Pronoun-based question
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**PREVIOUS CONVERSATION**:
{history_summary}

**USER QUERY**: "{query}"

**APPLY THE CORE PRINCIPLE**:
Would a new person understand WHAT this query is asking about?

Respond with ONLY ONE WORD (lowercase): standalone or context_dependent"""

    messages = [{"role": "user", "content": classification_prompt}]

    try:
        response = llm.generate(messages, max_tokens=10, temperature=0.0)
        classification = response.content.strip().lower()

        # Validate response
        if classification in ["context_dependent", "standalone"]:
            print(f"[IntentClassifier] Query: '{query[:50]}...' → {classification.upper()}")
            return classification

        # Invalid response, default to context_dependent for safety
        print(f"[IntentClassifier] Invalid response '{classification}', defaulting to context_dependent")
        return "context_dependent"

    except Exception as e:
        print(f"[IntentClassifier] Error: {e}, defaulting to context_dependent")
        # Safe fallback: assume context-dependent (will trigger reformulation)
        return "context_dependent"


def _build_history_summary(
    chat_history: List[Dict[str, str]],
    max_messages: int = 4,
    current_query: str = "",
    compression_llm: Optional[BaseLLMClient] = None
) -> str:
    """
    Build a concise summary of chat history for the intent classifier.

    Strategy:
    - Include ALL messages (user + assistant) for context
    - Smart compression for assistant responses:
      * If compression_llm provided AND current_query has reference terms:
        → Use LLM to extract relevant portions semantically
      * Otherwise:
        → Simple truncation to first 100 chars
    - This handles "summarize the above" / "explain that" queries

    Args:
        chat_history: List of messages
        max_messages: Maximum messages to include (default: 4 = 2 rounds)
        current_query: Current user query (to extract relevant context)
        compression_llm: Optional LLM for semantic compression (GPT-4o-mini recommended)

    Returns:
        Formatted history summary with smart compression
    """
    if not chat_history:
        return "No previous conversation."

    # Take last N messages (sliding window)
    recent = chat_history[-max_messages:]

    # Format all messages (user + compressed assistant)
    lines = []
    for i, msg in enumerate(recent, 1):
        role = msg["role"].capitalize()
        content = msg["content"]

        # Smart compression for assistant responses
        if role == "Assistant":
            content = _compress_assistant_response(
                response=content,
                current_query=current_query,
                compression_llm=compression_llm
            )
        else:
            # User queries: truncate only if very long
            if len(content) > 150:
                content = content[:150] + "..."

        lines.append(f"{i}. {role}: {content}")

    return "\n".join(lines)


def _compress_assistant_response(
    response: str,
    current_query: str,
    compression_llm: Optional[BaseLLMClient]
) -> str:
    """
    Intelligently compress assistant response using LLM-based semantic extraction.

    Strategy:
    1. If response is short (≤200 chars) → return as-is
    2. If no current_query OR no compression_llm → simple truncation (first 100 chars)
    3. If current_query has reference terms ("above", "that", etc.) → LLM compression
    4. Otherwise → simple truncation

    This is the PRODUCTION approach used by LangChain's ContextualCompressionRetriever.

    Args:
        response: Full assistant response
        current_query: Current user query
        compression_llm: LLM client for compression (GPT-4o-mini recommended)

    Returns:
        Compressed response (relevant portions extracted)

    Cost: ~$0.001 per compression (GPT-4o-mini)
    Latency: 100-200ms
    """
    # Case 1: Short response, no compression needed
    if len(response) <= 200:
        return response

    # Case 2: No LLM available OR no current query → simple truncation
    if not compression_llm or not current_query or len(current_query.strip()) == 0:
        first_sentence = response.split('.')[0] + '.' if '.' in response else response
        return first_sentence[:100] + "..." if len(first_sentence) > 100 else first_sentence

    # Case 3: Check if query has STRONG reference terms (indicates user referring to previous response)
    # Note: Removed "the " to avoid false positives with general entities like "the customers", "the market"
    reference_indicators = [
        "above",           # "summarize the above"
        " it ",            # "explain it" (with spaces to avoid "itation")
        " that ",          # "elaborate on that" (with spaces)
        "this",            # "this point", "this issue"
        "those",           # "those problems"
        "point ",          # "point 3", "the point about"
        "item ",           # "item 5", "the item you"
        "number ",         # "number 4", "the number"
        "mentioned",       # "you mentioned"
        "said",            # "you said"
        "previous",        # "previous response"
        "earlier",         # "earlier you"
    ]
    has_reference = any(term in current_query.lower() for term in reference_indicators)

    if not has_reference:
        # No reference detected, simple truncation is fine
        first_sentence = response.split('.')[0] + '.' if '.' in response else response
        return first_sentence[:100] + "..." if len(first_sentence) > 100 else first_sentence

    # Case 4: LLM-based STRUCTURED semantic compression
    # Production-grade: Preserves names, keywords, topic for reformulation
    try:
        compression_prompt = f"""You are a Senior Context Engineer for an Automotive Marketing & After-Sales RAG system. 
Your goal is to compress a high-volume assistant response into a "Semantic Snapshot" that 
directly empowers a downstream Query Reformulator.

**ASSISTANT'S PREVIOUS RESPONSE**:
{response}

**USER'S FOLLOW-UP QUERY**: "{current_query}"

**YOUR TASK**: Extract the following in a structured format (this will be used for query reformulation, so be thorough!):

1. **Topic**: Main subject discussed (1-3 words)
2. **Names**: ALL person/customer names, if mentioned (comma-separated, include ALL names)
3. **Keywords**: Important domain keywords (3-5 words, comma-separated)
4. **Summary**: Brief 3-sentence summary of the overall response content

**CRITICAL RULES**:
- **Names**: Extract EVERY customer/person name mentioned (not just the first one!)
  - Look for patterns: "Ahmed said", "Customer Shariq", "Usman complained", etc.
  - Include ALL names in comma-separated format
- **Keywords**: Focus on automotive/business keywords (delivery, timeline, brake, AC, etc.)
- **Topic**: What is the main subject? Or is it multi subject? (e.g., "delivery timeline", "brake issues", "pricing", "angry customers and after sales feedback")
- **Summary**: Three sentence capturing the essence

**OUTPUT FORMAT** (exactly like this):
Topic: [main subject in 1-3 words]
Names: [name1, name2, name3, ...] OR None if no names
Keywords: [keyword1, keyword2, keyword3]
Summary: [three sentence summary]

**EXAMPLE 1**:
If response talks about 5 customers complaining about delivery delays:
Topic: Delivery delays
Names: Shariq, Ahmed, Usman, Bilal, Kashif
Keywords: delivery, delay, timeline, 60-75 days, frustration
Summary: Five customers experiencing delivery delays, quoted 60-75 days timeline

Example 2: (Technical Issue & Location)
- Response: "I checked the records for the Karachi workshop. Customers Ahmed and Bilal both 
  reported H6 brake squeaking issues. Ahmed was quoted 2 days for service."
- User Query: "What about the guy in Lahore?"
- Output:
Topic: Brake issues 
Names: Ahmed, Bilal
Keywords: H6, brake squeaking, Karachi, workshop, service timeline
Summary: Ahmed and Bilal reported H6 brake noise in Karachi. Service estimate was 2 days. 
         User is now pivoting to a Lahore-based customer.

Example 3: (Marketing & Multiple Models)
- Response: "The Jolion is available in White and Blue. The H6 is only in Black. Pricing 
  starts from 8M PKR."
- User Query: "And the references for the H6?"
- Output:
Topic: Vehicle Availability & Pricing
Names: None
Keywords: Jolion, H6, White, Blue, Black, 8M PKR, variant pricing
Summary: Assistant provided color options for Jolion and H6 and base pricing. User is 
         now seeking evidence/sources specifically for the H6 data.

**YOUR STRUCTURED EXTRACTION**:"""

        # Call compression LLM (GPT-4o-mini: fast, cheap, good at extraction)
        messages = [{"role": "user", "content": compression_prompt}]
        compressed_response = compression_llm.generate(messages, max_tokens=150, temperature=0.0)

        compressed_text = compressed_response.content.strip()

        # Validate compression (ensure it's not empty or too short)
        if len(compressed_text) >= 10:
            print(f"[Compression] ✅ Structured compression successful")
            print(f"[Compression]   Original: {len(response)} chars")
            print(f"[Compression]   Compressed: {len(compressed_text)} chars")
            print(f"[Compression]   Content:\n{compressed_text}")
            return compressed_text

        # Fallback if compression failed
        print(f"[Compression] ❌ Failed, using simple truncation")
        first_sentence = response.split('.')[0] + '.' if '.' in response else response
        return first_sentence[:100] + "..." if len(first_sentence) > 100 else first_sentence

    except Exception as e:
        print(f"[Compression] Error: {e}, falling back to simple truncation")
        first_sentence = response.split('.')[0] + '.' if '.' in response else response
        return first_sentence[:100] + "..." if len(first_sentence) > 100 else first_sentence


def needs_reformulation(
    query: str,
    chat_history: Optional[List[Dict[str, str]]],
    llm: BaseLLMClient
) -> bool:
    """
    Convenience function: Returns True if query needs reformulation.

    Args:
        query: User's current query
        chat_history: Recent conversation messages
        llm: LLM client for classification

    Returns:
        True if query is context-dependent (needs reformulation), False otherwise
    """
    classification = classify_query_intent(query, chat_history, llm)
    return classification == "context_dependent"
