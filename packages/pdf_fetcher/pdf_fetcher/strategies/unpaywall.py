"""
Unpaywall Strategy

Finds open access versions of papers using the Unpaywall API.

This is a meta-strategy that works across ALL publishers by finding
legal, open access versions of papers. Should be tried FIRST before
publisher-specific strategies.

API: https://unpaywall.org/products/api
Rate limit: 100,000 requests/day (free for research)
No authentication required, just email address

Example:
    GET https://api.unpaywall.org/v2/10.1016/j.jpaa.2024.107712?email=YOUR_EMAIL

    Returns:
    {
        "doi": "10.1016/j.jpaa.2024.107712",
        "is_oa": true/false,
        "best_oa_location": {
            "url_for_pdf": "https://arxiv.org/pdf/...",
            "version": "submittedVersion",
            "license": "cc-by"
        },
        "oa_locations": [...]
    }
"""

from typing import Optional, Set
import requests
import logging
import time

# Handle both package import and standalone testing
try:
    from .base import DownloadStrategy
except ImportError:
    from base import DownloadStrategy

logger = logging.getLogger(__name__)


class UnpaywallStrategy(DownloadStrategy):
    """
    Strategy for finding open access PDFs via Unpaywall API.

    Benefits:
    - Works for ANY publisher
    - Finds legal open access versions
    - Fast (single API call)
    - High success rate for OA papers
    - No authentication needed

    Limitations:
    - Only works if OA version exists
    - Rate limited (100k/day - very generous)
    - Requires email address
    """

    def __init__(self, email: str = "research@example.org"):
        """
        Initialize Unpaywall strategy.

        Args:
            email: Your email for Unpaywall API (required)
                   Use your real email - it's for contact, not spam
        """
        super().__init__(name="Unpaywall")
        self.email = email
        self.api_base = "https://api.unpaywall.org/v2"
        self._last_request_time = 0
        self._min_delay = 0.1  # Be nice to API (100ms between requests)

    def can_handle(self, identifier: str, url: Optional[str] = None) -> bool:
        """
        Unpaywall can handle any DOI.

        Returns True if identifier looks like a DOI (starts with 10.)
        """
        # Check if it's a DOI
        if identifier.startswith("10."):
            return True

        # Extract DOI from URL if present
        if url and "10." in url:
            return True

        return False

    def get_pdf_url(
        self, identifier: str, landing_url: str, html_content: str = "", driver=None
    ) -> Optional[str]:
        """
        Find PDF URL via Unpaywall API.

        Process:
        1. Query Unpaywall API with DOI
        2. Check if open access version exists
        3. Return best OA PDF location

        Args:
            identifier: DOI (required)
            landing_url: Not used (Unpaywall doesn't need it)
            html_content: Not used
            driver: Not used

        Returns:
            URL to open access PDF, or None if not available
        """
        self._stats["handled"] += 1

        # Extract clean DOI
        doi = self._extract_doi(identifier, landing_url)
        if not doi:
            logger.warning(f"Could not extract DOI from {identifier}")
            self._stats["pdf_not_found"] += 1
            return None

        # Rate limiting
        self._respect_rate_limit()

        try:
            # Query Unpaywall API
            api_url = f"{self.api_base}/{doi}"
            params = {"email": self.email}

            logger.debug(f"Querying Unpaywall: {api_url}")

            response = requests.get(
                api_url,
                params=params,
                timeout=10,
                headers={"User-Agent": f"Academic PDF Fetcher (mailto:{self.email})"},
            )

            # Track request time for rate limiting
            self._last_request_time = time.time()

            if response.status_code == 404:
                # DOI not found in Unpaywall database
                logger.debug(f"DOI not in Unpaywall database: {doi}")
                self._stats["pdf_not_found"] += 1
                return None

            if response.status_code != 200:
                logger.warning(f"Unpaywall API error {response.status_code}: {doi}")
                self._stats["pdf_not_found"] += 1
                return None

            # Parse response
            data = response.json()

            # Check if open access
            if not data.get("is_oa", False):
                logger.debug(f"No OA version available: {doi}")
                self._stats["pdf_not_found"] += 1
                return None

            # Get best OA location
            best_oa = data.get("best_oa_location")
            if not best_oa:
                # Try first oa_location
                oa_locations = data.get("oa_locations", [])
                if oa_locations:
                    best_oa = oa_locations[0]

            if not best_oa:
                logger.debug(f"OA marked but no location found: {doi}")
                self._stats["pdf_not_found"] += 1
                return None

            # Get PDF URL
            pdf_url = best_oa.get("url_for_pdf") or best_oa.get("url")

            if not pdf_url:
                logger.debug(f"OA location has no PDF URL: {doi}")
                self._stats["pdf_not_found"] += 1
                return None

            # Success!
            version = best_oa.get("version", "unknown")
            license_type = best_oa.get("license", "unknown")

            logger.info(
                f"Found OA PDF via Unpaywall: {doi} "
                f"(version: {version}, license: {license_type})"
            )

            self._stats["pdf_found"] += 1
            return pdf_url

        except requests.Timeout:
            logger.error(f"Unpaywall API timeout: {doi}")
            self._stats["pdf_not_found"] += 1
            return None

        except requests.RequestException as e:
            logger.error(f"Unpaywall API request failed: {e}")
            self._stats["pdf_not_found"] += 1
            return None

        except ValueError as e:
            logger.error(f"Unpaywall API invalid JSON: {e}")
            self._stats["pdf_not_found"] += 1
            return None

    def _extract_doi(self, identifier: str, url: str = "") -> Optional[str]:
        """
        Extract clean DOI from identifier or URL.

        Examples:
            "10.1016/j.jpaa.2024.107712" → "10.1016/j.jpaa.2024.107712"
            "https://doi.org/10.1007/..." → "10.1007/..."
        """
        # If already a clean DOI
        if identifier.startswith("10.") and "/" in identifier:
            # Remove any URL prefix
            if "doi.org/" in identifier:
                return identifier.split("doi.org/")[-1]
            return identifier

        # Try to extract from URL
        for text in [identifier, url]:
            if "10." in text:
                # Find DOI pattern
                import re

                match = re.search(r'10\.\d+/[^\s\'"<>]+', text)
                if match:
                    return match.group(0).rstrip(".,;")

        return None

    def _respect_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_delay:
                time.sleep(self._min_delay - elapsed)

    def should_postpone(self, error_msg: str, html: str = "") -> bool:
        """
        Unpaywall postponement logic.

        Postpone for:
        - API errors (503, 429)
        - Timeout

        Don't postpone for:
        - Not found (404)
        - No OA version (expected)
        """
        error_lower = error_msg.lower()

        # API rate limiting - postpone
        if "429" in error_msg or "rate limit" in error_lower:
            self._stats["postponed"] += 1
            return True

        # API down - postpone
        if "503" in error_msg or "service unavailable" in error_lower:
            self._stats["postponed"] += 1
            return True

        # Timeout - postpone
        if "timeout" in error_lower:
            self._stats["postponed"] += 1
            return True

        # Everything else is permanent (no OA version, etc)
        return False

    def get_priority(self) -> int:
        """
        HIGHEST priority - try Unpaywall FIRST!

        Unpaywall should be attempted before publisher-specific
        strategies because:
        1. Works across all publishers
        2. Bypasses paywalls legally
        3. Fast (single API call)
        4. High success rate for OA papers
        """
        return 5  # Lower = higher priority

    def get_doi_prefixes(self) -> Set[str]:
        """Unpaywall works with any DOI prefix."""
        return set()  # Empty = handles all

    def get_domains(self) -> Set[str]:
        """Unpaywall works with any domain."""
        return set()  # Empty = handles all


