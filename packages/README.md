# Packages

Shareable, reusable Python packages.

These packages are designed to be useful beyond your specific research projects. They're polished, documented, and can be shared with collaborators or the wider community.

## Available Packages

### [api_clients](api_clients/)
Unified clients for academic APIs (Scopus, Crossref).
- Rate limiting and retry logic
- Automatic caching
- Configuration management
- Supports both search and record fetching

### [caching](caching/)
File-based and string-based caching systems.
- **LocalCache**: Heavy data (DataFrames) with pickle storage
- **StringCache**: Lightweight tracking with status field
- Expiration support
- Human-readable metadata

### [web_fetcher](web_fetcher/)
Web page fetching with optional Selenium support.
- Simple HTTP fetching
- JavaScript rendering with Selenium
- CAPTCHA handling hooks
- PDF download support

### [arxiv_metadata](arxiv_metadata/)
Tools for working with arXiv metadata.
- Metadata fetching and parsing
- Filtering and analysis
- Bulk download support

### [pipelines](pipelines/)
Reusable data pipeline framework.
- Generic `BasePipeline` class for any workflow
- Configuration and result tracking
- Built-in logging and error handling
- Zero dependencies (pure Python)

## Installation

Install all packages:
```bash
cd ../  # From repo root
./scripts/install.sh --packages
```

Install individual package:
```bash
pip install -e packages/caching
```

## Development Guidelines

When creating new packages:

1. **Use this directory**: Put reusable code in `packages/`, not `research/`
2. **Include README**: Every package needs a README.md
3. **Add setup.py**: Make it pip-installable
4. **No research imports**: Don't import from `research/` or `utils/`
5. **Document well**: Others should understand without asking you
6. **Test locally**: Use `pip install -e` during development

## Sharing Packages

To share one or more packages with collaborators:

```bash
cd ../
./scripts/extract_for_sharing.sh
# Select the packages to include
# Creates a standalone git repo ready to push
```

## Package Structure Template

```
my_package/
├── my_package/
│   ├── __init__.py
│   ├── core.py
│   └── utils.py
├── tests/
│   └── test_core.py
├── examples/
│   └── basic_usage.py
├── README.md
├── setup.py
└── .gitignore
```

## Dependencies

Packages can depend on each other. In `setup.py`:

```python
install_requires=[
    "caching",  # Another package in this monorepo
    "pandas",   # External dependency
]
```

When installed with editable mode, cross-package imports work automatically.
