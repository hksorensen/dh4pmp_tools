# Web Page Fetcher

A robust web page fetching library with local file-based caching, retry logic, and optional Selenium support for JavaScript-heavy pages and CAPTCHA handling.

## Features

- **Local file-based caching**: Efficient caching using MD5-keyed JSON files
- **Automatic retry logic**: Configurable retries with exponential backoff
- **Two implementations**:
  - `WebPageFetcher`: Lightweight requests-based fetcher
  - `SeleniumWebFetcher`: Extended version with Selenium support
- **PDF downloading**: Intelligent PDF detection and download with CloudFlare support
- **CAPTCHA handling**: Manual and automated CAPTCHA solving capabilities
- **Rate limiting**: Built-in delays for batch fetching
- **Context manager support**: Clean resource management

## Installation

### Basic installation (requests only)

```bash
pip install requests urllib3
```

### With Selenium support

```bash
pip install requests urllib3 selenium
```

You'll also need to install a browser driver:

**Chrome/Chromium:**
```bash
# Ubuntu/Debian
sudo apt-get install chromium-chromedriver

# macOS
brew install chromedriver

# Or download from: https://chromedriver.chromium.org/
```

**Firefox:**
```bash
# Ubuntu/Debian
sudo apt-get install firefox-geckodriver

# macOS
brew install geckodriver

# Or download from: https://github.com/mozilla/geckodriver/releases
```

## Usage

### Basic Usage with WebPageFetcher

```python
from web_fetcher import WebPageFetcher

# Create fetcher instance
fetcher = WebPageFetcher(
    cache_dir="./cache/web_pages",
    max_retries=3,
    backoff_factor=1.0,
)

# Fetch a single page
result = fetcher.fetch("https://example.com")
print(f"Status: {result['status_code']}")
print(f"From cache: {result['cached']}")
print(f"Content: {result['content'][:200]}")

# Fetch with query parameters
result = fetcher.fetch(
    "https://api.example.com/data",
    params={'key': 'value', 'page': 1}
)

# Fetch multiple URLs
urls = ["https://example.com", "https://python.org"]
results = fetcher.fetch_multiple(urls, delay=1.0)
```

### Using Context Manager

```python
with WebPageFetcher(cache_dir="./cache") as fetcher:
    result = fetcher.fetch("https://example.com")
    # Session automatically closed
```

### Advanced Features

```python
# Force refresh (bypass cache)
fetcher = WebPageFetcher(force_refresh=True)
result = fetcher.fetch("https://example.com")

# Custom headers
result = fetcher.fetch(
    "https://example.com",
    headers={'Authorization': 'Bearer token123'}
)

# POST requests
result = fetcher.fetch(
    "https://api.example.com/submit",
    method="POST",
    data={'key': 'value'}
)

# Clear cache
fetcher.clear_cache()  # Clear all
fetcher.clear_cache(url="https://example.com")  # Clear specific URL
```

### Using Selenium for JavaScript Rendering

```python
from selenium_web_fetcher import SeleniumWebFetcher
from selenium.webdriver.common.by import By

# Create Selenium-enabled fetcher
fetcher = SeleniumWebFetcher(
    cache_dir="./cache/selenium",
    use_selenium=True,
    headless=True,
)

# Basic fetch with Selenium
result = fetcher.fetch("https://example.com")

# Wait for specific element before capturing
result = fetcher.fetch(
    "https://dynamic-site.com",
    wait_for_element=(By.ID, "content")
)

# Execute JavaScript after page load
result = fetcher.fetch(
    "https://example.com",
    execute_script="window.scrollTo(0, document.body.scrollHeight);"
)

# Automatically accept cookies if present
result = fetcher.fetch(
    "https://example.com",
    cookie_accept_selector=(By.ID, "accept-cookies")  # or By.CLASS_NAME, By.XPATH, etc.
)

# Don't forget to close the driver
fetcher.close_driver()
```

### Mixed Usage (Requests + Selenium)

```python
# Use requests by default, Selenium when needed
with SeleniumWebFetcher(use_selenium=False) as fetcher:
    # This uses requests (fast)
    result1 = fetcher.fetch("https://simple-page.com")
    
    # This uses Selenium (slower but handles JS)
    result2 = fetcher.fetch(
        "https://javascript-heavy-page.com",
        use_selenium=True,
        wait_for_element=(By.CLASS_NAME, "dynamic-content"),
        cookie_accept_selector=(By.CLASS_NAME, "cookie-accept")  # Auto-accept cookies
    )
```

### Lazy Initialization (Using Utility Methods Without Browser)

The browser only opens when you actually need Selenium. You can use utility methods like `get_cache_filename` without browser overhead:

