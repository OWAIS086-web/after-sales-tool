# ai/utils/reddit_data.py
"""
Reddit data processing utilities for the Haval pipeline.
Converts Reddit posts to conversation blocks for analysis.
"""

from typing import List, Dict, Any
from ai.models import ConversationBlock
import hashlib
from datetime import datetime


def reddit_posts_to_conversation_blocks(data: Dict[str, Any]) -> List[ConversationBlock]:
    """
    Convert Reddit posts data to conversation blocks.
    
    Args:
        data: Reddit data dictionary containing posts
        
    Returns:
        List of ConversationBlock objects
    """
    blocks = []
    posts = data.get("posts", [])
    query = data.get("query", "reddit_search")
    
    print(f"[RedditData] Processing {len(posts)} Reddit posts for query: '{query}'")
    
    for i, post in enumerate(posts):
        try:
            # Extract post information
            post_id = post.get("post_id", f"reddit_post_{i}")
            # Convert post_id to int for CleanPost model
            try:
                post_id_int = int(post_id.split('_')[-1]) if isinstance(post_id, str) else post_id
            except (ValueError, IndexError):
                post_id_int = i + 1
            title = post.get("title", "")
            selftext = post.get("selftext", "")
            author = post.get("author", "Unknown")
            subreddit = post.get("subreddit", "")
            created_at = post.get("created_at", "")
            score = post.get("score", 0)
            num_comments = post.get("num_comments", 0)
            permalink = post.get("permalink", "")
            
            # Combine title and selftext for content
            content_parts = []
            if title:
                content_parts.append(f"Title: {title}")
            if selftext:
                content_parts.append(f"Content: {selftext}")
            
            content = "\n".join(content_parts) if content_parts else title or "No content"
            
            # Parse timestamp
            try:
                if created_at:
                    # Reddit timestamps are in format "YYYY-MM-DD HH:MM:SS"
                    timestamp = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                else:
                    timestamp = datetime.now()
            except (ValueError, TypeError):
                timestamp = datetime.now()
            
            # Create CleanPost for the Reddit post
            from ai.models import CleanPost
            clean_post = CleanPost(
                thread_id=f"reddit_{query}",
                source_url=permalink,
                post_id=post_id_int,  # Use integer post_id
                post_number=i + 1,  # Sequential numbering
                username=author,
                created_at=timestamp,
                updated_at=timestamp,
                text=content,  # Use 'text' not 'clean_text'
                reply_to_post_number=None,  # Reddit posts don't have replies in our model
                topic_title=f"Reddit Search: {query}",
                date=timestamp.date(),
                week_year=timestamp.isocalendar()[0],
                week_number=timestamp.isocalendar()[1]
            )
            
            # Generate unique block ID
            block_id = f"reddit_{query}_{post_id}"
            
            # Create conversation block
            block = ConversationBlock(
                block_id=block_id,
                thread_id=f"reddit_{query}",
                source_url=permalink,
                topic_title=f"Reddit Search: {query}",
                root_post=clean_post,
                replies=[],  # Reddit posts don't have replies in our model
                flattened_text=content,
                start_datetime=timestamp,
                end_datetime=timestamp,
                phone_number=None  # Not applicable for Reddit
            )
            
            blocks.append(block)
            
        except Exception as e:
            print(f"[RedditData] Error processing post {i}: {e}")
            continue
    
    print(f"[RedditData] Successfully created {len(blocks)} conversation blocks from Reddit posts")
    return blocks


def format_reddit_post_for_display(post: Dict[str, Any]) -> str:
    """
    Format a Reddit post for display in the chat interface.
    
    Args:
        post: Reddit post dictionary
        
    Returns:
        Formatted string for display
    """
    title = post.get("title", "")
    author = post.get("author", "Unknown")
    subreddit = post.get("subreddit", "")
    score = post.get("score", 0)
    num_comments = post.get("num_comments", 0)
    selftext = post.get("selftext", "")
    permalink = post.get("permalink", "")
    
    # Build formatted output
    output_parts = []
    
    # Header with subreddit and author
    if subreddit:
        output_parts.append(f"**r/{subreddit}** • u/{author}")
    else:
        output_parts.append(f"u/{author}")
    
    # Title
    if title:
        output_parts.append(f"**{title}**")
    
    # Content (if available)
    if selftext:
        # Truncate long content
        content = selftext[:500] + "..." if len(selftext) > 500 else selftext
        output_parts.append(content)
    
    # Stats
    stats_parts = []
    if score is not None:
        stats_parts.append(f"↑ {score}")
    if num_comments is not None:
        stats_parts.append(f"💬 {num_comments}")
    
    if stats_parts:
        output_parts.append(" • ".join(stats_parts))
    
    # Link
    if permalink:
        output_parts.append(f"[View on Reddit]({permalink})")
    
    return "\n\n".join(output_parts)


def extract_reddit_insights(blocks: List[ConversationBlock]) -> Dict[str, Any]:
    """
    Extract insights from Reddit conversation blocks.
    
    Args:
        blocks: List of conversation blocks from Reddit
        
    Returns:
        Dictionary containing insights
    """
    if not blocks:
        return {}
    
    # Collect statistics
    total_posts = len(blocks)
    subreddits = set()
    authors = set()
    total_score = 0
    total_comments = 0
    
    for block in blocks:
        metadata = block.metadata or {}
        subreddit = metadata.get("subreddit", "")
        author = metadata.get("author", "")
        score = metadata.get("score", 0)
        num_comments = metadata.get("num_comments", 0)
        
        if subreddit:
            subreddits.add(subreddit)
        if author:
            authors.add(author)
        
        total_score += score if isinstance(score, int) else 0
        total_comments += num_comments if isinstance(num_comments, int) else 0
    
    # Calculate averages
    avg_score = total_score / total_posts if total_posts > 0 else 0
    avg_comments = total_comments / total_posts if total_posts > 0 else 0
    
    return {
        "total_posts": total_posts,
        "unique_subreddits": len(subreddits),
        "unique_authors": len(authors),
        "subreddits": list(subreddits),
        "total_score": total_score,
        "total_comments": total_comments,
        "average_score": round(avg_score, 2),
        "average_comments": round(avg_comments, 2)
    }