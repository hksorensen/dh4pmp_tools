"""
PDF Downloader - Specialized web fetcher for downloading PDFs from DOIs.

This module provides a PDFDownloader class that extends SeleniumWebFetcher
to handle the complex process of resolving DOIs to PDF files, including:
- Publisher landing page navigation
- PDF link/button detection
- Cloudflare and CAPTCHA handling
- Paywall detection and graceful failure
- Local caching with metadata tracking
"""

import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin, urlparse
import hashlib
from datetime import datetime

try:
    from .selenium_fetcher import SeleniumWebFetcher, CloudflareRateLimitError
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    SeleniumWebFetcher = None

import logging
logger = logging.getLogger(__name__)


class PDFDownloadError(Exception):
    """Base exception for PDF download errors."""
    pass


class PaywallError(PDFDownloadError):
    """Raised when content is behind a paywall."""
    pass


class PDFNotFoundError(PDFDownloadError):
    """Raised when PDF cannot be found on landing page."""
    pass


class PDFDownloader:
    """
    Download PDFs from DOIs with intelligent navigation and caching.
    
    This class handles the complete pipeline from DOI to PDF file:
    1. Resolve DOI to publisher landing page
    2. Detect and navigate to PDF download
    3. Handle various publisher patterns
    4. Save PDF with metadata
    5. Track download status
    
    Attributes:
        pdf_dir: Directory to store downloaded PDFs
        cache_dir: Directory for web page caching
        metadata_tracking: Whether to create .json sidecar files
        max_retries: Maximum retry attempts
        headless: Whether to run browser in headless mode
    """
    
    # Common publisher patterns for PDF detection
    PUBLISHER_PATTERNS = {
        'nature': {
            'domains': ['nature.com', 'springernature.com'],
            'pdf_selectors': [
                'a[data-track-action="download pdf"]',
                'a[href*="/pdf/"]',
                '.c-pdf-download a',
            ]
        },
        'elsevier': {
            'domains': ['sciencedirect.com', 'elsevier.com'],
            'pdf_selectors': [
                'a.download-pdf-link',
                'a[pdfurl]',
                'a[href*=".pdf"]',
            ]
        },
        'springer': {
            'domains': ['springer.com', 'link.springer.com'],
            'pdf_selectors': [
                'a.c-pdf-download__link',
                'a[href*="/content/pdf/"]',
            ]
        },
        'wiley': {
            'domains': ['onlinelibrary.wiley.com'],
            'pdf_selectors': [
                'a.pdf-download',
                'a[href*=".pdf"]',
                'a[title*="PDF"]',
            ]
        },
        'arxiv': {
            'domains': ['arxiv.org'],
            'pdf_selectors': [
                'a[href*="/pdf/"]',
            ]
        },
        'plos': {
            'domains': ['plos.org', 'plosone.org'],
            'pdf_selectors': [
                'a[href*="manuscript?id="]',
                'a.download',
            ]
        },
    }
    
    # Patterns that suggest a paywall
    PAYWALL_INDICATORS = [
        'access denied',
        'subscription required',
        'purchase this article',
        'buy article',
        'institutional access',
        'log in to view',
        'sign in to access',
    ]
    
    def __init__(
        self,
        pdf_dir: Union[str, Path] = "./pdfs",
        cache_dir: Union[str, Path] = "./cache/web",
        metadata_tracking: bool = True,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        headless: bool = True,
        timeout: int = 30,
        user_agent: Optional[str] = None,
    ):
        """
        Initialize PDFDownloader.
        
        Args:
            pdf_dir: Directory to store downloaded PDFs
            cache_dir: Directory for web page caching
            metadata_tracking: Create .json files with download metadata
            max_retries: Maximum number of retry attempts
            backoff_factor: Backoff multiplier for retries
            headless: Run browser in headless mode
            timeout: Timeout for page loads (seconds)
            user_agent: Custom user agent string
        """
        if not SELENIUM_AVAILABLE:
            raise ImportError(
                "PDFDownloader requires Selenium. "
                "Install with: pip install selenium"
            )
        
        assert SeleniumWebFetcher is not None, "SeleniumWebFetcher is not imported"
        
        self.pdf_dir = Path(pdf_dir)
        self.cache_dir = Path(cache_dir)
        self.metadata_tracking = metadata_tracking
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.headless = headless
        self.timeout = timeout
        
        # Create directories
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize fetcher (will be created per-download)
        self.user_agent = user_agent
        self._fetcher = None
    
    def _get_fetcher(self) -> SeleniumWebFetcher:
        """Get or create a SeleniumWebFetcher instance."""
        try:
            if self._fetcher is None:
                assert SeleniumWebFetcher is not None, "SeleniumWebFetcher is not imported"
                self._fetcher = SeleniumWebFetcher(
                    cache_dir=str(self.cache_dir),
                    max_retries=self.max_retries,
                    backoff_factor=self.backoff_factor,
                    headless=self.headless,
                    timeout=self.timeout,
                    user_agent=self.user_agent,
                    use_selenium=True,  # PDFDownloader always needs Selenium
                )
                # Initialize driver immediately since we need it for driver.current_url, etc.
                if not self._fetcher._driver_initialized:
                    self._fetcher._init_driver()
        except Exception as e:
            logger.error(f"Error creating fetcher: {e}")
            raise
        finally:
            assert self._fetcher is not None, "Fetcher is None"
            assert self._fetcher.driver is not None, "Driver is None"
            return self._fetcher
    
    def close(self):
        """Close the browser and cleanup resources."""
        if self._fetcher is not None:
            self._fetcher.close_driver()
            self._fetcher = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    @staticmethod
    def sanitize_doi(doi: str) -> str:
        """
        Convert DOI to safe filename.
        
        Args:
            doi: DOI string (with or without https://doi.org/ prefix)
        
        Returns:
            Sanitized filename-safe string
        """
        # Remove common prefixes
        doi = doi.replace('https://doi.org/', '')
        doi = doi.replace('http://doi.org/', '')
        doi = doi.replace('doi:', '')
        doi = doi.strip()
        
        # Replace unsafe characters
        safe_doi = doi.replace('/', '_').replace('\\', '_')
        safe_doi = re.sub(r'[<>:"|?*]', '_', safe_doi)
        
        return safe_doi
    
    def _get_pdf_path(self, doi: str) -> Path:
        """Get the expected PDF file path for a DOI."""
        safe_doi = self.sanitize_doi(doi)
        return self.pdf_dir / f"{safe_doi}.pdf"
    
    def _get_metadata_path(self, doi: str) -> Path:
        """Get the metadata JSON file path for a DOI."""
        safe_doi = self.sanitize_doi(doi)
        return self.pdf_dir / f"{safe_doi}.json"
    
    def _resolve_doi(self, doi: str) -> str:
        """
        Resolve DOI to publisher landing page URL.
        
        Args:
            doi: DOI string
        
        Returns:
            Publisher landing page URL
        """
        # Clean DOI
        # doi = self.sanitize_doi(doi)
        
        # Use dx.doi.org for resolution
        return f"https://doi.org/{doi}"
    
    def _detect_paywall(self, page_text: str) -> bool:
        """
        Check if page content suggests a paywall.
        
        Args:
            page_text: Page text content
        
        Returns:
            True if paywall detected
        """
        page_text_lower = page_text.lower()
        return any(
            indicator in page_text_lower
            for indicator in self.PAYWALL_INDICATORS
        )
    
    def _detect_publisher(self, url: str) -> Optional[str]:
        """
        Detect publisher from URL.
        
        Args:
            url: Publisher landing page URL
        
        Returns:
            Publisher name or None
        """
        domain = urlparse(url).netloc.lower()
        
        for publisher, config in self.PUBLISHER_PATTERNS.items():
            if any(d in domain for d in config['domains']):
                return publisher
        
        return None
    
    def _find_pdf_link(
        self,
        driver,
        url: str,
        publisher: Optional[str] = None
    ) -> Optional[str]:
        """
        Find PDF download link on page.
        
        Args:
            driver: Selenium WebDriver instance
            url: Current page URL
            publisher: Detected publisher name
        
        Returns:
            PDF URL or None
        """
        pdf_url = None
        
        # Try publisher-specific selectors first
        if publisher and publisher in self.PUBLISHER_PATTERNS:
            config = self.PUBLISHER_PATTERNS[publisher]
            for selector in config['pdf_selectors']:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    href = element.get_attribute('href')
                    if href:
                        pdf_url = urljoin(url, href)
                        break
                except NoSuchElementException:
                    continue
        
        # Generic PDF link detection
        if not pdf_url:
            # Look for links with .pdf extension
            try:
                pdf_links = driver.find_elements(
                    By.CSS_SELECTOR,
                    'a[href*=".pdf"], a[href*="/pdf/"]'
                )
                
                for link in pdf_links:
                    href = link.get_attribute('href')
                    text = link.text.lower()
                    
                    # Prefer links with "download" or "pdf" in text
                    if href and ('download' in text or 'pdf' in text):
                        pdf_url = urljoin(url, href)
                        break
                
                # If no preferred link, take first .pdf link
                if not pdf_url and pdf_links:
                    href = pdf_links[0].get_attribute('href')
                    if href:
                        pdf_url = urljoin(url, href)
                        
            except NoSuchElementException:
                pass
        
        # Look for PDF buttons
        if not pdf_url:
            logger.info(f"No PDF link found, looking for buttons")
            logger.info(f"{driver is None}: Driver is None")
            try:
                buttons = driver.find_elements(
                    By.CSS_SELECTOR,
                    'button, a.button, a.btn'
                )
                
                for button in buttons:
                    text = button.text.lower()
                    if 'pdf' in text or 'download' in text:
                        # Try to click and get URL from navigation
                        try:
                            button.click()
                            time.sleep(2)  # Wait for navigation
                            new_url = driver.current_url
                            if new_url != url and '.pdf' in new_url:
                                pdf_url = new_url
                                break
                        except Exception:
                            continue
                            
            except NoSuchElementException:
                pass
        
        return pdf_url
    
    def _download_pdf(
        self,
        pdf_url: str,
        output_path: Path
    ) -> bool:
        """
        Download PDF from URL.
        
        Args:
            pdf_url: Direct PDF URL
            output_path: Where to save the PDF
        
        Returns:
            True if successful
        """
        fetcher = self._get_fetcher()
        
        try:
            # Fetch PDF content
            result = fetcher.fetch(
                pdf_url,
                force_refresh=True  # Don't cache PDFs
            )
            
            if result['status_code'] == 200:
                # Write to file
                content = result['content']
                
                # Handle both string and bytes content
                if isinstance(content, str):
                    # Might be base64 or text, try to detect
                    if content.startswith('%PDF'):
                        content = content.encode('latin-1')
                    else:
                        # Assume it's already PDF bytes as string
                        content = content.encode('latin-1')
                
                output_path.write_bytes(content)
                
                # Verify it's a PDF
                header = output_path.read_bytes()[:4]
                if header != b'%PDF':
                    output_path.unlink()  # Delete invalid file
                    return False
                
                return True
                
        except Exception as e:
            if output_path.exists():
                output_path.unlink()
            return False
        
        return False
    
    def _save_metadata(
        self,
        doi: str,
        status: str,
        url: Optional[str] = None,
        error: Optional[str] = None,
        pdf_path: Optional[Path] = None
    ):
        """
        Save download metadata to JSON file.
        
        Args:
            doi: Original DOI
            status: 'success', 'failure', or 'paywall'
            url: Landing page or PDF URL
            error: Error message if failed
            pdf_path: Path to downloaded PDF if successful
        """
        if not self.metadata_tracking:
            return
        
        metadata = {
            'doi': doi,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'error': error,
            'pdf_path': str(pdf_path) if pdf_path else None,
        }
        
        metadata_path = self._get_metadata_path(doi)
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def download_from_doi(
        self,
        doi: str,
        force_refresh: bool = False
    ) -> Dict:
        """
        Download PDF from DOI.
        
        Args:
            doi: DOI string (with or without prefix)
            force_refresh: Re-download even if file exists
        
        Returns:
            Dictionary with download result:
            {
                'success': bool,
                'doi': str,
                'pdf_path': Path or None,
                'url': str or None,
                'cached': bool,
                'error': str or None,
                'status': 'success'|'failure'|'paywall'
            }
        """
        pdf_path = self._get_pdf_path(doi)
        
        # Check if already downloaded
        if pdf_path.exists() and not force_refresh:
            return {
                'success': True,
                'doi': doi,
                'pdf_path': pdf_path,
                'url': None,
                'cached': True,
                'error': None,
                'status': 'success',
            }
        
        result = {
            'success': False,
            'doi': doi,
            'pdf_path': None,
            'url': None,
            'cached': False,
            'error': None,
            'status': 'failure',
        }
        
        try:
            # Resolve DOI
            doi_url = self._resolve_doi(doi)
            logging.info(f"Resolved DOI to: {doi_url}")
            fetcher = self._get_fetcher()
            
            # Navigate to landing page (use_selenium=True to ensure Selenium is used)
            page_result = fetcher.fetch(doi_url, use_selenium=True)
            
            if page_result['status_code'] != 200:
                raise PDFDownloadError(
                    f"Failed to load landing page: {page_result['status_code']}"
                )
            
            landing_url = fetcher.driver.current_url
            logger.info(f"Landing URL: {landing_url}")
            result['url'] = landing_url
            
            # Check for paywall
            page_text = fetcher.driver.page_source
            if self._detect_paywall(page_text):
                raise PaywallError("Content is behind paywall")
            
            # Detect publisher
            publisher = self._detect_publisher(landing_url)
            
            # Find PDF link
            pdf_url = self._find_pdf_link(
                fetcher.driver,
                landing_url,
                publisher
            )
            
            if not pdf_url:
                raise PDFNotFoundError("Could not find PDF link on page")
            
            result['url'] = pdf_url
            
            # Download PDF
            if self._download_pdf(pdf_url, pdf_path):
                result['success'] = True
                result['pdf_path'] = pdf_path
                result['status'] = 'success'
                
                # Save metadata
                self._save_metadata(
                    doi=doi,
                    status='success',
                    url=pdf_url,
                    pdf_path=pdf_path
                )
            else:
                raise PDFDownloadError("Failed to download or verify PDF")
                
        except PaywallError as e:
            result['error'] = str(e)
            result['status'] = 'paywall'
            self._save_metadata(
                doi=doi,
                status='paywall',
                url=result.get('url'),
                error=str(e)
            )
            
        except (PDFNotFoundError, PDFDownloadError, CloudflareRateLimitError) as e:
            result['error'] = str(e)
            result['status'] = 'failure'
            self._save_metadata(
                doi=doi,
                status='failure',
                url=result.get('url'),
                error=str(e)
            )
            
        except Exception as e:
            result['error'] = f"Unexpected error: {str(e)}"
            result['status'] = 'failure'
            self._save_metadata(
                doi=doi,
                status='failure',
                url=result.get('url'),
                error=str(e)
            )
        
        return result
    
    def download_batch(
        self,
        dois: List[str],
        delay: float = 2.0,
        force_refresh: bool = False,
        progress: bool = True,
    ) -> List[Dict]:
        """
        Download multiple PDFs from a list of DOIs.
        
        Args:
            dois: List of DOI strings
            delay: Delay between downloads (seconds)
            force_refresh: Re-download existing files
            progress: Show progress information
        
        Returns:
            List of result dictionaries
        """
        results = []
        
        for i, doi in enumerate(dois, 1):
            if progress:
                print(f"[{i}/{len(dois)}] Processing {doi}")
            
            result = self.download_from_doi(doi, force_refresh=force_refresh)
            results.append(result)
            
            if progress:
                status = result['status']
                if result['success']:
                    cached = " (cached)" if result['cached'] else ""
                    print(f"  ✓ Success{cached}: {result['pdf_path']}")
                elif status == 'paywall':
                    print(f"  ⚠ Paywall: {result['error']}")
                else:
                    print(f"  ✗ Failed: {result['error']}")
            
            # Delay between requests (except for last one)
            if i < len(dois):
                time.sleep(delay)
        
        return results
    
    def list_downloaded(self) -> List[Dict]:
        """
        List all successfully downloaded PDFs.
        
        Returns:
            List of metadata dictionaries for successful downloads
        """
        downloaded = []
        
        for json_file in self.pdf_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    metadata = json.load(f)
                    if metadata.get('status') == 'success':
                        downloaded.append(metadata)
            except Exception:
                continue
        
        return downloaded
    
    def get_statistics(self) -> Dict:
        """
        Get download statistics.
        
        Returns:
            Dictionary with download statistics
        """
        stats = {
            'total_files': 0,
            'success': 0,
            'failure': 0,
            'paywall': 0,
            'total_size_mb': 0.0,
        }
        
        # Count PDFs
        for pdf_file in self.pdf_dir.glob("*.pdf"):
            stats['total_files'] += 1
            stats['total_size_mb'] += pdf_file.stat().st_size / (1024 * 1024)
        
        # Count statuses
        for json_file in self.pdf_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    metadata = json.load(f)
                    status = metadata.get('status', 'unknown')
                    if status in stats:
                        stats[status] += 1
            except Exception:
                continue
        
        return stats
