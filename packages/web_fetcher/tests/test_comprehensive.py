"""Comprehensive test of PDF fetching with delays between calls."""

import time
import tempfile
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Test URLs
LANDING_PAGE = "https://pubs.geoscienceworld.org/msa/ammin/article/96/5-6/946/3631753"
DIRECT_PDF = "https://pubs.geoscienceworld.org/msa/ammin/article-pdf/96/5-6/946/3631753/29_573WaychunasIntro.pdf"

DELAY_BETWEEN_TESTS = 3  # seconds

def create_driver(download_dir: Path, headless: bool = False):
    """Create a Chrome driver with PDF download configuration."""
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
    
    driver = webdriver.Chrome(options=options)
    
    # Enable downloads via CDP
    driver.execute_cdp_cmd('Page.setDownloadBehavior', {
        'behavior': 'allow',
        'downloadPath': str(download_dir)
    })
    
    return driver

def check_cloudflare(driver) -> bool:
    """Check if current page is a Cloudflare challenge."""
    try:
        page_source = driver.page_source.lower()
        title = driver.title.lower()
        
        indicators = [
            'i am human' in page_source,
            'just a moment' in title or 'just a moment' in page_source[:2000],
            'cf-challenge' in page_source,
            'challenge-platform' in page_source,
            'cf-turnstile' in page_source,
            'checking your browser' in page_source[:2000]
        ]
        return any(indicators)
    except:
        return False

