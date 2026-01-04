"""
AMS (American Mathematical Society) Strategy

Handles PDF downloads from AMS publications.

DOI prefix: 10.1090
Domains: ams.org, ams.org/journals

Common patterns:
- Landing URL: ams.org/journals/...
- PDF URL: ams.org/.../article-pdf/...
- Also: Direct PDF link in HTML

AMS publishes:
- Journals: JAMS, TAMS, PROC, etc.
- Memoirs (memo)
- Proceedings (pspum)
- Books
"""

from typing import Optional, Set
from urllib.parse import urlparse, urljoin
import logging
import re

# Handle both package import and standalone testing
try:
    from .base import DownloadStrategy
except ImportError:
    from base import DownloadStrategy

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger(__name__)


class AMSStrategy(DownloadStrategy):
    """
    Strategy for AMS (American Mathematical Society) downloads.

    AMS quirks:
    - PDF URLs vary by publication type (journal, memo, proceedings)
    - Common pattern: /article-pdf/ in URL
    - Open access for older content
    - May require subscription for recent articles
    """

    def __init__(self):
        super().__init__(name="AMS")

    def can_handle(self, identifier: str, url: Optional[str] = None) -> bool:
        """
        Check if this is an AMS DOI/URL.

        AMS uses DOI prefix 10.1090
        Domain: ams.org
        """
        # Check DOI prefix
        if identifier.startswith('10.1090/'):
            return True

        # Check URL domain
        if url:
            parsed = urlparse(url)
            if 'ams.org' in parsed.netloc:
                return True

        return False

    def get_pdf_url(
        self,
        identifier: str,
        landing_url: str,
        html_content: str = "",
        driver=None
    ) -> Optional[str]:
        """
        Find PDF URL on AMS page.

        AMS PDF URL patterns:
        1. HTML parsing for PDF link (most reliable)
        2. Meta tag: <meta name="citation_pdf_url">
        3. Pattern-based construction from DOI

        Examples:
        - 10.1090/memo/1523 → journals/memo/memo1523.pdf
        - 10.1090/pspum/105/19 → pspum/pspum105/19/article-pdf
        """
        self._stats['handled'] += 1

        # Method 1: Parse HTML for PDF links
        if html_content and BeautifulSoup:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')

                # Priority 1: Look for meta tag with PDF URL (most reliable)
                meta_pdf = soup.find('meta', {'name': 'citation_pdf_url'})
                if meta_pdf and meta_pdf.get('content'):
                    pdf_url = meta_pdf['content']
                    logger.info(f"Found AMS PDF in meta tag: {pdf_url}")
                    self._stats['pdf_found'] += 1
                    return pdf_url

                # Priority 2: Look for direct PDF links
                # AMS typically uses links with "article-pdf" or ".pdf" in href
                pdf_links = soup.find_all('a', href=re.compile(r'\.pdf|article-pdf', re.I))

                for link in pdf_links:
                    href = link.get('href', '')
                    link_text = link.get_text(strip=True).lower()

                    # Skip unwanted links
                    skip_patterns = [
                        'license', 'agreement', 'cover', 'preview',
                        'abstract', 'copyright', 'terms'
                    ]

                    if any(skip in href.lower() for skip in skip_patterns):
                        continue

                    if any(skip in link_text for skip in skip_patterns):
                        continue

                    # Make absolute URL
                    if href.startswith('http'):
                        pdf_url = href
                    else:
                        pdf_url = urljoin(landing_url, href)

                    logger.info(f"Found AMS PDF link: {pdf_url}")
                    self._stats['pdf_found'] += 1
                    return pdf_url

                # Look for download button/link
                download_link = soup.find('a', {'class': re.compile(r'download|pdf', re.I)})
                if download_link:
                    href = download_link.get('href', '')
                    if href:
                        pdf_url = urljoin(landing_url, href)
                        logger.info(f"Found AMS download link: {pdf_url}")
                        self._stats['pdf_found'] += 1
                        return pdf_url

            except Exception as e:
                logger.error(f"Error parsing AMS HTML: {e}")

        # Method 2: Try pattern-based construction
        # AMS DOI format: 10.1090/[publication]/[number]
        # Examples:
        #   10.1090/memo/1523
        #   10.1090/pspum/105/19

        doi = identifier
        if 'doi.org/' in doi:
            doi = doi.split('doi.org/')[-1]

        # Extract publication and article ID from DOI
        match = re.match(r'10\.1090/([^/]+)/(.+)', doi)
        if match:
            publication, article_id = match.groups()

            # Try different URL patterns based on publication type
            patterns = [
                f"https://www.ams.org/journals/{publication}/{publication}{article_id}.pdf",
                f"https://www.ams.org/{publication}/{publication}{article_id}/article-pdf",
                f"https://www.ams.org/journals/{publication}/article-pdf/{article_id}",
            ]

            # Return first pattern (will be tested by fetcher)
            logger.debug(f"Trying AMS pattern: {patterns[0]}")
            self._stats['pdf_found'] += 1
            return patterns[0]

        logger.warning(f"Could not find AMS PDF URL for {identifier}")
        self._stats['pdf_not_found'] += 1
        return None

    def should_postpone(self, error_msg: str, html: str = "") -> bool:
        """
        AMS postponement logic.

        Postpone for:
        - Server errors (503, 500)
        - Timeout
        - Cloudflare

        Don't postpone for:
        - 404 (article not found)
        - 403 (paywall/no access)
        - "Buy article"
        """
        error_lower = error_msg.lower()

        # Server errors - postpone
        if '503' in error_msg or '500' in error_msg:
            self._stats['postponed'] += 1
            return True

        # Timeout - postpone
        if 'timeout' in error_lower:
            self._stats['postponed'] += 1
            return True

        # Cloudflare - postpone
        if 'cloudflare' in error_lower or 'checking your browser' in html.lower():
            self._stats['postponed'] += 1
            return True

        # Paywall/no access - don't postpone
        if '403' in error_msg or 'forbidden' in error_lower:
            return False

        if '404' in error_msg:
            return False

        if any(phrase in html.lower() for phrase in ['buy article', 'purchase', 'subscription required']):
            return False

        # Everything else - don't postpone
        return False

    def get_priority(self) -> int:
        """
        AMS priority: 10 (same as other publisher-specific strategies).

        Lower than Unpaywall (5), higher than Generic (100).
        """
        return 10

    def get_doi_prefixes(self) -> Set[str]:
        """AMS DOI prefix."""
        return {'10.1090'}

    def get_domains(self) -> Set[str]:
        """AMS domains."""
        return {'ams.org', 'www.ams.org'}


