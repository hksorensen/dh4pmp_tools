"""
arXiv Metadata Fetcher
======================

A streamlined toolkit for fetching and filtering arXiv metadata.

Basic usage:
    >>> from arxiv_metadata import ArxivMetadata, Category
    >>> fetcher = ArxivMetadata()
    >>> df = fetcher.fetch(categories=Category.MATH, years=2024)
"""

from .fetcher import ArxivMetadata
from .filters import Category, FilterBuilder
from .exceptions import ArxivFetchError, CacheError

__version__ = "0.1.0"
__all__ = [
    "ArxivMetadata",
    "Category", 
    "FilterBuilder",
    "ArxivFetchError",
    "CacheError",
]
