"""
Test script to compare raw Selenium vs SeleniumBase for PDF fetching.

This script tests whether SeleniumBase's anti-detection features
help bypass Cloudflare challenges.
"""

import time
import logging
from pathlib import Path
from typing import Optional

# Try to import SeleniumBase
try:
    from seleniumbase import SB
    SELENIUMBASE_AVAILABLE = True
except ImportError:
    SELENIUMBASE_AVAILABLE = False
    print("SeleniumBase not installed. Install with: pip install seleniumbase")

# Try to import raw Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Selenium not installed. Install with: pip install selenium")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_with_raw_selenium(url: str, headless: bool = True) -> dict:
    """Test with raw Selenium."""
    if not SELENIUM_AVAILABLE:
        return {"error": "Selenium not available"}
    
    result = {
        "method": "raw_selenium",
        "url": url,
        "cloudflare_detected": False,
        "page_loaded": False,
        "page_size": 0,
        "pdf_downloaded": False,
        "error": None,
        "time_taken": 0
    }
    
    driver = None
    download_dir = None
    try:
        import tempfile
        import os
        from pathlib import Path
        
        start_time = time.time()
        
        # Create temporary download directory
        download_dir = Path(tempfile.mkdtemp())
        result["download_dir"] = str(download_dir)
        
        options = Options()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Configure Chrome to download PDFs instead of viewing them
        prefs = {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
            "plugins.plugins_disabled": ["Chrome PDF Viewer"],
        }
        options.add_experimental_option("prefs", prefs)
        options.add_argument('--disable-pdf-viewer')
        
        # Use Chrome DevTools Protocol to force download behavior
        driver = webdriver.Chrome(options=options)
        
        # Enable downloads via CDP
        driver.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': str(download_dir)
        })
        
        driver.get(url)
        time.sleep(5)  # Wait for page load and potential download
        
        # Check if PDF was downloaded
        pdf_files = list(download_dir.glob('*.pdf'))
        if pdf_files:
            result["pdf_downloaded"] = True
            result["pdf_file"] = str(pdf_files[0])
            result["pdf_size"] = pdf_files[0].stat().st_size
        
        page_source = driver.page_source
        current_url = driver.current_url
        page_lower = page_source.lower()
        
        # Check if this is a PDF URL - PDFs might not have HTML content
        is_pdf_url = url.lower().endswith('.pdf') or current_url.lower().endswith('.pdf')
        
        # Check for Cloudflare
        cloudflare_indicators = [
            'i am human' in page_lower,
            'just a moment' in page_lower[:2000],
            'cf-challenge' in page_lower,
            'challenge-platform' in page_lower,
            'cf-turnstile' in page_lower,
            'checking your browser' in page_lower[:2000]
        ]
        
        result["cloudflare_detected"] = any(cloudflare_indicators)
        result["page_loaded"] = len(page_source) > 1000 or is_pdf_url or result["pdf_downloaded"]
        result["page_size"] = len(page_source)
        result["time_taken"] = time.time() - start_time
        
        # If PDF was downloaded, that's success!
        if result["pdf_downloaded"]:
            result["error"] = None
            return result
        
        # For PDF URLs, check if we got redirected or if PDF is being served
        if is_pdf_url:
            # PDF URLs might show minimal HTML or redirect
            if result["cloudflare_detected"]:
                result["error"] = "Cloudflare challenge detected"
            elif len(page_source) < 500:
                # Very small page - might be PDF download or error
                if 'pdf' in page_lower or '%pdf' in page_source[:100]:
                    result["error"] = None  # PDF might be downloading
                    result["page_loaded"] = True
                else:
                    result["error"] = "Small page - PDF not downloaded"
            else:
                result["error"] = None  # Page has content
        else:
            # Check if we got actual content (not just Cloudflare)
            if result["cloudflare_detected"]:
                result["error"] = "Cloudflare challenge detected"
            elif len(page_source) < 1000:
                result["error"] = "Page too small - likely not loaded"
            else:
                # Check for content indicators
                content_indicators = [
                    'article' in page_lower[:50000],
                    'abstract' in page_lower[:50000],
                    'pdf' in page_lower[:50000],
                    'doi' in page_lower[:50000]
                ]
                if not any(content_indicators):
                    result["error"] = "No content indicators found"
        
    except Exception as e:
        result["error"] = str(e)
    finally:
        if driver:
            driver.quit()
        # Clean up download directory
        if download_dir and download_dir.exists():
            import shutil
            try:
                shutil.rmtree(download_dir)
            except:
                pass
    
    return result


