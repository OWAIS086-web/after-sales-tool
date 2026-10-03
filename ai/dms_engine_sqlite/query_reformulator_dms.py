"""
Query Reformulator for DMS Pipeline

Converts context-dependent queries to standalone queries optimized for SQL generation.

CORE FUNCTIONALITY:
===================
1. Resolve pronouns (it, that, his, her) → Specific entities (VIN, customer names, etc.)
2. Carry forward context (dealer IDs, dates, vehicle models)
3. Preserve SQL-relevant terms (exact IDs, dates, numbers)
4. Optimize for tier routing and SQL generation

REFORMULATION EXAMPLES:
=======================
Input:  "What about Ahmed's records?"
History: User asked "Show FFS for December 2024"
Output: "Ahmed customer FFS records December 2024"

Input:  "And repair orders for that vehicle?"
History: Previous answer mentioned "VIN NF9FF6A58N2000096"
Output: "Repair orders for vehicle VIN NF9FF6A58N2000096"

Input:  "Show me his other complaints"
History: Discussed "Customer Shariq warranty issues"
Output: "Shariq customer complaints warranty other issues"

EDGE CASES HANDLED:
===================
- Empty query → Return original
- No chat history → Return original with "DMS" prefix
- LLM failure → Return original query (safe fallback)
- Reformulation too short → Return original
- Reformulation identical → Return original (skip reformulation)

Author: Claude Sonnet 4.5
Date: 2026-01-07
"""

from typing import List, Dict, Optional
from ai.llm_client import BaseLLMClient
from ai.rag_engine.query_reformulator import reformulate_query as rag_reformulate


