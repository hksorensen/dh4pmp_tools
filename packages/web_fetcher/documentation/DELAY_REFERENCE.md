# SeleniumWebFetcher Delay Reference

Complete reference for which operations involve delays and how to minimize them.

## Quick Reference

### Operations That NEVER Involve Delays

These methods work instantly regardless of configuration:

```python
fetcher = SeleniumWebFetcher(use_selenium=True, cache_dir="./cache")

# Cache inspection (instant)
fetcher.get_cache_filename(url)           # Get path to cached file
fetcher.has_cache(url)                    # Check if URL is cached
fetcher._get_cache_key(url, params)       # Get cache key
fetcher._get_cache_path(cache_key)        # Get cache file path
fetcher.clear_cache(url)                  # Delete cache file

# No browser opened, no delays!
```

### Operations That MAY Involve Delays

These operations only involve delays if they need to fetch from the web:

```python
# If cached: instant
# If not cached: involves page load + waits
result = fetcher.fetch(url, use_selenium=True)
```

## Delay Configuration Parameters

### 1. page_load_wait (default: 2.0 seconds)

**When it happens:**
- After `driver.get(url)` completes
- Before checking for content/Cloudflare

**What it's for:**
- Gives JavaScript time to render
- Lets dynamic content load
- Required for SPAs (Single Page Applications)

**When to reduce:**
- Static pages (no JavaScript)
- Content is cached
- You're only checking cache

**Example configurations:**
```python
# Cache operations only
page_load_wait=0.0        # Instant

# Simple static pages  
page_load_wait=0.5        # Half second

# Standard modern sites (default)
page_load_wait=2.0        # Two seconds

# Heavy JavaScript sites
page_load_wait=3.0        # Three seconds
```

### 2. wait_timeout (default: 10 seconds)

**When it happens:**
- When waiting for specific elements with `WebDriverWait`
- When using `wait_for_element` parameter

**What it's for:**
- Maximum time to wait for element to appear
- Prevents infinite waiting

**When to reduce:**
- Elements load quickly
- You're willing to fail fast
- Cache operations only

**Example configurations:**
```python
# Fail fast (cache operations)
wait_timeout=1            # One second max

# Quick sites
wait_timeout=5            # Five seconds

# Standard (default)
wait_timeout=10           # Ten seconds

# Slow sites
wait_timeout=20           # Twenty seconds
```

### 3. random_wait_min / random_wait_max (default: 0.0)

**When it happens:**
- Before EACH fetch request
- Only if `random_wait_max > 0`

**What it's for:**
- Mimics human browsing behavior
- Avoids rate limiting
- Prevents bot detection

**When to use:**
```python
# No delays (default)
random_wait_min=0.0, random_wait_max=0.0

# Light throttling
random_wait_min=0.5, random_wait_max=1.5

# Human-like browsing
random_wait_min=1.0, random_wait_max=3.0

# Very cautious
random_wait_min=2.0, random_wait_max=5.0
```

## Detailed Delay Breakdown

### Fetching Flow with Default Settings

```
fetch(url, use_selenium=True) called
│
├─> Cache check (0ms) [INSTANT]
│   └─> If cached: Return immediately [DONE - INSTANT]
│
├─> Random wait (0-Xms) [IF random_wait_max > 0]
│
├─> Browser initialization (if needed)
│   └─> Opens browser (~500-2000ms) [ONE-TIME COST]
│
├─> driver.get(url)
│   └─> Browser loads page (~100-5000ms) [DEPENDS ON PAGE]
│
├─> page_load_wait (2000ms by default) [CONFIGURABLE]
│   └─> Waits for JavaScript to render
│
├─> Cloudflare detection (~4000ms) [AUTOMATIC]
│   ├─> Looks for Cloudflare challenge
│   └─> Handles if present
│
├─> wait_for_element (if specified)
│   └─> Waits up to wait_timeout [CONFIGURABLE]
│
├─> Execute script (if specified)
│   └─> Small delay (~500ms) [AUTOMATIC]
│
└─> Return result
```

### Total Time Breakdown

**Best case (cached):**
- Cache check: ~1ms
- Total: **~1ms**

**Typical case (not cached, simple page):**
- Browser init (first time): ~1000ms
- Page load: ~2000ms
- page_load_wait: 2000ms
- Cloudflare check: ~4000ms
- Total: **~9000ms (9 seconds)**

**Fast configuration (not cached):**
- Browser init (first time): ~1000ms
- Page load: ~2000ms
- page_load_wait: 0ms
- Cloudflare check: 0ms (may fail on protected sites)
- Total: **~3000ms (3 seconds)**

## Configuration Recipes

### Recipe 1: Cache-Only Operations (Fastest)

