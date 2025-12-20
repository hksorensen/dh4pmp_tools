"""
Inspect what test #3 (User-Agent Rotation) actually sees.
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

# User agent from the test
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

url = "https://doi.org/10.1016/j.jcp.2019.108971"

options = Options()
# Run in non-headless so we can see what's happening
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument(f'--user-agent={USER_AGENT}')

driver = None
try:
    print(f"Loading: {url}")
    print(f"User-Agent: {USER_AGENT[:80]}...")
    print()
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    driver.get(url)
    time.sleep(5)  # Wait for page to fully load
    
    print(f"{'='*80}")
    print("PAGE INSPECTION - User-Agent Rotation Test")
    print(f"{'='*80}")
    print(f"Current URL: {driver.current_url}")
    print(f"Page Title: {driver.title}")
    print(f"Page Size: {len(driver.page_source):,} bytes")
    print()
    
    # Check for robot/CAPTCHA indicators
    page_source_lower = driver.page_source.lower()
    print("Bot Detection Indicators:")
    print(f"  'are you a robot': {'are you a robot' in page_source_lower}")
    print(f"  'i am human': {'i am human' in page_source_lower}")
    print(f"  'captcha': {'captcha' in page_source_lower}")
    print(f"  'recaptcha': {'recaptcha' in page_source_lower}")
    print(f"  'hcaptcha': {'hcaptcha' in page_source_lower}")
    print(f"  'turnstile': {'turnstile' in page_source_lower}")
    print(f"  'cloudflare': {'cloudflare' in page_source_lower}")
    print()
    
    # Show first 3000 characters
    print(f"{'='*80}")
    print("First 3000 characters of page source:")
    print(f"{'='*80}")
    print(driver.page_source[:3000])
    print()
    
    # Try to find CAPTCHA/bot detection elements
    print(f"{'='*80}")
    print("Looking for CAPTCHA/bot detection elements:")
    print(f"{'='*80}")
    try:
        # Check for common CAPTCHA iframes
        iframes = driver.find_elements("tag name", "iframe")
        print(f"Found {len(iframes)} iframes")
        for i, iframe in enumerate(iframes[:5], 1):
            try:
                src = iframe.get_attribute('src') or 'no src'
                print(f"  Iframe {i}: {src[:100]}")
            except:
                pass
        
        # Check for CAPTCHA containers
        captcha_elements = driver.find_elements("css selector", "[id*='captcha'], [class*='captcha'], [id*='robot'], [class*='robot'], [id*='challenge'], [class*='challenge']")
        print(f"Found {len(captcha_elements)} potential CAPTCHA/bot detection elements")
        for i, elem in enumerate(captcha_elements[:5], 1):
            try:
                text = elem.text[:100] if elem.text else "No text"
                print(f"  Element {i}: {elem.tag_name}, text: {text[:100]}")
            except:
                pass
    except Exception as e:
        print(f"Error finding elements: {e}")
    
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



