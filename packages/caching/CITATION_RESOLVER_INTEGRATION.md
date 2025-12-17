# StringCache Integration for Your Citation Resolver

Complete step-by-step guide for adding StringCache to your `citation_resolver.py`.

## What Gets Cached

Your citation resolver will cache **three things**:

1. **Status**: Which citations are pending/completed/failed (StringCache)
2. **LLM Responses**: The parsed citation data from LLM (JSON file)
3. **Final Results**: Complete resolution results including DOI (JSON file)

## Benefits

- ✅ **Skip completed citations** - Instant if already resolved
- ✅ **Resume interrupted processing** - Pick up where you left off
- ✅ **Avoid redundant LLM calls** - LLM responses cached separately
- ✅ **Track failures** - Know which citations failed and why
- ✅ **Retry failed citations** - Easy retry mechanism

## Step-by-Step Integration

### Step 1: Add Imports

Add these at the top of `citation_resolver.py`:

```python
from caching import StringCache, get_cache_dir
from pathlib import Path
import json
import hashlib
```

### Step 2: Add Cache Key Helper

Add this helper function after your imports:

```python
def get_citation_cache_key(citation: str) -> str:
    """
    Generate a stable cache key for a citation.
    Uses MD5 hash of citation string to create short, consistent key.
    """
    return hashlib.md5(citation.encode('utf-8')).hexdigest()
```

### Step 3: Update `__init__` Method

Modify the `CitationResolver.__init__` method to add caching:

```python
def __init__(
    self,
    citation_parser,
    scimago_file: Path,
    confidence_threshold: float = 80.0,
    mailto: str = None,
    cache_dir: Path = None,  # NEW PARAMETER
):
    """
    Args:
        citation_parser: LLM-based citation parser
        scimago_file: Path to Scimago journal data file
        confidence_threshold: Minimum Crossref score to accept
        mailto: Email for Crossref polite pool
        cache_dir: Directory for cache files (default: uses path_config)
    """
    self.parser = citation_parser
    self.confidence_threshold = confidence_threshold
    self.base_url = "https://api.crossref.org/works"
    self.headers = {
        "User-Agent": (
            f"CitationResolver/2.0 (mailto:{mailto})"
            if mailto
            else "CitationResolver/2.0"
        )
    }
    self.rate_limit_delay = 0.05 if mailto else 0.1

    # Initialize ISSN lookup
    self.issn_lookup = JournalISSNLookup(scimago_file)

    # ====================================================================
    # NEW: Initialize caches
    # ====================================================================
    
    if cache_dir is None:
        cache_dir = get_cache_dir() / "citation_resolver"
    else:
        cache_dir = Path(cache_dir)
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Status cache: track which citations have been processed
    self.status_cache = StringCache(
        cache_file=cache_dir / "resolution_status.json"
    )
    
    # LLM response cache: store LLM parsing results
    self.llm_cache_file = cache_dir / "llm_responses.json"
    if not self.llm_cache_file.exists():
        self.llm_cache_file.write_text("{}")
    
    # Results cache: store final resolution results
    self.results_cache_file = cache_dir / "resolution_results.json"
    if not self.results_cache_file.exists():
        self.results_cache_file.write_text("{}")
    
    logger.info(f"Citation resolver cache directory: {cache_dir}")
```

### Step 4: Add Cache Methods

Add these new methods to the `CitationResolver` class:

