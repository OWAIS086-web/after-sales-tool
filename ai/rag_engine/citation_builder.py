# ai/rag_engine/citation_builder.py
"""
Citation Building Module

Handles construction of context and citation blocks:
- Build context from retrieved blocks for LLM processing
- Generate formatted citations with metadata
- Handle Forum, Reddit, and WhatsApp source formatting
"""

from __future__ import annotations
from typing import List, Optional, Dict
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

from ai.vector_store import RetrievedBlock


def build_context_whatsapp_semantic(
    retrieved: List[RetrievedBlock],
    max_block_chars: int = 2048
) -> str:
    """
    Build WhatsApp context grouped BY CUSTOMER for semantic queries.

    Prevents LLM hallucination by clearly separating each customer's messages.
    Used for broad queries like "are there any angry customers?" to ensure
    the LLM doesn't mix up information across different customers.

    Design:
    - Groups retrieved blocks by customer name (root_post.username)
    - Creates clear visual boundaries between customers
    - Shows message count and aggregate metadata per customer
    - Impossible for LLM to attribute Customer A's content to Customer B

    Args:
        retrieved: List of retrieved blocks (from semantic search)
        max_block_chars: Maximum characters per message block

    Returns:
        Formatted context string with customer grouping

    Example output:
        ════════════════════════════════════════════════════════════════
        CUSTOMER: bashobashomal1
        Phone: +923002025980
        Message Count: 2 messages
        Date Range: 2025-12-22 to 2025-12-22
        Sentiment: neutral
        ════════════════════════════════════════════════════════════════

        [Message 1] 📅 2025-12-22
        "Hi"

        [Message 2] 📅 2025-12-22
        "Register a complaint"

        ════════════════════════════════════════════════════════════════
        CUSTOMER: AnotherCustomer
        ...
    """
    if not retrieved:
        return "(No messages retrieved)"

    # Group blocks by customer name
    # Key: customer_name (username), Value: List of RetrievedBlock objects
    customer_blocks: Dict[str, List[RetrievedBlock]] = defaultdict(list)

    for rb in retrieved:
        customer_name = rb.block.root_post.username
        customer_blocks[customer_name].append(rb)

    # Build context with clear customer separation
    ctx_parts: List[str] = []

    # Sort customers by total sentiment (negative first for priority)
    def customer_priority(customer_name: str) -> tuple:
        """Sort customers by: 1) negative sentiment count, 2) message count (descending)"""
        blocks = customer_blocks[customer_name]
        negative_count = sum(
            1 for rb in blocks
            if getattr(rb.block, "dominant_sentiment", None) == "negative"
        )
        return (-negative_count, -len(blocks))  # Descending order

    sorted_customers = sorted(customer_blocks.keys(), key=customer_priority)

    for customer_name in sorted_customers:
        blocks = customer_blocks[customer_name]

        # === CUSTOMER HEADER ===
        separator = "═" * 70
        ctx_parts.append(separator)
        ctx_parts.append(f"CUSTOMER: {customer_name}")

        # Phone number (if available)
        phone_number = None
        if hasattr(blocks[0].block, 'phone_number') and blocks[0].block.phone_number:
            phone_number = blocks[0].block.phone_number
            ctx_parts.append(f"Phone: {phone_number}")

        # Message count
        total_messages = sum(1 + len(rb.block.replies) for rb in blocks)
        ctx_parts.append(f"Message Count: {total_messages} message{'s' if total_messages != 1 else ''}")

        # Date range
        all_dates = []
        for rb in blocks:
            all_dates.append(rb.block.root_post.created_at)
            all_dates.extend(reply.created_at for reply in rb.block.replies)

        if all_dates:
            min_date = min(all_dates).date()
            max_date = max(all_dates).date()
            if min_date == max_date:
                ctx_parts.append(f"Date: {min_date}")
            else:
                ctx_parts.append(f"Date Range: {min_date} to {max_date}")

        # Aggregate metadata across all blocks for this customer
        sentiments = [
            getattr(rb.block, "dominant_sentiment", None)
            for rb in blocks
        ]
        sentiments = [s for s in sentiments if s]  # Remove None values

        if sentiments:
            # Count sentiment occurrences
            sentiment_counts = {}
            for s in sentiments:
                sentiment_counts[s] = sentiment_counts.get(s, 0) + 1

            # Show dominant sentiment
            dominant = max(sentiment_counts.items(), key=lambda x: x[1])
            if len(sentiment_counts) == 1:
                ctx_parts.append(f"Sentiment: {dominant[0]}")
            else:
                sentiment_summary = ", ".join(
                    f"{sent} ({count})"
                    for sent, count in sorted(sentiment_counts.items(), key=lambda x: -x[1])
                )
                ctx_parts.append(f"Sentiments: {sentiment_summary}")

        # Aggregate tags
        all_tags = []
        for rb in blocks:
            tags = getattr(rb.block, "aggregated_tags", None) or []
            all_tags.extend(tags)

        if all_tags:
            # Count tag occurrences and show top 5
            tag_counts = {}
            for tag in all_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

            top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:5]
            tags_str = ", ".join(f"{tag} ({count})" for tag, count in top_tags)
            ctx_parts.append(f"Topics: {tags_str}")

        ctx_parts.append(separator)
        ctx_parts.append("")  # Blank line after header

        # === CUSTOMER MESSAGES ===
        message_index = 1
        for rb in sorted(blocks, key=lambda x: x.block.root_post.created_at):
            b = rb.block

            # Format each message in this block
            date = b.root_post.created_at.date()

            # CRITICAL: ALWAYS use flattened_text for WhatsApp semantic queries
            # DO NOT use summary - summaries can be hallucinated for short conversations
            # Example: "Hi" + "Register complaint" → summary hallucinated "battery failure"
            content = b.flattened_text
            
            # Remove any BLOCK_ID references from the content
            content = content.replace(f"BLOCK_ID={b.block_id}", "").strip()
            
            if len(content) > max_block_chars:
                content = content[:max_block_chars] + "..."
            content = content.strip()

            ctx_parts.append(f"[Conversation Block {message_index}] 📅 {date}")

            # Add metadata tags if available for this specific block
            block_meta = []
            if getattr(b, "dominant_variant", None):
                block_meta.append(f"variant={b.dominant_variant}")
            if getattr(b, "dominant_sentiment", None):
                block_meta.append(f"sentiment={b.dominant_sentiment}")

            # Show enrichment tags but with a warning
            tags = getattr(b, "aggregated_tags", None) or []
            if tags:
                # Only show top 3 tags to avoid clutter
                top_tags = tags[:3]
                block_meta.append(f"ai_tags={', '.join(top_tags)}")

            if block_meta:
                ctx_parts.append(" | ".join(block_meta))

            # Show ACTUAL conversation (not AI-generated summary)
            ctx_parts.append(f"ACTUAL CONVERSATION:")
            ctx_parts.append(f'"{content}"')

            # Optional: Show summary with warning if it exists AND conversation is substantial
            summary = getattr(b, "summary", None)
            if summary and len(content) > 300:  # Only for substantial conversations
                ctx_parts.append(f"⚠️ AI Summary (verify against actual messages): {summary[:150]}...")

            ctx_parts.append("")  # Blank line after message

            message_index += 1

        ctx_parts.append("")  # Extra blank line between customers

    return "\n".join(ctx_parts)


