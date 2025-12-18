"""
Web Fetcher - A robust web page fetching library with caching and retry logic.

This package provides classes for fetching web pages with automatic retries,
local file-based caching, and optional Selenium support for JavaScript-heavy
pages and CAPTCHA handling.

New in 0.2.0: PDFDownloader for downloading PDFs from DOIs
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

# PDF Fetcher v2 (spec-compliant implementation)
try:
    from .pdf_fetcher_v2 import (
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
except ImportError:
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

__version__ = "0.2.0"
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
    # v2 exports
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
]
