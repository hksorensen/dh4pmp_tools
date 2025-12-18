# Debugging Interrupt Issues in Jupyter Notebooks

If a Jupyter notebook cell continues running after interruption, here's how to debug:

## Quick Fix

Always use a context manager or explicitly close:

```python
# Option 1: Context manager (recommended)
with PDFFetcher(pdf_dir="./pdfs") as fetcher:
    results = fetcher.download_batch(identifiers)

# Option 2: Explicit close
fetcher = PDFFetcher(pdf_dir="./pdfs")
try:
    results = fetcher.download_batch(identifiers)
finally:
    fetcher.close()  # Always closes drivers
```

## Debugging Steps

### 1. Check for Running Chrome Processes

```bash
# On macOS/Linux
ps aux | grep -i chrome | grep -v grep

# Kill all Chrome processes (if needed)
pkill -f chrome
```

### 2. Check Python Processes

```bash
# Find Python processes
ps aux | grep python | grep -v grep

# Check if your notebook kernel is stuck
jupyter kernelspec list
```

### 3. Add Debug Logging

The code now logs when interrupted:

```
============================================================
INTERRUPTED BY USER (KeyboardInterrupt)
============================================================
Cleaning up resources (Selenium drivers, etc.)...
Cleanup complete. Execution stopped.
```

If you see this but execution continues, the issue is likely:
- Selenium driver processes not responding to quit()
- Background threads/subprocesses
- Jupyter kernel issues

### 4. Force Cleanup

If drivers won't close, manually clean up:

```python
# In a new cell
from web_fetcher import PDFFetcher

# If you have a fetcher instance
if 'fetcher' in locals():
    fetcher.close()
    fetcher._cleanup_domain_drivers()

# Or create a new one just to ensure cleanup
temp_fetcher = PDFFetcher()
temp_fetcher._cleanup_domain_drivers()
temp_fetcher.close()
```

### 5. Restart Kernel

If all else fails:
- Kernel → Restart Kernel
- This will kill all Python processes and free resources

## Common Causes

1. **Selenium drivers not responding**: Chrome processes can hang
2. **Long-running operations**: `time.sleep()` or Selenium waits don't check for interrupts
3. **Background threads**: If any threading is used, threads may continue
4. **Jupyter kernel issues**: Sometimes the kernel itself gets stuck

## Prevention

1. **Use context managers**: Ensures cleanup even on interruption
2. **Set timeouts**: Use `driver.set_page_load_timeout()` to prevent indefinite waits
3. **Check for interrupts**: The code now checks at batch boundaries
4. **Monitor processes**: Keep an eye on Chrome processes during long runs

## If Problem Persists

1. Check Jupyter logs: `jupyter notebook --log-level=DEBUG`
2. Check system logs for Chrome processes
3. Try running in a script instead of notebook (easier to interrupt)
4. Use smaller batch sizes to reduce time between interrupt checks