def build_context(retrieved: List[RetrievedBlock], max_block_chars: int = 2048) -> str:
    """
    Build textual context block from retrieved conversation blocks.

    Uses summary (from enrichment) as main content when available,
    plus variant/sentiment/tags metadata. Falls back to flattened_text.

    Args:
        retrieved: List of retrieved blocks
        max_block_chars: Maximum characters per block

    Returns:
        Formatted context string for LLM consumption
    """
    ctx_parts: List[str] = []
    for rb in retrieved:
        b = rb.block
        header = (
            f"root_author={b.root_post.username} | "
            f"date={b.root_post.created_at.date()}"
        )

        meta_bits: List[str] = []
        v = getattr(b, "dominant_variant", None)
        if v:
            meta_bits.append(f"variant={v}")
        s = getattr(b, "dominant_sentiment", None)
        if s:
            meta_bits.append(f"sentiment={s}")
        tags = getattr(b, "aggregated_tags", None) or []
        if tags:
            meta_bits.append("tags=" + ", ".join(tags[:6]))

        meta_line = " | ".join(meta_bits) if meta_bits else ""

        # Prefer summary if enrichment has created one
        summary = getattr(b, "summary", None)
        if summary:
            content = summary.strip()
        else:
            snippet = b.flattened_text
            # Remove BLOCK_ID references from content
            snippet = snippet.replace(f"BLOCK_ID={b.block_id}", "").strip()
            if len(snippet) > max_block_chars:
                snippet = snippet[: max_block_chars] + "..."
            content = snippet.strip()

        block_text = header
        if meta_line:
            block_text += "\n" + meta_line
        block_text += "\n" + content

        ctx_parts.append(block_text)

    return "\n\n---\n\n".join(ctx_parts)


