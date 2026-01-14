"""
ArXiv Strategy

Downloads PDFs directly from ArXiv.org using ArXiv identifiers.

ArXiv is an open-access preprint repository that provides free access to all papers.
PDFs are directly accessible via a simple URL pattern, making this one of the
simplest and most reliable strategies.

PDF URL Pattern:
    https://arxiv.org/pdf/{arxiv_id}.pdf

ArXiv ID Formats:
    - New format: YYMM.NNNNN (e.g., 2301.12345)
    - Old format: archive/YYMMNNN (e.g., math.GT/0309136)
    - With version: 2301.12345v1 (version suffix is optional)

Examples:
    - ArXiv ID: "2301.12345" → https://arxiv.org/pdf/2301.12345.pdf
    - With version: "2301.12345v1" → https://arxiv.org/pdf/2301.12345v1.pdf
    - Old format: "math.GT/0309136" → https://arxiv.org/pdf/math.GT/0309136.pdf

API Guidelines:
    ArXiv asks for:
    - Rate limiting (be polite, don't hammer servers)
    - Realistic User-Agent
    - Avoid bulk downloads during peak hours (9am-5pm US Eastern)

See: https://info.arxiv.org/help/api/index.html
"""

from typing import Optional, Set
import re
import logging
import time
import threading

# Handle both package import and standalone testing
try:
    from .base import DownloadStrategy
except ImportError:
    from base import DownloadStrategy

logger = logging.getLogger(__name__)


