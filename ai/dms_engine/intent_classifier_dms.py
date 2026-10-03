"""
Intent Classifier for DMS Pipeline

Classifies DMS queries to determine if they need conversational context.
Reuses production-tested RAG intent classifier with DMS-specific adaptations.

CLASSIFICATION TYPES:
====================
1. STANDALONE: Query can be understood without context
   - "Show all repair orders from December 2024"
   - "Find vehicles with VIN starting with NF9"

2. CONTEXT_DEPENDENT: Query needs chat history
   - "What about Ahmed?" (who is Ahmed?)
   - "And repair orders?" (repair orders for what?)

3. META_OP: Query operates on previous answer
   - "Summarize above in 100 words"
   - "Elaborate on that"
   - "Give me that in chart form"

4. TOPIC_SWITCH: New topic, ignore context
   - "Now show me delivery complaints"
   - "Switch to warranty analysis"

OPTIMIZATION STRATEGY:
=====================
1. Regex-first (0 tokens, ~70% of queries) - INSTANT
2. LLM fallback (ambiguous cases only) - ~200ms

"""

from typing import List, Dict, Optional
from ai.llm_client import BaseLLMClient
from ai.rag_engine.intent_classifier import classify_query_intent as rag_classify
from ai.rag_engine.regex_classifiers import classify_query_intent_regex


def classify_dms_query_intent(
    query: str,
    chat_history: Optional[List[Dict[str, str]]],
    llm: BaseLLMClient,
    verbose: bool = True
) -> str:
    """
    Classify DMS query intent using regex-first optimization.

    WORKFLOW:
    =========
    1. Try regex patterns first (instant, 0 tokens)
    2. If regex returns None → LLM fallback (ambiguous cases)
    3. Return classification: standalone | context_dependent | meta_op | topic_switch

    Args:
        query: User's query string
        chat_history: Recent conversation history (list of message dicts)
        llm: LLM client for fallback classification
        verbose: Enable detailed logging (default: True)

    Returns:
        Classification string (lowercase)

    Examples:
        >>> classify_dms_query_intent("Show FFS for D001", None, llm)
        "standalone"  # Clear topic, no context needed

        >>> classify_dms_query_intent("What about Ahmed?", history, llm)
        "context_dependent"  # Who is Ahmed? Need context

        >>> classify_dms_query_intent("Summarize above", history, llm)
        "meta_op"  # Operating on previous answer

    Edge Cases Handled:
        - No chat history → Always standalone
        - Empty query → Standalone (graceful handling)
        - Regex fails → LLM fallback
        - LLM fails → Default to standalone (safe fallback)
    """
    # =========================================================================
    # EDGE CASE 1: Empty or None query
    # =========================================================================
    if not query or len(query.strip()) == 0:
        if verbose:
            print("[IntentClassifier] ⚠ Empty query received, defaulting to standalone")
        return "standalone"

    # =========================================================================
    # EDGE CASE 2: No chat history → Always standalone
    # =========================================================================
    has_history = chat_history is not None and len(chat_history) > 0

    if not has_history:
        if verbose:
            print(f"[IntentClassifier] No chat history → STANDALONE (skip classification)")
        return "standalone"

    # =========================================================================
    # STEP 1: REGEX-FIRST CLASSIFICATION (0 tokens, instant)
    # =========================================================================
    if verbose:
        print(f"[IntentClassifier] Classifying: '{query[:60]}...'")
        print(f"[IntentClassifier] Chat history: {len(chat_history)} messages")

    try:
        regex_result = classify_query_intent_regex(
            question=query,
            has_history=has_history
        )

        # If regex found a clear answer, use it (instant, saves ~500 tokens)
        if regex_result is not None:
            # Convert to lowercase for consistency
            result_lower = regex_result.lower()

            if verbose:
                print(f"[IntentClassifier] ✓ REGEX HIT → {result_lower.upper()} (0 tokens, 0ms)")

            # Map regex results to expected values
            if result_lower == "meta_op":
                return "standalone"  # Meta-ops don't need reformulation
            elif result_lower == "topic_switch":
                return "standalone"  # Topic switch = new query, ignore context
            elif result_lower == "standalone":
                return "standalone"
            elif result_lower == "context_dependent":
                return "context_dependent"
            else:
                # Unknown result, fallback to LLM
                if verbose:
                    print(f"[IntentClassifier] ⚠ Unknown regex result '{result_lower}', trying LLM")

        else:
            if verbose:
                print(f"[IntentClassifier] Regex returned None → LLM FALLBACK")

    except Exception as e:
        if verbose:
            print(f"[IntentClassifier] ⚠ Regex classification error: {e}, falling back to LLM")

    # =========================================================================
    # STEP 2: LLM FALLBACK (for ambiguous cases)
    # =========================================================================
    try:
        if verbose:
            print(f"[IntentClassifier] Running LLM classification...")

        # Reuse production-tested RAG classifier
        result = rag_classify(query, chat_history, llm)

        if verbose:
            print(f"[IntentClassifier] ✓ LLM CLASSIFICATION → {result.upper()} (~200ms)")

        return result

    except Exception as e:
        # =====================================================================
        # EDGE CASE 3: LLM fails → Default to standalone (safe fallback)
        # =====================================================================
        if verbose:
            print(f"[IntentClassifier] ✗ LLM classification error: {e}")
            print(f"[IntentClassifier] FALLBACK → STANDALONE (safe default)")

        # Safe fallback: treat as standalone (no reformulation)
        # Better to skip reformulation than to fail the entire query
        return "standalone"


