"""
Test Cloudflare circumvention strategies:
1. Undetected ChromeDriver
2. User-Agent Rotation
3. Session Persistence

Tests landing pages that typically hit Cloudflare challenges.
"""

import time
import tempfile
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Test URLs that typically hit Cloudflare
# Default: Test only the specified DOI
TEST_URLS = [
    {
        "name": "Elsevier/ScienceDirect DOI (10.1016/j.jcp.2019.108971)",
        "url": "https://doi.org/10.1016/j.jcp.2019.108971",
        "expected_cloudflare": False  # ScienceDirect usually works
    },
]

# Uncomment to test additional URLs:
# TEST_URLS.extend([
#     {
#         "name": "GeoScienceWorld Landing Page",
#         "url": "https://pubs.geoscienceworld.org/msa/ammin/article/96/5-6/946/3631753",
#         "expected_cloudflare": True
#     },
#     {
#         "name": "GeoScienceWorld Direct PDF",
#         "url": "https://pubs.geoscienceworld.org/msa/ammin/article-pdf/96/5-6/946/3631753/29_573WaychunasIntro.pdf",
#         "expected_cloudflare": False  # Direct PDFs usually work
#     },
# ])

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


def check_cloudflare(driver) -> bool:
    """Check if current page is a Cloudflare challenge."""
    try:
        page_source = driver.page_source.lower()
        title = driver.title.lower()
        page_size = len(page_source)
        
        # Primary indicators (definitive Cloudflare challenge)
        primary_indicators = [
            'i am human' in page_source,
            'just a moment' in title,
            'are you a robot' in page_source,  # Cloudflare Turnstile challenge
            'cf-challenge' in page_source,
            'cf-turnstile' in page_source,
            'turnstile' in page_source,  # Cloudflare Turnstile
            'checking your browser' in page_source[:2000],
        ]
        
        # Secondary indicators (may appear in normal pages too, need context)
        secondary_indicators = [
            'challenge-platform' in page_source,
            'cf-browser-verification' in page_source,
        ]
        
        # If we have primary indicators, it's definitely Cloudflare
        if any(primary_indicators):
            return True
        
        # For secondary indicators, require small page size (< 100KB) or specific title
        # Challenge pages are typically small, while real article pages are large (MB)
        if any(secondary_indicators):
            # Challenge pages are usually < 100KB, real pages are much larger
            if page_size < 100000 or 'just a moment' in title or 'checking' in title:
                return True
        
        return False
    except:
        return False


