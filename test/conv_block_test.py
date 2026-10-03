from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Hashable, Tuple
from collections import Counter

from ai.models import RawPost, CleanPost


@dataclass
class DuplicateStats:
    total_items: int                 # len(list)
    unique_keys: int                 # keys that appear exactly once
    keys_with_duplicates: int        # keys that appear > 1
    duplicate_key_counts: Dict[Hashable, int]  # key -> occurrence count (>1 only)


def _summarize_counts(counts: Counter) -> DuplicateStats:
    total_items = sum(counts.values())
    unique_keys = sum(1 for c in counts.values() if c == 1)
    dup_key_counts = {k: c for k, c in counts.items() if c > 1}
    keys_with_duplicates = len(dup_key_counts)
    return DuplicateStats(
        total_items=total_items,
        unique_keys=unique_keys,
        keys_with_duplicates=keys_with_duplicates,
        duplicate_key_counts=dup_key_counts,
    )


# -------------------------------------------------------------------
# RAW POSTS
# -------------------------------------------------------------------

def analyze_raw_post_duplicates(raw_posts: List[RawPost]) -> Dict[str, DuplicateStats]:
    """
    Check duplication in RawPost list.

    - by_post_id:  every RawPost with the same post_id grouped together.
      This is usually the main thing you care about for scraper duplication.

    Returns a dict of DuplicateStats keyed by strategy.
    """
    # By post_id
    by_id_counts = Counter(p.post_id for p in raw_posts)
    by_id_stats = _summarize_counts(by_id_counts)

    return {
        "by_post_id": by_id_stats,
    }


# -------------------------------------------------------------------
# CLEAN POSTS
# -------------------------------------------------------------------

def analyze_clean_post_duplicates(clean_posts: List[CleanPost]) -> Dict[str, DuplicateStats]:
    """
    Check duplication in CleanPost list using two different keys:

    - by_post_id:            same logical post across runs.
    - by_thread_post_number: same position in the thread (thread_id, post_number).

    Returns a dict of DuplicateStats keyed by strategy.
    """
    # By post_id
    by_id_counts = Counter(p.post_id for p in clean_posts)
    by_id_stats = _summarize_counts(by_id_counts)

    # By (thread_id, post_number)
    by_thread_post_counts = Counter((p.thread_id, p.post_number) for p in clean_posts)
    by_thread_post_stats = _summarize_counts(by_thread_post_counts)

    return {
        "by_post_id": by_id_stats,
        "by_thread_post_number": by_thread_post_stats,
    }


# -------------------------------------------------------------------
# OPTIONAL: nice debug printer
# -------------------------------------------------------------------

def print_duplicate_report_raw(raw_posts: List[RawPost]) -> None:
    stats_map = analyze_raw_post_duplicates(raw_posts)
    stats = stats_map["by_post_id"]

    print("=== RAW POSTS DUPLICATE REPORT (by post_id) ===")
    print(f"Total RawPost items:      {stats.total_items}")
    print(f"Unique post_id values:    {stats.unique_keys}")
    print(f"post_id with duplicates:  {stats.keys_with_duplicates}")

    if stats.duplicate_key_counts:
        print("\nDuplicated post_id values (post_id -> count):")
        # Show sorted by count descending
        for pid, count in sorted(stats.duplicate_key_counts.items(), key=lambda x: -x[1]):
            print(f"  {pid}: {count}")
    else:
        print("\nNo duplicated post_id values found.")


