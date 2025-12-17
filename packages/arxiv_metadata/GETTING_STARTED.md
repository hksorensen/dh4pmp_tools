# Getting Started

## Quick Setup (5 minutes)

### Step 1: Install the package

From the package directory:

```bash
cd arxiv-metadata-fetcher
pip install -e .
```

This installs the package in "editable" mode, meaning you can modify the source code and changes take effect immediately.

### Step 2: Download metadata

You have two options:

**Option A: Automatic Download with Filtering (Recommended)**

Set up Kaggle credentials once:

1. Get your API key from https://www.kaggle.com/settings/account
2. Create `~/.kaggle/kaggle.json`:
```json
{"username":"your_username","key":"your_api_key"}
```

Then use download_and_fetch() which downloads and filters in one step:

```python
from arxiv_metadata import ArxivMetadata, Category

fetcher = ArxivMetadata()
# Downloads from Kaggle and filters during download (memory efficient!)
df = fetcher.download_and_fetch(
    categories=Category.MATH,
    years=2024,
    limit=100
)
```

**Option B: Manual Download**

1. Go to https://www.kaggle.com/datasets/Cornell-University/arxiv
2. Download `arxiv-metadata-oai-snapshot.json`
3. Place at `~/.arxiv_cache/arxiv_metadata.jsonl`

```bash
mkdir -p ~/.arxiv_cache
mv ~/Downloads/arxiv-metadata-oai-snapshot.json ~/.arxiv_cache/arxiv_metadata.jsonl
```

**Option C: Set environment variable**

```bash
export ARXIV_METADATA_PATH="/path/to/arxiv-metadata-oai-snapshot.json"
```

### Step 3: Test it works

```python
from arxiv_metadata import ArxivMetadata, Category

fetcher = ArxivMetadata()
df = fetcher.fetch(categories=Category.MATH, years=2024, limit=10)
print(f"✓ Found {len(df)} papers")
print(df[['arxiv_id', 'title', 'year']].head())
```

If this runs without errors, you're ready to go!

## Your First Queries

### Example 1: Math papers from 2024

```python
from arxiv_metadata import ArxivMetadata, Category

fetcher = ArxivMetadata()

# Get all math papers from 2024
df = fetcher.fetch(
    categories=Category.MATH,
    years=2024
)

print(f"Found {len(df)} math papers from 2024")

# What are the most common subcategories?
print(df['primary_category'].value_counts().head(10))

# How many authors on average?
print(f"Average authors: {df['num_authors'].mean():.2f}")
```

### Example 2: Specific subcategories

```python
# Algebraic Geometry and Number Theory
df = fetcher.fetch(
    categories=["math.AG", "math.NT"],
    years=[2023, 2024]
)

print(f"Found {len(df)} papers in AG and NT")

# Show some titles
for title in df['title'].head(5):
    print(f"  • {title}")
```

### Example 3: Filter by author count

```python
# Multi-author math papers from recent years
df = fetcher.fetch(
    categories=Category.MATH,
    years=range(2020, 2025),
    min_authors=3,
    max_authors=5
)

print(f"Found {len(df)} papers with 3-5 authors")

# Distribution of author counts
print(df['num_authors'].value_counts().sort_index())
```

### Example 4: Custom text filtering

```python
# Papers about topology
df = fetcher.fetch(
    categories=Category.MATH,
    years=2024,
    filter_fn=lambda p: 'topology' in p['abstract'].lower()
)

print(f"Found {len(df)} papers about topology")
```

### Example 5: Memory-efficient streaming

For very large queries, use streaming:

```python
# Stream papers one at a time (uses minimal memory)
count = 0
for paper in fetcher.stream(categories=Category.MATH, years=2024):
    print(f"{paper['arxiv_id']}: {paper['title'][:60]}...")
    count += 1
    if count >= 10:  # Just show first 10
        break
```

## Common Patterns

### Count papers by category over time

