"""
Example usage of PDF Fetcher v2.

This demonstrates how to use the new PDF fetcher implementation
according to the specification.
"""

import logging
from pathlib import Path
from web_fetcher.pdf_fetcher_v2 import PDFFetcher, DownloadStatus

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Example usage of PDF Fetcher."""
    
    # Initialize fetcher
    fetcher = PDFFetcher(
        pdf_dir="./pdfs",
        metadata_path="./pdfs/metadata.json",
        headless=True,
        requests_per_second=1.0,  # 1 request per second per domain
        max_retries=3
    )
    
    # Test identifiers
    test_identifiers = [
        "10.2138/am.2011.573",  # DOI
        "https://doi.org/10.1016/j.amc.2021.126357",  # DOI-URL
        # Add more test cases as needed
    ]
    
    results = []
    for identifier in test_identifiers:
        print(f"\n{'='*60}")
        print(f"Downloading: {identifier}")
        print(f"{'='*60}")
        
        result = fetcher.download(identifier)
        results.append(result)
        
        print(f"Status: {result.status.value}")
        print(f"Publisher: {result.publisher}")
        print(f"Landing URL: {result.landing_url}")
        print(f"PDF URL: {result.pdf_url}")
        print(f"PDF Path: {result.pdf_path}")
        
        if result.status == DownloadStatus.SUCCESS:
            print(f"✓ Successfully downloaded to: {result.pdf_path}")
        elif result.status == DownloadStatus.ALREADY_EXISTS:
            print(f"✓ PDF already exists: {result.pdf_path}")
        else:
            print(f"✗ Failed: {result.error_reason}")
    
    # Summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    for result in results:
        print(f"{result.identifier}: {result.status.value}")
    
    # Cleanup
    fetcher.close()


if __name__ == "__main__":
    main()

