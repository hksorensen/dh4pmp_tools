"""
Base Download Strategy

Abstract base class for publisher-specific download strategies.
Each strategy knows how to handle a specific publisher or domain.

This is the ONLY contract between fetcher and strategies.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Set
import logging

logger = logging.getLogger(__name__)


class DownloadStrategy(ABC):
    """
    Strategy for handling publisher-specific download logic.
    
    Each strategy is INDEPENDENT and TESTABLE.
    Knows how to:
    - Detect if it can handle a URL/identifier
    - Find the PDF URL from a landing page  
    - Determine if errors should postpone vs. fail
    - Provide custom headers if needed
    
    Does NOT:
    - Make HTTP requests (fetcher does that)
    - Save files (fetcher does that)
    - Manage retries (fetcher does that)
    """
    
    def __init__(self, name: str):
        """
        Initialize strategy.
        
        Args:
            name: Human-readable name (e.g., "Springer", "Elsevier")
        """
        self.name = name
        self._stats = {
            'handled': 0,
            'pdf_found': 0,
            'pdf_not_found': 0,
            'postponed': 0,
        }
    
    @abstractmethod
    def can_handle(self, identifier: str, url: Optional[str] = None) -> bool:
        """
        Check if this strategy can handle this identifier/URL.
        
        Called BEFORE download to select the right strategy.
        
        Args:
            identifier: Original identifier (DOI, arXiv ID, etc.)
            url: Resolved landing page URL (if available)
        
        Returns:
            True if this strategy should handle this download
        
        Example:
            # Springer handles dois starting with 10.1007
            if identifier.startswith('10.1007/'):
                return True
            
            # Or URLs from springer.com domain
            if url and 'springer.com' in url:
                return True
        """
        pass
    
    @abstractmethod
    def get_pdf_url(
        self, 
        identifier: str, 
        landing_url: str, 
        html_content: str = "",
        driver=None
    ) -> Optional[str]:
        """
        Extract PDF URL from landing page.
        
        Called AFTER landing page is fetched.
        Strategy examines HTML to find PDF link.
        
        Args:
            identifier: Original identifier
            landing_url: Landing page URL
            html_content: HTML content of landing page
            driver: Selenium WebDriver (if available, for JS-heavy pages)
        
        Returns:
            PDF URL (absolute) or None if not found
        
        Example:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find PDF link with specific class
            link = soup.find('a', class_='pdf-download')
            if link and link.get('href'):
                return urljoin(landing_url, link['href'])
            
            return None
        """
        pass
    
    def should_postpone(self, error_msg: str, html: str = "") -> bool:
        """
        Determine if error should postpone (retry later) vs. fail permanently.
        
        Called AFTER download fails.
        
        Postpone = Temporary issue, might work later
        - Cloudflare challenge
        - Rate limiting  
        - 403 Forbidden (sometimes temporary)
        - 503 Service Unavailable
        
        Fail = Permanent issue, won't work later
        - 404 Not Found
        - Invalid DOI
        - No PDF available
        - Paywall (no access)
        
        Args:
            error_msg: Error message/exception text
            html: HTML content (if available)
        
        Returns:
            True to postpone, False to fail permanently
        
        Default: Never postpone (conservative)
        Override for publisher-specific logic.
        """
        return False
    
    def get_priority(self) -> int:
        """
        Priority for strategy selection (lower = higher priority).
        
        When multiple strategies can handle the same identifier,
        the one with lowest priority number wins.
        
        Priority guidelines:
        - 1-10: Very specific (exact domain match)
        - 11-50: Specific (DOI prefix match)
        - 51-100: Moderate (domain substring)
        - 101-500: Low (generic patterns)
        - 501+: Fallback (catch-all)
        
        Returns:
            Priority number (default: 100)
        """
        return 100
    
    def get_custom_headers(self, identifier: str) -> Dict[str, str]:
        """
        Custom HTTP headers for this publisher.
        
        Some publishers require specific headers:
        - Referer
        - Accept
        - Custom tokens
        
        Args:
            identifier: Identifier being downloaded
        
        Returns:
            Dict of headers to add (empty by default)
        """
        return {}
    
    def preprocess_url(self, url: str) -> str:
        """
        Modify URL before requesting (e.g., add parameters).
        
        Some publishers need URL modifications:
        - Add access tokens
        - Change subdomain
        - Add parameters
        
        Args:
            url: Original URL
        
        Returns:
            Modified URL (default: unchanged)
        """
        return url
    
    def get_doi_prefixes(self) -> Set[str]:
        """
        DOI prefixes this publisher uses.
        
        Used for fast DOI-based matching.
        
        Returns:
            Set of DOI prefixes (e.g., {'10.1007', '10.1038'})
            Empty set if publisher doesn't use DOIs
        """
        return set()
    
    def get_domains(self) -> Set[str]:
        """
        Domains this publisher uses.
        
        Used for fast domain-based matching.
        
        Returns:
            Set of domains (e.g., {'springer.com', 'link.springer.com'})
        """
        return set()
    
    def get_stats(self) -> Dict[str, int]:
        """Get usage statistics for this strategy."""
        return self._stats.copy()
    
    def reset_stats(self):
        """Reset usage statistics."""
        self._stats = {
            'handled': 0,
            'pdf_found': 0,
            'pdf_not_found': 0,
            'postponed': 0,
        }
    
    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(name='{self.name}', priority={self.get_priority()})"
