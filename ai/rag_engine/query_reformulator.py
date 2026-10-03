"""
Query Reformulation Module

Rewrites context-dependent queries into standalone, search-optimized queries
using chat history for context resolution.

Optimized for ChromaDB vector retrieval with automotive domain specificity.
"""

from __future__ import annotations
from typing import List, Dict, Optional
from ai.llm_client import BaseLLMClient


def reformulate_query(
    query: str,
    chat_history: List[Dict[str, str]],
    llm: BaseLLMClient,
    company_name: str = "Haval"
) -> str:
    """
    Reformulate a context-dependent query into a standalone search query.

    Converts vague follow-ups into explicit, search-optimized queries by:
    - Resolving pronouns (it, that, ones) to specific entities
    - Carrying forward context (car models, locations, features)
    - Adding relevant keywords for better vector retrieval

    Args:
        query: User's context-dependent query
        chat_history: Recent conversation messages (last 4 messages recommended)
        llm: LLM client for reformulation
        company_name: Company name for domain-specific optimization (default: "Haval")

    Returns:
        Reformulated standalone query optimized for vector search

    Examples:
        Input:  "What about white ones?"
        History: User asked "Haval H6 price"
        Output: "Haval H6 white color variant pricing Pakistan"

        Input:  "Anything in Lahore?"
        History: User asked "Haval listings in Karachi"
        Output: "Haval car listings available in Lahore Pakistan"

        Input:  "Does it have a sunroof?"
        History: Discussing "Haval Jolion"
        Output: "Haval Jolion sunroof panoramic roof feature availability"
    """
    if not chat_history or len(chat_history) == 0:
        # No history, return original query with domain boost
        return f"{company_name} {query}"

    # Build context from chat history (with smart compression)
    # Get compression LLM from config if available
    compression_llm = None
    try:
        from config.llm_config import get_llm_for_component
        compression_llm = get_llm_for_component("context_compression", fallback_api_key=None)
    except Exception as e:
        print(f"[QueryReformulator] Warning: Could not load compression LLM: {e}")
        print(f"[QueryReformulator] Falling back to simple truncation")

    history_context = _build_reformulation_context(
        chat_history=chat_history,
        current_query=query,
        compression_llm=compression_llm
    )

    # Reformulation prompt
    reformulation_prompt = f"""You are a query reformulator for an automotive marketing & dealership management system.

**TASK**: Rewrite the user's query into a STANDALONE, SEARCH-OPTIMIZED query that can be understood WITHOUT conversation context.

**RULES FOR REFORMULATION**:

0. **CRITICAL - Distinguish Meta-Operations from Context-Dependent New Queries** (HIGHEST PRIORITY):
   ═══════════════════════════════════════════════════════════════════════════════

   **A. META-OPERATIONS** (Transform existing answer, NO new data fetch):
   ─────────────────────────────────────────────────────────────────────────────
   Keywords: "summarize", "elaborate", "explain more", "clarify", "give more details",
            "expand on this", "translate", "simplify", "rephrase", "give in bullet points"

   → These want to REFORMAT/TRANSFORM the existing answer
   → DO NOT include specific entities (customer names, VINs, dealer IDs)
   → ONLY include the TOPIC from previous answer

   Examples (WhatsApp/Forum):
   - Previous: Answer about delivery delays (mentions 10 customers)
   - User: "summarize above in 150 words"
   - Reformulate: "delivery delays complaints summary" ✅ (NO customer names!)

   - Previous: Answer about brake issues (mentions Shariq, Ahmed, Bilal)
   - User: "elaborate on this"
   - Reformulate: "brake issues details" ✅ (NO customer names!)

   Examples (DMS/Dealership):
   - Previous: "There are 12,549 FFS inspections performed in total"
   - User: "explain more"
   - Reformulate: "FFS inspections details" ✅ (NO count!)

   - Previous: List of repair orders for dealer D001
   - User: "summarize the above"
   - Reformulate: "repair orders summary" ✅ (NO dealer ID!)

   **WHY**: Meta-operations transform the ANSWER, not re-query the database.
   If we include entities, the system will route to entity-specific handlers instead of summarizing!


   **B. CONTEXT-DEPENDENT NEW QUERIES** (Fetch data with additional details/grouping):
   ─────────────────────────────────────────────────────────────────────────────
   Keywords: "categorize by X", "break down by Y", "show for Z", "filter by W",
            "group by", "split by", "organize by", "segment by",
            "complete list", "full list", "with VIN", "with details", "for the above"

   → These want the SAME base data with MORE DETAILS or DIFFERENT grouping
   → **CRITICAL**: MUST preserve THE COMPLETE DESCRIPTION from previous query (the WHAT)
   → ADD the new dimension/detail/filter (the HOW)
   → **NEVER lose the original query context!**

   **RULE**: When you see "the above", "for above", "complete list", etc.:
   1. Look at the PREVIOUS USER QUERY (not the assistant's answer!)
   2. Copy the ENTIRE query description word-for-word
   3. Append the new requested detail/grouping

   Examples (WhatsApp/Forum):
   - Previous Query: "Haval H6 complaints about delivery delays"
   - User: "categorize above by city"
   - Reformulate: "Haval H6 delivery delay complaints categorized by city" ✅
   - NOTE: Preserved "Haval H6 delivery delay complaints" (the WHAT), added "by city" (the HOW)

   - Previous Query: "Price discussions on the forum"
   - User: "break down above by month"
   - Reformulate: "Haval price discussions forum monthly breakdown" ✅

   Examples (DMS/Dealership):
   - Previous Query: "Vehicles where free service was followed by immediate repair visit"
   - User: "please break down the complete list including vin numbers for the above"
   - Reformulate: "Vehicles where free service followed by immediate repair visit with VIN numbers customer names dealership details" ✅
   - NOTE: Preserved ENTIRE description "vehicles where free service followed by immediate repair", added "with VIN numbers..."

   - Previous Answer: "There are 12,549 FFS inspections performed in total"
   - Previous Query: "How many FFS inspections?"
   - User: "could you please categorize the above in dealer wise?"
   - Reformulate: "FFS inspections categorized by dealer" ✅
   - NOTE: Extracted "FFS inspections" from query, added "by dealer"

   - Previous Query: "Repair orders for December 2024"
   - User: "break down above by service advisor"
   - Reformulate: "Repair orders for December 2024 by service advisor" ✅

   - Previous Query: "Total warranty claims processed"
   - User: "show above for each vehicle model"
   - Reformulate: "Warranty claims by vehicle model" ✅

   - Previous Query: "Identify vehicles showing early-life failure pattern"
   - User: "show me the full list with VIN numbers"
   - Reformulate: "Vehicles showing early-life failure pattern with VIN numbers customer details" ✅

   **WHY**: These need database queries that return the SAME entities but with:
   - Additional SELECT columns (VIN, customer name, dates)
   - Additional GROUP BY clauses (by dealer, by advisor, by model)
   - Same WHERE clause as before

   **CRITICAL WARNING**: DO NOT lose the original query context!
   ❌ WRONG: "complete list breakdown with VIN numbers for above data"
   ✅ RIGHT: "[Complete original query description] with VIN numbers"


   **DECISION TREE**:
   ┌─ Contains "summarize/elaborate/explain/clarify"? → META-OPERATION (Rule 0.A)
   │  └─ Extract TOPIC only, drop entities
   │
   └─ Contains "categorize/break down/show for/filter by"? → NEW QUERY (Rule 0.B)
      └─ Preserve ALL entities + add new dimension
   ═══════════════════════════════════════════════════════════════════════════════

1. **Resolve Pronouns**: Replace "it", "that", "ones", "this" with actual entities from context

   Examples (WhatsApp/Forum):
   - "Does it have a sunroof?" → "Haval Jolion sunroof feature"
   - "What about white ones?" → "Kia white color variant"

   Examples (DMS/Dealership):
   - "Show me the history for it" → "Show repair history for VIN ABC123XYZ4567890"
   - "What about that customer?" → "What about customer Ahmed Khan"

2. **Preserve Intent**: Keep the core question/intent from the original query

   Examples (WhatsApp/Forum):
   - "What about Lahore?" (intent: location change) → "Haval listings in Lahore"
   - "And the price?" (intent: pricing) → "Kia price Pakistan"

   Examples (DMS/Dealership):
   - "What about December?" (intent: time filter) → "December FFS inspections dealer D001"
   - "And the warranty claims?" (intent: warranty data) → "warranty claims dealer D001"

3. **CRITICAL - Reference/Citation Requests** (High Priority):
   When user asks for "references", "sources", "citations", "examples", "proof", "evidence":
   → They want supporting data for the TOPIC just discussed
   → You MUST preserve the TOPIC from previous message
   → You MUST preserve ALL CUSTOMER/ENTITY NAMES mentioned in previous response

   Examples (WhatsApp/Forum):
   - Previous: "delivery timeline quoted to customers"
   - User: "can you please provide the references?"
   - Reformulate: "Haval H6 delivery timeline references customer quotes"

   - Previous: Response mentions "Shariq, Ahmed, Usman complained about delays"
   - User: "provide references of the customers you mentioned"
   - Reformulate: "Haval H6 customer chats Shariq Ahmed Usman delivery delay references"

   Examples (DMS/Dealership):
   - Previous: "3 vehicles failed FFS inspection"
   - User: "show me the references"
   - Reformulate: "vehicles failed FFS inspection details references"

   - Previous: "Dealer D001 has highest customer satisfaction"
   - User: "can you provide the sources?"
   - Reformulate: "dealer D001 customer satisfaction sources evidence"

4. **Carry Forward Context ONLY if Relevant**:
   - Car model name (H6, Jolion, Tank, Picanto etc.) → ONLY if discussing car features/pricing
   - Date or date range if mentioned → ONLY if discussing time-based queries
   - Customer/User name → ONLY if asking about that specific person
   - Dealer ID (D001, D002) → ONLY if asking about that specific dealer
   - VIN number → ONLY if asking about that specific vehicle

   **CRITICAL**: Do NOT mix contexts!

   Examples (WhatsApp/Forum):
   - If user asks "Show me Ahmed's chat" after discussing H6 → DO NOT add "Haval H6" to the query
   - If user switches topic → DO NOT carry forward unrelated context
   - If user asks about location after discussing features → Replace feature context with location

   Examples (DMS/Dealership):
   - If user asks "Show FFS records" after discussing dealer D001 → Include dealer D001
   - If user switches from dealer D001 to dealer D002 → REPLACE dealer, don't add both
   - If user asks "What about warranty?" after FFS query → Switch topic completely

5. **Optimize for Search**: Use keywords that help vector similarity matching

   Examples (WhatsApp/Forum):
   - Add "Pakistan" for local queries
   - Use synonyms: "sunroof" → "sunroof panoramic roof"
   - Add context: "price" → "price cost pricing"

   Examples (DMS/Dealership):
   - Use abbreviations: "First Free Service" → "FFS inspection"
   - Add entity types: "D001" → "dealer D001"
   - Expand technical terms: "RO" → "repair order"

6. **Handle Topic Switches Intelligently**:

   Examples (WhatsApp/Forum):
   - If user switches from car discussion to user chat query → DO NOT mix contexts
   - If user switches from Karachi to Lahore → REPLACE location, don't add both
   - If user switches from price to features → REPLACE topic, don't add both

   Examples (DMS/Dealership):
   - If user switches from FFS to repair orders → REPLACE service type, don't add both
   - If user switches from dealer D001 to dealer D002 → REPLACE dealer, don't add both
   - If user switches from December to January → REPLACE date range, don't add both

7. **CRITICAL - Customer Name Preservation**:
   If previous conversation mentions customer/person names:
   → You MUST include ALL names in reformulated query
   → Look for structured format: "Names: Ahmed, Shariq, Usman"
   → Include in query: "customer chats Ahmed Shariq Usman references"
   → NEVER drop names - they are crucial for filtering!

   This applies to BOTH WhatsApp customer chats AND DMS customer records.

8. **Keep it Concise**: 5-15 words max, focused on search keywords

**DOMAIN CONTEXT**:
═════════════════════════════════════════════════════════════════════════════
- Company: {company_name}

**Automotive (WhatsApp/Forum/Reddit)**:
- Common models: H6, Jolion, Tank 300, Tank 500, Picanto, Sportage
- Common topics: price, features, availability, listings, reviews, issues, service
- Data sources: Forum posts, WhatsApp customer chats, Reddit discussions

**Dealership Management System (DMS)**:
- Common entities: FFS (First Free Service), repair orders, warranty claims, vehicle inspections
- Common dimensions: dealer (D001, D002), service advisor, vehicle model, VIN
- Common metrics: count, revenue, customer satisfaction, completion time
- Common operations: categorize by dealer, break down by month, filter by status
═════════════════════════════════════════════════════════════════════════════


**PREVIOUS CONVERSATION**:
{history_context}

**USER'S VAGUE QUERY**: "{query}"

**CRITICAL REMINDERS**:
1. If query has "categorize/break down/complete list/full list/with VIN/for the above" → It's a NEW QUERY with more details!
   **YOU MUST COPY THE ENTIRE PREVIOUS QUERY DESCRIPTION!** Don't say "above data" - say exactly what data!
   Example: "Vehicles where free service followed by immediate repair visit with VIN numbers" ✅
   NOT: "complete list breakdown with VIN numbers for above data" ❌

2. If query has "summarize/elaborate/explain more" → It's a META-OP, preserve topic only!

3. If history contains "Names: [list]", include ALL names in reformulated query

4. If user asks for "references/sources/citations", preserve topic + names from previous message

5. Never drop customer names - they are used for filtering retrieval!

6. For DMS queries, preserve dealer IDs, VINs, and date ranges if relevant

7. **MOST CRITICAL**: When user says "for the above", look at the PREVIOUS USER QUERY (not assistant answer)
   and copy the COMPLETE description word-for-word!

**YOUR REFORMULATED QUERY** (standalone, search-optimized, 5-15 words):
"""

    messages = [{"role": "user", "content": reformulation_prompt}]

    try:
        response = llm.generate(messages, max_tokens=200, temperature=0.2)
        reformulated = response.content.strip()

        # Clean up the reformulated query
        reformulated = _clean_reformulated_query(reformulated, query)

        print(f"[QueryReformulator] ✅ Reformulation successful")
        print(f"[QueryReformulator]   Original: '{query}'")
        print(f"[QueryReformulator]   Reformulated: '{reformulated}'")

        return reformulated

    except Exception as e:
        print(f"[QueryReformulator] ❌ Error during reformulation: {e}")
        # Fallback: Use original query with company name
        fallback = f"{company_name} {query}"
        print(f"[QueryReformulator]   Fallback: '{fallback}'")
        return fallback


