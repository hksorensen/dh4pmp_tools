"""Version information for PDF Fetcher v2."""

__version__ = "0.3.0"
__author__ = "Henrik Kragh Sørensen"
__description__ = "PDF fetcher with DOI resolution, publisher detection, and Cloudflare handling"

# Version history
CHANGELOG = """
0.3.0 (2024-12-18)
------------------
- Added configuration file support (YAML/JSON)
- Added separate log directory configuration
- Added structured logging with download summaries
- Improved Cloudflare handling options
- Added versioning system

0.2.0 (2024-12-18)
------------------
- Reimplementation from scratch with cleaner architecture
- Added Crossref integration for direct PDF URL lookup
- Improved rate limiting and batch processing
- Better publisher detection
- Cloudflare challenge detection and logging

0.1.0 (2024-12-17)
------------------
- Initial implementation
- DOI resolution and PDF downloading
- Basic Selenium support
"""
