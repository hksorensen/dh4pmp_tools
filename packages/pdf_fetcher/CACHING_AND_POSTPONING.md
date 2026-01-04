# Caching and Postponing in PDFFetcher

## Overview

PDFFetcher has comprehensive caching and postponing mechanisms to handle:
1. **Download tracking** - Never re-download successful PDFs
2. **Retry logic** - Smart retry with attempt limits
3. **Domain-level postponing** - Skip entire domains that hit Cloudflare/access issues
4. **DOI prefix postponing** - Skip entire publishers with access problems
5. **Persistent cache** - Survives between runs, shared globally

## Architecture

### 1. Download Metadata Database (`DownloadMetadataDB`)

**Location:** `pdf_fetcher/database.py`
**Storage:** SQLite database at `~/.pdf_fetcher/metadata.db` (centralized)

**Purpose:** Track individual DOI download attempts

**Features:**
- Records success/failure for each identifier
- Tracks attempt count to prevent infinite retries
- Stores error messages and Cloudflare detection
- `should_retry` flag for permanent failures (paywalls, 404s)
- File verification (checks if PDF still exists)

**Schema:**
```sql
CREATE TABLE download_results (
    identifier TEXT PRIMARY KEY,
    status TEXT NOT NULL,  -- 'success', 'failure', 'postponed'
    first_attempted DATETIME,
    last_attempted DATETIME,
    attempt_count INTEGER DEFAULT 1,
    should_retry BOOLEAN DEFAULT 1,
    publisher TEXT,
    strategy_used TEXT,
    landing_url TEXT,
    pdf_url TEXT,
    local_path TEXT,
    file_exists BOOLEAN DEFAULT 1,
    error_reason TEXT,
    cloudflare_detected BOOLEAN DEFAULT 0,
    updated_at DATETIME
)
```

**Usage:**
```python
fetcher = PDFFetcher()

# Check if should download (skips if already downloaded or max attempts reached)
should_dl, reason = fetcher.db.should_download('10.1007/paper123')

# Record success
fetcher.db.record_success(
    identifier='10.1007/paper123',
    local_path='/path/to/paper.pdf',
    publisher='Springer',
    strategy_used='SpringerStrategy'
)

# Record failure with Cloudflare detection
fetcher.db.record_failure(
    identifier='10.1234/paper456',
    error_reason='Cloudflare challenge detected',
    cloudflare_detected=True,
    should_retry=True  # Will be retried later
)

# Get stats
stats = fetcher.db.get_stats()
# {'total': 100, 'success': 75, 'failure': 20, 'postponed': 5}
```

### 2. Postponed Domains Cache (`PostponedDomainsCache`)

**Location:** `pdf_fetcher/postponed_cache.py`
**Storage:** SQLite database at `~/.cache/pdffetcher/postponed_domains.db` (global)

**Purpose:** Track domains and DOI prefixes that consistently fail (Cloudflare, 403 Forbidden, etc.)

**Features:**
- Domain-level blocking (e.g., skip ALL requests to `cloudflare-site.com`)
- DOI prefix blocking (e.g., skip ALL `10.xxxx/*` from blocked publisher)
- Persistent between runs (survives restarts)
- Global cache shared across all projects
- Automatic cache updates from download results
- Pre-filtering for batch operations

**Schema:**
```sql
CREATE TABLE postponed_domains (
    domain TEXT PRIMARY KEY,
    reason TEXT,  -- 'Cloudflare', '403 Forbidden', etc.
    first_detected TEXT,
    last_detected TEXT,
    detection_count INTEGER DEFAULT 1
)

CREATE TABLE postponed_doi_prefixes (
    prefix TEXT PRIMARY KEY,
    reason TEXT,
    first_detected TEXT,
    last_detected TEXT,
    detection_count INTEGER DEFAULT 1
)
```

