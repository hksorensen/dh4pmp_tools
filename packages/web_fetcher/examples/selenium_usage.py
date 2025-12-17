"""
Selenium usage examples for web_fetcher package.

Note: Requires selenium to be installed:
    pip install web-fetcher[selenium]
    
Also requires a browser driver (chromedriver or geckodriver) to be installed.
"""

try:
    from web_fetcher import SeleniumWebFetcher, SELENIUM_AVAILABLE
    from selenium.webdriver.common.by import By
except ImportError:
    print("Error: Selenium not available. Install with: pip install web-fetcher[selenium]")
    exit(1)


def example_selenium_basic():
    """Example: Basic Selenium fetch."""
    if not SELENIUM_AVAILABLE:
        print("Selenium not available")
        return
    
    print("\n" + "="*60)
    print("Example 1: Basic Selenium Fetch")
    print("="*60)
    
    try:
        with SeleniumWebFetcher(
            cache_dir="./cache/selenium_examples",
            use_selenium=True,
            headless=True,
        ) as fetcher:
            result = fetcher.fetch("https://example.com")
            
            print(f"Status: {result['status_code']}")
            print(f"Fetched with Selenium: {result.get('fetched_with_selenium', False)}")
            print(f"Content length: {len(result['content'])} bytes")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure chromedriver or geckodriver is installed")


def example_wait_for_element():
    """Example: Wait for specific element."""
    if not SELENIUM_AVAILABLE:
        print("Selenium not available")
        return
    
    print("\n" + "="*60)
    print("Example 2: Wait for Element")
    print("="*60)
    
    try:
        with SeleniumWebFetcher(
            cache_dir="./cache/selenium_examples",
            use_selenium=True,
            headless=True,
        ) as fetcher:
            result = fetcher.fetch(
                "https://example.com",
                wait_for_element=(By.TAG_NAME, "h1")
            )
            
            print(f"Page loaded and h1 element found")
            print(f"Content length: {len(result['content'])} bytes")
    except Exception as e:
        print(f"Error: {e}")


def example_execute_javascript():
    """Example: Execute JavaScript after page load."""
    if not SELENIUM_AVAILABLE:
        print("Selenium not available")
        return
    
    print("\n" + "="*60)
    print("Example 3: Execute JavaScript")
    print("="*60)
    
    try:
        with SeleniumWebFetcher(
            cache_dir="./cache/selenium_examples",
            use_selenium=True,
            headless=True,
        ) as fetcher:
            # Scroll to bottom
            result = fetcher.fetch(
                "https://example.com",
                execute_script="window.scrollTo(0, document.body.scrollHeight);"
            )
            
            print(f"Page loaded and JavaScript executed")
            print(f"Content length: {len(result['content'])} bytes")
    except Exception as e:
        print(f"Error: {e}")


def example_mixed_mode():
    """Example: Mixed mode - requests by default, Selenium when needed."""
    if not SELENIUM_AVAILABLE:
        print("Selenium not available")
        return
    
    print("\n" + "="*60)
    print("Example 4: Mixed Mode")
    print("="*60)
    
    try:
        with SeleniumWebFetcher(
            cache_dir="./cache/selenium_examples",
            use_selenium=False,  # Default to requests
            headless=True,
        ) as fetcher:
            # This uses requests (fast)
            result1 = fetcher.fetch("https://example.com")
            print(f"example.com - Used Selenium: {result1.get('fetched_with_selenium', False)}")
            
            # This uses Selenium (slower but handles JS)
            result2 = fetcher.fetch(
                "https://example.com",
                use_selenium=True,  # Override
            )
            print(f"example.com (forced) - Used Selenium: {result2.get('fetched_with_selenium', False)}")
    except Exception as e:
        print(f"Error: {e}")


def example_firefox():
    """Example: Using Firefox instead of Chrome."""
    if not SELENIUM_AVAILABLE:
        print("Selenium not available")
        return
    
    print("\n" + "="*60)
    print("Example 5: Using Firefox")
    print("="*60)
    
    try:
        with SeleniumWebFetcher(
            cache_dir="./cache/selenium_examples",
            use_selenium=True,
            browser='firefox',  # Use Firefox
            headless=True,
        ) as fetcher:
            result = fetcher.fetch("https://example.com")
            
            print(f"Fetched with Firefox")
            print(f"Content length: {len(result['content'])} bytes")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure geckodriver is installed for Firefox")


def example_cookie_acceptance():
    """Example: Automatically accepting cookies."""
    if not SELENIUM_AVAILABLE:
        print("Selenium not available")
        return
    
    print("\n" + "="*60)
    print("Example 6: Cookie Acceptance")
    print("="*60)
    
    try:
        with SeleniumWebFetcher(
            cache_dir="./cache/selenium_examples",
            use_selenium=True,
            headless=True,
        ) as fetcher:
            # Example: Accept cookies if present
            # Adjust the selector based on the website's cookie button
            result = fetcher.fetch(
                "https://example.com",
                cookie_accept_selector=(By.ID, "accept-cookies")  # or By.CLASS_NAME, By.XPATH, etc.
            )
            
            print(f"Page fetched with cookie handling")
            print(f"Content length: {len(result['content'])} bytes")
            print("\nNote: If cookie button was found, it was automatically clicked")
    except Exception as e:
        print(f"Error: {e}")
        print("\nNote: This example uses a placeholder selector.")
        print("Replace 'accept-cookies' with the actual selector for your target website.")


if __name__ == "__main__":
    import logging
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\nNote: These examples require:")
    print("  1. pip install web-fetcher[selenium]")
    print("  2. chromedriver or geckodriver installed")
    print("  3. Internet connection\n")
    
    if not SELENIUM_AVAILABLE:
        print("Selenium is not installed!")
        print("Install with: pip install web-fetcher[selenium]")
    else:
        # Run examples
        try:
            example_selenium_basic()
            example_wait_for_element()
            example_execute_javascript()
            example_mixed_mode()
            example_firefox()
            example_cookie_acceptance()
            
            print("\n" + "="*60)
            print("All examples completed!")
            print("="*60)
            
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
