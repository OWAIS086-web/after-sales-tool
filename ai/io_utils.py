# haval_insights/io_utils.py
import json
from datetime import datetime
from typing import List, Dict, Any
from ai.models import RawPost


def _parse_iso(dt_str: str) -> datetime:
    """
    Parse ISO 8601 strings like '2023-03-22T10:12:49.411+05:00'.
    datetime.fromisoformat handles this format directly in Python 3.11+.
    """
    return datetime.fromisoformat(dt_str)


def load_raw_posts_from_json(
    json_path: str,
) -> List[RawPost]:
    """
    Load the single-thread JSON (as you've shown) and convert to RawPost objects.

    Assumptions:
    - JSON is a dict with keys: topic, url, posts
    - posts is a list of dicts with 'cooked', 'created_at', etc.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    topic = data.get("topic")
    url = data.get("url")
    posts_data = data.get("posts", [])
    topic_title = posts_data[0].get("topic_title") if posts_data else ""

    raw_posts: List[RawPost] = []
    for p in posts_data:
        raw_posts.append(
            RawPost(
                topic=str(topic),
                url=url,
                post_id=p.get("post_id", p.get("post_number", 0)),  # Use post_number as fallback if post_id not available
                post_number=p["post_number"],
                username=p["username"],
                created_at=_parse_iso(p["created_at"]),
                updated_at=_parse_iso(p["updated_at"]),
                cooked_html=p["cooked"],
                reply_to_post_number=p.get("reply_to_post_number"),
                topic_title=p.get("topic_title", topic_title),
                metadata={
                    # keep extra stuff here
                    "reply_count": p.get("reply_count"),
                    "quote_count": p.get("quote_count"),
                    "reads": p.get("reads"),
                },
            )
        )

    return raw_posts


def load_raw_posts_from_data(
    data: Dict[str, Any],
) -> List[RawPost]:
    """
    Same logic as load_raw_posts_from_json, but accepts a parsed dict.

    Useful for Streamlit where we get JSON via upload rather than from disk.
    """
    topic = data.get("topic")
    url = data.get("url")
    posts_data = data.get("posts", [])
    topic_title = posts_data[0].get("topic_title") if posts_data else ""

    raw_posts: List[RawPost] = []
    for p in posts_data:
        raw_posts.append(
            RawPost(
                topic=str(topic),
                url=url,
                post_id=p["post_id"],
                post_number=p["post_number"],
                username=p["username"],
                created_at=_parse_iso(p["created_at"]),
                updated_at=_parse_iso(p["updated_at"]),
                cooked_html=p["cooked"],
                reply_to_post_number=p.get("reply_to_post_number"),
                topic_title=p.get("topic_title", topic_title),
                metadata={
                    "reply_count": p.get("reply_count"),
                    "quote_count": p.get("quote_count"),
                    "reads": p.get("reads"),
                },
            )
        )

    return raw_posts
