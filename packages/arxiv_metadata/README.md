# arXiv Metadata Fetcher

A modern, streamlined Python toolkit for fetching and filtering arXiv metadata with streaming downloads and intelligent caching.

## Features

- 🚀 **Streaming downloads** - Process metadata without loading entire dataset into memory
- 🎯 **Smart filtering** - Built-in filters for categories, years, and custom criteria
- 💾 **Intelligent caching** - Local caching with automatic cache management
- 🔧 **Easy to use** - Clean API with sensible defaults
- 📦 **Pip installable** - Standard Python package installation

## Installation

```bash
pip install arxiv-metadata-fetcher
```

### Development Installation

```bash
git clone https://github.com/yourusername/arxiv-metadata-fetcher.git
cd arxiv-metadata-fetcher
pip install -e ".[dev]"
```

## Quick Start

```python
from arxiv_metadata import ArxivMetadata, Category

# Initialize the fetcher (default cache: ~/.cache/arxiv)
fetcher = ArxivMetadata()

# Check cache info and dataset version
cache_info = fetcher.get_cache_info()
print(cache_info)

# Option 1: Download and filter in one step (memory efficient!)
df = fetcher.download_and_fetch(
    categories=Category.MATH,
    years=range(2020, 2025),
    min_authors=2
)

# Option 2: Use cached metadata (after first download)
df = fetcher.fetch(
    categories=Category.MATH,
    years=2023
)

# Option 3: Stream for minimal memory usage
for paper in fetcher.stream(categories=Category.CS, years=2024):
    print(f"{paper['title']} - {paper['primary_category']}")
```

### Kaggle Credentials Setup

To use automatic downloads, set up Kaggle credentials:

1. Get your API key from https://www.kaggle.com/settings/account
2. Create `~/.kaggle/kaggle.json`:
   ```json
   {"username":"your_username","key":"your_api_key"}
   ```
3. Or set environment variables:
   ```bash
   export KAGGLE_USERNAME=your_username
   export KAGGLE_KEY=your_api_key
   ```

**Note**: The metadata file is approximately 1.5 GB and contains 2.7M+ papers.

## API Reference

### ArxivMetadata

Main class for fetching arXiv metadata.

#### Constructor

```python
ArxivMetadata(
    cache_dir: str = "~/.arxiv_cache",
    use_cache: bool = True,
    cache_expiry_days: int = 30
)
```

**Parameters:**
- `cache_dir`: Directory for caching downloaded metadata (default: ~/.cache/arxiv)
- `use_cache`: Whether to use local cache
- `cache_expiry_days`: Days before cache expires

#### Methods

##### `get_cache_info()`

Get information about cached dataset including version.

```python
info = fetcher.get_cache_info()
# Returns dict with:
# - cache_exists: bool
# - cache_path: str
# - cache_valid: bool
# - size_gb: float (if exists)
# - age_days: int (if exists)
# - dataset_version: str (if available)
# - last_updated: str (if available)
```

##### `download_and_fetch()`

Download from Kaggle and filter on-the-fly (most memory efficient).

```python
download_and_fetch(
    categories: Category | list[str] | str | None = None,
    years: int | range | list[int] | None = None,
    min_authors: int | None = None,
    max_authors: int | None = None,
    has_doi: bool | None = None,
    filter_fn: Callable | None = None,
    columns: list[str] | None = None,
    limit: int | None = None,
    show_progress: bool = True,
    force_download: bool = False
) -> pd.DataFrame
```

**When to use**: First time download or when you want to filter during download to save memory.

##### `fetch()`

Download and filter metadata, returns pandas DataFrame.

```python
fetch(
    categories: Category | list[str] | str | None = None,
    years: int | range | list[int] | None = None,
    min_authors: int | None = None,
    max_authors: int | None = None,
    has_doi: bool | None = None,
    filter_fn: Callable | None = None,
    columns: list[str] | None = None,
    limit: int | None = None
) -> pd.DataFrame
```

##### `stream()`

Stream papers one at a time (memory efficient).

```python
stream(
    categories: Category | list[str] | str | None = None,
    years: int | range | list[int] | None = None,
    filter_fn: Callable | None = None
) -> Iterator[dict]
```

