# PDF Fetcher v2

A clean, specification-compliant implementation of the PDF fetcher.

## Overview

This implementation follows the specification in `pdf_fetcher_specification_chat.md` and provides:

- **Clean architecture** with separated concerns
- **Multiple PDF discovery strategies** (direct links, buttons, inline PDFs, page scanning)
- **Publisher-specific handling** (Elsevier/ScienceDirect, Springer, Nature, etc.)
- **Rate limiting** with per-domain throttling
- **Metadata tracking** with JSON storage
- **Error handling** with proper categorization
- **Repeat download avoidance** by checking existing files

## Architecture

The implementation is organized into focused classes:

- **`PDFFetcher`**: Main entry point
- **`IdentifierNormalizer`**: Handles DOI/URL normalization and sanitization
- **`PublisherDetector`**: Detects publisher from URL
- **`DOIResolver`**: Resolves DOIs to landing URLs
- **`PDFLinkFinder`**: Finds PDF URLs using multiple strategies
- **`DownloadManager`**: Handles actual PDF downloads
- **`MetadataStore`**: Manages JSON metadata
- **`RateLimiter`**: Per-domain rate limiting

## Key Features

### 1. Identifier Handling

Supports three input types:
- **DOI**: `10.2138/am.2011.573`
- **DOI-URL**: `https://doi.org/10.2138/am.2011.573`
- **Resource URL**: `https://pubs.geoscienceworld.org/ammin/article/96/5-6/946/45401`

### 2. PDF Discovery Strategies

1. **Publisher-specific** (e.g., ScienceDirect PII extraction)
2. **Direct links** (CSS selectors for PDF links)
3. **Button/link clicking** (finds and clicks PDF buttons)
4. **Inline PDF detection** (checks if current page is PDF)
5. **Page source scanning** (regex patterns as last resort)

### 3. Download Handling

- Transfers cookies from Selenium to requests session
- Handles 403/4xx responses that may still contain PDF
- Validates PDF header (`%PDF`) before saving
- Uses temporary files to avoid corruption

### 4. Metadata

Stores comprehensive metadata in JSON:
- Original identifier
- Sanitized filename
- Landing URL, PDF URL
- Publisher
- Status and error reasons
- Timestamps

## Usage

```python
from web_fetcher.pdf_fetcher_v2 import PDFFetcher, DownloadStatus

# Initialize
fetcher = PDFFetcher(
    pdf_dir="./pdfs",
    metadata_path="./pdfs/metadata.json",
    headless=True,
    requests_per_second=1.0
)

# Download
result = fetcher.download("10.2138/am.2011.573")

if result.status == DownloadStatus.SUCCESS:
    print(f"Downloaded to: {result.pdf_path}")
else:
    print(f"Failed: {result.error_reason}")

# Cleanup
fetcher.close()
```

## Configuration

- `pdf_dir`: Directory to store PDFs (default: `./pdfs`)
- `metadata_path`: Path to metadata JSON (default: `./pdfs/metadata.json`)
- `headless`: Run browser headless (default: `True`)
- `requests_per_second`: Rate limit per domain (default: `1.0`)
- `max_retries`: Max retries for network errors (default: `3`)
- `user_agent`: Custom user agent string (optional)

## Status Codes

- `SUCCESS`: PDF downloaded successfully
- `ALREADY_EXISTS`: PDF already exists locally
- `PAYWALL`: Content behind paywall
- `PDF_NOT_FOUND`: Could not find PDF link
- `NETWORK_ERROR`: Network/connection error
- `INVALID_IDENTIFIER`: Malformed DOI/URL
- `FAILURE`: Other failure

## Differences from v1

- **Cleaner architecture**: Separated concerns into focused classes
- **Better error handling**: Proper status codes and error categorization
- **Metadata management**: Centralized JSON metadata store
- **Rate limiting**: Per-domain rate limiting with jitter
- **Spec compliance**: Follows the specification more closely
- **Simpler API**: Single `download()` method with clear return type

## Future Enhancements

- Shared folder monitoring (`~/Downloads/`)
- Parallel downloads for non-Selenium operations
- More publisher-specific strategies
- robots.txt respect
- Progress callbacks

