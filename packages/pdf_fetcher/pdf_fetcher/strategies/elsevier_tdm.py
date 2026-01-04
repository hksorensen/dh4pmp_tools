"""
Elsevier TDM (Text and Data Mining) Strategy

Uses Elsevier's official TDM API for authorized access to full-text articles.
Requires API key from https://dev.elsevier.com/

This is the PREFERRED strategy for Elsevier content if you have institutional access.
Falls back to scraping (elsevier.py) if TDM fails.

DOI prefixes: 10.1016 (primary)
API: https://api.elsevier.com/content/article/doi/{doi}
Rate limit: Typically 20,000 requests/week with institutional access

Configuration: ~/.config/elsevier.yaml
"""

from typing import Optional, Set, Dict
import requests
import logging
import time
import yaml
from pathlib import Path

# Handle both package import and standalone testing
try:
    from .base import DownloadStrategy
except ImportError:
    from base import DownloadStrategy

logger = logging.getLogger(__name__)


class ElsevierTDMStrategy(DownloadStrategy):
    """
    Strategy for Elsevier TDM API access.
    
    Advantages over scraping:
    - Direct API access (no HTML parsing)
    - Fast and reliable
    - Respects rate limits automatically
    - Legal and authorized
    - Works off-campus (with InstToken)
    
    Requirements:
    - API key from dev.elsevier.com
    - Institutional subscription to content
    - Optional: InstToken for off-campus access
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize Elsevier TDM strategy.
        
        Args:
            config_path: Path to config file (default: ~/.config/elsevier.yaml)
        """
        super().__init__(name="ElsevierTDM")
        
        # Load configuration
        if config_path is None:
            config_path = Path.home() / '.config' / 'elsevier.yaml'
        else:
            config_path = Path(config_path)
        
        self.config = self._load_config(config_path)
        
        # API settings
        self.api_key = self.config.get('api_key')
        self.inst_token = self.config.get('inst_token')
        self.api_base = "https://api.elsevier.com/content/article/doi"
        
        # Rate limiting
        rate_config = self.config.get('rate_limit', {})
        self.requests_per_second = rate_config.get('requests_per_second', 5)
        self.max_requests_per_week = rate_config.get('max_requests_per_week', 20000)
        
        # TDM settings
        tdm_config = self.config.get('tdm', {})
        self.format = tdm_config.get('format', 'pdf')
        self.timeout = tdm_config.get('timeout', 30)
        self.max_retries = tdm_config.get('max_retries', 3)
        
        # Rate limiting state
        self._last_request_time = 0
        self._min_delay = 1.0 / self.requests_per_second
        self._request_count = 0
        self._quota_reset_time = time.time() + (7 * 24 * 3600)  # 7 days
        
        # Validate configuration
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            logger.warning(
                "Elsevier API key not configured! "
                f"Please edit {config_path} and add your API key from dev.elsevier.com"
            )
            self._enabled = False
        else:
            self._enabled = True
            logger.info(f"Elsevier TDM initialized with API key: {self.api_key[:10]}...")
    
    def _load_config(self, config_path: Path) -> Dict:
        """Load configuration from YAML file."""
        if not config_path.exists():
            logger.error(f"Elsevier config not found: {config_path}")
            return {}
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
            return config
        except Exception as e:
            logger.error(f"Error loading Elsevier config: {e}")
            return {}
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        # Check quota
        if self._request_count >= self.max_requests_per_week:
            if time.time() < self._quota_reset_time:
                raise Exception(
                    f"Elsevier API quota exhausted ({self.max_requests_per_week}/week). "
                    f"Resets in {int((self._quota_reset_time - time.time()) / 3600)} hours."
                )
            else:
                # Reset quota
                self._request_count = 0
                self._quota_reset_time = time.time() + (7 * 24 * 3600)
        
        # Enforce delay between requests
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_delay:
            time.sleep(self._min_delay - elapsed)
        
        self._last_request_time = time.time()
        self._request_count += 1
    
    def can_handle(self, identifier: str, url: Optional[str] = None) -> bool:
        """
        Check if this is an Elsevier DOI.
        
        Only handles DOIs with prefix 10.1016 (Elsevier's exclusive prefix).
        """
        if not self._enabled:
            return False
        
        # Only handle Elsevier DOIs
        return identifier.startswith('10.1016/')
    
    def get_pdf_url(
        self, 
        identifier: str, 
        landing_url: str, 
        html_content: str = "",
        driver=None
    ) -> Optional[str]:
        """
        Get PDF directly from Elsevier TDM API.
        
        Unlike scraping strategies, this doesn't parse HTML.
        Instead, it constructs the API URL and lets the fetcher download it.
        
        Args:
            identifier: DOI (e.g., "10.1016/j.jalgebra.2024.07.049")
            landing_url: Unused (API doesn't need landing page)
            html_content: Unused
            driver: Unused
        
        Returns:
            API URL for PDF download, or None if unavailable
        """
        self._stats['handled'] += 1
        
        if not self._enabled:
            logger.debug("Elsevier TDM not enabled (check API key)")
            self._stats['pdf_not_found'] += 1
            return None
        
        try:
            # Rate limiting
            self._rate_limit()
            
            # Construct API URL
            # The API URL itself IS the PDF URL - we just need to add headers
            api_url = f"{self.api_base}/{identifier}"
            
            # Test if article is accessible
            # We'll do a HEAD request to check before returning the URL
            headers = self._get_headers()
            
            response = requests.head(
                api_url,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            if response.status_code == 200:
                self._stats['pdf_found'] += 1
                logger.debug(f"Elsevier TDM: PDF available for {identifier}")
                
                # Return the API URL - fetcher will download it with our custom headers
                return api_url
            
            elif response.status_code == 404:
                logger.debug(f"Elsevier TDM: Article not found {identifier}")
                self._stats['pdf_not_found'] += 1
                return None
            
            elif response.status_code == 403:
                logger.warning(
                    f"Elsevier TDM: Access forbidden for {identifier}. "
                    "Check institutional subscription or add InstToken."
                )
                self._stats['pdf_not_found'] += 1
                return None
            
            else:
                logger.warning(
                    f"Elsevier TDM: Unexpected status {response.status_code} for {identifier}"
                )
                self._stats['pdf_not_found'] += 1
                return None
        
        except Exception as e:
            logger.error(f"Elsevier TDM error for {identifier}: {e}")
            self._stats['pdf_not_found'] += 1
            return None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API request."""
        headers = {
            'X-ELS-APIKey': self.api_key,
            'Accept': 'application/pdf',
            'User-Agent': 'pdf-fetcher/1.0 (Text and Data Mining; research use)'
        }
        
        if self.inst_token:
            headers['X-ELS-Insttoken'] = self.inst_token
        
        return headers
    
    def get_custom_headers(self, identifier: str) -> Dict[str, str]:
        """
        Provide custom headers for fetcher to use when downloading.
        
        This is called by the fetcher when actually downloading the PDF.
        """
        return self._get_headers()
    
    def should_postpone(self, error_msg: str, html: str = "") -> bool:
        """
        Determine if error should postpone vs. fail.
        
        Postpone for:
        - Rate limiting (429)
        - Temporary server errors (503)
        - Quota exceeded (wait for reset)
        
        Fail for:
        - 404 Not Found (article doesn't exist)
        - 403 Forbidden (no access)
        - 401 Unauthorized (bad API key)
        """
        error_lower = error_msg.lower()
        
        # Rate limiting - postpone
        if '429' in error_msg or 'rate limit' in error_lower:
            self._stats['postponed'] += 1
            return True
        
        # Quota exceeded - postpone
        if 'quota exhausted' in error_lower:
            self._stats['postponed'] += 1
            return True
        
        # Server errors - postpone
        if '503' in error_msg or 'service unavailable' in error_lower:
            self._stats['postponed'] += 1
            return True
        
        # 500 - might be temporary
        if '500' in error_msg or 'internal server error' in error_lower:
            self._stats['postponed'] += 1
            return True
        
        # Permanent failures
        # 404, 403, 401 - fail immediately
        return False
    
    def get_priority(self) -> int:
        """
        Very high priority for Elsevier TDM.
        
        Priority 5 = higher than scraping ElsevierStrategy (10)
        This ensures TDM is tried first, falls back to scraping if it fails.
        """
        return 5
    
    def get_doi_prefixes(self) -> Set[str]:
        """Elsevier uses DOI prefix 10.1016"""
        return {'10.1016'}
    
    def get_domains(self) -> Set[str]:
        """Elsevier API domains"""
        return {'api.elsevier.com'}
    
    def get_quota_info(self) -> Dict:
        """Get current quota usage information."""
        time_until_reset = max(0, int(self._quota_reset_time - time.time()))
        return {
            'requests_used': self._request_count,
            'requests_limit': self.max_requests_per_week,
            'requests_remaining': self.max_requests_per_week - self._request_count,
            'reset_in_seconds': time_until_reset,
            'reset_in_hours': time_until_reset / 3600,
        }


if __name__ == '__main__':
    # Test the strategy
    import sys
    
    print("="*80)
    print("Elsevier TDM Strategy Test")
    print("="*80)
    
    # Check if config exists
    config_path = Path.home() / '.config' / 'elsevier.yaml'
    if not config_path.exists():
        print(f"\n✗ Config not found: {config_path}")
        print("Please create config file first.")
        sys.exit(1)
    
    # Initialize strategy
    strategy = ElsevierTDMStrategy()
    
    print(f"\nStrategy: {strategy.name}")
    print(f"Priority: {strategy.get_priority()}")
    print(f"DOI prefixes: {strategy.get_doi_prefixes()}")
    print(f"Enabled: {strategy._enabled}")
    
    if not strategy._enabled:
        print("\n✗ Strategy not enabled. Check API key in config.")
        sys.exit(1)
    
    # Test can_handle
    print("\n" + "-"*80)
    print("Testing can_handle:")
    test_cases = [
        ('10.1016/j.jalgebra.2024.07.049', True),
        ('10.1007/some-paper', False),
        ('10.1016/j.spa.2025.104685', True),
    ]
    
    for doi, expected in test_cases:
        result = strategy.can_handle(doi)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {doi:40s} -> {result} (expected {expected})")
    
    # Test PDF URL retrieval
    print("\n" + "-"*80)
    print("Testing get_pdf_url (with real API call):")
    
    test_doi = '10.1016/j.jalgebra.2024.07.049'
    print(f"\nTesting: {test_doi}")
    
    pdf_url = strategy.get_pdf_url(test_doi, landing_url="", html_content="")
    
    if pdf_url:
        print(f"✓ PDF URL: {pdf_url}")
        print(f"\nHeaders that will be used:")
        for key, value in strategy.get_custom_headers(test_doi).items():
            if 'key' in key.lower():
                print(f"  {key}: {value[:10]}...{value[-4:]}")
            else:
                print(f"  {key}: {value}")
    else:
        print(f"✗ Could not get PDF URL")
    
    # Show stats
    print("\n" + "-"*80)
    print("Statistics:")
    print(f"  {strategy.get_stats()}")
    
    # Show quota
    print("\nQuota Info:")
    quota = strategy.get_quota_info()
    for key, value in quota.items():
        print(f"  {key}: {value}")