def is_meta_operation(query: str, verbose: bool = True) -> bool:
    """
    Enhanced meta-operation detection with syntactic analysis.

    META-OPERATIONS (transform previous answer):
    - "Summarize above" → verb + "above"
    - "Give me that in bullet points" → transformation verb

    NOT META-OPERATIONS (context references):
    - "the above VIN" → "the above" + noun (entity reference)
    - "tell me about above" → query verb + "above"
    - "What about Ahmed?" → context-dependent query

    EDGE CASES HANDLED:
    ===================
    - Empty query → False
    - Syntactic pattern analysis (not just keywords)
    - Distinguishes transformation verbs from query verbs

    Args:
        query: User's query string
        verbose: Enable logging (default: True)

    Returns:
        True if meta-operation, False otherwise

    Examples:
        >>> is_meta_operation("Summarize above in 100 words")
        True

        >>> is_meta_operation("can you tell me the customer name for the above VIN?")
        False (context-dependent, needs database query)

        >>> is_meta_operation("Give me that in bullet points")
        True
    """
    # =========================================================================
    # EDGE CASE 1: Empty query
    # =========================================================================
    if not query or len(query.strip()) == 0:
        if verbose:
            print("[MetaOpCheck] Empty query → NOT meta-operation")
        return False

    query_lower = query.lower()

    # =========================================================================
    # STEP 1: Check for META-OP action verbs (transformation operations)
    # =========================================================================
    meta_action_verbs = [
        'summarize', 'summary', 'sum up', 'condense', 'brief',
        'elaborate', 'expand', 'explain more',
        'reformat', 'convert', 'transform',
        'generate report', 'create report', 'make report'
    ]

    has_meta_verb = any(verb in query_lower for verb in meta_action_verbs)

    # =========================================================================
    # STEP 2: Check for META-OP format patterns
    # =========================================================================
    meta_format_patterns = [
        'in bullet', 'as bullet', 'bullet points',
        'in table', 'as table', 'tabular',
        'in chart', 'as chart', 'graph it',
        'for my manager', 'executive summary'
    ]

    has_meta_format = any(pattern in query_lower for pattern in meta_format_patterns)

    # =========================================================================
    # STEP 3: Check for reference words (ambiguous)
    # =========================================================================
    reference_words = ['above', 'previous', 'earlier', 'that answer', 'your response']
    has_reference = any(ref in query_lower for ref in reference_words)

    # =========================================================================
    # DECISION LOGIC: Syntactic Pattern Analysis
    # =========================================================================

    # Pattern 1: Meta-op verb + reference → META-OP
    # "summarize above", "elaborate on previous answer"
    if has_meta_verb and has_reference:
        if verbose:
            print(f"[MetaOpCheck] ✓ META-OPERATION (transformation verb + reference)")
        return True

    # Pattern 2: Meta-op format pattern → META-OP
    # "give me that in bullet points", "show it as a table"
    if has_meta_format:
        if verbose:
            print(f"[MetaOpCheck] ✓ META-OPERATION (format transformation)")
        return True

    # Pattern 3: Meta-op verb alone → META-OP
    # "elaborate on the findings", "summarize the results"
    if has_meta_verb:
        if verbose:
            print(f"[MetaOpCheck] ✓ META-OPERATION (transformation verb)")
        return True

    # =========================================================================
    # Pattern 4: Reference word ALONE (no meta verb/format)
    # =========================================================================
    # This is the CRITICAL disambiguation!
    # "the above VIN" or "tell me about above" → NOT meta-op
    if has_reference and not (has_meta_verb or has_meta_format):
        # Check for QUERY verbs (not transformation verbs)
        query_verbs = [
            'show', 'tell', 'get', 'find', 'what', 'which', 'who',
            'how many', 'can you', 'could you', 'give me', 'list'
        ]
        has_query_verb = any(verb in query_lower for verb in query_verbs)

        # Check for entity references that indicate database query
        entity_patterns = [
            r'\b(the|that|this)\s+above\s+\w+',  # "the above VIN", "that above customer"
            r'about\s+(the\s+)?above',           # "about above", "about the above"
            r'for\s+(the\s+)?above',             # "for above", "for the above"
            r'of\s+(the\s+)?above'               # "of above", "of the above"
        ]

        import re
        has_entity_pattern = any(re.search(pattern, query_lower) for pattern in entity_patterns)

        if has_query_verb or has_entity_pattern:
            if verbose:
                print(f"[MetaOpCheck] NOT a meta-operation (query verb/entity reference + 'above' = context-dependent)")
            return False

    # =========================================================================
    # Default: NOT a meta-operation
    # =========================================================================
    if verbose:
        print(f"[MetaOpCheck] NOT a meta-operation")
    return False


