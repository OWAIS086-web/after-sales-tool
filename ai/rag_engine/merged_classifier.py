# ai/rag_engine/merged_classifier.py
"""
Merged Classifier Module - Single LLM call for domain + format + optimization

Combines 3 separate LLM calls into 1:
- Domain classification (in_domain, out_of_domain, small_talk)
- Format instruction detection (bullet points, 200 words, etc.)
- Query optimization (search sub-queries for vector retrieval)

Strategy:
1. REGEX FIRST (instant, 0 tokens) - handles ~80% of domain classification
2. If regex returns in_domain -> run merged classifier for format + optimization only
3. If regex returns out_of_domain/small_talk -> skip LLM entirely
4. If regex returns None (ambiguous) -> run full merged classifier including domain

Savings: ~25% faster pre-retrieval phase (verified by experiment)
"""

from __future__ import annotations
import json
from typing import Dict, Any, List, Optional
from ai.llm_client import BaseLLMClient
from .regex_classifiers import classify_query_domain_regex


def get_merged_classifier_prompt(
    question: str,
    company_id: str = "haval",
    source: str = "forum",
    include_domain: bool = True,
    current_time: str = None,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Build unified prompt for merged classification.

    Args:
        question: User query
        company_id: Company identifier
        source: Data source (forum, whatsapp, reddit)
        include_domain: If False, skip domain classification (regex already handled it)
        current_time: Current datetime in ISO format for time window extraction
        chat_history: Recent conversation history for context-aware classification

    Returns:
        Prompt string for LLM
    """
    from config import get_company_config
    from datetime import datetime

    try:
        company_config = get_company_config(company_id)
        company_name = company_config.full_name
        variants = company_config.variants if hasattr(company_config, 'variants') else []
    except Exception:
        company_name = company_id.title()
        variants = []

    variant_examples = ", ".join(variants[:5]) if variants else "various models"

    source_context = {
        "whatsapp": "WhatsApp customer service conversations (bookings, delivery, support, complaints)",
        "pakwheels": "Forum discussions (owner experiences, reviews, comparisons)",
        "forum": "Forum discussions (owner experiences, reviews, comparisons)",
        "reddit": "Reddit community discussions (reviews, complaints, comparisons)",
        "reddit_lucid": "Reddit community discussions (reviews, complaints, comparisons)"
    }.get(source, "customer data")

    # Get current time for time window extraction
    if current_time is None:
        current_time = datetime.now().isoformat()

    # Build history context for follow-up detection
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
  → AND current query uses reference terms ("above", "point", "it", "that", "summarize", "tell me more") or refers to previous chat
  → THEN classify as **in_domain** ✅ (it's a follow-up to an in-domain conversation)

**Examples**:
Previous: "Haval H6 problems on the forum" [in_domain]
Current: "Summarize point 3 above" → **in_domain** ✅ (follow-up)
"""

    # Build domain classification section if needed
    domain_section = ""
    domain_json_field = ""
    if include_domain:
        domain_section = f"""
TASK 1: DOMAIN CLASSIFICATION
──────────────────────────────────────────────────────────────────────
Classify into: "in_domain", "out_of_domain", or "small_talk"
- in_domain: {company_name} vehicles, automotive topics, {source_context.split('(')[0]}, analysis/recommendations based on customer data
- out_of_domain: Essays, recipes, entertainment, general knowledge (world history, science, geography - NOT analyzing vehicle history/data), unrelated topics
- small_talk: Greetings, thanks

**CRITICAL**: Questions asking for marketing strategies, recommendations, or analysis based on customer feedback/opinions are IN_DOMAIN ✅{history_context}
"""
        domain_json_field = '"domain": "in_domain" | "out_of_domain" | "small_talk",'

    prompt = f"""You are a query analyzer for {company_name} customer support (Pakistan).

**USER QUERY**: "{question}"
**DATA SOURCE**: {source_context}
**CURRENT_TIME**: {current_time}
{domain_section}
TASK {'2' if include_domain else '1'}: FORMAT DETECTION
──────────────────────────────────────────────────────────────────────
Detect EXPLICIT format requests (HOW to format, not WHAT content):

Categories: Word count (in 200 words), List style (bullet points, numbered), Table format, Document type (report, memo), Length (briefly, in detail), Tone (simple language)

✅ Examples (detect format):
- "Summarize in 200 words" → "in 200 words"
- "Give bullet points about issues" → "as bullet points"
- "Create table of top 10" → "table format"

❌ Examples (ignore, these are CONTENT):
- "What are top 10 problems?" → null (asking for top 10 is content, not format)
- "Tell me about brakes" → null (no format specified)

TASK {'3' if include_domain else '2'}: SEARCH OPTIMIZATION + TIME EXTRACTION
──────────────────────────────────────────────────────────────────────
Generate 1-3 search queries for vector retrieval.

TIME WINDOW EXTRACTION:
- If query mentions time ("yesterday", "last week", "in May 2025", "last month") or any other time reference:
  Extract [start_datetime, end_datetime] relative to CURRENT_TIME
  **CRITICAL**: Apply SAME time window to ALL search queries
- If no time mentioned: set both to null for ALL queries

✅ Example with time:
Query: "Show me complaints from yesterday"
CURRENT_TIME: 2024-05-15T10:00:00
→ start_datetime: "2024-05-14T00:00:00"
→ end_datetime: "2024-05-14T23:59:59"

✅ Example without time:
Query: "What are brake issues?"
→ start_datetime: null, end_datetime: null

OPTIMIZATION RULES:
- Remove filler ("can you", "please", "I want")
- Keep core keywords and intent
- Focus on: {source_context}

YOUR RESPONSE (JSON only, no explanation):
{{
  {domain_json_field}
  "format_instruction": "format string" | null,
  "search_queries": [
    {{
      "query": "optimized search text",
      "start_datetime": "YYYY-MM-DDTHH:MM:SS" | null,
      "end_datetime": "YYYY-MM-DDTHH:MM:SS" | null
    }}
  ]
}}"""

    return prompt


def run_merged_classifier(
    question: str,
    llm: BaseLLMClient,
    company_id: str = "haval",
    source: str = "forum",
    include_domain: bool = True,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Run merged classifier - single LLM call for domain + format + optimization.

    Args:
        question: User query
        llm: LLM client for classification
        company_id: Company identifier
        source: Data source (forum, whatsapp, reddit)
        include_domain: If False, domain was already classified by regex
        chat_history: Recent conversation history for context-aware classification

    Returns:
        {
            "domain": "in_domain" | "out_of_domain" | "small_talk" | None,
            "format_instruction": str | None,
            "search_queries": List[Dict] with query, start_datetime, end_datetime
        }
    """
    from datetime import datetime

    current_time = datetime.now().isoformat()
    prompt = get_merged_classifier_prompt(question, company_id, source, include_domain, current_time, chat_history)
    messages = [{"role": "user", "content": prompt}]

    try:
        response = llm.generate(messages, max_tokens=400, temperature=0.0)
        content = response.content.strip()

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        result = json.loads(content)

        # Extract search queries (now with time windows)
        search_queries = result.get("search_queries", [])

        # Normalize to list of dicts if simple strings returned
        if search_queries and isinstance(search_queries[0], str):
            search_queries = [{"query": q, "start_datetime": None, "end_datetime": None} for q in search_queries]
        elif not search_queries:
            search_queries = [{"query": question, "start_datetime": None, "end_datetime": None}]

        # Validate and provide defaults
        return {
            "domain": result.get("domain") if include_domain else None,
            "format_instruction": result.get("format_instruction"),
            "search_queries": search_queries
        }

    except json.JSONDecodeError as e:
        print(f"  [MergedClassifier] JSON parse error: {e}")
        return {
            "domain": "in_domain" if include_domain else None,
            "format_instruction": None,
            "search_queries": [{"query": question, "start_datetime": None, "end_datetime": None}]
        }
    except Exception as e:
        print(f"  [MergedClassifier] Error: {e}")
        return {
            "domain": "in_domain" if include_domain else None,
            "format_instruction": None,
            "search_queries": [{"query": question, "start_datetime": None, "end_datetime": None}]
        }


def classify_merged_with_regex_first(
    question: str,
    llm: BaseLLMClient,
    company_id: str = "haval",
    source: str = "forum",
    data_sources: Optional[List[str]] = None,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Main entry point: Regex first, then merged LLM classifier.

    Flow:
    1. Try regex for domain classification (instant, 0 tokens)
    2. If regex returns in_domain -> run merged classifier (format + optimization only)
    3. If regex returns out_of_domain/small_talk -> return immediately (skip LLM)
    4. If regex returns None (ambiguous) -> run full merged classifier (domain + format + optimization)

    Args:
        question: User query
        llm: LLM client for classification
        company_id: Company identifier
        source: Data source (forum, whatsapp, reddit)
        data_sources: Available data sources for regex context
        chat_history: Recent conversation history for context-aware classification

    Returns:
        {
            "domain": "in_domain" | "out_of_domain" | "small_talk",
            "domain_source": "regex" | "llm",
            "format_instruction": str | None,
            "search_queries": List[str]
        }
    """
    import time

    total_start = time.perf_counter()

    # =========================================================================
    # STEP 1: REGEX DOMAIN CLASSIFICATION (instant, 0 tokens)
    # =========================================================================
    mode = "auto"
    if data_sources:
        if "pakwheels" in data_sources:
            mode = "pakwheels"
        elif "whatsapp" in data_sources:
            mode = "whatsapp"
        elif "reddit" in data_sources:
            mode = "reddit"
    elif source:
        mode = source

    regex_start = time.perf_counter()
    regex_result = classify_query_domain_regex(
        question=question,
        company_id=company_id,
        mode=mode
    )
    regex_time = (time.perf_counter() - regex_start) * 1000

    # =========================================================================
    # STEP 2: HANDLE BASED ON REGEX RESULT
    # =========================================================================

    if regex_result in ['out_of_domain', 'small_talk']:
        # Fast exit - no LLM needed at all!
        # print(f"  [MergedClassifier] Regex fast-exit: {regex_result.upper()} (0 tokens)")
        return {
            "domain": regex_result,
            "domain_source": "regex",
            "format_instruction": None,
            "search_queries": [{"query": question, "start_datetime": None, "end_datetime": None}]
        }

    if regex_result == 'in_domain':
        # Regex confirmed in_domain -> run merged classifier for format + optimization only
        llm_start = time.perf_counter()
        merged_result = run_merged_classifier(
            question=question,
            llm=llm,
            company_id=company_id,
            source=source,
            include_domain=False,  # Skip domain, regex already confirmed
            chat_history=chat_history
        )
        llm_time = (time.perf_counter() - llm_start) * 1000
        total_time = (time.perf_counter() - total_start) * 1000

        # Compact single-line log
        # print(f"  [MergedClassifier] Regex:IN_DOMAIN LLM:{llm_time:.0f}ms Total:{total_time:.0f}ms")

        return {
            "domain": "in_domain",  # From regex
            "domain_source": "regex",
            "format_instruction": merged_result.get("format_instruction"),
            "search_queries": merged_result.get("search_queries", [{"query": question, "start_datetime": None, "end_datetime": None}])
        }

    # =========================================================================
    # STEP 3: REGEX AMBIGUOUS -> RUN FULL MERGED CLASSIFIER
    # =========================================================================
    llm_start = time.perf_counter()
    merged_result = run_merged_classifier(
        question=question,
        llm=llm,
        company_id=company_id,
        source=source,
        include_domain=True,  # Include domain classification
        chat_history=chat_history
    )
    llm_time = (time.perf_counter() - llm_start) * 1000
    total_time = (time.perf_counter() - total_start) * 1000
    domain = merged_result.get("domain", "in_domain")

    # print(f"  [MergedClassifier] Regex:ambiguous LLM:{domain.upper()} {llm_time:.0f}ms Total:{total_time:.0f}ms")

    return {
        "domain": domain,
        "domain_source": "llm",
        "format_instruction": merged_result.get("format_instruction"),
        "search_queries": merged_result.get("search_queries", [{"query": question, "start_datetime": None, "end_datetime": None}])
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'classify_merged_with_regex_first',
    'run_merged_classifier',
    'get_merged_classifier_prompt',
]
