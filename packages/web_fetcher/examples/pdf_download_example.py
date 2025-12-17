"""
Example: Downloading PDFs with web_fetcher

This example demonstrates how to use the new PDF downloading functionality
that handles CloudFlare challenges and cookie acceptance.
"""

import logging
from pathlib import Path
from selenium.webdriver.common.by import By

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

try:
    from web_fetcher import SeleniumWebFetcher, SELENIUM_AVAILABLE
    
    if not SELENIUM_AVAILABLE:
        print("Selenium is not installed. Install it with: pip install selenium")
        exit(1)
    
    # Initialize fetcher with Selenium enabled
    with SeleniumWebFetcher(
        cache_dir="./cache/pdf_example",
        use_selenium=True,
        headless=True,  # Set to False to see browser actions
        use_undetected=True,  # Helps bypass bot detection
        random_wait_min=2.0,  # Wait 2-5 seconds between requests
        random_wait_max=5.0,
    ) as fetcher:
        
        # Example 1: Direct PDF URL
        print("\n" + "="*60)
        print("Example 1: Direct PDF URL")
        print("="*60)
        pdf_path = fetcher.download_pdf(
            url="https://example.com/document.pdf",  # Replace with actual PDF URL
            output_path=Path("./downloads/example1.pdf")
        )
        if pdf_path:
            print(f"✓ PDF downloaded to: {pdf_path}")
        else:
            print("✗ Failed to download PDF")
        
        # Example 2: Page with PDF download link
        print("\n" + "="*60)
        print("Example 2: Page with PDF download link")
        print("="*60)
        pdf_path = fetcher.download_pdf(
            url="https://example.com/article",  # Replace with actual article URL
            output_path=Path("./downloads/example2.pdf"),
            cookie_accept_selector=(By.ID, "accept-cookies"),  # Adjust selector as needed
        )
        if pdf_path:
            print(f"✓ PDF downloaded to: {pdf_path}")
        else:
            print("✗ Failed to download PDF")
        
        # Example 3: Science.org article (with CloudFlare and cookies)
        print("\n" + "="*60)
        print("Example 3: Science.org article (CloudFlare + cookies)")
        print("="*60)
        pdf_path = fetcher.download_pdf(
            url="https://www.science.org/doi/10.1126/science.abc123",  # Replace with actual DOI
            output_path=Path("./downloads/science_article.pdf"),
            cookie_accept_selector=(By.CLASS_NAME, "osano-cm-acceptAll"),  # Science.org cookie button
        )
        if pdf_path:
            print(f"✓ PDF downloaded to: {pdf_path}")
        else:
            print("✗ Failed to download PDF")
            print("Note: This may require manual intervention for CloudFlare challenges")
        
        # Example 4: Batch download multiple PDFs
        print("\n" + "="*60)
        print("Example 4: Batch download")
        print("="*60)
        urls = [
            "https://example.com/paper1",
            "https://example.com/paper2",
            "https://example.com/paper3",
        ]
        
        for i, url in enumerate(urls, 1):
            print(f"\nDownloading PDF {i}/{len(urls)}: {url}")
            pdf_path = fetcher.download_pdf(
                url=url,
                output_path=Path(f"./downloads/paper_{i}.pdf"),
            )
            if pdf_path:
                print(f"✓ Success: {pdf_path}")
            else:
                print(f"✗ Failed: {url}")

except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure web_fetcher is installed: pip install -e .")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

