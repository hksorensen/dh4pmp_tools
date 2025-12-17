# Rate Limiting and Batching Guide

When downloading many pages, you'll encounter rate limits. Here's how to handle them.

## Understanding Rate Limits

### Symptoms
- HTTP 429 "Too Many Requests"
- Cloudflare challenges appearing frequently
- Temporary bans (minutes to hours)
- Slower response times

### Causes
- Too many requests in short time
- Requests coming too fast (looks like bot)
- No variation in timing (consistent intervals = bot)

## Solution 1: Random Delays Between Requests

Use the built-in random wait feature:

```python
from web_fetcher import SeleniumWebFetcher

# Add 1-3 second random delays between requests
fetcher = SeleniumWebFetcher(
    use_selenium=True,
    headless=True,
    cache_dir="./cache",
    
    # Keep Cloudflare handling intact
    page_load_wait=2.0,      # Standard delays for CF
    wait_timeout=10,
    
    # Add random delays to mimic human behavior
    random_wait_min=1.0,     # Minimum 1 second
    random_wait_max=3.0      # Maximum 3 seconds
)

# This automatically adds random 1-3s delay before EACH fetch
for url in urls:
    result = fetcher.fetch(url, use_selenium=True)
    # Random delay happens automatically before next iteration

fetcher.close()
```

## Solution 2: Batch Processing with Sleep

For large batches, add explicit sleep between batches:

```python
import time
from web_fetcher import SeleniumWebFetcher

urls = [...]  # List of 1000 URLs

BATCH_SIZE = 50
BATCH_DELAY = 60  # 60 seconds between batches

fetcher = SeleniumWebFetcher(
    use_selenium=True,
    cache_dir="./cache",
    random_wait_min=1.0,
    random_wait_max=3.0
)

for i in range(0, len(urls), BATCH_SIZE):
    batch = urls[i:i+BATCH_SIZE]
    
    print(f"Processing batch {i//BATCH_SIZE + 1}/{len(urls)//BATCH_SIZE + 1}")
    
    for url in batch:
        # Check cache first - instant if cached!
        if fetcher.has_cache(url):
            print(f"  Cached: {url}")
            result = fetcher.fetch(url)  # Instant from cache
        else:
            print(f"  Fetching: {url}")
            result = fetcher.fetch(url, use_selenium=True)
    
    # Sleep between batches (except last batch)
    if i + BATCH_SIZE < len(urls):
        print(f"  Sleeping {BATCH_DELAY}s before next batch...")
        time.sleep(BATCH_DELAY)

fetcher.close()
```

## Solution 3: Progressive Backoff on Errors

Detect rate limits and slow down automatically:

```python
import time
from web_fetcher import SeleniumWebFetcher

def fetch_with_backoff(fetcher, url, max_retries=3):
    """Fetch with exponential backoff on rate limit errors."""
    
    for attempt in range(max_retries):
        try:
            result = fetcher.fetch(url, use_selenium=True)
            
            # Check for rate limit indicators in response
            if 'rate limit' in result.get('text', '').lower():
                wait_time = 2 ** attempt * 60  # 1min, 2min, 4min
                print(f"Rate limited! Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            return result
            
        except Exception as e:
            if '429' in str(e) or 'rate' in str(e).lower():
                wait_time = 2 ** attempt * 60
                print(f"Rate limited! Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
    
    raise Exception(f"Failed after {max_retries} retries")

# Usage
fetcher = SeleniumWebFetcher(
    use_selenium=True,
    random_wait_min=2.0,
    random_wait_max=5.0
)

for url in urls:
    if not fetcher.has_cache(url):
        result = fetch_with_backoff(fetcher, url)

fetcher.close()
```

## Solution 4: Cache-First Approach

Minimize requests by checking cache aggressively:

```python
from web_fetcher import SeleniumWebFetcher

# Create list of URLs to fetch
urls_to_fetch = [...]

# First pass: identify what needs fetching
fetcher = SeleniumWebFetcher(
    use_selenium=True,
    cache_dir="./cache"
)

uncached = []
cached = []

for url in urls_to_fetch:
    if fetcher.has_cache(url):
        cached.append(url)
    else:
        uncached.append(url)

print(f"Cached: {len(cached)}, Need to fetch: {len(uncached)}")

# Only fetch uncached URLs with delays
fetcher_with_delays = SeleniumWebFetcher(
    use_selenium=True,
    cache_dir="./cache",
    random_wait_min=2.0,
    random_wait_max=5.0
)

for i, url in enumerate(uncached):
    print(f"Fetching {i+1}/{len(uncached)}: {url}")
    result = fetcher_with_delays.fetch(url, use_selenium=True)
    
    # Extra sleep every 20 requests
    if (i + 1) % 20 == 0:
        print("  Pause for 2 minutes...")
        time.sleep(120)

fetcher_with_delays.close()

# Now fetch all from cache (instant)
for url in cached:
    result = fetcher.fetch(url)  # Instant!

fetcher.close()
```

## Solution 5: Distributed Over Time

Schedule fetching across hours/days:

```python
import time
from datetime import datetime
from web_fetcher import SeleniumWebFetcher

# Fetch 100 URLs per hour
URLS_PER_HOUR = 100
DELAY_BETWEEN_URLS = 3600 / URLS_PER_HOUR  # 36 seconds

fetcher = SeleniumWebFetcher(
    use_selenium=True,
    cache_dir="./cache",
    random_wait_min=1.0,
    random_wait_max=3.0
)

for i, url in enumerate(urls):
    if fetcher.has_cache(url):
        result = fetcher.fetch(url)  # Instant from cache
    else:
        print(f"{datetime.now()}: Fetching {i+1}/{len(urls)}: {url}")
        result = fetcher.fetch(url, use_selenium=True)
        
        # Sleep to maintain rate
        if i + 1 < len(urls):  # Don't sleep after last URL
            time.sleep(DELAY_BETWEEN_URLS)

fetcher.close()
```

