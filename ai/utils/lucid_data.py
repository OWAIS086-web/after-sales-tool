# ai/utils/lucid_data.py
"""
Lucid data processing utilities for the Haval pipeline.
Converts Lucid forum posts to conversation blocks for analysis.
"""

from typing import List, Dict, Any, Optional
from ai.models import ConversationBlock, CleanPost
from datetime import datetime
import re


def _parse_lucid_timestamp(timestamp_str: Optional[str]) -> datetime:
    """
    Parse Lucid timestamp string to datetime object.
    Handles various formats like "Mar 5, 2025", "Jan 1, 2024 at 10:30 AM"
    """
    if not timestamp_str:
        return datetime.now()
    
    try:
        # Try common datetime formats (order matters - most specific first)
        for fmt in [
            "%b %d, %Y at %I:%M %p",      # "Mar 5, 2025 at 10:30 AM"
            "%B %d, %Y at %I:%M %p",      # "March 5, 2025 at 10:30 AM"
            "%b %d, %Y",                   # "Mar 5, 2025"
            "%B %d, %Y",                   # "March 5, 2025"
            "%Y-%m-%d %H:%M:%S",          # "2025-03-05 10:30:00"
            "%d/%m/%Y %H:%M",             # "05/03/2025 10:30"
        ]:
            try:
                return datetime.strptime(timestamp_str.strip(), fmt)
            except ValueError:
                continue
        
        # Fallback to current time if parsing fails
        print(f"[LucidData] Warning: Could not parse timestamp '{timestamp_str}', using current time")
        return datetime.now()
    except Exception as e:
        print(f"[LucidData] Error parsing timestamp '{timestamp_str}': {e}")
        return datetime.now()


def _clean_text(text: Optional[str]) -> Optional[str]:
    """Clean and normalize text content."""
    if not text:
        return None
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text if text else None


def _extract_post_id(post_link: str) -> int:
    """Extract numeric post ID from post link."""
    try:
        # Try to extract number from URL
        match = re.search(r'post-(\d+)', post_link)
        if match:
            return int(match.group(1))
        
        # Fallback: use hash of URL
        import hashlib
        return int(hashlib.md5(post_link.encode()).hexdigest(), 16) % (10 ** 8)
    except Exception:
        return 0