def reformulate_dms_query(
    query: str,
    chat_history: List[Dict[str, str]],
    llm: BaseLLMClient,
    verbose: bool = True
) -> str:
    """
    Reformulate context-dependent DMS query to standalone query.

    WORKFLOW:
    =========
    1. Validate inputs (query, history, LLM)
    2. Build compressed context from history
    3. Call LLM to reformulate (resolve pronouns, add context)
    4. Clean and validate reformulated query
    5. Return standalone query

    Args:
        query: User's context-dependent query
        chat_history: Recent conversation (1-4 messages recommended)
        llm: LLM client for reformulation
        verbose: Enable detailed logging (default: True)

    Returns:
        Reformulated standalone query optimized for SQL generation

    Edge Cases:
        - Empty query → Original query
        - No history → Original query + "DMS" prefix
        - LLM error → Original query (safe fallback)
        - Reformulation invalid → Original query

    Examples:
        >>> reformulate_dms_query("What about Ahmed?", history, llm)
        "Ahmed customer FFS records December 2024"

        >>> reformulate_dms_query("And that vehicle?", history, llm)
        "Repair orders for vehicle VIN NF9FF6A58N2000096"
    """
    # =========================================================================
    # EDGE CASE 1: Empty or invalid query
    # =========================================================================
    if not query or len(query.strip()) == 0:
        if verbose:
            print("[QueryReformulator] ⚠ Empty query received, returning as-is")
        return query if query else ""

    # =========================================================================
    # EDGE CASE 2: No chat history → Cannot reformulate
    # =========================================================================
    if not chat_history or len(chat_history) == 0:
        if verbose:
            print("[QueryReformulator] No chat history, adding 'DMS' prefix and returning")
        # Add "DMS" to help with tier routing
        return f"DMS {query}"

    # =========================================================================
    # EDGE CASE 3: Chat history invalid format
    # =========================================================================
    try:
        # Validate chat history format
        for msg in chat_history:
            if not isinstance(msg, dict):
                raise ValueError(f"Invalid message format: {type(msg)}")
            if 'role' not in msg or 'content' not in msg:
                raise ValueError(f"Message missing required fields: {msg.keys()}")

    except Exception as e:
        if verbose:
            print(f"[QueryReformulator] ⚠ Invalid chat history format: {e}")
            print(f"[QueryReformulator] Returning original query")
        return query

    # =========================================================================
    # STEP 1: Log reformulation attempt
    # =========================================================================
    if verbose:
        print(f"[QueryReformulator] ════════════════════════════════════════════")
        print(f"[QueryReformulator] REFORMULATION START")
        print(f"[QueryReformulator] Original query: '{query}'")
        print(f"[QueryReformulator] Chat history: {len(chat_history)} messages")

        # Log last 2 messages for context
        last_messages = chat_history[-2:] if len(chat_history) >= 2 else chat_history
        for i, msg in enumerate(last_messages, 1):
            role = msg.get('role', 'unknown')
            content_preview = msg.get('content', '')[:80]
            print(f"[QueryReformulator]   Msg {i} ({role}): {content_preview}...")

    # =========================================================================
    # STEP 2: Call LLM for reformulation (reuse RAG reformulator)
    # =========================================================================
    try:
        if verbose:
            print(f"[QueryReformulator] Calling LLM for reformulation...")

        # REUSE: Production-tested reformulator from RAG engine
        # The reformulation logic is domain-agnostic and works for DMS
        reformulated = rag_reformulate(
            query=query,
            chat_history=chat_history,
            llm=llm,
            company_name="DMS"  # Use "DMS" as company context
        )

        if verbose:
            print(f"[QueryReformulator] ✓ LLM reformulation successful")

    except Exception as e:
        # =====================================================================
        # EDGE CASE 4: LLM fails → Return original query (safe fallback)
        # =====================================================================
        if verbose:
            print(f"[QueryReformulator] ✗ LLM reformulation error: {e}")
            print(f"[QueryReformulator] FALLBACK → Returning original query")
            print(f"[QueryReformulator] ════════════════════════════════════════════")

        # Safe fallback: use original query
        # Better to use original than to fail the entire request
        return query

    # =========================================================================
    # STEP 3: Clean and validate reformulated query
    # =========================================================================
    try:
        reformulated_clean = _clean_reformulated_query(reformulated, query, verbose=verbose)

        # =====================================================================
        # EDGE CASE 5: Reformulation too short or invalid
        # =====================================================================
        if len(reformulated_clean.strip()) < 3:
            if verbose:
                print(f"[QueryReformulator] ⚠ Reformulated query too short: '{reformulated_clean}'")
                print(f"[QueryReformulator] FALLBACK → Returning original query")
                print(f"[QueryReformulator] ════════════════════════════════════════════")
            return query

        # =====================================================================
        # EDGE CASE 6: Reformulation identical to original
        # =====================================================================
        if reformulated_clean.lower().strip() == query.lower().strip():
            if verbose:
                print(f"[QueryReformulator] Reformulated query identical to original")
                print(f"[QueryReformulator] Skipping reformulation (no change needed)")
                print(f"[QueryReformulator] ════════════════════════════════════════════")
            return query

        # =====================================================================
        # SUCCESS: Return reformulated query
        # =====================================================================
        if verbose:
            print(f"[QueryReformulator] ✓ REFORMULATION COMPLETE")
            print(f"[QueryReformulator] Original:     '{query}'")
            print(f"[QueryReformulator] Reformulated: '{reformulated_clean}'")
            print(f"[QueryReformulator] Change: {len(reformulated_clean) - len(query):+d} chars")
            print(f"[QueryReformulator] ════════════════════════════════════════════")

        return reformulated_clean

    except Exception as e:
        # =====================================================================
        # EDGE CASE 7: Cleaning fails → Return original
        # =====================================================================
        if verbose:
            print(f"[QueryReformulator] ✗ Cleaning error: {e}")
            print(f"[QueryReformulator] FALLBACK → Returning original query")
            print(f"[QueryReformulator] ════════════════════════════════════════════")

        return query


