"""
Example: Using SeleniumWebFetcher utility methods without opening browser.

The fetcher now uses lazy initialization - the browser only opens when you
actually fetch a page with Selenium. Utility methods like get_cache_filename
work immediately without browser overhead.
"""

from web_fetcher import SeleniumWebFetcher

# Create fetcher with Selenium support enabled
# Browser will NOT open yet!
fetcher = SeleniumWebFetcher(
    use_selenium=True,  # Enable Selenium
    headless=True,
    cache_dir="./cache"
)

print("✓ Fetcher created (no browser opened)")

# Use utility methods - no browser needed
url = "https://example.com"

# Check if URL is cached
cache_file = fetcher.get_cache_filename(url)
if cache_file:
    print(f"✓ Found cached file: {cache_file}")
else:
    print("✗ No cache file found")

# Get cache key
cache_key = fetcher._get_cache_key(url)
print(f"✓ Cache key: {cache_key}")

# Get cache path
cache_path = fetcher._get_cache_path(cache_key)
print(f"✓ Cache path: {cache_path}")

# Check if cache exists
has_cache = fetcher.has_cache(url)
print(f"✓ Has cache: {has_cache}")

print("\n" + "="*50)
print("All utility methods work without opening browser!")
print("="*50)

# Only when you actually fetch, the browser opens
print("\nNow if we fetch, browser will open...")
# response = fetcher.fetch(url, use_selenium=True)
# print(f"✓ Fetched: {response['url']}")

# Close when done (if browser was opened)
if fetcher.driver:
    fetcher.close()
    print("✓ Browser closed")