def lucid_posts_to_conversation_blocks(data: Dict[str, Any]) -> List[ConversationBlock]:
    """
    Convert Lucid forum posts data to conversation blocks.
    
    Args:
        data: Lucid data dictionary containing thread_link and posts
        
    Returns:
        List of ConversationBlock objects
    """
    blocks = []
    thread_link = data.get("thread_link", "")
    posts = data.get("posts", [])
    
    # Extract thread title from URL or use generic title
    thread_title = thread_link.split('/')[-1].replace('-', ' ').title() if thread_link else "Lucid Forum Thread"
    
    print(f"[LucidData] Processing {len(posts)} posts from thread: {thread_link}")
    
    if not posts:
        return blocks
    
    # Group posts by thread for conversation blocks
    try:
        # Create a single conversation block for the entire thread
        clean_posts = []
        
        for i, post in enumerate(posts):
            try:
                post_id = _extract_post_id(post.get("post_link", ""))
                author = _clean_text(post.get("author", "Unknown"))
                timestamp_str = post.get("timestamp", "")
                text = _clean_text(post.get("text", ""))
                post_link = post.get("post_link", "")
                
                # Parse timestamp
                created_at = _parse_lucid_timestamp(timestamp_str)
                
                # Create CleanPost object
                clean_post = CleanPost(
                    thread_id=f"lucid_{thread_link.split('/')[-1]}",
                    source_url=post_link,
                    post_id=post_id,
                    post_number=i + 1,
                    username=author or "Anonymous",
                    created_at=created_at,
                    updated_at=created_at,
                    text=text or "No content",
                    reply_to_post_number=None,
                    topic_title=thread_title,
                    date=created_at.date(),
                    week_year=created_at.isocalendar()[0],
                    week_number=created_at.isocalendar()[1]
                )
                
                clean_posts.append(clean_post)
                
            except Exception as e:
                print(f"[LucidData] Error processing post {i}: {e}")
                continue
        
        if clean_posts:
            # Create individual blocks for each post (or small groups)
            # This ensures 75 posts create multiple blocks, not just 1
            
            # Group posts into chunks of 5-10 posts per block for better granularity
            chunk_size = 5
            
            for chunk_idx in range(0, len(clean_posts), chunk_size):
                chunk = clean_posts[chunk_idx:chunk_idx + chunk_size]
                
                if not chunk:
                    continue
                
                root_post = chunk[0]
                replies = chunk[1:] if len(chunk) > 1 else []
                
                # Combine text for this chunk
                flattened_parts = []
                for post in chunk:
                    if post.username and post.text:
                        flattened_parts.append(f"{post.username}: {post.text}")
                
                flattened_text = "\n\n".join(flattened_parts)
                
                # Determine time range for this chunk
                chunk_timestamps = [p.created_at for p in chunk]
                start_datetime = min(chunk_timestamps) if chunk_timestamps else datetime.now()
                end_datetime = max(chunk_timestamps) if chunk_timestamps else datetime.now()
                
                # Create conversation block with unique ID for each chunk
                block = ConversationBlock(
                    block_id=f"lucid_{thread_link.split('/')[-1]}_chunk_{chunk_idx // chunk_size}",
                    thread_id=f"lucid_{thread_link.split('/')[-1]}",
                    source_url=thread_link,
                    topic_title=thread_title,
                    root_post=root_post,
                    replies=replies,
                    flattened_text=flattened_text,
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    phone_number=None
                )
                
                blocks.append(block)
    
    except Exception as e:
        print(f"[LucidData] Error creating conversation blocks: {e}")
    
    print(f"[LucidData] Successfully created {len(blocks)} conversation blocks from Lucid posts")
    return blocks


def format_lucid_post_for_display(post: Dict[str, Any]) -> str:
    """
    Format a Lucid forum post for display in the chat interface.
    
    Args:
        post: Lucid post dictionary
        
    Returns:
        Formatted string for display
    """
    author = post.get("author", "Unknown")
    timestamp = post.get("timestamp", "")
    text = post.get("text", "")
    post_link = post.get("post_link", "")
    
    # Build formatted output
    output_parts = []
    
    # Header with author and timestamp
    header = f"**{author}**"
    if timestamp:
        header += f" • {timestamp}"
    output_parts.append(header)
    
    # Content
    if text:
        # Truncate long content
        content = text[:500] + "..." if len(text) > 500 else text
        output_parts.append(content)
    
    # Link
    if post_link:
        output_parts.append(f"[View Post]({post_link})")
    
    return "\n\n".join(output_parts)


def extract_lucid_insights(blocks: List[ConversationBlock]) -> Dict[str, Any]:
    """
    Extract insights from Lucid conversation blocks.
    
    Args:
        blocks: List of conversation blocks from Lucid
        
    Returns:
        Dictionary containing insights
    """
    if not blocks:
        return {}
    
    # Collect statistics
    total_posts = sum(1 + len(block.replies) for block in blocks)
    authors = set()
    total_words = 0
    
    for block in blocks:
        # Count root post author
        if block.root_post and block.root_post.username:
            authors.add(block.root_post.username)
            if block.root_post.text:
                total_words += len(block.root_post.text.split())
        
        # Count reply authors and words
        for reply in block.replies:
            if reply.username:
                authors.add(reply.username)
            if reply.text:
                total_words += len(reply.text.split())
    
    avg_words_per_post = total_words / total_posts if total_posts > 0 else 0
    
    return {
        "total_posts": total_posts,
        "total_threads": len(blocks),
        "unique_authors": len(authors),
        "total_words": total_words,
        "average_words_per_post": round(avg_words_per_post, 2),
        "authors": list(authors)[:10]  # Top 10 authors
    }
