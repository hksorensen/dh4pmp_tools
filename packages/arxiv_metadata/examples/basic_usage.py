#!/usr/bin/env python3
"""
Basic example of using arxiv-metadata-fetcher.

This example shows how to:
1. Initialize the fetcher
2. Fetch papers by category and year
3. Apply filters
4. Work with the resulting DataFrame
"""

from arxiv_metadata import ArxivMetadata, Category

def main():
    # Initialize the fetcher
    # By default, it caches to ~/.arxiv_cache
    fetcher = ArxivMetadata()
    
    print("Example 1: Fetch all math papers from 2024")
    print("=" * 60)
    df = fetcher.fetch(
        categories=Category.MATH,
        years=2024,
        limit=100  # Limit for demo purposes
    )
    print(f"Found {len(df)} papers")
    print("\nSample papers:")
    print(df[['arxiv_id', 'title', 'primary_category', 'year']].head(10))
    
    print("\n\nExample 2: Specific subcategories with author filter")
    print("=" * 60)
    df = fetcher.fetch(
        categories=["math.AG", "math.NT"],  # Algebraic Geometry and Number Theory
        years=[2023, 2024],
        min_authors=2,
        limit=50
    )
    print(f"Found {len(df)} papers")
    print(f"Average authors: {df['num_authors'].mean():.2f}")
    
    print("\n\nExample 3: Custom filtering")
    print("=" * 60)
    df = fetcher.fetch(
        categories=Category.MATH,
        years=2024,
        filter_fn=lambda p: 'topology' in p.get('abstract', '').lower(),
        limit=20
    )
    print(f"Found {len(df)} papers about topology")
    print("\nTitles:")
    for title in df['title'].head(5):
        print(f"  - {title}")
    
    print("\n\nExample 4: Memory-efficient streaming")
    print("=" * 60)
    print("First 5 math papers from 2024 with 'manifold' in abstract:")
    count = 0
    for paper in fetcher.stream(categories=Category.MATH, years=2024):
        if 'manifold' in paper.get('abstract', '').lower():
            print(f"  {paper['arxiv_id']}: {paper['title'][:60]}...")
            count += 1
            if count >= 5:
                break

if __name__ == '__main__':
    main()
