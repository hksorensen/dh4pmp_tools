"""
zbMath API client — resolves DOIs to MSC classification codes.

Usage:
    config = ZbMathConfig(api_key="your_key")
    client = ZbMathClient(config)
    msc = client.get_msc_by_doi("10.1007/s00222-019-00934-y")
    # Returns e.g. ["11F80", "11R39"] or None if not found
"""

from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from urllib.parse import quote_plus
import logging

from .base_client import BaseAPIClient, APIConfig, RateLimiter
from caching import LocalCache

logger = logging.getLogger(__name__)


# NOTE: Actual endpoint observed during testing:
# - GET /document/_search?search_string=doi:{doi}
# - NOT /document/_doi/{doi} as initially assumed
# - Response structure: {"result": [...], "status": {...}}
# - MSC codes in: result[0]["msc"] as array of {"code": "11F80", "scheme": "msc2020", "text": "..."}
# - API is freely accessible (no authentication required, despite api_key parameter in config)
# - 404 status indicates DOI not found in zbMath database


@dataclass
class ZbMathConfig(APIConfig):
    """zbMath-specific configuration."""
    api_key: str = ""  # Optional — zbMath Open is freely accessible since 2021
    base_url: str = "https://api.zbmath.org/v1"

    # Conservative rate limiting (zbMath documentation suggests 1 req/sec)
    requests_per_second: float = 1.0
    burst_size: int = 3

    # TODO: consolidate with central config system when available


class ZbMathRateLimiter(RateLimiter):
    """zbMath-specific rate limiter."""

    def update_from_headers(self, headers: Dict[str, str]):
        """zbMath does not expose rate limit headers."""
        pass