##### `download_metadata()`

Download raw metadata file (usually not needed directly).

```python
download_metadata(force: bool = False) -> Path
```

### Category Enum

Predefined category filters for convenience.

```python
from arxiv_metadata import Category

Category.MATH        # All math.* categories
Category.CS          # All cs.* categories  
Category.PHYSICS     # All physics.* categories
Category.STAT        # All stat.* categories
Category.EESS        # All eess.* categories
Category.ECON        # All econ.* categories
```

## Examples

### Example 1: Math papers from recent years

```python
from arxiv_metadata import ArxivMetadata, Category

fetcher = ArxivMetadata()

# Get all math papers from 2020-2024
df = fetcher.fetch(
    categories=Category.MATH,
    years=range(2020, 2025)
)

print(f"Found {len(df)} papers")
print(df[['arxiv_id', 'title', 'primary_category', 'year']].head())
```

### Example 2: Specific subcategories with author filter

```python
# Algebraic Geometry and Number Theory papers with multiple authors
df = fetcher.fetch(
    categories=["math.AG", "math.NT"],
    years=[2022, 2023, 2024],
    min_authors=2
)

# Analyze author counts
print(df['num_authors'].describe())
```

### Example 3: Custom filtering

```python
# Papers about neural networks with DOIs
df = fetcher.fetch(
    categories=Category.CS,
    has_doi=True,
    filter_fn=lambda p: 'neural network' in p['abstract'].lower()
)
```

### Example 4: Memory-efficient streaming

```python
# Process large dataset without loading all into memory
count = 0
for paper in fetcher.stream(categories=Category.MATH, years=2024):
    if 'topology' in paper['abstract'].lower():
        print(f"{paper['arxiv_id']}: {paper['title']}")
        count += 1
        if count >= 100:
            break
```

### Example 5: Cross-category analysis

```python
# Papers categorized in both math and CS
df = fetcher.fetch(
    filter_fn=lambda p: any(c.startswith('math.') for c in p['categories']) 
                        and any(c.startswith('cs.') for c in p['categories'])
)
```

## Data Schema

The returned DataFrame contains the following columns:

- `arxiv_id`: arXiv identifier (e.g., "2301.12345")
- `title`: Paper title
- `authors`: List of author names
- `authors_parsed`: List of parsed author names [surname, given_names, suffix]
- `abstract`: Paper abstract
- `categories`: List of arXiv categories
- `primary_category`: Primary category
- `doi`: DOI if available
- `year`: Publication year (extracted from arxiv_id)
- `created`: Creation date
- `updated`: Last update date
- `num_authors`: Number of authors
- `num_versions`: Number of versions

## Caching

The package automatically caches downloaded metadata to avoid repeated downloads:

- Default cache location: `~/.cache/arxiv/`
- Cache expires after 30 days by default
- Version information saved alongside cache
- Manually check cache: `fetcher.get_cache_info()`
- Manually clear cache: `fetcher.clear_cache()`
- Force re-download: `fetcher.download_metadata(force=True)`

```python
# Check cache status and version
info = fetcher.get_cache_info()
if info['cache_exists']:
    print(f"Cache: {info['size_gb']:.2f} GB")
    print(f"Age: {info['age_days']} days")
    if 'dataset_version' in info:
        print(f"Dataset version: {info['dataset_version']}")
```

## Performance Tips

1. **Use streaming for large datasets**: If you're processing many papers, use `stream()` instead of `fetch()`
2. **Filter early**: Apply filters in `fetch()` rather than filtering the DataFrame afterwards
3. **Cache wisely**: The default 30-day cache expiry works for most use cases
4. **Specify columns**: Request only needed columns to reduce memory usage

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.

## Citation

If you use this package in research, please cite the arXiv dataset:

```bibtex
@misc{arxiv_dataset,
  author = {arXiv},
  title = {arXiv Dataset},
  year = {2024},
  howpublished = {\\url{https://arxiv.org/help/bulk_data_s3}},
}
```

## Acknowledgments

Data provided by [arXiv](https://arxiv.org/), an open-access archive operated by Cornell University.
