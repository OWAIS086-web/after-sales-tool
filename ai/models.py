# haval_insights/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


@dataclass
class RawPost:
    """
    Direct representation of what we get from PakWheels JSON.

    This stays very close to the scraped schema, so if the scraper changes
    it's easy to debug from here.
    """
    topic: str
    url: str
    post_id: int
    post_number: int
    username: str
    created_at: datetime
    updated_at: datetime
    cooked_html: str
    reply_to_post_number: Optional[int]
    topic_title: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CleanPost:
    """
    RawPost + cleaned text fields and time features, but still 1:1 with the
    original post.
    """
    thread_id: str               # e.g. "pakwheels_haval_h6"
    source_url: str
    post_id: int
    post_number: int
    username: str
    created_at: datetime
    updated_at: datetime
    text: str                    # plain text (no HTML)
    reply_to_post_number: Optional[int]
    topic_title: str

    # Time features for analytics
    date: date                   # created_at.date()
    week_year: int               # ISO week year
    week_number: int             # ISO week number (1-53)

    # Placeholder for future enrichment (LLM-based)
    variant: Optional[str] = None      # "PHEV", "HEV", "ICE", etc.
    sentiment: Optional[str] = None    # "positive", "negative", "mixed", etc.
    tags: List[str] = field(default_factory=list)  # ["fuel_economy", "charging_cost", ...]
    is_owner: Optional[bool] = None


@dataclass
class ConversationBlock:
    """
    Root post + its replies merged into a single 'document' for RAG.

    This is what we will eventually embed and push into the vector DB.

    Design choices:
    - We keep root + replies in structured form (list of messages),
      *and* also a flattened_text for embeddings / LLM summarization.
    - For WhatsApp: phone_number is the primary key (lifetime conversation per customer)
    """
    block_id: str                          # thread_id + ":" + root_post_number
    thread_id: str
    source_url: str
    topic_title: str

    root_post: CleanPost
    replies: List[CleanPost]

    # Flattened concatenation of root + replies, in a readable format
    flattened_text: str

    # Aggregate time features (based on root, but you can extend)
    start_datetime: datetime
    end_datetime: datetime

    # WhatsApp-specific: customer phone number (used for grouping lifetime conversations)
    # For PakWheels: None (forum usernames used instead)
    phone_number: Optional[str] = None

    # Optional aggregated labels (later, from LLM)
    dominant_variant: Optional[str] = None
    dominant_sentiment: Optional[str] = None
    aggregated_tags: List[str] = field(default_factory=list)
    
    # Source type: "pakwheels", "whatsapp", "reddit", etc.
    # Must be at end since it has a default value
    source_type: Optional[str] = None