class ArxivStrategy(DownloadStrategy):
    """
    Strategy for downloading PDFs from ArXiv.org.

    Benefits:
    - Open access (always free)
    - Direct PDF URL (no scraping needed)
    - Very reliable servers
    - Fast downloads
    - No authentication required

    Supports multiple identifier formats:
    - ArXiv ID: "2301.12345"
    - Prefixed: "arxiv:2301.12345"
    - With version: "2301.12345v1"
    - Old format: "math.GT/0309136"
    - DOI that resolves to ArXiv: "10.48550/arXiv.2301.12345"
    - ArXiv URL: "https://arxiv.org/abs/2301.12345"

    Rate Limiting:
    - Enforces cooldown between requests (default: 1 second)
    - Respects ArXiv's guidelines for polite API usage
    - Thread-safe for parallel downloads
    """

    # ArXiv ID patterns
    # New format: YYMM.NNNNN(vN)?
    ARXIV_NEW_PATTERN = re.compile(r'(\d{4}\.\d{4,5})(v\d+)?')
    # Old format: archive/YYMMNNN or archive.XX/YYMMNNN
    ARXIV_OLD_PATTERN = re.compile(r'([a-z\-]+(?:\.[A-Z]{2})?/\d{7})')
    # DOI pattern for ArXiv: 10.48550/arXiv.YYMM.NNNNN
    ARXIV_DOI_PATTERN = re.compile(r'10\.48550/arXiv\.(\d{4}\.\d{4,5})(v\d+)?')

    # Class-level rate limiting (shared across all instances)
    _last_request_time = 0
    _rate_limit_lock = threading.Lock()
    _cooldown = 1.0  # Default 1 second cooldown

    # Class-level rate limit pause flag
    # When True, ALL arXiv downloads should be skipped to avoid hammering servers
    _rate_limited = False
    _rate_limit_detected_time = 0

    def __init__(self, cooldown: float = 1.0):
        """
        Initialize ArXiv strategy.

        Args:
            cooldown: Minimum seconds between requests (default: 1.0)
                     Set to 0 to disable rate limiting (not recommended)
        """
        super().__init__(name="ArXiv")
        # Update class-level cooldown if specified
        if cooldown != 1.0:
            ArxivStrategy._cooldown = cooldown

    @classmethod
    def enforce_rate_limit(cls):
        """
        Enforce rate limiting by sleeping if needed.

        Thread-safe: Uses lock to ensure only one thread accesses rate limiter.
        """
        if cls._cooldown <= 0:
            return  # Rate limiting disabled

        with cls._rate_limit_lock:
            now = time.time()
            time_since_last = now - cls._last_request_time

            if time_since_last < cls._cooldown:
                sleep_time = cls._cooldown - time_since_last
                logger.debug(f"ArXiv rate limit: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)

            cls._last_request_time = time.time()

    @classmethod
    def is_rate_limited(cls) -> bool:
        """
        Check if ArXiv is currently rate limited.

        Returns:
            True if ArXiv downloads should be paused
        """
        return cls._rate_limited

    @classmethod
    def set_rate_limited(cls, reason: str = "Rate limit detected"):
        """
        Mark ArXiv as rate limited - pauses ALL ArXiv downloads.

        This is called when we detect captcha, "too many requests", or other
        rate limiting indicators. Once set, all ArXiv downloads will be skipped
        until manually reset.

        Args:
            reason: Reason for rate limiting (for logging)
        """
        cls._rate_limited = True
        cls._rate_limit_detected_time = time.time()
        logger.warning(f"🚫 ArXiv rate limit activated: {reason}")
        logger.warning(f"   All ArXiv downloads will be skipped until reset")

    @classmethod
    def reset_rate_limit(cls):
        """
        Reset ArXiv rate limit flag - allows downloads to resume.

        Call this manually after waiting for rate limit to expire,
        or automatically after a cooldown period.
        """
        if cls._rate_limited:
            duration = time.time() - cls._rate_limit_detected_time
            logger.info(f"✓ ArXiv rate limit reset (was paused for {duration:.0f}s)")
            cls._rate_limited = False
            cls._rate_limit_detected_time = 0

    def can_handle(self, identifier: str, url: Optional[str] = None) -> bool:
        """
        Check if this identifier is from ArXiv.

        Handles:
        - ArXiv IDs (2301.12345, math.GT/0309136)
        - ArXiv DOIs (10.48550/arXiv.2301.12345)
        - ArXiv DOI URLs (https://doi.org/10.48550/arXiv.2301.12345)
        - ArXiv URLs (arxiv.org/abs/...)
        - Prefixed IDs (arxiv:2301.12345)

        Args:
            identifier: The identifier to check
            url: Optional landing page URL

        Returns:
            True if this is an ArXiv paper
        """
        
        # Check for explicit arxiv prefix
        if identifier.lower().startswith('arxiv:'):
            return True

        # Check for ArXiv DOI (bare or as URL)
        if self.ARXIV_DOI_PATTERN.search(identifier):
            return True

        # Check for doi.org URL with ArXiv DOI
        if 'doi.org/10.48550/arXiv' in identifier:
            return True

        # Check for ArXiv URL
        if 'arxiv.org' in identifier.lower():
            return True

        # Check for direct ArXiv ID patterns
        if self.ARXIV_NEW_PATTERN.match(identifier):
            return True

        if self.ARXIV_OLD_PATTERN.match(identifier):
            return True

        # Check URL if provided
        if url and 'arxiv.org' in url.lower():
            return True

        return False

    def extract_arxiv_id(self, identifier: str) -> Optional[str]:
        """
        Extract ArXiv ID from various formats.

        Args:
            identifier: Input identifier (ID, DOI, URL, etc.)

        Returns:
            Clean ArXiv ID or None if not found

        Examples:
            "arxiv:2301.12345v1" → "2301.12345v1"
            "10.48550/arXiv.2301.12345" → "2301.12345"
            "https://arxiv.org/abs/2301.12345" → "2301.12345"
            "2301.12345" → "2301.12345"
        """
        # Remove common prefixes
        identifier = identifier.replace('arxiv:', '').replace('arXiv:', '')

        # Extract from ArXiv DOI
        doi_match = self.ARXIV_DOI_PATTERN.search(identifier)
        if doi_match:
            arxiv_id = doi_match.group(1)
            version = doi_match.group(2) or ''
            return arxiv_id + version

        # Extract from URL
        if 'arxiv.org' in identifier.lower():
            # Handle both /abs/ and /pdf/ URLs
            # https://arxiv.org/abs/2301.12345v1
            # https://arxiv.org/pdf/2301.12345v1.pdf
            parts = identifier.split('/')
            for part in parts:
                # Remove .pdf extension if present
                part = part.replace('.pdf', '')
                # Check if this part is an ArXiv ID
                if self.ARXIV_NEW_PATTERN.match(part):
                    return part
                if self.ARXIV_OLD_PATTERN.match(part):
                    return part

        # Try direct match (new format)
        new_match = self.ARXIV_NEW_PATTERN.match(identifier)
        if new_match:
            arxiv_id = new_match.group(1)
            version = new_match.group(2) or ''
            return arxiv_id + version

        # Try direct match (old format)
        old_match = self.ARXIV_OLD_PATTERN.match(identifier)
        if old_match:
            return old_match.group(1)

        return None

    def get_pdf_url(
        self,
        identifier: str,
        landing_url: str,
        html_content: str = "",
        driver=None
    ) -> Optional[str]:
        """
        Get direct PDF URL from ArXiv ID.

        No HTML parsing needed - ArXiv has a simple URL pattern!

        Args:
            identifier: ArXiv ID or identifier
            landing_url: Landing page URL (not used, but required by interface)
            html_content: HTML content (not used)
            driver: Selenium driver (not used)

        Returns:
            Direct PDF URL or None if ID extraction fails
        """
        # Enforce rate limiting (be polite to ArXiv!)
        self.enforce_rate_limit()

        # Extract clean ArXiv ID
        arxiv_id = self.extract_arxiv_id(identifier)

        if not arxiv_id:
            logger.warning(f"Could not extract ArXiv ID from: {identifier}")
            return None

        # Construct PDF URL
        pdf_url = f"https://export.arxiv.org/pdf/{arxiv_id}.pdf" # Use export.arxiv.org as preferred by arXiv

        logger.debug(f"ArXiv PDF URL: {pdf_url}")
        return pdf_url

    def should_postpone(self, error_msg: str, html: str = "") -> bool:
        """
        Determine if error should postpone vs. fail.

        ArXiv is very reliable, so most errors are permanent:
        - 404 = paper doesn't exist (fail)
        - HTML/captcha response = rate limiting/bot detection (postpone)
        - Network errors = temporary (postpone)

        When rate limiting is detected, this method also sets a class-level
        flag that pauses ALL ArXiv downloads across the entire batch.

        Args:
            error_msg: Error message
            html: HTML content (if any)

        Returns:
            True if should retry later, False if permanent failure
        """
        error_lower = error_msg.lower()

        # Postpone on network/server errors
        if any(x in error_lower for x in ['timeout', 'connection', 'network', '503', '502', '500']):
            return True

        # Postpone if we got HTML instead of PDF (captcha/rate limiting)
        if 'not a pdf' in error_lower or 'html' in error_lower:
            logger.warning(f"ArXiv returned HTML instead of PDF - possible captcha/rate limiting")
            # Activate batch-level pause
            self.set_rate_limited("HTML instead of PDF (captcha/rate limiting)")
            return True

        # Check HTML content for captcha indicators
        if html:
            html_lower = html.lower()
            captcha_indicators = [
                'captcha',
                'recaptcha',
                'verify you are human',
                'security check',
                'unusual traffic',
                'automated requests',
                'too many requests'
            ]
            if any(indicator in html_lower for indicator in captcha_indicators):
                logger.warning(f"ArXiv captcha/rate limit detected - postponing")
                # Activate batch-level pause
                self.set_rate_limited(f"Captcha/rate limit detected in response")
                return True

        # Fail permanently on 404
        if '404' in error_lower or 'not found' in error_lower:
            return False

        # Default: don't postpone (conservative)
        return False

    def get_priority(self) -> int:
        """
        Priority for strategy selection.

        ArXiv gets high priority (5) because:
        - Open access (free for everyone)
        - Very fast and reliable
        - Should be tried before paid publishers

        Priority scale:
        1-10: Very specific / Open access (ArXiv, Unpaywall)
        11-50: Publisher-specific strategies
        51+: Generic/fallback strategies

        Returns:
            Priority 5 (try early, after Unpaywall)
        """
        return 5

    def get_domains(self) -> Set[str]:
        """
        Domains used by ArXiv.

        Returns:
            Set of ArXiv domains
        """
        return {'arxiv.org', 'export.arxiv.org'}

    def get_doi_prefixes(self) -> Set[str]:
        """
        DOI prefixes used by ArXiv.

        ArXiv uses 10.48550 for its DOIs.

        Returns:
            Set containing ArXiv DOI prefix
        """
        return {'10.48550'}

    def __repr__(self) -> str:
        """String representation."""
        return f"ArxivStrategy(name='{self.name}', priority={self.get_priority()})"