if __name__ == "__main__":
    # Test the strategy
    print("=" * 80)
    print("Unpaywall Strategy Test")
    print("=" * 80)

    # NOTE: Use a real email for actual testing
    strategy = UnpaywallStrategy(email="test@example.org")

    # Test can_handle
    print("\n1. Testing can_handle:")
    test_cases = [
        ("10.1016/j.jpaa.2024.107712", True),
        ("10.1007/s10623-024-01403-z", True),
        ("10.1038/nature12345", True),
        ("not-a-doi", False),
        ("https://example.com", False),
    ]

    for identifier, expected in test_cases:
        result = strategy.can_handle(identifier)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {identifier[:40]:40s} -> {result} (expected {expected})")

    # Test DOI extraction
    print("\n2. Testing DOI extraction:")
    doi_cases = [
        ("10.1016/j.jpaa.2024.107712", "10.1016/j.jpaa.2024.107712"),
        ("https://doi.org/10.1007/test", "10.1007/test"),
    ]

    for input_val, expected in doi_cases:
        result = strategy._extract_doi(input_val)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {input_val[:40]:40s} -> {result}")

    # Test real API call (if online)
    print("\n3. Testing real Unpaywall API call:")
    print("   (This requires internet connection)")

    # Use a known OA paper
    test_doi = "10.1371/journal.pone.0000308"  # PLoS ONE - always OA
    print(f"   Testing with OA paper: {test_doi}")

    try:
        pdf_url = strategy.get_pdf_url(
            identifier=test_doi, landing_url=f"https://doi.org/{test_doi}"
        )

        if pdf_url:
            print(f"   ✓ Found PDF: {pdf_url}")
        else:
            print(f"   ✗ No PDF found (unexpected for PLoS ONE)")
    except Exception as e:
        print(f"   ⚠ API call failed: {e}")

    # Test postponement
    print("\n4. Testing should_postpone:")
    error_cases = [
        ("429 Too Many Requests", True),
        ("503 Service Unavailable", True),
        ("Timeout", True),
        ("404 Not Found", False),
        ("No OA version", False),
    ]

    for error, expected in error_cases:
        result = strategy.should_postpone(error)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{error:30s}' -> postpone={result} (expected {expected})")

    # Show stats
    print(f"\n5. Strategy info:")
    print(f"  Name: {strategy.name}")
    print(f"  Priority: {strategy.get_priority()} (lower = higher priority)")
    print(f"  Email: {strategy.email}")
    print(f"  API: {strategy.api_base}")
    print(f"\n  Stats: {strategy.get_stats()}")

    print("\n" + "=" * 80)
    print("✓ Unpaywall strategy ready!")
    print("=" * 80)
    print("\nReminder: Use a real email address when deploying!")
    print("Get one at: https://unpaywall.org/products/api")
