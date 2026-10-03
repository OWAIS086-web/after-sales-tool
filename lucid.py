import requests
import time
import json
from bs4 import BeautifulSoup
import os
from pathlib import Path
from typing import Dict, Any, Optional

BASE = "https://lucidowners.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Controlled Forum Crawler)"
}

session = requests.Session()
session.headers.update(HEADERS)

visited_threads = set()


def fetch(url):
    for _ in range(3):
        try:
            r = session.get(url, timeout=15)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print("Retrying:", e)
            time.sleep(2)
    return None


def extract_forum_sections(html):
    soup = BeautifulSoup(html, "lxml")
    return list(set(a["href"] for a in soup.select("a[href^='/forums/']")))


def extract_threads(html):
    soup = BeautifulSoup(html, "lxml")
    return list(set(a["href"] for a in soup.select("a[href^='/threads/']")))


def extract_posts(html, thread_url):
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
            post_link = BASE + permalink_tag["href"]
        else:
            post_link = BASE + thread_url + "#" + post_id if post_id else ""

        posts.append({
            "post_id": post_id,
            "post_link": post_link,
            "author": author.text.strip() if author else "",
            "timestamp": time_tag.text.strip() if time_tag else "",
            "text": body.get_text("\n").strip() if body else ""
        })

    return posts


def save_data(thread_data, filename="SCRAPED_DATA.json"):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []

    data.append(thread_data)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def crawl_thread(thread_url, max_posts, base_url=BASE):
    page = 1
    collected_posts = []

    while True:
        if max_posts and len(collected_posts) >= max_posts:
            break

        if page == 1:
            url = base_url + thread_url
        else:
            url = base_url + thread_url + f"page-{page}"

        print("   Scraping:", url)

        html = fetch(url)
        if not html:
            break

        posts = extract_posts(html, thread_url)
        if not posts:
            break

        for p in posts:
            if max_posts and len(collected_posts) >= max_posts:
                break
            collected_posts.append(p)

        page += 1
        time.sleep(1)

    return collected_posts


def crawl(max_threads, max_posts_per_thread):
    html = fetch(BASE + "/forums/")
    if not html:
        print("Failed to load forum root.")
        return

    sections = extract_forum_sections(html)
    thread_count = 0

    for section in sections:
        page = 1
        while True:
            if max_threads and thread_count >= max_threads:
                print("Reached thread limit.")
                return

            section_url = BASE + section + f"page-{page}"
            print("Section:", section_url)

            html = fetch(section_url)
            if not html:
                break

            threads = extract_threads(html)
            if not threads:
                break

            for t in threads:
                if max_threads and thread_count >= max_threads:
                    return

                if t in visited_threads:
                    continue

                visited_threads.add(t)
                thread_count += 1

                print(f"\nCrawling thread {thread_count}: {t}")

                posts = crawl_thread(t, max_posts_per_thread)

                thread_data = {
                    "thread_link": BASE + t,
                    "posts": posts
                }

                save_data(thread_data)

                print("Saved thread:", t)
                time.sleep(1)

            page += 1


