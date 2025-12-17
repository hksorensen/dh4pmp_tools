#!/usr/bin/env python3
"""
Example: Direct download and filtering from Kaggle

This example demonstrates the download_and_fetch() method which:
1. Downloads metadata directly from Kaggle
2. Filters on-the-fly during download (memory efficient)
3. Returns only matching papers as DataFrame
4. Caches full file for future use

This is the most memory-efficient approach for first-time downloads.
"""

from arxiv_metadata import ArxivMetadata, Category

def main():
    # Initialize fetcher
    fetcher = ArxivMetadata()
    
    print("=" * 70)
    print("DOWNLOAD AND FILTER IN ONE STEP")
    print("=" * 70)
    print()
    print("This method:")
    print("  ✓ Downloads from Kaggle automatically")
    print("  ✓ Filters during download (very memory efficient)")
    print("  ✓ Caches full file for future use")
    print()
    
    # Example 1: Download recent math papers
    print("Example 1: Download math papers from 2023-2024")
    print("-" * 70)
    
    try:
        df = fetcher.download_and_fetch(
            categories=Category.MATH,
            years=range(2023, 2025),
            limit=100  # Limit for this example
        )
        
        print(f"\nFound {len(df)} papers")
        print("\nSample papers:")
        print(df[['arxiv_id', 'title', 'primary_category', 'year']].head())
        
        print("\n\nExample 2: Download with multiple filters")
        print("-" * 70)
        
        # Example 2: More complex filtering
        df = fetcher.download_and_fetch(
            categories=["math.AG", "math.NT"],
            years=2024,
            min_authors=2,
            has_doi=True,
            limit=50
        )
        
        print(f"\nFound {len(df)} papers with all criteria:")
        print("  ✓ Categories: math.AG or math.NT")
        print("  ✓ Year: 2024")
        print("  ✓ Authors: 2+")
        print("  ✓ Has DOI: Yes")
        
        print("\n\nExample 3: Custom filter function")
        print("-" * 70)
        
        # Example 3: Custom filtering
        df = fetcher.download_and_fetch(
            categories=Category.MATH,
            years=2024,
            filter_fn=lambda p: (
                'topology' in p.get('abstract', '').lower() and
                len(p.get('title', '')) > 50  # Longer titles
            ),
            limit=20
        )
        
        print(f"\nFound {len(df)} papers about topology with long titles")
        for title in df['title'].head(5):
            print(f"  • {title[:80]}...")
        
        print("\n\n" + "=" * 70)
        print("AFTER FIRST DOWNLOAD")
        print("=" * 70)
        print()
        print("The full metadata file is now cached.")
        print("Future queries will be much faster using fetch() or stream():")
        print()
        print("  df = fetcher.fetch(categories=Category.CS, years=2024)")
        print()
        
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you have Kaggle credentials set up:")
        print("1. Get API key from: https://www.kaggle.com/settings/account")
        print("2. Create ~/.kaggle/kaggle.json with:")
        print('   {"username":"your_username","key":"your_api_key"}')
        print()
        print("Or set environment variables:")
        print("  export KAGGLE_USERNAME=your_username")
        print("  export KAGGLE_KEY=your_api_key")

if __name__ == '__main__':
    main()
