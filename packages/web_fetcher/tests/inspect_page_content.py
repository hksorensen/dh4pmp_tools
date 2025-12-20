"""
Quick script to inspect what's actually in the page when Cloudflare is detected.
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

def inspect_page(url: str):
    """Inspect the actual page content."""
    options = Options()
    # Run in non-headless mode so we can see what's happening
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = None
    try:
        print(f"Loading: {url}")
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(5)  # Wait for page to fully load
        
        print(f"\n{'='*80}")
        print("PAGE INSPECTION")
        print(f"{'='*80}")
        print(f"Current URL: {driver.current_url}")
        print(f"Page Title: {driver.title}")
        print(f"Page Size: {len(driver.page_source):,} bytes")
        
        # Check for Cloudflare indicators
        page_source_lower = driver.page_source.lower()
        print(f"\nCloudflare Indicators:")
        print(f"  'i am human' in page: {'i am human' in page_source_lower}")
        print(f"  'just a moment' in page: {'just a moment' in page_source_lower}")
        print(f"  'cf-challenge' in page: {'cf-challenge' in page_source_lower}")
        print(f"  'cloudflare' in page: {'cloudflare' in page_source_lower}")
        
        # Check for actual article content
        print(f"\nContent Indicators:")
        print(f"  'article' in page: {'article' in page_source_lower[:50000]}")
        print(f"  'abstract' in page: {'abstract' in page_source_lower[:50000]}")
        print(f"  'doi' in page: {'doi' in page_source_lower[:50000]}")
        print(f"  'pdf' in page: {'pdf' in page_source_lower[:50000]}")
        print(f"  'sciencedirect' in page: {'sciencedirect' in page_source_lower[:50000]}")
        
        # Show first 2000 characters of page source
        print(f"\n{'='*80}")
        print("First 2000 characters of page source:")
        print(f"{'='*80}")
        print(driver.page_source[:2000])
        
        # Show last 1000 characters
        print(f"\n{'='*80}")
        print("Last 1000 characters of page source:")
        print(f"{'='*80}")
        print(driver.page_source[-1000:])
        
        # Try to find specific elements
        print(f"\n{'='*80}")
        print("Looking for common elements:")
        print(f"{'='*80}")
        try:
            # Check for Cloudflare challenge elements
            cf_elements = driver.find_elements("css selector", "[id*='cf'], [class*='cf'], [id*='challenge'], [class*='challenge']")
            print(f"Found {len(cf_elements)} potential Cloudflare elements")
            if cf_elements:
                for i, elem in enumerate(cf_elements[:5], 1):
                    try:
                        print(f"  Element {i}: {elem.tag_name}, id={elem.get_attribute('id')}, class={elem.get_attribute('class')}")
                    except:
                        pass
        except Exception as e:
            print(f"Error finding elements: {e}")
        
        # Check for article/paper elements
        try:
            article_elements = driver.find_elements("css selector", "article, [class*='article'], [id*='article'], [class*='abstract'], [id*='abstract']")
            print(f"Found {len(article_elements)} potential article elements")
            if article_elements:
                for i, elem in enumerate(article_elements[:5], 1):
                    try:
                        text_preview = elem.text[:100] if elem.text else "No text"
                        print(f"  Element {i}: {elem.tag_name}, text preview: {text_preview[:100]}...")
                    except:
                        pass
        except Exception as e:
            print(f"Error finding article elements: {e}")
        
        print(f"\n{'='*80}")
        print("Press Enter to close browser...")
        input()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    import sys
    
    url = "https://doi.org/10.1016/j.jcp.2019.108971"
    if len(sys.argv) > 1:
        url = sys.argv[1]
    
    inspect_page(url)



