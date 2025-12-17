# Setup and Installation Guide

## Quick Start

### 1. Install the package

```bash
# From PyPI (once published)
pip install arxiv-metadata-fetcher

# Or install from source
git clone https://github.com/yourusername/arxiv-metadata-fetcher.git
cd arxiv-metadata-fetcher
pip install -e .
```

### 2. Download the metadata

The package requires the arXiv metadata file. You have several options:

#### Option A: Download from Kaggle (Recommended)

1. Create a Kaggle account at https://www.kaggle.com
2. Go to https://www.kaggle.com/datasets/Cornell-University/arxiv
3. Download `arxiv-metadata-oai-snapshot.json` (warning: ~5GB file)
4. Place it in `~/.arxiv_cache/arxiv_metadata.jsonl`

```bash
mkdir -p ~/.arxiv_cache
mv ~/Downloads/arxiv-metadata-oai-snapshot.json ~/.arxiv_cache/arxiv_metadata.jsonl
```

#### Option B: Use Environment Variable

Set the `ARXIV_METADATA_PATH` environment variable to point to your metadata file:

```bash
export ARXIV_METADATA_PATH="/path/to/arxiv-metadata-oai-snapshot.json"
```

Add this to your `~/.bashrc` or `~/.zshrc` to make it permanent.

#### Option C: Download from arXiv S3 (Advanced)

```bash
# Requires AWS CLI
aws s3 cp s3://arxiv/arxiv/arxiv-metadata-oai-snapshot.json ~/.arxiv_cache/arxiv_metadata.jsonl --no-sign-request
```

### 3. Verify installation

```python
from arxiv_metadata import ArxivMetadata

fetcher = ArxivMetadata()
df = fetcher.fetch(categories="math.AG", years=2024, limit=10)
print(f"Found {len(df)} papers")
```

## Development Setup

For contributing to the package:

```bash
# Clone repository
git clone https://github.com/yourusername/arxiv-metadata-fetcher.git
cd arxiv-metadata-fetcher

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ tests/

# Type checking
mypy src/
```

## Troubleshooting

### "No metadata file found" error

Make sure you've downloaded the metadata file and placed it in the correct location:
- Default: `~/.arxiv_cache/arxiv_metadata.jsonl`
- Or set `ARXIV_METADATA_PATH` environment variable

### Memory issues

If you're running into memory issues:
1. Use `stream()` instead of `fetch()` for large queries
2. Apply filters to reduce the result set
3. Use the `limit` parameter

### Slow performance

First run will be slow as it processes the entire metadata file. Subsequent runs use the cache and are much faster. Consider:
- Using more specific filters
- Filtering by recent years only
- Using `limit` parameter for testing

## Configuration

### Cache Settings

```python
from arxiv_metadata import ArxivMetadata

# Custom cache directory
fetcher = ArxivMetadata(cache_dir="/path/to/cache")

# Disable caching
fetcher = ArxivMetadata(use_cache=False)

# Custom cache expiry (in days)
fetcher = ArxivMetadata(cache_expiry_days=7)
```

### Clear Cache

```python
fetcher = ArxivMetadata()
fetcher.clear_cache()
```

## Next Steps

- Check out the [examples](examples/) directory for usage patterns
- Read the [API documentation](README.md#api-reference)
- See [advanced examples](examples/advanced_analysis.py) for inspiration
