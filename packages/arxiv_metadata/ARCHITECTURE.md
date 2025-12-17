# Project Architecture

## Overview

`arxiv-metadata-fetcher` is a modern Python package for fetching and filtering arXiv metadata with the following design principles:

1. **Streaming architecture** - Process large datasets without loading into memory
2. **Lazy evaluation** - Only process papers that match filters
3. **Smart caching** - Local cache with expiry management
4. **Type safety** - Full type hints for better IDE support
5. **Extensibility** - Easy to add custom filters

## Directory Structure

```
arxiv-metadata-fetcher/
├── pyproject.toml          # Modern Python package configuration
├── README.md               # User documentation
├── SETUP.md               # Installation and setup guide
├── LICENSE                # MIT License
├── MANIFEST.in            # Include additional files in distribution
├── .gitignore            # Git ignore rules
│
├── src/
│   └── arxiv_metadata/
│       ├── __init__.py          # Public API exports
│       ├── fetcher.py           # Main ArxivMetadata class
│       ├── filters.py           # Category enum and filter utilities
│       └── exceptions.py        # Custom exceptions
│
├── tests/
│   ├── test_fetcher.py         # Tests for fetcher module
│   └── test_filters.py         # Tests for filters module
│
├── examples/
│   ├── basic_usage.py          # Basic usage examples
│   └── advanced_analysis.py    # Advanced analysis examples
│
└── scripts/
    └── download_metadata.py     # Utility for downloading metadata
```

## Core Components

### 1. ArxivMetadata (fetcher.py)

The main class that handles:
- Metadata file management
- Cache management
- Streaming and batch fetching
- Year parsing from arXiv IDs
- Paper processing and enrichment

**Key Methods:**
- `fetch()` - Batch fetch papers as DataFrame
- `stream()` - Memory-efficient streaming
- `download_metadata()` - Download/manage metadata file
- `clear_cache()` - Clear cached data

### 2. Filters (filters.py)

Filtering system with two approaches:

**Category Enum:**
```python
Category.MATH      # Matches all math.* papers
Category.CS        # Matches all cs.* papers
# etc.
```

**FilterBuilder:**
```python
filter_fn = (FilterBuilder()
    .categories(["math.AG"])
    .years([2023, 2024])
    .min_authors(2)
    .build())
```

### 3. Exceptions (exceptions.py)

Custom exceptions for better error handling:
- `ArxivFetchError` - Base exception
- `CacheError` - Cache-related errors
- `DownloadError` - Download failures
- `ParseError` - Parsing errors

## Data Flow

```
User Request
    ↓
ArxivMetadata.fetch(filters)
    ↓
1. Check cache validity
2. Get metadata file path
3. Open file for streaming
    ↓
For each line in file:
    ↓
4. Parse JSON
5. Process paper (add year, categories, etc.)
6. Apply filters (short-circuit on failure)
7. Yield/collect matching papers
    ↓
8. Convert to DataFrame (if fetch)
9. Return results
```

## Streaming Architecture

The streaming approach processes papers one at a time:

```python
def stream(self, categories=None, years=None, ...):
    with open(metadata_file) as f:
        for line in f:
            paper = json.loads(line)
            paper = self._process_paper(paper)
            
            # Early exit if filters don't match
            if not matches_filters(paper):
                continue
                
            yield paper
```

**Benefits:**
- Constant memory usage (only one paper in memory at a time)
- Can process multi-GB files on limited hardware
- Supports lazy evaluation and early termination

## Filter System

Filters are applied in sequence with short-circuit evaluation:

```python
# Category filter (most selective, checked first)
if categories and not matches_categories(paper, categories):
    continue

# Year filter (moderately selective)
if years and paper['year'] not in years:
    continue

# Author count (less selective)
if min_authors and paper['num_authors'] < min_authors:
    continue

# Custom filter (variable selectivity)
if filter_fn and not filter_fn(paper):
    continue
```

## Caching Strategy

Cache validation:
1. Check if cache file exists
2. Check file modification time
3. Compare with `cache_expiry_days`
4. Use cache if valid, otherwise trigger download

Cache locations:
- Default: `~/.arxiv_cache/arxiv_metadata.jsonl`
- Environment variable: `ARXIV_METADATA_PATH`
- Custom via constructor: `ArxivMetadata(cache_dir="/path")`

## Extension Points

### Adding New Filters

Add to `FilterBuilder`:

```python
class FilterBuilder:
    def has_keyword(self, keyword: str):
        def filter_fn(paper: dict) -> bool:
            abstract = paper.get('abstract', '').lower()
            return keyword.lower() in abstract
        
        self._filters.append(filter_fn)
        return self
```

### Custom Paper Processing

Override `_process_paper`:

```python
class CustomArxiv(ArxivMetadata):
    def _process_paper(self, paper):
        paper = super()._process_paper(paper)
        # Add custom fields
        paper['has_deep_learning'] = 'deep learning' in paper['abstract'].lower()
        return paper
```

### Alternative Data Sources

The design supports alternative metadata sources:

```python
class ArxivFromAPI(ArxivMetadata):
    def _get_metadata_path(self):
        # Fetch from API instead of file
        return self._download_from_api()
```

## Performance Characteristics

### Memory Usage

- **Streaming**: O(1) - constant memory per paper
- **Batch fetch**: O(n) where n = matching papers
- **Full dataset**: ~5GB compressed, ~25GB uncompressed

### Time Complexity

- **First run**: O(n) where n = total papers (~3M)
- **With filters**: O(n × f) where f = filter cost
- **With cache hit**: O(m) where m = matching papers

### Optimization Strategies

1. **Filter ordering**: Most selective filters first
2. **Early termination**: Use `limit` parameter
3. **Column selection**: Request only needed columns
4. **Caching**: Reuse processed results

## Testing Strategy

### Unit Tests

- Filter logic (test_filters.py)
- Paper processing (test_fetcher.py)
- Cache management
- Error handling

### Integration Tests

- Full pipeline with sample data
- Multiple filter combinations
- Cache invalidation scenarios

### Test Fixtures

Sample metadata file with diverse papers:
- Different years
- Various categories
- Different author counts
- With/without DOIs

## Deployment

### pip Installation

```bash
pip install arxiv-metadata-fetcher
```

### Development Installation

```bash
git clone <repo>
cd arxiv-metadata-fetcher
pip install -e ".[dev]"
```

### Building Distribution

```bash
python -m build
twine upload dist/*
```

## Future Enhancements

Potential improvements:

1. **Parallel processing** - Multi-threaded streaming
2. **Database backend** - SQLite cache for faster queries
3. **Incremental updates** - Download only new papers
4. **Remote APIs** - Fetch directly from arXiv API
5. **Full-text search** - Index abstracts for searching
6. **Compressed storage** - gzip cache files automatically
7. **Progress estimation** - Better progress bars for large queries

## Dependencies

### Required
- pandas: DataFrame support
- requests: HTTP downloads
- tqdm: Progress bars

### Optional
- pytest: Testing
- black: Code formatting
- mypy: Type checking
- kagglehub: Kaggle downloads

## Version Compatibility

- Python: ≥ 3.8
- pandas: ≥ 1.5.0
- requests: ≥ 2.28.0
- tqdm: ≥ 4.64.0
