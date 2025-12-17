# Changelog

All notable changes to the web_fetcher package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-12-17

### Added
- Initial release with versioning
- `WebPageFetcher`: HTTP-based web page fetching with caching
- `SeleniumWebFetcher`: JavaScript-heavy page support (optional)
- Automatic retry logic with exponential backoff
- Local file-based caching with MD5 key generation
- Rate limiting and batch fetching support
- Automatic User-Agent and header management
- CAPTCHA handling hooks
- PDF download support
- Cloudflare rate limit detection

### Features
- Requests mode for simple HTML pages
- Selenium mode for JavaScript-rendered content
- Context manager support for proper resource cleanup
- Configurable retry strategies
- Cookie and session management
- Referer header auto-generation

### Technical
- Python 3.8+ support
- Proper package structure with `__version__`
- Comprehensive pyproject.toml configuration
- Optional selenium dependencies
