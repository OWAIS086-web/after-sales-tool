"""
URL Validator for PakWheels URLs

Validates PakWheels discussion thread URLs to ensure they follow the correct format.
"""

import re
from typing import Tuple


def validate_pakwheels_url(url: str) -> Tuple[bool, str]:
    """
    Validate a PakWheels discussion thread URL.

    Args:
        url: URL to validate

    Returns:
        Tuple of (is_valid, error_message)
        - If valid: (True, "")
        - If invalid: (False, "Error message explaining why")
    """
    if not url or not url.strip():
        return False, "URL cannot be empty"

    url = url.strip()

    # Check if URL starts with correct domain
    if not url.startswith("https://www.pakwheels.com/forums/t/"):
        return False, "URL must start with https://www.pakwheels.com/forums/t/"

    # Expected format: https://www.pakwheels.com/forums/t/{topic-slug}/{topic-id}
    # Optional: May have query params or hash, but should NOT have /post_number at end
    pattern = r'^https://www\.pakwheels\.com/forums/t/[a-z0-9\-]+/(\d+)(?:\?.*)?(?:#.*)?$'

    # Check for invalid post number suffix (e.g., /972, /22)
    if re.search(r'/\d+/\d+$', url):
        return False, "URL should not include specific post numbers (e.g., /972). Use the base thread URL only."

    match = re.match(pattern, url)

    if not match:
        return False, "Invalid PakWheels URL format. Expected: https://www.pakwheels.com/forums/t/topic-name/123456"

    topic_id = match.group(1)

    if not topic_id.isdigit():
        return False, "Topic ID must be numeric"

    return True, ""


def normalize_pakwheels_url(url: str) -> str:
    """
    Normalize a PakWheels URL by removing query params and hash fragments.

    Args:
        url: URL to normalize

    Returns:
        Normalized URL (base thread URL only)
    """
    if not url:
        return url

    url = url.strip()

    # Remove query params
    if '?' in url:
        url = url.split('?')[0]

    # Remove hash fragments
    if '#' in url:
        url = url.split('#')[0]

    # Remove trailing slash
    url = url.rstrip('/')

    return url