```python
df = fetcher.fetch(
    categories=Category.MATH,
    years=range(2015, 2025)
)

# Papers per year
yearly = df.groupby('year').size()
print(yearly)

# Top subcategories
top_cats = df['primary_category'].value_counts().head(10)
print(top_cats)
```

### Find interdisciplinary papers

```python
df = fetcher.fetch(
    filter_fn=lambda p: (
        any(c.startswith('math.') for c in p['categories']) and
        any(c.startswith('cs.') for c in p['categories'])
    ),
    years=2024
)

print(f"Found {len(df)} interdisciplinary papers (math + CS)")
```

### Papers with specific keywords

```python
keywords = ['neural', 'topology', 'manifold']

df = fetcher.fetch(
    categories=Category.MATH,
    years=2024,
    filter_fn=lambda p: any(
        kw in p['abstract'].lower() for kw in keywords
    )
)

print(f"Found {len(df)} papers with keywords: {keywords}")
```

## Running the Examples

The package includes complete example scripts:

```bash
# Basic usage examples
python examples/basic_usage.py

# Advanced analysis
python examples/advanced_analysis.py
```

## Running Tests

Verify everything works correctly:

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=arxiv_metadata

# Run specific test file
pytest tests/test_filters.py
```

## Next Steps

1. **Read the docs:**
   - `README.md` - Full documentation
   - `QUICKREF.md` - Quick reference
   - `ARCHITECTURE.md` - Design details

2. **Check examples:**
   - `examples/basic_usage.py`
   - `examples/advanced_analysis.py`

3. **Customize:**
   - Modify filters in `src/arxiv_metadata/filters.py`
   - Extend fetcher in `src/arxiv_metadata/fetcher.py`

4. **Migrate old code:**
   - See `MIGRATION.md` for migration guide

## Troubleshooting

### "No metadata file found"

Make sure you've downloaded the metadata file and placed it correctly:
```bash
ls -lh ~/.arxiv_cache/arxiv_metadata.jsonl
```

Or set the environment variable:
```bash
export ARXIV_METADATA_PATH="/path/to/file"
```

### "Memory Error"

Use streaming instead of batch fetch:
```python
# Instead of:
df = fetcher.fetch(categories=Category.MATH)  # Might be too large

# Use:
for paper in fetcher.stream(categories=Category.MATH):
    # Process one at a time
    pass
```

### Slow queries

First query processes the entire file (~5 min). Subsequent queries are much faster due to caching. To speed up:
- Use more specific filters
- Use `limit` parameter for testing
- Filter by recent years only

### Import errors

Make sure you installed the package:
```bash
pip install -e .
```

And verify installation:
```bash
python -c "from arxiv_metadata import ArxivMetadata; print('✓ Success')"
```

## Tips for Best Performance

1. **Start with small queries** - Use `limit=100` for testing
2. **Filter by year** - Recent years process faster
3. **Use specific categories** - More selective filters = faster
4. **Stream large datasets** - Use `stream()` instead of `fetch()`
5. **Cache is your friend** - First run is slow, subsequent runs are fast

## Support

- Documentation: See `*.md` files
- Examples: See `examples/` directory
- Tests: See `tests/` directory
- Issues: Open a GitHub issue

## What's Inside

```
arxiv-metadata-fetcher/
├── README.md              # Full documentation
├── QUICKREF.md           # Quick reference
├── SETUP.md              # Detailed setup
├── MIGRATION.md          # Migration from old code
├── ARCHITECTURE.md       # Design docs
├── GETTING_STARTED.md    # This file
│
├── src/arxiv_metadata/   # Main package
│   ├── fetcher.py        # ArxivMetadata class
│   ├── filters.py        # Category enum and filters
│   └── exceptions.py     # Custom exceptions
│
├── examples/             # Usage examples
│   ├── basic_usage.py
│   └── advanced_analysis.py
│
├── tests/                # Unit tests
│   ├── test_fetcher.py
│   └── test_filters.py
│
└── scripts/              # Utility scripts
    └── download_metadata.py
```

Happy researching! 📚