## Recommended Settings by Site Type

### Well-Behaved Sites (no rate limiting)
```python
SeleniumWebFetcher(
    random_wait_min=0.5,
    random_wait_max=1.5
)
# ~1 second between requests
```

### Normal Sites (moderate rate limiting)
```python
SeleniumWebFetcher(
    random_wait_min=2.0,
    random_wait_max=5.0
)
# ~3.5 seconds between requests
```

### Strict Sites (aggressive rate limiting)
```python
SeleniumWebFetcher(
    random_wait_min=5.0,
    random_wait_max=10.0
)
# ~7.5 seconds between requests
# + batch delays every 20-50 requests
```

### Very Strict Sites (Cloudflare, anti-bot)
```python
SeleniumWebFetcher(
    random_wait_min=10.0,
    random_wait_max=20.0,
    use_undetected=True
)
# ~15 seconds between requests
# + longer batch delays (5+ minutes)
# + smaller batches (10-20 URLs)
```

## Monitoring for Rate Limits

Check for rate limit indicators:

```python
def is_rate_limited(result):
    """Detect if response indicates rate limiting."""
    text = result.get('text', '').lower()
    status = result.get('status_code', 200)
    
    indicators = [
        status == 429,
        'rate limit' in text,
        'too many requests' in text,
        'please slow down' in text,
        'blocked' in text,
        'captcha' in text and 'cloudflare' not in text  # Non-CF captcha
    ]
    
    return any(indicators)

# Usage
for url in urls:
    result = fetcher.fetch(url, use_selenium=True)
    
    if is_rate_limited(result):
        print("Rate limited! Sleeping 5 minutes...")
        time.sleep(300)
        result = fetcher.fetch(url, use_selenium=True)  # Retry
```

## Best Practices

1. **Always use cache** - Check `has_cache()` first
2. **Add random delays** - Use `random_wait_min/max`
3. **Batch processing** - Process in chunks with breaks
4. **Monitor responses** - Detect rate limits early
5. **Keep Cloudflare delays** - Don't disable `page_load_wait` completely
6. **Be patient** - Slower is more reliable
7. **Log everything** - Track what's been fetched

## Example: Complete Rate-Limited Scraper

```python
import time
import logging
from web_fetcher import SeleniumWebFetcher

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 50
BATCH_DELAY = 300  # 5 minutes between batches
MAX_RETRIES = 3

def fetch_with_rate_limiting(urls, cache_dir="./cache"):
    """Fetch URLs with comprehensive rate limiting."""
    
    fetcher = SeleniumWebFetcher(
        use_selenium=True,
        headless=True,
        cache_dir=cache_dir,
        
        # Keep Cloudflare handling
        page_load_wait=2.0,
        wait_timeout=10,
        
        # Add human-like delays
        random_wait_min=2.0,
        random_wait_max=5.0
    )
    
    # Separate cached and uncached
    uncached = [url for url in urls if not fetcher.has_cache(url)]
    cached = [url for url in urls if fetcher.has_cache(url)]
    
    logger.info(f"Total URLs: {len(urls)}")
    logger.info(f"Cached: {len(cached)}, Need to fetch: {len(uncached)}")
    
    # Process uncached in batches
    for batch_num, i in enumerate(range(0, len(uncached), BATCH_SIZE)):
        batch = uncached[i:i+BATCH_SIZE]
        logger.info(f"Batch {batch_num + 1}: Processing {len(batch)} URLs")
        
        for j, url in enumerate(batch):
            for attempt in range(MAX_RETRIES):
                try:
                    logger.info(f"  [{j+1}/{len(batch)}] Fetching: {url}")
                    result = fetcher.fetch(url, use_selenium=True)
                    
                    if result.get('status_code') == 200:
                        break  # Success
                    else:
                        logger.warning(f"    Got status {result.get('status_code')}, retrying...")
                        time.sleep(30)
                        
                except Exception as e:
                    logger.error(f"    Error: {e}")
                    if attempt < MAX_RETRIES - 1:
                        logger.info(f"    Retrying in 60s...")
                        time.sleep(60)
                    else:
                        logger.error(f"    Failed after {MAX_RETRIES} attempts")
        
        # Sleep between batches
        if i + BATCH_SIZE < len(uncached):
            logger.info(f"  Sleeping {BATCH_DELAY}s before next batch...")
            time.sleep(BATCH_DELAY)
    
    fetcher.close()
    logger.info("Complete!")

# Usage
urls = [...]  # Your URL list
fetch_with_rate_limiting(urls)
```

## Summary

**Key insight:** All your Cloudflare/CAPTCHA delays are still there! I only made the optional delays configurable:

- ✅ Cloudflare detection delays: **Still there** (hard-coded)
- ✅ CAPTCHA handling: **Still there** (hard-coded)
- ✅ Page load wait: **Configurable** (but keep at 2.0 for CF sites)
- ✅ Random delays: **Configurable** (use for rate limiting)

**For rate limiting:**
1. Use `random_wait_min/max` for delays between requests
2. Add batch delays every 50-100 URLs
3. Always check cache first
4. Monitor for rate limit responses
5. Be patient - slower is more reliable!
