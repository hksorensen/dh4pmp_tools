#!/usr/bin/env python3
"""
Example: Using PDFDownloader to download PDFs from DOIs

This script demonstrates basic and batch usage of the PDFDownloader class.
"""

from web_fetcher import PDFDownloader
import logging

# Setup logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    print("=== PDFDownloader Example ===\n")
    
    # Example DOIs (mix of open access and potentially paywalled)
    example_dois = [
        "10.1371/journal.pone.0033693",  # PLoS ONE (open access)
        "10.48550/arXiv.2301.07041",      # arXiv (open access)
        "10.1038/s41586-024-07998-6",     # Nature (likely paywalled)
    ]
    
    # Create downloader
    downloader = PDFDownloader(
        pdf_dir="./example_pdfs",
        cache_dir="./example_cache",
        headless=True,  # Run browser in background
        max_retries=3
    )
    
    print("1. Single PDF Download")
    print("-" * 50)
    result = downloader.download_from_doi(example_dois[0])
    
    if result['success']:
        print(f"✓ Success: {result['pdf_path']}")
        print(f"  Cached: {result['cached']}")
    else:
        print(f"✗ Failed: {result['error']}")
        print(f"  Status: {result['status']}")
    
    print("\n2. Batch Download")
    print("-" * 50)
    results = downloader.download_batch(
        example_dois,
        delay=2.0,  # 2 seconds between requests
        progress=True
    )
    
    print("\n3. Statistics")
    print("-" * 50)
    stats = downloader.get_statistics()
    print(f"Total files: {stats['total_files']}")
    print(f"Successful: {stats['success']}")
    print(f"Failed: {stats['failure']}")
    print(f"Paywalled: {stats['paywall']}")
    print(f"Total size: {stats['total_size_mb']:.2f} MB")
    
    print("\n4. List Downloaded")
    print("-" * 50)
    downloaded = downloader.list_downloaded()
    for item in downloaded:
        print(f"✓ {item['doi']}")
        print(f"  Path: {item['pdf_path']}")
        print(f"  Downloaded: {item['timestamp']}")
    
    # Close browser
    downloader.close()
    
    print("\n=== Done ===")

if __name__ == "__main__":
    main()