**Usage:**
```python
from pdf_fetcher import PDFFetcher, PostponedDomainsCache

# Automatic (fetcher initializes cache automatically)
fetcher = PDFFetcher()
# Cache is at: fetcher.postponed_cache

# Manual (for advanced use)
cache = PostponedDomainsCache()

# Check if DOI should be skipped
should_skip, reason = cache.should_skip_doi('10.1234/paper')
# (True, "DOI prefix 10.1234 is postponed (Cloudflare/access issues)")

# Check if URL should be skipped
should_skip, reason = cache.should_skip_url('https://blocked-site.com/paper.pdf')
# (True, "Domain blocked-site.com is postponed (Cloudflare/access issues)")

# Pre-filter batch
identifiers = ['10.1007/a', '10.1234/b', '10.5678/c']
processable, blocked = cache.filter_batch(identifiers)
# processable: ['10.1007/a', '10.5678/c']
# blocked: ['10.1234/b']  # if 10.1234 prefix is in cache

# Add domain/prefix manually
cache.add_domain('cloudflare-site.com', reason='Cloudflare challenge')
cache.add_doi_prefix('10.1234', reason='403 Forbidden')

# Get stats
stats = cache.get_stats()
# {
#     'blocked_domains': 5,
#     'blocked_doi_prefixes': 3,
#     'domains': ['cloudflare-site.com', 'example.com', ...],
#     'doi_prefixes': ['10.1234', '10.5678', ...]
# }

# Clear cache (use with caution!)
cache.clear()
```

### 3. Strategy-Level Postpone Detection

**Location:** Individual strategy files (`strategies/springer.py`, `strategies/ams.py`, etc.)

**Purpose:** Each publisher strategy knows what errors should postpone vs. fail permanently

**Method:** `should_postpone(error_msg: str, html: str = "") -> bool`

