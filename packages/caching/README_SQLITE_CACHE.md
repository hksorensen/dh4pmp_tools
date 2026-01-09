# SQLiteLocalCache - Fast Metadata Storage for Large Caches

## Overview

`SQLiteLocalCache` is a drop-in replacement for `LocalCache` that uses SQLite for metadata storage instead of JSON. This provides significant performance improvements for large caches (1000+ entries).

## When to Use SQLiteLocalCache

**Use SQLiteLocalCache when:**
- Cache has 500+ entries
- You need concurrent access from multiple processes
- Metadata file I/O is a bottleneck
- You're doing batch operations that scan all cached queries

**Stick with LocalCache when:**
- Cache has <100 entries
- Simple single-process usage
- Startup time matters (SQLiteLocalCache has slightly higher initialization cost)

## Performance Characteristics

| Operation | LocalCache | SQLiteLocalCache | Winner |
|-----------|------------|------------------|--------|
| Store (small cache) | Fast | Slightly slower | LocalCache |
| Store (large cache 1000+) | Slow (full JSON rewrite) | Fast (indexed insert) | **SQLite** |
| has() single call | Very fast (dict lookup) | Fast (indexed query) | LocalCache |
| list_queries() large cache | Slow (parse entire JSON) | Fast (SQL query) | **SQLite** |
| get_ID_list() | O(n) iteration | O(1) indexed query | **SQLite** |
| Concurrent access | Race conditions possible | Thread-safe | **SQLite** |

## Usage

### Basic Usage (Drop-in Replacement)

```python
# Before
from caching import LocalCache
cache = LocalCache(cache_dir="~/.cache/my_cache")

# After
from caching import SQLiteLocalCache
cache = SQLiteLocalCache(cache_dir="~/.cache/my_cache")

# API is identical
cache.store("query1", dataframe)
result = cache.get("query1")
queries = cache.list_queries()
```

### Crossref Client Integration

For `crossref_client.py` and `base_client.py`:

```python
# In crossref_client.py or base_client.py
from caching import SQLiteLocalCache

class CrossrefBibliographicFetcher(BaseSearchFetcher):
    def __init__(self, ...):
        # Replace LocalCache with SQLiteLocalCache
        self.cache = SQLiteLocalCache(
            cache_dir=cache_dir,
            compression=True,
            max_age_days=365
        )
```

### Migration from LocalCache

Use the migration script to convert existing caches:

```bash
# Migrate existing cache
cd /Users/fvb832/Documents/dh4pmp_tools/packages/caching
python migrate_to_sqlite.py ~/.cache/my_cache --backup

# Dry run to see what would happen
python migrate_to_sqlite.py ~/.cache/my_cache --dry-run
```

The migration script:
- Converts `_metadata.json` to `_metadata.db`
- Keeps pickle files unchanged
- Optionally creates backup
- Validates migration success

## API Reference

All methods are identical to `LocalCache`:

### `store(query: str, data: pd.DataFrame, **meta_kwargs)`
Store DataFrame in cache with metadata.

```python
cache.store("my_query", df, source="crossref", retry_count=0)
```

### `get(query: str) -> Optional[pd.DataFrame]`
Retrieve cached DataFrame.

```python
df = cache.get("my_query")
if df is not None:
    print(f"Cache hit: {len(df)} rows")
```

### `has(query: str) -> bool`
Check if query exists and is not expired.

```python
if cache.has("my_query"):
    print("Query is cached")
```

### `list_queries() -> List[Dict]`
List all cached queries with metadata.

```python
for item in cache.list_queries():
    print(f"{item['query']}: {item['num_rows']} rows, {item['timestamp']}")
```

### `get_ID_list() -> List[str]`
Get list of all cached query strings (fast indexed query).

```python
cached_queries = set(cache.get_ID_list())
queries_to_fetch = [q for q in all_queries if q not in cached_queries]
```

### `delete(query: str)`
Remove query from cache.

```python
cache.delete("my_query")
```

### `clear_expired()`
Remove expired entries (based on `max_age_days`).

```python
cache.clear_expired()
```

### `clear_all()`
Remove all cached data.

```python
cache.clear_all()
```

### `get_stats() -> Dict`
Get cache statistics.

