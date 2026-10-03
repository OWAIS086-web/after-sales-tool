"""
LLM-Based Keyword Extraction Module

Uses LLM to robustly extract keywords for citation filtering.
Handles edge cases automatically: short terms, multi-word phrases, negation, synonyms.

Advantages over rule-based extraction:
- Context-aware (understands "fuel economy" as a phrase)
- Expands synonyms ("mileage" for "fuel economy")
- Detects sentiment ("issues" → negative filter)
- No maintenance (adapts to new car models/terms automatically)
"""

from typing import List, Dict, Optional
from ai.llm_client import BaseLLMClient


def extract_keywords_with_llm(
    query: str,
    llm: BaseLLMClient,
    max_keywords: int = 5,
    include_synonyms: bool = True
) -> Dict[str, any]:
    """
    Extract keywords from user query using LLM.

    Args:
        query: User query string
        llm: LLM client for keyword extraction
        max_keywords: Maximum number of keywords to extract (default: 5)
        include_synonyms: Whether to include related synonyms (default: True)

    Returns:
        Dictionary with:
        - 'keywords': List of extracted keywords (single words + multi-word phrases)
        - 'sentiment_filter': 'negative', 'positive', or None
        - 'synonyms': List of related terms (if include_synonyms=True)

    Examples:
        >>> extract_keywords_with_llm("DCT transmission issues", llm)
        {
            'keywords': ['DCT', 'transmission'],
            'sentiment_filter': 'negative',
            'synonyms': ['dual clutch', 'gearbox', 'gear shift']
        }

        >>> extract_keywords_with_llm("fuel economy", llm)
        {
            'keywords': ['fuel economy'],
            'sentiment_filter': None,
            'synonyms': ['mileage', 'fuel average', 'consumption']
        }
    """
    prompt = f"""You are an automotive keyword extraction specialist. Extract keywords from user queries for filtering automotive discussion data.

**YOUR TASK:**
Extract the MOST SPECIFIC keywords for filtering automotive conversations (forum posts, WhatsApp messages). Focus on PRECISION - only extract keywords that meaningfully narrow down the search.

**CRITICAL RULES:**

1. **Multi-Word Phrases**: Keep common phrases together (don't split)
   - "fuel economy" → Keep as ONE keyword: "fuel economy"
   - "brake fluid" → Keep as ONE keyword: "brake fluid"
   - "engine oil" → Keep as ONE keyword: "engine oil"
   - "after sales service" → Keep as ONE phrase if it's about a SPECIFIC after-sales issue

2. **Short Technical Terms**: ALWAYS include automotive abbreviations (even if ≤3 chars)
   - Transmissions: DCT, CVT, AMT, AT, MT
   - Drivetrain: AWD, 4WD, 2WD, FWD, RWD
   - Safety: ABS, ESP, EBD, TCS, ESC
   - Tech: AC, GPS, USB, LED, HID, DRL
   - Fuel: LPG, CNG, HEV, PHEV, ICE
   - Models: H6, H9, Rio (single/short model names)
   - Other: RPM, KMH, BHP, PSI, NVH

3. **ALWAYS SKIP - Too Generic / Broad**:

   a) **Question Words & Quantifiers**:
      - what, which, where, when, how, why, who
      - most, top, all, some, any, many, few
      - first, last, main, major, best, worst

   b) **Reference Words**:
      - customer, customers, user, users, owner, owners
      - chat, chats, conversation, message, messages
      - post, posts, thread, comment, feedback, review

   c) **Generic Automotive Terms** (too broad - matches EVERYTHING):
      - car, cars, vehicle, vehicles, model, models
      - auto, automobile, motor

   d) **Brand Names** (ALWAYS SKIP unless part of specific model):
      - Haval, Kia, Toyota, Honda, Suzuki, Nissan, Mazda, Hyundai, Ford, Chevrolet
      - MG, Changan, Proton, Geely, BYD, Cherry
      - **Exception**: Keep if it's a model name itself (e.g., "Sportage", "Corolla")

      **Brand Name Rules**:
      - "Haval H6" → Keep "H6" ONLY (skip "Haval")
      - "Kia Sportage" → Keep "Sportage" ONLY (skip "Kia")
      - "Toyota Camry" → Keep "Camry" ONLY (skip "Toyota")
      - "Haval battery issues" → Keep "battery" ONLY (skip "Haval")

   e) **Generic Service Terms** (too broad unless part of specific issue):
      - after sales, aftersales, after-sales (unless "after sales SERVICE issue")
      - service, service center, dealership, dealer
      - company, manufacturer, brand
      - **Exception**: Keep if combined with specific issue like "after sales delay" or "service center closed"

   f) **Generic Problem Words** (extract as SENTIMENT instead):
      - issue, issues, problem, problems
      - complaint, complaints, concern, concerns
      - These become sentiment_filter: "negative", NOT keywords

4. **Sentiment Detection** (problem/praise words → sentiment filter, NOT keywords):

   **NEGATIVE Sentiment Signals**:
   - issue, issues, problem, problems, fault, faults
   - complaint, complaints, defect, defects, failure, failures
   - broken, damaged, faulty, error, errors, bug, bugs
   → Set sentiment_filter: "negative"

   **POSITIVE Sentiment Signals**:
   - praise, excellent, great, amazing, awesome, fantastic
   - love, loved, satisfied, happy, pleased
   - best, perfect, flawless, outstanding
   → Set sentiment_filter: "positive"

   **Otherwise**: sentiment_filter: null

5. **Negation Handling** (reverse logic):
   - "NOT battery issues" → SKIP "battery" (negated keyword)
   - "without problems" → sentiment_filter: "positive" (absence of problems = positive)
   - "no complaints" → sentiment_filter: "positive" (inverted)
   - "cars that DON'T have X" → SKIP X, sentiment_filter: "positive"

6. **Synonym Expansion** (ONLY if include_synonyms=True):
   - Use underscores for multi-word synonyms (matches enrichment tags format)
   - Max 4-5 most relevant automotive-specific synonyms

   **Examples**:
   - "fuel economy" → ["mileage", "fuel_average", "consumption", "kmpl"]
   - "battery" → ["battery_drain", "battery_life", "battery_health", "battery_failure"]
   - "brake" → ["braking", "brake_pad", "brake_fluid", "brake_disc", "brake_noise"]
   - "AC" → ["air_conditioning", "cooling", "climate_control", "AC_compressor"]
   - "engine" → ["engine_noise", "engine_vibration", "engine_performance", "engine_oil"]

   **Synonym Quality Rules**:
   - Use underscores (battery_drain, not "battery drain") to match tag format
   - Only include SPECIFIC automotive terms, not generic words
   - Prefer technical terms over colloquial ones

**OUTPUT FORMAT (JSON):**
{{
  "keywords": ["keyword1", "multi word phrase", "H6"],
  "sentiment_filter": "negative" | "positive" | null,
  "synonyms": ["synonym1", "synonym2"] | []
}}

**EXAMPLES:**

Example 1 - Short technical terms + brand filtering:
Query: "DCT transmission problems in Haval H6"
Output:
{{
  "keywords": ["DCT", "transmission", "H6"],
  "sentiment_filter": "negative",
  "synonyms": ["dual_clutch", "gearbox", "gear_shift", "transmission_fluid"]
}}
Note: "Haval" SKIPPED (brand name), "H6" KEPT (specific model), "problems" → sentiment

Example 2 - Multi-word phrase preservation:
Query: "fuel economy"
Output:
{{
  "keywords": ["fuel economy"],
  "sentiment_filter": null,
  "synonyms": ["mileage", "fuel_average", "consumption", "kmpl"]
}}

Example 3 - Problem words → sentiment filter:
Query: "brake issues"
Output:
{{
  "keywords": ["brake"],
  "sentiment_filter": "negative",
  "synonyms": ["braking", "brake_pad", "brake_fluid", "brake_disc", "brake_noise"]
}}
Note: "issues" → sentiment_filter, NOT a keyword

Example 4 - Generic terms filtered:
Query: "What are the most top customer complaints about battery from after sales?"
Output:
{{
  "keywords": ["battery"],
  "sentiment_filter": "negative",
  "synonyms": ["battery_drain", "battery_life", "battery_health", "battery_failure"]
}}
Note: SKIPPED: "what", "most", "top", "customer", "complaints" (sentiment), "after sales" (too generic)

Example 5 - Negation handling:
Query: "Cars WITHOUT battery issues"
Output:
{{
  "keywords": [],
  "sentiment_filter": "positive",
  "synonyms": []
}}
Note: "battery" SKIPPED (negated by "WITHOUT"), "issues" → positive sentiment (inverted)

Example 6 - Positive sentiment:
Query: "Show me positive reviews about AC performance"
Output:
{{
  "keywords": ["AC", "performance"],
  "sentiment_filter": "positive",
  "synonyms": ["air_conditioning", "cooling", "climate_control", "AC_compressor"]
}}

Example 7 - Brand + specific issue (your exact query):
Query: "what are the most top complains about battery issues from haval after sales?"
Output:
{{
  "keywords": ["battery"],
  "sentiment_filter": "negative",
  "synonyms": ["battery_drain", "battery_life", "battery_health", "battery_failure"]
}}
Note: SKIPPED: "what", "most", "top", "complains" (sentiment), "haval" (brand), "after sales" (generic service term)
Note: KEPT: "battery" (specific component)
Note: "issues" + "complains" → sentiment_filter: "negative"

**USER QUERY:** "{query}"

Extract keywords following ALL rules above. Return ONLY valid JSON (no markdown, no extra text).
"""

    messages = [{"role": "user", "content": prompt}]

    try:
        response = llm.generate(messages, max_tokens=200, temperature=0.0)
        content = response.content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        # Parse JSON response
        import json
        result = json.loads(content)

        # Validate and clean result
        keywords = result.get("keywords", [])
        sentiment_filter = result.get("sentiment_filter")
        synonyms = result.get("synonyms", []) if include_synonyms else []

        # Limit keywords to max_keywords
        if len(keywords) > max_keywords:
            keywords = keywords[:max_keywords]

        # print(f"[Keyword Extraction] Query: '{query}'")
        # print(f"  Keywords: {keywords}")
        # print(f"  Sentiment: {sentiment_filter}")
        # if synonyms:
        #     print(f"  Synonyms: {synonyms}")

        return {
            "keywords": keywords,
            "sentiment_filter": sentiment_filter,
            "synonyms": synonyms
        }

    except Exception as e:
        print(f"[Keyword Extraction] Error: {e}")
        print(f"[Keyword Extraction] Falling back to simple extraction")

        # Fallback: Simple word extraction (no LLM)
        words = query.lower().split()
        simple_keywords = [
            w.strip('?.,!;:()')
            for w in words
            if len(w) > 3 and w.lower() not in {
                'what', 'which', 'where', 'when', 'show', 'tell',
                'customer', 'chat', 'message', 'about', 'from', 'with'
            }
        ]

        return {
            "keywords": simple_keywords[:max_keywords],
            "sentiment_filter": None,
            "synonyms": []
        }


