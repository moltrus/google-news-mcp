"""
Google News MCP Server

Exposes Google News RSS feeds as MCP tools with support for:
  - Top headlines (by country/language)
  - Category feeds (Technology, Business, Science, etc.)
  - Search-based feeds (keyword search)
  - Geo-location feeds (city/region specific)

Required environment variables:
  GOOGLE_NEWS_LANGUAGE - Language code (e.g., 'en', 'fr') [default: 'en']
  GOOGLE_NEWS_COUNTRY  - Country code (e.g., 'US', 'GB')  [default: 'US']

"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from functools import lru_cache
from html import unescape
from typing import Any
from urllib.parse import quote

import feedparser
import httpx
from dotenv import load_dotenv
from googlenewsdecoder import gnewsdecoder
from mcp.server.fastmcp import FastMCP

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GOOGLE_NEWS_BASE = "https://news.google.com/rss"
LANGUAGE = os.getenv("GOOGLE_NEWS_LANGUAGE", "en")
COUNTRY = os.getenv("GOOGLE_NEWS_COUNTRY", "US")

_url_decode_cache: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1024)
def _cached_gnewsdecoder(url: str) -> dict[str, Any]:
    """
    Cached wrapper around gnewsdecoder to avoid redundant HTTP calls.
    Uses LRU cache with 1024 entry limit.
    """
    try:
        return gnewsdecoder(source_url=url)
    except Exception as e:
        logger.warning(f"Error in gnewsdecoder for {url}: {type(e).__name__}: {e}")
        return {"status": False, "message": str(e)}


async def resolve_google_news_url(url: str) -> str:
    """
    Decodes Google News encoded URLs to get the actual article URL.
    Uses caching and async executor for better performance. Non-blocking with concurrent processing.
    If the URL is not a Google News URL or decoding fails, returns the original URL.
    """
    if "news.google.com" not in url:
        return url

    if url in _url_decode_cache:
        return _url_decode_cache[url]

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _cached_gnewsdecoder, url)

    if result.get("status"):
        decoded_url = result.get("decoded_url")
        logger.info(f"Google News URL decoded: {decoded_url}")
        _url_decode_cache[url] = decoded_url
        return decoded_url
    else:
        logger.warning(f"Failed to decode Google News URL: {result.get('message')}")
        _url_decode_cache[url] = url
        return url


async def extract_text_with_decoded_urls(html: str) -> str:
    """
    Async version: Extract plain text from HTML and decode Google News URLs concurrently.
    Processes HTML summary to:
    1. Extract link text and decode Google News URLs in parallel
    2. Return plain text with decoded URLs
    """
    if not html:
        return ""

    links = re.findall(r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>([^<]*)</a>', html, flags=re.IGNORECASE)

    # Create concurrent decode tasks
    async def process_link(url: str, link_text: str) -> str:
        link_text = link_text.strip()
        if "news.google.com" in url:
            decoded_url = await resolve_google_news_url(url)
        else:
            decoded_url = url
        return f"{link_text} ({decoded_url})"

    # Process all links concurrently
    tasks = [process_link(url, link_text) for url, link_text in links]
    text_items = await asyncio.gather(*tasks)

    result = "\n".join(text_items)
    result = unescape(result)
    return result.strip()




async def _fetch_rss_feed(url: str) -> dict[str, Any]:
    """
    Async version: Fetch and parse RSS feed with concurrent URL decoding.
    Returns a dict with 'entries' list and 'feed' metadata.
    """
    logger.info(f"Fetching RSS feed: {url}")
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10.0, follow_redirects=True)
        response.raise_for_status()

    feed = feedparser.parse(response.text)

    entries = []
    
    async def process_entry(entry: Any) -> dict[str, Any]:
        link = entry.get("link", "")

        if link and "news.google.com" in link:
            link = await resolve_google_news_url(link)

        summary = entry.get("summary", "")
        if summary:
            summary = await extract_text_with_decoded_urls(summary)

        return {
            "title": entry.get("title", ""),
            "link": link,
            "published": entry.get("published", ""),
            "summary": summary,
            "source": entry.get("source", {}).get("title", "Unknown") if "source" in entry else "Unknown",
        }

    # Process all entries concurrently
    entry_tasks = [process_entry(entry) for entry in feed.entries]
    entries = await asyncio.gather(*entry_tasks)

    return {
        "title": feed.feed.get("title", ""),
        "link": feed.feed.get("link", ""),
        "description": feed.feed.get("description", ""),
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "google-news",
    instructions=(
        "This server provides access to Google News RSS feeds. "
        "Use get_top_headlines for global news, get_category_feed for specific topics, "
        "get_search_feed for keyword-based search, or get_geo_feed for location-specific news."
    ),
)


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_top_headlines(
    language: str | None = None,
    country: str | None = None,
) -> dict[str, Any]:
    """
    Get top headlines for a country.

    Args:
        language: Language code (e.g., 'en', 'fr') [default: from config]
        country: Country code (e.g., 'US', 'GB') [default: from config]

    Returns:
        Dict with feed title, description, and list of article entries
    """
    lang = language or LANGUAGE
    ctry = country or COUNTRY

    url = f"{GOOGLE_NEWS_BASE}?hl={lang}&gl={ctry}&ceid={ctry}:{lang}"
    return await _fetch_rss_feed(url)


@mcp.tool()
async def get_category_feed(
    category: str,
    language: str | None = None,
    country: str | None = None,
) -> dict[str, Any]:
    """
    Get headlines for a specific category.

    Args:
        category: Category name (WORLD, NATION, BUSINESS, TECHNOLOGY, ENTERTAINMENT, 
                  SPORTS, SCIENCE, HEALTH)
        language: Language code [default: from config]
        country: Country code [default: from config]

    Returns:
        Dict with feed title, description, and list of article entries
    """
    lang = language or LANGUAGE
    ctry = country or COUNTRY
    category_upper = category.upper()

    url = (
        f"{GOOGLE_NEWS_BASE}/headlines/section/topic/{category_upper}"
        f"?hl={lang}&gl={ctry}&ceid={ctry}:{lang}"
    )
    return await _fetch_rss_feed(url)


@mcp.tool()
async def get_search_feed(
    query: str,
    language: str | None = None,
    country: str | None = None,
) -> dict[str, Any]:
    """
    Search Google News and get RSS feed for results.

    Supports advanced search operators:
      - Exact match: "phrase in quotes"
      - Exclude: -word
      - Site specific: site:domain.com
      - Time range: when:24h (options: 1h, 24h, 7d, 30d, 1y) or when:1m
      - After date: after:YYYY-MM-DD
      - Before date: before:YYYY-MM-DD
      - Title search: intitle:keyword
      - Multiple terms: term1 OR term2

    Args:
        query: Search query with optional advanced operators
        language: Language code [default: from config]
        country: Country code [default: from config]

    Returns:
        Dict with feed title, description, and list of article entries (up to 100)
    """
    lang = language or LANGUAGE
    ctry = country or COUNTRY

    encoded_query = quote(query)

    url = (
        f"{GOOGLE_NEWS_BASE}/search?q={encoded_query}"
        f"&hl={lang}&gl={ctry}&ceid={ctry}:{lang}"
    )
    return await _fetch_rss_feed(url)


@mcp.tool()
async def get_geo_feed(
    location: str,
    language: str | None = None,
    country: str | None = None,
) -> dict[str, Any]:
    """
    Get news specific to a geographic location.

    Args:
        location: City, state, or region name (e.g., 'San Francisco', 'London')
        language: Language code [default: from config]
        country: Country code [default: from config]

    Returns:
        Dict with feed title, description, and list of article entries
    """
    lang = language or LANGUAGE
    ctry = country or COUNTRY

    encoded_location = quote(location)

    url = (
        f"{GOOGLE_NEWS_BASE}/headlines/section/geo/{encoded_location}"
        f"?hl={lang}&gl={ctry}&ceid={ctry}:{lang}"
    )
    return await _fetch_rss_feed(url)


@mcp.tool()
async def decode_google_news_url(urls: list[str]) -> dict[str, list[dict[str, str]]]:
    """
    Convert multiple Google News URLs to their actual article URLs.

    Decodes Google News wrapped URLs (news.google.com/articles/...) to their 
    original article URLs concurrently. If a URL is not a Google News URL or 
    decoding fails, returns the original URL.

    Args:
        urls: A list of Google News URLs to decode 
              (e.g., ["https://news.google.com/articles/CAIiE...", ...])

    Returns:
        Dict with "decoded_urls" list containing dicts with "original_url" and "decoded_url" fields
    """
    async def decode_one(url: str) -> dict[str, str]:
        decoded = await resolve_google_news_url(url)
        return {
            "original_url": url,
            "decoded_url": decoded,
        }
    
    tasks = [decode_one(url) for url in urls]
    decoded_urls = await asyncio.gather(*tasks)
    
    return {
        "decoded_urls": decoded_urls,
    }


@mcp.tool()
def list_categories() -> dict[str, list[str]]:
    """
    List available news categories for get_category_feed.

    Returns:
        Dict with list of category names
    """
    return {
        "categories": [
            "WORLD",
            "NATION",
            "BUSINESS",
            "TECHNOLOGY",
            "ENTERTAINMENT",
            "SPORTS",
            "SCIENCE",
            "HEALTH",
        ]
    }


@mcp.tool()
async def get_topic_feed(
    topic_id: str,
    language: str | None = None,
    country: str | None = None,
) -> dict[str, Any]:
    """
    Get news for a specific Google News topic ID.

    Topic IDs are hashes for trending topics (e.g., cryptocurrency, AI, etc.)

    Args:
        topic_id: Google News topic hash identifier
        language: Language code [default: from config]
        country: Country code [default: from config]

    Returns:
        Dict with feed title, description, and list of article entries
    """
    lang = language or LANGUAGE
    ctry = country or COUNTRY

    url = (
        f"{GOOGLE_NEWS_BASE}/topics/{topic_id}"
        f"?hl={lang}&gl={ctry}&ceid={ctry}:{lang}"
    )
    return await _fetch_rss_feed(url)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the Google News MCP server."""
    import asyncio
    asyncio.run(mcp.run(transport="stdio"))

if __name__ == "__main__":
    main()