def test_strategy_1_standard_selenium(url: str, headless: bool = False) -> Dict:
    """Test 1: Standard Selenium (baseline)."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    
    result = {
        "strategy": "standard_selenium",
        "url": url,
        "cloudflare_detected": False,
        "page_loaded": False,
        "page_size": 0,
        "time_taken": 0,
        "error": None,
        "success": False
    }
    
    driver = None
    try:
        start_time = time.time()
        
        options = Options()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)  # 30 second timeout
        driver.get(url)
        time.sleep(3)  # Wait for page to fully load
        
        result["cloudflare_detected"] = check_cloudflare(driver)
        result["page_loaded"] = len(driver.page_source) > 1000
        result["page_size"] = len(driver.page_source)
        result["time_taken"] = time.time() - start_time
        result["current_url"] = driver.current_url
        result["page_title"] = driver.title[:100] if driver.title else ""
        
        # Check for actual content indicators
        page_lower = driver.page_source.lower()
        has_content = any([
            'article' in page_lower[:50000],
            'abstract' in page_lower[:50000],
            'doi' in page_lower[:50000],
            'pdf' in page_lower[:50000],
            'download' in page_lower[:50000]
        ])
        result["has_content_indicators"] = has_content
        
        if result["cloudflare_detected"]:
            result["error"] = "Cloudflare challenge detected"
        elif not result["page_loaded"]:
            if result["page_size"] < 500:
                result["error"] = f"Page too small ({result['page_size']} bytes) - likely error page"
            else:
                result["error"] = "Page did not load properly"
        elif not has_content:
            result["error"] = "Page loaded but no content indicators found"
        else:
            result["success"] = True
    
    except Exception as e:
        result["error"] = str(e)
    finally:
        if driver:
            driver.quit()
    
    return result


def test_strategy_2_undetected_chromedriver(url: str, headless: bool = False) -> Dict:
    """Test 2: Undetected ChromeDriver."""
    try:
        import undetected_chromedriver as uc
    except ImportError:
        return {
            "strategy": "undetected_chromedriver",
            "url": url,
            "error": "undetected-chromedriver not installed (pip install undetected-chromedriver)"
        }
    
    result = {
        "strategy": "undetected_chromedriver",
        "url": url,
        "cloudflare_detected": False,
        "page_loaded": False,
        "page_size": 0,
        "time_taken": 0,
        "error": None,
        "success": False
    }
    
    driver = None
    try:
        start_time = time.time()
        
        options = uc.ChromeOptions()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = uc.Chrome(options=options, version_main=None)
        driver.set_page_load_timeout(30)  # 30 second timeout
        driver.get(url)
        time.sleep(3)
        
        result["cloudflare_detected"] = check_cloudflare(driver)
        result["page_loaded"] = len(driver.page_source) > 1000
        result["page_size"] = len(driver.page_source)
        result["time_taken"] = time.time() - start_time
        result["current_url"] = driver.current_url
        result["page_title"] = driver.title[:100] if driver.title else ""
        
        # Check for actual content indicators
        page_lower = driver.page_source.lower()
        has_content = any([
            'article' in page_lower[:50000],
            'abstract' in page_lower[:50000],
            'doi' in page_lower[:50000],
            'pdf' in page_lower[:50000],
            'download' in page_lower[:50000]
        ])
        result["has_content_indicators"] = has_content
        
        if result["cloudflare_detected"]:
            result["error"] = "Cloudflare challenge detected"
        elif not result["page_loaded"]:
            if result["page_size"] < 500:
                result["error"] = f"Page too small ({result['page_size']} bytes) - likely error page"
            else:
                result["error"] = "Page did not load properly"
        elif not has_content:
            result["error"] = "Page loaded but no content indicators found"
        else:
            result["success"] = True
    
    except Exception as e:
        result["error"] = str(e)
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return result


def test_strategy_3_user_agent_rotation(url: str, user_agent: str, headless: bool = False) -> Dict:
    """Test 3: User-Agent Rotation."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    
    result = {
        "strategy": "user_agent_rotation",
        "url": url,
        "user_agent": user_agent[:50] + "...",
        "cloudflare_detected": False,
        "page_loaded": False,
        "page_size": 0,
        "time_taken": 0,
        "error": None,
        "success": False
    }
    
    driver = None
    try:
        start_time = time.time()
        
        options = Options()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(f'--user-agent={user_agent}')
        
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)  # 30 second timeout
        driver.get(url)
        time.sleep(3)  # Wait for page to fully load
        
        result["cloudflare_detected"] = check_cloudflare(driver)
        result["page_loaded"] = len(driver.page_source) > 1000
        result["page_size"] = len(driver.page_source)
        result["time_taken"] = time.time() - start_time
        result["current_url"] = driver.current_url
        result["page_title"] = driver.title[:100] if driver.title else ""
        
        # Check for actual content indicators
        page_lower = driver.page_source.lower()
        has_content = any([
            'article' in page_lower[:50000],
            'abstract' in page_lower[:50000],
            'doi' in page_lower[:50000],
            'pdf' in page_lower[:50000],
            'download' in page_lower[:50000]
        ])
        result["has_content_indicators"] = has_content
        
        if result["cloudflare_detected"]:
            result["error"] = "Cloudflare challenge detected"
        elif not result["page_loaded"]:
            if result["page_size"] < 500:
                result["error"] = f"Page too small ({result['page_size']} bytes) - likely error page"
            else:
                result["error"] = "Page did not load properly"
        elif not has_content:
            result["error"] = "Page loaded but no content indicators found"
        else:
            result["success"] = True
    
    except Exception as e:
        result["error"] = str(e)
    finally:
        if driver:
            driver.quit()
    
    return result


