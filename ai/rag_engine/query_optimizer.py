# ai/rag_engine/query_optimizer.py
"""
Query Optimization Module

Handles query decomposition and optimization:
- Splits complex queries into focused sub-queries
- Extracts time windows from natural language
- Generates semantic filters (variants, sentiments, tags)
- Produces optimized query structures for vector search
"""

from __future__ import annotations
from typing import List, Dict, Optional, Any
from datetime import datetime
from zoneinfo import ZoneInfo
import json

from ai.vector_store import ChromaVectorStore
from ai.llm_client import BaseLLMClient
from ai.enrichment import EnrichmentState


def extract_json_block(raw: str) -> Any:
    """
    Try to load JSON even if the model wraps it with extra text.

    Attempts:
    1. Direct JSON parsing
    2. Extract content between first '{' and last '}'

    Args:
        raw: Raw string potentially containing JSON

    Returns:
        Parsed JSON object or None if parsing fails
    """
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        # Try to locate the first '{' and last '}' and parse that slice
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = raw[start : end + 1]
            try:
                return json.loads(snippet)
            except Exception:
                return None
        return None


def parse_iso_or_none(s: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO 8601 datetime string, handling timezone awareness.

    Args:
        s: ISO format datetime string

    Returns:
        Timezone-aware datetime (Pakistan timezone) or None if parsing fails
    """
    if not s:
        return None
    if not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        # Make timezone-aware if naive (use Pakistan timezone)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("Asia/Karachi"))
        return dt
    except Exception:
        return None


def format_range(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> str:
    """
    Format time range for human-readable display.

    Args:
        start_dt: Range start datetime
        end_dt: Range end datetime

    Returns:
        Formatted string like "2024-01-15 to 2024-01-20" or "from 2024-01-15 onwards"
    """
    if start_dt and end_dt:
        if start_dt.date() == end_dt.date():
            return start_dt.date().isoformat()
        return f"{start_dt.date().isoformat()} to {end_dt.date().isoformat()}"
    if start_dt:
        return f"from {start_dt.date().isoformat()} onwards"
    if end_dt:
        return f"up to {end_dt.date().isoformat()}"
    return "all time"


def has_enriched_metadata(vector_store: ChromaVectorStore) -> bool:
    """
    Check if vector store has meaningful variant/tags metadata.

    If no enrichment exists, we shouldn't ask LLM to produce filters
    as they would just zero out retrieval.

    Args:
        vector_store: Vector store to check

    Returns:
        True if enriched metadata exists
    """
    # Handle case when vector store is None (no data loaded yet)
    if vector_store is None:
        return False

    for b in vector_store.blocks_by_id.values():
        if getattr(b, "aggregated_tags", None):
            return True
        v = getattr(b, "dominant_variant", None)
        if v and v != "Unknown":
            return True
    return False


def optimize_queries(
    question: str,
    vector_store: ChromaVectorStore,
    llm: BaseLLMClient,
    state: Optional[EnrichmentState],
    is_broad: bool,
    company_id: str = "haval"
) -> List[Dict[str, Any]]:
    """
    Use LLM to optimize user query into focused sub-queries.

    Process:
    1. Split question into 1-5 focused sub-queries if needed
    2. Create semantic-search-friendly query text
    3. Extract time windows (start_datetime, end_datetime)
    4. Generate metadata filters (variants, sentiments, tags)

    Args:
        question: User's natural language question
        vector_store: Vector store to query
        llm: LLM client for optimization
        state: Enrichment state with known variants/tags
        is_broad: Whether this is a broad insight question
        company_id: Company identifier (e.g., "haval", "kia", "toyota")

    Returns:
        List of optimized query dicts with structure:
        {
            "query": "optimized query text",
            "start_dt": datetime | None,
            "end_dt": datetime | None,
            "variant_filter": ["PHEV"] or None,
            "sentiment_filter": ["negative"] or None,
            "tags_filter": ["problem_report"] or None,
        }
    """
    from config import get_company_config

    # Get company configuration
    try:
        company_config = get_company_config(company_id)
        company_name = company_config.full_name
    except Exception:
        company_name = company_id.title()

    now_iso = datetime.now().isoformat()
    has_filters = has_enriched_metadata(vector_store)

    # Use enrichment state as hint for LLM
    variants_list = sorted(list(state.variants)) if state else []
    tags_list = sorted(list(state.tags)) if state else []

    base_intro = (
        "You are a query optimisation assistant for a semantic search engine.\n"
        f"The search index contains Pakistani automotive discussions about {company_name} vehicles.\n\n"
        "The system stores posts as conversation blocks with timestamps and, when available,\n"
        "metadata such as variant, sentiment, and tags.\n"
    )

    if is_broad:
        task_description = (
            "TASK:\n"
            "1. Interpret the user question as a request for overall insights.\n"
            "   Generate 3–5 sub-queries, each focusing on DIFFERENT aspects, e.g.:\n"
            "   - transmission / DCT / gearbox problems\n"
            "   - fuel economy / running cost\n"
            "   - build quality / noise / comfort issues\n"
            "   - after-sales / dealership experiences\n"
            "   - availability / booking / delivery\n"
            "   Create only those that are clearly relevant.\n"
        )
    else:
        task_description = (
            "TASK:\n"
            "1. Decide whether the user question should be split into multiple\n"
            "   focused sub-questions (maximum 4). Split only if it clearly asks\n"
            "   about multiple distinct aspects (e.g., reliability, fuel economy,\n"
            "   and features in one sentence).\n"
        )

    # Time window instructions
    time_part = (
        "2. For each sub-question, produce a short, information-dense query\n"
        "   optimised for semantic vector search:\n"
        "   - Focus on key entities, nouns, and technical phrases.\n"
        "   - Drop politeness and filler words.\n"
        "   - Keep ~3–15 words per query.\n"
        "3. If the user question mentions time expressions (e.g. 'yesterday',\n"
        "   'last week', 'in May 2024'), interpret them relative to the\n"
        "   CURRENT_TIME shown below and derive an appropriate time window\n"
        "   [start_datetime, end_datetime] in ISO 8601 format (local time).\n"
        "   - **CRITICAL**: Apply this SAME time window to ALL sub-queries.\n"
        "     Do not create sub-queries with different or missing time constraints.\n"
        "   - If no specific time constraint is implied, set both to null for ALL sub-queries.\n"
    )

    # Filter instructions only if enriched metadata exists
    if has_filters:
        filter_part = (
            "4. Optionally propose filters for each sub-query when it makes sense:\n"
            "   - 'variant_filter': list of variant names if the question clearly\n"
            "      targets certain variants (e.g. PHEV, HEV, Jolion). Known examples:\n"
            f"      {variants_list or '[no pre-known variants; infer from context]'}\n"
            "   - 'sentiment_filter': a subset of ['positive', 'negative', 'mixed', 'neutral']\n"
            "      if the question is clearly about complaints, praise, etc.\n"
            "   - 'tag_filter': list of tag names capturing key themes, for example:\n"
            f"      {tags_list or '[no pre-known tags; infer compact snake_case tags]'}\n"
            "   Only use filters when the user question strongly implies them. Otherwise\n"
            "   set them to null or empty.\n"
        )

        json_schema = (
            "5. Return STRICT JSON with this schema and nothing else:\n"
            '   { "sub_queries": [\n'
            '       {\n'
            '         "query": "text",\n'
            '         "start_datetime": "YYYY-MM-DDTHH:MM:SS" or null,\n'
            '         "end_datetime": "YYYY-MM-DDTHH:MM:SS" or null,\n'
            '         "variant_filter": ["..."] or null,\n'
            '         "sentiment_filter": ["positive", ...] or null,\n'
            '         "tag_filter": ["tag1", "tag2", ...] or null\n'
            '       }\n'
            "     ] }\n"
        )

        sys_prompt = base_intro + task_description + time_part + filter_part + json_schema

        user_prompt = f"""CURRENT_TIME: {now_iso}

User question:
\"\"\"{question}\"\"\"

Now output ONLY valid JSON in the format:
{{
  "sub_queries": [
    {{
      "query": "query 1 here",
      "start_datetime": "YYYY-MM-DDTHH:MM:SS" or null,
      "end_datetime": "YYYY-MM-DDTHH:MM:SS" or null,
      "variant_filter": ["PHEV"] or null,
      "sentiment_filter": ["negative"] or null,
      "tag_filter": ["problem_report", "fuel_economy"] or null
    }}
  ]
}}"""
    else:
        # No metadata to filter on – keep it simple with only time windows
        json_schema = (
            "4. Return STRICT JSON with this schema and nothing else:\n"
            '   { "sub_queries": [\n'
            '       {\n'
            '         "query": "text",\n'
            '         "start_datetime": "YYYY-MM-DDTHH:MM:SS" or null,\n'
            '         "end_datetime": "YYYY-MM-DDTHH:MM:SS" or null\n'
            '       }\n'
            "     ] }\n"
        )

        sys_prompt = base_intro + task_description + time_part + json_schema

        user_prompt = f"""CURRENT_TIME: {now_iso}

User question:
\"\"\"{question}\"\"\"

Now output ONLY valid JSON in the format:
{{
  "sub_queries": [
    {{
      "query": "query 1 here",
      "start_datetime": "YYYY-MM-DDTHH:MM:SS" or null,
      "end_datetime": "YYYY-MM-DDTHH:MM:SS" or null
    }}
  ]
}}"""

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        resp = llm.generate(messages, max_tokens=1024, temperature=0.0)
        raw = (resp.content or "").strip()
    except Exception:
        # Fallback – no optimisation
        return [
            {
                "query": question,
                "start_dt": None,
                "end_dt": None,
                "variant_filter": None,
                "sentiment_filter": None,
                "tags_filter": None,
            }
        ]

    data = extract_json_block(raw)
    if not isinstance(data, dict):
        return [
            {
                "query": question,
                "start_dt": None,
                "end_dt": None,
                "variant_filter": None,
                "sentiment_filter": None,
                "tags_filter": None,
            }
        ]

    sub_queries = data.get("sub_queries")
    if not isinstance(sub_queries, list):
        return [
            {
                "query": question,
                "start_dt": None,
                "end_dt": None,
                "variant_filter": None,
                "sentiment_filter": None,
                "tags_filter": None,
            }
        ]

    cleaned: List[Dict[str, Any]] = []
    for item in sub_queries:
        if not isinstance(item, dict):
            continue

        q = item.get("query")
        if not isinstance(q, str):
            continue
        q = q.strip()
        if not q:
            continue

        # Time parsing
        start_raw = item.get("start_datetime")
        end_raw = item.get("end_datetime")
        start_dt = parse_iso_or_none(start_raw)
        end_dt = parse_iso_or_none(end_raw)

        # Filters (only meaningful if has_filters == True)
        variant_filter: Optional[List[str]] = None
        sentiment_filter: Optional[List[str]] = None
        tags_filter: Optional[List[str]] = None

        if has_filters:
            v = item.get("variant_filter")
            if isinstance(v, list):
                v_clean = [vv.strip() for vv in v if isinstance(vv, str) and vv.strip()]
                variant_filter = v_clean or None

            s = item.get("sentiment_filter")
            if isinstance(s, list):
                s_clean = [
                    ss.strip().lower()
                    for ss in s
                    if isinstance(ss, str) and ss.strip()
                ]
                # Only keep valid sentiments
                allowed_sent = {"positive", "negative", "mixed", "neutral"}
                s_clean = [ss for ss in s_clean if ss in allowed_sent]
                sentiment_filter = s_clean or None

            t = item.get("tag_filter")
            if isinstance(t, list):
                t_clean = [tt.strip() for tt in t if isinstance(tt, str) and tt.strip()]
                tags_filter = t_clean or None

        cleaned.append(
            {
                "query": q,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "variant_filter": variant_filter,
                "sentiment_filter": sentiment_filter,
                "tags_filter": tags_filter,
            }
        )

    if not cleaned:
        return [
            {
                "query": question,
                "start_dt": None,
                "end_dt": None,
                "variant_filter": None,
                "sentiment_filter": None,
                "tags_filter": None,
            }
        ]

    return cleaned
