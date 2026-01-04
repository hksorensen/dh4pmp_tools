"""
PDF Fetcher - Automated academic PDF downloader

A Python package for automatically downloading academic PDFs using:
- Unpaywall API for open access discovery
- Publisher-specific strategies (Springer, AMS, MDPI, etc.)
- Fallback generic HTML parsing
- SQLite database for tracking downloads
- Parallel downloading with progress tracking
"""

from pdf_fetcher.__version__ import __version__, __author__, __email__
from pdf_fetcher.fetcher import PDFFetcher, DownloadResult
from pdf_fetcher.postponed_cache import PostponedDomainsCache
from pdf_fetcher.utils import (
    sanitize_doi_to_filename,
    get_publisher,
    get_doi_prefix,
    DOI_PREFIX_TO_PUBLISHER,
)

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "PDFFetcher",
    "DownloadResult",
    "PostponedDomainsCache",
    "sanitize_doi_to_filename",
    "get_publisher",
    "get_doi_prefix",
    "DOI_PREFIX_TO_PUBLISHER",
]