def test_with_seleniumbase(url: str, headless: bool = True, undetected: bool = True) -> dict:
    """Test with SeleniumBase."""
    if not SELENIUMBASE_AVAILABLE:
        return {"error": "SeleniumBase not available"}
    
    result = {
        "method": "seleniumbase",
        "url": url,
        "undetected_mode": undetected,
        "cloudflare_detected": False,
        "page_loaded": False,
        "page_size": 0,
        "pdf_downloaded": False,
        "error": None,
        "time_taken": 0
    }
    
    download_dir = None
    try:
        import tempfile
        from pathlib import Path
        
        start_time = time.time()
        
        # Create temporary download directory
        download_dir = Path(tempfile.mkdtemp())
        result["download_dir"] = str(download_dir)
        
        # SeleniumBase with undetected mode (anti-detection)
        # Note: SeleniumBase download configuration is different
        # We'll configure it after opening the browser
        with SB(uc=undetected, headless=headless) as sb:
            # Configure download behavior via CDP if available
            try:
                sb.execute_cdp_cmd('Page.setDownloadBehavior', {
                    'behavior': 'allow',
                    'downloadPath': str(download_dir)
                })
            except:
                pass  # CDP might not be available in all modes
            
            sb.open(url)
            sb.sleep(5)  # Wait for page load and potential download
            
            # Check if PDF was downloaded
            pdf_files = list(download_dir.glob('*.pdf'))
            if pdf_files:
                result["pdf_downloaded"] = True
                result["pdf_file"] = str(pdf_files[0])
                result["pdf_size"] = pdf_files[0].stat().st_size
            
            page_source = sb.get_page_source()
            current_url = sb.get_current_url()
            page_lower = page_source.lower()
            
            # Check if this is a PDF URL
            is_pdf_url = url.lower().endswith('.pdf') or current_url.lower().endswith('.pdf')
            
            # Check for Cloudflare
            cloudflare_indicators = [
                'i am human' in page_lower,
                'just a moment' in page_lower[:2000],
                'cf-challenge' in page_lower,
                'challenge-platform' in page_lower,
                'cf-turnstile' in page_lower,
                'checking your browser' in page_lower[:2000]
            ]
            
            result["cloudflare_detected"] = any(cloudflare_indicators)
            result["page_loaded"] = len(page_source) > 1000 or is_pdf_url or result["pdf_downloaded"]
            result["page_size"] = len(page_source)
            result["time_taken"] = time.time() - start_time
            
            # If PDF was downloaded, that's success!
            if result["pdf_downloaded"]:
                result["error"] = None
                return result
            
            # For PDF URLs, check if we got redirected or if PDF is being served
            if is_pdf_url:
                if result["cloudflare_detected"]:
                    result["error"] = "Cloudflare challenge detected"
                elif len(page_source) < 500:
                    if 'pdf' in page_lower or '%pdf' in page_source[:100]:
                        result["error"] = None
                        result["page_loaded"] = True
                    else:
                        result["error"] = "Small page - PDF not downloaded"
                else:
                    result["error"] = None
            else:
                # Check if we got actual content
                if result["cloudflare_detected"]:
                    result["error"] = "Cloudflare challenge detected"
                elif len(page_source) < 1000:
                    result["error"] = "Page too small - likely not loaded"
                else:
                    # Check for content indicators
                    content_indicators = [
                        'article' in page_lower[:50000],
                        'abstract' in page_lower[:50000],
                        'pdf' in page_lower[:50000],
                        'doi' in page_lower[:50000]
                    ]
                    if not any(content_indicators):
                        result["error"] = "No content indicators found"
        
    except Exception as e:
        result["error"] = str(e)
    finally:
        # Clean up download directory
        if download_dir and download_dir.exists():
            import shutil
            try:
                shutil.rmtree(download_dir)
            except:
                pass
    
    return result


