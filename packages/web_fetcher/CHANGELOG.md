# Changelog

All notable changes to the web_fetcher package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2024-12-17

### Added
- **PDFDownloader class**: New specialized class for downloading PDFs from DOIs
  - DOI resolution to publisher landing pages
  - Intelligent PDF link detection on publisher pages
  - Support for major academic publishers (Nature, Elsevier, Springer, Wiley, arXiv, PLoS)
  - Button and link clicking for multi-step downloads
  - Paywall detection and graceful handling
  - Cloudflare challenge handling
  - Local PDF caching with metadata tracking
  - JSON sidecar files for download status tracking
  - Batch download support with progress tracking
  - Resume capability (skip already downloaded files)
  - Statistics and reporting functions
  - Context manager support

### Changed
- Updated `__init__.py` to export PDFDownloader and related exceptions
- Updated README with comprehensive PDFDownloader documentation
- Bumped version to 0.2.0 in both `__init__.py` and `setup.py`

### Documentation
- Added detailed usage examples for PDFDownloader
- Added scaling guidelines for large-scale downloads (50,000+ PDFs)
- Added example script `example_pdf_downloader.py`
- Enhanced README with publisher-specific information
- Added error handling documentation

## [0.1.0] - 2024-11-XX

### Added
- Initial release
- `WebPageFetcher`: Lightweight HTTP fetcher with caching
- `SeleniumWebFetcher`: Browser-based fetcher for JavaScript-heavy pages
- Local file-based caching system
- Automatic retry logic with exponential backoff
- CAPTCHA handling hooks
- Rate limiting support
- Context manager support
- Comprehensive test suite

### Features
- MD5-based cache keys
- Configurable timeout and retry parameters
- Custom user agent support
- Session persistence
- PDF download support (basic)
- CloudFlare rate limit detection
