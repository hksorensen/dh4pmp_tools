# PDF Fetcher Consolidation Summary

## What Was Done

Consolidated two versions of pdf_fetcher code into a single standalone package in `dh4pmp_tools/packages/pdf_fetcher/`.

### Removed from web_fetcher Package:

**Source Files (3 versions):**
- `web_fetcher/pdf_fetcher.py` (original version)
- `web_fetcher/pdf_fetcher_v2.py` (optimized version)
- `web_fetcher/pdf_fetcher_v2_optimized.py` (further optimized)
- Total: ~5,632 lines of code removed

**Documentation:**
- `OPTIMIZATIONS_IMPLEMENTED.md` - Detailed optimization strategies for v2
- `documentation/PDF_FETCHER_V2_README.md` - v2-specific documentation

**Examples:**
- `examples/pdf_fetcher_v2_example.py` - Example usage of v2 API

**Exports Removed from web_fetcher/__init__.py:**
- `PDFFetcher`, `DownloadStatus`, `DownloadResult`
- `RateLimiter`, `IdentifierNormalizer`, `PublisherDetector`
- `DOIResolver`, `PDFLinkFinder`, `DownloadManager`, `MetadataStore`
- `PDFFetcherConfig`, `load_config`, `create_example_config`
- `setup_logging`, `create_download_summary_log`, `CHANGELOG`

### New Standalone Package Structure:

```
packages/pdf_fetcher/
├── pdf_fetcher/
│   ├── __init__.py           # Exports: BasePDFFetcher, DownloadResult
│   ├── __version__.py        # Version info
│   ├── cli.py                # Command-line interface
│   ├── database.py           # SQLite metadata tracking
│   ├── fetcher.py            # Main BasePDFFetcher class
│   ├── utils.py              # Utilities (sanitize_doi_to_filename, etc.)
│   └── strategies/           # Publisher-specific download strategies
│       ├── __init__.py
│       ├── base.py
│       ├── unpaywall.py
│       ├── springer.py
│       ├── ams.py
│       └── mdpi.py
├── README.md
├── pyproject.toml
└── setup.py (if present)
```

## Key Features Removed (For Now)

### 1. Cloudflare Detection and Handling

**What was removed:**
- Automatic Cloudflare challenge detection
- Domain-based postponement (skip domains that hit Cloudflare)
- DOI prefix-based postponement
- Postponed domain caching between runs
- `set_postponed_domains()` method
- `_cloudflare_domains` and `_cloudflare_doi_prefixes` attributes

**Where it was used:**
- In `research/diagrams_in_arxiv/data/stages/pdf_fetching.py`:
  - Cached postponed domains to avoid retrying Cloudflare-protected sites
  - Extracted postponed domains from metadata.json
  - Pre-filtered DOIs matching cached postponed domains
  - Logged Cloudflare/403 errors with context

### 2. Advanced Identifier Normalization

**What was removed:**
- `IdentifierNormalizer` class with:
  - `normalize(identifier)` → (kind, doi, url)
  - `sanitize_for_filename(doi)`
  - Support for DOI URLs, resource URLs, plain DOIs
  - URL validation and cleaning

**Where it was used:**
- File existence checking (matching DOIs to filenames)
- Domain prediction for parallel processing
- Sorting by domain for session persistence

### 3. Complex Status Tracking

**What was removed:**
- `DownloadStatus` enum with values: SUCCESS, FAILURE, ALREADY_EXISTS, POSTPONED
- Rich DownloadResult with fields: `landing_url`, `pdf_url`, `cloudflare_detected`
- Detailed error context in results

**Where it was used:**
- Status comparison: `result.status.value == "success"`
- Creating typed results: `DownloadStatus.FAILURE`
- Tracking landing pages and PDF URLs for debugging

## Impact on Existing Code

### ⚠️ Breaking Changes:

**`research/diagrams_in_arxiv/data/stages/pdf_fetching.py`** will NOT work without updates:
- Imports `PDFFetcher` (now `BasePDFFetcher`)
- Uses `DownloadStatus` enum (now plain strings)
- Relies on Cloudflare domain tracking
- Uses `IdentifierNormalizer` extensively
- Accesses `result.landing_url`, `result.pdf_url` fields

**Migration required** for this file - estimated effort: 4-6 hours to refactor

### ✅ No Impact:

- Other packages in dh4pmp_tools (don't use pdf_fetcher)
- web_fetcher package (pdf_fetcher cleanly removed)

## How to Implement Cloudflare Handling in the Future

### Option 1: Lightweight Plugin System

Add Cloudflare detection as an optional plugin/extension:

```python
# In pdf_fetcher/extensions/cloudflare_handler.py

class CloudflareHandler:
    """
    Extension for detecting and managing Cloudflare-protected domains.

    Can be attached to BasePDFFetcher to add Cloudflare tracking.
    """

    def __init__(self, cache_file: str = "cloudflare_cache.json"):
        self.blocked_domains = set()
        self.blocked_doi_prefixes = set()
        self.cache_file = cache_file
        self._load_cache()

    def check_response(self, response, url: str) -> tuple[bool, str]:
        """
        Check if response indicates Cloudflare challenge.

        Returns:
            (is_cloudflare, reason)
        """
        if 'cf-ray' in response.headers:
            if response.status_code == 403:
                return True, "Cloudflare 403 Forbidden"
            if 'Checking if the site connection is secure' in response.text:
                return True, "Cloudflare challenge page detected"
        return False, ""

    def mark_domain_blocked(self, domain: str, reason: str = "Cloudflare"):
        """Add domain to blocked list and update cache."""
        self.blocked_domains.add(domain)
        self._save_cache()

    def mark_prefix_blocked(self, doi_prefix: str, reason: str = "Cloudflare"):
        """Add DOI prefix to blocked list and update cache."""
        self.blocked_doi_prefixes.add(doi_prefix)
        self._save_cache()

    def should_skip(self, identifier: str) -> tuple[bool, str]:
        """
        Check if identifier should be skipped due to known Cloudflare blocks.

        Returns:
            (should_skip, reason)
        """
        # Parse identifier to extract domain/DOI prefix
        # Check against blocked lists
        # Return skip decision
        pass

# Usage:
from pdf_fetcher import BasePDFFetcher
from pdf_fetcher.extensions import CloudflareHandler

fetcher = BasePDFFetcher(...)
cf_handler = CloudflareHandler(cache_file="postponed_domains.json")

# Hook into fetch workflow
for doi in dois:
    should_skip, reason = cf_handler.should_skip(doi)
    if should_skip:
        print(f"Skipping {doi}: {reason}")
        continue

    result = fetcher.fetch(doi)

    # Check result for Cloudflare
    if result.error_reason and "403" in result.error_reason:
        # Extract domain and mark as blocked
        cf_handler.mark_domain_blocked(extract_domain(doi))
```

### Option 2: Middleware/Hook System

Add a generic middleware system to BasePDFFetcher:

```python
# In pdf_fetcher/fetcher.py

class BasePDFFetcher:
    def __init__(self, ..., middlewares=None):
        self.middlewares = middlewares or []

    def fetch(self, identifier: str) -> DownloadResult:
        # Pre-fetch hooks
        for mw in self.middlewares:
            skip, reason = mw.before_fetch(identifier)
            if skip:
                return DownloadResult(
                    identifier=identifier,
                    status="skipped",
                    error_reason=reason
                )

        # Normal fetch logic
        result = self._do_fetch(identifier)

        # Post-fetch hooks
        for mw in self.middlewares:
            mw.after_fetch(identifier, result)

        return result

# Cloudflare middleware implementation:
class CloudflareMiddleware:
    def before_fetch(self, identifier: str) -> tuple[bool, str]:
        # Check if identifier matches blocked domain/prefix
        pass

    def after_fetch(self, identifier: str, result: DownloadResult):
        # Check result for Cloudflare indicators
        # Update blocked lists if detected
        pass

# Usage:
cf_middleware = CloudflareMiddleware(cache_file="postponed_domains.json")
fetcher = BasePDFFetcher(..., middlewares=[cf_middleware])
```

### Option 3: Result Analyzer Pattern

Keep fetcher simple, analyze results separately:

```python
# In pdf_fetcher/analysis/cloudflare_detector.py

class CloudflareDetector:
    """
    Analyzes DownloadResult objects to detect Cloudflare patterns.
    Maintains blocked domain/prefix lists.
    """

    def analyze_results(self, results: List[DownloadResult]) -> Dict[str, Any]:
        """
        Analyze batch of results for Cloudflare patterns.

        Returns summary with newly detected domains/prefixes.
        """
        newly_blocked_domains = set()
        newly_blocked_prefixes = set()

        for result in results:
            if self._is_cloudflare_error(result):
                domain = self._extract_domain(result.identifier)
                if domain:
                    newly_blocked_domains.add(domain)

                prefix = self._extract_doi_prefix(result.identifier)
                if prefix:
                    newly_blocked_prefixes.add(prefix)

        return {
            'newly_blocked_domains': newly_blocked_domains,
            'newly_blocked_prefixes': newly_blocked_prefixes,
            'total_blocked_domains': self.blocked_domains,
            'total_blocked_prefixes': self.blocked_doi_prefixes
        }

    def filter_batch(self, identifiers: List[str]) -> tuple[List[str], List[str]]:
        """
        Split identifiers into (processable, blocked).
        """
        processable = []
        blocked = []

        for ident in identifiers:
            if self._should_skip(ident):
                blocked.append(ident)
            else:
                processable.append(ident)

        return processable, blocked

# Usage in pipeline:
detector = CloudflareDetector(cache_file="postponed_domains.json")

# Pre-filter before fetching
processable_dois, blocked_dois = detector.filter_batch(all_dois)
print(f"Skipping {len(blocked_dois)} known Cloudflare-blocked DOIs")

# Fetch processable ones
results = fetcher.fetch_batch(processable_dois)

# Analyze results to update blocked lists
analysis = detector.analyze_results(results)
print(f"Found {len(analysis['newly_blocked_domains'])} new Cloudflare domains")
```

## Recommended Approach

**Option 3 (Result Analyzer)** is cleanest because:

1. **Separation of concerns**: Fetcher focuses on downloading, analyzer focuses on pattern detection
2. **Easy to test**: Can test Cloudflare detection independently
3. **Flexible**: Can swap in different detection strategies
4. **Backward compatible**: Existing code can add analyzer without changing fetcher
5. **Cacheable**: Analyzer can manage its own cache file
6. **Extensible**: Can add other analyzers (paywall detection, rate limiting, etc.)

## Migration Timeline

### Phase 1 (Complete ✓):
- ✓ Consolidate pdf_fetcher to standalone package
- ✓ Remove old versions from web_fetcher
- ✓ Document what was removed

### Phase 2 (TODO):
- [ ] Implement CloudflareDetector analyzer class
- [ ] Add identifier normalization utilities (sanitize_doi_to_filename, etc.)
- [ ] Test analyzer with sample data

### Phase 3 (TODO):
- [ ] Migrate pdf_fetching.py to use new pdf_fetcher + CloudflareDetector
- [ ] Verify all features still work
- [ ] Update documentation

### Phase 4 (Optional):
- [ ] Add middleware system for other extensions
- [ ] Create paywall detector
- [ ] Add rate limiting middleware
