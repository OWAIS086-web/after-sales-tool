# haval_insights/text_cleaning.py
import re
from html import unescape
from typing import List
from bs4 import BeautifulSoup 
from typing import List
from ai.models import RawPost, CleanPost


QUOTE_PREFIX = "> "


def html_to_text(cooked_html: str) -> str:
    """
    Convert PakWheels 'cooked' HTML to readable plain text.

    Key points:
    - Convert <aside class="quote"> blocks into '> quoted text' style to keep context.
    - Strip images, emojis etc. (we can improve later if needed).
    - Normalize whitespace.
    """
    soup = BeautifulSoup(cooked_html, "html.parser")

    # Handle quote blocks explicitly
    texts: List[str] = []

    for elem in soup.contents:
        if getattr(elem, "name", None) == "aside" and "quote" in elem.get("class", []):
            # Extract quoted text
            quoted_text = elem.get_text(separator=" ", strip=True)
            # Prefix each line with '> '
            quoted_lines = [
                QUOTE_PREFIX + line.strip()
                for line in re.split(r"\r?\n", quoted_text)
                if line.strip()
            ]
            if quoted_lines:
                texts.append("\n".join(quoted_lines))
        else:
            # For everything else, just take text
            plain = (
                elem.get_text(separator=" ", strip=True)
                if hasattr(elem, "get_text")
                else str(elem).strip()
            )
            if plain:
                texts.append(plain)

    full_text = "\n\n".join(texts)
    full_text = unescape(full_text)

    # Normalize whitespace (no crazy multiple spaces)
    full_text = re.sub(r"[ \t]+", " ", full_text)
    # And trim excessive blank lines
    full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()

    return full_text



def raw_to_clean_posts(
    raw_posts: List[RawPost],
    thread_id: str,
) -> List[CleanPost]:
    """
    Apply html_to_text and enrich with time features.

    Assumptions:
    - All posts belong to the same thread_id and source_url.
    """
    clean_posts: List[CleanPost] = []
    for rp in raw_posts:
        text = html_to_text(rp.cooked_html)
        d = rp.created_at.date()
        iso = rp.created_at.isocalendar()  # (year, week, weekday)

        clean_posts.append(
            CleanPost(
                thread_id=thread_id,
                source_url=rp.url,
                post_id=rp.post_id,
                post_number=rp.post_number,
                username=rp.username,
                created_at=rp.created_at,
                updated_at=rp.updated_at,
                text=text,
                reply_to_post_number=rp.reply_to_post_number,
                topic_title=rp.topic_title,
                date=d,
                week_year=iso[0],
                week_number=iso[1],
            )
        )

    return clean_posts
