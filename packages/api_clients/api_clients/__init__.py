"""
API Clients Package

Unified API client framework with specializations for:
- Crossref (primary - easiest to use, no API key needed)
- Scopus
- (Future: OpenAlex, PubMed, etc.)

All clients share:
- Local file-based caching
- Proactive rate limiting
- Exponential backoff for retries
- Comprehensive error handling

Usage:
    # Crossref (default - easiest)
    from api_clients import CrossrefSearchFetcher
    crossref = CrossrefSearchFetcher()  # Auto-loads email from config
    results = crossref.fetch("machine learning")
    
    # Scopus
    from api_clients import ScopusSearchFetcher
    scopus = ScopusSearchFetcher()  # Auto-loads API key from config
    results = scopus.fetch("TITLE-ABS-KEY(machine learning)")
"""

__version__ = "1.1.0"

# Base classes (for advanced users who want to extend)
from .base_client import (
    BaseAPIClient,
    BaseSearchFetcher,
    APIConfig,
    RateLimiter,
    TokenBucket,
    parse_429_response,
)

# Crossref (primary - easiest to use)
from .crossref_client import (
    CrossrefSearchClient,
    CrossrefSearchFetcher,
    CrossrefBibliographicClient,
    CrossrefBibliographicFetcher,
    CrossrefConfig,
)

# Scopus
from .scopus_client import (
    ScopusSearchClient,
    ScopusSearchFetcher,
    ScopusAbstractFetcher,
    ScopusConfig,
)

# Gemini image generation
from .gemini_image_client import (
    GeminiImageClient,
    GeminiImageFetcher,
    GeminiImageConfig,
    get_gemini_api_key,
)

# NOTE: LocalCache and MultiQueryCache have been moved to the 'caching' package
# Import from there instead: from caching import LocalCache, MultiQueryCache

# Main exports (Crossref first as primary/default)
__all__ = [
    # User-facing classes (in order of ease of use)
    "CrossrefSearchFetcher",       # Primary - easiest, no API key
    "CrossrefBibliographicFetcher", # Citation resolution with caching
    "ScopusSearchFetcher",
    "ScopusAbstractFetcher",
    "GeminiImageFetcher",
    
    # Advanced classes (for extension)
    "BaseAPIClient",
    "BaseSearchFetcher",
    "CrossrefSearchClient",
    "CrossrefBibliographicClient",
    "ScopusSearchClient",
    "GeminiImageClient",
    
    # Configuration
    "APIConfig",
    "CrossrefConfig",
    "ScopusConfig",
    "GeminiImageConfig",
    "get_gemini_api_key",
    
    # Utilities
    "RateLimiter",
    "TokenBucket",
    "parse_429_response",
]
