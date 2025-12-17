# Changelog

All notable changes to the arxiv_metadata package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-12-17

### Added
- Initial release with versioning
- `ArxivMetadata`: Main fetcher class with streaming architecture
- `Category` enum for filtering by arXiv category
- `FilterBuilder`: Composable filter system
- Streaming and batch fetching modes
- Automatic metadata download from Kaggle
- Smart caching with expiration management
- Year parsing from arXiv IDs
- Memory-efficient line-by-line processing

### Features
- Fetch by category (Category.MATH, Category.CS, etc.)
- Filter by years, author count, title keywords
- Stream large datasets without loading into memory
- Automatic cache management
- Built-in progress bars
- Type-safe API with full type hints

### Technical
- Python 3.8+ support
- Streaming architecture processes ~5GB metadata with ~100MB RAM
- Proper package structure with `__version__`
- Comprehensive pyproject.toml configuration
- Uses src/ layout for clean separation
- Integration with kagglehub for data downloads

### Documentation
- Comprehensive README with API reference
- GETTING_STARTED guide with step-by-step tutorial
- QUICKREF for common patterns
- ARCHITECTURE documentation
- MIGRATION guide for old code
- Examples for basic and advanced usage
