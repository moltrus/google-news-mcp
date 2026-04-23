# Google News MCP

A **Model Context Protocol (MCP)** server that exposes **Google News RSS feeds** as MCP tools, allowing AI assistants (Claude, GPT-4, etc.) to access real-time news data with automatic URL decoding, concurrent processing, and intelligent caching.

### Key Features

**Async & Concurrent** - All operations run asynchronously with concurrent URL decoding for maximum performance  
**Smart Caching** - LRU cache (1024 entries) for fast repeated URL decodings  
**Batch URL Decoding** - Decode multiple Google News URLs in parallel  
**Clean Summaries** - Extracts plain text from HTML summaries with decoded article links  
**Token-Oriented Object Notation (TOON)** - Support for a compact, token-efficient response format (30-60% reduction)  
**Multi-language Support** - Configure for any language/country combination  
**Advanced Search** - Full support for Google News search operators (site:, when:, intitle:, etc.)  
**Page Extraction** - Fetch and summarize full article content using [Jina Reader](https://jina.ai/reader/) and [Groq](https://groq.com/)

---

## Tool Overview

| Tool | Purpose | Parameters |
|---|---|---|
| `get_top_headlines` | Latest headlines by country | `language`, `country` |
| `get_category_feed` | News by category (TECH, BUSINESS, etc.) | `category`, `language`, `country` |
| `get_search_feed` | Search news with advanced operators | `query`, `language`, `country` |
| `get_geo_feed` | Location-specific news | `location`, `language`, `country` |
| `get_topic_feed` | Trending topic by ID | `topic_id`, `language`, `country` |
| `decode_google_news_url` | Decode Google News URLs | `urls` (list) |
| `list_categories` | Available news categories | (none) |
| `fetch_content` | Fetch and summarize page content | `url`, `summarize` |

**Total: 8 tools**

---

## Quick Start

### Installation

**Option 1: Using uv (recommended)**

```bash
# Clone the repository
git clone https://github.com/moltrus/google-news-mcp.git
cd google-news-mcp

# Install with uv
uv sync
```

**Option 2: Using pip with virtual environment**

```bash
# Clone the repository
git clone https://github.com/moltrus/google-news-mcp.git
cd google-news-mcp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .
```

**For Global Usage (Any Method)**

To use the `google-news-mcp` command globally from anywhere:

```bash
pip install -e .
```

This installs the command-line entry point system-wide, allowing you to run `google-news-mcp` from any directory.

### Configuration

Create a `.env` file based on [.env.example](.env.example):

```bash
# RSS Preferences
GOOGLE_NEWS_LANGUAGE=en
GOOGLE_NEWS_COUNTRY=US

# Response Optimization
# Options: "json" (standard) or "toon" (token-optimized)
RESPONSE_FORMAT=json

# Fetching & Summarization
JINA_API_KEY=your_jina_key
GROQ_API_KEY=your_groq_key
GROQ_MODEL=qwen/qwen3-32b
```

### Running the Server

```bash
google-news-mcp
```

Or directly:

```bash
python -m google_news_mcp.server
```

---

## Tool Documentation

### get_top_headlines

Fetch the latest top headlines for a country.

**Parameters:**
- `language` (string, optional): Language code (e.g., `'en'`, `'fr'`, `'es'`). Defaults to `GOOGLE_NEWS_LANGUAGE` env var.
- `country` (string, optional): Country code (e.g., `'US'`, `'GB'`, `'JP'`). Defaults to `GOOGLE_NEWS_COUNTRY` env var.

**Returns:**
```json
{
  "title": "Google News",
  "link": "https://news.google.com",
  "description": "Latest news",
  "entries": [
    {
      "title": "Article Title",
      "link": "https://source.com/article",
      "published": "2026-03-31T10:00:00Z",
      "summary": "Article Title (https://source.com/article)\nAnother Article (https://another.com/news)",
      "source": "Source Name"
    }
  ]
}
```

**Notes:**
- Articles are sorted by relevance (Google News default)
- URLs are automatically decoded from Google News redirects
- Summaries contain extracted links in plain text format

---

### get_category_feed

Get news headlines for a specific category.

**Parameters:**
- `category` (string, required): News category. Valid values:
  - `WORLD` - International news
  - `NATION` - National/local headlines
  - `BUSINESS` - Business & finance
  - `TECHNOLOGY` - Tech & AI
  - `ENTERTAINMENT` - Entertainment & pop culture
  - `SPORTS` - Sports
  - `SCIENCE` - Science & research
  - `HEALTH` - Health & medicine
- `language` (string, optional): Language code. Defaults to config.
- `country` (string, optional): Country code. Defaults to config.

**Returns:** Same as `get_top_headlines`

**Examples:**
```
get_category_feed(category="TECHNOLOGY")
get_category_feed(category="BUSINESS", country="UK")
```

---

### get_search_feed

Search Google News with keyword queries and advanced operators.

**Parameters:**
- `query` (string, required): Search query with optional operators
- `language` (string, optional): Language code. Defaults to config.
- `country` (string, optional): Country code. Defaults to config.

**Supported Search Operators:**
- **Exact phrase:** `"Artificial Intelligence"` (must match exactly)
- **Exclude term:** `-apple` (exclude articles with "apple")
- **Site-specific:** `site:techcrunch.com` (only from domain)
- **Time range (relative):** `when:1h`, `when:24h`, `when:7d`, `when:30d`, `when:1y`, `when:1m`
- **Time range (absolute):** `after:2026-01-01`, `before:2026-03-31`
- **Title search:** `intitle:merger` (term appears in headline only)
- **Boolean OR:** `Tesla OR SpaceX` (either term)
- **Combinations:** `"GPT-4" site:openai.com when:7d` (all together)

**Returns:** Same as `get_top_headlines` (max ~100 articles)

**Query Examples:**
```
"OpenAI Sora"                                # Exact phrase
AI -hype                                     # Include AI, exclude hype
site:arxiv.org quantum computing             # From academic site
when:1h breaking                             # Last hour
when:24h -rumor Bitcoin                      # Last 24h, exclude rumors
after:2026-03-01 before:2026-03-31 merger    # Date range
intitle:IPO tech companies                   # IPO in headline
SpaceX OR Blue Origin                        # Either company OR other
```

**Important:** Date filters work on a **daily basis** (not hourly/minute precision).

---

### get_geo_feed

Get news for a specific geographic location.

**Parameters:**
- `location` (string, required): City, state, region, or country (e.g., `'San Francisco'`, `'California'`, `'Japan'`)
- `language` (string, optional): Language code. Defaults to config.
- `country` (string, optional): Country code. Defaults to config.

**Returns:** Same as `get_top_headlines`

**Examples:**
```
get_geo_feed(location="New York")
get_geo_feed(location="London", language="en")
get_geo_feed(location="Tokyo", country="JP")
```

---

### fetch_content

Fetch clean page content from a URL using Jina Reader API, with optional summarization via Groq.

**Parameters:**
- `url` (string, required): Absolute URL to fetch (must start with http:// or https://)
- `summarize` (boolean, optional): If `true`, returns a concise summary via Groq and omits the full raw content to save tokens. Defaults to `false`.

**Returns:**
```json
{
  "url": "https://example.com/article",
  "reader_url": "https://r.jina.ai/https://example.com/article",
  "content": "Full article text...",
  "summary": "Concise summary points...",
  "summary_model": "qwen/qwen3-32b",
  "summary_error": "Error message if summarization fails"
}
```

**Notes:**
- **Token Efficiency:** When `summarize` is `true`, the `content` field is automatically removed from the response to prevent context window bloat.
- **Environment Variables:**
  - `JINA_API_KEY`: Required for content extraction.
  - `GROQ_API_KEY`: Required for summarization.
  - `GROQ_MODEL`: Optional. Specific model to use (defaults to `qwen/qwen3-32b`).

---

### decode_google_news_url

Decode multiple Google News URLs to their actual article destinations **in parallel**.

**Parameters:**
- `urls` (list of strings, required): Array of Google News redirect URLs to decode

**Returns:**
```json
{
  "decoded_urls": [
    {
      "original_url": "https://news.google.com/articles/CBMi8wFAUU...",
      "decoded_url": "https://techcrunch.com/2026/03/31/ai-news"
    },
    {
      "original_url": "https://news.google.com/articles/CBMixAFAUU...",
      "decoded_url": "https://theverge.com/2026/3/31/10987654"
    }
  ]
}
```

**Performance:**
- All URLs decoded **concurrently** (no sequential delays)
- Results cached for repeat lookups (instant on cache hit)
- LRU cache with 1024 entry limit

**Examples:**
```python
decode_google_news_url(urls=[
  "https://news.google.com/articles/CBMi8wFAUU...",
  "https://news.google.com/articles/CBMixAFAUU...",
  "https://news.google.com/articles/CBMi5gFAUU..."
])
```

---

### get_topic_feed

Get news for a specific trending topic by its topic ID.

Google News tracks trending topics as hashes (e.g., companies, events, recurring themes).

**Parameters:**
- `topic_id` (string, required): Google News topic hash identifier
- `language` (string, optional): Language code. Defaults to config.
- `country` (string, optional): Country code. Defaults to config.

**Returns:** Same as `get_top_headlines`

**Common Topic IDs:**
- `CAAqKAgKIiJDQkFTRXdvS0wyMHZNSFp3YWpSZlloSUZaVzR0UjBJb0FBUAE` - Cryptocurrencies
- Find more by exploring Google News and checking the topic parameter in URLs

**Examples:**
```
get_topic_feed(topic_id="CAAqKAgKIiJDQkFTRXdvS0wyMHZNSFp3YWpSZlloSUZaVzR0UjBJb0FBUAE")
```

---

### list_categories

Get the list of available news categories.

**Parameters:** None

**Returns:**
```json
{
  "categories": [
    "WORLD",
    "NATION",
    "BUSINESS",
    "TECHNOLOGY",
    "ENTERTAINMENT",
    "SPORTS",
    "SCIENCE",
    "HEALTH"
  ]
}
```

---

## Architecture

### Performance Optimizations

1. **Async/Await** - All I/O operations (HTTP, decoding) are non-blocking
2. **Concurrent Processing** - Multiple URLs and entries processed in parallel via `asyncio.gather()`
3. **LRU Cache (1024 entries)** - Decoded URLs cached at function level
4. **In-Memory Dictionary Cache** - Additional fast lookup cache for decoded URLs
5. **Batch Operations** - `decode_google_news_url` processes lists of URLs concurrently

### Summary Format

Article summaries are extracted from HTML and returned as **plain text** with decoded links:

```
Article Title 1 (https://original-source.com/article1)
Image caption link (https://image-source.com/photo)
Article Title 2 (https://original-source.com/article2)
```

HTML tags, CDATA wrappers, and entities are stripped for clean, readable text.

---

## Usage Examples

### 1. Get breaking news in the last hour

```
get_search_feed(query="when:1h breaking", country="US")
```

### 2. Decode multiple article URLs at once

```
decode_google_news_url(urls=[
  "https://news.google.com/articles/CBMi8wFAUU...",
  "https://news.google.com/articles/CBMixAFAUU..."
])
```

### 3. Tech news from specific source

```
get_search_feed(query="site:techcrunch.com AI")
```

### 4. Local news for a city

```
get_geo_feed(location="San Francisco")
```

### 5. Search with date range

```
get_search_feed(query="SpaceX after:2026-03-01 before:2026-03-31")
```

### 6. Get health news

```
get_category_feed(category="HEALTH")
```

### 7. Trending cryptocurrency news

```
get_topic_feed(topic_id="CAAqJggKIiBDQkFTRWdvSUwyMHZNR3d5YldFeVpYVXVhVzV6U0FpQkFQAQ")
```

### 8. Fetch and summarize a full article

```
fetch_content(url="https://techcrunch.com/article-url", summarize=true)
```

---

## Token Efficiency & TOON

This server supports **Token-Oriented Object Notation (TOON)**, a compact data format designed specifically for LLMs.

### Why use TOON?
Standard JSON can be verbose for LLMs due to repeated keys and punctuation. TOON reduces token usage by **30-60%** by:
- Defining keys once for arrays of objects (tabular format).
- Removing unnecessary braces, brackets, and quotes.
- Using indentation and simple delimiters.

### Configuration
To enable TOON globally for all tool responses, set the following in your `.env`:
```bash
RESPONSE_FORMAT=toon
```

### Comparison

| JSON (Verbose) | TOON (Compact) |
| :--- | :--- |
| `{"entries": [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]}` | `entries[2,]{id,title}:`<br>&nbsp;&nbsp;`1,A`<br>&nbsp;&nbsp;`2,B` |

---

## Limitations

1. **Result limit:** Google News RSS returns max ~100 articles per request
2. **Sorting:** Default is relevance. Use `when:` filters for temporal ordering
3. **Date precision:** Filters work on **daily basis**, not by hour/minute
4. **Rate limiting:** No API keys needed for RSS, but Jina Reader and Groq have their own limits/quotas
5. **Content Extraction:** `fetch_content` depends on Jina Reader's ability to parse the target site
7. **Topic IDs:** Must be discovered from Google News URLs; no lookup API

---

## License

MIT
