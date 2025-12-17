"""
Web Fetcher - A robust web page fetching library with caching and retry logic.

This package provides classes for fetching web pages with automatic retries,
local file-based caching, and optional Selenium support for JavaScript-heavy
pages and CAPTCHA handling.
"""

from .core import WebPageFetcher

try:
    from .selenium_fetcher import SeleniumWebFetcher, SELENIUM_AVAILABLE, CloudflareRateLimitError
    # Export By for convenience
    try:
        from selenium.webdriver.common.by import By
    except ImportError:
        By = None
except ImportError:
    # Selenium not installed, only provide core functionality
    SELENIUM_AVAILABLE = False
    SeleniumWebFetcher = None
    By = None
    CloudflareRateLimitError = None

__version__ = "0.1.0"
__author__ = "Henrik Sørensen"

__all__ = [
    "WebPageFetcher",
    "SeleniumWebFetcher",
    "SELENIUM_AVAILABLE",
    "By",
    "CloudflareRateLimitError",
]