def compare_methods(urls: list[str], headless: bool = True):
    """Compare raw Selenium vs SeleniumBase on multiple URLs."""
    print("\n" + "=" * 80)
    print("SELENIUMBASE vs RAW SELENIUM COMPARISON TEST")
    print("=" * 80)
    
    results = []
    
    for i, url in enumerate(urls, 1):
        print(f"\n{'='*80}")
        print(f"Test {i}/{len(urls)}: {url}")
        print(f"{'='*80}")
        
        # Test with raw Selenium
        print("\n[1/3] Testing with Raw Selenium...")
        raw_result = test_with_raw_selenium(url, headless=headless)
        print(f"  Cloudflare detected: {raw_result.get('cloudflare_detected', 'N/A')}")
        print(f"  Page loaded: {raw_result.get('page_loaded', 'N/A')}")
        print(f"  Page size: {raw_result.get('page_size', 0):,} bytes")
        if raw_result.get('pdf_downloaded'):
            print(f"  ✓ PDF downloaded: {raw_result.get('pdf_file', 'N/A')} ({raw_result.get('pdf_size', 0):,} bytes)")
        print(f"  Time: {raw_result.get('time_taken', 0):.2f}s")
        if raw_result.get('error'):
            print(f"  Error: {raw_result['error']}")
        
        # Test with SeleniumBase (normal mode)
        if SELENIUMBASE_AVAILABLE:
            print("\n[2/3] Testing with SeleniumBase (normal mode)...")
            sb_normal_result = test_with_seleniumbase(url, headless=headless, undetected=False)
            print(f"  Cloudflare detected: {sb_normal_result.get('cloudflare_detected', 'N/A')}")
            print(f"  Page loaded: {sb_normal_result.get('page_loaded', 'N/A')}")
            print(f"  Page size: {sb_normal_result.get('page_size', 0):,} bytes")
            if sb_normal_result.get('pdf_downloaded'):
                print(f"  ✓ PDF downloaded: {sb_normal_result.get('pdf_file', 'N/A')} ({sb_normal_result.get('pdf_size', 0):,} bytes)")
            print(f"  Time: {sb_normal_result.get('time_taken', 0):.2f}s")
            if sb_normal_result.get('error'):
                print(f"  Error: {sb_normal_result['error']}")
            
            # Test with SeleniumBase (undetected mode)
            print("\n[3/3] Testing with SeleniumBase (undetected mode)...")
            sb_undetected_result = test_with_seleniumbase(url, headless=headless, undetected=True)
            print(f"  Cloudflare detected: {sb_undetected_result.get('cloudflare_detected', 'N/A')}")
            print(f"  Page loaded: {sb_undetected_result.get('page_loaded', 'N/A')}")
            print(f"  Page size: {sb_undetected_result.get('page_size', 0):,} bytes")
            if sb_undetected_result.get('pdf_downloaded'):
                print(f"  ✓ PDF downloaded: {sb_undetected_result.get('pdf_file', 'N/A')} ({sb_undetected_result.get('pdf_size', 0):,} bytes)")
            print(f"  Time: {sb_undetected_result.get('time_taken', 0):.2f}s")
            if sb_undetected_result.get('error'):
                print(f"  Error: {sb_undetected_result['error']}")
        else:
            sb_normal_result = None
            sb_undetected_result = None
        
        results.append({
            "url": url,
            "raw_selenium": raw_result,
            "seleniumbase_normal": sb_normal_result,
            "seleniumbase_undetected": sb_undetected_result
        })
        
        # Wait between tests
        if i < len(urls):
            print(f"\nWaiting 5 seconds before next test...")
            time.sleep(5)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    for result in results:
        url = result["url"]
        raw = result["raw_selenium"]
        sb_normal = result.get("seleniumbase_normal")
        sb_undetected = result.get("seleniumbase_undetected")
        
        print(f"\nURL: {url}")
        print(f"  Raw Selenium:        Cloudflare={raw.get('cloudflare_detected')}, Success={not raw.get('error')}")
        if sb_normal:
            print(f"  SeleniumBase (norm):  Cloudflare={sb_normal.get('cloudflare_detected')}, Success={not sb_normal.get('error')}")
        if sb_undetected:
            print(f"  SeleniumBase (UC):   Cloudflare={sb_undetected.get('cloudflare_detected')}, Success={not sb_undetected.get('error')}")
    
    return results


if __name__ == "__main__":
    # Test URLs - use ones that have been problematic
    # These should be URLs that have been hitting Cloudflare challenges
    test_urls = [
        # Landing page URL (where Cloudflare challenges typically appear)
        "https://pubs.geoscienceworld.org/msa/ammin/article/96/5-6/946/3631753",
        # Direct PDF URL (for comparison)
        "https://pubs.geoscienceworld.org/msa/ammin/article-pdf/96/5-6/946/3631753/29_573WaychunasIntro.pdf",
    ]
    
    # You can also test with DOIs that resolve to Cloudflare-protected pages
    # For example, if you have a list of DOIs that failed:
    # test_urls = [
    #     "https://doi.org/10.1016/j.dam.2022.11.002",  # Example DOI
    # ]
    
    if not test_urls or test_urls == [""]:
        print("Please add test URLs to the test_urls list in the script")
        print("These should be URLs that have been hitting Cloudflare challenges")
    else:
        # Run comparison
        # Set headless=False to see what's happening in browser
        # Set headless=True for faster automated testing
        results = compare_methods(test_urls, headless=False)
        
        print("\n" + "=" * 80)
        print("RECOMMENDATION")
        print("=" * 80)
        
        # Analyze results
        raw_success = sum(1 for r in results if not r["raw_selenium"].get("cloudflare_detected") and not r["raw_selenium"].get("error"))
        sb_undetected_success = 0
        if SELENIUMBASE_AVAILABLE:
            sb_undetected_success = sum(1 for r in results if r.get("seleniumbase_undetected") and not r["seleniumbase_undetected"].get("cloudflare_detected") and not r["seleniumbase_undetected"].get("error"))
        
        print(f"\nRaw Selenium success rate: {raw_success}/{len(results)}")
        if SELENIUMBASE_AVAILABLE:
            print(f"SeleniumBase (undetected) success rate: {sb_undetected_success}/{len(results)}")
            
            if sb_undetected_success > raw_success:
                print("\n✓ SeleniumBase undetected mode shows improvement!")
                print("  Consider integrating it into pdf_fetcher_v2.py")
            elif sb_undetected_success == raw_success:
                print("\n→ SeleniumBase shows similar results to raw Selenium")
                print("  May not be worth the additional dependency")
            else:
                print("\n✗ SeleniumBase did not improve results")
                print("  Stick with raw Selenium")