def apply_keyword_filter(
    blocks: List,
    keywords: List[str],
    synonyms: List[str] = None,
    sentiment_filter: Optional[str] = None
) -> List:
    """
    Filter blocks by keywords, synonyms, and sentiment.

    Args:
        blocks: List of RetrievedBlock objects
        keywords: Primary keywords to match
        synonyms: Related synonyms to also match (optional)
        sentiment_filter: 'negative', 'positive', or None

    Returns:
        Filtered list of blocks matching keywords/synonyms/sentiment

    Example:
        >>> keywords = ["battery"]
        >>> synonyms = ["battery_drain", "battery_life"]
        >>> filtered = apply_keyword_filter(blocks, keywords, synonyms, sentiment_filter="negative")
    """
    import re

    if not keywords and not synonyms and not sentiment_filter:
        return blocks  # No filters, return all

    # Combine keywords and synonyms
    all_keywords = keywords + (synonyms or [])

    relevant_blocks = []

    for rb in blocks:
        block_tags = getattr(rb.block, 'aggregated_tags', [])
        block_text = getattr(rb.block, 'flattened_text', '').lower()
        block_sentiment = getattr(rb.block, 'dominant_sentiment', None)

        # Check sentiment filter first
        if sentiment_filter:
            if block_sentiment and block_sentiment.lower() != sentiment_filter.lower():
                continue  # Sentiment doesn't match, skip block

        # Check keyword/synonym matches
        match_found = False

        for kw in all_keywords:
            kw_lower = kw.lower()

            # Tag match (substring is OK for tags)
            tag_match = any(kw_lower in tag.lower() for tag in block_tags)

            # Content match (use word boundaries to prevent false positives)
            # Handle multi-word phrases (e.g., "fuel economy")
            if ' ' in kw_lower:
                # Multi-word phrase: use substring matching
                content_match = kw_lower in block_text
            else:
                # Single word: use word boundaries
                pattern = rf'\b{re.escape(kw_lower)}\b'
                content_match = bool(re.search(pattern, block_text, re.IGNORECASE))

            if tag_match or content_match:
                match_found = True
                break

        if match_found:
            relevant_blocks.append(rb)

    return relevant_blocks
