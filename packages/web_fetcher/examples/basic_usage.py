"""
Basic usage examples for web_fetcher package.
"""

from web_fetcher import WebPageFetcher


def example_basic_fetch():
    """Example: Basic page fetching."""
    print("\n" + "="*60)
    print("Example 1: Basic Fetch")
    print("="*60)
    
    fetcher = WebPageFetcher(cache_dir="./cache/examples")
    
    # Fetch a page
    result = fetcher.fetch("https://example.com")
    
    print(f"URL: {result['url']}")
    print(f"Status: {result['status_code']}")
    print(f"From cache: {result['cached']}")
    print(f"Content length: {len(result['content'])} bytes")
    print(f"First 200 chars: {result['content'][:200]}")


def example_with_params():
    """Example: Fetching with query parameters."""
    print("\n" + "="*60)
    print("Example 2: Fetch with Parameters")
    print("="*60)
    
    with WebPageFetcher(cache_dir="./cache/examples") as fetcher:
        result = fetcher.fetch(
            "https://httpbin.org/get",
            params={'key': 'value', 'page': '1'}
        )
        
        print(f"Final URL: {result['url']}")
        print(f"Status: {result['status_code']}")


def example_batch_fetch():
    """Example: Fetching multiple URLs."""
    print("\n" + "="*60)
    print("Example 3: Batch Fetching")
    print("="*60)
    
    urls = [
        "https://example.com",
        "https://www.python.org",
        "https://httpbin.org/get",
    ]
    
    with WebPageFetcher(cache_dir="./cache/examples") as fetcher:
        results = fetcher.fetch_multiple(urls, delay=1.0)
        
        for url, result in results.items():
            if 'error' not in result:
                print(f"✓ {url}: {result['status_code']}")
            else:
                print(f"✗ {url}: {result['error']}")


def example_custom_headers():
    """Example: Using custom headers."""
    print("\n" + "="*60)
    print("Example 4: Custom Headers")
    print("="*60)
    
    fetcher = WebPageFetcher(
        cache_dir="./cache/examples",
        user_agent="MyCustomBot/1.0"
    )
    
    result = fetcher.fetch(
        "https://httpbin.org/headers",
        headers={'X-Custom-Header': 'CustomValue'}
    )
    
    print(f"Status: {result['status_code']}")
    print("Headers sent successfully!")


def example_cache_control():
    """Example: Cache management."""
    print("\n" + "="*60)
    print("Example 5: Cache Control")
    print("="*60)
    
    fetcher = WebPageFetcher(cache_dir="./cache/examples")
    
    # Fetch (will cache)
    result1 = fetcher.fetch("https://example.com")
    print(f"First fetch - cached: {result1['cached']}")
    
    # Fetch again (from cache)
    result2 = fetcher.fetch("https://example.com")
    print(f"Second fetch - cached: {result2['cached']}")
    
    # Clear cache and fetch
    fetcher.clear_cache(url="https://example.com")
    result3 = fetcher.fetch("https://example.com")
    print(f"After clear - cached: {result3['cached']}")


if __name__ == "__main__":
    import logging
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run examples
    try:
        example_basic_fetch()
        example_with_params()
        example_batch_fetch()
        example_custom_headers()
        example_cache_control()
        
        print("\n" + "="*60)
        print("All examples completed!")
        print("="*60)
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
