"""Simple test of raw Selenium with PDF download configuration."""

import time
import tempfile
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Test URL
url = "https://pubs.geoscienceworld.org/msa/ammin/article-pdf/96/5-6/946/3631753/29_573WaychunasIntro.pdf"

# Create temporary download directory
download_dir = Path(tempfile.mkdtemp())
print(f"Download directory: {download_dir}")

# Configure Chrome options
options = Options()
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

# Create driver
print("\nStarting Chrome...")
driver = webdriver.Chrome(options=options)

try:
    # Enable downloads via CDP
    driver.execute_cdp_cmd('Page.setDownloadBehavior', {
        'behavior': 'allow',
        'downloadPath': str(download_dir)
    })
    
    print(f"Navigating to: {url}")
    start_time = time.time()
    driver.get(url)
    
    # Wait for download
    print("Waiting for download (max 15 seconds)...")
    pdf_downloaded = False
    for i in range(15):
        time.sleep(1)
        pdf_files = list(download_dir.glob('*.pdf'))
        if pdf_files:
            pdf_file = pdf_files[0]
            # Check if download is complete (not .crdownload)
            if not pdf_file.name.endswith('.crdownload'):
                file_size = pdf_file.stat().st_size
                print(f"\n✓ PDF downloaded successfully!")
                print(f"  File: {pdf_file.name}")
                print(f"  Size: {file_size:,} bytes")
                print(f"  Time: {time.time() - start_time:.2f}s")
                pdf_downloaded = True
                break
        print(f"  Waiting... ({i+1}/15)", end='\r')
    
    if not pdf_downloaded:
        print(f"\n✗ PDF not downloaded after 15 seconds")
        print(f"  Files in download dir: {list(download_dir.glob('*'))}")
        
        # Check page source
        page_source = driver.page_source
        print(f"  Page source length: {len(page_source)} bytes")
        print(f"  Current URL: {driver.current_url}")
        print(f"  Page title: {driver.title}")
        
        # Check for Cloudflare
        page_lower = page_source.lower()
        if 'i am human' in page_lower or 'just a moment' in page_lower[:2000]:
            print(f"  ⚠ Cloudflare challenge detected!")
        
        # Check if PDF is in page source (might be embedded)
        if '%pdf' in page_source[:500]:
            print(f"  ℹ PDF content detected in page source (might be embedded)")
    
finally:
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