def detect_topic_switch(query: str, verbose: bool = True) -> bool:
    """
    Detect if query is switching to a completely new topic.

    Topic switches should ignore previous context to avoid contamination.

    EDGE CASES HANDLED:
    ===================
    - Empty query → False
    - Case-insensitive matching
    - Multiple indicators

    Args:
        query: User's query string
        verbose: Enable logging (default: True)

    Returns:
        True if topic switch detected, False otherwise

    Examples:
        >>> detect_topic_switch("Now show me delivery complaints")
        True

        >>> detect_topic_switch("What about Ahmed?")
        False
    """
    # =========================================================================
    # EDGE CASE: Empty query
    # =========================================================================
    if not query or len(query.strip()) == 0:
        if verbose:
            print("[TopicSwitch] Empty query → NOT a topic switch")
        return False

    # =========================================================================
    # TOPIC SWITCH INDICATORS
    # =========================================================================
    switch_indicators = [
        'now show', 'now display', 'now give',
        'switch to', 'change to', 'move to',
        'instead show', 'rather show',
        'let me see', 'i want to see',
        'forget that', 'never mind'
    ]

    query_lower = query.lower()

    is_switch = any(indicator in query_lower for indicator in switch_indicators)

    if verbose:
        if is_switch:
            matched = [ind for ind in switch_indicators if ind in query_lower]
            print(f"[TopicSwitch] ✓ TOPIC SWITCH detected (indicators: {matched[:2]}...)")
        else:
            print(f"[TopicSwitch] NOT a topic switch")

    return is_switch
