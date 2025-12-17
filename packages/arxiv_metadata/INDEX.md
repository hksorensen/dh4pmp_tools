# Package Index

## Quick Navigation

### 📚 Documentation
| File | Purpose | When to Read |
|------|---------|--------------|
| [README.md](README.md) | Complete documentation | First stop for API reference |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Step-by-step tutorial | Starting from scratch |
| [QUICKREF.md](QUICKREF.md) | Quick reference | Need a quick reminder |
| [SETUP.md](SETUP.md) | Installation guide | Setting up the package |
| [MIGRATION.md](MIGRATION.md) | Migration guide | Coming from old code |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Design details | Understanding internals |
| [PACKAGE_OVERVIEW.txt](PACKAGE_OVERVIEW.txt) | Visual overview | Quick glance at features |

### 💻 Source Code
| File | Contents |
|------|----------|
| [src/arxiv_metadata/__init__.py](src/arxiv_metadata/__init__.py) | Public API |
| [src/arxiv_metadata/fetcher.py](src/arxiv_metadata/fetcher.py) | ArxivMetadata class |
| [src/arxiv_metadata/filters.py](src/arxiv_metadata/filters.py) | Category enum, FilterBuilder |
| [src/arxiv_metadata/exceptions.py](src/arxiv_metadata/exceptions.py) | Custom exceptions |

### 📝 Examples
| File | Demonstrates |
|------|-------------|
| [examples/basic_usage.py](examples/basic_usage.py) | Common usage patterns |
| [examples/advanced_analysis.py](examples/advanced_analysis.py) | Complex analysis examples |

### 🧪 Tests
| File | Tests |
|------|-------|
| [tests/test_fetcher.py](tests/test_fetcher.py) | ArxivMetadata functionality |
| [tests/test_filters.py](tests/test_filters.py) | Filter system |

### 🔧 Configuration
| File | Purpose |
|------|---------|
| [pyproject.toml](pyproject.toml) | Package configuration |
| [MANIFEST.in](MANIFEST.in) | Distribution files |
| [LICENSE](LICENSE) | MIT License |
| [.gitignore](.gitignore) | Git ignore rules |

### 🛠️ Scripts
| File | Purpose |
|------|---------|
| [scripts/download_metadata.py](scripts/download_metadata.py) | Metadata download utility |

## Reading Order for Different Users

### New User (Never used the package)
1. [PACKAGE_OVERVIEW.txt](PACKAGE_OVERVIEW.txt) - Quick overview
2. [GETTING_STARTED.md](GETTING_STARTED.md) - Setup and first queries
3. [examples/basic_usage.py](examples/basic_usage.py) - See it in action
4. [QUICKREF.md](QUICKREF.md) - Keep handy for reference

### Migrating from Old Code
1. [MIGRATION.md](MIGRATION.md) - Migration guide
2. [README.md](README.md) - New API reference
3. [examples/basic_usage.py](examples/basic_usage.py) - New patterns
4. [ARCHITECTURE.md](ARCHITECTURE.md) - Understand design changes

### Power User
1. [README.md](README.md) - Full API documentation
2. [ARCHITECTURE.md](ARCHITECTURE.md) - Internals
3. [src/arxiv_metadata/](src/arxiv_metadata/) - Source code
4. [examples/advanced_analysis.py](examples/advanced_analysis.py) - Advanced patterns

### Developer/Contributor
1. [ARCHITECTURE.md](ARCHITECTURE.md) - Design philosophy
2. [src/arxiv_metadata/](src/arxiv_metadata/) - Implementation
3. [tests/](tests/) - Test suite
4. [SETUP.md](SETUP.md) - Development setup

## Common Tasks

### Installation
→ See [SETUP.md](SETUP.md) Section: "Quick Start"
→ See [GETTING_STARTED.md](GETTING_STARTED.md) Section: "Step 1"

### First Query
→ See [GETTING_STARTED.md](GETTING_STARTED.md) Section: "Your First Queries"
→ See [examples/basic_usage.py](examples/basic_usage.py)

### Specific Category
→ See [QUICKREF.md](QUICKREF.md) Section: "Common Queries"
→ See [README.md](README.md) Section: "Category Enum"

### Custom Filtering
→ See [README.md](README.md) Section: "Custom filtering"
→ See [examples/advanced_analysis.py](examples/advanced_analysis.py)

### Memory Issues
→ See [README.md](README.md) Section: "Performance Tips"
→ See [ARCHITECTURE.md](ARCHITECTURE.md) Section: "Streaming Architecture"

### Cache Management
→ See [README.md](README.md) Section: "Caching"
→ See [SETUP.md](SETUP.md) Section: "Configuration"

### Testing
→ See [GETTING_STARTED.md](GETTING_STARTED.md) Section: "Running Tests"
→ See [tests/](tests/) directory

### Extending the Package
→ See [ARCHITECTURE.md](ARCHITECTURE.md) Section: "Extension Points"
→ See [src/arxiv_metadata/filters.py](src/arxiv_metadata/filters.py)

## File Sizes
- Total package: ~50 KB
- Documentation: ~150 KB
- Tests: ~20 KB
- Examples: ~10 KB

## Dependencies
- **Required**: pandas, requests, tqdm
- **Optional**: pytest, black, mypy (for development)
- **Data**: arxiv-metadata-oai-snapshot.json (~5 GB, not included)

## Support
- Issues: Open on GitHub
- Documentation: This package
- Examples: See examples/ directory

## Version
Current version: 0.1.0
Last updated: 2024
Python: ≥ 3.8
License: MIT
