# PDF Fetcher - Timeout and Ctrl+C Fixes

**Date:** 2026-01-21
**Issues Fixed:**
1. Batch timeout at 360s (batch 27)
2. Freezing beyond Ctrl+C

---

## Issue 1: Timeout Workaround

### Problem
Parallel downloads with ThreadPoolExecutor can hang if some threads block on I/O operations (SSL handshakes, slow reads). The batch timeout (`timeout * 3`) triggers but doesn't help if threads are stuck.

### Solution: Sequential Mode

**Set `max_workers=1` to disable parallel downloads completely:**

```python
from pdf_fetcher import PDFFetcher

# Sequential mode - no parallel processing, no timeouts
fetcher = PDFFetcher(
    output_dir="./pdfs",
    max_workers=1,  # ← KEY: Sequential mode
    timeout=30
)

# Fetch batch sequentially
results = fetcher.fetch_batch(dois, show_progress=True)
```

**Advantages:**
- ✅ No batch timeouts (downloads happen one at a time)
- ✅ Simpler error handling
- ✅ Better for debugging individual download issues
- ✅ More respectful of rate limits

**Disadvantages:**
- ⏱️ Slower (4x-10x slower depending on typical `max_workers` setting)

**When to use sequential mode:**
- Debugging download issues
- Small batches (<50 PDFs)
- When timeouts are frequent
- When Ctrl+C responsiveness is critical

---

## Issue 2: Improved Ctrl+C Handling

### Changes Made

#### 1. Reduced Global Socket Timeout (Line 26)
```python
# OLD: socket.setdefaulttimeout(60)  # 60 seconds
# NEW:
socket.setdefaulttimeout(15)  # 15 seconds - faster Ctrl+C response
```

**Effect:** Threads stuck in C-level socket operations will timeout faster, making Ctrl+C more responsive.

#### 2. Daemon Threads (Lines 978-987)
```python
executor = ThreadPoolExecutor(
    max_workers=self.max_workers,
    thread_name_prefix="PDFFetcher",
)
# Make worker threads daemon - they die when main thread exits
for thread in threading.enumerate():
    if thread.name.startswith("PDFFetcher"):
        thread.daemon = True
```

**Effect:** When main thread exits (after Ctrl+C), daemon threads are forcibly terminated by Python runtime.

#### 3. Watchdog Timer (Lines 134-145)
```python
# Start a watchdog - if we don't exit cleanly in 5 seconds, force quit
def force_quit_watchdog():
    time.sleep(5)
    if cls._interrupted:
        logger.error("\n⚠ Failed to shutdown cleanly after 5s - forcing exit")
        os._exit(1)

watchdog = threading.Thread(target=force_quit_watchdog, daemon=True)
watchdog.start()
```

**Effect:**
- First Ctrl+C: Graceful shutdown attempt + 5-second watchdog
- If still running after 5s: Automatic force quit with `os._exit(1)`
- Second Ctrl+C: Immediate force quit

#### 4. More Aggressive Second Ctrl+C (Lines 155-160)
```python
else:
    # Second interrupt - force quit immediately, no mercy
    try:
        logger.warning(f"\n⚠ Force quit (interrupt #{cls._interrupt_count})")
    except:
        pass  # Logger might be broken, just exit
    os._exit(1)
```

**Effect:** Second Ctrl+C always succeeds, even if logging is broken.

---

## How to Use

### Sequential Mode (Recommended for Avoiding Timeouts)

```bash
# In your script or command-line tool
python your_script.py --max-workers 1
```

Or in code:
```python
fetcher = PDFFetcher(max_workers=1)  # Sequential mode
results = fetcher.fetch_batch(dois)
```

### Parallel Mode (Default, Faster)

```python
fetcher = PDFFetcher(max_workers=4)  # Parallel mode (default)
results = fetcher.fetch_batch(dois)
```

**If timeouts occur:**
1. First try increasing timeout: `PDFFetcher(timeout=60, max_workers=4)`
2. If still timing out: Use sequential mode: `PDFFetcher(max_workers=1)`

---

## Testing the Ctrl+C Fix

```bash
# Start a long download
python your_download_script.py

# Press Ctrl+C once - should see:
# ⚠ SIGINT received - shutting down gracefully...
# (Press Ctrl+C again within 3 seconds to force quit)

# Wait 5 seconds - if still running, watchdog kicks in:
# ⚠ Failed to shutdown cleanly after 5s - forcing exit
# [Process exits]

# OR press Ctrl+C again immediately:
# ⚠ Force quit (interrupt #2)
# [Process exits immediately]
```

---

## Summary of Changes

| File | Lines | Change |
|------|-------|--------|
| `fetcher.py` | 26 | Reduced socket timeout: 60s → 15s |
| `fetcher.py` | 134-145 | Added 5-second watchdog timer |
| `fetcher.py` | 155-160 | More robust second Ctrl+C handler |
| `fetcher.py` | 894-922 | Added sequential mode branch (max_workers=1) |
| `fetcher.py` | 978-987 | Make worker threads daemon threads |

---

## Migration Guide

### For CLI Tools

Add a command-line flag:
```python
parser.add_argument('--sequential', action='store_true',
                   help='Use sequential downloads (no parallelism, avoids timeouts)')

# In code:
max_workers = 1 if args.sequential else 4
fetcher = PDFFetcher(max_workers=max_workers)
```

### For Config Files

Add to your `config.yaml`:
```yaml
# Set to 1 for sequential mode (no timeouts, slower)
# Set to 4 for parallel mode (faster, may timeout)
max_workers: 1
```

---

## Known Limitations

1. **Sequential mode is slower**: 4x-10x slower than parallel mode
2. **Watchdog is not instant**: Takes up to 5 seconds to force quit
3. **Daemon threads caveat**: Threads are forcibly killed, may leave incomplete downloads

## Recommendations

1. **Use sequential mode** (`max_workers=1`) for:
   - Initial debugging
   - Small batches (<50 PDFs)
   - When timeout issues are frequent

2. **Use parallel mode** (`max_workers=4`) for:
   - Large batches (>100 PDFs)
   - Production downloads
   - When timeouts are rare

3. **Monitor timeouts**: If >10% of batches timeout, switch to sequential mode

---

**Questions or issues?** Open an issue at the pdf_fetcher repository.