def test_strategy_4_session_persistence(urls: List[str], headless: bool = False) -> Dict:
    """Test 4: Session Persistence (reuse same driver for multiple URLs)."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    
    result = {
        "strategy": "session_persistence",
        "urls": urls,
        "results": [],
        "cloudflare_count": 0,
        "success_count": 0,
        "total_time": 0
    }
    
    driver = None
    try:
        start_time = time.time()
        
        options = Options()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)  # 30 second timeout
        
        for i, url in enumerate(urls, 1):
            url_result = {
                "url": url,
                "attempt": i,
                "cloudflare_detected": False,
                "page_loaded": False,
                "page_size": 0,
                "time_taken": 0
            }
            
            try:
                url_start = time.time()
                driver.get(url)
                time.sleep(2)  # Shorter wait for subsequent requests
                
                url_result["cloudflare_detected"] = check_cloudflare(driver)
                url_result["page_loaded"] = len(driver.page_source) > 1000
                url_result["page_size"] = len(driver.page_source)
                url_result["time_taken"] = time.time() - url_start
                
                if url_result["cloudflare_detected"]:
                    result["cloudflare_count"] += 1
                elif url_result["page_loaded"]:
                    result["success_count"] += 1
                
            except Exception as e:
                url_result["error"] = str(e)
            
            result["results"].append(url_result)
            
            # Small delay between requests in same session
            if i < len(urls):
                time.sleep(1)
        
        result["total_time"] = time.time() - start_time
    
    except Exception as e:
        result["error"] = str(e)
    finally:
        if driver:
            driver.quit()
    
    return result


def test_strategy_5_combined(url: str, user_agent: str, headless: bool = False) -> Dict:
    """Test 5: Combined - Undetected ChromeDriver + User-Agent."""
    try:
        import undetected_chromedriver as uc
    except ImportError:
        return {
            "strategy": "combined",
            "url": url,
            "error": "undetected-chromedriver not installed"
        }
    
    result = {
        "strategy": "combined_undetected_ua",
        "url": url,
        "user_agent": user_agent[:50] + "...",
        "cloudflare_detected": False,
        "page_loaded": False,
        "page_size": 0,
        "time_taken": 0,
        "error": None,
        "success": False
    }
    
    driver = None
    try:
        start_time = time.time()
        
        options = uc.ChromeOptions()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'--user-agent={user_agent}')
        
        driver = uc.Chrome(options=options, version_main=None)
        driver.set_page_load_timeout(30)  # 30 second timeout
        driver.get(url)
        time.sleep(3)
        
        result["cloudflare_detected"] = check_cloudflare(driver)
        result["page_loaded"] = len(driver.page_source) > 1000
        result["page_size"] = len(driver.page_source)
        result["time_taken"] = time.time() - start_time
        result["current_url"] = driver.current_url
        result["page_title"] = driver.title[:100] if driver.title else ""
        
        # Check for actual content indicators
        page_lower = driver.page_source.lower()
        has_content = any([
            'article' in page_lower[:50000],
            'abstract' in page_lower[:50000],
            'doi' in page_lower[:50000],
            'pdf' in page_lower[:50000],
            'download' in page_lower[:50000]
        ])
        result["has_content_indicators"] = has_content
        
        if result["cloudflare_detected"]:
            result["error"] = "Cloudflare challenge detected"
        elif not result["page_loaded"]:
            if result["page_size"] < 500:
                result["error"] = f"Page too small ({result['page_size']} bytes) - likely error page"
            else:
                result["error"] = "Page did not load properly"
        elif not has_content:
            result["error"] = "Page loaded but no content indicators found"
        else:
            result["success"] = True
    
    except Exception as e:
        result["error"] = str(e)
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return result


def run_comparison_tests(test_urls: List[Dict], headless: bool = False):
    """Run all strategies and compare results."""
    print("="*80)
    print("CLOUDFLARE CIRCUMVENTION STRATEGY COMPARISON")
    print("="*80)
    print(f"Testing {len(test_urls)} URLs")
    print(f"Headless mode: {headless}")
    print()
    
    all_results = []
    
    for test_case in test_urls:
        url = test_case["url"]
        name = test_case["name"]
        expected_cf = test_case.get("expected_cloudflare", False)
        
        print(f"\n{'='*80}")
        print(f"Testing: {name}")
        print(f"URL: {url}")
        print(f"Expected Cloudflare: {expected_cf}")
        print(f"{'='*80}")
        
        # Extract DOI from URL for display
        doi_display = url
        if 'doi.org/' in url:
            doi_display = url.split('doi.org/')[-1]
        elif url.startswith('10.'):
            doi_display = url
        
        # Test 1: Standard Selenium (baseline)
        print(f"\n[1/5] Standard Selenium (baseline) - {doi_display}")
        print(f"  → Testing Standard Selenium on {doi_display}...")
        result1 = test_strategy_1_standard_selenium(url, headless=headless)
        all_results.append(result1)
        print(f"  Cloudflare: {result1.get('cloudflare_detected', 'N/A')}")
        print(f"  Page loaded: {result1.get('page_loaded', 'N/A')}")
        print(f"  Page size: {result1.get('page_size', 0):,} bytes")
        print(f"  Has content: {result1.get('has_content_indicators', 'N/A')}")
        print(f"  Time: {result1.get('time_taken', 0):.2f}s")
        if result1.get('success'):
            print(f"  ✓ Success!")
        if result1.get('error'):
            print(f"  Error: {result1['error']}")
        
        time.sleep(2)  # Delay between tests
        
        # Test 2: Undetected ChromeDriver
        print(f"\n[2/5] Undetected ChromeDriver - {doi_display}")
        print(f"  → Testing Undetected ChromeDriver on {doi_display}...")
        result2 = test_strategy_2_undetected_chromedriver(url, headless=headless)
        all_results.append(result2)
        print(f"  Cloudflare: {result2.get('cloudflare_detected', 'N/A')}")
        print(f"  Page loaded: {result2.get('page_loaded', 'N/A')}")
        print(f"  Page size: {result2.get('page_size', 0):,} bytes")
        print(f"  Has content: {result2.get('has_content_indicators', 'N/A')}")
        print(f"  Time: {result2.get('time_taken', 0):.2f}s")
        if result2.get('success'):
            print(f"  ✓ Success!")
        if result2.get('error'):
            print(f"  Error: {result2['error']}")
        
        time.sleep(2)
        
        # Test 3: User-Agent Rotation (test with first user agent)
        print(f"\n[3/5] User-Agent Rotation (Chrome macOS) - {doi_display}")
        print(f"  → Testing User-Agent Rotation on {doi_display}...")
        result3 = test_strategy_3_user_agent_rotation(url, USER_AGENTS[0], headless=headless)
        all_results.append(result3)
        print(f"  Cloudflare: {result3.get('cloudflare_detected', 'N/A')}")
        print(f"  Page loaded: {result3.get('page_loaded', 'N/A')}")
        print(f"  Page size: {result3.get('page_size', 0):,} bytes")
        print(f"  Has content: {result3.get('has_content_indicators', 'N/A')}")
        print(f"  Time: {result3.get('time_taken', 0):.2f}s")
        if result3.get('success'):
            print(f"  ✓ Success!")
        if result3.get('error'):
            print(f"  Error: {result3['error']}")
        
        time.sleep(2)
        
        # Test 4: Session Persistence (skip if only one URL - needs multiple URLs to test persistence)
        if len(test_urls) > 1:
            print(f"\n[4/5] Session Persistence (reusing driver) - {doi_display}")
            print(f"  → Testing Session Persistence on {doi_display}...")
            urls_to_test = [tc["url"] for tc in test_urls[:3]]  # Test first 3 URLs
            result4 = test_strategy_4_session_persistence(urls_to_test, headless=headless)
            all_results.append(result4)
            print(f"  URLs tested: {len(result4.get('results', []))}")
            print(f"  Cloudflare hits: {result4.get('cloudflare_count', 0)}")
            print(f"  Successes: {result4.get('success_count', 0)}")
            print(f"  Total time: {result4.get('total_time', 0):.2f}s")
            if result4.get('error'):
                print(f"  Error: {result4['error']}")
        else:
            print("\n[4/5] Session Persistence (skipped - needs multiple URLs)")
        
        time.sleep(2)
        
        # Test 5: Combined (Undetected + User-Agent)
        print(f"\n[5/5] Combined (Undetected ChromeDriver + User-Agent) - {doi_display}")
        print(f"  → Testing Combined strategy on {doi_display}...")
        result5 = test_strategy_5_combined(url, USER_AGENTS[0], headless=headless)
        all_results.append(result5)
        print(f"  Cloudflare: {result5.get('cloudflare_detected', 'N/A')}")
        print(f"  Page loaded: {result5.get('page_loaded', 'N/A')}")
        print(f"  Page size: {result5.get('page_size', 0):,} bytes")
        print(f"  Has content: {result5.get('has_content_indicators', 'N/A')}")
        print(f"  Time: {result5.get('time_taken', 0):.2f}s")
        if result5.get('success'):
            print(f"  ✓ Success!")
        if result5.get('error'):
            print(f"  Error: {result5['error']}")
        
        print(f"\nWaiting 5 seconds before next URL...")
        time.sleep(5)
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    strategies = {}
    for result in all_results:
        strategy = result.get('strategy', 'unknown')
        if strategy not in strategies:
            strategies[strategy] = {
                'total': 0,
                'cloudflare_hits': 0,
                'successes': 0,
                'errors': 0
            }
        
        strategies[strategy]['total'] += 1
        if result.get('cloudflare_detected'):
            strategies[strategy]['cloudflare_hits'] += 1
        elif result.get('success') or (result.get('page_loaded') and result.get('has_content_indicators')):
            strategies[strategy]['successes'] += 1
        elif result.get('error'):
            strategies[strategy]['errors'] += 1
    
    for strategy, stats in strategies.items():
        print(f"\n{strategy}:")
        print(f"  Total tests: {stats['total']}")
        print(f"  Cloudflare hits: {stats['cloudflare_hits']}")
        print(f"  Successes: {stats['successes']}")
        print(f"  Errors: {stats['errors']}")
        if stats['total'] > 0:
            success_rate = (stats['successes'] / stats['total']) * 100
            cf_rate = (stats['cloudflare_hits'] / stats['total']) * 100
            print(f"  Success rate: {success_rate:.1f}%")
            print(f"  Cloudflare rate: {cf_rate:.1f}%")
    
    # Save results to JSON
    results_file = Path("cloudflare_strategy_test_results.json")
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "test_urls": test_urls,
            "results": all_results,
            "summary": strategies
        }, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"Results saved to: {results_file}")
    print(f"{'='*80}")
    
    return all_results, strategies


if __name__ == "__main__":
    import sys
    
    # Check if undetected-chromedriver is available
    try:
        import undetected_chromedriver
        print("✓ undetected-chromedriver is available")
    except ImportError:
        print("⚠ undetected-chromedriver not installed")
        print("  Install with: pip install undetected-chromedriver")
        print("  Some tests will be skipped")
    
    print()
    
    # Allow testing a single URL via command line argument
    test_urls = TEST_URLS
    if len(sys.argv) > 1 and sys.argv[1] not in ['--headless']:
        # If first arg is a URL or DOI, use it
        url_arg = sys.argv[1]
        if url_arg.startswith('http') or url_arg.startswith('10.'):
            if url_arg.startswith('10.'):
                url_arg = f"https://doi.org/{url_arg}"
            test_urls = [{
                "name": f"Custom URL: {url_arg}",
                "url": url_arg,
                "expected_cloudflare": False
            }]
            print(f"Testing single URL: {url_arg}")
            print()
    
    # Run tests
    headless = '--headless' in sys.argv
    print(f"Testing {len(test_urls)} URL(s) with 5 strategies each = {len(test_urls) * 5} browser instances")
    print(f"Estimated time: ~{len(test_urls) * 5 * 5} seconds (5s per test)")
    print()
    results, summary = run_comparison_tests(test_urls, headless=headless)
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    # Analyze and recommend
    best_strategy = None
    best_success_rate = 0
    
    for strategy, stats in summary.items():
        if stats['total'] > 0:
            success_rate = (stats['successes'] / stats['total']) * 100
            if success_rate > best_success_rate:
                best_success_rate = success_rate
                best_strategy = strategy
    
    if best_strategy:
        print(f"\n✓ Best performing strategy: {best_strategy} ({best_success_rate:.1f}% success rate)")
    else:
        print("\n⚠ No strategy showed clear advantage")
    
    print("\nConsiderations:")
    print("  - Undetected ChromeDriver: May help but adds dependency")
    print("  - User-Agent Rotation: Easy to implement, may help slightly")
    print("  - Session Persistence: Can help for same-domain requests")
    print("  - Combined strategies: May provide best results")