```python
def _get_llm_response(self, citation: str) -> Optional[Dict]:
    """
    Get cached LLM response or call LLM and cache result.
    
    Args:
        citation: Citation string to parse
        
    Returns:
        Parsed citation dict or None on error
    """
    cache_key = get_citation_cache_key(citation)
    
    # Check cache
    llm_cache = json.loads(self.llm_cache_file.read_text())
    if cache_key in llm_cache:
        logger.info(f"  Using cached LLM response")
        return llm_cache[cache_key]
    
    # Call LLM
    try:
        logger.info(f"  Calling LLM to parse citation...")
        parsed = self.parser.parse_citation(citation)
        
        # Cache the response
        llm_cache[cache_key] = parsed
        self.llm_cache_file.write_text(json.dumps(llm_cache, indent=2))
        
        return parsed
        
    except Exception as e:
        logger.error(f"  LLM parsing failed: {e}")
        return None

def _get_cached_result(self, citation: str) -> Optional[Dict]:
    """Get cached resolution result if available."""
    cache_key = get_citation_cache_key(citation)
    results_cache = json.loads(self.results_cache_file.read_text())
    return results_cache.get(cache_key)

def _save_result(self, citation: str, result: Dict):
    """Save resolution result to cache."""
    cache_key = get_citation_cache_key(citation)
    results_cache = json.loads(self.results_cache_file.read_text())
    results_cache[cache_key] = result
    self.results_cache_file.write_text(json.dumps(results_cache, indent=2))
```

### Step 5: Update `resolve_citation` Method

Replace your existing `resolve_citation` method (lines 939-982) with:

```python
def resolve_citation(self, citation: str, use_cache: bool = True) -> Dict:
    """
    Resolve a citation to DOI using two-stage approach with caching.

    Stage 1: Parse with LLM, query Crossref with structured data
    Stage 2: If Stage 1 fails, try raw citation string

    Args:
        citation: Raw citation string
        use_cache: Whether to use cached results (default: True)

    Returns:
        Dict with doi, score, title, match_method, parsed_citation, crossref_record
    """
    # Check status cache
    status = self.status_cache.get_status(citation)
    
    if use_cache and status == "completed":
        logger.info(f"Citation already resolved (cached)")
        cached = self._get_cached_result(citation)
        if cached:
            return cached
    
    if use_cache and status == "failed":
        logger.warning(f"Citation previously failed, skipping")
        return {
            "doi": None,
            "score": 0,
            "title": None,
            "match_method": None,
            "parsed_citation": None,
            "crossref_record": None,
            "error": "Previously failed"
        }
    
    # Mark as pending
    self.status_cache.set_pending(citation)
    
    result = {
        "doi": None,
        "score": 0,
        "title": None,
        "match_method": None,
        "parsed_citation": None,
        "crossref_record": None,
    }

    try:
        # Stage 1: Parse with LLM (uses LLM cache)
        logger.info(f"Parsing citation with LLM...")
        parsed = self._get_llm_response(citation)  # CHANGED: use cached method
        result["parsed_citation"] = parsed

        # Try structured query if we got useful parsed data
        if parsed and (parsed.get("journal_name") or parsed.get("year")):
            logger.info(f"Attempting structured Crossref query...")
            match = self._query_crossref_structured(parsed)

            if match:
                result.update(match)
                # Mark as completed
                self.status_cache.set_completed(citation)
                self._save_result(citation, result)
                return result

        # Stage 2: Fallback to unstructured query
        logger.info(f"Falling back to unstructured query...")
        match = self._query_crossref_unstructured(citation)

        if match:
            result.update(match)
            # Mark as completed
            self.status_cache.set_completed(citation)
            self._save_result(citation, result)
            return result
        
        # No match found
        logger.warning(f"No match found for citation")
        self.status_cache.set_failed(citation)
        self._save_result(citation, result)
        return result
        
    except Exception as e:
        logger.error(f"Error resolving citation: {e}")
        self.status_cache.set_failed(citation)
        result["error"] = str(e)
        self._save_result(citation, result)
        return result
```

### Step 6: Add Utility Methods (Optional but Recommended)

Add these helpful methods for cache management:

```python
def get_cache_statistics(self) -> Dict:
    """Get statistics about cached citations."""
    return {
        "pending": len(self.status_cache.get_pending()),
        "completed": len(self.status_cache.get_completed()),
        "failed": len(self.status_cache.get_failed()),
        "llm_cached": len(json.loads(self.llm_cache_file.read_text())),
        "results_cached": len(json.loads(self.results_cache_file.read_text())),
    }

def clear_cache(self, clear_llm: bool = False, clear_results: bool = False):
    """
    Clear cached data.
    
    Args:
        clear_llm: Clear LLM response cache
        clear_results: Clear resolution results cache
    """
    if clear_llm:
        self.llm_cache_file.write_text("{}")
        logger.info("Cleared LLM response cache")
    
    if clear_results:
        self.results_cache_file.write_text("{}")
        logger.info("Cleared resolution results cache")
    
    self.status_cache.clear()
    logger.info("Cleared status cache")

def retry_failed(self, citations: list[str] = None) -> pd.DataFrame:
    """
    Retry previously failed citations.
    
    Args:
        citations: Specific citations to retry, or None for all failed
        
    Returns:
        DataFrame with retry results
    """
    if citations is None:
        # Get all failed citations from status cache
        citations = list(self.status_cache.get_failed())
    
    if not citations:
        logger.info("No failed citations to retry")
        return pd.DataFrame()
    
    logger.info(f"Retrying {len(citations)} failed citations...")
    
    # Clear failed status for these citations
    for citation in citations:
        self.status_cache.remove(citation)
    
    # Resolve them again
    return self.resolve(citations)
```

## Usage Examples

### Basic Usage (With Caching)

```python
from citation_resolver import create_resolver
from pathlib import Path

# Create resolver (caching is automatic)
resolver = create_resolver(
    scimago_file=Path("~/.cache/scimago.xlsx").expanduser(),
    model="llama3.1:latest",
    mailto="your@email.com"
)

# Resolve citations (uses cache automatically)
citations = [
    "Smith, J. (2020). Machine Learning. Nature, 123, 45-67.",
    "Jones, A. et al. Deep Learning. Science 2021.",
]

results = resolver.resolve(citations)
print(results)
```

### Check Cache Statistics

```python
# See what's cached
stats = resolver.get_cache_statistics()
print(f"Completed: {stats['completed']}")
print(f"Failed: {stats['failed']}")
print(f"LLM responses cached: {stats['llm_cached']}")
```

### Resume Interrupted Processing

```python
# If your script crashes or is interrupted:
# 1. Restart script
# 2. Run resolve again with same citations
# Already-completed citations will be instant!

resolver = create_resolver(...)
results = resolver.resolve(citations)  # Picks up where it left off
```

### Retry Failed Citations

```python
# After initial run, retry the ones that failed
failed_results = resolver.retry_failed()
print(f"Retried {len(failed_results)} failed citations")
```

### Force Recompute (Ignore Cache)

```python
# Resolve without using cache (for testing)
result = resolver.resolve_citation(citation, use_cache=False)
```

### Clear Cache

```python
# Clear all caches
resolver.clear_cache(clear_llm=True, clear_results=True)

# Or clear only status
resolver.clear_cache()  # Keeps LLM and results
```

## Cache File Locations

Default cache location (using path_config):
```
~/.cache/dh4pmp/citation_resolver/
├── resolution_status.json    # StringCache (pending/completed/failed)
├── llm_responses.json         # Cached LLM parsing results
└── resolution_results.json    # Final resolution results
```

Custom cache location:
```python
resolver = CitationResolver(
    ...,
    cache_dir=Path("./my_cache")  # Use custom directory
)
```

## Summary of Changes

**Files to modify**: `citation_resolver.py`

**Lines to change**:
1. Imports (top of file)
2. `__init__` method - add cache initialization
3. `resolve_citation` method - add cache checks and saves
4. Add 3 new cache methods: `_get_llm_response`, `_get_cached_result`, `_save_result`
5. (Optional) Add utility methods: `get_cache_statistics`, `clear_cache`, `retry_failed`

**Benefits**:
- Instant resolution for cached citations
- Resume interrupted processing
- No redundant LLM calls
- Track failures
- Easy retry mechanism

That's it! Your citation resolver now has comprehensive caching. 🎉
