# ArXiv Rate Limit Batch Pause

## Problem

When downloading 100k+ papers from ArXiv, if one request hits a rate limit (captcha, "too many requests", etc.), it makes no sense to keep hammering their servers. The old behavior would:

1. Hit rate limit on paper #1234
2. Mark that paper as "postponed"
3. **Continue trying papers #1235, #1236, #1237...** ← Wastes time and may get IP blocked!

## Solution

When **any** ArXiv paper triggers a rate limit, we now:

1. **Detect** the rate limit (captcha, HTML instead of PDF, etc.)
2. **Pause** ALL ArXiv downloads immediately
3. **Mark** all remaining ArXiv papers in the batch as "postponed"
4. **Continue** downloading non-ArXiv papers (Springer, Elsevier, etc.)

This prevents wasting time and protects against IP blocking.

## How It Works

### Automatic Detection

The system automatically detects rate limiting when ArXiv returns:

- HTML page instead of PDF
- Captcha page ("verify you are human")
- "Too many requests" error
- "Unusual traffic" message
- "Automated requests" warning

When detected:
```
🚫 ArXiv rate limit activated: HTML instead of PDF (captcha/rate limiting)
   All ArXiv downloads will be skipped until reset
⏸ Skipping 1,247 ArXiv papers (rate limit active)
```

### Class-Level Flag

The rate limit is tracked at the **class level** in `ArxivStrategy`:

```python
# Shared across ALL instances and threads
ArxivStrategy._rate_limited = True
```

This means:
- Once triggered, affects ALL subsequent downloads
- Persists across batches
- Thread-safe (uses locks internally)

## Usage

### In Production Code

No changes needed! Rate limiting is automatic:

```python
from pdf_fetcher import PDFFetcher

fetcher = PDFFetcher(output_dir="pdfs", max_workers=5)

# Download 100k papers
arxiv_ids = [....]  # Your list of ArXiv IDs
results = fetcher.fetch_batch(arxiv_ids, show_progress=True)

# If rate limit hit, remaining ArXiv papers automatically postponed
```

### Manual Control

#### Check Status

```python
from pdf_fetcher.strategies.arxiv import ArxivStrategy

# Check if currently rate limited
if ArxivStrategy.is_rate_limited():
    print("ArXiv downloads are paused")
```

#### Manual Reset

After waiting for rate limit to expire (e.g., 1 hour later):

```python
from pdf_fetcher.strategies.arxiv import ArxivStrategy

# Reset the rate limit flag
ArxivStrategy.reset_rate_limit()

# Now ArXiv downloads will resume
fetcher.fetch_batch(remaining_arxiv_ids)
```

#### Manual Trigger (for testing)

```python
# Simulate rate limit detection
ArxivStrategy.set_rate_limited("Testing rate limit behavior")
```

## Example Scenario

### Initial Batch (10,000 papers)

```
Papers to download:
  - 7,000 ArXiv papers
  - 2,000 Springer papers
  - 1,000 Elsevier papers

Progress:
  ✓ 2301.12345 (ArXiv)
  ✓ 2301.12346 (ArXiv)
  ⏸ 2301.12347 (ArXiv) - HTML received, rate limit detected!
  🚫 ArXiv rate limit activated
  ⏸ Skipping 6,997 ArXiv papers (rate limit active)
  ✓ 10.1007/s00285-023-01234-5 (Springer) - continues normally
  ✓ 10.1016/j.jmaa.2023.127123 (Elsevier) - continues normally
  ...

Final results:
  - 2 ArXiv papers downloaded
  - 6,998 ArXiv papers postponed
  - 3,000 non-ArXiv papers processed normally
```

### After Waiting (1 hour later)

```python
# Reset rate limit
ArxivStrategy.reset_rate_limit()

# Retry postponed ArXiv papers
arxiv_postponed = [r.identifier for r in results if r.status == "postponed"]
retry_results = fetcher.fetch_batch(arxiv_postponed)

# If rate limit hit again, will pause again automatically
```

## Implementation Details

### Detection in ArxivStrategy

```python
def should_postpone(self, error_msg: str, html: str = "") -> bool:
    # Check for rate limiting indicators
    if 'not a pdf' in error_msg.lower() or 'html' in error_msg:
        # Trigger batch-level pause
        self.set_rate_limited("HTML instead of PDF (captcha/rate limiting)")
        return True

    # Check HTML content for captcha
    if 'captcha' in html.lower():
        self.set_rate_limited("Captcha detected in response")
        return True

    # ... other checks
```

### Filtering in PDFFetcher

```python
def fetch_batch(self, identifiers: List[str], ...):
    # Before submitting to thread pool:
    for identifier in batch_identifiers:
        # Check if ArXiv and rate limited
        if self._is_arxiv_identifier(identifier) and ArxivStrategy.is_rate_limited():
            # Skip - mark as postponed immediately
            results.append(DownloadResult(
                identifier=identifier,
                status="postponed",
                error_reason="ArXiv rate limited - batch paused"
            ))
        else:
            # Submit to thread pool
            batch_to_submit.append(identifier)
```

## Benefits

1. **Prevents IP blocking** - Stops hammering ArXiv when rate limited
2. **Saves time** - No wasted attempts on doomed downloads
3. **Automatic** - No code changes needed
4. **Selective** - Only pauses ArXiv, not other publishers
5. **Recoverable** - Manual reset allows retry after waiting

## Testing

Run the test suite:

```bash
python test_arxiv_rate_limit.py
```

Expected output:
```
ARXIV RATE LIMIT TEST
======================================================================

Test scenario:
  6 papers: 4 ArXiv, 2 non-ArXiv
  Manually triggering rate limit after first paper

ArXiv rate limited: False

→ Simulating rate limit detection...
🚫 ArXiv rate limit activated: Test: Manual simulation
   All ArXiv downloads will be skipped until reset
ArXiv rate limited: True

...

✓ TEST PASSED: All ArXiv papers were postponed when rate limited
✓ TEST PASSED: Non-ArXiv papers were still attempted
```

## Configuration

No configuration needed - works out of the box!

The rate limit is tracked at the class level, so:
- Persists across `PDFFetcher` instances
- Shared between threads
- Survives batch boundaries

## Troubleshooting

### Rate limit not resetting automatically

The flag persists until manually reset:

```python
ArxivStrategy.reset_rate_limit()
```

**Why?** We don't know how long to wait before retrying ArXiv. Better to let you decide when it's safe to resume.

### Non-ArXiv papers also postponed

Check your identifier format:

```python
fetcher._is_arxiv_identifier("10.1007/...")  # Should return False
fetcher._is_arxiv_identifier("2301.12345")   # Should return True
```

### Rate limit triggered too easily

The detection is intentionally sensitive to protect against IP blocking. If you're getting false positives, check the logs for what triggered it:

```
🚫 ArXiv rate limit activated: <reason here>
```

## Future Enhancements

Potential improvements (not yet implemented):

1. **Auto-reset timer** - Reset after N minutes automatically
2. **Per-IP tracking** - Different limits for different IPs
3. **Gradual retry** - Exponential backoff instead of full pause
4. **Rate limit metrics** - Track how often we hit limits

For now, manual reset provides maximum control.