```python
# Create fetcher - browser does NOT open yet
fetcher = SeleniumWebFetcher(
    use_selenium=True,
    headless=True,
    cache_dir="./cache"
)

# Use utility methods without opening browser
url = "https://example.com"

# Check if cached
cache_file = fetcher.get_cache_filename(url)
if cache_file:
    print(f"Found: {cache_file}")

# Get cache information
has_cache = fetcher.has_cache(url)
cache_key = fetcher._get_cache_key(url)

# Browser only opens when you actually fetch
response = fetcher.fetch(url, use_selenium=True)  # Browser opens here

fetcher.close()
```

This is useful when you want to check cache status or manage cache files without the overhead of launching a browser.

### Eliminating Delays for Cache Operations

The fetcher includes several configurable delays for page loading. For cache-only operations, you can eliminate all delays:

```python
# Zero delays - instant cache operations
fetcher = SeleniumWebFetcher(
    use_selenium=True,
    headless=True,
    page_load_wait=0.0,     # No wait after page load (default: 2.0)
    wait_timeout=1,         # Minimal timeout (default: 10)
    random_wait_min=0.0,    # No random delays (default: 0.0)
    random_wait_max=0.0     # No random delays (default: 0.0)
)

# Cache operations are instant regardless of configuration
cache_file = fetcher.get_cache_filename(url)  # Instant
has_cache = fetcher.has_cache(url)            # Instant
```

**Delay parameters:**
- `page_load_wait`: Time to wait after page loads (for JS rendering)
- `wait_timeout`: Max time to wait for specific elements
- `random_wait_min/max`: Random delay between requests (for rate limiting)

**When to use different configurations:**
- **Cache operations only**: `page_load_wait=0.0, wait_timeout=1`
- **Simple pages**: `page_load_wait=0.5, wait_timeout=5`  
- **Standard sites** (default): `page_load_wait=2.0, wait_timeout=10`
- **Heavy JS sites**: `page_load_wait=3.0, wait_timeout=15`
- **Avoid rate limits**: Set `random_wait_max=3.0` for 0-3s random delays

See `examples/minimal_delays.py` for detailed configuration examples.

### Cookie Acceptance

For websites that show cookie consent banners, you can automatically accept cookies:

```python
from selenium.webdriver.common.by import By

fetcher = SeleniumWebFetcher(
    use_selenium=True,
    headless=True,
)

# Automatically click cookie accept button if present
result = fetcher.fetch(
    "https://example.com",
    cookie_accept_selector=(By.ID, "accept-cookies")
)

# The fetcher will:
# 1. Load the page
# 2. Check if the cookie button exists
# 3. Click it if found
# 4. Wait for the page to reload
# 5. Return the final page content
```

You can use any Selenium `By` locator:
- `By.ID` - for element IDs
- `By.CLASS_NAME` - for CSS classes
- `By.XPATH` - for XPath expressions
- `By.CSS_SELECTOR` - for CSS selectors
- `By.TAG_NAME` - for HTML tag names

**Note:** The cookie accept button is only clicked if it's present. If the button doesn't exist, the fetcher will continue normally without error.

### PDF Downloading

The `SeleniumWebFetcher` includes intelligent PDF downloading that handles:
- Direct PDF URLs
- Pages with PDF download links/buttons
- CloudFlare challenges
- Cookie acceptance

The download process follows a 3-step approach:
1. Check if the page itself is a PDF file → download it
2. If not, search for PDF links/buttons (with text like "DOI", "Download", "PDF") → click and go to step 1
3. If neither works, report failure and continue

```python
from pathlib import Path
from selenium.webdriver.common.by import By

with SeleniumWebFetcher(
    use_selenium=True,
    headless=True,
    use_undetected=True,  # Helps bypass bot detection
    random_wait_min=2.0,  # Wait between requests to avoid rate limiting
    random_wait_max=5.0,
) as fetcher:
    
    # Example 1: Direct PDF URL
    pdf_path = fetcher.download_pdf(
        url="https://example.com/document.pdf",
        output_path=Path("./downloads/document.pdf")
    )
    if pdf_path:
        print(f"✓ Downloaded: {pdf_path}")
    
    # Example 2: Page with PDF download link
    pdf_path = fetcher.download_pdf(
        url="https://example.com/article",
        output_path=Path("./downloads/article.pdf"),
        cookie_accept_selector=(By.ID, "accept-cookies"),  # Auto-accept cookies
    )
    
    # Example 3: Science.org article (handles CloudFlare automatically)
    pdf_path = fetcher.download_pdf(
        url="https://www.science.org/doi/10.1126/science.abc123",
        output_path=Path("./downloads/science_article.pdf"),
        cookie_accept_selector=(By.CLASS_NAME, "osano-cm-acceptAll"),
    )
```