def _build_reformulation_context(
    chat_history: List[Dict[str, str]],
    max_messages: int = 4,
    current_query: str = "",
    compression_llm: Optional[BaseLLMClient] = None
) -> str:
    """
    Build focused context for query reformulation.

    Strategy:
    - Include ALL messages (user + assistant) for context
    - Smart compression for assistant responses:
      * If compression_llm provided AND current_query has reference terms:
        → Use LLM to extract relevant portions semantically
      * Otherwise:
        → Simple truncation to first 100 chars
    - This handles "summarize the above" / "explain that" queries

    Args:
        chat_history: Recent conversation messages
        max_messages: Maximum messages to include (default: 4 = 2 rounds)
        current_query: Current user query (to extract relevant context)
        compression_llm: Optional LLM for semantic compression (GPT-4o-mini recommended)

    Returns:
        Formatted context string with smart compression
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

        # Smart compression for assistant responses (use same logic as intent classifier)
        if role == "Assistant":
            # Import the compression function from intent_classifier
            from .intent_classifier import _compress_assistant_response
            content = _compress_assistant_response(
                response=content,
                current_query=current_query,
                compression_llm=compression_llm
            )
        else:
            # User queries: truncate only if very long
            if len(content) > 200:
                content = content[:200] + "..."

        lines.append(f"{i}. {role}: {content}")

    return "\n".join(lines)


def _clean_reformulated_query(reformulated: str, original: str) -> str:
    """
    Clean and validate reformulated query.

    Removes common LLM artifacts and ensures quality.

    Args:
        reformulated: LLM-generated reformulated query
        original: Original user query

    Returns:
        Cleaned reformulated query
    """
    # Remove quotation marks
    reformulated = reformulated.strip('"\'')

    # Remove common LLM prefixes
    prefixes_to_remove = [
        "Reformulated query:",
        "Query:",
        "Standalone query:",
        "Search query:",
        "Output:",
    ]

    for prefix in prefixes_to_remove:
        if reformulated.lower().startswith(prefix.lower()):
            reformulated = reformulated[len(prefix):].strip()
            reformulated = reformulated.lstrip(':').strip()

    # Remove trailing punctuation except question marks
    while reformulated and reformulated[-1] in ['.', ',', ';']:
        reformulated = reformulated[:-1].strip()

    # If reformulation is too short or empty, return original
    if len(reformulated) < 3:
        return original

    # If reformulation is identical to original, no need to reformulate
    if reformulated.lower() == original.lower():
        return original

    return reformulated


def extract_entities_from_history(
    chat_history: List[Dict[str, str]],
    enrichment_state=None
) -> Dict[str, Optional[str]]:
    """
    Extract key entities from chat history for context carryover.

    DYNAMIC EXTRACTION - No hardcoded models/locations.
    Uses enrichment_state variants if available, otherwise generic pattern matching.

    Args:
        chat_history: Recent conversation messages
        enrichment_state: Optional EnrichmentState with known variants/locations

    Returns:
        Dict with extracted entities (for debugging/validation only)
    """
    import re

    entities = {
        "car_model": None,
        "location": None,
        "topic": None,  # Generic topic (price, features, etc.)
    }

    # Get car models from enrichment state if available
    car_models = []
    if enrichment_state and hasattr(enrichment_state, 'known_variants'):
        car_models = list(enrichment_state.known_variants.keys())

    # Common Pakistani cities (fallback)
    common_locations = ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad"]

    # Scan recent USER messages only (reverse order = most recent first)
    for msg in reversed(chat_history):
        if msg["role"].lower() != "user":
            continue

        content = msg["content"]

        # Extract car model (from enrichment state or generic pattern)
        if not entities["car_model"] and car_models:
            for model in car_models:
                if re.search(rf'\b{model}\b', content, re.IGNORECASE):
                    entities["car_model"] = model
                    break

        # Extract location
        if not entities["location"]:
            for location in common_locations:
                if re.search(rf'\b{location}\b', content, re.IGNORECASE):
                    entities["location"] = location
                    break

        # Extract generic topic (price, features, etc.)
        if not entities["topic"]:
            topics = ["price", "features", "mileage", "fuel", "safety", "warranty", "sunroof"]
            for topic in topics:
                if re.search(rf'\b{topic}\b', content, re.IGNORECASE):
                    entities["topic"] = topic
                    break

    return entities
