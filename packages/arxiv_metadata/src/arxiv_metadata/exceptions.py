"""Custom exceptions for arxiv-metadata-fetcher."""


class ArxivFetchError(Exception):
    """Base exception for arXiv fetching errors."""
    pass


class CacheError(ArxivFetchError):
    """Exception raised for cache-related errors."""
    pass


class DownloadError(ArxivFetchError):
    """Exception raised when download fails."""
    pass


class ParseError(ArxivFetchError):
    """Exception raised when parsing metadata fails."""
    pass
