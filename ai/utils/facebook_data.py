from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple
import re
import zlib
from ai.models import CleanPost, ConversationBlock

# ----------------------------
# helpers
# ----------------------------

_FB_UI_JUNK_RE = re.compile(
    r"(?im)^\s*(like|reply|share|see translation)\s*$|^\s*\d+\s*$|^\s*\d+\s*[wdhm]\s*$"
)

def _parse_scraped_at(s: Optional[str]) -> datetime:
    """
    Input example: "2025-11-28 15:11:15"
    Assume it's local time; store as UTC-ish just to satisfy dataclass typing.
    If you want correct TZ later, replace with ZoneInfo("Asia/Karachi").
    """
    if not s:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _stable_int(s: Any) -> int:
    """
    Stable across runs (unlike python hash()).
    """
    b = str(s).encode("utf-8", errors="ignore")
    return int(zlib.crc32(b) & 0xFFFFFFFF)


def _clean_fb_text(raw_text: Optional[str], author: Optional[str]) -> str:
    """
    Your scraped 'text' includes:
      AuthorName
      actual content
      1w
      Like
      Reply
      Share
      [maybe numbers like 3]
    We'll strip the author header (if duplicated) and UI junk/footer lines.
    """
    txt = (raw_text or "").replace("\r\n", "\n").strip()
    lines = [ln.strip() for ln in txt.split("\n") if ln.strip()]

    # Drop first line if it matches author (common in your sample)
    if author and lines and lines[0].strip().lower() == author.strip().lower():
        lines = lines[1:]

    # Remove junk lines
    cleaned = []
    for ln in lines:
        if _FB_UI_JUNK_RE.match(ln):
            continue
        cleaned.append(ln)

    # If everything got removed, fallback to original minus author line
    out = "\n".join(cleaned).strip()
    if not out:
        out = "\n".join(lines).strip()

    return out


def _make_clean_post_fb(
    *,
    thread_id: str,
    source_url: str,
    topic_title: str,
    post_number: int,
    author: str,
    created_dt: datetime,
    text: str,
    post_id_raw: Any,
) -> CleanPost:
    d = created_dt.date()
    iso = created_dt.isocalendar()
    return CleanPost(
        thread_id=thread_id,
        source_url=source_url,
        post_id=_stable_int(post_id_raw),
        post_number=post_number,
        username=author,
        created_at=created_dt,
        updated_at=created_dt,
        text=text,
        reply_to_post_number=None,
        topic_title=topic_title,
        date=d,
        week_year=iso.year,
        week_number=iso.week,
        is_owner=None,  # not applicable for FB scrape
    )


def _format_flattened(posts: List[CleanPost]) -> str:
    lines: List[str] = []
    for p in posts:
        ts = p.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines.append(f"[{ts}] {p.username}: {p.text}")
    return "\n".join(lines).strip()


# ----------------------------
# main function
# ----------------------------

def facebook_posts_to_conversation_blocks(
    posts: List[Dict[str, Any]],
    *,
    thread_prefix: str = "facebook",
    default_topic_title: str = "Facebook Group",
    # chunking controls (since we don't have reply trees yet)
    max_posts_per_block: int = 40,
) -> List[ConversationBlock]:
    """
    Convert your current FB scraped format into ConversationBlock list.

    Since the scrape has no "reply_to" or per-post created time, we:
    - group by (group/url)
    - order by scraped_at (then post_id)
    - chunk into blocks of max_posts_per_block
    """
    # group key: (group name, url)
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for p in posts:
        group_name = str(p.get("group") or "Facebook Group")
        url = str(p.get("url") or "")
        key = (group_name, url)
        grouped.setdefault(key, []).append(p)

    blocks: List[ConversationBlock] = []

    for (group_name, url), items in grouped.items():
        # sort deterministically
        items_sorted = sorted(
            items,
            key=lambda x: (
                _parse_scraped_at(x.get("scraped_at")).timestamp(),
                str(x.get("post_id") or ""),
            ),
        )

        # thread id stable for this group/url
        thread_id = f"{thread_prefix}_{_stable_int(group_name + '|' + url)}"
        source_url = url or f"facebook://group/{_stable_int(group_name)}"
        topic_title = group_name or default_topic_title

        # build CleanPosts first
        clean_posts: List[CleanPost] = []
        for idx, p in enumerate(items_sorted, start=1):
            author = str(p.get("author") or "Unknown").strip() or "Unknown"
            raw_text = p.get("text")
            cleaned_text = _clean_fb_text(raw_text, author)
            if not cleaned_text:
                continue

            dt = _parse_scraped_at(p.get("scraped_at"))
            clean_posts.append(
                _make_clean_post_fb(
                    thread_id=thread_id,
                    source_url=source_url,
                    topic_title=topic_title,
                    post_number=idx,
                    author=author,
                    created_dt=dt,
                    text=cleaned_text,
                    post_id_raw=p.get("post_id") or f"{thread_id}:{idx}",
                )
            )

        # chunk into ConversationBlocks
        for start_i in range(0, len(clean_posts), max_posts_per_block):
            chunk = clean_posts[start_i : start_i + max_posts_per_block]
            if not chunk:
                continue

            root = chunk[0]
            replies = chunk[1:]
            flattened = _format_flattened(chunk)

            block = ConversationBlock(
                block_id=f"{thread_id}:{root.post_number}",
                thread_id=thread_id,
                source_url=source_url,
                topic_title=topic_title,
                root_post=root,
                replies=replies,
                flattened_text=flattened,
                start_datetime=chunk[0].created_at,
                end_datetime=chunk[-1].created_at,
            )
            blocks.append(block)

    blocks.sort(key=lambda b: b.start_datetime)
    return blocks
