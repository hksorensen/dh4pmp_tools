"""
Web Fetcher - A robust web page fetching library with caching and retry logic.

This package provides classes for fetching web pages with automatic retries,
local file-based caching, and optional Selenium support for JavaScript-heavy
pages and CAPTCHA handling.

Version 1.0.0: Production release with integrated configuration system
"""

from .core import WebPageFetcher

try:
    from .selenium_fetcher import SeleniumWebFetcher, SELENIUM_AVAILABLE, CloudflareRateLimitError
    from .pdf_downloader import (
        PDFDownloader,
        PDFDownloadError,
        PaywallError,
        PDFNotFoundError,
    )
    # Export By for convenience
    try:
        from selenium.webdriver.common.by import By
    except ImportError:
        By = None
except ImportError:
    # Selenium not installed, only provide core functionality
    SELENIUM_AVAILABLE = False
    SeleniumWebFetcher = None
    PDFDownloader = None
    By = None
    CloudflareRateLimitError = None
    PDFDownloadError = None
    PaywallError = None
    PDFNotFoundError = None

# PDF Fetcher (spec-compliant implementation with YAML configuration)
try:
    from .pdf_fetcher import (
        PDFFetcher,
        DownloadStatus,
        DownloadResult,
        RateLimiter,
        IdentifierNormalizer,
        PublisherDetector,
        DOIResolver,
        PDFLinkFinder,
        DownloadManager,
        MetadataStore,
    )
    # Configuration system (YAML-only)
    from .config import PDFFetcherConfig, load_config, create_example_config
    from .logging_config import setup_logging, create_download_summary_log
    # Version info
    from .version import __version__ as _pdf_fetcher_version, CHANGELOG
except ImportError as e:
    PDFFetcher = None
    DownloadStatus = None
    DownloadResult = None
    RateLimiter = None
    IdentifierNormalizer = None
    PublisherDetector = None
    DOIResolver = None
    PDFLinkFinder = None
    DownloadManager = None
    MetadataStore = None
    PDFFetcherConfig = None
    load_config = None
    create_example_config = None
    setup_logging = None
    create_download_summary_log = None
    _pdf_fetcher_version = None
    CHANGELOG = None

__version__ = "1.0.0"
__author__ = "Henrik Sørensen"

__all__ = [
    "WebPageFetcher",
    "SeleniumWebFetcher",
    "PDFDownloader",
    "SELENIUM_AVAILABLE",
    "By",
    "CloudflareRateLimitError",
    "PDFDownloadError",
    "PaywallError",
    "PDFNotFoundError",
    # PDF Fetcher core
    "PDFFetcher",
    "DownloadStatus",
    "DownloadResult",
    "RateLimiter",
    "IdentifierNormalizer",
    "PublisherDetector",
    "DOIResolver",
    "PDFLinkFinder",
    "DownloadManager",
    "MetadataStore",
    # PDF Fetcher configuration (YAML-only)
    "PDFFetcherConfig",
    "load_config",
    "create_example_config",
    "setup_logging",
    "create_download_summary_log",
    "CHANGELOG",
]
