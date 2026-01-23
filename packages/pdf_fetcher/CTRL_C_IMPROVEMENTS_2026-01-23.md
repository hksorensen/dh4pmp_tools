# Ctrl+C Improvements for Sequential Mode - 2026-01-23

## Problem
When using `max_workers=1` (sequential mode), Ctrl+C was not responsive because:
1. Interrupt check only happened at start of each download loop iteration
2. If a download was in progress, it would complete before checking `_interrupted`
3. Downloads could block for up to 15s (socket timeout) or longer with retries

## Solution

### 1. Added Interrupt Checks Inside `fetch()` Method

**Three strategic locations:**

```python
# 1. At the start of fetch() - prevents new downloads
if self._interrupted:
    return DownloadResult(status="skipped", error_reason="Interrupted by user")

# 2. Before each strategy attempt - exits between retries
for strategy in strategies_to_try:
    if self._interrupted:
        return DownloadResult(status="skipped", error_reason="Interrupted by user")

# 3. Inside chunk download loop - interrupts during active download
for chunk in pdf_response.iter_content(chunk_size=8192):
    if self._interrupted:
        pdf_response.close()
        return DownloadResult(status="skipped", error_reason="Interrupted by user")
```

**Impact:**
- Ctrl+C now interrupts:
  - Before starting a new download ✓
  - Between strategy retries ✓
  - During active chunk downloads ✓

### 2. Improved Watchdog Timer

**Before:**
```python
def force_quit_watchdog():
    time.sleep(5)
    if cls._interrupted and not sys.__stdout__.closed:
        logger.error("Failed to shutdown cleanly after 5s - forcing exit")
        os._exit(1)
```

**After:**
```python
def force_quit_watchdog():
    time.sleep(3)  # Reduced from 5s to 3s
    if cls._interrupted:  # Removed stdout check
        try:
            logger.error("Failed to shutdown cleanly after 3s - forcing exit")
        except:
            pass  # Logger might fail, but we still exit
        os._exit(1)
```

**Changes:**
- ✅ Reduced timeout from 5s to 3s (more responsive)
- ✅ Removed `sys.__stdout__.closed` check (always force quit if interrupted)
- ✅ Added try/except around logging (handles broken logger)
- ✅ Updated user message: "wait 3s for automatic force quit"

### 3. Existing Protections (Already in Place)

- Global socket timeout: **15 seconds** (line 27)
  ```python
  socket.setdefaulttimeout(15)
  ```

- Chunked download with timeout checks
  - Per-chunk timeout: `self.timeout` seconds (default 30s)
  - Total download timeout: `self.timeout * 2` seconds
  - Both checked every 8KB chunk

- Second Ctrl+C → immediate `os._exit(1)` (no mercy)

## Expected Behavior

### Sequential Mode (max_workers=1)
1. **First Ctrl+C:**
   - Sets `_interrupted = True`
   - Shows: "⚠ SIGINT received - shutting down gracefully..."
   - Shows: "(Press Ctrl+C again to force quit, or wait 3s for automatic force quit)"
   - Starts 3-second watchdog timer

2. **During interrupt:**
   - Current download: Checks `_interrupted` at each chunk (every 8KB)
   - Between downloads: Checks `_interrupted` before starting next
   - Between retries: Checks `_interrupted` before next strategy

3. **Automatic force quit:**
   - If not exited within 3 seconds: `os._exit(1)`

4. **Second Ctrl+C:**
   - Immediate `os._exit(1)` (bypasses all cleanup)

### Maximum Wait Times

| Scenario | Max Wait | Why |
|----------|----------|-----|
| Between downloads | ~0ms | Checked immediately before next download |
| During strategy retry | ~0ms | Checked before each strategy attempt |
| During chunk download | 8KB transfer time | Checked between chunks |
| Network stall | 15s | Global socket timeout |
| Total freeze | 3s | Watchdog timer forces exit |
| Second Ctrl+C | 0s | Immediate force quit |

## Testing

To test improvements:

```bash
cd ~/Documents/dh4pmp/research/diagrams_in_arxiv
python3 pipeline/pipeline.py

# When downloads start, press Ctrl+C
# Should see graceful shutdown within 1-3 seconds
# Or press Ctrl+C twice for immediate exit
```

## Files Modified

1. **fetcher.py:**
   - Added interrupt check at start of `fetch()` (~line 463)
   - Added interrupt check in strategy loop (~line 589)
   - Added interrupt check in chunk download loop (~line 652)
   - Improved watchdog timer (3s, removed stdout check) (~line 146)
   - Updated user message (~line 137)

2. **fetch_corpus.py:**
   - Set `max_workers=1` for both ArXiv and published PDF fetchers

## Next Steps

If Ctrl+C still freezes for >3 seconds:
1. Check if there are C extensions or libraries bypassing Python signal handling
2. Verify signal handler is installed (should see "⚠ SIGINT received" message)
3. Check for bare `except:` clauses that might catch KeyboardInterrupt
4. Consider adding `signal.alarm()` as ultimate backup (Unix only)

---

**Summary:** Ctrl+C should now be responsive within 1-3 seconds in sequential mode, with multiple layers of interrupt checking and a 3-second watchdog as ultimate fallback.
