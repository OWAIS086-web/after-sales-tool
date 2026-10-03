"""
Scraped URLs Tracker

Tracks which PakWheels URLs have already been scraped for each company
to avoid duplicate scraping.
"""

import json
import os
from typing import List, Set
from utils.logger import server_logger


def get_scraped_urls_file(company_id: str) -> str:
    """Get the path to the scraped URLs tracking file for a company"""
    return f"data/scraped_urls_{company_id}.json"


def load_scraped_urls(company_id: str) -> Set[str]:
    """Load the list of already-scraped URLs for a company"""
    file_path = get_scraped_urls_file(company_id)

    if not os.path.exists(file_path):
        return set()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data.get('scraped_urls', []))
    except Exception as e:
        server_logger.warning(f"Failed to load scraped URLs for {company_id}: {e}")
        return set()


def save_scraped_urls(company_id: str, urls: Set[str]) -> None:
    """Save the list of scraped URLs for a company"""
    file_path = get_scraped_urls_file(company_id)

    try:
        # Ensure data directory exists
        os.makedirs('data', exist_ok=True)

        data = {
            'company_id': company_id,
            'scraped_urls': sorted(list(urls))
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        server_logger.info(f"Saved {len(urls)} scraped URLs for {company_id}")
    except Exception as e:
        server_logger.error(f"Failed to save scraped URLs for {company_id}: {e}")


def mark_url_as_scraped(company_id: str, url: str) -> None:
    """Mark a URL as scraped for a company"""
    scraped_urls = load_scraped_urls(company_id)
    scraped_urls.add(url)
    save_scraped_urls(company_id, scraped_urls)
    server_logger.info(f"Marked URL as scraped for {company_id}: {url}")


def is_url_scraped(company_id: str, url: str) -> bool:
    """Check if a URL has already been scraped for a company"""
    scraped_urls = load_scraped_urls(company_id)
    return url in scraped_urls


def get_unscraped_urls(company_id: str, all_urls: List[str]) -> List[str]:
    """Filter a list of URLs to only include those not yet scraped"""
    scraped_urls = load_scraped_urls(company_id)
    return [url for url in all_urls if url not in scraped_urls]


# ============== Reddit URL Tracking ==============

def get_scraped_reddit_urls_file(company_id: str) -> str:
    """Get the path to the scraped Reddit URLs tracking file for a company"""
    return f"data/scraped_reddit_urls_{company_id}.json"


def load_scraped_reddit_urls(company_id: str) -> Set[str]:
    """Load the list of already-scraped Reddit URLs for a company"""
    file_path = get_scraped_reddit_urls_file(company_id)

    if not os.path.exists(file_path):
        return set()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data.get('scraped_reddit_urls', []))
    except Exception as e:
        server_logger.warning(f"Failed to load scraped Reddit URLs for {company_id}: {e}")
        return set()


def save_scraped_reddit_urls(company_id: str, urls: Set[str]) -> None:
    """Save the list of scraped Reddit URLs for a company"""
    file_path = get_scraped_reddit_urls_file(company_id)

    try:
        os.makedirs('data', exist_ok=True)

        data = {
            'company_id': company_id,
            'scraped_reddit_urls': sorted(list(urls))
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        server_logger.info(f"Saved {len(urls)} scraped Reddit URLs for {company_id}")
    except Exception as e:
        server_logger.error(f"Failed to save scraped Reddit URLs for {company_id}: {e}")


def mark_reddit_url_as_scraped(company_id: str, url: str) -> None:
    """Mark a Reddit URL as scraped for a company"""
    scraped_urls = load_scraped_reddit_urls(company_id)
    scraped_urls.add(url)
    save_scraped_reddit_urls(company_id, scraped_urls)
    server_logger.info(f"Marked Reddit URL as scraped for {company_id}: {url}")