**Logic:**
- **Postpone** (retry later): Cloudflare, 403 Forbidden, 503 Service Unavailable, rate limiting
- **Fail permanently** (don't retry): 404 Not Found, paywall, invalid DOI

**Example (SpringerStrategy):**
```python
def should_postpone(self, error_msg: str, html: str = "") -> bool:
    error_lower = error_msg.lower()

    # Cloudflare - postpone
    if 'cloudflare' in error_lower or 'cf-ray' in error_lower:
        return True

    # 403 Forbidden - postpone (might be temporary)
    if '403' in error_lower or 'forbidden' in error_lower:
        return True

    # 404 Not Found - fail permanently
    if '404' in error_lower or 'not found' in error_lower:
        return False

    # Default: don't postpone
    return False
```

## How It Works Together

### During Initialization:
```
PDFFetcher.__init__()
├── Initialize DownloadMetadataDB (~/.pdf_fetcher/metadata.db)
│   └── Load existing download history
└── Initialize PostponedDomainsCache (~/.cache/pdffetcher/postponed_domains.db)
    ├── Load blocked domains (e.g., 5 domains)
    └── Load blocked DOI prefixes (e.g., 3 prefixes)
```

### During Batch Download:
```
PDFFetcher.fetch_batch(['10.1007/a', '10.1234/b', '10.5678/c'])

1. Pre-filter with PostponedDomainsCache
   ├── Check each identifier against blocked domains/prefixes
   ├── Skip known blocked ones (e.g., '10.1234/b' if prefix in cache)
   └── Continue with: ['10.1007/a', '10.5678/c']

2. Check DownloadMetadataDB
   ├── Skip already downloaded successfully
   ├── Skip if max attempts reached
   └── Continue with identifiers needing download

3. Download PDFs
   ├── Try strategies for each identifier
   ├── Record success/failure in DownloadMetadataDB
   └── Strategies detect Cloudflare using should_postpone()

4. Update PostponedDomainsCache
   ├── Analyze results for new Cloudflare/403 errors
   ├── Extract domains from failed URLs
   ├── Extract DOI prefixes from failed DOIs
   └── Add to cache for next run
```

### Example Flow:

```python
from pdf_fetcher import PDFFetcher

fetcher = PDFFetcher()

# First run: 100 DOIs, 5 hit Cloudflare from 'blocked-publisher.com'
results = fetcher.fetch_batch(dois_100)

# PostponedDomainsCache automatically updated:
# - Added domain: 'blocked-publisher.com'
# - Added DOI prefix: '10.1234' (if consistent)

# Second run: 1000 DOIs including 200 from same publisher
results = fetcher.fetch_batch(dois_1000)

# Pre-filtering happens automatically:
# - 200 DOIs from '10.1234/*' are skipped immediately
# - No network calls made for known blocked publisher
# - Much faster, avoids wasting time on Cloudflare challenges
```

## Configuration

### Database Locations:

**Download metadata (per-user, centralized):**
- Default: `~/.pdf_fetcher/metadata.db`
- Override: `PDFFetcher(metadata_db_path='/custom/path.db')`

**Postponed domains cache (global):**
- Default: `~/.cache/pdffetcher/postponed_domains.db`
- Override: `PostponedDomainsCache(db_path='/custom/cache.db')`

### Retry Limits:

**Max attempts per identifier:**
- Default: 3 attempts
- Override: `PDFFetcher(max_attempts=5)`

**Postpone vs. Fail:**
- Postponed: Will be retried up to max_attempts
- Failed (should_retry=False): Never retried (404, paywall, etc.)

## Benefits

### 1. Efficiency
- **No redundant downloads**: Database tracks what's already downloaded
- **No wasted retries**: Cloudflare-blocked domains skipped on subsequent runs
- **Batch pre-filtering**: 200 blocked DOIs filtered in ~1ms vs. ~2000ms of failed attempts

### 2. Robustness
- **Persistent state**: Survives crashes, restarts
- **Smart retry**: Distinguishes temporary (Cloudflare) from permanent (404) failures
- **File verification**: Re-downloads if file was deleted

### 3. Observability
- **Clear logging**: Shows why identifiers are skipped
- **Statistics**: Total downloads, success rate, blocked domains
- **Debugging**: Error reasons and strategy attempts stored

## Example Logs:

```
INFO: Postponed domains cache initialized: 5 domains, 3 DOI prefixes
INFO: Pre-filtered 200/1000 identifiers (known postponed domains/prefixes)
INFO: Batch status check: 500 need download, 300 can skip
INFO: Downloaded 450/500 successfully (90% success rate)
INFO: Updated postponed cache: +2 domains, +1 DOI prefixes (total: 7 domains, 4 prefixes)
```

## Management

### View cache stats:
```python
from pdf_fetcher import PostponedDomainsCache

cache = PostponedDomainsCache()
stats = cache.get_stats()

print(f"Blocked domains: {stats['blocked_domains']}")
print(f"Blocked DOI prefixes: {stats['blocked_doi_prefixes']}")
print(f"Domains: {stats['domains']}")
print(f"DOI prefixes: {stats['doi_prefixes']}")
```

### Clear cache:
```python
cache = PostponedDomainsCache()
cache.clear()  # Use with caution! Removes all blocked domains/prefixes
```

### Inspect database directly:
```bash
# View postponed domains
sqlite3 ~/.cache/pdffetcher/postponed_domains.db "SELECT * FROM postponed_domains"

# View postponed DOI prefixes
sqlite3 ~/.cache/pdffetcher/postponed_domains.db "SELECT * FROM postponed_doi_prefixes"

# View download history
sqlite3 ~/.pdf_fetcher/metadata.db "SELECT identifier, status, cloudflare_detected FROM download_results WHERE cloudflare_detected=1"
```

## Database Storage (uses db_utils)

The PostponedDomainsCache uses `db_utils.SQLiteTableStorage` for persistence:

```python
from db_utils import SQLiteTableStorage

# Domain storage
self.domain_storage = SQLiteTableStorage(
    db_path='~/.cache/pdffetcher/postponed_domains.db',
    table_name='postponed_domains',
    column_ID='domain',
    ID_type=str,
    table_layout={
        'domain': 'TEXT PRIMARY KEY',
        'reason': 'TEXT',
        'first_detected': 'TEXT',
        'last_detected': 'TEXT',
        'detection_count': 'INTEGER DEFAULT 1'
    }
)
```

Benefits of using db_utils:
- ✅ Automatic schema management
- ✅ Safe concurrent access
- ✅ Pandas DataFrame integration
- ✅ Consistent API across packages