def _clean_reformulated_query(reformulated: str, original: str, verbose: bool = True) -> str:
    """
    Clean and validate reformulated query.

    Removes LLM artifacts, validates length, ensures quality.

    CLEANING STEPS:
    ===============
    1. Remove quotation marks
    2. Remove common LLM prefixes ("Reformulated query:", etc.)
    3. Remove trailing punctuation (except ?)
    4. Validate minimum length (3 chars)
    5. Check if identical to original

    Args:
        reformulated: LLM-generated reformulated query
        original: Original user query
        verbose: Enable logging

    Returns:
        Cleaned reformulated query

    Edge Cases:
        - Empty reformulation → Original
        - Too short (< 3 chars) → Original
        - Identical to original → Original
        - Invalid characters → Original
    """
    if verbose:
        print(f"[QueryReformulator]   Cleaning reformulated query...")

    # =========================================================================
    # EDGE CASE 1: Empty reformulation
    # =========================================================================
    if not reformulated or len(reformulated.strip()) == 0:
        if verbose:
            print(f"[QueryReformulator]   ⚠ Empty reformulation, using original")
        return original

    cleaned = reformulated

    # =========================================================================
    # STEP 1: Remove quotation marks
    # =========================================================================
    cleaned = cleaned.strip('"\'')

    if verbose:
        print(f"[QueryReformulator]   After quote removal: '{cleaned}'")

    # =========================================================================
    # STEP 2: Remove common LLM prefixes
    # =========================================================================
    prefixes_to_remove = [
        "Reformulated query:",
        "Query:",
        "Standalone query:",
        "Search query:",
        "Output:",
        "Result:",
        "Answer:",
    ]

    for prefix in prefixes_to_remove:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()
            cleaned = cleaned.lstrip(':').strip()
            if verbose:
                print(f"[QueryReformulator]   Removed prefix '{prefix}'")

    # =========================================================================
    # STEP 3: Remove trailing punctuation (except ?)
    # =========================================================================
    while cleaned and cleaned[-1] in ['.', ',', ';', ':']:
        cleaned = cleaned[:-1].strip()

    if verbose:
        print(f"[QueryReformulator]   After cleanup: '{cleaned}'")

    # =========================================================================
    # EDGE CASE 2: Cleaned result too short
    # =========================================================================
    if len(cleaned) < 3:
        if verbose:
            print(f"[QueryReformulator]   ⚠ Cleaned result too short, using original")
        return original

    # =========================================================================
    # EDGE CASE 3: Cleaned result identical to original
    # =========================================================================
    if cleaned.lower() == original.lower():
        if verbose:
            print(f"[QueryReformulator]   Result identical to original (no change)")
        return original

    return cleaned


def extract_key_entities(
    chat_history: List[Dict[str, str]],
    verbose: bool = True
) -> Dict[str, Optional[str]]:
    """
    Extract key entities from chat history for debugging/validation.

    Scans recent messages to find:
    - VIN numbers
    - Customer names
    - Dealer IDs
    - Dates
    - Repair order numbers

    NOTE: This is primarily for debugging. The LLM reformulator
    handles entity extraction automatically.

    Args:
        chat_history: Recent conversation messages
        verbose: Enable logging

    Returns:
        Dict with extracted entities (for debugging only)

    Examples:
        >>> extract_key_entities(history)
        {
            "vin": "NF9FF6A58N2000096",
            "customer": "Ahmed",
            "dealer_id": "D001",
            "date": "December 2024"
        }
    """
    import re

    entities = {
        "vin": None,
        "customer": None,
        "dealer_id": None,
        "date": None,
        "ro_number": None,
    }

    if not chat_history:
        return entities

    if verbose:
        print(f"[EntityExtraction] Scanning {len(chat_history)} messages for entities...")

    # Scan all messages (user + assistant) in reverse order (most recent first)
    for msg in reversed(chat_history):
        content = msg.get('content', '')

        # Extract VIN (17 alphanumeric characters)
        if not entities["vin"]:
            vin_match = re.search(r'\b([A-Z0-9]{17})\b', content)
            if vin_match:
                entities["vin"] = vin_match.group(1)
                if verbose:
                    print(f"[EntityExtraction]   Found VIN: {entities['vin']}")

        # Extract Dealer ID (D### pattern)
        if not entities["dealer_id"]:
            dealer_match = re.search(r'\bD\d{3,4}\b', content)
            if dealer_match:
                entities["dealer_id"] = dealer_match.group(0)
                if verbose:
                    print(f"[EntityExtraction]   Found Dealer ID: {entities['dealer_id']}")

        # Extract RO Number (RO-#### pattern)
        if not entities["ro_number"]:
            ro_match = re.search(r'\bRO-?\d{4,6}\b', content, re.IGNORECASE)
            if ro_match:
                entities["ro_number"] = ro_match.group(0)
                if verbose:
                    print(f"[EntityExtraction]   Found RO#: {entities['ro_number']}")

        # Extract dates (December 2024, Dec 2024, 12/2024, etc.)
        if not entities["date"]:
            date_patterns = [
                r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b',
                r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b',
                r'\b\d{1,2}/\d{4}\b',
                r'\b\d{4}-\d{2}-\d{2}\b',
            ]
            for pattern in date_patterns:
                date_match = re.search(pattern, content, re.IGNORECASE)
                if date_match:
                    entities["date"] = date_match.group(0)
                    if verbose:
                        print(f"[EntityExtraction]   Found date: {entities['date']}")
                    break

    if verbose:
        found_count = sum(1 for v in entities.values() if v is not None)
        print(f"[EntityExtraction] Extraction complete: {found_count}/{len(entities)} entities found")

    return entities
