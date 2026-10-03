# haval_insights/reply_merge.py
from __future__ import annotations
from typing import List, Dict, Optional
from collections import defaultdict
from ai.models import CleanPost, ConversationBlock


def _build_post_index(posts: List[CleanPost]) -> Dict[int, CleanPost]:
    """
    Map post_number -> CleanPost for quick lookup.
    """
    return {p.post_number: p for p in posts}


def _find_root_post_number(
    post: CleanPost,
    index: Dict[int, CleanPost],
) -> int:
    """
    Walk up reply_to_post_number chain until we reach a post with no parent.

    This gives us the 'conversation root' for each post.
    """
    current = post
    visited = set()

    while current.reply_to_post_number is not None:
        if current.post_number in visited:
            # Just in case of weird cycles
            break
        visited.add(current.post_number)

        parent_num = current.reply_to_post_number
        parent = index.get(parent_num)
        if parent is None:
            # Orphan reply – treat this as root itself
            break
        current = parent

    return current.post_number


def group_posts_into_conversation_blocks(
    posts: List[CleanPost],
) -> List[ConversationBlock]:
    """
    Merge replies so that each ConversationBlock corresponds to a root post
    and ALL its descendant replies (direct + nested).

    This 'flattens' the thread into digestible chunks for RAG and analytics.

    Steps:
    1) Build index post_number -> CleanPost
    2) For each post, find its root_post_number using _find_root_post_number
    3) Group posts by that root_post_number
    4) Inside each group, identify the root and replies, and build flattened_text
    """
    if not posts:
        return []

    # Ensure posts are sorted chronologically by created_at (or post_number)
    posts_sorted = sorted(posts, key=lambda p: (p.created_at, p.post_number))
    index = _build_post_index(posts_sorted)

    groups: Dict[int, List[CleanPost]] = defaultdict(list)
    for p in posts_sorted:
        root_num = _find_root_post_number(p, index)
        groups[root_num].append(p)

    blocks: List[ConversationBlock] = []

    # Single thread_id + url in this POC, so we can take from first
    thread_id = posts_sorted[0].thread_id
    source_url = posts_sorted[0].source_url
    topic_title = posts_sorted[0].topic_title

    for root_num, group_posts in groups.items():
        # Identify root post
        root_post = index[root_num]

        # Replies = all group_posts except root
        replies = [p for p in group_posts if p.post_number != root_num]

        # Build a nicely formatted flattened_text
        # Format: [username @ timestamp]\ntext\n\n...
        lines = []

        def fmt_post(p: CleanPost) -> str:
            # Keep it human-readable
            ts = p.created_at.strftime("%Y-%m-%d %H:%M")
            header = f"[{p.username} @ {ts}]"
            return header + "\n" + p.text.strip()

        lines.append(fmt_post(root_post))
        for r in replies:
            lines.append(fmt_post(r))

        flattened_text = "\n\n".join(lines).strip()

        # Aggregate time span
        start_dt = min(p.created_at for p in group_posts)
        end_dt = max(p.created_at for p in group_posts)

        block_id = f"{thread_id}:{root_post.post_number}"

        blocks.append(
            ConversationBlock(
                block_id=block_id,
                thread_id=thread_id,
                source_url=source_url,
                topic_title=topic_title,
                root_post=root_post,
                replies=replies,
                flattened_text=flattened_text,
                start_datetime=start_dt,
                end_datetime=end_dt,
            )
        )

    # For consistency, sort blocks by their start time
    blocks.sort(key=lambda b: b.start_datetime)
    return blocks