def run_with_pipeline(base_url: str = BASE,
                     chroma_path: str = "data/chroma_lucid",
                     blocks_file: str = "data/lucid_blocks.pkl",
                     max_threads: Optional[int] = None,
                     max_posts: Optional[int] = None,
                     enable_enrichment: bool = True):
    """
    Run Lucid scraper and process through pipeline.
    
    Args:
        base_url: Base URL for Lucid forum
        chroma_path: Path to Chroma persistent database
        blocks_file: Path to pickle file for conversation blocks
        max_threads: Maximum threads to scrape (None = unlimited)
        max_posts: Maximum posts per thread (None = unlimited)
        enable_enrichment: Whether to enrich with embeddings and index to Chroma
    """
    from ai.lucid_pipeline import LucidPipeline
    
    print("\n" + "="*60)
    print("LUCID SCRAPER: Starting scrape with pipeline")
    print(f"Base URL: {base_url}")
    print(f"Chroma DB: {chroma_path}")
    print(f"Blocks file: {blocks_file}")
    print("="*60)
    
    # Collect all thread data
    all_threads = []
    
    html = fetch(base_url + "/forums/")
    if not html:
        print("Failed to load forum root.")
        return
    
    sections = extract_forum_sections(html)
    thread_count = 0
    
    for section in sections:
        page = 1
        while True:
            if max_threads and thread_count >= max_threads:
                print("Reached thread limit.")
                break
            
            section_url = base_url + section + f"page-{page}"
            print("Section:", section_url)
            
            html = fetch(section_url)
            if not html:
                break
            
            threads = extract_threads(html)
            if not threads:
                break
            
            for t in threads:
                if max_threads and thread_count >= max_threads:
                    break
                
                if t in visited_threads:
                    continue
                
                visited_threads.add(t)
                thread_count += 1
                
                print(f"\nCrawling thread {thread_count}: {t}")
                
                posts = crawl_thread(t, max_posts, base_url)
                
                thread_data = {
                    "thread_link": base_url + t,
                    "posts": posts
                }
                
                all_threads.append(thread_data)
                
                print("Collected thread:", t)
                time.sleep(1)
            
            page += 1
    
    print(f"\n[Scraper] Collected {len(all_threads)} threads")
    
    # Process through pipeline
    if all_threads and enable_enrichment:
        pipeline = LucidPipeline(chroma_path=chroma_path, blocks_file=blocks_file)
        
        for thread_data in all_threads:
            try:
                print(f"\n[Pipeline] Processing thread: {thread_data['thread_link']}")
                results = pipeline.full_pipeline(thread_data)
                print(f"[Pipeline] Results: {results['blocks_count']} blocks, {results['duration_seconds']:.2f}s")
            except Exception as e:
                print(f"[Pipeline] Error processing thread: {e}")
                # Still save raw data even if enrichment fails
                pipeline.save_raw_data(thread_data)
    else:
        # Just save raw data without enrichment
        for thread_data in all_threads:
            save_data(thread_data)
    
    print("\n" + "="*60)
    print("LUCID SCRAPER: Complete")
    print("="*60 + "\n")


if __name__ == "__main__":
    from config import get_company_config
    
    print("\n" + "="*60)
    print("LUCID FORUM SCRAPER")
    print("="*60)
    
    # Get company selection
    company_id = input("Enter company ID (haval/kia/toyota) [haval]: ").strip().lower() or "haval"
    
    try:
        config = get_company_config(company_id)
    except ValueError as e:
        print(f"Error: {e}")
        exit(1)
    
    if not config.has_lucid:
        print(f"Warning: Lucid forum not configured for {config.name}")
        enable_lucid = input("Enable Lucid forum for this company? (y/n): ").lower() == 'y'
        if not enable_lucid:
            exit(0)
    
    # Get scraping parameters
    try:
        base_url = input(f"Enter Lucid forum URL [{config.lucid_url or BASE}]: ").strip() or (config.lucid_url or BASE)
        max_threads = int(input("Enter max number of threads (0 = unlimited): "))
        max_posts = int(input("Enter max posts per thread (0 = unlimited): "))
        enable_pipeline = input("Enable pipeline enrichment? (y/n) [y]: ").lower() != 'n'
    except ValueError:
        print("Invalid input.")
        exit(1)

    if max_threads == 0:
        max_threads = None
    if max_posts == 0:
        max_posts = None

    # Get Chroma and blocks file paths from config
    chroma_path = config.chroma_lucid_path or "data/chroma_lucid"
    blocks_file = config.lucid_blocks_file or "data/lucid_blocks.pkl"

    if enable_pipeline:
        run_with_pipeline(
            base_url=base_url,
            chroma_path=chroma_path,
            blocks_file=blocks_file,
            max_threads=max_threads,
            max_posts=max_posts,
            enable_enrichment=True
        )
    else:
        crawl(max_threads, max_posts)
        print("\nScraping finished.")