class ZbMathClient(BaseAPIClient):
    """
    zbMath API client for resolving DOIs to MSC classification codes.

    The zbMath Open database provides freely accessible mathematical
    bibliographic metadata, including MSC (Mathematics Subject Classification)
    codes for mathematical publications.
    """

    def __init__(self, config: ZbMathConfig):
        self.config = config
        self.rate_limiter = ZbMathRateLimiter(config)

        # Initialize cache
        # TODO: consolidate with caching system when that package is finalized
        cache_dir = Path.home() / ".cache" / "dh4pmp" / "zbmath"
        self.cache = LocalCache(cache_dir=cache_dir, compression=True)

        super().__init__(config)

    def _setup_session(self):
        """Setup zbMath session headers."""
        user_agent = "api_clients/1.0"

        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'application/json',
        })

        # Only add Authorization header if api_key is provided
        # Testing confirmed zbMath Open works without authentication
        if self.config.api_key:
            self.session.headers['Authorization'] = f"Bearer {self.config.api_key}"
            logger.info("zbMath client using API key authentication")
        else:
            logger.info("zbMath client using public (unauthenticated) access")

    def _build_search_url(self, query: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Build search URL - not used for DOI lookups."""
        raise NotImplementedError("zbMath client only supports DOI lookups via get_msc_by_doi()")

    def _parse_page_response(self, response_data: Dict[str, Any], page: int) -> Dict[str, Any]:
        """Parse page response - not used for DOI lookups."""
        raise NotImplementedError("zbMath client only supports DOI lookups via get_msc_by_doi()")

    def _get_next_page_url(self, response_data: Dict[str, Any], current_url: str) -> Optional[str]:
        """Get next page URL - not used for DOI lookups."""
        raise NotImplementedError("zbMath client only supports DOI lookups via get_msc_by_doi()")

    def get_msc_by_doi(self, doi: str) -> Optional[List[str]]:
        """
        Resolve a DOI to MSC classification codes.

        This method queries the zbMath Open database for a document by DOI
        and extracts its Mathematics Subject Classification (MSC) codes.
        Results are cached locally to minimize API calls.

        Args:
            doi: DOI string (e.g., "10.1007/s00222-019-00934-y")

        Returns:
            List of MSC codes with primary code first (e.g., ["11F80", "11R39"])
            or None if:
            - DOI not found in zbMath database (404)
            - No MSC codes available for the document
            - Request failed after retries

        Example:
            >>> client = ZbMathClient(ZbMathConfig())
            >>> msc = client.get_msc_by_doi("10.1215/00127094-1723706")
            >>> print(msc)
            ['22E57', '11F70', '11F80', '11R39', '14G35']

        Note:
            A 404 response means the DOI is not in zbMath's database.
            This is expected for many DOIs, as zbMath focuses on mathematical
            literature. The method will log a warning and return None.
        """
        # Check cache first
        cache_key = f"doi:{doi}"
        if self.cache.has(cache_key):
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for DOI: {doi}")
                # Cache stores the raw JSON response
                return self._parse_msc_codes(cached)

        # Build request URL
        # Observed endpoint format: /document/_search?search_string=doi:{doi}
        search_string = f"doi:{doi}"
        url = f"{self.config.base_url}/document/_search?search_string={quote_plus(search_string)}"

        logger.info(f"Fetching MSC codes for DOI: {doi}")

        # Make request
        response = self._make_request(url)

        if response is None:
            logger.error(f"Failed to fetch DOI {doi} after retries")
            return None

        # Handle 404 - DOI not found in zbMath
        if response.status_code == 404:
            logger.warning(f"DOI not found in zbMath database: {doi}")
            # Cache negative result to avoid repeated lookups
            self.cache.store(cache_key, {"result": None}, total_results=0, num_pages=0)
            return None

        # Parse response
        try:
            data = response.json()
        except ValueError as e:
            logger.error(f"Invalid JSON response for DOI {doi}: {e}")
            return None

        # Cache the raw response
        self.cache.store(cache_key, data, total_results=1, num_pages=1)

        # Parse and return MSC codes
        return self._parse_msc_codes(data)

    def _parse_msc_codes(self, data: Dict[str, Any]) -> Optional[List[str]]:
        """
        Parse MSC codes from zbMath API response.

        Response structure observed:
        {
            "result": [
                {
                    "msc": [
                        {"code": "22E57", "scheme": "msc2020", "text": "..."},
                        {"code": "11F70", "scheme": "msc2020", "text": "..."},
                        ...
                    ],
                    ...
                }
            ],
            "status": {"status_code": 200, ...}
        }

        Args:
            data: JSON response from zbMath API

        Returns:
            List of MSC codes (primary code first) or None if no codes found
        """
        # Check if result exists and is not empty
        result = data.get("result")
        if not result or not isinstance(result, list) or len(result) == 0:
            logger.warning("No results found in zbMath response")
            return None

        # Get first document (zbMath returns array but DOI search should return single result)
        document = result[0]

        # Extract MSC codes
        msc_entries = document.get("msc")
        if not msc_entries or not isinstance(msc_entries, list):
            logger.warning("No MSC codes found in document")
            return None

        # Extract code strings (first code is primary)
        # Actual field names observed: "code", "scheme", "text"
        msc_codes = []
        for entry in msc_entries:
            if isinstance(entry, dict) and "code" in entry:
                code = entry["code"]
                if code:  # Skip None/empty codes
                    msc_codes.append(code)

        if not msc_codes:
            logger.warning("MSC entries present but no valid codes extracted")
            return None

        logger.info(f"Found {len(msc_codes)} MSC codes (primary: {msc_codes[0]})")
        return msc_codes


def get_msc(doi: str, api_key: str = "") -> Optional[List[str]]:
    """
    Convenience wrapper: resolve a single DOI to MSC codes.

    Args:
        doi: DOI string
        api_key: Optional API key (zbMath Open works without authentication)

    Returns:
        List of MSC codes or None if not found

    Example:
        >>> msc = get_msc("10.1215/00127094-1723706")
        >>> print(msc)
        ['22E57', '11F70', '11F80', '11R39', '14G35']
    """
    config = ZbMathConfig(api_key=api_key)
    client = ZbMathClient(config)
    return client.get_msc_by_doi(doi)