```python
stats = cache.get_stats()
print(f"Entries: {stats['num_entries']}")
print(f"Size: {stats['total_size_mb']:.2f} MB")
```

## Implementation Details

### Storage Structure

```
cache_dir/
├── _metadata.db              # SQLite database (metadata)
├── query_prefix_abc123.pkl.gz  # Pickle file (DataFrame data)
├── query_prefix_def456.pkl.gz
└── ...
```

### SQLite Schema

```sql
CREATE TABLE cache_metadata (
    cache_key TEXT PRIMARY KEY,      -- MD5 hash of query
    query TEXT,                      -- Original query string
    timestamp TEXT,                  -- ISO format timestamp
    num_rows INTEGER,                -- DataFrame row count
    extra_metadata TEXT              -- JSON-encoded extra kwargs
);

CREATE INDEX idx_timestamp ON cache_metadata(timestamp);
```

### Key Features

1. **Efficient Upsert**: Uses `INSERT OR REPLACE` for atomic updates
2. **Indexed Queries**: Fast lookups on cache_key and timestamp
3. **Thread-Safe**: SQLite handles concurrent access
4. **Backward Compatible**: Same API as LocalCache

## Performance Tips

### 1. Batch Operations

Instead of checking cache for each query individually:

```python
# Slow (N queries to SQLite)
for query in queries:
    if cache.has(query):
        results.append(cache.get(query))

# Fast (1 query to SQLite)
cached_queries = set(cache.get_ID_list())
for query in queries:
    if query in cached_queries:
        results.append(cache.get(query))
```

### 2. Connection Pooling

For heavy concurrent usage, consider connection pooling (future enhancement).

### 3. Periodic Maintenance

Run `clear_expired()` periodically to remove old entries:

```python
# In a cron job or at startup
cache.clear_expired()
```

## Troubleshooting

### Issue: "no such table: cache_metadata"

**Cause**: Database file exists but table wasn't created.

**Solution**: Delete `_metadata.db` and let SQLiteLocalCache recreate it:

```bash
rm ~/.cache/my_cache/_metadata.db
```

### Issue: Performance not better than LocalCache

**Cause**: Cache might be too small (<500 entries).

**Solution**: SQLiteLocalCache shines with large caches. For small caches, LocalCache is faster.

### Issue: Migration failed

**Cause**: Corrupted `_metadata.json` file.

**Solution**: Check JSON file format:

```bash
python -m json.tool ~/.cache/my_cache/_metadata.json
```

## Comparison with LocalCache

| Feature | LocalCache | SQLiteLocalCache |
|---------|-----------|------------------|
| Metadata Storage | JSON file | SQLite database |
| Data Storage | Pickle files | Pickle files |
| Concurrent Access | Not safe | Thread-safe |
| Large Cache Performance | Degrades | Scales well |
| Startup Time | Fast | Slightly slower |
| Dependencies | None | SQLite (built-in) |

## Future Enhancements

Potential improvements:
- Connection pooling for concurrent access
- In-memory cache layer (LRU)
- Async write operations
- Store DataFrames in SQLite BLOBs (Option 2)
- Automatic migration from LocalCache

## Example: Crossref Client Usage

```python
from caching import SQLiteLocalCache
from api_clients import CrossrefBibliographicFetcher

# Create fetcher with SQLite cache
fetcher = CrossrefBibliographicFetcher(
    cache_dir="~/.cache/crossref_cache"
)

# Replace internal cache
fetcher.cache = SQLiteLocalCache(
    cache_dir="~/.cache/crossref_cache",
    compression=True,
    max_age_days=365  # Cache for 1 year
)

# Use normally
citations = ["10.1234/example", "10.5678/another"]
results = fetcher.provide(citations)

# Check cache stats
stats = fetcher.cache.get_stats()
print(f"Cached {stats['num_entries']} entries ({stats['total_size_mb']:.1f} MB)")
```

## See Also

- `LocalCache` - Original JSON-based cache
- `SQLiteStringCache` - SQLite cache for string/dict data
- `db_utils.SQLiteTableStorage` - Underlying storage layer
- `migrate_to_sqlite.py` - Migration script

## Support

For issues or questions:
- Check existing cache with: `cache.get_stats()`
- Run migration in dry-run mode first
- Compare performance with `benchmark_cache.py`