def wait_for_download(download_dir: Path, timeout: int = 15) -> tuple[bool, Path | None, int]:
    """Wait for PDF download to complete."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        pdf_files = list(download_dir.glob('*.pdf'))
        crdownload_files = list(download_dir.glob('*.crdownload'))
        
        # Check for completed PDF (not .crdownload)
        completed_pdfs = [f for f in pdf_files if not f.name.endswith('.crdownload')]
        if completed_pdfs:
            pdf_file = completed_pdfs[0]
            file_size = pdf_file.stat().st_size
            # Wait a bit more to ensure download is complete
            time.sleep(1)
            new_size = pdf_file.stat().st_size
            if new_size == file_size:  # Size stable = download complete
                return True, pdf_file, file_size
        
        time.sleep(0.5)
    
    return False, None, 0

def test_direct_pdf_download(driver, download_dir: Path, test_num: int) -> dict:
    """Test 1: Direct PDF URL download."""
    print(f"\n{'='*80}")
    print(f"TEST {test_num}: Direct PDF URL Download")
    print(f"{'='*80}")
    print(f"URL: {DIRECT_PDF}")
    
    result = {
        "test": "direct_pdf",
        "success": False,
        "cloudflare": False,
        "pdf_downloaded": False,
        "pdf_size": 0,
        "time_taken": 0,
        "error": None
    }
    
    try:
        start_time = time.time()
        
        # Clear any existing PDFs
        for f in download_dir.glob('*.pdf'):
            f.unlink()
        
        print("Navigating to PDF URL...")
        driver.get(DIRECT_PDF)
        time.sleep(2)
        
        # Check for Cloudflare
        if check_cloudflare(driver):
            result["cloudflare"] = True
            result["error"] = "Cloudflare challenge detected"
            print("  ✗ Cloudflare challenge detected")
            return result
        
        # Wait for download
        print("Waiting for PDF download...")
        downloaded, pdf_file, file_size = wait_for_download(download_dir, timeout=15)
        
        result["time_taken"] = time.time() - start_time
        
        if downloaded:
            result["success"] = True
            result["pdf_downloaded"] = True
            result["pdf_size"] = file_size
            print(f"  ✓ PDF downloaded successfully!")
            print(f"    File: {pdf_file.name}")
            print(f"    Size: {file_size:,} bytes")
            print(f"    Time: {result['time_taken']:.2f}s")
        else:
            result["error"] = "PDF not downloaded within timeout"
            print(f"  ✗ PDF not downloaded")
            print(f"    Current URL: {driver.current_url}")
            print(f"    Page title: {driver.title[:100]}")
    
    except Exception as e:
        result["error"] = str(e)
        print(f"  ✗ Error: {e}")
    
    return result

def test_landing_page_navigation(driver, download_dir: Path, test_num: int) -> dict:
    """Test 2: Navigate to landing page and find PDF link."""
    print(f"\n{'='*80}")
    print(f"TEST {test_num}: Landing Page Navigation")
    print(f"{'='*80}")
    print(f"URL: {LANDING_PAGE}")
    
    result = {
        "test": "landing_page",
        "success": False,
        "cloudflare": False,
        "pdf_link_found": False,
        "pdf_downloaded": False,
        "pdf_size": 0,
        "time_taken": 0,
        "error": None
    }
    
    try:
        start_time = time.time()
        
        # Clear any existing PDFs
        for f in download_dir.glob('*.pdf'):
            f.unlink()
        
        print("Navigating to landing page...")
        driver.get(LANDING_PAGE)
        time.sleep(3)  # Wait for page load
        
        # Check for Cloudflare
        if check_cloudflare(driver):
            result["cloudflare"] = True
            result["error"] = "Cloudflare challenge detected on landing page"
            print("  ✗ Cloudflare challenge detected")
            print("    This is expected - we skip these in production")
            return result
        
        print("  ✓ Landing page loaded")
        print(f"    Page title: {driver.title[:100]}")
        print(f"    Page size: {len(driver.page_source):,} bytes")
        
        # Look for PDF link/button
        print("Searching for PDF link...")
        pdf_url = None
        
        # Try various selectors
        selectors = [
            ("a[href*='.pdf']", "PDF link"),
            ("a[href*='article-pdf']", "Article PDF link"),
            ("button[onclick*='pdf']", "PDF button"),
            ("a:contains('PDF')", "Link with PDF text"),
        ]
        
        for selector, desc in selectors:
            try:
                if ':contains' in selector:
                    # XPath for text contains
                    elements = driver.find_elements(By.XPATH, "//a[contains(text(), 'PDF') or contains(text(), 'Download')]")
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for elem in elements:
                    try:
                        href = elem.get_attribute('href')
                        if href and ('.pdf' in href.lower() or 'article-pdf' in href.lower()):
                            pdf_url = href
                            result["pdf_link_found"] = True
                            print(f"  ✓ Found PDF link: {href[:100]}")
                            break
                    except:
                        continue
                
                if pdf_url:
                    break
            except:
                continue
        
        if not pdf_url:
            # Try searching page source
            page_source = driver.page_source
            import re
            pdf_patterns = [
                r'href=["\']([^"\']*article-pdf[^"\']*)["\']',
                r'href=["\']([^"\']*\.pdf[^"\']*)["\']',
            ]
            for pattern in pdf_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                if matches:
                    pdf_url = matches[0]
                    if not pdf_url.startswith('http'):
                        # Make absolute URL
                        from urllib.parse import urljoin
                        pdf_url = urljoin(LANDING_PAGE, pdf_url)
                    result["pdf_link_found"] = True
                    print(f"  ✓ Found PDF URL in page source: {pdf_url[:100]}")
                    break
        
        if not pdf_url:
            result["error"] = "Could not find PDF link on landing page"
            print("  ✗ Could not find PDF link")
            return result
        
        # Navigate to PDF URL
        print(f"Navigating to PDF URL...")
        driver.get(pdf_url)
        time.sleep(2)
        
        # Check for Cloudflare again
        if check_cloudflare(driver):
            result["cloudflare"] = True
            result["error"] = "Cloudflare challenge detected on PDF URL"
            print("  ✗ Cloudflare challenge detected on PDF URL")
            return result
        
        # Wait for download
        print("Waiting for PDF download...")
        downloaded, pdf_file, file_size = wait_for_download(download_dir, timeout=15)
        
        result["time_taken"] = time.time() - start_time
        
        if downloaded:
            result["success"] = True
            result["pdf_downloaded"] = True
            result["pdf_size"] = file_size
            print(f"  ✓ PDF downloaded successfully!")
            print(f"    File: {pdf_file.name}")
            print(f"    Size: {file_size:,} bytes")
            print(f"    Time: {result['time_taken']:.2f}s")
        else:
            result["error"] = "PDF not downloaded within timeout"
            print(f"  ✗ PDF not downloaded")
    
    except Exception as e:
        result["error"] = str(e)
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    return result

def main():
    """Run comprehensive tests."""
    print("="*80)
    print("COMPREHENSIVE PDF FETCHING TEST")
    print("="*80)
    print(f"Delay between tests: {DELAY_BETWEEN_TESTS} seconds")
    
    # Create download directory
    download_dir = Path(tempfile.mkdtemp())
    print(f"\nDownload directory: {download_dir}")
    
    driver = None
    results = []
    
    try:
        # Create driver (non-headless so we can see what's happening)
        print("\nInitializing Chrome driver...")
        driver = create_driver(download_dir, headless=False)
        print("  ✓ Driver initialized")
        
        # Test 1: Direct PDF download (first attempt)
        result1 = test_direct_pdf_download(driver, download_dir, 1)
        results.append(result1)
        
        if DELAY_BETWEEN_TESTS > 0:
            print(f"\nWaiting {DELAY_BETWEEN_TESTS} seconds before next test...")
            time.sleep(DELAY_BETWEEN_TESTS)
        
        # Test 2: Direct PDF download (second attempt - test consistency)
        result2 = test_direct_pdf_download(driver, download_dir, 2)
        results.append(result2)
        
        if DELAY_BETWEEN_TESTS > 0:
            print(f"\nWaiting {DELAY_BETWEEN_TESTS} seconds before next test...")
            time.sleep(DELAY_BETWEEN_TESTS)
        
        # Test 3: Direct PDF download (third attempt - test rate limiting)
        result3 = test_direct_pdf_download(driver, download_dir, 3)
        results.append(result3)
        
        if DELAY_BETWEEN_TESTS > 0:
            print(f"\nWaiting {DELAY_BETWEEN_TESTS} seconds before next test...")
            time.sleep(DELAY_BETWEEN_TESTS)
        
        # Test 4: Landing page navigation
        result4 = test_landing_page_navigation(driver, download_dir, 4)
        results.append(result4)
        
        # Summary
        print(f"\n{'='*80}")
        print("TEST SUMMARY")
        print(f"{'='*80}")
        
        for i, result in enumerate(results, 1):
            status = "✓ PASS" if result["success"] else "✗ FAIL"
            print(f"\nTest {i} ({result['test']}): {status}")
            if result["cloudflare"]:
                print(f"  Cloudflare detected: Yes")
            if result["pdf_downloaded"]:
                print(f"  PDF downloaded: Yes ({result['pdf_size']:,} bytes)")
            if result.get("pdf_link_found"):
                print(f"  PDF link found: Yes")
            if result["error"]:
                print(f"  Error: {result['error']}")
            print(f"  Time: {result['time_taken']:.2f}s")
        
        # Overall stats
        successful = sum(1 for r in results if r["success"])
        cloudflare_hits = sum(1 for r in results if r["cloudflare"])
        
        print(f"\n{'='*80}")
        print(f"Overall: {successful}/{len(results)} tests passed")
        print(f"Cloudflare hits: {cloudflare_hits}/{len(results)}")
        print(f"{'='*80}")
        
    finally:
        if driver:
            print("\nClosing browser...")
            driver.quit()
        
        # Clean up
        if download_dir.exists():
            import shutil
            try:
                shutil.rmtree(download_dir)
                print("Cleaned up download directory")
            except:
                print(f"Could not clean up {download_dir}")

if __name__ == "__main__":
    main()