def build_citations(
    retrieved: List[RetrievedBlock],
    max_refs: int = 5,
    similarity_threshold: float = 0.6,
    citation_start_dt: Optional[datetime] = None,
    citation_end_dt: Optional[datetime] = None,
    **kwargs  # Accept additional parameters like forum_base_url
) -> str:
    """
    Build human-readable references section from retrieved blocks.

    Uses consistent formatting that matches HTML template parsing patterns.
    Filters by similarity threshold for relevance.

    Args:
        retrieved: List of retrieved blocks
        max_refs: Maximum number of references (default 5, max 10 in thinking mode)
        similarity_threshold: Only include blocks with score >= this value (default 0.6)
        citation_start_dt: Start of time window (for finding relevant message date)
        citation_end_dt: End of time window (for finding relevant message date)
        **kwargs: Additional parameters (pakwheels_base_url for company-specific forum URLs)

    Returns:
        Formatted citations section or empty string if no relevant blocks
    """
    if not retrieved:
        return ""

    # Filter by similarity threshold for strict relevance
    filtered_retrieved = [rb for rb in retrieved if rb.score >= similarity_threshold]

    if not filtered_retrieved:
        return ""  # No sufficiently relevant blocks found

    # Log base URL for debugging
    base_url = kwargs.get('pakwheels_base_url', 'https://www.pakwheels.com/forums/t/haval-h6-dedicated-discussion-owner-fan-club-thread/2198325')
    print(f"[Citations] Building citations with base URL: {base_url}")

    lines: List[str] = []
    lines.append("\n\n---")
    lines.append("### 📋 References")
    lines.append("")

    # Include only up to max_refs references with strict similarity
    for i, rb in enumerate(filtered_retrieved[:max_refs], 1):
        b = rb.block

        # Find the most relevant message date
        # For multi-message blocks (forum threads/WhatsApp), show the date of relevant messages
        relevant_date = b.root_post.created_at.date()

        if hasattr(b, 'replies') and b.replies:
            # Case 1: Time window specified - find messages within that window
            if citation_start_dt and citation_end_dt:
                all_messages = [b.root_post] + b.replies
                messages_in_window = []

                for msg in all_messages:
                    msg_dt = msg.created_at
                    # Normalize timezone
                    if msg_dt.tzinfo is None:
                        msg_dt = msg_dt.replace(tzinfo=ZoneInfo("Asia/Karachi"))
                    elif msg_dt.tzinfo != citation_start_dt.tzinfo:
                        msg_dt = msg_dt.astimezone(ZoneInfo("Asia/Karachi"))

                    # Check if message is within the time window
                    if citation_start_dt <= msg_dt <= citation_end_dt:
                        messages_in_window.append(msg)

                # If we found messages in the window, use the first one's date
                if messages_in_window:
                    relevant_date = messages_in_window[0].created_at.date()

            # Case 2: No time window - show latest message date from the thread
            # This handles queries like "latest message" for old threads with recent replies
            else:
                all_messages = [b.root_post] + b.replies
                latest_message = max(all_messages, key=lambda m: m.created_at)
                relevant_date = latest_message.created_at.date()

        date = relevant_date
        username = b.root_post.username
        source_url = b.source_url

        # Prefer summary; otherwise pick first non-header content line
        if getattr(b, "summary", None):
            base_text = b.summary
            body_lines = [ln for ln in base_text.splitlines() if ln.strip()]
        else:
            base_text = b.flattened_text
            body_lines = [ln for ln in base_text.splitlines() if ln.strip()]
            # Strip simple header lines like "[user @ date]"
            body_lines = [
                ln
                for ln in body_lines
                if not (ln.startswith("[") and "@" in ln and "]" in ln)
            ]

        snippet = body_lines[0] if body_lines else base_text
        snippet = snippet.strip()
        if len(snippet) > 180:
            snippet = snippet[:180] + "..."

        # Detect source from block's source_type attribute first (most reliable)
        source_label = "Forum"  # Default
        enhanced_url = source_url
        phone_info = ""

        # Check block's source_type attribute first (set during retrieval)
        if hasattr(b, 'source_type') and b.source_type:
            source_type = b.source_type.lower()
            if source_type == "whatsapp":
                source_label = "WhatsApp"
            elif "reddit" in source_type:
                source_label = "Reddit"
            elif source_type == "reddit_lucid":
                source_label = "Reddit"
            elif source_type == "lucid":
                source_label = "Lucid Forum"
            else:
                source_label = "PakWheels Forum"
            # print(f"[DEBUG] Citation {i}: source_type={b.source_type}, source_label={source_label}")
        elif rb.metadata and "source" in rb.metadata:
            # Fallback to metadata if source_type not set
            source_value = rb.metadata["source"]
            if source_value == "Whatsapp":
                source_label = "WhatsApp"
            elif "reddit" in source_value.lower():
                source_label = "Reddit"
            elif source_value == "Lucid":
                source_label = "Lucid Forum"
            else:
                source_label = "PakWheels Forum"
            # print(f"[DEBUG] Citation {i}: source_value={source_value}, source_label={source_label}")
        else:
            pass
            # print(f"[DEBUG] Citation {i}: No source found. metadata keys: {list(rb.metadata.keys()) if rb.metadata else 'None'}")

        if "WhatsApp" in source_label:
            # Try metadata first, then block attribute
            phone_number = None
            if rb.metadata and "phone_number" in rb.metadata and rb.metadata["phone_number"]:
                phone_number = rb.metadata["phone_number"]
            elif hasattr(b, 'phone_number') and b.phone_number:
                phone_number = b.phone_number

            # Only show phone number if it's valid and not empty
            if phone_number and str(phone_number).strip() and str(phone_number).strip() != "N/A":
                phone_info = f" | 📞 {phone_number}"
                # print(f"[DEBUG] WhatsApp citation {i}: phone_number={phone_number} (from {'metadata' if rb.metadata and 'phone_number' in rb.metadata else 'block'})")
            else:
                phone_info = ""  # Don't show phone info if not available
                # print(f"[DEBUG] WhatsApp citation {i}: NO valid phone_number found. Skipping phone display.")

        elif "Lucid Forum" in source_label:
            # Handle Lucid Forum URLs - use post_link from metadata (actual post URL from database)
            if rb.metadata and "post_link" in rb.metadata and rb.metadata["post_link"]:
                enhanced_url = rb.metadata["post_link"]
                print(f"[DEBUG] Lucid citation {i}: using post_link from metadata: {enhanced_url}")
            elif rb.metadata and "lucid_url" in rb.metadata:
                enhanced_url = rb.metadata["lucid_url"]
                print(f"[DEBUG] Lucid citation {i}: using lucid_url from metadata: {enhanced_url}")
            elif rb.metadata and "thread_url" in rb.metadata:
                enhanced_url = rb.metadata["thread_url"]
                print(f"[DEBUG] Lucid citation {i}: using thread_url from metadata: {enhanced_url}")
            elif source_url and "lucidowners.com" in source_url:
                enhanced_url = source_url
                print(f"[DEBUG] Lucid citation {i}: using source_url: {enhanced_url}")
            else:
                # Use company-specific Lucid base URL from kwargs
                lucid_base_url = kwargs.get('lucid_base_url', 'https://lucidowners.com')
                enhanced_url = lucid_base_url
                print(f"[DEBUG] Lucid citation {i}: NO specific Lucid URL found, using base URL: {enhanced_url}")

        elif source_label == "Forum":
            # Try to get post_number first (preferred), then fall back to post_id
            post_number = None
            if rb.metadata and "post_number" in rb.metadata:
                post_number = rb.metadata["post_number"]
            elif hasattr(b.root_post, 'post_number') and b.root_post.post_number:
                post_number = b.root_post.post_number
            elif rb.metadata and "post_id" in rb.metadata:
                # Fallback to post_id if post_number not available
                post_number = rb.metadata["post_id"]
            elif hasattr(b.root_post, 'post_id') and b.root_post.post_id:
                # Fallback to post_id if post_number not available
                post_number = b.root_post.post_id

            if post_number:
                # Use company-specific base URL from kwargs
                base_url = kwargs.get('pakwheels_base_url', 'https://www.pakwheels.com/forums/t/haval-h6-dedicated-discussion-owner-fan-club-thread/2198325')
                enhanced_url = f"{base_url}/{post_number}"
                # print(f"[DEBUG] PakWheels citation {i}: post_number={post_number}, enhanced_url={enhanced_url} (from {'metadata' if rb.metadata and ('post_number' in rb.metadata or 'post_id' in rb.metadata) else 'block'})")
            else:
                pass
                # print(f"[DEBUG] PakWheels citation {i}: NO post_number found. Block root_post.post_number={getattr(b.root_post, 'post_number', 'MISSING')}, root_post.post_id={getattr(b.root_post, 'post_id', 'MISSING')}, metadata post_number={rb.metadata.get('post_number', 'MISSING') if rb.metadata else 'NO_METADATA'}, metadata post_id={rb.metadata.get('post_id', 'MISSING') if rb.metadata else 'NO_METADATA'}")

        elif "Reddit" in source_label:
            # Handle Reddit URLs - use the original source_url or construct from metadata
            if rb.metadata and "reddit_url" in rb.metadata:
                enhanced_url = rb.metadata["reddit_url"]
                print(f"[DEBUG] Reddit citation {i}: using reddit_url from metadata: {enhanced_url}")
            elif rb.metadata and "post_url" in rb.metadata:
                enhanced_url = rb.metadata["post_url"]
                print(f"[DEBUG] Reddit citation {i}: using post_url from metadata: {enhanced_url}")
            elif source_url and "reddit.com" in source_url:
                enhanced_url = source_url
                print(f"[DEBUG] Reddit citation {i}: using source_url: {enhanced_url}")
            else:
                # Fallback to a generic Reddit URL if no specific URL available
                enhanced_url = "https://www.reddit.com/"
                print(f"[DEBUG] Reddit citation {i}: NO specific Reddit URL found, using generic Reddit URL")
            # For other sources, use the original source_url
            print(f"[DEBUG] Citation {i}: Using original source_url for {source_label}: {enhanced_url}")

        # Format that matches HTML template parsing patterns
        lines.append(f"**[{i}]** 👤 {username} | 📅 {date} | 🔗 {source_label}{phone_info}")
        lines.append(f"💬 *\"{snippet}\"*")
        lines.append(f"🔗 [View Source]({enhanced_url})")
        lines.append("")

    lines.append("---")
    return "\n".join(lines)