"""
Elsevier Publisher Strategy

Handles PDF downloads from Elsevier journals (ScienceDirect).

Common issues seen in metadata:
- "Could not find PDF link" - Need better PDF link detection
- Landing URL: linkinghub.elsevier.com → redirects to sciencedirect.com

DOI prefixes: 10.1016 (primary)
Domains: elsevier.com, sciencedirect.com, linkinghub.elsevier.com
"""

from typing import Optional, Set
from urllib.parse import urlparse, urljoin
import logging

# Handle both package import and standalone testing
try:
    from .base import DownloadStrategy
except ImportError:
    from base import DownloadStrategy

logger = logging.getLogger(__name__)


class ElsevierStrategy(DownloadStrategy):
    """
    Strategy for Elsevier/ScienceDirect downloads.
    
    Elsevier quirks:
    - linkinghub.elsevier.com redirects to sciencedirect.com
    - PDF link often in <a class="article-header-pdf-link">
    - Sometimes requires institutional access
    - May show "Get Access" instead of PDF link
    """
    
    def __init__(self):
        super().__init__(name="Elsevier")
    
    def can_handle(self, identifier: str, url: Optional[str] = None) -> bool:
        """
        Check if this is an Elsevier DOI/URL.
        
        Elsevier uses DOI prefix 10.1016
        Domains: sciencedirect.com, elsevier.com
        """
        # Check DOI prefix
        if identifier.startswith('10.1016/'):
            return True
        
        # Check URL domain
        if url:
            parsed = urlparse(url)
            if any(domain in parsed.netloc for domain in [
                'elsevier.com',
                'sciencedirect.com',
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
        Find PDF URL on Elsevier page.
        
        Elsevier PDF links:
        - Class: "article-header-pdf-link"
        - Or meta tag: <meta name="citation_pdf_url">
        - Or direct URL pattern: /science/article/pii/{PII}/pdfft?isDTMRedir=true
        """
        self._stats['handled'] += 1
        
        if not html_content and not driver:
            logger.warning(f"No HTML content or driver for {identifier}")
            return None
        
        # Try BeautifulSoup parsing
        if html_content:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Method 1: Find PDF link by class
                pdf_link = soup.find('a', class_='article-header-pdf-link')
                if pdf_link and pdf_link.get('href'):
                    url = urljoin(landing_url, pdf_link['href'])
                    self._stats['pdf_found'] += 1
                    logger.debug(f"Found Elsevier PDF (method 1): {url}")
                    return url
                
                # Method 2: Meta tag citation_pdf_url
                meta_pdf = soup.find('meta', attrs={'name': 'citation_pdf_url'})
                if meta_pdf and meta_pdf.get('content'):
                    url = meta_pdf['content']
                    self._stats['pdf_found'] += 1
                    logger.debug(f"Found Elsevier PDF (method 2): {url}")
                    return url
                
                # Method 3: Look for any link with "pdf" in href
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '/pdfft' in href or '/pdf/' in href:
                        url = urljoin(landing_url, href)
                        self._stats['pdf_found'] += 1
                        logger.debug(f"Found Elsevier PDF (method 3): {url}")
                        return url
                
            except ImportError:
                logger.warning("BeautifulSoup not available, trying Selenium")
            except Exception as e:
                logger.error(f"Error parsing Elsevier HTML: {e}")
        
        # Try Selenium if driver available
        if driver:
            try:
                # Wait for PDF link to load
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                
                # Try to find PDF link
                try:
                    element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "article-header-pdf-link"))
                    )
                    url = element.get_attribute('href')
                    if url:
                        self._stats['pdf_found'] += 1
                        logger.debug(f"Found Elsevier PDF (selenium): {url}")
                        return url
                except:
                    pass  # Link not found via Selenium
                
            except Exception as e:
                logger.error(f"Error using Selenium on Elsevier: {e}")
        
        # PDF not found
        self._stats['pdf_not_found'] += 1
        logger.debug(f"Could not find PDF link for {identifier}")
        return None
    
    def should_postpone(self, error_msg: str, html: str = "") -> bool:
        """
        Elsevier postponement logic.
        
        Postpone for:
        - 403 Forbidden (might be temporary access issue)
        - Rate limiting
        - Cloudflare
        
        Fail for:
        - Could not find PDF link (no access or paywall)
        - 404 Not Found
        """
        error_lower = error_msg.lower()
        
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
        if '503' in error_msg or 'service unavailable' in error_lower:
            self._stats['postponed'] += 1
            return True
        
        # These are permanent - fail
        # - Could not find PDF link (paywall/no access)
        # - 404 Not Found
        # - Invalid DOI
        return False
    
    def get_priority(self) -> int:
        """
        High priority for Elsevier.
        
        DOI prefix 10.1016 is exclusively Elsevier.
        """
        return 10
    
    def get_doi_prefixes(self) -> Set[str]:
        """Elsevier uses DOI prefix 10.1016"""
        return {'10.1016'}
    
    def get_domains(self) -> Set[str]:
        """Elsevier domains"""
        return {
            'elsevier.com',
            'sciencedirect.com',
            'linkinghub.elsevier.com',
        }


if __name__ == '__main__':
    # Test the strategy
    print("="*80)
    print("Elsevier Strategy Test")
    print("="*80)
    
    strategy = ElsevierStrategy()
    
    # Test can_handle
    print("\n1. Testing can_handle:")
    test_cases = [
        ('10.1016/j.ecresq.2020.04.004', None, True),
        ('10.1007/some-paper', None, False),
        ('paper-123', 'https://www.sciencedirect.com/science/article/pii/S0095895621001015', True),
        ('paper-456', 'https://springer.com/article', False),
    ]
    
    for identifier, url, expected in test_cases:
        result = strategy.can_handle(identifier, url)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {identifier[:30]:30s} -> {result} (expected {expected})")
    
    # Test postponement
    print("\n2. Testing should_postpone:")
    error_cases = [
        ("403 Forbidden", True),
        ("cloudflare challenge", True),
        ("Could not find PDF link", False),
        ("404 Not Found", False),
        ("rate limit exceeded", True),
    ]
    
    for error, expected in error_cases:
        result = strategy.should_postpone(error)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{error:30s}' -> postpone={result} (expected {expected})")
    
    # Show stats
    print(f"\n3. Strategy info:")
    print(f"  Name: {strategy.name}")
    print(f"  Priority: {strategy.get_priority()}")
    print(f"  DOI prefixes: {strategy.get_doi_prefixes()}")
    print(f"  Domains: {strategy.get_domains()}")
    print(f"\n  Stats: {strategy.get_stats()}")
