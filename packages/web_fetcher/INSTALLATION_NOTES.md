# Installation Notes for web_fetcher v0.2.0

## What's New in 0.2.0

- **PDFDownloader class**: Download PDFs directly from DOIs
- Publisher-aware navigation (Nature, Elsevier, Springer, Wiley, arXiv, PLoS)
- Paywall detection
- Batch downloading with progress tracking
- Metadata tracking with JSON sidecar files

## Installation

### 1. Extract and install the package

```bash
# Extract the tarball
tar -xzf web_fetcher-0.2.0.tar.gz
cd packages/web_fetcher

# Install in editable mode
pip install -e .

# Or with Selenium support (required for PDFDownloader)
pip install -e ".[selenium]"
```

### 2. Install browser driver (for PDFDownloader)

**Chrome/Chromium (recommended):**
```bash
# Ubuntu/Debian
sudo apt-get install chromium-chromedriver

# macOS
brew install chromedriver
```

**Firefox:**
```bash
# Ubuntu/Debian
sudo apt-get install firefox-geckodriver

# macOS
brew install geckodriver
```

## Quick Start

### Download a single PDF

```python
from web_fetcher import PDFDownloader

downloader = PDFDownloader(pdf_dir="./pdfs")
result = downloader.download_from_doi("10.1371/journal.pone.0033693")

if result['success']:
    print(f"Downloaded: {result['pdf_path']}")
else:
    print(f"Error: {result['error']}")
```

### Batch download

```python
dois = [
    "10.1371/journal.pone.0033693",
    "10.48550/arXiv.2301.07041",
    # ... more DOIs
]

results = downloader.download_batch(dois, delay=2.0, progress=True)
```

## Testing

Run the example script:
```bash
python example_pdf_downloader.py
```

This will download a few test PDFs to `./example_pdfs/`

## File Organization

PDFs are saved with metadata:
```
pdfs/
├── 10.1371_journal.pone.0033693.pdf
├── 10.1371_journal.pone.0033693.json
├── 10.48550_arXiv.2301.07041.pdf
└── 10.48550_arXiv.2301.07041.json
```

## Upgrading from 0.1.0

The package is backward compatible. Existing code using `WebPageFetcher` and `SeleniumWebFetcher` will continue to work without changes.

## Next Steps After Testing

If everything works:
1. Commit changes to GitHub
2. Push to remote repository
3. Confirm version numbers match (0.2.0)

## Troubleshooting

**"Selenium not available"**: Install Selenium and browser driver
```bash
pip install selenium
sudo apt-get install chromium-chromedriver  # Ubuntu
```

**"PDF not found"**: Some PDFs may be behind paywalls or require institutional access

**Cloudflare challenges**: The downloader handles these automatically, but may take longer

## Support

See README.md for full documentation and examples.
