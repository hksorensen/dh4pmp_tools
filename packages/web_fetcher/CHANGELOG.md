# Changelog - web_fetcher

All notable changes to the web_fetcher package.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-12-18

### Major Release - Production Ready

**Breaking Changes:**
- Configuration now uses YAML-only (single source of truth)
  - Removed JSON config support for consistency
  - YAML is more human-readable and standard in scientific computing

**Added:**
- Fully integrated configuration system into PDFFetcher
- PDFFetcher.__init__() now accepts `config`, `config_file`, or `**kwargs`
- Backward compatibility: old API still works via kwargs
- Example configuration file with recommended profiles
- `create_example_config()` function to generate template configs
- Production/Stable development status

**Configuration System:**
- YAML-only configuration (pip install pyyaml)
- Priority: config object > config_file > kwargs > defaults
- All parameters now configurable via YAML file
- Separate PDF and log directories
- Configurable Cloudflare handling strategies

**Logging:**
- Structured logging with console and file outputs
- Automatic download summaries after batch operations
- Log files saved to configurable directory
- Statistics tracking (success/failure/paywall counts)

**Documentation:**
- Complete integration guide
- Example configurations for different use cases
- Migration guide from 0.x versions
- CloudFlare handling strategies documented

### Changed
- Updated from Development/Beta to Production/Stable
- Made PyYAML a required dependency (was optional)
- Improved error messages for missing dependencies
- Enhanced setup.py with full, progress extras

### Fixed
- Corrected date in version history (2024, not 2025)
- Consistent version numbers across all files

## [0.3.0] - 2024-12-18

### Added
- Configuration file support (YAML and JSON)
- Separate log directory configuration
- Structured logging with download summaries
- Improved Cloudflare handling options
- Version tracking system

## [0.2.0] - 2024-12-18

### Added
- PDFDownloader class for DOI-based downloads
- PDF Fetcher v2 with complete reimplementation
- Crossref integration for direct PDF URL lookup
- Enhanced rate limiting with per-domain tracking
- Publisher detection and navigation
- Metadata tracking with JSON storage
- Batch processing with retry support

## [0.1.0] - 2024-11-XX

### Added
- Initial release
- WebPageFetcher and SeleniumWebFetcher
- Basic PDF downloading
- Caching and retry logic

## Migration Guide

### From 0.x to 1.0.0

**No breaking changes to the API!** Old code still works:

```python
# Old way (still works)
fetcher = PDFFetcher(
    pdf_dir="./pdfs",
    metadata_path="./pdfs/metadata.json",
    headless=True
)

# New way (recommended)
fetcher = PDFFetcher(config_file="fetcher_config.yaml")
```

**New features to adopt:**

1. **Create a config file:**
   ```python
   from web_fetcher import create_example_config
   create_example_config("my_config.yaml")
   # Edit my_config.yaml with your settings
   ```

2. **Use config file:**
   ```python
   from web_fetcher import PDFFetcher
   fetcher = PDFFetcher(config_file="my_config.yaml")
   ```

3. **Benefits:**
   - Separate log directory
   - Easier to manage settings
   - Better logging and diagnostics
   - Download summaries for batches

### Removing JSON Config Support

If you had JSON config files from 0.3.0:

```bash
# Convert JSON to YAML (simple Python script)
python << EOF
import json
import yaml

with open('config.json') as f:
    config = json.load(f)

with open('config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)
EOF
```

Or just create a new YAML config:
```python
from web_fetcher import create_example_config
create_example_config("new_config.yaml")
```

## Installation

### Version 1.0.0

```bash
# Full installation (recommended)
pip install -e ".[full]"

# Or step by step
pip install -e .              # Base (includes YAML)
pip install -e ".[selenium]"  # Add Selenium
pip install -e ".[progress]"  # Add progress bars
```

### Dependencies

- **Required:** PyYAML (for YAML config)
- **Recommended:** Selenium (for PDF downloading)
- **Optional:** tqdm (for progress bars)

## Usage Examples

### Basic Usage (v1.0.0)

```python
from web_fetcher import PDFFetcher

# Option 1: Use config file (recommended)
fetcher = PDFFetcher(config_file="fetcher_config.yaml")

# Option 2: Use config file with overrides
fetcher = PDFFetcher(
    config_file="production.yaml",
    pdf_dir="./test_pdfs",  # Override for testing
    headless=False          # Override for debugging
)

# Option 3: Use parameters only (old way)
fetcher = PDFFetcher(
    pdf_dir="./pdfs",
    log_dir="./logs",
    headless=True
)

# Download PDFs
result = fetcher.download("10.1234/example")
results = fetcher.download_batch(dois, batch_size=10)
```

### Creating Config Files

```python
from web_fetcher import create_example_config

# Create template config
create_example_config("my_fetcher_config.yaml")

# Edit the file, then use it
fetcher = PDFFetcher(config_file="my_fetcher_config.yaml")
```

### Configuration Profiles

For different use cases, adjust your YAML config:

**Conservative (avoid Cloudflare):**
```yaml
requests_per_second: 0.5
delay_between_requests: 3.0
delay_between_batches: 30.0
```

**Balanced (default):**
```yaml
requests_per_second: 1.0
delay_between_requests: 2.0
delay_between_batches: 10.0
```

**Aggressive (fast):**
```yaml
requests_per_second: 2.0
delay_between_requests: 1.0
delay_between_batches: 5.0
```

## Support

- Documentation: See README.md and INIT_UPDATE_GUIDE.md
- Issues: https://github.com/hksorensen/dh4pmp_tools/issues
- Examples: See examples/ directory
