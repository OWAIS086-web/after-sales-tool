import os
import time
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin
from tqdm import tqdm
from flask import current_app
from models.database import get_db_connection
from models.post import Post
from utils.logger import scraping_logger, warning_logger, log_error

# Configuration
BASE = "https://www.pakwheels.com/forums/"
REDDIT_BASE = "https://www.reddit.com"
DATA_DIR = "data"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9"
}
REDDIT_HEADERS = {
    "User-Agent": ("RedditScraper/1.0 (by /u/YourUsername) Python/3.9"),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9"
}
DEFAULT_DELAY = 0.6
DEFAULT_MAX_TOPICS = 500
DEFAULT_MAX_POSTS = 10000

def filter_posts_by_year(posts, min_year):
    """
    Filter posts to only include those from min_year onwards.

    Args:
        posts: List of post dictionaries with 'created_at' field
        min_year: Minimum year (e.g., 2025) - can be int or str

    Returns:
        Filtered list of posts
    """
    from datetime import datetime
    from dateutil import parser as date_parser

    if not min_year or not posts:
        return posts

    # Ensure min_year is an integer
    try:
        min_year = int(min_year)
    except (ValueError, TypeError):
        scraping_logger.warning(f"⚠️ Invalid min_year value: {min_year}, skipping year filter")
        return posts

    filtered = []
    removed_count = 0

    for post in posts:
        try:
            # Parse the created_at timestamp
            created_at_str = post.get('created_at', '')
            if created_at_str:
                # Try multiple date formats
                post_dt = None

                # Format 1: Reddit format "YYYY-MM-DD HH:MM:SS"
                try:
                    post_dt = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    pass

                # Format 2: ISO 8601 with timezone (PakWheels format)
                if not post_dt:
                    try:
                        post_dt = date_parser.isoparse(created_at_str)
                    except (ValueError, TypeError):
                        pass

                # If we successfully parsed the date, check the year
                if post_dt:
                    post_year = post_dt.year
                    if post_year >= min_year:
                        filtered.append(post)
                    else:
                        removed_count += 1
                else:
                    # If parsing failed, keep the post (benefit of the doubt)
                    scraping_logger.warning(f"⚠️  Could not parse date '{created_at_str}', keeping post")
                    filtered.append(post)
            else:
                # If no created_at, keep the post (benefit of the doubt)
                filtered.append(post)
        except Exception as e:
            # If parsing fails, keep the post
            scraping_logger.warning(f"⚠️  Failed to parse date for filtering: {e}")
            filtered.append(post)

    if removed_count > 0:
        scraping_logger.info(f"🗑️  Filtered out {removed_count} posts older than {min_year}")

    return filtered

def get_soup(url, timeout=15):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        scraping_logger.warning(f"Failed to GET {url}: {e}")
        return None


