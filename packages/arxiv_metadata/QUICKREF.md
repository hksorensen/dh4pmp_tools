# Quick Reference

## Installation

```bash
pip install arxiv-metadata-fetcher
```

## Basic Usage

```python
from arxiv_metadata import ArxivMetadata, Category

fetcher = ArxivMetadata()
```

## Common Queries

### All math papers from 2024
```python
df = fetcher.fetch(categories=Category.MATH, years=2024)
```

### Specific subcategories
```python
df = fetcher.fetch(categories=["math.AG", "math.NT"], years=2023)
```

### Multiple years
```python
df = fetcher.fetch(categories=Category.CS, years=range(2020, 2025))
```

### With author filter
```python
df = fetcher.fetch(
    categories=Category.MATH,
    min_authors=2,
    max_authors=5
)
```

### Papers with DOI
```python
df = fetcher.fetch(categories=Category.MATH, has_doi=True)
```

### Custom filter
```python
df = fetcher.fetch(
    categories=Category.CS,
    filter_fn=lambda p: 'neural network' in p['abstract'].lower()
)
```

### Limit results
```python
df = fetcher.fetch(categories=Category.MATH, limit=100)
```

### Select specific columns
```python
df = fetcher.fetch(
    categories=Category.MATH,
    columns=['arxiv_id', 'title', 'abstract', 'year']
)
```

## Streaming (Memory Efficient)

```python
for paper in fetcher.stream(categories=Category.MATH, years=2024):
    print(f"{paper['arxiv_id']}: {paper['title']}")
```

## Available Categories

```python
Category.MATH        # All math.*
Category.CS          # All cs.*
Category.PHYSICS     # All physics.*
Category.STAT        # All stat.*
Category.EESS        # All eess.*
Category.ECON        # All econ.*
Category.QUANT_BIO   # All q-bio.*
Category.QUANT_FIN   # All q-fin.*

# Physics subcategories
Category.ASTRO_PH
Category.COND_MAT
Category.GR_QC
Category.HEP_TH
Category.QUANT_PH
# ... and more
```

## DataFrame Columns

```python
# Available columns in returned DataFrame:
[
    'arxiv_id',          # e.g., "2301.12345"
    'title',             # Paper title
    'authors',           # List of author names
    'authors_parsed',    # [[surname, given, suffix], ...]
    'abstract',          # Paper abstract
    'categories',        # List of categories
    'primary_category',  # Main category
    'doi',              # DOI if available
    'year',             # Publication year
    'created',          # Creation date
    'updated',          # Last update
    'num_authors',      # Author count
    'num_versions',     # Version count
]
```

## Advanced: FilterBuilder

```python
from arxiv_metadata import FilterBuilder

filter_fn = (FilterBuilder()
    .categories(["math.AG", "math.NT"])
    .years([2023, 2024])
    .min_authors(2)
    .has_doi()
    .custom(lambda p: 'theorem' in p['title'].lower())
    .build())

df = fetcher.fetch(filter_fn=filter_fn)
```

## Configuration

```python
# Custom cache directory
fetcher = ArxivMetadata(cache_dir="/path/to/cache")

# Disable cache
fetcher = ArxivMetadata(use_cache=False)

# Custom expiry (days)
fetcher = ArxivMetadata(cache_expiry_days=7)

# Clear cache
fetcher.clear_cache()
```

## Environment Variables

```bash
# Point to metadata file
export ARXIV_METADATA_PATH="/path/to/arxiv-metadata-oai-snapshot.json"
```

## Common Patterns

### Count papers by category
```python
df = fetcher.fetch(categories=Category.MATH, years=2024)
df['primary_category'].value_counts()
```

### Find interdisciplinary papers
```python
df = fetcher.fetch(
    filter_fn=lambda p: len(set(c.split('.')[0] for c in p['categories'])) > 1
)
```

### Most prolific authors
```python
from collections import Counter
authors = Counter()
for paper in fetcher.stream(categories=Category.MATH, years=2024):
    for author in paper['authors_parsed']:
        authors[author[0]] += 1  # Count by surname
print(authors.most_common(10))
```

### Collaboration network
```python
import pandas as pd
df = fetcher.fetch(categories=Category.MATH, years=2024)
df['author_count'] = df['authors_parsed'].apply(len)
print(df['author_count'].describe())
```

## Troubleshooting

### No metadata file found
Download from https://www.kaggle.com/datasets/Cornell-University/arxiv
Place at `~/.arxiv_cache/arxiv_metadata.jsonl`

### Memory issues
Use `stream()` instead of `fetch()` for large queries

### Slow performance
Use more specific filters and `limit` parameter for testing

## Examples Location

Check the `examples/` directory for complete working examples:
- `basic_usage.py` - Common use cases
- `advanced_analysis.py` - Analysis patterns
