# haval_insights/time_analytics.py
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import List, Dict, Tuple
from ai.models import CleanPost


@dataclass
class DailyStats:
    day: date
    post_count: int
    unique_authors: int

    # Placeholders for future metrics
    sentiment_counts: Dict[str, int] = field(default_factory=dict)
    tag_counts: Dict[str, int] = field(default_factory=dict)
    variant_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class WeeklyStats:
    week_year: int
    week_number: int
    post_count: int
    unique_authors: int

    sentiment_counts: Dict[str, int] = field(default_factory=dict)
    tag_counts: Dict[str, int] = field(default_factory=dict)
    variant_counts: Dict[str, int] = field(default_factory=dict)


def compute_daily_stats(posts: List[CleanPost]) -> List[DailyStats]:
    """
    Aggregate simple daily metrics.

    Later, when sentiment/tags/variants are populated (via LLM),
    this function will automatically start reflecting those.
    """
    by_day: Dict[date, List[CleanPost]] = defaultdict(list)
    for p in posts:
        by_day[p.date].append(p)

    daily_stats: List[DailyStats] = []

    for d, plist in sorted(by_day.items(), key=lambda x: x[0]):
        authors = {p.username for p in plist}

        sentiment_counter = Counter()
        tag_counter = Counter()
        variant_counter = Counter()

        for p in plist:
            if p.sentiment:
                sentiment_counter[p.sentiment] += 1
            for t in p.tags:
                tag_counter[t] += 1
            if p.variant:
                variant_counter[p.variant] += 1

        daily_stats.append(
            DailyStats(
                day=d,
                post_count=len(plist),
                unique_authors=len(authors),
                sentiment_counts=dict(sentiment_counter),
                tag_counts=dict(tag_counter),
                variant_counts=dict(variant_counter),
            )
        )

    return daily_stats


def compute_weekly_stats(posts: List[CleanPost]) -> List[WeeklyStats]:
    """
    Aggregate simple weekly metrics using ISO week (year, week_number).

    This gives a high-level view of how active the thread is,
    and once we have tags, it’ll give 'weekly concern trends'.
    """
    key_to_posts: Dict[Tuple[int, int], List[CleanPost]] = defaultdict(list)
    for p in posts:
        key_to_posts[(p.week_year, p.week_number)].append(p)

    weekly_stats: List[WeeklyStats] = []

    for (wy, wn), plist in sorted(key_to_posts.items()):
        authors = {p.username for p in plist}

        sentiment_counter = Counter()
        tag_counter = Counter()
        variant_counter = Counter()

        for p in plist:
            if p.sentiment:
                sentiment_counter[p.sentiment] += 1
            for t in p.tags:
                tag_counter[t] += 1
            if p.variant:
                variant_counter[p.variant] += 1

        weekly_stats.append(
            WeeklyStats(
                week_year=wy,
                week_number=wn,
                post_count=len(plist),
                unique_authors=len(authors),
                sentiment_counts=dict(sentiment_counter),
                tag_counts=dict(tag_counter),
                variant_counts=dict(variant_counter),
            )
        )

    return weekly_stats
