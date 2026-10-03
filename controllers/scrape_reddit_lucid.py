"""
Reddit Lucid Scraper - Scrapes Lucid Motors subreddits in a loop
Handles: r/lucidmotors and r/LUCID
Saves to: reddit_lucid_posts table in posts.db
"""

import json
import time
from datetime import datetime
from pathlib import Path
from controllers.scraping import search_reddit_posts, export_reddit_posts_to_files
from models.reddit_lucid_post import RedditLucidPost
from utils.logger import server_logger


def scrape_reddit_lucid_loop(subreddits=None, max_posts_per_subreddit=100, delay_between_subreddits=5):
    """
    Scrape Lucid Motors subreddits in a loop
    
    Args:
        subreddits: List of subreddit URLs (e.g., ["https://www.reddit.com/r/lucidmotors/", "https://www.reddit.com/r/LUCID/"])
        max_posts_per_subreddit: Maximum posts to scrape per subreddit
        delay_between_subreddits: Delay in seconds between scraping subreddits
    
    Returns:
        Dictionary with scraping results
    """
    
    if subreddits is None:
        subreddits = [
            "https://www.reddit.com/r/lucidmotors/",
            "https://www.reddit.com/r/LUCID/"
        ]
    
    results = {
        "total_posts": 0,
        "total_saved": 0,
        "total_skipped": 0,
        "subreddits_processed": [],
        "errors": []
    }
    
    # Ensure table exists
    RedditLucidPost.create_table()
    
    for idx, subreddit_url in enumerate(subreddits):
        try:
            # Extract subreddit name from URL
            subreddit_name = subreddit_url.strip('/').split('/')[-1]
            
            server_logger.info(f"[Reddit Lucid] Scraping subreddit {idx + 1}/{len(subreddits)}: {subreddit_name}")
            print(f"\n[Reddit Lucid] Scraping subreddit {idx + 1}/{len(subreddits)}: {subreddit_name}")
            
            # Search for Lucid-related posts in this subreddit
            posts = search_reddit_posts(
                query="Lucid",
                subreddit=subreddit_name,
                sort="new",
                time_filter="all",
                max_posts=max_posts_per_subreddit,
                include_comments=True
            )
            
            if not posts:
                server_logger.warning(f"[Reddit Lucid] No posts found in {subreddit_name}")
                print(f"⚠️ No posts found in {subreddit_name}")
                results["subreddits_processed"].append({
                    "subreddit": subreddit_name,
                    "posts_found": 0,
                    "posts_saved": 0,
                    "posts_skipped": 0
                })
                continue
            
            server_logger.info(f"[Reddit Lucid] Found {len(posts)} posts in {subreddit_name}")
            print(f"✅ Found {len(posts)} posts in {subreddit_name}")
            
            # Save posts to database
            saved, skipped = RedditLucidPost.save_reddit_lucid_posts_to_db(
                subreddit=subreddit_name,
                posts=posts,
                user_id=1,  # Default user ID
                company_id="lucid"
            )
            
            results["total_posts"] += len(posts)
            results["total_saved"] += saved
            results["total_skipped"] += skipped
            
            results["subreddits_processed"].append({
                "subreddit": subreddit_name,
                "posts_found": len(posts),
                "posts_saved": saved,
                "posts_skipped": skipped
            })
            
            server_logger.info(f"[Reddit Lucid] Saved {saved} posts, skipped {skipped} duplicates from {subreddit_name}")
            print(f"💾 Saved {saved} posts, skipped {skipped} duplicates")
            
            # Delay between subreddits to avoid rate limiting
            if idx < len(subreddits) - 1:
                print(f"⏳ Waiting {delay_between_subreddits} seconds before next subreddit...")
                time.sleep(delay_between_subreddits)
        
        except Exception as e:
            error_msg = f"Error scraping {subreddit_url}: {str(e)}"
            server_logger.error(f"[Reddit Lucid] {error_msg}")
            print(f"❌ {error_msg}")
            results["errors"].append(error_msg)
    
    # Log final results
    server_logger.info(f"[Reddit Lucid] Scraping complete: {results['total_posts']} posts found, {results['total_saved']} saved, {results['total_skipped']} skipped")
    print(f"\n[Reddit Lucid] Scraping complete:")
    print(f"  Total posts found: {results['total_posts']}")
    print(f"  Total saved: {results['total_saved']}")
    print(f"  Total skipped: {results['total_skipped']}")
    
    return results


def export_reddit_lucid_to_json(company_id="lucid"):
    """
    Export Reddit Lucid posts from database to JSON file
    
    Args:
        company_id: Company ID (default: "lucid")
    
    Returns:
        Path to exported JSON file
    """
    
    # Get all Reddit Lucid posts for the company
    posts = RedditLucidPost.get_posts_by_company(company_id)
    
    if not posts:
        print(f"⚠️ No Reddit Lucid posts found for {company_id}")
        return None
    
    # Convert to dictionary format
    posts_data = []
    for post in posts:
        posts_data.append({
            "post_id": post.post_id,
            "subreddit": post.subreddit,
            "title": post.title,
            "author": post.author,
            "created_at": post.created_at,
            "text": post.text,
            "post_url": post.post_url,
            "score": post.score,
            "num_comments": post.num_comments
        })
    
    # Create JSON file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_filename = f"data/reddit_lucid_{company_id}_{timestamp}.json"
    
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump({
            "subreddits": ["r/lucidmotors", "r/LUCID"],
            "total_posts": len(posts_data),
            "exported_at": datetime.now().isoformat(),
            "posts": posts_data
        }, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Exported {len(posts_data)} Reddit Lucid posts to {json_filename}")
    return json_filename


def get_reddit_lucid_statistics():
    """Get statistics about Reddit Lucid posts"""
    stats = RedditLucidPost.get_statistics(company_id="lucid")
    return stats
