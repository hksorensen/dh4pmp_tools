#!/usr/bin/env python3
"""
Advanced example: Analyzing collaboration patterns in math papers.

This example demonstrates:
1. Fetching data for multiple years
2. Analyzing trends over time
3. Cross-category analysis
4. Creating visualizations (if matplotlib available)
"""

from arxiv_metadata import ArxivMetadata, Category
import pandas as pd

def analyze_collaboration_trends():
    """Analyze how collaboration patterns have changed in math over time."""
    fetcher = ArxivMetadata()
    
    print("Fetching math papers from 2015-2024...")
    print("(This may take a few minutes on first run)")
    
    df = fetcher.fetch(
        categories=Category.MATH,
        years=range(2015, 2025),
        show_progress=True
    )
    
    print(f"\nTotal papers: {len(df)}")
    
    # Analyze by year
    print("\n" + "=" * 60)
    print("Collaboration Trends by Year")
    print("=" * 60)
    
    yearly_stats = df.groupby('year').agg({
        'arxiv_id': 'count',
        'num_authors': ['mean', 'median', 'max']
    }).round(2)
    
    yearly_stats.columns = ['Total Papers', 'Avg Authors', 'Median Authors', 'Max Authors']
    print(yearly_stats)
    
    # Analyze single vs multi-author papers
    print("\n" + "=" * 60)
    print("Single vs Multi-Author Papers")
    print("=" * 60)
    
    df['author_type'] = df['num_authors'].apply(
        lambda x: 'Single' if x == 1 else 'Collaboration'
    )
    
    author_type_stats = df.groupby(['year', 'author_type']).size().unstack(fill_value=0)
    author_type_pct = author_type_stats.div(author_type_stats.sum(axis=1), axis=0) * 100
    
    print("\nPercentage of papers:")
    print(author_type_pct.round(1))
    
    # Top subcategories
    print("\n" + "=" * 60)
    print("Top 10 Math Subcategories (2020-2024)")
    print("=" * 60)
    
    recent_df = df[df['year'] >= 2020]
    cat_counts = recent_df['primary_category'].value_counts().head(10)
    print(cat_counts)
    
    # Papers with DOI
    print("\n" + "=" * 60)
    print("Papers with DOI")
    print("=" * 60)
    
    df['has_doi'] = df['doi'].notna() & (df['doi'] != '')
    doi_by_year = df.groupby('year')['has_doi'].apply(lambda x: (x.sum() / len(x) * 100))
    print("Percentage of papers with DOI by year:")
    print(doi_by_year.round(1))

def find_interdisciplinary_papers():
    """Find papers that span multiple disciplines."""
    fetcher = ArxivMetadata()
    
    print("\n\n" + "=" * 60)
    print("Interdisciplinary Papers (Math + CS)")
    print("=" * 60)
    
    df = fetcher.fetch(
        filter_fn=lambda p: (
            any(c.startswith('math.') for c in p.get('categories', [])) and
            any(c.startswith('cs.') for c in p.get('categories', []))
        ),
        years=range(2022, 2025),
        limit=1000
    )
    
    print(f"\nFound {len(df)} interdisciplinary papers")
    
    # Find common category combinations
    def get_main_categories(cats):
        return tuple(sorted(set(c.split('.')[0] for c in cats)))
    
    df['main_categories'] = df['categories'].apply(get_main_categories)
    
    print("\nSample interdisciplinary papers:")
    sample = df[['arxiv_id', 'title', 'categories', 'year']].head(5)
    for _, row in sample.iterrows():
        print(f"\n{row['arxiv_id']} ({row['year']})")
        print(f"  {row['title']}")
        print(f"  Categories: {', '.join(row['categories'])}")

def main():
    try:
        analyze_collaboration_trends()
        find_interdisciplinary_papers()
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you have the metadata file downloaded.")
        print("See README.md for instructions.")

if __name__ == '__main__':
    main()
