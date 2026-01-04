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

# Note: PDFFetcher has been moved to a standalone package
# Install with: pip install -e packages/pdf_fetcher
# Import with: from pdf_fetcher import BasePDFFetcher, DownloadResult

# Note: Pipeline base classes have been moved to the 'pipelines' package
# Import them with: from pipelines import BasePipeline, PipelineConfig, PipelineResult

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
]
