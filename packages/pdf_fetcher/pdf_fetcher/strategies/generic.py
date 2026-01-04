"""
Generic Fallback Strategy

Handles DOIs from publishers we don't have specific strategies for.
Uses common patterns to try to find PDF links.
"""

from .base import DownloadStrategy
from typing import Optional
import re

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


class GenericStrategy(DownloadStrategy):
    """
    Generic fallback strategy for unknown publishers.

    Tries common patterns:
    - doi.org redirect
    - meta tags (citation_pdf_url)
    - common link patterns
    """

    def __init__(self):
        super().__init__(name="Generic Fallback")

    def get_priority(self) -> int:
        """Lowest priority - only used as last resort."""
        return 1000

    def can_handle(self, identifier: str) -> bool:
        """Can handle any DOI as fallback."""
        return identifier.startswith("10.")

    def get_landing_url(self, identifier: str) -> str:
        """Get landing page URL via doi.org resolver."""
        return f"https://doi.org/{identifier}"

    def get_pdf_url(
        self, identifier: str, landing_url: str, html_content: Optional[str] = None
    ) -> Optional[str]:
        """
        Try to find PDF URL using common patterns.

        Tries in order of reliability:
        1. Meta tags (citation_pdf_url, DC.identifier)
        2. BeautifulSoup link text matching (PDF, Download PDF, etc.)
        3. Specific publisher URL patterns (/doi/pdf/, /content/pdf/, etc.)
        4. Data attributes (data-pdf-url, data-download)
        5. Class-based patterns (class="pdf-download", etc.)
        6. Generic PDF link patterns (.pdf, /pdf/, /download/)
        """
        if not html_content:
            return None

        from urllib.parse import urlparse, urljoin

        # Helper to make URLs absolute
        def make_absolute(url):
            if url.startswith("http"):
                return url
            return urljoin(landing_url, url)

        # Method 1: Meta tags (most reliable)
        meta_patterns = [
            r'<meta\s+name=["\']citation_pdf_url["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+name=["\']DC\.identifier["\']\s+content=["\']([^"\']+\.pdf[^"\']*)["\']',
            r'<meta\s+property=["\']og:pdf["\']\s+content=["\']([^"\']+)["\']',
        ]

        for pattern in meta_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                return make_absolute(match.group(1))

        # Method 2: BeautifulSoup link text matching (if available)
        if BeautifulSoup:
            try:
                soup = BeautifulSoup(html_content, "html.parser")

                # Look for links with PDF-related text
                pdf_text_patterns = [
                    re.compile(r"^\s*PDF\s*$", re.I),
                    re.compile(r"Download\s+PDF", re.I),
                    re.compile(r"Full\s+Text\s+PDF", re.I),
                    re.compile(r"View\s+PDF", re.I),
                    re.compile(r"Download\s+Article", re.I),
                ]

                for link in soup.find_all("a", href=True):
                    link_text = link.get_text(strip=True)
                    for text_pattern in pdf_text_patterns:
                        if text_pattern.search(link_text):
                            return make_absolute(link["href"])

            except Exception:
                pass  # BeautifulSoup parsing failed, continue with regex

        # Method 3: Specific publisher URL patterns
        specific_patterns = [
            r'href=["\']([^"\']*\/doi\/pdf\/[^"\']+)["\']',  # /doi/pdf/ (common)
            r'href=["\']([^"\']*\/content\/pdf\/[^"\']+)["\']',  # /content/pdf/
            r'href=["\']([^"\']*\/fulltext\.pdf[^"\']*)["\']',  # /fulltext.pdf
            r'href=["\']([^"\']*\/article[^"\']*\.pdf[^"\']*)["\']',  # /article/...pdf
            r'href=["\']([^"\']*\/viewPDFInterstitial[^"\']*)["\']',  # Oxford pattern
            r'href=["\']([^"\']*\/pdf\/[0-9\.]+[^"\']*)["\']',  # /pdf/10.xxxx/...
        ]

        for pattern in specific_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                return make_absolute(match.group(1))

        # Method 4: Data attributes
        data_patterns = [
            r'data-pdf-url=["\']([^"\']+)["\']',
            r'data-download=["\']([^"\']+\.pdf[^"\']*)["\']',
            r'data-article-pdf=["\']([^"\']+)["\']',
        ]

        for pattern in data_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                return make_absolute(match.group(1))

        # Method 5: Class-based patterns
        class_patterns = [
            r'class=["\'][^"\']*pdf-download[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
            r'class=["\'][^"\']*download-pdf[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
            r'class=["\'][^"\']*full-text[^"\']*["\'][^>]*href=["\']([^"\']+\.pdf[^"\']*)["\']',
        ]

        for pattern in class_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                return make_absolute(match.group(1))

        # Method 6: Generic PDF link patterns (least reliable, cast wide net)
        generic_patterns = [
            r'href=["\']([^"\']*\.pdf[^"\']*)["\']',  # .pdf files
            r'href=["\']([^"\']*\/pdf\/[^"\']*)["\']',  # /pdf/ paths
            r'href=["\']([^"\']*\/download\/[^"\']*)["\']',  # /download/ paths
            r'href=["\']([^"\']*/getPDF[^"\']*)["\']',  # /getPDF
        ]

        for pattern in generic_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                # Filter out obvious non-PDFs (images, css, js, etc.)
                for url in matches:
                    url_lower = url.lower()
                    if any(
                        ext in url_lower for ext in [".jpg", ".png", ".css", ".js", ".gif", ".svg"]
                    ):
                        continue
                    # Filter out tracking/analytics
                    if any(word in url_lower for word in ["tracking", "analytics", "pixel"]):
                        continue
                    return make_absolute(url)

        return None

    def should_postpone(self, error_message: str) -> bool:
        """
        Determine if error is temporary and should be retried.

        Args:
            error_message: Error message string

        Returns:
            True if should retry later, False if permanent failure
        """
        error_lower = error_message.lower()

        # Temporary errors - should retry
        temporary_indicators = [
            "403",  # Might be temporary access issue
            "429",  # Rate limiting
            "503",  # Service unavailable
            "504",  # Gateway timeout
            "timeout",
            "cloudflare",
            "rate limit",
        ]

        for indicator in temporary_indicators:
            if indicator in error_lower:
                return True

        # Permanent errors - don't retry
        permanent_indicators = [
            "could not find pdf",
            "404",
            "not found",
            "invalid doi",
        ]

        for indicator in permanent_indicators:
            if indicator in error_lower:
                return False

        # Default: assume temporary (be optimistic)
        return True


if __name__ == "__main__":
    # Quick test
    strategy = GenericStrategy()

    print("Testing GenericStrategy...")
    print(f"Priority: {strategy.get_priority()}")
    print(f"Can handle 10.1234/test: {strategy.can_handle('10.1234/test')}")
    print(f"Landing URL: {strategy.get_landing_url('10.1234/test')}")
    print("\n✓ GenericStrategy works!")
