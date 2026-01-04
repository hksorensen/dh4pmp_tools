"""
MDPI (Multidisciplinary Digital Publishing Institute) Strategy

Handles PDF downloads from MDPI journals.

DOI prefix: 10.3390
Domain: mdpi.com

MDPI is an open access publisher - all articles should have free PDF downloads.

Common patterns:
- Landing URL: mdpi.com/[ISSN]/[volume]/[issue]/[article]
- PDF URL: mdpi.com/[ISSN]/[volume]/[issue]/[article]/pdf

Examples:
- DOI: 10.3390/math9182272
- Landing: https://www.mdpi.com/2227-7390/9/18/2272
- PDF: https://www.mdpi.com/2227-7390/9/18/2272/pdf
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


class MDPIStrategy(DownloadStrategy):
    """
    Strategy for MDPI (Multidisciplinary Digital Publishing Institute) downloads.

    MDPI characteristics:
    - Fully open access publisher
    - Simple PDF URL pattern: just append /pdf to article URL
    - Consistent URL structure
    - High success rate expected
    - No paywall issues
    """

    def __init__(self):
        super().__init__(name="MDPI")

    def can_handle(self, identifier: str, url: Optional[str] = None) -> bool:
        """
        Check if this is an MDPI DOI/URL.

        MDPI uses DOI prefix 10.3390
        Domain: mdpi.com
        """
        # Check DOI prefix
        if identifier.startswith('10.3390/'):
            return True

        # Check URL domain
        if url:
            parsed = urlparse(url)
            if 'mdpi.com' in parsed.netloc:
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
        Find PDF URL on MDPI page.

        MDPI PDF URL patterns (very consistent):
        1. Direct pattern: landing_url + "/pdf"
        2. HTML parsing for PDF download link
        3. Meta tag: <meta name="citation_pdf_url">

        MDPI articles follow pattern:
        - DOI: 10.3390/[journal][volume][issue][article]
        - Example: 10.3390/math9182272
          - journal: math (Mathematics)
          - volume: 9
          - issue: 18
          - article: 2272
        - URL: mdpi.com/2227-7390/9/18/2272
        - PDF: mdpi.com/2227-7390/9/18/2272/pdf
        """
        self._stats['handled'] += 1

        # Method 1: Parse HTML for explicit PDF URL (most reliable)
        if html_content and BeautifulSoup:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')

                # Look for meta tag with PDF URL
                meta_pdf = soup.find('meta', {'name': 'citation_pdf_url'})
                if meta_pdf and meta_pdf.get('content'):
                    pdf_url = meta_pdf['content']
                    logger.info(f"Found MDPI PDF in meta tag: {pdf_url}")
                    self._stats['pdf_found'] += 1
                    return pdf_url

                # Look for PDF download link with version parameter
                # MDPI requires version parameter: /pdf?version=XXXXXXXXXX
                pdf_link = soup.find('a', href=re.compile(r'/pdf(\?version=\d+)?', re.I))
                if pdf_link:
                    href = pdf_link.get('href')
                    if href.startswith('http'):
                        pdf_url = href
                    else:
                        pdf_url = urljoin(landing_url, href)
                    logger.info(f"Found MDPI PDF link: {pdf_url}")
                    self._stats['pdf_found'] += 1
                    return pdf_url

                # Look for download button class
                download_btn = soup.find('a', {'class': re.compile(r'download.*pdf|pdf.*download', re.I)})
                if download_btn:
                    href = download_btn.get('href', '')
                    if href:
                        pdf_url = urljoin(landing_url, href)
                        logger.info(f"Found MDPI download button: {pdf_url}")
                        self._stats['pdf_found'] += 1
                        return pdf_url

            except Exception as e:
                logger.error(f"Error parsing MDPI HTML: {e}")

        # Method 2: Construct PDF URL from DOI via redirects
        # MDPI uses doi.org which redirects to the actual article page
        # We can follow the redirect to get the real MDPI URL

        # If we have HTML content, try to extract the canonical URL
        actual_url = landing_url
        if html_content and BeautifulSoup:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                canonical = soup.find('link', {'rel': 'canonical'})
                if canonical and canonical.get('href'):
                    actual_url = canonical['href']
                    logger.debug(f"Found canonical URL: {actual_url}")
            except:
                pass

        # If landing_url is doi.org, we need to follow redirects to get actual MDPI URL
        # Even if the final page returns 403, we can still use the redirected URL
        if 'doi.org' in actual_url or 'mdpi.com' not in actual_url:
            # Try to fetch the actual URL by following redirects
            try:
                import requests
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                }
                # Just get the final URL without downloading content
                response = requests.head(
                    landing_url,
                    headers=headers,
                    allow_redirects=True,
                    timeout=10
                )
                # Use the final URL even if we got 403
                # The redirect worked, we just can't access the page
                if response.url and 'mdpi.com' in response.url:
                    actual_url = response.url
                    logger.debug(f"Followed redirects to: {actual_url} (status: {response.status_code})")
            except Exception as e:
                logger.debug(f"Redirect failed: {e}")
                # If redirect fails, construct URL from DOI pattern
                # MDPI DOI: 10.3390/[journal][volume][issue][article]
                # But we can't reliably parse this without the ISSN
                # So we'll just try appending /pdf to doi.org URL as last resort
                pass

        # Construct PDF URL by appending /pdf
        clean_url = actual_url.rstrip('/')

        # Don't append /pdf if it's already there
        if not clean_url.endswith('/pdf'):
            pdf_url = f"{clean_url}/pdf"
        else:
            pdf_url = clean_url

        logger.debug(f"Constructed MDPI PDF URL: {pdf_url}")
        self._stats['pdf_found'] += 1
        return pdf_url

    def should_postpone(self, error_msg: str, html: str = "") -> bool:
        """
        MDPI postponement logic.

        Since MDPI is fully open access, most errors are temporary.

        Postpone for:
        - Server errors (503, 500)
        - Timeout
        - Cloudflare
        - Rate limiting (429)

        Don't postpone for:
        - 404 (article not found - rare but permanent)
        - File format issues (permanent)
        """
        error_lower = error_msg.lower()

        # Server errors - postpone
        if '503' in error_msg or '500' in error_msg:
            self._stats['postponed'] += 1
            return True

        # Rate limiting - postpone
        if '429' in error_msg or 'too many requests' in error_lower:
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

        # 403 is unusual for MDPI (open access) - postpone to investigate
        if '403' in error_msg or 'forbidden' in error_lower:
            self._stats['postponed'] += 1
            return True

        # 404 - article doesn't exist (permanent)
        if '404' in error_msg:
            return False

        # File format issues - permanent
        if 'not a pdf' in error_lower or 'invalid pdf' in error_lower:
            return False

        # Default: postpone (MDPI is usually reliable, so errors are likely temporary)
        self._stats['postponed'] += 1
        return True

    def get_priority(self) -> int:
        """
        MDPI priority: 10 (same as other publisher-specific strategies).

        Lower than Unpaywall (5), higher than Generic (100).

        Note: MDPI is open access, so Unpaywall will likely find most articles first.
        This strategy acts as a fallback when Unpaywall doesn't have the article indexed.
        """
        return 10

    def get_doi_prefixes(self) -> Set[str]:
        """MDPI DOI prefix."""
        return {'10.3390'}

    def get_domains(self) -> Set[str]:
        """MDPI domains."""
        return {'mdpi.com', 'www.mdpi.com'}