if __name__ == '__main__':
    # Test the strategy
    print("="*80)
    print("AMS Strategy Test")
    print("="*80)

    strategy = AMSStrategy()

    # Test can_handle
    print("\n1. Testing can_handle:")
    test_cases = [
        ('10.1090/memo/1523', True),
        ('10.1090/pspum/105/19', True),
        ('10.1007/s10623-024-01403-z', False),
        ('10.3390/math9182272', False),
    ]

    for identifier, expected in test_cases:
        result = strategy.can_handle(identifier)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {identifier:40s} -> {result} (expected {expected})")

    # Test pattern matching
    print("\n2. Testing DOI pattern extraction:")
    doi_cases = [
        '10.1090/memo/1523',
        '10.1090/pspum/105/19',
    ]

    for doi in doi_cases:
        match = re.match(r'10\.1090/([^/]+)/(.+)', doi)
        if match:
            pub, article = match.groups()
            print(f"  ✓ {doi} -> publication={pub}, article={article}")
        else:
            print(f"  ✗ {doi} -> no match")

    # Test should_postpone
    print("\n3. Testing should_postpone:")
    error_cases = [
        ("503 Service Unavailable", True),
        ("Timeout", True),
        ("Cloudflare", True),
        ("403 Forbidden", False),
        ("404 Not Found", False),
    ]

    for error, expected in error_cases:
        result = strategy.should_postpone(error)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{error:30s}' -> postpone={result} (expected {expected})")

    # Show stats
    print(f"\n4. Strategy info:")
    print(f"  Name: {strategy.name}")
    print(f"  Priority: {strategy.get_priority()}")
    print(f"  DOI Prefixes: {strategy.get_doi_prefixes()}")
    print(f"  Domains: {strategy.get_domains()}")

    print("\n" + "="*80)
    print("✓ AMS strategy ready!")
    print("="*80)
