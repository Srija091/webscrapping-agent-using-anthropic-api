"""
CogniScan Web Scraper
Fetches and parses article content from government health websites.
"""

from __future__ import annotations

import re
import logging
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; CogniScan/1.0; "
        "Government Mental Health News Aggregator; "
        "+https://github.com/your-org/cogniscan)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Tag/class selectors to try for main article content (in priority order)
CONTENT_SELECTORS = [
    ("article", {}),
    ("main", {}),
    ("div", {"class": re.compile(r"article|content|body|post|entry", re.I)}),
    ("div", {"id": re.compile(r"article|content|main|body", re.I)}),
    ("section", {"class": re.compile(r"content|article|body", re.I)}),
]

# Tags to strip from parsed content
STRIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "form", "iframe"}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.TransportError),
    reraise=True,
)
async def fetch_page(url: str, timeout: int = 20) -> Optional[str]:
    """Async fetch of a URL, returns raw HTML or None on failure."""
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=timeout) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP %s for %s", e.response.status_code, url)
            return None
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", url, e)
            return None


def extract_article_text(html: str, url: str = "") -> dict:
    """
    Parse raw HTML and extract:
      - title
      - main body text (cleaned)
      - meta description
      - publication date (best-effort)
    """
    soup = BeautifulSoup(html, "lxml")

    # --- Title ---
    title = ""
    if soup.title:
        title = soup.title.string or ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"]
    h1 = soup.find("h1")
    if h1 and not title:
        title = h1.get_text(strip=True)
    title = title.strip()

    # --- Meta description ---
    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"].strip()
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        description = og_desc["content"].strip()

    # --- Publication date ---
    pub_date = _extract_date(soup)

    # --- Main content ---
    # Remove noise tags first
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()

    body_text = ""
    for tag, attrs in CONTENT_SELECTORS:
        element = soup.find(tag, attrs)
        if element:
            body_text = element.get_text(separator="\n", strip=True)
            if len(body_text) > 300:
                break

    if not body_text:
        body_text = soup.get_text(separator="\n", strip=True)

    body_text = _clean_text(body_text)

    return {
        "title": title,
        "description": description,
        "body": body_text[:8000],   # cap to avoid huge context windows
        "date": pub_date,
        "url": url,
        "domain": urlparse(url).netloc,
    }


def _extract_date(soup: BeautifulSoup) -> Optional[str]:
    """Best-effort extraction of a publication date from common meta patterns."""
    candidates = [
        soup.find("meta", attrs={"name": "date"}),
        soup.find("meta", property="article:published_time"),
        soup.find("meta", attrs={"name": "DC.date"}),
        soup.find("time"),
    ]
    for c in candidates:
        if c is None:
            continue
        val = c.get("content") or c.get("datetime") or c.get_text(strip=True)
        if val:
            # Trim to YYYY-MM-DD if long ISO string
            return val[:10] if len(val) >= 10 else val
    return None


def _clean_text(text: str) -> str:
    """Collapse excessive whitespace/newlines."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Remove duplicate adjacent lines
    deduped = []
    prev = None
    for ln in lines:
        if ln != prev:
            deduped.append(ln)
        prev = ln
    return "\n".join(deduped)