def print_duplicate_report_clean(clean_posts: List[CleanPost]) -> None:
    stats_map = analyze_clean_post_duplicates(clean_posts)

    id_stats = stats_map["by_post_id"]
    tp_stats = stats_map["by_thread_post_number"]

    print("=== CLEAN POSTS DUPLICATE REPORT ===")

    print("\n-- By post_id --")
    print(f"Total CleanPost items:    {id_stats.total_items}")
    print(f"Unique post_id values:    {id_stats.unique_keys}")
    print(f"post_id with duplicates:  {id_stats.keys_with_duplicates}")
    if id_stats.duplicate_key_counts:
        print("Duplicated post_id values (post_id -> count):")
        for pid, count in sorted(id_stats.duplicate_key_counts.items(), key=lambda x: -x[1]):
            print(f"  {pid}: {count}")
    else:
        print("No duplicated post_id values found.")

    print("\n-- By (thread_id, post_number) --")
    print(f"Unique (thread_id, post_number) keys: {tp_stats.unique_keys}")
    print(f"Keys with duplicates:                  {tp_stats.keys_with_duplicates}")
    if tp_stats.duplicate_key_counts:
        print("Duplicated (thread_id, post_number) values (key -> count):")
        for key, count in sorted(tp_stats.duplicate_key_counts.items(), key=lambda x: -x[1]):
            print(f"  {key}: {count}")
    else:
        print("No duplicated (thread_id, post_number) keys found.")

import csv
from collections import Counter
from pathlib import Path

def report_csv_row_duplicates(csv_path: str) -> None:
    """
    Read a CSV of posts and report how many times each full row is duplicated.

    CSV is expected to have headers:
        post_id, author, created_at, content
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    counts: Counter[tuple] = Counter()

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"post_id", "author", "created_at", "content"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {missing}")

        for row in reader:
            key = (
                row["post_id"],
                row["author"],
                row["created_at"],
                row["content"],
            )
            counts[key] += 1

    total_rows = sum(counts.values())
    unique_rows = len(counts)
    dup_rows = {k: c for k, c in counts.items() if c > 1}

    print("=== CSV ROW DUPLICATE REPORT (by full row) ===")
    print(f"File: {csv_path}")
    print(f"Total rows:          {total_rows}")
    print(f"Unique rows:         {unique_rows}")
    print(f"Rows with duplicates:{len(dup_rows)}")
    print()

    if not dup_rows:
        print("No duplicated rows found.")
        return

    print("Duplicated rows (row -> count):\n")
    # Sort by highest duplicate count first
    for (post_id, author, created_at, content), count in sorted(
        dup_rows.items(), key=lambda x: -x[1]
    ):
        snippet = content.replace("\n", " ")
        if len(snippet) > 120:
            snippet = snippet[:120] + "..."
        print(f"- post_id={post_id}, author={author}, created_at={created_at}, count={count}")
        print(f"  content_snippet={snippet!r}")
        print()


from ai.io_utils import load_raw_posts_from_json
from ai.text_cleaning import raw_to_clean_posts
from ai.reply_merge import group_posts_into_conversation_blocks
from ai.models import ConversationBlock, RawPost, CleanPost

csv_path = r"E:\VisionRD\haval-marketing\haval_marketing_tool\data\featured_research__Haval H6 Dedicated Discussion.csv"
json_path = r"E:\VisionRD\haval-marketing\haval_marketing_tool\data\featured_research__Haval H6 Dedicated Discussion.json"
raw_posts = load_raw_posts_from_json(json_path)
clean_posts = raw_to_clean_posts(raw_posts, "Haval H6 Dedicated Discussion")
blocks = group_posts_into_conversation_blocks(clean_posts)

from typing import Dict, List

def count_posts_in_blocks(blocks: List[ConversationBlock]) -> int:
    total = 0
    for block in blocks:
        # 1 for root_post + number of replies
        total += 1 + len(block.replies)
    return total

def posts_per_block(blocks: List[ConversationBlock]) -> Dict[str, int]:
    """
    Return a mapping of block_id -> number of posts in that block.
    """
    return {
        block.block_id: 1 + len(block.replies)
        for block in blocks
    }

if __name__ == "__main__":
    total_posts = count_posts_in_blocks(blocks)
    print(f"Total posts in {len(blocks)} conversation blocks: {total_posts}")

    posts_count_map = posts_per_block(blocks)   
    

    print_duplicate_report_raw(raw_posts)
    print_duplicate_report_clean(clean_posts)

    # report_csv_row_duplicates(csv_path)
    import pdb; pdb.set_trace()