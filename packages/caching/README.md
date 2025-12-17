# Caching

File-based and string-based caching utilities for API data and status tracking.

## Features

Two complementary caching systems:

### LocalCache - Heavy Data Storage
- Compressed pickle storage for DataFrames
- Efficient for large API responses
- MD5-keyed file names
- Metadata tracking
- Optional expiration

### StringCache - Lightweight Status Tracking
- JSON storage for string data
- Status field for tracking state (pending/completed/failed)
- Perfect for tracking API processing
- Query by status
- Human-readable format

## Installation

```bash
pip install -e .

# Optional: For config.yaml support
pip install -e .[yaml]
```

## Path Configuration

The caching package uses a centralized path configuration system that:
- Uses XDG Base Directory defaults (Unix standard)
- Supports optional `config.yaml` override at repo root
- Automatically creates directories as needed

### Default Paths (XDG Standard)

Without any configuration:
- Cache: `~/.cache/dh4pmp/`
- Data: `~/.local/share/dh4pmp/`
- Results: `~/results/dh4pmp/`

### Custom Configuration

Create `config.yaml` at the repo root (copy from `config.example.yaml`):

```yaml
paths:
  cache_dir: ~/my_custom_cache
  data_dir: ~/my_data
  results_dir: ~/my_results
```

### Using Path Configuration

```python
from caching import get_cache_dir, get_data_dir, get_results_dir

# Get configured paths
cache = get_cache_dir()      # Creates directory if needed
data = get_data_dir()
results = get_results_dir()

# Use in your code
import pandas as pd
df.to_csv(results / 'output.csv')

# Print current configuration
from caching import print_path_config
print_path_config()
```

### Automatic Path Usage

`LocalCache` and `StringCache` use configured paths by default:

```python
from caching import LocalCache, StringCache

# Uses ~/.cache/dh4pmp/local_cache/ (or configured cache_dir)
cache = LocalCache()

# Uses ~/.cache/dh4pmp/string_cache.json (or configured)
status = StringCache()

# Override if needed
cache = LocalCache(cache_dir="/custom/path")
```

## Usage

### LocalCache Example

```python
from caching import LocalCache
import pandas as pd

# Create cache
cache = LocalCache(cache_dir="~/.cache/my_data")

# Store DataFrame
query = "TITLE-ABS-KEY(machine learning)"
data = pd.DataFrame({'ID': [1, 2, 3], 'title': ['A', 'B', 'C']})
cache.store(query, data)

# Retrieve
cached_data = cache.get(query)

# Check if cached
if cache.has(query):
    print("Found in cache!")

# Get statistics
stats = cache.get_stats()
print(f"Cache size: {stats['total_size_mb']:.2f} MB")
```

### StringCache Example

```python
from caching import StringCache

# Create cache
cache = StringCache(cache_file="~/.cache/doi_status.json")

# Mark as pending
cache.set("10.1234/example", "", status="pending")

# Later, store result
cache.set("10.1234/example", "abstract text here", status="completed")

# Or mark failure
cache.set("10.5678/error", "404 not found", status="failed")

# Get only completed
result = cache.get("10.1234/example", status="completed")

# List all failed entries
failed_dois = cache.list_keys(status="failed")

# Get full entry with metadata
entry = cache.get_entry("10.1234/example")
print(f"Status: {entry['status']}, Time: {entry['timestamp']}")
```

### Combined Workflow

```python
from caching import StringCache, LocalCache
import pandas as pd

# Track DOI resolution status
status_cache = StringCache("~/.cache/doi_status.json")

# Store actual abstract data
data_cache = LocalCache("~/.cache/abstracts")

# Processing workflow
for doi in dois:
    if status_cache.has(doi, status="completed"):
        # Already processed
        abstract = data_cache.get(f"abstract:{doi}")
        continue
    
    try:
        # Mark as pending
        status_cache.set(doi, "", status="pending")
        
        # Fetch abstract
        abstract = fetch_abstract(doi)
        
        # Store result
        df = pd.DataFrame([{'doi': doi, 'abstract': abstract}])
        data_cache.store(f"abstract:{doi}", df)
        status_cache.set(doi, abstract, status="completed")
        
    except Exception as e:
        status_cache.set(doi, str(e), status="failed")

# Later, retry only failed
for doi in status_cache.list_keys(status="failed"):
    # Retry logic here
    pass
```

## API Reference

### LocalCache

- `has(query)` - Check if query is cached
- `get(query)` - Retrieve cached DataFrame
- `store(query, data, **metadata)` - Store DataFrame
- `delete(query)` - Remove from cache
- `list_queries()` - List all cached queries
- `clear_expired()` - Remove expired entries
- `clear_all()` - Clear entire cache
- `get_stats()` - Get cache statistics

### StringCache

- `has(key, status=None)` - Check if key exists
- `get(key, default=None, status=None)` - Get cached value
- `get_entry(key)` - Get full entry with metadata
- `set(key, value, status="completed", **extra)` - Store value
- `update_status(key, status)` - Update entry status
- `delete(key)` - Remove key
- `list_keys(status=None)` - List keys (optionally filtered)
- `list_entries(status=None)` - List entries with metadata
- `clear_expired()` - Remove expired entries
- `clear_status(status)` - Remove entries with given status
- `clear_all()` - Clear entire cache
- `get_stats()` - Get cache statistics

## Configuration

### LocalCache Options

```python
cache = LocalCache(
    cache_dir="~/.cache/my_data",
    compression=True,           # Use gzip compression
    max_age_days=30,           # Expire after 30 days (None = never)
)
```

### StringCache Options

```python
cache = StringCache(
    cache_file="~/.cache/status.json",
    max_age_days=7,            # Expire after 7 days (None = never)
    auto_save=True,            # Save after each modification
)
```

## Design Principles

- **Single-user optimized**: No database overhead
- **Human-readable**: JSON for strings, inspectable metadata
- **Fail-safe**: Corrupt cache entries don't crash your program
- **Flexible**: Extend with custom metadata fields
- **Portable**: Just copy the cache directory

## License

MIT
