# Optimization Strategies for 50K PDF Downloads

## Current Bottlenecks

1. **Sequential processing** - One PDF at a time
2. **Selenium overhead** - Browser automation is slow (~2-10s per page)
3. **Fixed delays** - Even with zero delays on domain switch, still delays within same domain
4. **Redundant checks** - File existence checked after normalization, not before
5. **No connection pooling** - New connections for each request
6. **Landing page navigation** - Even when Crossref provides direct PDF URL

## Optimization Strategies (Ranked by Impact)

### 🚀 **High Impact - Implement First**

#### 1. **Pre-filter Already Downloaded Files** ⭐⭐⭐⭐⭐
**Impact:** Can skip 10-50% of work immediately
**Effort:** Low
**Implementation:**
```python
def prefilter_existing(identifiers: List[str], pdf_dir: Path) -> Tuple[List[str], List[str]]:
    """Check which PDFs already exist before any network calls."""
    existing = []
    to_download = []
    
    for identifier in identifiers:
        kind, doi, url = IdentifierNormalizer.normalize(identifier)
        if doi:
            sanitized = IdentifierNormalizer.sanitize_for_filename(doi)
        else:
            sanitized = hashlib.md5(url.encode()).hexdigest()[:16]
        
        pdf_path = pdf_dir / f"{sanitized}.pdf"
        if pdf_path.exists():
            try:
                if pdf_path.read_bytes()[:4] == b'%PDF':
                    existing.append(identifier)
                    continue
            except:
                pass
        
        to_download.append(identifier)
    
    return existing, to_download
```

#### 2. **Parallel Processing by Domain** ⭐⭐⭐⭐⭐
**Impact:** 5-10x speedup for multi-domain batches
**Effort:** Medium
**Implementation:**
- Process different domains in parallel (ThreadPoolExecutor or ProcessPoolExecutor)
- Each domain gets its own worker with session persistence
- Limit concurrent Selenium drivers (e.g., max 5-10)
- Use asyncio for I/O-bound operations (requests, not Selenium)

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

def download_batch_parallel(self, identifiers, max_workers=5):
    # Group by domain
    by_domain = defaultdict(list)
    for identifier in identifiers:
        domain = self._predict_domain(identifier)
        by_domain[domain].append(identifier)
    
    # Process each domain in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(self._download_domain_batch, domain, ids): domain
            for domain, ids in by_domain.items()
        }
        
        for future in as_completed(futures):
            domain = futures[future]
            results = future.result()
            # Collect results
```

#### 3. **Aggressive Crossref Usage** ⭐⭐⭐⭐
**Impact:** Skip landing page navigation for 30-40% of DOIs
**Effort:** Low
**Current:** Already implemented, but could optimize:
- Batch Crossref lookups (if API supports it)
- Cache Crossref results more aggressively
- Pre-fetch Crossref metadata for all DOIs before starting downloads

#### 4. **Cache Landing Page Resolutions** ⭐⭐⭐⭐
**Impact:** Skip DOI→landing URL resolution for repeated DOIs
**Effort:** Low
**Implementation:**
- Cache DOI → landing URL mappings
- Check cache before resolving
- Cache expires rarely (DOIs don't change)

#### 5. **Reduce Selenium Usage** ⭐⭐⭐⭐
**Impact:** 5-10x faster for requests-only downloads
**Effort:** Medium
**Strategies:**
- Only use Selenium when Crossref fails AND direct requests fail
- Use Selenium only for Cloudflare-protected sites (detect early)
- Reuse Selenium driver longer (already doing this)
- Disable images/JS in Selenium when not needed

### ⚡ **Medium Impact - Good ROI**

#### 6. **Connection Pooling & Keep-Alive** ⭐⭐⭐
**Impact:** 20-30% faster for requests-based downloads
**Effort:** Low
**Implementation:**
```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.poolmanager import PoolManager

# Use connection pooling
adapter = HTTPAdapter(
    pool_connections=10,  # Number of connection pools
    pool_maxsize=20,      # Max connections per pool
    max_retries=Retry(total=3, backoff_factor=1)
)
session.mount('http://', adapter)
session.mount('https://', adapter)
```

#### 7. **Smart Delay Reduction** ⭐⭐⭐
**Impact:** 30-50% faster for same-domain batches
**Effort:** Low
**Current:** Zero delay on domain switch ✅
**Enhancement:**
- Adaptive delays: Start with small delay, increase if rate-limited
- Track success rate per domain, reduce delays for reliable domains
- Skip delays entirely for direct PDF URLs (no landing page)

#### 8. **Batch Pre-processing** ⭐⭐⭐
**Impact:** Better organization, faster overall
**Effort:** Medium
**Implementation:**
```python
def preprocess_batch(identifiers):
    # 1. Pre-filter existing files
    existing, to_download = prefilter_existing(identifiers, pdf_dir)
    
    # 2. Pre-resolve all DOIs to domains
    domain_map = {}
    for identifier in to_download:
        domain = predict_domain(identifier)
        domain_map[identifier] = domain
    
    # 3. Pre-fetch Crossref metadata (batch if possible)
    crossref_results = {}
    dois = [id for id in to_download if id.startswith('10.')]
    for doi in dois:
        crossref_results[doi] = crossref_fetcher.fetch_by_doi(doi)
    
    # 4. Sort by domain (already doing this)
    sorted_ids = sort_by_domain(to_download, domain_map)
    
    return existing, sorted_ids, crossref_results