def get_json(url, timeout=15, max_retries=3):
    """
    Fetch JSON data from URL with retry mechanism and better error handling
    """
    for attempt in range(max_retries):
        try:
            scraping_logger.info(f"🔍 Fetching JSON (attempt {attempt + 1}/{max_retries}): {url}")
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            
            # Check if response looks like JSON before parsing
            try:
                return resp.json()
            except json.JSONDecodeError as json_err:
                # Log the actual response content for debugging
                response_preview = resp.text[:200] if resp.text else "Empty response"
                scraping_logger.warning(f"❌ JSON decode error for {url}: {json_err}")
                scraping_logger.warning(f"Response preview: {response_preview}")
                
                # Check for common error patterns
                if 'page not found' in resp.text.lower():
                    scraping_logger.warning(f"📄 'Page not found' detected - URL may be invalid: {url}")
                    return None  # Don't retry for page not found
                elif 'error' in resp.text.lower() and len(resp.text) < 1000:
                    scraping_logger.warning(f"❌ Error page detected - skipping: {url}")
                    return None  # Don't retry for error pages
                
                # For other JSON errors, continue to retry logic
                if attempt < max_retries - 1:
                    scraping_logger.info(f"🔄 Will retry JSON parsing...")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    scraping_logger.error(f"💥 Final JSON decode failure for {url}")
                    return None
                    
        except requests.exceptions.Timeout:
            scraping_logger.warning(f"⏰ Timeout fetching JSON from {url} (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        except requests.exceptions.ConnectionError:
            scraping_logger.warning(f"🔌 Connection error fetching JSON from {url} (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                scraping_logger.warning(f"📄 Post not found (404): {url}")
                return None  # Don't retry for 404s
            elif e.response.status_code == 429:
                scraping_logger.warning(f"🚫 Rate limited (429): {url} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))  # Longer wait for rate limiting
            else:
                scraping_logger.warning(f"🌐 HTTP error {e.response.status_code} fetching JSON from {url} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        except Exception as e:
            scraping_logger.warning(f"❌ Failed to GET JSON {url} (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    scraping_logger.error(f"💥 Failed to fetch JSON after {max_retries} attempts: {url}")
    return None


def fetch_categories():
    """Scrape forum main page and return category links (unique)."""
    soup = get_soup(BASE)
    if not soup:
        return []

    cats = []
    seen = set()
    for a in soup.select("a[href*='/forums/c/']"):
        name = a.get_text(strip=True)
        href = a.get("href")
        if not href or not name:
            continue
        full = urljoin(BASE, href)
        if full not in seen:
            cats.append({"name": name, "href": full})
            seen.add(full)
    # sort by name
    cats.sort(key=lambda x: x["name"].lower())
    return cats


def collect_all_topics_from_category(category_url, delay=DEFAULT_DELAY, max_topics=DEFAULT_MAX_TOPICS):
    """
    Walk pagination for a category and collect topic titles + urls until end or max_topics reached.
    Returns list of {title, href}
    """
    topics = []
    seen = set()
    page = 1
    while True:
        if page == 1:
            url = category_url
        else:
            # Discourse uses ?page=N for forum category pagination
            url = f"{category_url}?page={page}"
        scraping_logger.info(f"Fetching topic list: {url}")
        soup = get_soup(url)
        if not soup:
            break

        found_on_page = 0
        for a in soup.select("a[href*='/t/']"):
            href = a.get("href")
            if not href:
                continue
            full = urljoin(category_url, href)
            title = a.get_text(strip=True)
            if not title or full in seen:
                continue
            topics.append({"title": title, "href": full})
            seen.add(full)
            found_on_page += 1
            if len(topics) >= max_topics:
                return topics

        if found_on_page == 0:
            break
        page += 1
        time.sleep(delay)
    return topics


def fetch_posts_for_topic_via_json(topic_url, max_posts=DEFAULT_MAX_POSTS, delay=DEFAULT_DELAY, descending=False, min_year=None):
    """
    Fetch posts from a Discourse topic using post number ranges.
    Gets LATEST posts when descending=True by fetching from the end.

    Args:
        topic_url: URL of the topic
        max_posts: Maximum number of posts to fetch
        delay: Delay between requests
        descending: If True, fetch latest posts first (newest to oldest)
        min_year: Minimum year for posts (e.g., 2025) - filters out older posts
    """
    # Convert max_posts to int if it's a string (from request parameters)
    try:
        max_posts = int(max_posts)
    except (ValueError, TypeError):
        scraping_logger.warning(f"Invalid max_posts value: {max_posts}, using default: {DEFAULT_MAX_POSTS}")
        max_posts = DEFAULT_MAX_POSTS
    
    # Clean URL
    base_url = topic_url.rstrip("/").split("?")[0].split("#")[0]
    json_url = base_url + ".json"
    
    # Add debugging for URL validation
    scraping_logger.info(f"🔗 Original topic URL: {topic_url}")
    scraping_logger.info(f"🔗 Cleaned base URL: {base_url}")
    scraping_logger.info(f"🔍 JSON URL to fetch: {json_url}")
    
    # Validate URL format
    if not base_url.startswith("https://www.pakwheels.com/forums/t/"):
        scraping_logger.error(f"❌ Invalid PakWheels URL format: {base_url}")
        scraping_logger.error("Expected format: https://www.pakwheels.com/forums/t/topic-name/topic-id")
        return []
    
    # Check if URL has proper topic ID
    url_parts = base_url.split('/')
    if len(url_parts) < 6:
        scraping_logger.error(f"❌ URL appears incomplete: {base_url}")
        scraping_logger.error("URL should have format: https://www.pakwheels.com/forums/t/topic-name/topic-id")
        return []
    
    topic_id = url_parts[-1]
    if not topic_id.isdigit():
        scraping_logger.warning(f"⚠️ Topic ID is not numeric: '{topic_id}' - this may cause issues")
    
    scraping_logger.info(f"🔍 Fetching topic: {json_url}")
    data = get_json(json_url)
    if not data:
        scraping_logger.error(f"❌ Failed to fetch topic data from: {json_url}")
        scraping_logger.error("🔧 Possible causes:")
        scraping_logger.error("   • Topic may not exist or has been deleted")
        scraping_logger.error("   • Topic URL is malformed or incorrect")
        scraping_logger.error("   • Network connectivity issues")
        scraping_logger.error("   • PakWheels server is down or blocking requests")
        scraping_logger.error("   • Rate limiting or firewall restrictions")
        scraping_logger.error("💡 Verify the topic URL is correct and accessible in a browser")
        return []

    # Validate response structure
    if not isinstance(data, dict):
        scraping_logger.error(f"❌ Invalid response format - expected dict, got {type(data)}")
        return []

    # Get topic metadata
    topic_title = data.get("title", "")
    posts_count = data.get("posts_count", 0)
    highest_post_number = data.get("highest_post_number", posts_count)
    
    if posts_count == 0:
        scraping_logger.warning(f"⚠️ Topic has no posts: {topic_title}")
        return []
    
    scraping_logger.info(f"📊 Topic: '{topic_title[:50]}...'")
    scraping_logger.info(f"📊 Total posts: {posts_count} | Highest post #: {highest_post_number}")
    
    # Determine which post numbers to fetch
    if descending:
        # Get LATEST posts - start from the highest post number and go backwards
        start_post = max(1, highest_post_number - max_posts + 1)
        end_post = highest_post_number
        scraping_logger.info(f"📥 LATEST MODE: Fetching posts #{start_post} to #{end_post} (newest first)")
    else:
        # Get OLDEST posts - start from post #1
        start_post = 1
        end_post = min(max_posts, highest_post_number)
        scraping_logger.info(f"📤 OLDEST MODE: Fetching posts #{start_post} to #{end_post} (oldest first)")
    
    # Fetch posts using post number ranges (Discourse loads 20 posts at a time)
    all_posts = []
    seen_post_ids = set()
    chunk_size = 20  # Discourse returns ~20 posts per request
    
    # Calculate how many requests we need
    total_posts_to_fetch = end_post - start_post + 1

    print(f"\n🔄 Starting to scrape {total_posts_to_fetch} posts in chunks of {chunk_size}...")
    for post_num in tqdm(range(start_post, end_post + 1, chunk_size),
                          desc="📡 Scraping posts",
                          unit="chunk",
                          ncols=100):
        # Fetch posts starting from this post number
        fetch_url = f"{base_url}/{post_num}.json"

        scraping_logger.info(f"📡 Fetching chunk from post #{post_num}: {fetch_url}")
        
        chunk_data = get_json(fetch_url)
        if not chunk_data:
            scraping_logger.warning(f"⚠️ Failed to fetch posts starting at #{post_num}")
            
            # Add retry logic for failed requests
            retry_count = 0
            max_retries = 3
            while retry_count < max_retries and not chunk_data:
                retry_count += 1
                scraping_logger.info(f"🔄 Retrying fetch for post #{post_num} (attempt {retry_count}/{max_retries})")
                time.sleep(delay * retry_count)  # Exponential backoff
                chunk_data = get_json(fetch_url)
            
            if not chunk_data:
                scraping_logger.error(f"❌ Failed to fetch posts after {max_retries} retries, skipping post #{post_num}")
                # Skip this chunk but continue with next
                continue
        
        chunk_posts = chunk_data.get("post_stream", {}).get("posts", [])
        
        # Process posts
        for p in chunk_posts:
            post_id = p.get("id")
            post_number = p.get("post_number", 0)
            
            # Skip if outside our range
            if post_number < start_post or post_number > end_post:
                continue
            
            # Skip duplicates
            if post_id in seen_post_ids:
                continue
            
            seen_post_ids.add(post_id)
            post_data = {
                "post_number": post_number,
                "username": p.get("username") or p.get("name") or "Unknown",
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at"),
                "cooked": p.get("cooked", ""),
                "reply_count": p.get("reply_count", 0),
                "reply_to_post_number": p.get("reply_to_post_number"),
                "quote_count": p.get("quote_count", 0),
                "reads": p.get("reads", 0),
                "topic_title": topic_title
            }
            all_posts.append(post_data)
        
        scraping_logger.info(f"   Retrieved {len(chunk_posts)} posts | Total unique: {len(all_posts)}")
        
        # Stop if we have enough posts
        if len(all_posts) >= total_posts_to_fetch:
            break
        
        # Polite delay
        time.sleep(delay)
    
    # Sort posts
    if descending:
        # Sort by post_number descending (newest first)
        all_posts.sort(key=lambda x: x.get("post_number", 0), reverse=True)
    else:
        # Sort by post_number ascending (oldest first)
        all_posts.sort(key=lambda x: x.get("post_number", 0))
    
    # Limit to max_posts
    all_posts = all_posts[:max_posts]

    # Apply year filter if specified
    if min_year:
        all_posts = filter_posts_by_year(all_posts, min_year)
        scraping_logger.info(f"✅ Fetched {len(all_posts)} unique posts (order: {'NEWEST→OLDEST' if descending else 'OLDEST→NEWEST'}, year filter: {min_year}+)")
    else:
        scraping_logger.info(f"✅ Fetched {len(all_posts)} unique posts (order: {'NEWEST→OLDEST' if descending else 'OLDEST→NEWEST'})")
    
    # Log date range
    if all_posts:
        first_date = all_posts[0].get("created_at", "")[:10]
        last_date = all_posts[-1].get("created_at", "")[:10]
        scraping_logger.info(f"📅 Date range: {first_date} to {last_date}")
    
    return all_posts


    scraping_logger.info(f"Saved {saved_count} new posts, skipped {skipped_count} duplicates")
    return saved_count, skipped_count


def export_topic_posts_to_files(category_slug, topic_title, topic_url, posts):
    """Save per-topic JSON and CSV in data/"""
    safe_slug = category_slug.replace("/", "_")
    topic_safe = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in topic_title)[:100]
    base = os.path.join(DATA_DIR, f"{safe_slug}__{topic_safe}")
    json_path = base + ".json"
    csv_path = base + ".csv"

    # JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"topic": topic_title, "url": topic_url, "posts": posts}, f, ensure_ascii=False, indent=2)

    # CSV (flatten)
    rows = []
    for p in posts:
        text = p.get("cooked") or ""
        plain = BeautifulSoup(text, "lxml").get_text(" ", strip=True) if text else ""
        rows.append({
            "post_number": p.get("post_number"),
            "author": p.get("username"),
            "created_at": p.get("created_at"),
            "content": plain
        })
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False, encoding="utf-8")

    return json_path, csv_path


# ============================================================================
# REDDIT SCRAPING FUNCTIONS
# ============================================================================

def get_reddit_json(url, timeout=15, max_retries=3):
    """
    Fetch JSON data from Reddit API with retry mechanism
    """
    for attempt in range(max_retries):
        try:
            scraping_logger.info(f"🔍 Fetching Reddit JSON (attempt {attempt + 1}/{max_retries}): {url}")
            resp = requests.get(url, headers=REDDIT_HEADERS, timeout=timeout)
            resp.raise_for_status()
            
            # Check if response looks like JSON before parsing
            try:
                return resp.json()
            except json.JSONDecodeError as json_err:
                # Log the actual response content for debugging
                response_preview = resp.text[:200] if resp.text else "Empty response"
                scraping_logger.warning(f"❌ JSON decode error for {url}: {json_err}")
                scraping_logger.warning(f"Response preview: {response_preview}")
                
                # Check for common error patterns
                if 'not found' in resp.text.lower() or '404' in resp.text:
                    scraping_logger.warning(f"📄 'Not found' detected - URL may be invalid: {url}")
                    return None  # Don't retry for not found
                elif 'error' in resp.text.lower() and len(resp.text) < 1000:
                    scraping_logger.warning(f"❌ Error page detected - skipping: {url}")
                    return None  # Don't retry for error pages
                
                # For other JSON errors, continue to retry logic
                if attempt < max_retries - 1:
                    scraping_logger.info(f"🔄 Will retry JSON parsing...")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    scraping_logger.error(f"💥 Final JSON decode failure for {url}")
                    return None
                    
        except requests.exceptions.Timeout:
            scraping_logger.warning(f"⏰ Timeout fetching JSON from {url} (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        except requests.exceptions.ConnectionError:
            scraping_logger.warning(f"🔌 Connection error fetching JSON from {url} (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                scraping_logger.warning(f"📄 Post not found (404): {url}")
                return None  # Don't retry for 404s
            elif e.response.status_code == 429:
                scraping_logger.warning(f"🚫 Rate limited (429): {url} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))  # Longer wait for rate limiting
            else:
                scraping_logger.warning(f"🌐 HTTP error {e.response.status_code} fetching JSON from {url} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        except Exception as e:
            scraping_logger.warning(f"❌ Failed to GET JSON {url} (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    scraping_logger.error(f"💥 Failed to fetch Reddit JSON after {max_retries} attempts: {url}")
    return None


def search_reddit_posts(query, subreddit=None, sort="relevance", time_filter="all", max_posts=DEFAULT_MAX_POSTS, delay=DEFAULT_DELAY, include_comments=True, disable_comments_on_403=True, min_year=None):
    """
    Search Reddit posts using multiple powerful scraping methods and optionally scrape comments

    Args:
        query: Search query (e.g., "haval car")
        subreddit: Specific subreddit to search (optional)
        sort: Sort method ("relevance", "hot", "top", "new", "comments")
        time_filter: Time filter ("all", "year", "month", "week", "day", "hour")
        max_posts: Maximum number of posts to fetch
        delay: Delay between requests
        include_comments: Whether to scrape comments for each post
        disable_comments_on_403: Disable comment scraping if getting 403 errors
        min_year: Minimum year for posts (e.g., 2025 to only get posts from 2025 onwards)
    """

    scraping_logger.info(f"📊 Parameters: q='{query}', restrict_sr='on', sort='{sort}', t='{time_filter}', limit={max_posts}")
    if min_year:
        scraping_logger.info(f"📅 Year filter: Only posts from {min_year} onwards")
    scraping_logger.info(f"🔄 Starting to search Reddit for '{query}' (max {max_posts} posts)...")
    if include_comments:
        scraping_logger.info(f"💬 Comments scraping: ENABLED")
    
    # Method 1: Try PRAW (Python Reddit API Wrapper) - Most reliable
    posts = try_praw_scraping(query, subreddit, sort, time_filter, max_posts, include_comments and not disable_comments_on_403)
    if posts:
        # Apply year filter if specified
        if min_year:
            posts = filter_posts_by_year(posts, min_year)
            scraping_logger.info(f"✅ Successfully fetched {len(posts)} posts using PRAW (after year filter: {min_year}+)")
        else:
            scraping_logger.info(f"✅ Successfully fetched {len(posts)} posts using PRAW")
        return posts

    # Method 2: Try Reddit JSON API with advanced techniques
    posts = try_advanced_reddit_api(query, subreddit, sort, time_filter, max_posts, include_comments and not disable_comments_on_403)
    if posts:
        # Apply year filter if specified
        if min_year:
            posts = filter_posts_by_year(posts, min_year)
            scraping_logger.info(f"✅ Successfully fetched {len(posts)} posts from Reddit API (after year filter: {min_year}+)")
        else:
            scraping_logger.info(f"✅ Successfully fetched {len(posts)} posts from Reddit API")
        return posts
    
    # Method 3: Try web scraping with requests-html
    posts = try_web_scraping_reddit(query, subreddit, sort, time_filter, max_posts, delay)
    if posts:
        scraping_logger.info(f"✅ Successfully scraped {len(posts)} posts from Reddit web")
        return posts
    
    # Method 4: Try Selenium web scraping (most powerful but slower)
    posts = try_selenium_reddit_scraping(query, subreddit, sort, time_filter, max_posts)
    if posts:
        scraping_logger.info(f"✅ Successfully scraped {len(posts)} posts using Selenium")
        return posts
    
    # Method 5: Try alternative Reddit endpoints
    posts = try_alternative_reddit_endpoints(query, subreddit, sort, time_filter, max_posts)
    if posts:
        scraping_logger.info(f"✅ Successfully fetched {len(posts)} posts from alternative endpoints")
        return posts
    
    # If all methods fail, inform user
    scraping_logger.error("❌ All Reddit scraping methods failed!")
    scraping_logger.error("🔧 Possible solutions:")
    scraping_logger.error("   • Check internet connection")
    scraping_logger.error("   • Try different search terms")
    scraping_logger.error("   • Reddit may be blocking requests")
    scraping_logger.error("   • Consider using Reddit API credentials")
    
    return []


def try_praw_scraping(query, subreddit=None, sort="relevance", time_filter="all", max_posts=DEFAULT_MAX_POSTS, include_comments=True):
    """
    Try to scrape Reddit using PRAW (Python Reddit API Wrapper) with comment scraping
    """
    try:
        scraping_logger.info("🚀 Attempting PRAW (Reddit API Wrapper)...")
        
        import praw
        
        # Ensure max_posts is an integer
        try:
            max_posts = int(max_posts)
        except (ValueError, TypeError):
            scraping_logger.warning(f"⚠️ Invalid max_posts value: {max_posts}, using default: {DEFAULT_MAX_POSTS}")
            max_posts = DEFAULT_MAX_POSTS
        
        # Initialize Reddit instance (read-only, no credentials needed for public data)
        reddit = praw.Reddit(
            client_id="dummy",  # Not needed for read-only access to public data
            client_secret="dummy",
            user_agent="RedditScraper/1.0 (Educational Purpose)"
        )
        
        posts = []
        
        if subreddit:
            # Search in specific subreddit
            subreddit_obj = reddit.subreddit(subreddit)
            
            if sort == "hot":
                submissions = subreddit_obj.hot(limit=max_posts)
            elif sort == "top":
                submissions = subreddit_obj.top(time_filter=time_filter, limit=max_posts)
            elif sort == "new":
                submissions = subreddit_obj.new(limit=max_posts)
            else:  # relevance or search
                submissions = subreddit_obj.search(query, sort=sort, time_filter=time_filter, limit=max_posts)
        else:
            # Search all of Reddit
            submissions = reddit.subreddit("all").search(query, sort=sort, time_filter=time_filter, limit=max_posts)
        
        scraping_logger.info(f"📡 Fetching posts using PRAW...")
        
        for i, submission in enumerate(submissions):
            try:
                from datetime import datetime
                
                post = {
                    "post_id": submission.id,
                    "title": submission.title,
                    "author": str(submission.author) if submission.author else "Unknown",
                    "subreddit": str(submission.subreddit),
                    "created_utc": submission.created_utc,
                    "created_at": datetime.fromtimestamp(submission.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                    "score": submission.score,
                    "upvote_ratio": submission.upvote_ratio,
                    "num_comments": submission.num_comments,
                    "selftext": submission.selftext,
                    "url": submission.url,
                    "permalink": f"https://reddit.com{submission.permalink}",
                    "is_self": submission.is_self,
                    "domain": submission.domain,
                    "thumbnail": submission.thumbnail if hasattr(submission, 'thumbnail') else "",
                    "over_18": submission.over_18,
                    "spoiler": submission.spoiler,
                    "locked": submission.locked,
                    "stickied": submission.stickied,
                    "distinguished": submission.distinguished,
                    "link_flair_text": submission.link_flair_text or "",
                    "author_flair_text": submission.author_flair_text or "",
                    "query": query
                }
                
                # Scrape comments if requested
                if include_comments and submission.num_comments > 0:
                    try:
                        scraping_logger.info(f"💬 Scraping comments for post {i+1}: {submission.id}")
                        
                        # Expand all comments
                        submission.comments.replace_more(limit=None)
                        
                        comments = []
                        for comment in submission.comments.list():
                            try:
                                if hasattr(comment, 'body') and comment.body not in ['[deleted]', '[removed]']:
                                    comment_data = {
                                        'comment_id': comment.id,
                                        'author': str(comment.author) if comment.author else 'Unknown',
                                        'body': comment.body,
                                        'score': comment.score,
                                        'created_utc': comment.created_utc,
                                        'created_at': datetime.fromtimestamp(comment.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                                        'parent_id': comment.parent_id,
                                        'is_submitter': comment.is_submitter,
                                        'distinguished': comment.distinguished,
                                        'edited': bool(comment.edited),
                                        'gilded': getattr(comment, 'gilded', 0),
                                        'controversiality': getattr(comment, 'controversiality', 0)
                                    }
                                    comments.append(comment_data)
                            except Exception as comment_err:
                                scraping_logger.warning(f"⚠️ Error processing comment: {comment_err}")
                                continue
                        
                        post['comments'] = comments
                        post['total_comments_scraped'] = len(comments)
                        scraping_logger.info(f"✅ Scraped {len(comments)} comments for post {submission.id}")
                        
                    except Exception as comment_err:
                        scraping_logger.warning(f"⚠️ Failed to scrape comments for {submission.id}: {comment_err}")
                        post['comments'] = []
                        post['total_comments_scraped'] = 0
                else:
                    post['comments'] = []
                    post['total_comments_scraped'] = 0
                
                posts.append(post)
                
                if len(posts) >= max_posts:
                    break
                    
            except Exception as e:
                scraping_logger.warning(f"⚠️ Error processing submission {submission.id}: {e}")
                continue
        
        if posts:
            total_comments = sum(post.get('total_comments_scraped', 0) for post in posts)
            scraping_logger.info(f"✅ PRAW returned {len(posts)} posts with {total_comments} total comments")
            return posts
        
        scraping_logger.warning("⚠️ PRAW returned no posts")
        return None
        
    except Exception as e:
        scraping_logger.warning(f"❌ PRAW failed: {e}")
        return None


def try_advanced_reddit_api(query, subreddit=None, sort="relevance", time_filter="all", max_posts=DEFAULT_MAX_POSTS, include_comments=True):
    """
    Try Reddit JSON API with advanced techniques (rotating user agents, headers, etc.)
    Enhanced to handle large numbers of posts and scrape comments
    """
    try:
        scraping_logger.info("🔧 Attempting advanced Reddit JSON API...")
        
        import requests
        from fake_useragent import UserAgent
        from urllib.parse import urlencode
        import time
        import random
        
        # Ensure max_posts is an integer
        try:
            max_posts = int(max_posts)
        except (ValueError, TypeError):
            scraping_logger.warning(f"⚠️ Invalid max_posts value: {max_posts}, using default: {DEFAULT_MAX_POSTS}")
            max_posts = DEFAULT_MAX_POSTS
        
        ua = UserAgent()
        
        # Multiple user agents to rotate
        user_agents = [
            ua.random,
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        all_posts = []
        after_token = None
        batch_size = 100  # Reddit API limit per request
        
        # Calculate how many batches we need
        batches_needed = (max_posts + batch_size - 1) // batch_size
        scraping_logger.info(f"📊 Need {batches_needed} batches to fetch {max_posts} posts")
        
        print(f"\n🔄 Fetching {max_posts} Reddit posts in batches of {batch_size}...")
        
        for batch_num in range(batches_needed):
            try:
                scraping_logger.info(f"📡 Fetching batch {batch_num + 1}/{batches_needed}")
                
                # Try multiple endpoints for each batch
                endpoints = []
                
                if subreddit:
                    endpoints = [
                        f"https://www.reddit.com/r/{subreddit}/search.json",
                        f"https://old.reddit.com/r/{subreddit}/search.json"
                    ]
                else:
                    endpoints = [
                        "https://www.reddit.com/search.json",
                        "https://old.reddit.com/search.json"
                    ]
                
                batch_posts = []
                
                for endpoint in endpoints:
                    try:
                        # Build parameters
                        params = {
                            'q': query,
                            'sort': sort,
                            't': time_filter,
                            'limit': min(batch_size, max_posts - len(all_posts)),
                            'raw_json': 1
                        }
                        
                        if subreddit:
                            params['restrict_sr'] = 'on'
                        
                        if after_token:
                            params['after'] = after_token
                        
                        # Random headers
                        headers = {
                            "User-Agent": random.choice(user_agents),
                            "Accept": "application/json, text/plain, */*",
                            "Accept-Language": "en-US,en;q=0.9",
                            "Accept-Encoding": "gzip, deflate, br",
                            "DNT": "1",
                            "Connection": "keep-alive",
                            "Upgrade-Insecure-Requests": "1",
                            "Sec-Fetch-Dest": "document",
                            "Sec-Fetch-Mode": "navigate",
                            "Sec-Fetch-Site": "none",
                            "Cache-Control": "max-age=0"
                        }
                        
                        # Add random delay
                        time.sleep(random.uniform(1.0, 3.0))
                        
                        response = requests.get(
                            endpoint,
                            params=params,
                            headers=headers,
                            timeout=20,
                            allow_redirects=True
                        )
                        
                        scraping_logger.info(f"📊 Response status: {response.status_code}")
                        
                        if response.status_code == 200:
                            try:
                                data = response.json()
                                posts = parse_reddit_json_response(data, query)
                                
                                if posts:
                                    batch_posts = posts
                                    
                                    # Get after token for pagination
                                    if 'data' in data and 'after' in data['data']:
                                        after_token = data['data']['after']
                                    
                                    break  # Success, exit endpoint loop
                                    
                            except Exception as json_err:
                                scraping_logger.warning(f"❌ JSON parsing failed for {endpoint}: {json_err}")
                                continue
                    
                    except Exception as e:
                        scraping_logger.warning(f"⚠️ Endpoint {endpoint} failed: {e}")
                        continue
                
                if batch_posts:
                    # Scrape comments for each post if requested
                    if include_comments:
                        scraping_logger.info(f"💬 Scraping comments for {len(batch_posts)} posts...")
                        batch_posts = scrape_comments_for_posts(batch_posts, skip_on_403=True, max_consecutive_403=3)
                    
                    all_posts.extend(batch_posts)
                    scraping_logger.info(f"✅ Batch {batch_num + 1}: Added {len(batch_posts)} posts (Total: {len(all_posts)})")
                    
                    # Check if we have enough posts
                    if len(all_posts) >= max_posts:
                        break
                else:
                    scraping_logger.warning(f"⚠️ Batch {batch_num + 1} returned no posts")
                    
                    # If no posts and no after token, we've reached the end
                    if not after_token:
                        break
                
            except Exception as batch_err:
                scraping_logger.warning(f"❌ Batch {batch_num + 1} failed: {batch_err}")
                continue
        
        if all_posts:
            # Limit to requested number
            all_posts = all_posts[:max_posts]
            scraping_logger.info(f"✅ Advanced API returned {len(all_posts)} posts total")
            return all_posts
        
        scraping_logger.warning("⚠️ All advanced API endpoints failed")
        return None
        
    except Exception as e:
        scraping_logger.warning(f"❌ Advanced Reddit API failed: {e}")
        return None


def scrape_comments_for_posts(posts, max_retries=3, skip_on_403=True, max_consecutive_403=5):
    """
    Scrape comments for a list of Reddit posts
    
    Args:
        posts: List of Reddit posts
        max_retries: Maximum retries for failed requests
        skip_on_403: Skip comment scraping if getting 403 errors
        max_consecutive_403: Maximum consecutive 403 errors before skipping all comments
    """
    try:
        scraping_logger.info(f"💬 Starting comment scraping for {len(posts)} posts...")
        
        import requests
        from fake_useragent import UserAgent
        import time
        import random
        import signal
        
        # Add interrupt handler
        def signal_handler(signum, frame):
            scraping_logger.warning("🛑 Interrupt received, stopping comment scraping gracefully...")
            raise KeyboardInterrupt("Comment scraping interrupted by user")
        
        signal.signal(signal.SIGINT, signal_handler)
        
        ua = UserAgent()
        enhanced_posts = []
        consecutive_403_count = 0
        
        scraping_logger.info(f"🔧 Comment scraping settings: skip_on_403={skip_on_403}, max_consecutive_403={max_consecutive_403}")
        
        for i, post in enumerate(posts):
            try:
                post_id = post.get('post_id', '')
                subreddit = post.get('subreddit', '')
                
                if not post_id or not subreddit:
                    enhanced_posts.append(post)
                    continue
                
                # Skip comment scraping if too many 403 errors
                if skip_on_403 and consecutive_403_count >= max_consecutive_403:
                    scraping_logger.warning(f"⏭️ Skipping comment scraping due to consecutive 403 errors")
                    post['comments'] = []
                    post['total_comments_scraped'] = 0
                    enhanced_posts.append(post)
                    continue
                
                # Build comment URL
                comment_url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
                
                headers = {
                    "User-Agent": ua.random,
                    "Accept": "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                }
                
                # Add longer delay to avoid rate limiting (Reddit is very strict)
                delay_time = random.uniform(3.0, 6.0)  # Increased from 2-4 seconds
                time.sleep(delay_time)
                
                scraping_logger.info(f"💬 Fetching comments for post {i+1}/{len(posts)}: {post_id}")
                
                try:
                    response = requests.get(comment_url, headers=headers, timeout=30)
                except requests.exceptions.RequestException as e:
                    scraping_logger.warning(f"⚠️ Network error for {post_id}: {e}")
                    post['comments'] = []
                    post['total_comments_scraped'] = 0
                    enhanced_posts.append(post)
                    continue
                
                if response.status_code == 200:
                    consecutive_403_count = 0  # Reset counter on success
                    try:
                        comment_data = response.json()
                        comments = extract_comments_from_reddit_json(comment_data)
                        
                        # Add comments to post
                        post['comments'] = comments
                        post['total_comments_scraped'] = len(comments)
                        
                        scraping_logger.info(f"✅ Scraped {len(comments)} comments for post {post_id}")
                        
                    except Exception as comment_err:
                        scraping_logger.warning(f"⚠️ Failed to parse comments for {post_id}: {comment_err}")
                        post['comments'] = []
                        post['total_comments_scraped'] = 0
                elif response.status_code == 403:
                    consecutive_403_count += 1
                    scraping_logger.warning(f"🚫 Access denied for {post_id} (Status 403) - Reddit rate limiting ({consecutive_403_count}/{max_consecutive_403})")
                    post['comments'] = []
                    post['total_comments_scraped'] = 0
                    # Add much longer delay after 403 error
                    time.sleep(random.uniform(10.0, 15.0))
                elif response.status_code == 429:
                    scraping_logger.warning(f"⏳ Rate limited for {post_id} (Status 429) - waiting longer")
                    post['comments'] = []
                    post['total_comments_scraped'] = 0
                    # Add very long delay after rate limit
                    time.sleep(random.uniform(20.0, 30.0))
                else:
                    consecutive_403_count = 0  # Reset counter on successful response
                    scraping_logger.warning(f"⚠️ Failed to fetch comments for {post_id}: Status {response.status_code}")
                    post['comments'] = []
                    post['total_comments_scraped'] = 0
                
                enhanced_posts.append(post)
                
            except KeyboardInterrupt:
                scraping_logger.warning("🛑 Comment scraping interrupted by user")
                # Add remaining posts without comments
                for remaining_post in posts[i:]:
                    remaining_post['comments'] = []
                    remaining_post['total_comments_scraped'] = 0
                    enhanced_posts.append(remaining_post)
                break
                
            except Exception as e:
                scraping_logger.warning(f"❌ Error processing comments for post {i}: {e}")
                post['comments'] = []
                post['total_comments_scraped'] = 0
                enhanced_posts.append(post)
        
        total_comments = sum(post.get('total_comments_scraped', 0) for post in enhanced_posts)
        scraping_logger.info(f"✅ Comment scraping complete: {total_comments} total comments scraped")
        
        return enhanced_posts
        
    except KeyboardInterrupt:
        scraping_logger.warning("🛑 Comment scraping interrupted by user - returning posts without comments")
        # Return posts without comments if interrupted
        for post in posts:
            if 'comments' not in post:
                post['comments'] = []
                post['total_comments_scraped'] = 0
        return posts
    except Exception as e:
        scraping_logger.warning(f"❌ Comment scraping failed: {e}")
        return posts  # Return original posts without comments


def extract_comments_from_reddit_json(comment_data):
    """
    Extract comments from Reddit JSON response
    """
    comments = []
    
    try:
        if isinstance(comment_data, list) and len(comment_data) > 1:
            # Standard Reddit comment structure
            comment_listing = comment_data[1]
            
            if 'data' in comment_listing and 'children' in comment_listing['data']:
                for comment_item in comment_listing['data']['children']:
                    comment = extract_single_comment(comment_item)
                    if comment:
                        comments.append(comment)
                        
                        # Extract replies recursively
                        replies = extract_comment_replies(comment_item)
                        comments.extend(replies)
    
    except Exception as e:
        scraping_logger.warning(f"⚠️ Error extracting comments: {e}")
    
    return comments


def extract_single_comment(comment_item):
    """
    Extract a single comment from Reddit JSON
    """
    try:
        if comment_item.get('kind') != 't1':  # t1 is comment type
            return None
        
        comment_data = comment_item.get('data', {})
        
        # Skip deleted/removed comments
        if comment_data.get('body') in ['[deleted]', '[removed]', '']:
            return None
        
        from datetime import datetime
        
        comment = {
            'comment_id': comment_data.get('id', ''),
            'author': comment_data.get('author', 'Unknown'),
            'body': comment_data.get('body', ''),
            'score': comment_data.get('score', 0),
            'created_utc': comment_data.get('created_utc', 0),
            'created_at': '',
            'parent_id': comment_data.get('parent_id', ''),
            'is_submitter': comment_data.get('is_submitter', False),
            'distinguished': comment_data.get('distinguished'),
            'edited': comment_data.get('edited', False),
            'gilded': comment_data.get('gilded', 0),
            'controversiality': comment_data.get('controversiality', 0)
        }
        
        # Format timestamp
        if comment['created_utc']:
            dt = datetime.fromtimestamp(comment['created_utc'])
            comment['created_at'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        
        return comment
        
    except Exception as e:
        scraping_logger.warning(f"⚠️ Error extracting single comment: {e}")
        return None


def extract_comment_replies(comment_item):
    """
    Recursively extract replies from a comment
    """
    replies = []
    
    try:
        comment_data = comment_item.get('data', {})
        
        if 'replies' in comment_data and comment_data['replies']:
            replies_data = comment_data['replies']
            
            if isinstance(replies_data, dict) and 'data' in replies_data:
                if 'children' in replies_data['data']:
                    for reply_item in replies_data['data']['children']:
                        reply = extract_single_comment(reply_item)
                        if reply:
                            replies.append(reply)
                            
                            # Recursively get nested replies
                            nested_replies = extract_comment_replies(reply_item)
                            replies.extend(nested_replies)
    
    except Exception as e:
        scraping_logger.warning(f"⚠️ Error extracting replies: {e}")
    
    return replies


def try_web_scraping_reddit(query, subreddit=None, sort="relevance", time_filter="all", max_posts=DEFAULT_MAX_POSTS, delay=DEFAULT_DELAY):
    """
    Try web scraping Reddit using requests-html
    """
    try:
        scraping_logger.info("🌐 Attempting web scraping with requests-html...")
        
        from requests_html import HTMLSession
        from fake_useragent import UserAgent
        import time
        import random
        
        # Ensure max_posts is an integer
        try:
            max_posts = int(max_posts)
        except (ValueError, TypeError):
            scraping_logger.warning(f"⚠️ Invalid max_posts value: {max_posts}, using default: {DEFAULT_MAX_POSTS}")
            max_posts = DEFAULT_MAX_POSTS
        
        session = HTMLSession()
        ua = UserAgent()
        
        # Build Reddit search URL
        if subreddit:
            base_url = f"https://old.reddit.com/r/{subreddit}/search"
            params = {
                'q': query,
                'restrict_sr': 'on',
                'sort': sort,
                't': time_filter
            }
        else:
            base_url = "https://old.reddit.com/search"
            params = {
                'q': query,
                'sort': sort,
                't': time_filter
            }
        
        headers = {
            'User-Agent': ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        scraping_logger.info(f"📡 Fetching: {base_url}")
        
        response = session.get(base_url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            posts = []
            
            # Parse the HTML
            search_results = response.html.find('.search-result')
            
            for result in search_results[:max_posts]:
                try:
                    # Extract post information
                    title_elem = result.find('.search-title a', first=True)
                    title = title_elem.text if title_elem else ""
                    
                    link_elem = result.find('.search-title a', first=True)
                    permalink = link_elem.attrs.get('href', '') if link_elem else ""
                    
                    author_elem = result.find('.search-author', first=True)
                    author = author_elem.text.replace('by ', '') if author_elem else "Unknown"
                    
                    subreddit_elem = result.find('.search-subreddit-link', first=True)
                    post_subreddit = subreddit_elem.text.replace('r/', '') if subreddit_elem else ""
                    
                    score_elem = result.find('.search-score', first=True)
                    score = 0
                    if score_elem:
                        try:
                            score = int(score_elem.text.split()[0])
                        except:
                            score = 0
                    
                    comments_elem = result.find('.search-comments', first=True)
                    num_comments = 0
                    if comments_elem:
                        try:
                            num_comments = int(comments_elem.text.split()[0])
                        except:
                            num_comments = 0
                    
                    # Get post content if available
                    content_elem = result.find('.search-expando-text', first=True)
                    selftext = content_elem.text if content_elem else ""
                    
                    from datetime import datetime
                    
                    post = {
                        "post_id": f"web_{len(posts)+1}",
                        "title": title,
                        "author": author,
                        "subreddit": post_subreddit or subreddit or "unknown",
                        "created_utc": int(datetime.now().timestamp()),
                        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "score": score,
                        "upvote_ratio": 0.8,  # Default estimate
                        "num_comments": num_comments,
                        "selftext": selftext,
                        "url": f"https://reddit.com{permalink}" if permalink.startswith('/') else permalink,
                        "permalink": permalink,
                        "is_self": True,
                        "domain": "reddit.com",
                        "thumbnail": "",
                        "over_18": False,
                        "spoiler": False,
                        "locked": False,
                        "stickied": False,
                        "distinguished": None,
                        "link_flair_text": "",
                        "author_flair_text": "",
                        "query": query
                    }
                    
                    posts.append(post)
                    
                except Exception as e:
                    scraping_logger.warning(f"⚠️ Error parsing search result: {e}")
                    continue
            
            if posts:
                scraping_logger.info(f"✅ Web scraping returned {len(posts)} posts")
                return posts
        
        scraping_logger.warning(f"⚠️ Web scraping failed with status {response.status_code}")
        return None
        
    except Exception as e:
        scraping_logger.warning(f"❌ Web scraping failed: {e}")
        return None


def try_selenium_reddit_scraping(query, subreddit=None, sort="relevance", time_filter="all", max_posts=DEFAULT_MAX_POSTS):
    """
    Try scraping Reddit using Selenium (most powerful but slower)
    Gracefully skips if Selenium/ChromeDriver not available
    """
    try:
        scraping_logger.info("🤖 Attempting Selenium web scraping...")
        
        # Ensure max_posts is an integer
        try:
            max_posts = int(max_posts)
        except (ValueError, TypeError):
            scraping_logger.warning(f"⚠️ Invalid max_posts value: {max_posts}, using default: {DEFAULT_MAX_POSTS}")
            max_posts = DEFAULT_MAX_POSTS
        
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from fake_useragent import UserAgent
            import time
        except ImportError as e:
            scraping_logger.warning(f"⚠️ Selenium not available: {e}")
            return None
        
        driver = None
        try:
            # Setup Chrome options
            chrome_options = Options()
            chrome_options.add_argument("--headless")  # Run in background
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            try:
                ua = UserAgent()
                chrome_options.add_argument(f"--user-agent={ua.random}")
            except:
                chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            # Initialize driver with timeout
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(15)
            
            # Build Reddit URL
            if subreddit:
                url = f"https://old.reddit.com/r/{subreddit}/search?q={query}&restrict_sr=on&sort={sort}&t={time_filter}"
            else:
                url = f"https://old.reddit.com/search?q={query}&sort={sort}&t={time_filter}"
            
            scraping_logger.info(f"📡 Selenium fetching: {url}")
            
            driver.get(url)
            
            # Wait for content to load with shorter timeout
            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "search-result"))
                )
            except:
                scraping_logger.warning("⚠️ Selenium timeout waiting for content")
                return None
            
            posts = []
            search_results = driver.find_elements(By.CLASS_NAME, "search-result")
            
            for result in search_results[:max_posts]:
                try:
                    # Extract post data
                    title_elem = result.find_element(By.CSS_SELECTOR, ".search-title a")
                    title = title_elem.text
                    permalink = title_elem.get_attribute("href")
                    
                    try:
                        author_elem = result.find_element(By.CLASS_NAME, "search-author")
                        author = author_elem.text.replace("by ", "")
                    except:
                        author = "Unknown"
                    
                    try:
                        subreddit_elem = result.find_element(By.CLASS_NAME, "search-subreddit-link")
                        post_subreddit = subreddit_elem.text.replace("r/", "")
                    except:
                        post_subreddit = subreddit or "unknown"
                    
                    try:
                        score_elem = result.find_element(By.CLASS_NAME, "search-score")
                        score = int(score_elem.text.split()[0])
                    except:
                        score = 0
                    
                    try:
                        comments_elem = result.find_element(By.CLASS_NAME, "search-comments")
                        num_comments = int(comments_elem.text.split()[0])
                    except:
                        num_comments = 0
                    
                    try:
                        content_elem = result.find_element(By.CLASS_NAME, "search-expando-text")
                        selftext = content_elem.text
                    except:
                        selftext = ""
                    
                    from datetime import datetime
                    
                    post = {
                        "post_id": f"selenium_{len(posts)+1}",
                        "title": title,
                        "author": author,
                        "subreddit": post_subreddit,
                        "created_utc": int(datetime.now().timestamp()),
                        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "score": score,
                        "upvote_ratio": 0.8,
                        "num_comments": num_comments,
                        "selftext": selftext,
                        "url": permalink,
                        "permalink": permalink,
                        "is_self": True,
                        "domain": "reddit.com",
                        "thumbnail": "",
                        "over_18": False,
                        "spoiler": False,
                        "locked": False,
                        "stickied": False,
                        "distinguished": None,
                        "link_flair_text": "",
                        "author_flair_text": "",
                        "query": query
                    }
                    
                    posts.append(post)
                    
                except Exception as e:
                    scraping_logger.debug(f"⚠️ Error parsing Selenium result: {e}")
                    continue
            
            if posts:
                scraping_logger.info(f"✅ Selenium returned {len(posts)} posts")
                return posts
            
            scraping_logger.warning("⚠️ Selenium found no posts")
            return None
            
        except Exception as e:
            scraping_logger.warning(f"⚠️ Selenium initialization failed: {str(e)[:100]}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
        
    except Exception as e:
        scraping_logger.warning(f"⚠️ Selenium scraping error: {str(e)[:100]}")
        return None


def try_alternative_reddit_endpoints(query, subreddit=None, sort="relevance", time_filter="all", max_posts=DEFAULT_MAX_POSTS):
    """
    Try alternative Reddit endpoints and methods with improved timeout handling
    """
    try:
        scraping_logger.info("🔄 Trying alternative Reddit endpoints...")
        
        # Ensure max_posts is an integer
        try:
            max_posts = int(max_posts)
        except (ValueError, TypeError):
            scraping_logger.warning(f"⚠️ Invalid max_posts value: {max_posts}, using default: {DEFAULT_MAX_POSTS}")
            max_posts = DEFAULT_MAX_POSTS
        
        import requests
        from fake_useragent import UserAgent
        import time
        import random
        
        try:
            ua = UserAgent()
        except:
            ua = None
        
        # Alternative endpoints to try (prioritized by reliability)
        endpoints = [
            f"https://www.reddit.com/r/{subreddit}/hot.json" if subreddit else "https://www.reddit.com/r/all/hot.json",
            f"https://www.reddit.com/r/{subreddit}/new.json" if subreddit else "https://www.reddit.com/r/all/new.json",
            f"https://www.reddit.com/r/{subreddit}/.json" if subreddit else "https://www.reddit.com/.json",
            "https://old.reddit.com/.json",
        ]
        
        for endpoint in endpoints:
            try:
                scraping_logger.info(f"📡 Trying endpoint: {endpoint}")
                
                headers = {
                    'User-Agent': ua.random if ua else 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.9'
                }
                
                time.sleep(random.uniform(0.5, 1.5))
                
                # Use shorter timeout for faster failure
                response = requests.get(endpoint, headers=headers, timeout=8)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        posts = parse_reddit_json_response(data, query)
                        
                        if posts:
                            # Filter posts by query if needed
                            filtered_posts = []
                            for post in posts:
                                if query.lower() in post.get('title', '').lower() or query.lower() in post.get('selftext', '').lower():
                                    filtered_posts.append(post)
                            
                            if filtered_posts:
                                scraping_logger.info(f"✅ Alternative endpoint returned {len(filtered_posts)} relevant posts")
                                return filtered_posts[:max_posts]
                    
                    except Exception as json_err:
                        scraping_logger.debug(f"⚠️ JSON parsing failed for {endpoint}: {str(json_err)[:50]}")
                        continue
                
            except requests.Timeout:
                scraping_logger.debug(f"⏱️ Timeout on {endpoint}, skipping...")
                continue
            except requests.ConnectionError:
                scraping_logger.debug(f"🔌 Connection error on {endpoint}, skipping...")
                continue
            except Exception as e:
                scraping_logger.debug(f"⚠️ Endpoint {endpoint} failed: {str(e)[:50]}")
                continue
        
        scraping_logger.warning("⚠️ All alternative endpoints failed or returned no results")
        return None
        
    except Exception as e:
        scraping_logger.warning(f"⚠️ Alternative endpoints error: {str(e)[:100]}")
        return None


def parse_reddit_json_response(data, query):
    """
    Parse Reddit JSON response and extract posts
    """
    posts = []
    
    try:
        # Handle different JSON structures
        if isinstance(data, dict):
            if 'data' in data and 'children' in data['data']:
                # Standard Reddit API response
                for item in data['data']['children']:
                    post_data = item.get('data', {})
                    post = extract_post_from_reddit_data(post_data, query)
                    if post:
                        posts.append(post)
            
            elif 'data' in data and isinstance(data['data'], list):
                # Alternative format
                for item in data['data']:
                    post = extract_post_from_reddit_data(item, query)
                    if post:
                        posts.append(post)
        
        elif isinstance(data, list):
            # Direct list of posts
            for item in data:
                if isinstance(item, dict):
                    post = extract_post_from_reddit_data(item, query)
                    if post:
                        posts.append(post)
    
    except Exception as e:
        scraping_logger.warning(f"⚠️ Error parsing Reddit JSON: {e}")
    
    return posts


def extract_post_from_reddit_data(post_data, query):
    """
    Extract post information from Reddit data
    """
    try:
        from datetime import datetime
        
        post = {
            "post_id": post_data.get('id', f"api_{len(str(post_data))}"),
            "title": post_data.get('title', ''),
            "author": post_data.get('author', 'Unknown'),
            "subreddit": post_data.get('subreddit', ''),
            "created_utc": post_data.get('created_utc', int(datetime.now().timestamp())),
            "created_at": "",
            "score": post_data.get('score', 0),
            "upvote_ratio": post_data.get('upvote_ratio', 0.0),
            "num_comments": post_data.get('num_comments', 0),
            "selftext": post_data.get('selftext', ''),
            "url": post_data.get('url', ''),
            "permalink": post_data.get('permalink', ''),
            "is_self": post_data.get('is_self', False),
            "domain": post_data.get('domain', ''),
            "thumbnail": post_data.get('thumbnail', ''),
            "over_18": post_data.get('over_18', False),
            "spoiler": post_data.get('spoiler', False),
            "locked": post_data.get('locked', False),
            "stickied": post_data.get('stickied', False),
            "distinguished": post_data.get('distinguished'),
            "link_flair_text": post_data.get('link_flair_text', ''),
            "author_flair_text": post_data.get('author_flair_text', ''),
            "query": query
        }
        
        # Format created_at from UTC timestamp
        if post['created_utc']:
            dt = datetime.fromtimestamp(post['created_utc'])
            post['created_at'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            post['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return post
        
    except Exception as e:
        scraping_logger.warning(f"⚠️ Error extracting post data: {e}")
        return None


# Sample data creation function removed - we now use real Reddit data!


    return saved_posts + saved_comments, skipped_posts + skipped_comments


def export_reddit_posts_to_files(query, posts, company_id=None):
    """Save Reddit posts to JSON and CSV files with company-specific naming"""
    safe_query = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in query)[:50]
    
    # Add company-specific naming
    if company_id and company_id != 'haval':
        base = os.path.join(DATA_DIR, f"reddit_search_{safe_query}_{company_id}")
    else:
        base = os.path.join(DATA_DIR, f"reddit_search_{safe_query}")
    
    json_path = base + ".json"
    csv_path = base + ".csv"

    # JSON with company information
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "query": query, 
            "search_type": "reddit_search",
            "company_id": company_id or "haval",
            "total_posts": len(posts),
            "posts": posts
        }, f, ensure_ascii=False, indent=2)

    # CSV (flatten)
    rows = []
    for p in posts:
        content_parts = []
        if p.get("title"):
            content_parts.append(p.get("title"))
        if p.get("selftext"):
            content_parts.append(p.get("selftext"))
        
        content = " | ".join(content_parts) if content_parts else ""
        
        rows.append({
            "post_id": p.get("post_id"),
            "title": p.get("title"),
            "author": p.get("author"),
            "subreddit": p.get("subreddit"),
            "created_at": p.get("created_at"),
            "score": p.get("score"),
            "num_comments": p.get("num_comments"),
            "content": content,
            "url": p.get("url"),
            "permalink": p.get("permalink"),
            "company_id": company_id or "haval"
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False, encoding="utf-8")

    return json_path, csv_path


# ============================================================================
# LUCID FORUM SCRAPING FUNCTIONS
# ============================================================================

def fetch_lucid_url(url, timeout=15, max_retries=3):
    """Fetch Lucid forum URL with retry logic"""
    headers = {"User-Agent": "Mozilla/5.0 (Controlled Forum Crawler)"}
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout, headers=headers)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return None
    return None


def extract_lucid_forum_sections(html):
    """Extract forum sections from Lucid forum"""
    soup = BeautifulSoup(html, "lxml")
    return list(set(a["href"] for a in soup.select("a[href^='/forums/']")))


def extract_lucid_threads(html):
    """Extract thread links from Lucid forum"""
    soup = BeautifulSoup(html, "lxml")
    return list(set(a["href"] for a in soup.select("a[href^='/threads/']")))


def extract_lucid_posts(html, base_url="https://lucidowners.com"):
    """Extract posts from Lucid forum thread"""
    soup = BeautifulSoup(html, "lxml")
    posts = []

    for art in soup.select("article.message"):
        post_id = art.get("id", "").strip()
        author = art.select_one(".username")
        time_tag = art.select_one("time")
        body = art.select_one(".message-body")

        # Extract permalink
        permalink_tag = art.select_one("a[href*='/post-']")
        if permalink_tag:
            post_link = base_url + permalink_tag["href"]
        else:
            post_link = base_url + "#" + post_id if post_id else ""

        posts.append({
            "post_id": post_id,
            "post_link": post_link,
            "author": author.text.strip() if author else "",
            "timestamp": time_tag.text.strip() if time_tag else "",
            "text": body.get_text("\n").strip() if body else ""
        })

    return posts


def scrape_lucid_forum(base_url="https://lucidowners.com", max_threads=None, max_posts=None, delay=DEFAULT_DELAY, min_year=None):
    """
    Scrape Lucid forum threads and posts
    
    Args:
        base_url: Base URL of Lucid forum
        max_threads: Maximum threads to scrape
        max_posts: Maximum posts per thread
        delay: Delay between requests
        min_year: Minimum year for posts (not implemented for Lucid yet)
    
    Returns:
        List of posts from Lucid forum
    """
    all_posts = []
    visited_threads = set()
    thread_count = 0
    
    try:
        # Fetch forum root
        print(f"[Lucid] Connecting to {base_url}/forums/")
        html = fetch_lucid_url(base_url + "/forums/")
        if not html:
            print("[Lucid] Failed to connect to forum root - returning empty list")
            return all_posts
        
        sections = extract_lucid_forum_sections(html)
        print(f"[Lucid] Found {len(sections)} sections")
        
        if not sections:
            print("[Lucid] No sections found - returning empty list")
            return all_posts
        
        # Scrape threads from each section
        for section in sections:
            if max_threads and thread_count >= max_threads:
                print(f"[Lucid] Reached max threads limit ({max_threads})")
                break
            
            page = 1
            max_pages = 10  # Limit pages to prevent infinite loops
            
            while page <= max_pages:
                if max_threads and thread_count >= max_threads:
                    break
                
                # Build section URL with pagination (matching lucid.py format)
                section_url = base_url + section + f"page-{page}"
                print(f"[Lucid] Fetching section page {page}: {section_url}")
                
                html = fetch_lucid_url(section_url)
                if not html:
                    print(f"[Lucid] Failed to fetch section page {page}, moving to next section")
                    break
                
                threads = extract_lucid_threads(html)
                print(f"[Lucid] Found {len(threads)} threads on page {page}")
                
                if not threads:
                    print(f"[Lucid] No threads found on page {page}, moving to next section")
                    break
                
                # Scrape each thread
                for thread_path in threads:
                    if max_threads and thread_count >= max_threads:
                        break
                    
                    if thread_path in visited_threads:
                        continue
                    
                    visited_threads.add(thread_path)
                    thread_count += 1
                    
                    print(f"[Lucid] Scraping thread {thread_count}/{max_threads or '∞'}: {thread_path}")
                    
                    # Scrape thread posts with pagination (matching lucid.py crawl_thread logic)
                    thread_posts = []
                    thread_page = 1
                    max_thread_pages = 10
                    
                    while thread_page <= max_thread_pages:
                        if max_posts and len(thread_posts) >= max_posts:
                            break
                        
                        # Build thread URL with pagination
                        if thread_page == 1:
                            thread_url = base_url + thread_path
                        else:
                            thread_url = base_url + thread_path + f"page-{thread_page}"
                        
                        print(f"[Lucid]   Fetching thread page {thread_page}: {thread_url}")
                        thread_html = fetch_lucid_url(thread_url)
                        
                        if not thread_html:
                            print(f"[Lucid]   Failed to fetch thread page {thread_page}")
                            break
                        
                        posts = extract_lucid_posts(thread_html, base_url)
                        print(f"[Lucid]   Found {len(posts)} posts on thread page {thread_page}")
                        
                        if not posts:
                            print(f"[Lucid]   No posts found on thread page {thread_page}")
                            break
                        
                        # Add posts up to max_posts limit
                        for post in posts:
                            if max_posts and len(thread_posts) >= max_posts:
                                break
                            thread_posts.append(post)
                        
                        thread_page += 1
                        time.sleep(delay)
                    
                    # Add thread info to posts
                    for post in thread_posts:
                        post["thread_url"] = base_url + thread_path
                        post["thread_title"] = thread_path.split('/')[-1].replace('-', ' ').title()
                    
                    all_posts.extend(thread_posts)
                    print(f"[Lucid] Collected {len(thread_posts)} posts from thread")
                    
                    time.sleep(delay)
                
                page += 1
        
        print(f"[Lucid] Total posts scraped: {len(all_posts)}")
        return all_posts
    
    except Exception as e:
        print(f"[Lucid] Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        return all_posts


def export_lucid_posts_to_files(base_url, posts, company_id=None):
    """
    Export Lucid posts to JSON and CSV files
    
    Args:
        base_url: Base URL of Lucid forum
        posts: List of posts
        company_id: Company identifier for file naming
    
    Returns:
        Tuple of (json_path, csv_path)
    """
    import csv
    from datetime import datetime
    
    # Create filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    company_suffix = f"_{company_id}" if company_id else ""
    base_filename = f"lucid_forum{company_suffix}_{timestamp}"
    
    json_path = f"data/{base_filename}.json"
    csv_path = f"data/{base_filename}.csv"
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Export to JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "source": "lucid_forum",
            "base_url": base_url,
            "posts": posts,
            "total_posts": len(posts),
            "scraped_at": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)
    
    print(f"[Lucid] Exported {len(posts)} posts to {json_path}")
    
    # Export to CSV
    if posts:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'post_id', 'author', 'timestamp', 'text', 'thread_title', 'thread_url'
            ])
            writer.writeheader()
            for post in posts:
                writer.writerow({
                    'post_id': post.get('post_id', ''),
                    'author': post.get('author', ''),
                    'timestamp': post.get('timestamp', ''),
                    'text': post.get('text', '')[:500],  # Truncate for CSV
                    'thread_title': post.get('thread_title', ''),
                    'thread_url': post.get('thread_url', '')
                })
    
    return json_path, csv_path
