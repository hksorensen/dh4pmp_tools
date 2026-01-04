"""
Springer Publisher Strategy

Handles PDF downloads from Springer and Nature journals.

DOI prefixes: 10.1007 (Springer), 10.1038 (Nature)
Domains: springer.com, link.springer.com, nature.com

Common patterns:
- Landing URL: link.springer.com/article/10.1007/...
- PDF URL: link.springer.com/content/pdf/10.1007/....pdf
- Or: Download button with data-track="click_download_pdf"
"""

#TODO: We need to handle chapters in collections.
# They are characterized by _XXXX at the end of the DOI (e.g. 10.1007/978-3-030-97182-9_1).

from typing import Optional, Set
from urllib.parse import urlparse, urljoin
import logging
import re

# Handle both package import and standalone testing
try:
    from .base import DownloadStrategy
except ImportError:
    from base import DownloadStrategy

logger = logging.getLogger(__name__)


class SpringerStrategy(DownloadStrategy):
    """
    Strategy for Springer/Nature downloads.
    
    Springer quirks:
    - PDF URL often follows pattern: /content/pdf/{DOI}.pdf
    - Download button might require JavaScript
    - Sometimes shows "Buy article" instead of download
    - May require institutional access
    """
    
    def __init__(self):
        super().__init__(name="Springer")
    
    def can_handle(self, identifier: str, url: Optional[str] = None) -> bool:
        """
        Check if this is a Springer/Nature DOI/URL.
        
        Springer uses DOI prefixes 10.1007 and 10.1038 (Nature)
        Domains: springer.com, nature.com
        """
        # Check DOI prefix
        if identifier.startswith('10.1007/') or identifier.startswith('10.1038/'):
            return True
        
        # Check URL domain
        if url:
            parsed = urlparse(url)
            if any(domain in parsed.netloc for domain in [
                'springer.com',
                'nature.com',
            ]):
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
        Find PDF URL on Springer page.
        
        Springer PDF URL patterns:
        1. Direct pattern: link.springer.com/content/pdf/{DOI}.pdf
        2. Download button: <a data-track="click_download_pdf">
        3. Meta tag: <meta name="citation_pdf_url">
        4. Link with class "c-pdf-download__link"
        """
        self._stats['handled'] += 1
        
        # Method 1: Construct direct PDF URL from DOI
        # This is the most reliable for Springer
        if identifier.startswith('10.1007/') or identifier.startswith('10.1038/'):
            # Extract clean DOI
            doi = identifier
            if 'doi.org/' in doi:
                doi = doi.split('doi.org/')[-1]
            
            # Try direct PDF URL pattern
            direct_url = f"https://link.springer.com/content/pdf/{doi}.pdf"
            self._stats['pdf_found'] += 1
            logger.debug(f"Constructed Springer direct PDF URL: {direct_url}")
            return direct_url
        
        # If not a DOI, try parsing HTML
        if not html_content and not driver:
            logger.warning(f"No HTML content or driver for {identifier}")
            self._stats['pdf_not_found'] += 1
            return None
        
        # Method 2: Try BeautifulSoup parsing
        if html_content:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Look for PDF download link with class
                pdf_link = soup.find('a', class_='c-pdf-download__link')
                if pdf_link and pdf_link.get('href'):
                    url = urljoin(landing_url, pdf_link['href'])
                    self._stats['pdf_found'] += 1
                    logger.debug(f"Found Springer PDF (css class): {url}")
                    return url
                
                # Look for download button with data-track attribute
                download_btn = soup.find('a', attrs={'data-track': 'click_download_pdf'})
                if download_btn and download_btn.get('href'):
                    url = urljoin(landing_url, download_btn['href'])
                    self._stats['pdf_found'] += 1
                    logger.debug(f"Found Springer PDF (data-track): {url}")
                    return url
                
                # Look for meta tag
                meta_pdf = soup.find('meta', attrs={'name': 'citation_pdf_url'})
                if meta_pdf and meta_pdf.get('content'):
                    url = meta_pdf['content']
                    self._stats['pdf_found'] += 1
                    logger.debug(f"Found Springer PDF (meta tag): {url}")
                    return url
                
                # Look for any link with /content/pdf/ or .pdf
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '/content/pdf/' in href or (href.endswith('.pdf') and 'download' in href.lower()):
                        url = urljoin(landing_url, href)
                        self._stats['pdf_found'] += 1
                        logger.debug(f"Found Springer PDF (generic): {url}")
                        return url
                
            except ImportError:
                logger.warning("BeautifulSoup not available, trying Selenium")
            except Exception as e:
                logger.error(f"Error parsing Springer HTML: {e}")
        
        # Method 3: Try Selenium if driver available
        if driver:
            try:
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                
                # Try to find PDF download link
                selectors = [
                    (By.CLASS_NAME, "c-pdf-download__link"),
                    (By.CSS_SELECTOR, "a[data-track='click_download_pdf']"),
                    (By.PARTIAL_LINK_TEXT, "Download PDF"),
                ]
                
                for by, selector in selectors:
                    try:
                        element = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((by, selector))
                        )
                        url = element.get_attribute('href')
                        if url:
                            self._stats['pdf_found'] += 1
                            logger.debug(f"Found Springer PDF (selenium {selector}): {url}")
                            return url
                    except:
                        continue  # Try next selector
                
            except Exception as e:
                logger.error(f"Error using Selenium on Springer: {e}")
        
        # PDF not found
        self._stats['pdf_not_found'] += 1
        logger.debug(f"Could not find PDF link for {identifier}")
        return None
    
    def should_postpone(self, error_msg: str, html: str = "") -> bool:
        """
        Springer postponement logic.
        
        Postpone for:
        - 403 Forbidden (might be temporary)
        - Cloudflare
        - Rate limiting
        
        Fail for:
        - 404 Not Found
        - "Buy article" in page (paywall)
        - Invalid DOI
        """
        error_lower = error_msg.lower()
        html_lower = html.lower()
        
        # Cloudflare - postpone
        if 'cloudflare' in error_lower or 'cf-ray' in error_lower:
            self._stats['postponed'] += 1
            return True
        
        # Rate limiting - postpone
        if 'rate limit' in error_lower or '429' in error_lower:
            self._stats['postponed'] += 1
            return True
        
        # 403 - might be temporary, postpone
        if '403' in error_msg or 'forbidden' in error_lower:
            self._stats['postponed'] += 1
            return True
        
        # 503 Service unavailable - postpone
        if '503' in error_msg:
            self._stats['postponed'] += 1
            return True
        
        # Paywall indicators - fail (permanent)
        if any(indicator in html_lower for indicator in [
            'buy article',
            'purchase article',
            'subscription required',
        ]):
            return False
        
        # 404 - fail (permanent)
        if '404' in error_msg:
            return False
        
        # Default: don't postpone
        return False
    
    def get_priority(self) -> int:
        """
        High priority for Springer.
        
        DOI prefixes 10.1007 and 10.1038 are exclusive to Springer/Nature.
        """
        return 10
    
    def get_doi_prefixes(self) -> Set[str]:
        """Springer/Nature DOI prefixes"""
        return {'10.1007', '10.1038'}
    
    def get_domains(self) -> Set[str]:
        """Springer/Nature domains"""
        return {
            'springer.com',
            'link.springer.com',
            'nature.com',
            'link.nature.com',
        }


if __name__ == '__main__':
    # Test the strategy
    print("="*80)
    print("Springer Strategy Test")
    print("="*80)
    
    strategy = SpringerStrategy()
    
    # Test can_handle
    print("\n1. Testing can_handle:")
    test_cases = [
        ('10.1007/s10623-024-01403-z', None, True),  # Real example!
        ('10.1038/nature12345', None, True),
        ('10.1016/j.example', None, False),
        ('paper-123', 'https://link.springer.com/article/10.1007/...', True),
        ('paper-456', 'https://elsevier.com/article', False),
    ]
    
    for identifier, url, expected in test_cases:
        result = strategy.can_handle(identifier, url)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {identifier[:40]:40s} -> {result} (expected {expected})")
    
    # Test PDF URL construction
    print("\n2. Testing PDF URL construction:")
    test_doi = '10.1007/s10623-024-01403-z'
    pdf_url = strategy.get_pdf_url(
        identifier=test_doi,
        landing_url='https://link.springer.com/article/10.1007/s10623-024-01403-z'
    )
    print(f"  DOI: {test_doi}")
    print(f"  PDF URL: {pdf_url}")
    expected_url = "https://link.springer.com/content/pdf/10.1007/s10623-024-01403-z.pdf"
    if pdf_url == expected_url:
        print(f"  ✓ Correct!")
    else:
        print(f"  ✗ Expected: {expected_url}")
    
    # Test postponement
    print("\n3. Testing should_postpone:")
    error_cases = [
        ("403 Forbidden", True),
        ("cloudflare challenge", True),
        ("404 Not Found", False),
        ("rate limit exceeded", True),
    ]
    
    for error, expected in error_cases:
        result = strategy.should_postpone(error)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{error:30s}' -> postpone={result} (expected {expected})")
    
    # Show stats
    print(f"\n4. Strategy info:")
    print(f"  Name: {strategy.name}")
    print(f"  Priority: {strategy.get_priority()}")
    print(f"  DOI prefixes: {strategy.get_doi_prefixes()}")
    print(f"  Domains: {strategy.get_domains()}")
    print(f"\n  Stats: {strategy.get_stats()}")
    
    print("\n" + "="*80)
    print("Ready for real-world testing!")
    print("="*80)