```

#### 9. **Skip Known Failures Early** ⭐⭐⭐
**Impact:** Avoid wasted time on impossible downloads
**Effort:** Low
**Implementation:**
- Maintain a "blacklist" of known Cloudflare-protected domains
- Skip domains that consistently fail
- Track failure patterns in metadata, skip on retry

#### 10. **Optimize Selenium Page Load Detection** ⭐⭐
**Impact:** 20-30% faster Selenium operations
**Effort:** Medium
**Current:** Using `time.sleep(2)` for page loads
**Better:**
- Use WebDriverWait with expected conditions
- Check for specific elements instead of fixed delays
- Detect PDF URLs faster (check page source before full load)

### 🔧 **Low Impact - Nice to Have**

#### 11. **HTTP/2 Support** ⭐⭐
**Impact:** 10-20% faster for requests
**Effort:** Medium
**Implementation:**
```python
# Use httpx instead of requests for HTTP/2
import httpx
client = httpx.Client(http2=True)
```

#### 12. **Compression** ⭐
**Impact:** Faster transfers for large PDFs
**Effort:** Low
**Implementation:**
```python
headers = {'Accept-Encoding': 'gzip, deflate, br'}
# requests handles decompression automatically
```

#### 13. **Metadata Pre-loading** ⭐
**Impact:** Faster status checks
**Effort:** Low
**Implementation:**
- Load metadata.json once at start
- Keep in memory during batch
- Write once at end (or periodically)

## Recommended Implementation Order

### Phase 1: Quick Wins (1-2 days)
1. ✅ Pre-filter existing files (before any network calls)
2. ✅ Cache landing page resolutions
3. ✅ Connection pooling
4. ✅ Skip delays for direct PDF URLs

### Phase 2: Parallel Processing (3-5 days)
5. ✅ Parallel processing by domain
6. ✅ Limit concurrent Selenium drivers
7. ✅ Better error handling for parallel execution

### Phase 3: Advanced Optimizations (1 week)
8. ✅ Batch Crossref pre-fetching
9. ✅ Smart delay reduction
10. ✅ Selenium optimization

## Expected Performance Gains

| Optimization | Speedup | Cumulative |
|-------------|---------|------------|
| Pre-filter existing | 1.2-1.5x | 1.2-1.5x |
| Parallel by domain | 5-10x | 6-15x |
| Aggressive Crossref | 1.3-1.4x | 8-21x |
| Cache resolutions | 1.1-1.2x | 9-25x |
| Reduce Selenium | 1.5-2x | 13-50x |
| Connection pooling | 1.2-1.3x | 16-65x |

**Realistic expectation:** 10-20x speedup with Phase 1 + Phase 2

## Example: 50K PDFs

**Current (sequential):**
- ~2-5 seconds per PDF (average)
- 50,000 × 3s = 150,000s = **~42 hours**

**With optimizations:**
- Pre-filter: Skip 20% = 40,000 remaining
- Parallel (5 workers): 5x speedup
- Other optimizations: 2x speedup
- 40,000 × 3s / (5 × 2) = 12,000s = **~3.3 hours**

**Best case (aggressive parallel):**
- 10 workers, 3x from other optimizations
- 40,000 × 3s / (10 × 3) = 4,000s = **~1.1 hours**

## Implementation Notes

### Thread Safety
- Selenium drivers are NOT thread-safe - one per thread
- Requests session can be shared (it's thread-safe)
- Metadata store needs locking for concurrent writes

### Resource Limits
- Limit concurrent Selenium drivers (memory intensive)
- Limit concurrent network requests per domain
- Monitor system resources (CPU, memory, network)

### Error Handling
- Parallel execution needs robust error handling
- Track failures per domain
- Retry logic needs to work with parallel execution

## Code Structure

```python
class OptimizedPDFFetcher(PDFFetcher):
    def __init__(self, *args, max_workers=5, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_workers = max_workers
        self.landing_url_cache = {}  # DOI -> landing URL
        self.crossref_cache = {}     # DOI -> PDF URL
    
    def download_batch_optimized(self, identifiers):
        # 1. Pre-filter
        existing, to_download = self._prefilter(identifiers)
        
        # 2. Pre-resolve domains
        domain_groups = self._group_by_domain(to_download)
        
        # 3. Parallel process
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Process each domain group in parallel
            ...
```

