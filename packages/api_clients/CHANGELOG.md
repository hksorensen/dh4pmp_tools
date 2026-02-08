# Changelog

All notable changes to the api_clients package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-02-06

### Added
- `GeminiImageFetcher`: Standalone client for Gemini image generation (Google AI Studio)
- `GeminiImageClient`: Low-level REST client for generateContent endpoint
- `GeminiImageConfig`: Configuration (model, rate limits, etc.)
- No caching (generative outputs are non-deterministic)
- Tests for image generation (skipped if no API key)

## [1.0.0] - 2024-12-17

### Added
- Initial versioned release
- `CrossrefSearchFetcher`: Primary API client (no API key needed)
- `CrossrefBibliographicFetcher`: Citation resolution with caching
- `ScopusSearchFetcher`: Scopus API client
- `ScopusAbstractFetcher`: Abstract retrieval
- Base classes for extending to new APIs
- Token bucket rate limiting algorithm
- Proactive rate limiting with configurable burst size
- Exponential backoff for retries
- Local file-based caching (via caching package)
- Comprehensive error handling
- Cursor-based pagination support
- Progress bars with tqdm integration

### Features
- Crossref client (easiest - no API key required)
  - Search functionality
  - Field queries (title, author, etc.)
  - Filter support
  - DOI metadata lookup
- Scopus client (requires API key)
  - Advanced search queries
  - Abstract retrieval
  - Author and affiliation data
- Base infrastructure
  - Shared rate limiting
  - Unified configuration system
  - Automatic retry with backoff
  - Response caching and cache management

### Technical
- Python 3.8+ support
- Proper package structure with `__version__ = "1.0.0"`
- Comprehensive pyproject.toml configuration
- Type hints throughout
- Integration with caching package from monorepo
