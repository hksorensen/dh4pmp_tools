"""
Example: Using SeleniumWebFetcher with minimal delays for cache operations.

Shows how to configure the fetcher to eliminate waits when you're only
working with cached data or don't need JavaScript rendering time.
"""

from web_fetcher import SeleniumWebFetcher

# ============================================================================
# Configuration 1: For cache-only operations (NO DELAYS!)
# ============================================================================

print("="*60)
print("Configuration 1: Cache-only operations (zero delays)")
print("="*60)

# Create fetcher with all waits disabled
fetcher_fast = SeleniumWebFetcher(
    use_selenium=True,      # Enable Selenium support
    headless=True,          # Run headless
    cache_dir="./cache",
    
    # ELIMINATE ALL DELAYS:
    page_load_wait=0.0,     # No wait after page load
    wait_timeout=1,         # Minimal timeout for elements
    random_wait_min=0.0,    # No random delays
    random_wait_max=0.0,    # No random delays
)

print("✓ Created fetcher with zero delays")

# Use cache operations - instant!
url = "https://example.com"
cache_file = fetcher_fast.get_cache_filename(url)
has_cache = fetcher_fast.has_cache(url)
print(f"✓ Cache check (instant): has_cache={has_cache}")

# If you fetch with this config and content is cached, it's instant
# If not cached, page loads with minimal waits (may fail on JS-heavy sites)
fetcher_fast.close()


# ============================================================================
# Configuration 2: For actual fetching with reasonable delays
# ============================================================================

print("\n" + "="*60)
print("Configuration 2: Normal fetching (with necessary delays)")
print("="*60)

# Create fetcher with reasonable delays for actual fetching
fetcher_normal = SeleniumWebFetcher(
    use_selenium=True,
    headless=True,
    cache_dir="./cache",
    
    # REASONABLE DELAYS FOR REAL FETCHING:
    page_load_wait=2.0,     # 2 seconds for JS to render
    wait_timeout=10,        # 10 seconds to wait for elements
    random_wait_min=0.0,    # Optional: avoid rate limiting
    random_wait_max=0.0,    # Set to e.g., 2.0 for random delays
)

print("✓ Created fetcher with normal delays")
print("  - page_load_wait: 2.0 seconds")
print("  - wait_timeout: 10 seconds")


# ============================================================================
# Configuration 3: For rate-limited sites (intentional delays)
# ============================================================================

print("\n" + "="*60)
print("Configuration 3: Rate-limited sites (intentional delays)")
print("="*60)

# Create fetcher with random delays to avoid detection
fetcher_stealth = SeleniumWebFetcher(
    use_selenium=True,
    headless=True,
    cache_dir="./cache",
    
    # STEALTH MODE WITH RANDOM DELAYS:
    page_load_wait=3.0,      # Extra time for complex sites
    wait_timeout=15,         # Longer timeout
    random_wait_min=1.0,     # Wait 1-3 seconds between requests
    random_wait_max=3.0,     # Mimics human behavior
)

print("✓ Created stealth fetcher")
print("  - page_load_wait: 3.0 seconds")
print("  - random delays: 1-3 seconds between requests")


# ============================================================================
# Recommendation
# ============================================================================

print("\n" + "="*60)
print("RECOMMENDATIONS")
print("="*60)
print("""
Choose configuration based on your use case:

1. CACHE OPERATIONS ONLY:
   page_load_wait=0.0, wait_timeout=1
   → Instant cache checks, minimal overhead

2. LIGHT FETCHING (simple pages):
   page_load_wait=0.5, wait_timeout=5
   → Quick fetching for pages without heavy JS

3. STANDARD FETCHING (most sites):
   page_load_wait=2.0, wait_timeout=10 (DEFAULT)
   → Reliable fetching for typical modern sites

4. HEAVY JS SITES (SPAs, complex apps):
   page_load_wait=3.0, wait_timeout=15
   → Ensures all dynamic content loads

5. RATE-LIMITED SITES (avoid bans):
   page_load_wait=2.0, random_wait_max=3.0
   → Mimics human browsing patterns

CACHE OPERATIONS NEVER NEED DELAYS:
- get_cache_filename()
- has_cache()
- clear_cache()
- _get_cache_key()
- _get_cache_path()

These work instantly regardless of your configuration!
""")

# Cleanup
fetcher_normal.close()
fetcher_stealth.close()