**PDF Detection:**
- Automatically detects if current page is a PDF (by content-type, URL, or content)
- Searches for PDF links by text keywords: "DOI", "Download", "PDF", "Full Text", etc.
- Searches for PDF links by URL patterns: `.pdf` extension, `/pdf` path, `format=pdf` parameter

**CloudFlare Handling:**
- Automatically waits for CloudFlare challenges to complete
- Falls back to manual intervention if automatic wait times out
- Handles rate limiting gracefully with informative error messages

**Cookie Acceptance:**
- Automatically clicks cookie accept buttons if selector is provided
- Handles cookies on both initial page and PDF link pages

### Manual CAPTCHA Solving

For pages with CAPTCHAs, you can use manual solving:

```python
fetcher = SeleniumWebFetcher(
    use_selenium=True,
    headless=False,  # Must be visible for manual solving
)

# Opens browser window and waits for you to solve CAPTCHA
result = fetcher.handle_captcha_manual(
    "https://site-with-captcha.com",
    timeout=120  # Wait up to 2 minutes
)

# Press Enter in terminal when done, or script continues after timeout
```

## Configuration

### WebPageFetcher Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cache_dir` | str/Path | `"./cache/web_pages"` | Directory for cache files |
| `max_retries` | int | `3` | Maximum retry attempts |
| `backoff_factor` | float | `1.0` | Exponential backoff multiplier |
| `timeout` | int/tuple | `(10, 30)` | Request timeout (connect, read) |
| `user_agent` | str | Chrome UA | User agent string |
| `force_refresh` | bool | `False` | Always bypass cache |

### SeleniumWebFetcher Additional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_selenium` | bool | `False` | Use Selenium by default |
| `headless` | bool | `True` | Run browser in headless mode |
| `browser` | str | `'chrome'` | Browser to use ('chrome' or 'firefox') |
| `executable_path` | str/Path | `None` | Path to browser driver |
| `wait_timeout` | int | `10` | Element wait timeout (seconds) |
| `page_load_wait` | float | `2.0` | Wait after page load (seconds) |

## Response Format

Both fetchers return a dictionary with:

```python
{
    'url': str,              # Final URL (after redirects)
    'status_code': int,      # HTTP status code
    'content': str,          # Page content
    'headers': dict,         # Response headers
    'encoding': str,         # Content encoding
    'cached': bool,          # Whether from cache
    'timestamp': float,      # Unix timestamp
    'fetched_with_selenium': bool,  # (Selenium only)
}
```

## Cache Structure

Cache files are stored in subdirectories based on MD5 hash:

```
cache_dir/
├── 00/
│   ├── 00a1b2c3d4e5f6g7h8i9j0k1l2m3n4.json
│   └── 00f9e8d7c6b5a4938271605948372615.json
├── 01/
│   └── ...
└── ff/
    └── ...
```

## Error Handling

The fetchers use Python's built-in retry mechanisms and raise `requests.RequestException` on failure:

```python
from requests.exceptions import RequestException

try:
    result = fetcher.fetch("https://example.com")
except RequestException as e:
    print(f"Failed to fetch: {e}")
```

## Integration with Existing Projects

This library is designed to work alongside the `api_clients` package and follows similar patterns:

- File-based caching (not database)
- Automatic retry with exponential backoff
- Context manager support
- Structured logging

### Example: Using with api_clients

```python
from api_clients import ScopusClient, CrossrefClient
from web_fetcher import WebPageFetcher

# Use API clients for structured data
scopus = ScopusClient(api_key="your_key")
crossref = CrossrefClient()

# Use web fetcher for scraping journal websites
web_fetcher = WebPageFetcher(cache_dir="./cache/web")

# Get metadata from API
paper_metadata = scopus.get_abstract("SCOPUS_ID:12345")

# Fetch full text from publisher website
if 'link' in paper_metadata:
    webpage = web_fetcher.fetch(paper_metadata['link'])
```

## Logging

Both classes use Python's `logging` module:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Now fetcher operations will log
fetcher = WebPageFetcher()
result = fetcher.fetch("https://example.com")
```

## Performance Considerations

- **Requests mode**: Very fast, ideal for simple HTML pages
- **Selenium mode**: Slower due to browser overhead, use only when necessary
- **Caching**: First request is slow, subsequent requests are instant
- **Batch fetching**: Use `fetch_multiple()` with appropriate delays to avoid rate limiting

## Tips

1. Start with `WebPageFetcher` for most use cases
2. Use `SeleniumWebFetcher` only for JavaScript-heavy sites
3. Set `headless=True` for production, `headless=False` for debugging
4. Cache directory grows over time - implement periodic cleanup if needed
5. For CAPTCHA-protected sites, consider using manual solving mode
6. Always use context managers or explicitly close drivers/sessions

## License

This code is part of the sciec research project and follows the same license.
