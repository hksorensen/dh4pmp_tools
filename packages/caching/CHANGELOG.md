# Changelog

All notable changes to the caching package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-12-17

### Added
- Initial release with versioning
- `LocalCache`: Heavy data caching with pickle storage
- `MultiQueryCache`: Batch query caching support
- `StringCache`: Lightweight string data with status tracking
- Path configuration system with XDG Base Directory support
- Centralized path utilities (get_cache_dir, get_data_dir, get_results_dir)
- Expiration support for cached data
- Human-readable metadata for cache entries

### Technical
- Python 3.8+ support
- Proper package structure with `__version__`
- Comprehensive pyproject.toml configuration