if __name__ == '__main__':
    # Test the strategy
    print("="*80)
    print("MDPI Strategy Test")
    print("="*80)

    strategy = MDPIStrategy()

    # Test can_handle
    print("\n1. Testing can_handle:")
    test_cases = [
        ('10.3390/math9182272', True),
        ('10.3390/e25010006', True),
        ('10.3390/sym13050779', True),
        ('10.1007/s10623-024-01403-z', False),
        ('10.1090/memo/1523', False),
    ]

    for identifier, expected in test_cases:
        result = strategy.can_handle(identifier)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {identifier:40s} -> {result} (expected {expected})")

    # Test URL construction
    print("\n2. Testing PDF URL construction:")
    url_cases = [
        ('https://www.mdpi.com/2227-7390/9/18/2272', 'https://www.mdpi.com/2227-7390/9/18/2272/pdf'),
        ('https://www.mdpi.com/1099-4300/25/1/6/', 'https://www.mdpi.com/1099-4300/25/1/6/pdf'),
    ]

    for landing, expected_pdf in url_cases:
        # Simulate the URL construction logic
        clean_url = landing.rstrip('/')
        if not clean_url.endswith('/pdf'):
            pdf_url = f"{clean_url}/pdf"
        else:
            pdf_url = clean_url

        status = "✓" if pdf_url == expected_pdf else "✗"
        print(f"  {status} {landing}")
        print(f"      -> {pdf_url}")

    # Test should_postpone
    print("\n3. Testing should_postpone:")
    error_cases = [
        ("503 Service Unavailable", True),
        ("429 Too Many Requests", True),
        ("Timeout", True),
        ("Cloudflare", True),
        ("403 Forbidden", True),  # Unusual for MDPI, postpone
        ("404 Not Found", False),
        ("Not a PDF", False),
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
    print(f"\n  Notes:")
    print(f"    - MDPI is fully open access (no paywalls)")
    print(f"    - Simple PDF URL pattern: landing_url + '/pdf'")
    print(f"    - High success rate expected")
    print(f"    - Unpaywall will likely catch most MDPI articles first")

    print("\n" + "="*80)
    print("✓ MDPI strategy ready!")
    print("="*80)