```python
fetcher = SeleniumWebFetcher(
    use_selenium=True,
    page_load_wait=0.0,
    wait_timeout=1,
    random_wait_min=0.0,
    random_wait_max=0.0
)

# Instant cache operations
cache_file = fetcher.get_cache_filename(url)
has_cache = fetcher.has_cache(url)

# Fast fetching (may fail on JS-heavy sites)
result = fetcher.fetch(url, use_selenium=True)
```

**Pros:** Minimal delays, instant cache checks
**Cons:** May fail on JavaScript-heavy sites

### Recipe 2: Balanced (Default)

```python
fetcher = SeleniumWebFetcher(
    use_selenium=True,
    page_load_wait=2.0,     # Default
    wait_timeout=10,        # Default
    random_wait_min=0.0,
    random_wait_max=0.0
)
```

**Pros:** Works on most sites reliably
**Cons:** 2-4 second delay per page

### Recipe 3: Heavy JavaScript Sites

```python
fetcher = SeleniumWebFetcher(
    use_selenium=True,
    page_load_wait=3.0,     # Extra time for JS
    wait_timeout=15,        # Generous timeout
    random_wait_min=0.0,
    random_wait_max=0.0
)
```

**Pros:** Reliable on complex SPAs
**Cons:** 3-5 second delay per page

### Recipe 4: Rate-Limited Sites

```python
fetcher = SeleniumWebFetcher(
    use_selenium=True,
    page_load_wait=2.0,
    wait_timeout=10,
    random_wait_min=1.0,    # 1-3 second random delay
    random_wait_max=3.0     # between requests
)
```

**Pros:** Avoids rate limiting, mimics humans
**Cons:** 1-3 second extra delay per request

### Recipe 5: Stealth Mode (Maximum Care)

```python
fetcher = SeleniumWebFetcher(
    use_selenium=True,
    headless=False,          # Visible browser (less suspicious)
    page_load_wait=3.0,      # Plenty of time
    wait_timeout=20,         # Very patient
    random_wait_min=2.0,     # 2-5 second delays
    random_wait_max=5.0,     # between requests
    use_undetected=True      # Anti-detection driver
)
```

**Pros:** Maximum stealth, avoids detection
**Cons:** Slow (5-10 seconds per page)

## Hard-Coded Delays

Some delays are hard-coded for specific situations and cannot be configured:

### Cloudflare Detection

```python
time.sleep(4)  # Wait for Cloudflare challenge to appear
time.sleep(3)  # Wait after handling challenge
```

**Why:** Cloudflare challenges load asynchronously after the page
**Impact:** ~4-7 seconds on protected sites
**Workaround:** None - required for Cloudflare sites

### Cookie Consent Buttons

```python
time.sleep(1)  # Wait for cookie banner to appear
time.sleep(0.5)  # Wait after clicking accept
```

**Why:** Cookie banners load after page
**Impact:** ~1-2 seconds if cookie banner present
**Workaround:** Use `cookie_accept_selector` parameter

### Script Execution

```python
time.sleep(0.5)  # After executing JavaScript
```

**Why:** Let JavaScript complete
**Impact:** ~0.5 seconds per script
**Workaround:** None needed - very fast

## Performance Tips

### 1. Use Cache Aggressively

```python
# Check cache first
if fetcher.has_cache(url):
    result = fetcher.fetch(url)  # Instant from cache
else:
    result = fetcher.fetch(url, use_selenium=True)  # Slow
```

### 2. Reuse Fetcher Instance

```python
# Good: Reuse fetcher (browser stays open)
fetcher = SeleniumWebFetcher(use_selenium=True)
for url in urls:
    fetcher.fetch(url)
fetcher.close()

# Bad: Create new fetcher each time (browser reopens)
for url in urls:
    with SeleniumWebFetcher(use_selenium=True) as fetcher:
        fetcher.fetch(url)  # Browser opens/closes every time!
```

### 3. Use Requests When Possible

```python
# Mixed mode: requests by default, Selenium when needed
fetcher = SeleniumWebFetcher(use_selenium=False)

# Fast: uses requests
result = fetcher.fetch("https://simple-page.com")

# Slow: uses Selenium only when needed
result = fetcher.fetch("https://js-heavy-page.com", use_selenium=True)
```

### 4. Batch with Context Manager

```python
with SeleniumWebFetcher(use_selenium=True) as fetcher:
    for url in urls:
        result = fetcher.fetch(url)
        # Browser stays open between requests
```

## Summary

**For instant cache operations:**
- Use `page_load_wait=0.0`
- Set `wait_timeout=1`
- Cache methods are always instant

**For reliable fetching:**
- Use default settings
- Accept 2-4 second delays per page
- Configure based on site complexity

**To minimize delays:**
1. Use cache aggressively
2. Reuse fetcher instances
3. Use requests mode when possible
4. Only use Selenium when needed

**Remember:**
- Cache operations are ALWAYS instant
- Browser initialization is one-time cost
- Most delays are configurable
- Some delays (Cloudflare) are unavoidable
