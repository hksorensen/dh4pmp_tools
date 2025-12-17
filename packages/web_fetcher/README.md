# Web Fetcher

A robust web page fetching library with local file-based caching, retry logic, and optional Selenium support for JavaScript-heavy pages and CAPTCHA handling.

**New in 0.2.0**: `PDFDownloader` class for downloading PDFs from DOIs with intelligent publisher navigation.

## Features

- **Local file-based caching**: Efficient caching using MD5-keyed JSON files
- **Automatic retry logic**: Configurable retries with exponential backoff
- **Three implementations**:
  - `WebPageFetcher`: Lightweight requests-based fetcher
  - `SeleniumWebFetcher`: Extended version with Selenium support
  - `PDFDownloader`: Specialized DOI → PDF downloader (new!)
- **PDF downloading**: Intelligent PDF detection and download with CloudFlare support
- **Publisher awareness**: Built-in patterns for major academic publishers
- **Paywall detection**: Graceful handling of restricted content
- **Batch processing**: Download multiple PDFs with progress tracking
- **Metadata tracking**: JSON sidecar files for download status
- **Rate limiting**: Built-in delays for batch fetching
- **Context manager support**: Clean resource management

## Installation

### Basic installation (requests only)

```bash
pip install requests urllib3
```

### With Selenium support (required for PDFDownloader)

```bash
pip install requests urllib3 selenium
```

You'll also need to install a browser driver:

**Chrome/Chromium:**
```bash
# Ubuntu/Debian
sudo apt-get install chromium-chromedriver

# macOS
brew install chromedriver

# Or download from: https://chromedriver.chromium.org/
```

**Firefox:**
```bash
# Ubuntu/Debian
sudo apt-get install firefox-geckodriver

# macOS
brew install geckodriver

# Or download from: https://github.com/mozilla/geckodriver/releases
```

## Usage

### NEW: PDF Downloader (0.2.0)

Download PDFs directly from DOIs with intelligent navigation:

```python
from web_fetcher import PDFDownloader

# Create downloader instance
downloader = PDFDownloader(
    pdf_dir="./pdfs",
    cache_dir="./cache",
    max_retries=3,
    headless=True
)

# Download single PDF
result = downloader.download_from_doi("10.1038/s41586-024-07998-6")

if result['success']:
    print(f"Downloaded to: {result['pdf_path']}")
else:
    print(f"Failed: {result['error']}")
    print(f"Status: {result['status']}")  # 'failure' or 'paywall'
```

**Batch downloading with progress:**

```python
dois = [
    "10.1038/s41586-024-07998-6",
    "10.1016/j.neuron.2024.01.015",
    "10.1371/journal.pone.0033693",
    # ... more DOIs
]

results = downloader.download_batch(
    dois,
    delay=2.0,  # 2 seconds between requests
    progress=True
)

# Check results
for result in results:
    if result['success']:
        print(f"✓ {result['doi']}")
    elif result['status'] == 'paywall':
        print(f"⚠ {result['doi']} - Paywall")
    else:
        print(f"✗ {result['doi']} - {result['error']}")
```

**Get statistics:**

```python
stats = downloader.get_statistics()
print(f"Downloaded: {stats['success']} PDFs")
print(f"Failed: {stats['failure']}")
print(f"Paywalled: {stats['paywall']}")
print(f"Total size: {stats['total_size_mb']:.1f} MB")
```

**List downloaded files:**

```python
downloaded = downloader.list_downloaded()
for item in downloaded:
    print(f"{item['doi']}: {item['pdf_path']}")
```

**Using context manager:**

```python
with PDFDownloader(pdf_dir="./pdfs") as downloader:
    result = downloader.download_from_doi("10.1038/...")
    # Browser automatically closed
```

#### PDF Download Features

- **Publisher awareness**: Recognizes Nature, Elsevier, Springer, Wiley, arXiv, PLoS patterns
- **Paywall detection**: Identifies paywalled content and reports gracefully
- **Cloudflare handling**: Automatically handles Cloudflare challenges
- **Resume capability**: Skips already downloaded PDFs (unless `force_refresh=True`)
- **Metadata tracking**: Creates `.json` files with download status, timestamps, URLs
- **Error handling**: Distinguishes between failures, paywalls, and missing PDFs

#### File Organization

PDFs are organized with metadata:

```
pdfs/
├── 10.1038_s41586-024-07998-6.pdf
├── 10.1038_s41586-024-07998-6.json
├── 10.1016_j.neuron-2024-01-015.pdf
└── 10.1016_j.neuron-2024-01-015.json
```

Metadata JSON contains:
```json
{
  "doi": "10.1038/s41586-024-07998-6",
  "status": "success",
  "timestamp": "2024-12-17T14:30:00",
  "url": "https://www.nature.com/articles/...",
  "pdf_path": "/path/to/pdfs/10.1038_s41586-024-07998-6.pdf"
}
```

### Basic Usage with WebPageFetcher

```python
from web_fetcher import WebPageFetcher

# Create fetcher instance
fetcher = WebPageFetcher(
    cache_dir="./cache/web_pages",
    max_retries=3,
    backoff_factor=1.0,
)

# Fetch a single page
result = fetcher.fetch("https://example.com")
print(f"Status: {result['status_code']}")
print(f"From cache: {result['cached']}")
print(f"Content: {result['content'][:200]}")

# Fetch with query parameters
result = fetcher.fetch(
    "https://api.example.com/data",
    params={'key': 'value', 'page': 1}
)

# Fetch multiple URLs
urls = ["https://example.com", "https://python.org"]
results = fetcher.fetch_multiple(urls, delay=1.0)
```

### Using SeleniumWebFetcher

For JavaScript-heavy pages or button clicking:

```python
from web_fetcher import SeleniumWebFetcher, By

# Create Selenium fetcher
fetcher = SeleniumWebFetcher(
    cache_dir="./cache",
    headless=True,
    timeout=30
)

# Fetch page
result = fetcher.fetch("https://example.com")

# Click a button
button = fetcher.driver.find_element(By.CSS_SELECTOR, ".download-button")
button.click()

# Wait for element
fetcher.wait_for_element(By.ID, "content", timeout=10)

# Handle CAPTCHA manually
result = fetcher.fetch_with_captcha_handling(
    "https://example.com",
    captcha_present=lambda d: "captcha" in d.page_source.lower()
)

# Close when done
fetcher.close()
```

### Using Context Manager

```python
with WebPageFetcher(cache_dir="./cache") as fetcher:
    result = fetcher.fetch("https://example.com")
    # Session automatically closed
```

### Advanced Features

```python
# Force refresh (bypass cache)
fetcher = WebPageFetcher(force_refresh=True)
result = fetcher.fetch("https://example.com")

# Custom headers
result = fetcher.fetch(
    "https://example.com",
    headers={'Authorization': 'Bearer token'}
)

# Custom timeout
fetcher = WebPageFetcher(timeout=60)
result = fetcher.fetch("https://slow-site.com")
```

## Integration with Existing Projects

This library is designed to work alongside the `api_clients` package and follows similar patterns:

- File-based caching (not database)
- Automatic retry with exponential backoff
- Context manager support
- Structured logging

### Example: Using with api_clients

```python
from api_clients import CrossrefClient
from web_fetcher import PDFDownloader

# Get DOIs from Crossref
crossref = CrossrefClient()
results = crossref.fetch("machine learning", rows=100)

# Extract DOIs
dois = [item['DOI'] for item in results['items'] if 'DOI' in item]

# Download PDFs
downloader = PDFDownloader(pdf_dir="./ml_papers")
pdf_results = downloader.download_batch(dois, delay=2.0)

print(f"Downloaded {sum(1 for r in pdf_results if r['success'])} PDFs")
```

## Logging

All classes use Python's `logging` module:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Now fetcher operations will log
downloader = PDFDownloader()
result = downloader.download_from_doi("10.1038/...")
```

## Performance Considerations

- **Requests mode**: Very fast, ideal for simple HTML pages
- **Selenium mode**: Slower due to browser overhead, use only when necessary
- **PDF downloading**: Varies by publisher; expect 2-5 seconds per PDF
- **Caching**: First request is slow, subsequent requests are instant
- **Batch fetching**: Use appropriate delays (2-3 seconds) to avoid rate limiting
- **Large batches**: For 50,000+ PDFs, consider sampling or batch archiving

## Scaling to Large Downloads

For large-scale PDF downloading (10,000+ files):

1. **Sampling**: Process a representative subset
2. **Batch checkpointing**: Download in chunks and archive
3. **Resume capability**: Built-in skip of existing files
4. **Progress tracking**: Monitor success/failure rates
5. **External storage**: Move completed batches to SFTP/cloud storage

Example for large-scale downloads:

```python
# Download in batches of 1000
batch_size = 1000
all_dois = [...50000 DOIs...]

for i in range(0, len(all_dois), batch_size):
    batch = all_dois[i:i+batch_size]
    
    downloader = PDFDownloader(pdf_dir=f"./pdfs/batch_{i//batch_size}")
    results = downloader.download_batch(batch, delay=2.0)
    
    # Archive batch before next one
    # tar -czf batch_N.tar.gz ./pdfs/batch_N
    # scp batch_N.tar.gz remote_server:/storage/
```

## Tips

1. Start with `WebPageFetcher` for most use cases
2. Use `SeleniumWebFetcher` only for JavaScript-heavy sites
3. Use `PDFDownloader` specifically for DOI → PDF workflows
4. Set `headless=True` for production, `headless=False` for debugging
5. Cache directory grows over time - implement periodic cleanup if needed
6. For CAPTCHA-protected sites, consider using manual solving mode
7. Always use context managers or explicitly close drivers/sessions
8. Monitor paywall rates to understand access limitations

## Error Handling

PDFDownloader distinguishes between different failure types:

```python
result = downloader.download_from_doi("10.1038/...")

if result['success']:
    print("Downloaded successfully")
elif result['status'] == 'paywall':
    print("Content is behind paywall")
elif result['status'] == 'failure':
    print(f"Download failed: {result['error']}")
```

## License

This code is part of the dh4pmp_tools project and follows the MIT license.
