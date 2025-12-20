"""
PDF Fetcher v2 - Implementation according to specification.

This module provides a clean, spec-compliant implementation for downloading
PDFs from DOIs, DOI-URLs, or resource URLs.
"""

import json
import re
import time
import hashlib
import tempfile
import shutil
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin, urlparse
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import contextmanager

# Optional tqdm support for progress bars
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    # Create a dummy tqdm class that does nothing
    class tqdm:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def update(self, n=1):
            pass
        def set_description(self, desc=None):
            pass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
try:
    from urllib3.exceptions import ReadTimeoutError as Urllib3ReadTimeoutError
except ImportError:
    Urllib3ReadTimeoutError = None

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.common.exceptions import (
        TimeoutException,
        NoSuchElementException,
        WebDriverException
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

import logging
logger = logging.getLogger(__name__)

from .version import __version__, __author__
from .config import PDFFetcherConfig, load_config
from .logging_config import setup_logging, create_download_summary_log

# Optional Crossref support
try:
    from api_clients.crossref_client import CrossrefBibliographicFetcher
    CROSSREF_AVAILABLE = True
except ImportError:
    CROSSREF_AVAILABLE = False
    logger.debug("Crossref client not available - will skip Crossref PDF URL lookup")


class DownloadStatus(Enum):
    """Download status enumeration."""
    SUCCESS = "success"
    FAILURE = "failure"
    PAYWALL = "paywall"
    ALREADY_EXISTS = "already_exists"
    PDF_NOT_FOUND = "pdf_not_found"
    NETWORK_ERROR = "network_error"
    INVALID_IDENTIFIER = "invalid_identifier"


@dataclass
class DownloadResult:
    """Result of a download attempt."""
    identifier: str
    sanitized_filename: Optional[str] = None
    landing_url: Optional[str] = None
    pdf_url: Optional[str] = None
    publisher: Optional[str] = None
    status: DownloadStatus = DownloadStatus.FAILURE
    error_reason: Optional[str] = None
    pdf_path: Optional[Path] = None
    first_attempted: Optional[str] = None
    last_attempted: Optional[str] = None
    last_successful: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['status'] = self.status.value
        if self.pdf_path:
            result['pdf_path'] = str(self.pdf_path)
        return result


class RateLimiter:
    """Per-domain rate limiter with jitter."""
    
    def __init__(self, requests_per_second: float = 1.0, jitter: Tuple[float, float] = (0.5, 1.5)):
        """
        Args:
            requests_per_second: Base rate limit
            jitter: Random delay range in seconds (min, max)
        """
        self.requests_per_second = requests_per_second
        self.jitter = jitter
        self.last_request_time: Dict[str, float] = {}
        self.min_delay = 1.0 / requests_per_second
    
    def wait_if_needed(self, domain: str):
        """Wait if needed to respect rate limit for domain."""
        now = time.time()
        if domain in self.last_request_time:
            elapsed = now - self.last_request_time[domain]
            if elapsed < self.min_delay:
                sleep_time = self.min_delay - elapsed
                # Add random jitter
                jitter = random.uniform(*self.jitter)
                sleep_time += jitter
                time.sleep(sleep_time)
        
        self.last_request_time[domain] = time.time()


class IdentifierNormalizer:
    """Normalize and classify input identifiers."""
    
    @staticmethod
    def clean_doi(doi: str) -> str:
        """Clean DOI by removing trailing/leading punctuation."""
        doi = doi.strip()
        # Remove trailing punctuation
        doi = re.sub(r'[.,;:!?)\]]+$', '', doi)
        # Remove leading punctuation
        doi = re.sub(r'^[.,;:!?(\[]+', '', doi)
        return doi.strip()
    
    @staticmethod
    def sanitize_for_filename(doi: str) -> str:
        """Sanitize DOI for use in filenames."""
        # Replace slashes and other problematic chars with underscores
        sanitized = doi.replace('/', '_').replace('\\', '_')
        sanitized = re.sub(r'[<>:"|?*]', '_', sanitized)
        return sanitized
    
    @staticmethod
    def normalize(identifier: str) -> Tuple[str, Optional[str], str]:
        """
        Normalize identifier and return (kind, doi, url).
        
        Returns:
            (kind, doi, url) where:
            - kind: 'doi', 'doi_url', or 'resource_url'
            - doi: cleaned DOI if applicable, None otherwise
            - url: URL to use for navigation
        """
        identifier = identifier.strip()
        
        if identifier.startswith('10.'):
            # It's a DOI
            cleaned_doi = IdentifierNormalizer.clean_doi(identifier)
            doi_url = f"https://doi.org/{cleaned_doi}"
            return ('doi', cleaned_doi, doi_url)
        elif identifier.startswith('http'):
            if 'doi.org/' in identifier:
                # It's a DOI-URL
                # Extract DOI from URL
                match = re.search(r'doi\.org/(10\.[^/\s?#]+)', identifier)
                if match:
                    doi = match.group(1)
                    cleaned_doi = IdentifierNormalizer.clean_doi(doi)
                    return ('doi_url', cleaned_doi, identifier)
                else:
                    return ('doi_url', None, identifier)
            else:
                # It's a resource URL
                return ('resource_url', None, identifier)
        else:
            raise ValueError(f"Unsupported identifier format: {identifier}")


class CrossrefPDFExtractor:
    """Extract PDF URLs from Crossref metadata."""
    
    @staticmethod
    def extract_pdf_url(metadata: Dict) -> Optional[str]:
        """
        Extract PDF URL from Crossref metadata.
        
        Args:
            metadata: Crossref metadata dict from fetch_by_doi()
        
        Returns:
            PDF URL if found, None otherwise
        """
        links = metadata.get('link', [])
        
        for link in links:
            url_val = link.get('URL', '')
            content_type = link.get('content-type', '')
            
            # Check if it's a PDF link
            is_pdf = (
                'pdf' in url_val.lower() or 
                'pdf' in content_type.lower() or
                content_type == 'application/pdf'
            )
            
            if is_pdf:
                logger.info(f"Found PDF URL in Crossref metadata: {url_val}")
                return url_val
        
        return None


class PublisherDetector:
    """Detect publisher from URL."""
    
    PUBLISHER_PATTERNS = {
        'elsevier': ['sciencedirect.com', 'elsevier.com'],
        'springer': ['springer.com', 'link.springer.com', 'springerlink.com'],
        'nature': ['nature.com', 'springernature.com'],
        'wiley': ['wiley.com', 'onlinelibrary.wiley.com'],
        'arxiv': ['arxiv.org'],
        'ieee': ['ieee.org', 'ieeexplore.ieee.org'],
        'plos': ['plos.org', 'journals.plos.org'],
        'acs': ['acs.org', 'pubs.acs.org'],
    }
    
    @staticmethod
    def detect(url: str) -> Optional[str]:
        """Detect publisher from URL."""
        domain = urlparse(url).netloc.lower()
        for publisher, domains in PublisherDetector.PUBLISHER_PATTERNS.items():
            if any(d in domain for d in domains):
                return publisher
        return None


class DOIResolver:
    """Resolve DOI to landing URL."""
    
    def __init__(self, session: requests.Session, rate_limiter: RateLimiter):
        self.session = session
        self.rate_limiter = rate_limiter
    
    def resolve(self, doi_url: str, use_selenium: bool = False, 
                selenium_driver=None) -> str:
        """
        Resolve DOI URL to landing URL.
        
        Args:
            doi_url: DOI URL (https://doi.org/...)
            use_selenium: Whether to use Selenium (for JS-heavy redirects)
            selenium_driver: Optional Selenium driver
        
        Returns:
            Final landing URL after redirects
        """
        domain = urlparse(doi_url).netloc
        self.rate_limiter.wait_if_needed(domain)
        
        if use_selenium and selenium_driver:
            try:
                selenium_driver.get(doi_url)
                time.sleep(2)  # Wait for redirects
                return selenium_driver.current_url
            except Exception as e:
                logger.warning(f"Selenium resolution failed: {e}, falling back to requests")
        
        # Try with requests first
        try:
            response = self.session.get(
                doi_url,
                allow_redirects=True,
                timeout=30
            )
            return response.url
        except Exception as e:
            logger.warning(f"Requests resolution failed: {e}")
            if use_selenium and selenium_driver:
                # Last resort: try Selenium
                try:
                    selenium_driver.get(doi_url)
                    time.sleep(3)
                    return selenium_driver.current_url
                except Exception as e2:
                    raise Exception(f"Both requests and Selenium failed: {e}, {e2}")
            raise


class PDFLinkFinder:
    """Find PDF links on a landing page."""
    
    def __init__(self, driver, rate_limiter: RateLimiter):
        self.driver = driver
        self.rate_limiter = rate_limiter
    
    def find_pdf_url(self, landing_url: str, publisher: Optional[str] = None) -> Optional[str]:
        """
        Find PDF URL using multiple strategies.
        
        Returns:
            PDF URL if found, None otherwise
        """
        # Strategy 1: Publisher-specific (e.g., ScienceDirect PII extraction, Springer direct URL)
        if publisher == 'elsevier':
            pdf_url = self._try_sciencedirect_direct(landing_url)
            if pdf_url:
                return pdf_url
        elif publisher == 'springer':
            pdf_url = self._try_springer_direct(landing_url)
            if pdf_url:
                return pdf_url
        
        # Strategy 2: Direct links
        pdf_url = self._find_direct_links(landing_url)
        if pdf_url:
            return pdf_url
        
        # Strategy 3: Button/link clicking
        pdf_url = self._find_via_buttons(landing_url)
        if pdf_url:
            return pdf_url
        
        # Strategy 4: Inline PDF check
        pdf_url = self._check_inline_pdf(landing_url)
        if pdf_url:
            return pdf_url
        
        # Strategy 5: Page source scanning
        pdf_url = self._scan_page_source(landing_url)
        if pdf_url:
            return pdf_url
        
        return None
    
    def _try_sciencedirect_direct(self, url: str) -> Optional[str]:
        """Try ScienceDirect direct PDF URL construction."""
        match = re.search(r'/science/article/pii/([A-Z0-9]+)', url, re.IGNORECASE)
        if match:
            pii = match.group(1)
            pdf_url = f"https://www.sciencedirect.com/science/article/pii/{pii}/pdfft?isDTMRedir=true&download=true"
            logger.info(f"Constructed ScienceDirect PDF URL: {pdf_url}")
            return pdf_url
        return None
    
    def _find_direct_links(self, url: str) -> Optional[str]:
        """Find direct PDF links."""
        try:
            # CSS selectors for PDF links
            selectors = [
                'a[href*=".pdf"]',
                'a[data-pdf-url]',
                'a[pdfurl]',
                'a[href*="/pdf/"]',
                'a[href*="/pdfft"]',
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        pdf_url = element.get_attribute('href') or element.get_attribute('data-pdf-url') or element.get_attribute('pdfurl')
                        if pdf_url:
                            pdf_url = urljoin(url, pdf_url)
                            if self._is_valid_pdf_url(pdf_url):
                                logger.info(f"Found direct PDF link: {pdf_url}")
                                return pdf_url
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
        except Exception as e:
            logger.debug(f"Direct link search failed: {e}")
        
        return None
    
    def _find_via_buttons(self, url: str) -> Optional[str]:
        """Find PDF via button/link clicking."""
        try:
            # Find all clickable elements
            elements = self.driver.find_elements(By.XPATH, "//button | //a | //*[@role='button']")
            
            button_texts = ['download pdf', 'view pdf', 'pdf', 'download', 'get pdf', 'article']
            
            for element in elements:
                try:
                    # Get text from various sources
                    element_text = ""
                    try:
                        element_text = element.text.strip().lower()
                    except:
                        pass
                    
                    if not element_text:
                        element_text = (element.get_attribute('aria-label') or "").strip().lower()
                    if not element_text:
                        element_text = (element.get_attribute('title') or "").strip().lower()
                    
                    # Check if text matches PDF patterns
                    for button_text in button_texts:
                        if button_text in element_text:
                            logger.info(f"Found PDF button with text: {element_text[:50]}")
                            
                            # Try data attributes first
                            pdf_url = (element.get_attribute('data-pdf-url') or 
                                      element.get_attribute('data-href') or
                                      element.get_attribute('data-url'))
                            if pdf_url:
                                pdf_url = urljoin(url, pdf_url)
                                if self._is_valid_pdf_url(pdf_url):
                                    return pdf_url
                            
                            # If it's a link, get href
                            if element.tag_name.lower() == 'a':
                                href = element.get_attribute('href')
                                if href:
                                    pdf_url = urljoin(url, href)
                                    if self._is_valid_pdf_url(pdf_url):
                                        return pdf_url
                            
                            # Try clicking
                            return self._click_and_detect_pdf(element, url)
                            
                except Exception as e:
                    logger.debug(f"Error processing element: {e}")
                    continue
        except Exception as e:
            logger.debug(f"Button search failed: {e}")
        
        return None
    
    def _click_and_detect_pdf(self, element, current_url: str) -> Optional[str]:
        """Click element and detect if PDF was opened."""
        try:
            # Scroll into view
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)
            
            # Get current window handles
            current_windows = self.driver.window_handles
            main_window = self.driver.current_window_handle
            
            # Try to click
            clicked = False
            try:
                wait = WebDriverWait(self.driver, 3)
                wait.until(EC.element_to_be_clickable(element))
                element.click()
                clicked = True
            except:
                # Fallback to JavaScript click
                try:
                    self.driver.execute_script("arguments[0].click();", element)
                    clicked = True
                except:
                    pass
            
            if not clicked:
                return None
            
            time.sleep(2)  # Wait for navigation
            
            # Check for new window
            new_windows = self.driver.window_handles
            if len(new_windows) > len(current_windows):
                for window in new_windows:
                    if window not in current_windows:
                        self.driver.switch_to.window(window)
                        new_url = self.driver.current_url
                        if self._is_valid_pdf_url(new_url) or self._is_pdf_page():
                            self.driver.close()
                            self.driver.switch_to.window(main_window)
                            return new_url
                        self.driver.close()
                        self.driver.switch_to.window(main_window)
            
            # Check if URL changed
            new_url = self.driver.current_url
            if new_url != current_url:
                if self._is_valid_pdf_url(new_url) or self._is_pdf_page():
                    return new_url
            
            # Check if current page is PDF
            if self._is_pdf_page():
                return new_url
            
        except Exception as e:
            logger.debug(f"Click detection failed: {e}")
        
        return None
    
    def _check_inline_pdf(self, url: str) -> Optional[str]:
        """Check if current page is an inline PDF."""
        try:
            if self._is_pdf_page():
                return self.driver.current_url
        except:
            pass
        return None
    
    def _scan_page_source(self, url: str) -> Optional[str]:
        """Scan page source for PDF URLs."""
        try:
            page_source = self.driver.page_source
            
            # Pattern 1: Direct PDF URLs
            pdf_pattern = r'https?://[^\s"\'<>]+\.pdf[^\s"\'<>]*'
            matches = re.findall(pdf_pattern, page_source, re.IGNORECASE)
            for match in matches:
                if self._is_valid_pdf_url(match):
                    return match
            
            # Pattern 2: ScienceDirect PII patterns
            pii_pattern = r'/science/article/pii/([A-Z0-9]+)'
            match = re.search(pii_pattern, page_source, re.IGNORECASE)
            if match:
                pii = match.group(1)
                pdf_url = f"https://www.sciencedirect.com/science/article/pii/{pii}/pdfft?isDTMRedir=true&download=true"
                return pdf_url
        except Exception as e:
            logger.debug(f"Page source scan failed: {e}")
        
        return None
    
    def _is_pdf_page(self) -> bool:
        """Check if current page is a PDF."""
        try:
            # Check content type via JavaScript
            content_type = self.driver.execute_script(
                "return document.contentType || ''"
            )
            if 'application/pdf' in content_type.lower():
                return True
            
            # Check if page source starts with PDF header
            page_source = self.driver.page_source[:100]
            if page_source.startswith('%PDF'):
                return True
        except:
            pass
        return False
    
    def _is_valid_pdf_url(self, url: str) -> bool:
        """Validate that URL looks like a PDF URL."""
        url_lower = url.lower()
        
        # Reject obvious non-PDF URLs
        if url_lower.endswith('/') and url_lower.count('/') <= 4:
            return False  # Homepage
        
        # Accept if it looks like PDF
        return (
            url_lower.endswith('.pdf') or
            '/pdf' in url_lower or
            '/pdfft' in url_lower or
            ('.pdf?' in url_lower) or
            ('sciencedirect.com' in url_lower and '/pii/' in url_lower and '/pdfft' in url_lower)
        )


class DownloadManager:
    """Handle actual PDF download."""
    
    def __init__(self, session: requests.Session, rate_limiter: RateLimiter, selenium_download_dir: Optional[Path] = None):
        self.session = session
        self.rate_limiter = rate_limiter
        self.selenium_download_dir = selenium_download_dir
    
    def download(self, pdf_url: str, output_path: Path, 
                 cookies: Optional[List[Dict]] = None,
                 referer: Optional[str] = None,
                 selenium_driver=None) -> bool:
        """
        Download PDF from URL.
        
        Args:
            pdf_url: URL to download from
            output_path: Where to save the PDF
            cookies: Optional cookies from Selenium
            referer: Referer header (landing page URL)
            selenium_driver: Optional Selenium driver for fallback
        
        Returns:
            True if successful
        """
        domain = urlparse(pdf_url).netloc
        self.rate_limiter.wait_if_needed(domain)
        
        # Transfer cookies if provided
        if cookies:
            for cookie in cookies:
                try:
                    self.session.cookies.set(
                        cookie['name'],
                        cookie['value'],
                        domain=cookie.get('domain', ''),
                        path=cookie.get('path', '/')
                    )
                except:
                    pass
        
        # Prepare headers
        headers = {}
        if referer:
            headers['Referer'] = referer
        
        try:
            # Download with streaming
            response = self.session.get(
                pdf_url,
                stream=True,
                timeout=60,
                allow_redirects=True,
                headers=headers
            )
            
            # Early detection: Check Content-Type header before downloading full file
            content_type = response.headers.get('content-type', '').lower()
            is_html_content_type = (
                'text/html' in content_type or 
                'application/xhtml' in content_type or
                'text/xml' in content_type
            )
            
            # Handle error status codes that might still contain PDF
            if response.status_code >= 400:
                logger.warning(f"Got HTTP {response.status_code}, checking if response is PDF...")
                # Save to temp file to check
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            tmp_file.write(chunk)
                    tmp_path = Path(tmp_file.name)
                
                # Check if it's a PDF
                if tmp_path.stat().st_size >= 4:
                    header = tmp_path.read_bytes()[:4]
                    if header == b'%PDF':
                        logger.info(f"Got {response.status_code} but response is PDF, saving...")
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        tmp_path.rename(output_path)
                        return True
                
                # Not a PDF, try Selenium fallback if available
                tmp_path.unlink()
                
                if selenium_driver and response.status_code in (403, 401):
                    # Explicit logging for ams.org 403 errors
                    if 'ams.org' in pdf_url.lower():
                        logger.warning("🔴 AMS.ORG - Got 403 in DownloadManager, trying Selenium fallback...")
                        logger.warning(f"   PDF URL: {pdf_url}")
                    logger.info(f"Trying Selenium fallback for {response.status_code} response...")
                    selenium_result = self._download_with_selenium(pdf_url, output_path, selenium_driver, referer)
                    # If Selenium also fails, raise an error with 403 info so it can be marked for postponement
                    if not selenium_result and response.status_code == 403:
                        if 'ams.org' in pdf_url.lower():
                            logger.warning("🔴 AMS.ORG - Selenium fallback also failed with 403, raising error...")
                        raise requests.HTTPError(f"403 Client Error: Forbidden for url: {pdf_url}", response=response)
                    return selenium_result
                
                # If no Selenium or not 403/401, raise error (this includes 403 when no Selenium fallback)
                response.raise_for_status()
            
            # Early HTML detection: If Content-Type indicates HTML, try to peek at content before full download
            if is_html_content_type:
                logger.warning(f"URL returned HTML content-type '{content_type}' instead of PDF - likely wrong URL")
                # Read just enough to confirm it's HTML (first chunk)
                first_chunk = next(response.iter_content(chunk_size=512), b'')
                if first_chunk.startswith(b'<!') or b'<!DOCTYPE' in first_chunk or b'<html' in first_chunk.lower():
                    logger.error(f"Confirmed HTML response from {pdf_url[:100]}... (Content-Type: {content_type})")
                    # Try Selenium fallback if available (might be a redirect or dynamic page)
                    if selenium_driver:
                        logger.info("Trying Selenium fallback for HTML response...")
                        return self._download_with_selenium(pdf_url, output_path, selenium_driver, referer)
                    return False
                # If first chunk doesn't look like HTML, continue (might be mislabeled)
            
            # Normal download
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check response status and content-type before downloading
            if response.status_code >= 400:
                logger.warning(f"HTTP {response.status_code} response from {pdf_url}")
                # Still try to download - might be PDF even with error status
            
            if 'application/pdf' not in content_type and content_type and not is_html_content_type:
                logger.debug(f"Content-Type is '{content_type}' (not application/pdf) - will verify header")
            
            # Write to temp file first
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp_file.write(chunk)
            
            # Verify PDF header
            header = tmp_path.read_bytes()[:4]
            if header != b'%PDF':
                # Read more of the file to see what we actually got
                file_size = tmp_path.stat().st_size
                preview = tmp_path.read_bytes()[:200]  # First 200 bytes
                
                # Try to decode as text to see if it's JSON/HTML/error message
                try:
                    preview_text = preview.decode('utf-8', errors='ignore')
                    
                    # Determine if this is expected (HTML) vs unexpected (other errors)
                    is_html = preview_text.strip().startswith('<!') or '<html' in preview_text.lower() or '<!DOCTYPE' in preview_text
                    
                    # Use WARNING for expected HTML responses, ERROR for unexpected issues
                    log_level = logger.warning if is_html else logger.error
                    log_level(f"Downloaded file is not a valid PDF (header: {header}, size: {file_size} bytes)")
                    
                    if is_html:
                        # HTML responses are common (wrong URL, redirect page, etc.) - less verbose
                        logger.debug(f"HTML response preview: {preview_text[:150]}...")
                    else:
                        # Unexpected content - more verbose
                        logger.error(f"Response preview: {preview_text[:150]}...")
                    
                    # Check if it's JSON (common for API error responses)
                    if preview_text.strip().startswith('{'):
                        try:
                            import json
                            error_data = json.loads(tmp_path.read_text()[:1000])
                            logger.warning(f"JSON error response: {error_data}")
                        except:
                            pass
                except:
                    logger.warning(f"Downloaded file is not a valid PDF (header: {header}, size: {file_size} bytes, binary content)")
                
                tmp_path.unlink()
                return False
            
            # Move to final location
            tmp_path.rename(output_path)
            logger.info(f"Downloaded {output_path.stat().st_size} bytes to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            # Try Selenium fallback if available
            if selenium_driver:
                logger.info("Trying Selenium fallback after requests failure...")
                return self._download_with_selenium(pdf_url, output_path, selenium_driver, referer)
            
            if output_path.exists():
                output_path.unlink()
            return False
    
    def _wait_for_download(self, download_dir: Optional[Path], timeout: int = 30, expected_filename: Optional[str] = None) -> Optional[Path]:
        """
        Wait for a file to appear in the download directory.
        
        Args:
            download_dir: Directory to monitor
            timeout: Maximum time to wait in seconds
            expected_filename: Optional expected filename (without extension)
        
        Returns:
            Path to downloaded file, or None if timeout
        """
        if not download_dir:
            return None
        
        start_time = time.time()
        initial_files = set(download_dir.glob('*'))
        initial_file_sizes = {f: f.stat().st_size for f in initial_files if f.is_file()}
        logger.debug(f"Monitoring download directory: {download_dir}")
        logger.debug(f"Initial files: {[f.name for f in initial_files]}")
        
        # Also check for .crdownload files (Chrome's temporary download files)
        last_check_time = start_time
        
        while time.time() - start_time < timeout:
            current_files = set(download_dir.glob('*'))
            
            # Check for .crdownload files (download in progress)
            crdownload_files = [f for f in current_files if f.is_file() and f.name.endswith('.crdownload')]
            if crdownload_files:
                logger.debug(f"Download in progress: {[f.name for f in crdownload_files]}")
                time.sleep(1)
                continue
            
            new_files = current_files - initial_files
            
            # Also check for files that changed size (might be the same file being written)
            for existing_file in initial_files:
                if existing_file.is_file() and existing_file in current_files:
                    try:
                        current_size = existing_file.stat().st_size
                        initial_size = initial_file_sizes.get(existing_file, 0)
                        if current_size > initial_size:
                            logger.debug(f"File {existing_file.name} is growing: {initial_size} -> {current_size}")
                            # Wait a bit more to see if it finishes
                            time.sleep(2)
                            # Check if it's now complete (no .crdownload)
                            if not existing_file.name.endswith('.crdownload'):
                                if existing_file.suffix.lower() == '.pdf':
                                    # Verify it's a PDF
                                    try:
                                        header = existing_file.read_bytes()[:4]
                                        if header == b'%PDF':
                                            logger.info(f"Found completed PDF: {existing_file.name}")
                                            return existing_file
                                    except:
                                        pass
                    except:
                        pass
            
            # Filter for PDF files
            pdf_files = [f for f in new_files if f.is_file() and f.suffix.lower() == '.pdf']
            
            # Also check for files without extension that might be PDFs
            for f in new_files:
                if f.is_file() and not f.suffix:
                    try:
                        header = f.read_bytes()[:4]
                        if header == b'%PDF':
                            logger.info(f"Found PDF without extension: {f.name}")
                            pdf_files.append(f)
                    except:
                        pass
            
            # If we have an expected filename, prefer files matching it
            if expected_filename:
                matching = [f for f in pdf_files if expected_filename.lower() in f.name.lower()]
                if matching:
                    # Wait a bit more to ensure download is complete
                    time.sleep(1)
                    # Verify it's complete
                    try:
                        header = matching[0].read_bytes()[:4]
                        if header == b'%PDF':
                            return matching[0]
                    except:
                        pass
            
            if pdf_files:
                # Wait a bit more to ensure download is complete
                time.sleep(1)
                # Verify and return the most recently modified PDF
                for pdf_file in sorted(pdf_files, key=lambda f: f.stat().st_mtime, reverse=True):
                    try:
                        header = pdf_file.read_bytes()[:4]
                        if header == b'%PDF':
                            logger.info(f"Found completed PDF: {pdf_file.name}")
                            return pdf_file
                    except:
                        continue
            
            # Log progress every 5 seconds
            if time.time() - last_check_time >= 5:
                logger.debug(f"Still waiting for download... ({int(time.time() - start_time)}s elapsed)")
                last_check_time = time.time()
            
            time.sleep(0.5)
        
        final_files = list(download_dir.glob('*'))
        logger.warning(f"Download timeout after {timeout}s.")
        logger.warning(f"Final files in directory ({len(final_files)}): {[f.name for f in final_files]}")
        
        # Log details about each file
        for f in final_files:
            try:
                size = f.stat().st_size
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                logger.warning(f"  - {f.name}: {size} bytes, modified {mtime}")
                # Check if it's HTML (Cloudflare page)
                if f.suffix == '.html' or f.name.endswith('.html'):
                    try:
                        content_preview = f.read_text()[:200]
                        logger.warning(f"    Content preview: {content_preview}")
                    except:
                        pass
            except Exception as e:
                logger.warning(f"  - {f.name}: (error reading: {e})")
        
        return None
    
    def _download_with_selenium(self, pdf_url: str, output_path: Path, 
                                driver, referer: Optional[str] = None) -> bool:
        """Download PDF using Selenium browser download (for watermarking services, etc.)."""
        try:
            logger.info(f"Downloading via Selenium browser download: {pdf_url}")
            
            # Get list of files before download
            initial_files = set(self.selenium_download_dir.glob('*'))
            logger.debug(f"Initial files in download dir: {len(initial_files)}")
            
            # Enable Chrome downloads using DevTools Protocol
            # Must use absolute path
            download_path = str(self.selenium_download_dir.resolve())
            try:
                driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                    'behavior': 'allow',
                    'downloadPath': download_path
                })
                logger.debug(f"Enabled Chrome downloads via DevTools Protocol to: {download_path}")
            except Exception as e:
                logger.debug(f"Could not enable downloads via CDP: {e}")
            
            # Navigate to PDF URL - browser will download it automatically
            driver.get(pdf_url)
            time.sleep(3)  # Wait for page to start loading
            
            current_url = driver.current_url
            logger.info(f"Current URL after navigation: {current_url}")
            
            # Check for Cloudflare challenge
            page_source = driver.page_source
            page_title = driver.title
            logger.debug(f"Page title: {page_title}")
            logger.debug(f"Page source length: {len(page_source)}")
            logger.debug(f"Page source preview (first 500 chars): {page_source[:500]}")
            
            # Check for Cloudflare "Just a moment" page
            is_cloudflare = (
                'just a moment' in page_title.lower() or
                'just a moment' in page_source.lower()[:2000] or
                'cloudflare' in page_source.lower()[:2000] or
                'checking your browser' in page_source.lower()[:2000]
            )
            
            if is_cloudflare:
                logger.warning("=" * 60)
                logger.warning("CLOUDFLARE CHALLENGE DETECTED")
                logger.warning(f"Page title: {page_title}")
                logger.warning("This is blocking the PDF download.")
                logger.warning("=" * 60)
                
                # Wait a bit to see if it resolves
                logger.info("Waiting for Cloudflare challenge to resolve (max 30s)...")
                start_wait = time.time()
                while time.time() - start_wait < 30:
                    time.sleep(2)
                    current_page = driver.page_source.lower()
                    current_title = driver.title.lower()
                    if 'just a moment' not in current_title and 'just a moment' not in current_page[:2000]:
                        logger.info("Cloudflare challenge appears to have resolved")
                        break
                    logger.debug(f"Still on Cloudflare page... ({int(time.time() - start_wait)}s)")
                
                # Re-check after waiting
                page_source = driver.page_source
                page_title = driver.title
                current_url = driver.current_url
                logger.info(f"After Cloudflare wait - URL: {current_url}, Title: {page_title[:100]}")
            
            # Log what files are currently in download directory
            current_files = list(self.selenium_download_dir.glob('*'))
            logger.debug(f"Files in download directory after navigation: {[f.name for f in current_files]}")
            
            # Check if we're redirected to a watermark page
            is_watermark = 'silverchair.com' in current_url or 'watermark' in current_url.lower()
            
            # Try to force download using JavaScript if it's a direct PDF URL
            if not is_watermark and (current_url.endswith('.pdf') or '/pdf' in current_url.lower()):
                logger.info("Attempting to force PDF download via JavaScript...")
                try:
                    # Use JavaScript to fetch and download the PDF
                    driver.execute_script("""
                        fetch(window.location.href)
                            .then(response => response.blob())
                            .then(blob => {
                                const url = window.URL.createObjectURL(blob);
                                const link = document.createElement('a');
                                link.href = url;
                                link.download = document.title || 'document.pdf';
                                document.body.appendChild(link);
                                link.click();
                                document.body.removeChild(link);
                                window.URL.revokeObjectURL(url);
                            })
                            .catch(err => console.error('Download failed:', err));
                    """)
                    time.sleep(2)
                    logger.info("JavaScript download trigger executed")
                except Exception as e:
                    logger.debug(f"JavaScript download trigger failed: {e}")
            
            # If we're on a watermark page, look for download links/buttons
            if is_watermark:
                logger.info("Detected watermarking service, looking for download trigger...")
                time.sleep(3)  # Wait for page to fully load
                
                # Look for download buttons/links
                download_selectors = [
                    "//a[contains(@href, '.pdf')]",
                    "//a[contains(text(), 'Download')]",
                    "//button[contains(text(), 'Download')]",
                    "//a[@download]",
                    "//*[contains(@class, 'download')]//a",
                    "//a[contains(@title, 'Download')]",
                    "//a[contains(@aria-label, 'Download')]",
                    "//a[contains(@class, 'pdf')]",
                ]
                
                clicked = False
                for selector in download_selectors:
                    try:
                        elements = driver.find_elements(By.XPATH, selector)
                        for element in elements:
                            href = element.get_attribute('href')
                            text = (element.text or "").lower()
                            
                            if href and ('.pdf' in href.lower() or 'download' in text):
                                logger.info(f"Found download link, clicking: {href or text[:50]}")
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                                time.sleep(0.5)
                                try:
                                    element.click()
                                except:
                                    driver.execute_script("arguments[0].click();", element)
                                clicked = True
                                time.sleep(2)  # Wait for download to start
                                break
                        if clicked:
                            break
                    except Exception as e:
                        logger.debug(f"Selector {selector} failed: {e}")
                        continue
            
            # Wait for download to complete
            if not self.selenium_download_dir:
                logger.error("Selenium download directory not configured")
                return False
            
            # Log current state before waiting
            logger.info(f"Waiting for browser download to complete...")
            logger.info(f"Download directory: {self.selenium_download_dir}")
            logger.info(f"Current page URL: {driver.current_url}")
            logger.info(f"Current page title: {driver.title}")
            
            # Check what's in the download directory now
            files_before_wait = list(self.selenium_download_dir.glob('*'))
            logger.debug(f"Files in download directory before wait: {[f.name for f in files_before_wait]}")
            
            downloaded_file = self._wait_for_download(self.selenium_download_dir, timeout=30)
            
            if downloaded_file:
                logger.info(f"Downloaded file found: {downloaded_file}")
                
                # Verify it's a PDF
                try:
                    header = downloaded_file.read_bytes()[:4]
                    if header != b'%PDF':
                        logger.error(f"Downloaded file is not a PDF (header: {header})")
                        downloaded_file.unlink()
                        return False
                except Exception as e:
                    logger.error(f"Error verifying PDF: {e}")
                    return False
                
                # Move to final location
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(downloaded_file), str(output_path))
                logger.info(f"Downloaded PDF moved to: {output_path} ({output_path.stat().st_size} bytes)")
                return True
            else:
                logger.warning("No PDF file appeared in download directory")
                # Fallback: Try to download using requests with cookies from Selenium
                logger.info("Falling back to requests download with Selenium cookies...")
                return self._save_pdf_from_selenium(driver, output_path)
            
        except Exception as e:
            logger.error(f"Selenium download failed: {e}", exc_info=True)
            return False
    
    def _is_pdf_page(self, driver) -> bool:
        """Check if current Selenium page is a PDF."""
        try:
            # Check content type
            content_type = driver.execute_script("return document.contentType || ''")
            if 'application/pdf' in content_type.lower():
                logger.debug("PDF detected via content type")
                return True
            
            # Check page source (first 100 bytes)
            try:
                page_source = driver.page_source[:100]
                if page_source.startswith('%PDF'):
                    logger.debug("PDF detected via page source header")
                    return True
            except:
                pass
            
            # Check if URL suggests PDF
            current_url = driver.current_url.lower()
            if current_url.endswith('.pdf') or '/pdf' in current_url or '/pdfft' in current_url:
                logger.debug("URL suggests PDF")
                # Try to verify by checking response
                try:
                    # Use JavaScript to fetch and check
                    is_pdf = driver.execute_script("""
                        return fetch(window.location.href, {method: 'HEAD'})
                            .then(r => r.headers.get('content-type'))
                            .then(ct => ct && ct.includes('application/pdf'))
                            .catch(() => false);
                    """)
                    if is_pdf:
                        return True
                except:
                    pass
        except Exception as e:
            logger.debug(f"Error checking if PDF page: {e}")
        return False
    
    def _save_pdf_from_selenium(self, driver, output_path: Path) -> bool:
        """Save PDF from current Selenium page."""
        try:
            current_url = driver.current_url
            logger.info(f"Attempting to save PDF from: {current_url}")
            cookies = driver.get_cookies()
            
            # Try to extract actual PDF URL from page if we're on a watermark page
            if 'silverchair.com' in current_url or 'watermark' in current_url.lower():
                logger.info("On watermark page, trying to extract PDF URL...")
                # Look for PDF URL in various places
                try:
                    # Check for PDF in iframe src
                    iframes = driver.find_elements(By.TAG_NAME, 'iframe')
                    for iframe in iframes:
                        src = iframe.get_attribute('src')
                        if src and ('.pdf' in src.lower() or 'silverchair' in src.lower()):
                            logger.info(f"Found PDF URL in iframe: {src}")
                            current_url = src
                            break
                    
                    # Check page source for PDF URLs
                    page_source = driver.page_source
                    pdf_urls = re.findall(r'https?://[^\s"\'<>]+\.pdf[^\s"\'<>]*', page_source, re.IGNORECASE)
                    for pdf_url in pdf_urls:
                        if 'silverchair' in pdf_url or 'watermark' in pdf_url:
                            logger.info(f"Found PDF URL in page source: {pdf_url}")
                            current_url = pdf_url
                            break
                except Exception as e:
                    logger.debug(f"Error extracting PDF URL: {e}")
            
            # Build requests session with cookies from Selenium
            session = requests.Session()
            try:
                user_agent = driver.execute_script("return navigator.userAgent;")
                session.headers.update({'User-Agent': user_agent})
            except:
                pass
            
            for cookie in cookies:
                try:
                    session.cookies.set(
                        cookie['name'],
                        cookie['value'],
                        domain=cookie.get('domain', ''),
                        path=cookie.get('path', '/')
                    )
                except:
                    pass
            
            # Add referer
            try:
                referer = driver.execute_script("return document.referrer;")
                if referer:
                    session.headers.update({'Referer': referer})
            except:
                pass
            
            # Try to download via requests with Selenium cookies
            logger.info(f"Downloading PDF via requests with Selenium cookies: {current_url}")
            response = session.get(current_url, stream=True, timeout=60, allow_redirects=True)
            
            if response.status_code >= 400:
                logger.warning(f"Got {response.status_code}, checking if response is PDF...")
                # Save to temp to check
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            tmp_file.write(chunk)
                    tmp_path = Path(tmp_file.name)
                
                if tmp_path.stat().st_size >= 4:
                    header = tmp_path.read_bytes()[:4]
                    if header == b'%PDF':
                        logger.info(f"Got {response.status_code} but response is PDF")
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        tmp_path.rename(output_path)
                        return True
                tmp_path.unlink()
                response.raise_for_status()
            
            # Normal download
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Verify
            # Verify it's actually a PDF
            header = output_path.read_bytes()[:4]
            if header == b'%PDF':
                logger.info(f"Downloaded PDF via Selenium+requests: {output_path.stat().st_size} bytes")
                return True
            else:
                logger.error(f"Downloaded file is not a valid PDF (header: {header})")
                output_path.unlink()
                return False
            
        except Exception as e:
            error_msg = str(e)
            # Explicit logging for ams.org errors in Selenium download
            # Check error message and current_url (which was set earlier in the method)
            try:
                current_url = driver.current_url if 'driver' in locals() else None
                is_ams_error = 'ams.org' in error_msg.lower() or (current_url and 'ams.org' in current_url.lower())
                if is_ams_error:
                    logger.warning("🔴 AMS.ORG - Failed to save PDF from Selenium")
                    if current_url:
                        logger.warning(f"   Current URL: {current_url}")
                    logger.warning(f"   Error: {error_msg[:300]}")
            except:
                # If we can't get current_url, just check error message
                if 'ams.org' in error_msg.lower():
                    logger.warning("🔴 AMS.ORG - Failed to save PDF from Selenium")
                    logger.warning(f"   Error: {error_msg[:300]}")
            logger.error(f"Failed to save PDF from Selenium: {e}")
            if output_path.exists():
                output_path.unlink()
            return False


class MetadataStore:
    """Manage metadata JSON file."""
    
    def __init__(self, metadata_path: Path):
        self.metadata_path = metadata_path
        self._metadata: Dict[str, Dict] = {}
        self._load()
    
    def _load(self):
        """Load metadata from file."""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, 'r') as f:
                    self._metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load metadata: {e}")
                self._metadata = {}
    
    def _save(self):
        """Save metadata to file."""
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_path, 'w') as f:
            json.dump(self._metadata, f, indent=2)
    
    def get(self, identifier: str) -> Optional[Dict]:
        """Get metadata for identifier."""
        return self._metadata.get(identifier)
    
    def update(self, result: DownloadResult):
        """Update metadata with download result."""
        identifier = result.identifier
        now = datetime.utcnow().isoformat()
        
        if identifier not in self._metadata:
            self._metadata[identifier] = {
                'first_attempted': now,
            }
        
        # Add Cloudflare detection flag for easy identification
        cloudflare_detected = (
            result.error_reason is not None and 
            'cloudflare' in result.error_reason.lower()
        )
        
        self._metadata[identifier].update({
            'last_attempted': now,
            'status': result.status.value,
            'publisher': result.publisher,
            'landing_url': result.landing_url,
            'pdf_url': result.pdf_url,
            'sanitized_filename': result.sanitized_filename,
            'error_reason': result.error_reason,
            'cloudflare_detected': cloudflare_detected,  # Easy to identify Cloudflare aborts
        })
        
        if result.status == DownloadStatus.SUCCESS:
            self._metadata[identifier]['last_successful'] = now
            if result.pdf_path:
                self._metadata[identifier]['pdf_path'] = str(result.pdf_path)
        
        self._save()


# Module-level flag to track if we've already logged initialization messages
# (prevents duplicate logs when multiple PDFFetcher instances are created in parallel)
_initialization_logged = False


class PDFFetcher:
    """
    Main PDF fetcher class following the specification.
    """
    
    def __init__(
        self,
        config: Optional[PDFFetcherConfig] = None,
        config_file: Optional[Union[str, Path]] = None,
        **kwargs
    ):
        """
        Initialize PDF fetcher.
        
        Args:
            config: PDFFetcherConfig object (highest priority)
            config_file: Path to YAML config file  
            **kwargs: Override parameters (e.g., pdf_dir="./pdfs")
        
        Priority: config object > config_file > kwargs > defaults
        
        Examples:
            # Use config file
            fetcher = PDFFetcher(config_file="fetcher_config.yaml")
            
            # Use config file with overrides
            fetcher = PDFFetcher(config_file="config.yaml", headless=False)
            
            # Use parameters (old way - still works!)
            fetcher = PDFFetcher(pdf_dir="./pdfs", headless=True)
            
            # Use config object
            config = PDFFetcherConfig(pdf_dir="./pdfs", log_dir="./logs")
            fetcher = PDFFetcher(config=config)
        """
        # Load configuration with priority: config > config_file > kwargs
        if config is None:
            config = load_config(config_file=config_file, **kwargs)
        
        self.config = config
        
        # Setup logging
        self.logger = setup_logging(
            log_file=config.log_file_path,
            console_level=logging.INFO,
            file_level=logging.DEBUG
        )
        # Only log initialization messages once (avoid duplicates in parallel processing)
        global _initialization_logged
        if not _initialization_logged:
            self.logger.info(f"PDF Fetcher v{__version__} initialized")
            self.logger.info(f"PDF directory: {config.pdf_dir}")
            self.logger.info(f"Log directory: {config.log_dir}")
            _initialization_logged = True
        
        # Use config values
        self.pdf_dir = Path(config.pdf_dir)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata_path = config.metadata_path
        self.metadata_store = MetadataStore(self.metadata_path)
        
        self.headless = config.headless
        self.max_retries = config.max_retries
        self.rate_limiter = RateLimiter(config.requests_per_second)
        self.delay_between_requests = config.delay_between_requests
        self.delay_between_batches = config.delay_between_batches
        
        # Setup Selenium download directory
        if config.selenium_download_dir:
            self.selenium_download_dir = Path(config.selenium_download_dir).resolve()
            self._selenium_download_dir_is_temp = False
        else:
            # Use a temp directory for Selenium downloads
            self.selenium_download_dir = Path(tempfile.mkdtemp(prefix='selenium_downloads_')).resolve()
            self._selenium_download_dir_is_temp = True
        self.selenium_download_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"Selenium download directory: {self.selenium_download_dir} (temp: {self._selenium_download_dir_is_temp})")
        
        # Setup requests session
        self.session = requests.Session()
        if config.user_agent:
            self.user_agent = config.user_agent
        else:
            self.user_agent = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        self.session.headers.update({'User-Agent': self.user_agent})
        
        # Caching for optimizations
        self._landing_url_cache: Dict[str, str] = {}  # DOI/URL -> landing URL
        self._crossref_pdf_cache: Dict[str, Optional[str]] = {}  # DOI -> PDF URL (None if not found)
        
        # Components
        self.doi_resolver = DOIResolver(self.session, self.rate_limiter)
        self.download_manager = DownloadManager(self.session, self.rate_limiter, self.selenium_download_dir)
        
        # Setup retry strategy with enhanced connection pooling
        retry_strategy = Retry(
            total=config.max_retries,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(
            pool_connections=10,  # Number of connection pools
            pool_maxsize=20,      # Max connections per pool
            max_retries=retry_strategy
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Selenium driver (lazy initialization)
        self._driver: Optional[webdriver.Chrome] = None
        self._driver_initialized = False
        
        # Session persistence: track drivers by domain
        self._drivers_by_domain: Dict[str, webdriver.Chrome] = {}
        self._current_domain: Optional[str] = None
        self._domain_driver_initialized: Dict[str, bool] = {}
        
        # Cloudflare domain tracking: postpone remaining requests from domains that hit Cloudflare
        self._cloudflare_domains: set = set()  # Domains that have hit Cloudflare (for resource URLs)
        self._cloudflare_doi_prefixes: set = set()  # DOI prefixes that have hit Cloudflare (e.g., '10.1103')
        
        # Optional Crossref support (for direct PDF URL lookup)
        self.crossref_fetcher = None
        if CROSSREF_AVAILABLE and config.use_crossref:
            try:
                self.crossref_fetcher = CrossrefBibliographicFetcher()
                self.logger.info("Crossref support enabled - will try Crossref for PDF URLs first")
            except Exception as e:
                self.logger.warning(f"Could not initialize Crossref fetcher: {e} - will skip Crossref lookup")
                self.crossref_fetcher = None
    
    def set_postponed_domains(self, domains: Optional[set] = None, doi_prefixes: Optional[set] = None):
        """
        Set postponed domains and DOI prefixes (e.g., from cache).
        
        This allows external code (like the pipeline) to initialize PDFFetcher
        with known problematic domains/prefixes to avoid unnecessary requests.
        
        Args:
            domains: Set of domain names to postpone (e.g., {'pubs.acs.org', 'www.ams.org'})
            doi_prefixes: Set of DOI prefixes to postpone (e.g., {'10.1021', '10.1088'})
        """
        if domains is not None:
            self._cloudflare_domains.update(domains)
        if doi_prefixes is not None:
            self._cloudflare_doi_prefixes.update(doi_prefixes)
    
    def _get_driver(self, domain: Optional[str] = None) -> webdriver.Chrome:
        """
        Get or create Selenium driver for a domain.
        
        Args:
            domain: Domain name (e.g., 'pubs.geoscienceworld.org'). 
                   If provided, reuses driver for same domain (session persistence).
                   If None, uses single shared driver.
        
        Returns:
            Chrome WebDriver instance
        """
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is not available")
        
        # If domain is provided, use domain-specific driver (session persistence)
        if domain:
            if domain not in self._drivers_by_domain:
                # Create new driver for this domain
                self._drivers_by_domain[domain] = self._create_driver()
                self._domain_driver_initialized[domain] = True
                logger.debug(f"Created new driver for domain: {domain}")
            return self._drivers_by_domain[domain]
        
        # Legacy: single shared driver (for backward compatibility)
        if not self._driver_initialized:
            self._driver = self._create_driver()
            self._driver_initialized = True
            logger.info(f"Selenium driver initialized with download directory: {self.selenium_download_dir}")
        
        return self._driver
    
    def _create_driver(self) -> webdriver.Chrome:
        """Create a new Chrome driver with configured options.
        
        Uses standard Selenium (not undetected-chromedriver) and Chrome's
        default user-agent to avoid triggering Cloudflare bot detection.
        """
        options = ChromeOptions()
        if self.headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        # Don't set custom user-agent - use Chrome's default to avoid Cloudflare detection
        # (Custom user-agents can trigger bot detection as shown in tests)
        options.add_argument('--window-size=1920,1080')
        
        # Configure download preferences
        # Set download directory (must be absolute path)
        download_dir_str = str(self.selenium_download_dir.resolve())
        prefs = {
            "download.default_directory": download_dir_str,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,  # Download PDFs instead of viewing
            "plugins.plugins_disabled": ["Chrome PDF Viewer"],  # Disable PDF viewer
        }
        options.add_experimental_option("prefs", prefs)
        logger.debug(f"Chrome download directory set to: {download_dir_str}")
        
        # Disable PDF viewer
        options.add_argument('--disable-pdf-viewer')
        options.add_argument('--disable-extensions')
        
        driver = webdriver.Chrome(options=options)
        
        # Set timeouts to prevent long waits
        # Use config timeout or default to 30 seconds
        selenium_timeout = getattr(self.config, 'selenium_timeout', 30)
        driver.set_page_load_timeout(selenium_timeout)
        driver.implicitly_wait(5)  # Shorter implicit wait for element finding
        
        # Enable downloads via CDP
        driver.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': str(self.selenium_download_dir.resolve())
        })
        
        return driver
    
    @contextmanager
    def _suppress_cloudflare_logging(self):
        """Context manager to suppress Cloudflare warning logs during retries.
        
        Cloudflare challenges are already logged during initial attempts,
        so we suppress redundant warnings during retries.
        """
        # Store original logger level
        original_level = logger.level
        
        try:
            # Temporarily raise logger level to ERROR to suppress WARNING messages
            # (Cloudflare warnings are at WARNING level)
            logger.setLevel(logging.ERROR)
            yield
        finally:
            # Restore original logging level
            logger.setLevel(original_level)
    
    def _is_cloudflare_challenge(self, driver) -> bool:
        """Check if current page is a Cloudflare challenge.
        
        Uses improved detection logic that distinguishes between real challenges
        and false positives (e.g., 'challenge-platform' in large article pages).
        """
        try:
            page_source = driver.page_source.lower()
            title = driver.title.lower()
            page_size = len(page_source)
            
            # Primary indicators (definitive Cloudflare challenge)
            primary_indicators = [
                'i am human' in page_source,
                'just a moment' in title,
                'are you a robot' in page_source,  # Cloudflare Turnstile challenge
                'cf-challenge' in page_source,
                'cf-turnstile' in page_source,
                'turnstile' in page_source,  # Cloudflare Turnstile
                'checking your browser' in page_source[:2000],
            ]
            
            # Secondary indicators (may appear in normal pages too, need context)
            secondary_indicators = [
                'challenge-platform' in page_source,
                'cf-browser-verification' in page_source,
            ]
            
            # If we have primary indicators, it's definitely Cloudflare
            if any(primary_indicators):
                return True
            
            # For secondary indicators, require small page size (< 100KB) or specific title
            # Challenge pages are typically small, while real article pages are large (MB)
            if any(secondary_indicators):
                if page_size < 100000 or 'just a moment' in title or 'checking' in title:
                    return True
            
            return False
        except:
            return False
    
    def _is_captcha_challenge(self, driver) -> bool:
        """Check if current page contains a captcha challenge (non-Cloudflare).
        
        Detects various captcha systems including:
        - IOP Publishing captcha
        - reCAPTCHA
        - hCaptcha
        - Other publisher-specific captchas
        """
        try:
            page_source = driver.page_source.lower()
            title = driver.title.lower()
            page_size = len(page_source)
            
            # Common captcha indicators (across multiple systems)
            captcha_indicators = [
                'captcha' in page_source,
                'recaptcha' in page_source,
                'hcaptcha' in page_source,
                'verify you are human' in page_source,
                'verify you are not a robot' in page_source,
                'prove you are human' in page_source,
                'security check' in page_source,
                'access denied' in page_source and 'captcha' in page_source,
            ]
            
            # IOP Publishing specific indicators
            iop_indicators = [
                'iop' in page_source and 'security' in page_source and ('captcha' in page_source or 'verify' in page_source),
                'iop.org' in driver.current_url.lower() and 'security' in page_source,
                'iop' in title.lower() and ('verify' in title.lower() or 'security' in title.lower()),
            ]
            
            # If page is small (< 50KB) and contains captcha indicators, likely a captcha page
            if page_size < 50000:
                if any(captcha_indicators) or any(iop_indicators):
                    return True
            
            # For larger pages, require multiple indicators or specific patterns
            if any(iop_indicators):
                return True
            
            if any(captcha_indicators) and page_size < 200000:
                # Additional check: captcha pages often have specific text patterns
                if 'please' in page_source and 'complete' in page_source:
                    return True
            
            return False
        except:
            return False
    
    def _prefilter_existing(self, identifiers: List[str]) -> Tuple[List[str], List[str]]:
        """
        OPTIMIZATION: Pre-filter identifiers to skip already downloaded files.
        
        This checks file existence BEFORE any normalization or network calls,
        which can save significant time for large batches.
        
        Returns:
            (existing_identifiers, to_download_identifiers)
        """
        existing = []
        to_download = []
        
        logger.info(f"Pre-filtering {len(identifiers)} identifiers for existing files...")
        
        for identifier in identifiers:
            try:
                # Quick check: try to normalize and check file
                kind, doi, url = IdentifierNormalizer.normalize(identifier)
                
                # Get sanitized filename
                if doi:
                    sanitized = IdentifierNormalizer.sanitize_for_filename(doi)
                else:
                    sanitized = hashlib.md5(url.encode()).hexdigest()[:16]
                
                pdf_path = self.pdf_dir / f"{sanitized}.pdf"
                
                # Check if file exists and is valid PDF
                if pdf_path.exists():
                    try:
                        header = pdf_path.read_bytes()[:4]
                        if header == b'%PDF':
                            existing.append(identifier)
                            continue
                    except:
                        pass  # File might be corrupted, re-download
                
                to_download.append(identifier)
            except Exception as e:
                logger.debug(f"Error pre-filtering {identifier}: {e}")
                to_download.append(identifier)  # Include on error
        
        logger.info(f"Pre-filter complete: {len(existing)} already exist, {len(to_download)} to download")
        return existing, to_download
    
    def _sort_identifiers_by_domain(self, identifiers: List[str]) -> List[str]:
        """
        Sort identifiers by their expected domain for session persistence.
        
        This allows processing all identifiers from the same publisher/domain
        together, so we only need to pass Cloudflare once per domain.
        """
        # Group by domain (best effort - we may not know domain until resolution)
        domain_groups: Dict[str, List[Tuple[str, str]]] = {}
        unknown_domain: List[str] = []
        
        for identifier in identifiers:
            try:
                kind, doi, url = IdentifierNormalizer.normalize(identifier)
                
                if kind == 'resource_url':
                    # We know the domain from the URL
                    domain = urlparse(url).netloc
                    if domain not in domain_groups:
                        domain_groups[domain] = []
                    domain_groups[domain].append((domain, identifier))
                elif kind in ('doi', 'doi_url'):
                    # For DOIs, try to predict domain from DOI prefix
                    # Common patterns: 10.1016 -> sciencedirect.com, 10.1038 -> nature.com, etc.
                    predicted_domain = self._predict_domain_from_doi(doi)
                    if predicted_domain:
                        if predicted_domain not in domain_groups:
                            domain_groups[predicted_domain] = []
                        domain_groups[predicted_domain].append((predicted_domain, identifier))
                    else:
                        unknown_domain.append(identifier)
            except:
                unknown_domain.append(identifier)
        
        # Sort domains alphabetically for consistent ordering
        sorted_domains = sorted(domain_groups.keys())
        
        # Build sorted list: process each domain group together
        sorted_identifiers = []
        for domain in sorted_domains:
            # Sort within domain group (by identifier for consistency)
            domain_items = sorted(domain_groups[domain], key=lambda x: x[1])
            sorted_identifiers.extend([item[1] for item in domain_items])
        
        # Append unknown domain items at the end
        sorted_identifiers.extend(unknown_domain)
        
        return sorted_identifiers
    
    def _predict_domain_from_doi(self, doi: str) -> Optional[str]:
        """Predict domain from DOI prefix (heuristic)."""
        # Common DOI prefixes and their domains
        # Use actual domains as they appear in URLs (with subdomains)
        doi_prefixes = {
            '10.1016': 'sciencedirect.com',  # Elsevier
            '10.1038': 'nature.com',  # Nature
            '10.1371': 'plos.org',  # PLOS
            '10.1126': 'science.org',  # Science
            '10.2138': 'pubs.geoscienceworld.org',  # GeoScienceWorld
            '10.1007': 'link.springer.com',  # Springer
            '10.1111': 'onlinelibrary.wiley.com',  # Wiley
            '10.1093': 'academic.oup.com',  # Oxford
            '10.1103': 'link.aps.org',  # American Physical Society (use actual domain)
        }
        
        for prefix, domain in doi_prefixes.items():
            if doi.startswith(prefix):
                return domain
        
        return None
    
    def _extract_doi_prefix(self, doi: str) -> Optional[str]:
        """
        Extract DOI prefix (e.g., '10.1103' from '10.1103/PhysRevResearch.4.043131').
        
        Args:
            doi: Full DOI string
            
        Returns:
            DOI prefix (e.g., '10.1103') or None if not a valid DOI
        """
        if not doi or not doi.startswith('10.'):
            return None
        
        # DOI format: 10.xxxx/...
        # Extract everything before the first slash
        parts = doi.split('/', 1)
        if len(parts) >= 1:
            prefix = parts[0].strip()
            # Validate it looks like a DOI prefix (starts with 10. and has at least one more part)
            if prefix.startswith('10.') and len(prefix) > 3:
                return prefix
        
        return None
    
    def _normalize_domain_for_matching(self, domain: str) -> str:
        """
        Normalize domain for matching (handle subdomain differences).
        
        Examples:
            'link.aps.org' -> 'aps.org'
            'www.example.com' -> 'example.com'
            'sciencedirect.com' -> 'sciencedirect.com'
        """
        domain = domain.lower().strip()
        # Remove 'www.' prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # For known subdomain patterns, extract base domain
        parts = domain.split('.')
        if len(parts) >= 3:
            # Common subdomain prefixes to strip
            subdomain_prefixes = ['link', 'www', 'pubs', 'onlinelibrary']
            if parts[0] in subdomain_prefixes:
                return '.'.join(parts[1:])  # Return base domain
        
        return domain
    
    def _domains_match(self, domain1: str, domain2: str) -> bool:
        """
        Check if two domains match (handling subdomain differences).
        
        Examples:
            'aps.org' matches 'link.aps.org' -> True
            'link.aps.org' matches 'aps.org' -> True
            'sciencedirect.com' matches 'sciencedirect.com' -> True
        """
        norm1 = self._normalize_domain_for_matching(domain1)
        norm2 = self._normalize_domain_for_matching(domain2)
        
        # Exact match after normalization
        if norm1 == norm2:
            return True
        
        # Check if one is a subdomain of the other
        if domain1.endswith('.' + norm2) or domain2.endswith('.' + norm1):
            return True
        
        return False
    
    def _cleanup_domain_drivers(self):
        """Clean up all domain-specific drivers."""
        for domain, driver in self._drivers_by_domain.items():
            try:
                driver.quit()
                logger.debug(f"Closed driver for domain: {domain}")
            except:
                pass
        
        self._drivers_by_domain.clear()
        self._domain_driver_initialized.clear()
        self._current_domain = None
    
    def _cleanup_extra_windows(self, driver):
        """
        Close any extra windows/tabs that may have been opened during download attempts.
        Keeps only the main window open for driver reuse.
        
        Args:
            driver: Selenium WebDriver instance
        """
        if not driver:
            return
        
        try:
            handles = driver.window_handles
            if len(handles) <= 1:
                return  # No extra windows to close
            
            # Get the first window as the main window (or try to keep current if valid)
            main_window = None
            try:
                current_handle = driver.current_window_handle
                if current_handle in handles:
                    main_window = current_handle
                else:
                    main_window = handles[0]
            except:
                main_window = handles[0]
            
            # Close all other windows
            for handle in handles:
                if handle != main_window:
                    try:
                        driver.switch_to.window(handle)
                        driver.close()
                    except Exception as e:
                        logger.debug(f"Could not close window {handle}: {e}")
            
            # Switch back to main window
            try:
                driver.switch_to.window(main_window)
            except Exception as e:
                logger.debug(f"Could not switch back to main window: {e}")
        except Exception as e:
            logger.debug(f"Error cleaning up extra windows: {e}")
    
    def _close_driver(self):
        """Close Selenium driver (legacy single driver)."""
        if self._driver and self._driver_initialized:
            try:
                self._driver.quit()
            except:
                pass
            self._driver = None
            self._driver_initialized = False
        
        # Also clean up domain drivers
        self._cleanup_domain_drivers()
        
        # Clean up temporary download directory if we created it
        if hasattr(self, '_selenium_download_dir_is_temp') and self._selenium_download_dir_is_temp:
            if self.selenium_download_dir.exists():
                try:
                    # Remove any remaining files
                    for file in self.selenium_download_dir.glob('*'):
                        try:
                            if file.is_file():
                                file.unlink()
                            elif file.is_dir():
                                shutil.rmtree(file)
                        except Exception as e:
                            logger.debug(f"Could not remove {file}: {e}")
                    # Remove the directory itself
                    self.selenium_download_dir.rmdir()
                    logger.debug(f"Cleaned up temporary download directory: {self.selenium_download_dir}")
                except Exception as e:
                    logger.debug(f"Could not clean up temporary download directory: {e}")
    
    def close(self):
        """Close all resources (drivers, sessions, etc.)."""
        self._close_driver()
        if hasattr(self, 'session'):
            self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def download(self, identifier: str) -> DownloadResult:
        """
        Download PDF for given identifier.
        
        Args:
            identifier: DOI, DOI-URL, or resource URL
        
        Returns:
            DownloadResult with status and details
        """
        result = DownloadResult(
            identifier=identifier,
            first_attempted=datetime.utcnow().isoformat(),
            last_attempted=datetime.utcnow().isoformat()
        )
        
        try:
            # Normalize identifier
            kind, doi, url = IdentifierNormalizer.normalize(identifier)
            result.identifier = identifier  # Keep original
            
            # Get sanitized filename
            if doi:
                sanitized = IdentifierNormalizer.sanitize_for_filename(doi)
            else:
                # Use hash of URL for non-DOI identifiers
                sanitized = hashlib.md5(url.encode()).hexdigest()[:16]
            
            result.sanitized_filename = f"{sanitized}.pdf"
            pdf_path = self.pdf_dir / result.sanitized_filename
            
            # OPTIMIZATION: Check if already exists BEFORE any network calls
            if pdf_path.exists():
                # Verify it's a valid PDF
                try:
                    header = pdf_path.read_bytes()[:4]
                    if header == b'%PDF':
                        result.status = DownloadStatus.ALREADY_EXISTS
                        result.pdf_path = pdf_path
                        result.last_successful = datetime.utcnow().isoformat()
                        self.metadata_store.update(result)
                        logger.debug(f"PDF already exists: {pdf_path}")
                        return result
                except:
                    pass  # File might be corrupted, re-download
            
            # OPTIMIZATION: Try to get landing URL and PDF URL from Crossref metadata first (if available)
            # Crossref metadata is already cached in api_client, so fetch once and use for both
            crossref_metadata = None
            landing_url = None
            if kind in ('doi', 'doi_url') and self.crossref_fetcher and doi:
                try:
                    # fetch_by_doi() already uses api_client cache, so this is fast if cached
                    crossref_metadata = self.crossref_fetcher.fetch_by_doi(doi)
                    if crossref_metadata:
                        # Crossref metadata may include landing URLs in the 'link' field
                        # Look for non-PDF links (these are often landing pages)
                        links = crossref_metadata.get('link', [])
                        for link in links:
                            link_url = link.get('URL', '')
                            content_type = link.get('content-type', '')
                            # Skip PDF links, look for landing page links
                            if link_url and 'pdf' not in link_url.lower() and 'pdf' not in content_type.lower():
                                # Common landing page indicators
                                if any(indicator in link_url.lower() for indicator in ['article', 'abstract', 'full', 'view', 'doi.org']):
                                    landing_url = link_url
                                    logger.debug(f"Found landing URL from Crossref metadata: {landing_url}")
                                    break
                except:
                    pass  # Fall back to resolution if Crossref doesn't have it
            
            # If Crossref didn't provide landing URL, resolve it
            if not landing_url:
                # OPTIMIZATION: Check cache for landing URL resolution
                cache_key = identifier if kind == 'resource_url' else url
                if cache_key in self._landing_url_cache:
                    landing_url = self._landing_url_cache[cache_key]
                    logger.debug(f"Using cached landing URL for {identifier}")
                else:
                    # Resolve to landing URL
                    try:
                        if kind in ('doi', 'doi_url'):
                            # Try requests first
                            try:
                                landing_url = self.doi_resolver.resolve(url, use_selenium=False)
                            except:
                                # Fall back to Selenium
                                # We don't know domain yet, so use default driver
                                driver = self._get_driver()
                                landing_url = self.doi_resolver.resolve(url, use_selenium=True, selenium_driver=driver)
                        else:
                            landing_url = url
                        
                        # Cache the result
                        self._landing_url_cache[cache_key] = landing_url
                    except Exception as e:
                        result.status = DownloadStatus.INVALID_IDENTIFIER
                        result.error_reason = f"Failed to resolve identifier: {e}"
                        self.metadata_store.update(result)
                        return result
            
            result.landing_url = landing_url
            
            # Detect publisher and extract domain for session persistence
            publisher = PublisherDetector.detect(landing_url)
            result.publisher = publisher
            domain = urlparse(landing_url).netloc
            
            # Explicit logging for ams.org encounters
            is_ams_domain = domain and ('ams.org' in domain.lower() or domain.lower() in ('ams.org', 'www.ams.org'))
            if is_ams_domain:
                logger.warning("🔴 AMS.ORG DETECTED - Processing identifier")
                logger.warning(f"   Identifier: {identifier}")
                logger.warning(f"   Landing URL: {landing_url}")
                logger.warning(f"   Domain: {domain}")
                logger.warning(f"   Publisher: {publisher}")
                logger.warning(f"   In postponed domains? {domain in self._cloudflare_domains or any('ams.org' in d for d in self._cloudflare_domains)}")
            
            # Explicit logging for books.rsc.org (test case for postponement debugging)
            is_rsc_domain = domain and 'rsc.org' in domain.lower()
            if is_rsc_domain:
                logger.warning("🔵 BOOKS.RSC.ORG DETECTED - Processing identifier")
                logger.warning(f"   Identifier: {identifier}")
                logger.warning(f"   Landing URL: {landing_url}")
                logger.warning(f"   Domain: {domain}")
                logger.warning(f"   Publisher: {publisher}")
                logger.warning(f"   In postponed domains? {domain in self._cloudflare_domains or any('rsc.org' in d for d in self._cloudflare_domains)}")
                logger.warning(f"   All postponed domains: {sorted(list(self._cloudflare_domains))}")
            
            # CRITICAL: Check if this domain/DOI prefix is already postponed BEFORE attempting download
            # This prevents wasting time on domains that we know will fail (Cloudflare, 403, captcha)
            should_skip = False
            skip_reason = None
            matched_postponed_item = None
            
            # Check DOI prefix first (most specific)
            if kind in ('doi', 'doi_url') and doi:
                doi_prefix = self._extract_doi_prefix(doi)
                if doi_prefix and doi_prefix in self._cloudflare_doi_prefixes:
                    should_skip = True
                    matched_postponed_item = doi_prefix
                    skip_reason = f"DOI prefix '{doi_prefix}' already marked for postponement (Cloudflare/403/captcha)"
            
            # Check domain (for resource URLs or as fallback)
            if not should_skip:
                for postponed_domain in self._cloudflare_domains:
                    if self._domains_match(domain, postponed_domain):
                        should_skip = True
                        matched_postponed_item = postponed_domain
                        skip_reason = f"Domain '{domain}' matches postponed domain '{postponed_domain}' (Cloudflare/403/captcha)"
                        break
            
            if should_skip:
                # Explicit logging for ams.org skips
                is_ams_skip = domain and ('ams.org' in domain.lower() or domain.lower() in ('ams.org', 'www.ams.org'))
                if is_ams_skip:
                    logger.warning("🔴 AMS.ORG SKIPPED - Postponed domain detected")
                    logger.warning(f"   Identifier: {identifier}")
                    logger.warning(f"   Landing URL: {landing_url}")
                    logger.warning(f"   Domain: {domain}")
                    logger.warning(f"   Matched postponed item: {matched_postponed_item}")
                    logger.warning(f"   Reason: {skip_reason}")
                    logger.warning(f"   All postponed domains: {sorted(list(self._cloudflare_domains))}")
                    logger.warning("   " + "=" * 56)
                else:
                    # Explicit logging for books.rsc.org skips
                    is_rsc_skip = domain and 'rsc.org' in domain.lower()
                    if is_rsc_skip:
                        logger.warning("🔵 BOOKS.RSC.ORG SKIPPED - Postponed domain detected")
                        logger.warning(f"   Identifier: {identifier}")
                        logger.warning(f"   Landing URL: {landing_url}")
                        logger.warning(f"   Domain: {domain}")
                        logger.warning(f"   Matched postponed item: {matched_postponed_item}")
                        logger.warning(f"   Reason: {skip_reason}")
                        logger.warning(f"   All postponed domains: {sorted(list(self._cloudflare_domains))}")
                        logger.warning("   " + "=" * 56)
                    else:
                        logger.debug("=" * 60)
                        logger.debug(f"SKIPPING IDENTIFIER - POSTPONED DOMAIN/PREFIX DETECTED")
                        logger.debug(f"Identifier: {identifier}")
                        logger.debug(f"Landing URL: {landing_url}")
                        logger.debug(f"Domain: {domain}")
                        if kind in ('doi', 'doi_url') and doi:
                            doi_prefix_check = self._extract_doi_prefix(doi)
                            logger.debug(f"DOI prefix: {doi_prefix_check}")
                        logger.debug(f"Matched postponed item: {matched_postponed_item}")
                        logger.debug(f"Reason: {skip_reason}")
                        logger.debug(f"Current postponed domains ({len(self._cloudflare_domains)}): {sorted(list(self._cloudflare_domains))}")
                        logger.debug(f"Current postponed DOI prefixes ({len(self._cloudflare_doi_prefixes)}): {sorted(list(self._cloudflare_doi_prefixes))}")
                        logger.debug("=" * 60)
                result.status = DownloadStatus.FAILURE
                result.error_reason = skip_reason
                self.metadata_store.update(result)
                return result
            
            # Strategy 1: Try Crossref for direct PDF URL (if DOI and Crossref available)
            # OPTIMIZATION: Reuse crossref_metadata if we already fetched it above
            # Crossref metadata is already cached in api_client, so we only cache extracted PDF URL locally
            pdf_url = None
            if kind in ('doi', 'doi_url') and self.crossref_fetcher and doi:
                # Check our local cache (for quick lookup without re-extracting from metadata)
                if doi in self._crossref_pdf_cache:
                    pdf_url = self._crossref_pdf_cache[doi]
                    if pdf_url:
                        logger.debug(f"Using cached Crossref PDF URL for {doi}")
                else:
                    try:
                        logger.info(f"Trying Crossref for PDF URL: {doi}")
                        # Reuse metadata if we already fetched it above, otherwise fetch now
                        # fetch_by_doi() already uses api_client cache, so this is fast if cached
                        if crossref_metadata is None:
                            crossref_metadata = self.crossref_fetcher.fetch_by_doi(doi)
                        
                        if crossref_metadata:
                            pdf_url = CrossrefPDFExtractor.extract_pdf_url(crossref_metadata)
                            # Cache only the extracted PDF URL locally (full metadata is in api_client cache)
                            self._crossref_pdf_cache[doi] = pdf_url
                            if pdf_url:
                                logger.info(f"✓ Found PDF URL via Crossref: {pdf_url}")
                                # Use the Crossref PDF URL directly - bypass landing page
                                result.landing_url = landing_url  # Keep original landing URL for reference
                                # Skip landing page navigation - proceed directly to download
                            else:
                                logger.debug("Crossref metadata found but no PDF URL available")
                        else:
                            logger.debug("Crossref did not return metadata for this DOI")
                            self._crossref_pdf_cache[doi] = None  # Cache negative result
                    except Exception as e:
                        logger.debug(f"Crossref lookup failed: {e} - falling back to landing page")
                        self._crossref_pdf_cache[doi] = None  # Cache negative result
                        pdf_url = None
            
            # Strategy 2: Find PDF URL from landing page (if Crossref didn't provide one)
            driver = None
            if not pdf_url:
                logger.info("Finding PDF URL from landing page...")
                # Use domain-specific driver for session persistence
                driver = self._get_driver(domain=domain)
                self._current_domain = domain  # Track current domain
                try:
                    driver.get(landing_url)
                except TimeoutException as e:
                    # Catch timeout during page load and handle gracefully
                    # Clean up any extra windows that may have been opened
                    self._cleanup_extra_windows(driver)
                    # This will be caught again in the outer try/except, but we want to log it cleanly here
                    logger.warning(f"Page load timeout for {identifier} at {landing_url}")
                    raise  # Re-raise to be handled by outer exception handler
                time.sleep(2)  # Wait for page load
                
                # Check for Cloudflare challenge - if detected, log and skip
                if self._is_cloudflare_challenge(driver):
                    # Mark this domain/DOI prefix as having hit Cloudflare
                    self._cloudflare_domains.add(domain)
                    
                    # Explicit logging for books.rsc.org (test case)
                    is_rsc_cloudflare = domain and 'rsc.org' in domain.lower()
                    if is_rsc_cloudflare:
                        logger.warning("🔵" * 30)
                        logger.warning("🔵 BOOKS.RSC.ORG - CLOUDFLARE DETECTED - MARKING FOR POSTPONEMENT 🔵")
                        logger.warning("🔵" * 30)
                        logger.warning(f"Identifier: {identifier}")
                        logger.warning(f"Resource URL: {landing_url}")
                        logger.warning(f"Domain: {domain}")
                        logger.warning(f"Domain '{domain}' added to _cloudflare_domains set")
                        logger.warning(f"Total postponed domains in this fetcher now: {len(self._cloudflare_domains)}")
                        logger.warning(f"All postponed domains in this fetcher: {sorted(list(self._cloudflare_domains))}")
                        logger.warning("🔵" * 30)
                    
                    # If this is a DOI, also mark the DOI prefix
                    if kind in ('doi', 'doi_url') and doi:
                        doi_prefix = self._extract_doi_prefix(doi)
                        if doi_prefix:
                            self._cloudflare_doi_prefixes.add(doi_prefix)
                            logger.warning(f"DOI prefix '{doi_prefix}' marked - remaining DOIs with this prefix will be postponed")
                    
                    logger.warning("=" * 60)
                    logger.warning("CLOUDFLARE CHALLENGE DETECTED - SKIPPING")
                    logger.warning(f"Identifier: {identifier}")
                    logger.warning(f"Resource URL: {landing_url}")
                    logger.warning(f"Publisher: {publisher or 'unknown'}")
                    logger.warning(f"Domain '{domain}' marked - remaining requests from this domain will be postponed")
                    logger.warning("=" * 60)
                    
                    result.status = DownloadStatus.FAILURE
                    result.error_reason = f"Cloudflare challenge - Resource URL: {landing_url}, Publisher: {publisher or 'unknown'}"
                    self.metadata_store.update(result)
                    return result
                
                # Check for captcha challenge (non-Cloudflare) - if detected, log and skip
                if self._is_captcha_challenge(driver):
                    # Mark this domain/DOI prefix as having hit captcha
                    self._cloudflare_domains.add(domain)
                    
                    # If this is a DOI, also mark the DOI prefix
                    if kind in ('doi', 'doi_url') and doi:
                        doi_prefix = self._extract_doi_prefix(doi)
                        if doi_prefix:
                            self._cloudflare_doi_prefixes.add(doi_prefix)
                            logger.warning(f"DOI prefix '{doi_prefix}' marked due to captcha - remaining DOIs with this prefix will be postponed")
                    
                    logger.warning("=" * 60)
                    logger.warning("CAPTCHA CHALLENGE DETECTED - SKIPPING")
                    logger.warning(f"Identifier: {identifier}")
                    logger.warning(f"Resource URL: {landing_url}")
                    logger.warning(f"Publisher: {publisher or 'unknown'}")
                    logger.warning(f"Domain '{domain}' marked - remaining requests from this domain will be postponed")
                    logger.warning("=" * 60)
                    
                    result.status = DownloadStatus.FAILURE
                    result.error_reason = f"Captcha challenge - Resource URL: {landing_url}, Publisher: {publisher or 'unknown'}"
                    self.metadata_store.update(result)
                    return result
                
                # Check for paywall indicators
                page_text = driver.page_source.lower()
                paywall_indicators = [
                    'purchase pdf', 'subscription required', 'sign in to access',
                    'institutional access required', 'pay per view'
                ]
                if any(indicator in page_text for indicator in paywall_indicators):
                    result.status = DownloadStatus.PAYWALL
                    result.error_reason = "Paywall detected"
                    self.metadata_store.update(result)
                    return result
                
                # Find PDF link from landing page
                finder = PDFLinkFinder(driver, self.rate_limiter)
                pdf_url = finder.find_pdf_url(landing_url, publisher)
            
            # If we still don't have a PDF URL, fail
            if not pdf_url:
                result.status = DownloadStatus.FAILURE
                if self.crossref_fetcher and kind in ('doi', 'doi_url'):
                    result.error_reason = "Could not find PDF link (tried Crossref and landing page)"
                else:
                    result.error_reason = "Could not find PDF link"
                self.metadata_store.update(result)
                return result
            
            result.pdf_url = pdf_url
            
            # Download PDF
            # If we got PDF URL from Crossref, we skipped landing page navigation
            # In that case, we don't have cookies or driver context
            cookies = None
            driver_for_download = None
            if driver:
                # We visited the landing page - get cookies and driver
                try:
                    cookies = driver.get_cookies()
                    driver_for_download = driver
                except:
                    pass
            else:
                # We got PDF URL from Crossref - no landing page visit needed
                # But we might still want to use a domain-specific driver for the download
                if domain:
                    try:
                        driver_for_download = self._get_driver(domain=domain)
                        cookies = driver_for_download.get_cookies()
                    except:
                        pass
                logger.debug("Using Crossref PDF URL - attempting to use domain driver for cookies")
            
            # Explicit logging for ams.org download attempts
            if 'domain' in locals() and domain and ('ams.org' in domain.lower() or domain.lower() in ('ams.org', 'www.ams.org')):
                logger.warning("🔴 AMS.ORG - Attempting PDF download")
                logger.warning(f"   PDF URL: {pdf_url}")
                logger.warning(f"   Output path: {pdf_path}")
            
            success = self.download_manager.download(
                pdf_url, 
                pdf_path, 
                cookies=cookies,
                referer=landing_url if landing_url else None,  # Pass referer for watermarking services
                selenium_driver=driver_for_download  # Pass driver for Selenium fallback
            )
            
            # Explicit logging for ams.org download results
            if 'domain' in locals() and domain and ('ams.org' in domain.lower() or domain.lower() in ('ams.org', 'www.ams.org')):
                if success:
                    logger.warning("🔴 AMS.ORG - Download SUCCESS")
                else:
                    logger.warning("🔴 AMS.ORG - Download FAILED")
            
            if success:
                result.status = DownloadStatus.SUCCESS
                result.pdf_path = pdf_path
                result.last_successful = datetime.utcnow().isoformat()
            else:
                result.status = DownloadStatus.FAILURE
                result.error_reason = "Download failed or file is not a valid PDF"
            
            self.metadata_store.update(result)
            return result
            
        except (TimeoutError, TimeoutException) as e:
            # Clean up any extra windows/tabs that may have been opened during the download attempt
            # Try to clean up drivers that were used during this download attempt
            try:
                # Check if we have a driver in local scope (for landing page navigation)
                if 'driver' in locals() and driver:
                    self._cleanup_extra_windows(driver)
                # Also check if driver_for_download exists (for PDF download)
                if 'driver_for_download' in locals() and driver_for_download:
                    self._cleanup_extra_windows(driver_for_download)
                # Also clean up the current domain's driver if set (domain-specific driver may have opened windows)
                if hasattr(self, '_current_domain') and self._current_domain:
                    domain_driver = self._drivers_by_domain.get(self._current_domain)
                    if domain_driver:
                        self._cleanup_extra_windows(domain_driver)
            except Exception as cleanup_error:
                logger.debug(f"Error during window cleanup after timeout: {cleanup_error}")
            
            # Handle Selenium/WebDriver timeouts gracefully
            # Get full error message - TimeoutException.msg contains the actual message
            # The error format is: "Message: timeout: Timed out receiving message from renderer: 29.596"
            timeout_msg = str(e)
            if hasattr(e, 'msg') and e.msg:
                timeout_msg = str(e.msg)
            # Also check the full exception representation for additional context
            full_msg = f"{timeout_msg} {repr(e)}".lower()
            timeout_msg_lower = timeout_msg.lower()
            
            selenium_timeout = getattr(self.config, 'selenium_timeout', 30)
            
            # Detect different types of timeouts (check multiple sources)
            # TimeoutException message format: "Message: timeout: Timed out receiving message from renderer: 29.596"
            # The message might be in e.msg, str(e), or the full exception representation
            renderer_indicators = [
                'receiving message from renderer',
                'timed out receiving message',
                'renderer timeout',
            ]
            # Check all possible message sources
            all_msg_sources = [timeout_msg_lower, full_msg]
            if hasattr(e, 'msg') and e.msg:
                all_msg_sources.append(str(e.msg).lower())
            
            is_renderer_timeout = any(
                any(indicator in msg_source for msg_source in all_msg_sources)
                for indicator in renderer_indicators
            )
            
            if is_renderer_timeout:
                # Chrome renderer timeout - page is stuck or taking too long to render
                result.status = DownloadStatus.FAILURE
                result.error_reason = (
                    f"Chrome renderer timeout ({selenium_timeout}s) - page took too long to render. "
                    f"This often happens with slow-loading or JavaScript-heavy pages. "
                    f"Try increasing 'selenium_timeout' in config."
                )
                # Log without traceback for cleaner output
                logger.warning(f"Renderer timeout for {identifier}: {result.error_reason}")
            elif 'localhost' in timeout_msg or 'port' in timeout_msg or 'HTTPConnectionPool' in timeout_msg:
                # This is a Selenium WebDriver timeout (connection to ChromeDriver)
                result.status = DownloadStatus.FAILURE
                result.error_reason = (
                    f"Selenium connection timeout ({selenium_timeout}s) - browser took too long to respond. "
                    f"Try increasing 'selenium_timeout' in config or check if Chrome/ChromeDriver is working."
                )
                logger.warning(f"Connection timeout for {identifier}: {result.error_reason}")
            elif 'page load' in timeout_msg.lower() or ('timeout' in timeout_msg.lower() and 'page' in timeout_msg.lower()):
                # Generic page load timeout
                result.status = DownloadStatus.FAILURE
                result.error_reason = (
                    f"Page load timeout ({selenium_timeout}s) - page took too long to load. "
                    f"Try increasing 'selenium_timeout' in config or check if the page is accessible."
                )
                logger.warning(f"Page load timeout for {identifier}: {result.error_reason}")
            else:
                # Generic timeout - check if it's a renderer timeout by checking the message more carefully
                # The error message format is "Message: timeout: Timed out receiving message from renderer: 29.596"
                if 'renderer' in full_msg or 'Timed out receiving message' in timeout_msg:
                    result.status = DownloadStatus.FAILURE
                    result.error_reason = (
                        f"Chrome renderer timeout ({selenium_timeout}s) - page took too long to render. "
                        f"Try increasing 'selenium_timeout' in config."
                    )
                    logger.warning(f"Renderer timeout for {identifier}: {result.error_reason}")
                else:
                    # Generic timeout - truncate to avoid long stacktraces
                    result.status = DownloadStatus.FAILURE
                    # Extract just the message part, not the full exception
                    clean_msg = timeout_msg.split('\n')[0][:200]  # First line, max 200 chars
                    result.error_reason = f"Timeout error: {clean_msg}"
                    logger.warning(f"Timeout for {identifier}: {clean_msg}")
            self.metadata_store.update(result)
            return result
        except Exception as e:
            # Clean up any extra windows/tabs that may have been opened during the download attempt
            try:
                # Check if we have a driver in local scope (for landing page navigation)
                if 'driver' in locals() and driver:
                    self._cleanup_extra_windows(driver)
                # Also check if driver_for_download exists (for PDF download)
                if 'driver_for_download' in locals() and driver_for_download:
                    self._cleanup_extra_windows(driver_for_download)
                # Also clean up the current domain's driver if set (domain-specific driver may have opened windows)
                if hasattr(self, '_current_domain') and self._current_domain:
                    domain_driver = self._drivers_by_domain.get(self._current_domain)
                    if domain_driver:
                        self._cleanup_extra_windows(domain_driver)
            except Exception as cleanup_error:
                logger.debug(f"Error during window cleanup after exception: {cleanup_error}")
            
            # Check for specific HTTP error codes
            error_str = str(e)
            error_str_lower = error_str.lower()
            error_type = type(e).__name__
            
            # Explicit logging for ams.org in ANY exception (before checking error types)
            if 'ams.org' in error_str_lower:
                logger.warning("🔴 AMS.ORG DETECTED IN EXCEPTION")
                logger.warning(f"   Exception type: {error_type}")
                logger.warning(f"   Identifier: {identifier}")
                logger.warning(f"   Error message: {error_str[:400]}")
                # Try to log domain if available
                if 'domain' in locals():
                    logger.warning(f"   Domain variable: {domain}")
                elif 'landing_url' in locals() and landing_url:
                    try:
                        domain_from_url = urlparse(landing_url).netloc
                        logger.warning(f"   Domain from landing_url: {domain_from_url}")
                    except:
                        pass
                if 'pdf_url' in locals() and pdf_url:
                    logger.warning(f"   PDF URL: {pdf_url}")
            
            # Check HTTP status code from exception if available
            http_status_code = None
            if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                http_status_code = e.response.status_code
            
            # Detect 404 Not Found errors (resource doesn't exist - permanent failure)
            is_404_error = (
                http_status_code == 404 or
                '404' in error_str_lower or 
                'not found' in error_str_lower or
                ('http' in error_str_lower and '404' in error_str_lower)
            )
            
            # Detect 403 Forbidden errors (access denied - might be temporary, postpone)
            is_403_error = (
                http_status_code == 403 or
                '403' in error_str_lower or 
                'forbidden' in error_str_lower or 
                ('http' in error_str_lower and '403' in error_str_lower)
            )
            
            # Handle 404 Not Found: mark as permanent failure (don't postpone)
            if is_404_error:
                result.status = DownloadStatus.PDF_NOT_FOUND
                if 'landing_url' in locals():
                    result.error_reason = f"404 Not Found - Resource URL: {landing_url}"
                else:
                    result.error_reason = f"404 Not Found: {error_str_lower[:200]}"
                logger.warning(f"PDF not found (404) for {identifier}: {result.error_reason}")
                self.metadata_store.update(result)
                return result
            
            if is_403_error:
                # Explicit logging for ams.org 403 errors
                error_contains_ams = 'ams.org' in error_str_lower
                if error_contains_ams:
                    logger.warning("🔴 AMS.ORG - 403 ERROR DETECTED")
                    logger.warning(f"   Identifier: {identifier}")
                    logger.warning(f"   Error: {error_str[:300]}")
                
                # Extract domain from various sources (error message, pdf_url, landing_url, or existing domain variable)
                detected_domain = None
                
                # First, try to get domain from existing variable scope (most reliable)
                if 'domain' in locals() and domain:
                    detected_domain = domain
                    if error_contains_ams:
                        logger.warning(f"   Extracted domain from variable scope: {detected_domain}")
                
                # Try to extract domain from PDF URL (if available)
                if not detected_domain:
                    if 'pdf_url' in locals() and pdf_url:
                        try:
                            detected_domain = urlparse(pdf_url).netloc
                            if error_contains_ams:
                                logger.warning(f"   Extracted domain from PDF URL: {detected_domain}")
                        except:
                            pass
                
                # Try to extract domain from landing URL (fallback)
                if not detected_domain:
                    if 'landing_url' in locals() and landing_url:
                        try:
                            detected_domain = urlparse(landing_url).netloc
                            if error_contains_ams:
                                logger.warning(f"   Extracted domain from landing URL: {detected_domain}")
                        except:
                            pass
                
                # Try to extract domain from error message (e.g., "403 Client Error: Forbidden for url: https://...")
                # This is important because errors from download_manager.download() include the URL in the error message
                if not detected_domain:
                    # Use original error string (not lowercased) for URL extraction to preserve case
                    # Try multiple patterns to extract URL from error message
                    url_patterns = [
                        r'for url:\s*(https?://[^\s\)]+)',  # Pattern: "for url: https://..." (most specific)
                        r'url:\s*(https?://[^\s\)]+)',  # Pattern: "url: https://..."
                        r'https?://([^\s/\)]+)',  # Basic pattern: http://domain or https://domain
                    ]
                    for pattern in url_patterns:
                        url_match = re.search(pattern, error_str, re.IGNORECASE)
                        if url_match:
                            # Extract URL and then get domain from it
                            extracted_url = url_match.group(1) if url_match.lastindex >= 1 else url_match.group(0)
                            try:
                                detected_domain = urlparse(extracted_url).netloc
                                if detected_domain:
                                    if error_contains_ams:
                                        logger.warning(f"   Extracted domain from error message URL: {extracted_url} -> {detected_domain}")
                                    break
                            except Exception:
                                # If URL parsing fails, the extracted_url might already be a domain
                                # Check if it looks like a domain (contains dots)
                                if '.' in extracted_url and not extracted_url.startswith('http'):
                                    detected_domain = extracted_url
                                    if error_contains_ams:
                                        logger.warning(f"   Extracted domain directly from error message: {detected_domain}")
                                    break
                
                # Extract domain from response URL if available (last resort)
                if not detected_domain and hasattr(e, 'response') and hasattr(e.response, 'url'):
                    try:
                        detected_domain = urlparse(e.response.url).netloc
                    except:
                        pass
                
                # Mark domain if we found it
                if detected_domain:
                    # Check if this is ams.org BEFORE adding (for logging)
                    is_ams_postponement = detected_domain and ('ams.org' in detected_domain.lower())
                    
                    self._cloudflare_domains.add(detected_domain)
                    
                    # Explicit logging for ams.org postponements - ALWAYS log this prominently
                    if is_ams_postponement:
                        logger.warning("")
                        logger.warning("🔴" * 30)
                        logger.warning("🔴 AMS.ORG 403 FORBIDDEN - MARKING FOR POSTPONEMENT 🔴")
                        logger.warning("🔴" * 30)
                        logger.warning(f"Identifier: {identifier}")
                        if 'landing_url' in locals() and landing_url:
                            logger.warning(f"Landing URL: {landing_url}")
                        if 'pdf_url' in locals() and pdf_url:
                            logger.warning(f"PDF URL: {pdf_url}")
                        logger.warning(f"Detected domain: {detected_domain}")
                        logger.warning(f"Domain '{detected_domain}' added to postponed domains set")
                        logger.warning(f"Total postponed domains now: {len(self._cloudflare_domains)}")
                        logger.warning(f"All postponed domains: {sorted(list(self._cloudflare_domains))}")
                        logger.warning("🔴" * 30)
                        logger.warning("")
                    else:
                        logger.warning("=" * 60)
                        logger.warning("403 FORBIDDEN ERROR - MARKING DOMAIN FOR POSTPONEMENT")
                        logger.warning(f"Identifier: {identifier}")
                        if 'landing_url' in locals() and landing_url:
                            logger.warning(f"Resource URL: {landing_url}")
                        if 'pdf_url' in locals() and pdf_url:
                            logger.warning(f"PDF URL: {pdf_url}")
                        logger.warning(f"Domain '{detected_domain}' marked - remaining requests from this domain will be postponed")
                        logger.warning("=" * 60)
                else:
                    # Log a warning if we couldn't extract the domain (shouldn't happen, but useful for debugging)
                    # Special logging if error contains ams.org
                    if 'ams.org' in error_str_lower:
                        logger.warning("🔴" * 30)
                        logger.warning("🔴 AMS.ORG 403 ERROR - BUT COULD NOT EXTRACT DOMAIN!")
                        logger.warning("🔴" * 30)
                        logger.warning(f"Identifier: {identifier}")
                        logger.warning(f"Error message: {error_str[:400]}")
                        logger.warning("This should not happen - domain should be extractable from error message")
                        logger.warning("🔴" * 30)
                    logger.warning(f"403 Forbidden error detected but could not extract domain from error: {error_str_lower[:200]}")
                
                # If this is a DOI, also mark the DOI prefix
                if 'kind' in locals() and kind in ('doi', 'doi_url') and 'doi' in locals() and doi:
                    doi_prefix = self._extract_doi_prefix(doi)
                    if doi_prefix:
                        self._cloudflare_doi_prefixes.add(doi_prefix)
                        logger.warning(f"DOI prefix '{doi_prefix}' marked due to 403 Forbidden - remaining DOIs with this prefix will be postponed")
                
                result.status = DownloadStatus.FAILURE
                if 'landing_url' in locals():
                    result.error_reason = f"403 Forbidden - Resource URL: {landing_url}"
                else:
                    result.error_reason = f"403 Forbidden error: {error_str_lower[:200]}"
                self.metadata_store.update(result)
                return result
            
            # Check if it's a urllib3 ReadTimeoutError (Selenium connection timeout)
            if (Urllib3ReadTimeoutError and isinstance(e, Urllib3ReadTimeoutError)) or \
               ('ReadTimeoutError' in error_type) or \
               ('HTTPConnectionPool' in error_str and 'localhost' in error_str and 'Read timed out' in error_str):
                selenium_timeout = getattr(self.config, 'selenium_timeout', 30)
                result.status = DownloadStatus.FAILURE
                result.error_reason = (
                    f"Selenium connection timeout ({selenium_timeout}s) - browser took too long to respond. "
                    f"Try increasing 'selenium_timeout' in config or check if Chrome/ChromeDriver is working."
                )
                logger.warning(f"Selenium timeout for {identifier}: {result.error_reason}")
            else:
                logger.error(f"Error downloading PDF: {e}", exc_info=True)
                result.status = DownloadStatus.FAILURE
                result.error_reason = str(e)
            self.metadata_store.update(result)
            return result
    
    def download_batch(
        self, 
        identifiers: List[str], 
        batch_size: int = 10,
        retry_failures: bool = True,
        sort_by_domain: bool = True,
        progress: bool = True,
        prefilter: bool = True
    ) -> List[DownloadResult]:
        """
        Download PDFs for multiple identifiers with batching and retry support.
        
        Uses session persistence: sorts identifiers by domain and reuses the same
        Selenium driver for requests to the same domain. This means you only need
        to pass Cloudflare once per domain, then subsequent requests in the same
        session should work.
        
        OPTIMIZATIONS:
        - Pre-filters existing files before any network calls
        - Skips delays for direct PDF URLs (from Crossref)
        - Caches landing page resolutions
        - Zero delays when switching domains
        
        Args:
            identifiers: List of DOIs, DOI-URLs, or resource URLs
            batch_size: Number of downloads per batch (smaller = less likely to trigger Cloudflare)
            retry_failures: Whether to retry failed downloads at the end
            sort_by_domain: If True, sort identifiers by domain first (enables session persistence)
            progress: If True, show tqdm progress bar (requires tqdm package)
            prefilter: If True, pre-filter existing files before processing (default: True)
        
        Returns:
            List of DownloadResult objects
        """
        all_results: List[DownloadResult] = []
        
        # OPTIMIZATION: Pre-filter existing files
        if prefilter:  # prefilter parameter is defined in function signature
            existing_ids, identifiers = self._prefilter_existing(identifiers)
            
            # Create results for existing files
            for identifier in existing_ids:
                try:
                    kind, doi, url = IdentifierNormalizer.normalize(identifier)
                    if doi:
                        sanitized = IdentifierNormalizer.sanitize_for_filename(doi)
                    else:
                        sanitized = hashlib.md5(url.encode()).hexdigest()[:16]
                    
                    pdf_path = self.pdf_dir / f"{sanitized}.pdf"
                    
                    result = DownloadResult(
                        identifier=identifier,
                        status=DownloadStatus.ALREADY_EXISTS,
                        pdf_path=pdf_path,
                        first_attempted=datetime.utcnow().isoformat(),
                        last_attempted=datetime.utcnow().isoformat(),
                        last_successful=datetime.utcnow().isoformat()
                    )
                    all_results.append(result)
                    self.metadata_store.update(result)
                except:
                    pass  # Skip if normalization fails
        
        if not identifiers:
            logger.info("All files already exist!")
            return all_results
        
        results: List[DownloadResult] = []
        total = len(identifiers)
        
        # Sort by domain for session persistence
        if sort_by_domain:
            logger.info("Sorting identifiers by domain for session persistence...")
            sorted_identifiers = self._sort_identifiers_by_domain(identifiers)
            logger.info(f"Sorted {len(sorted_identifiers)} identifiers into domain groups")
        else:
            sorted_identifiers = identifiers
        
        logger.info(f"Starting batch download: {total} identifiers, batch size: {batch_size}")
        if sort_by_domain:
            logger.info("Session persistence enabled: reusing drivers for same-domain requests")
        
        # Track postponed identifiers (from domains that hit Cloudflare)
        postponed_identifiers: List[str] = []
        
        # Setup progress bar
        pbar = None
        if progress and TQDM_AVAILABLE:
            # Configure tqdm for Jupyter notebooks
            pbar = tqdm(
                total=total, 
                desc="Downloading PDFs", 
                unit="PDF",
                file=sys.stdout,  # Ensure output goes to stdout
                dynamic_ncols=True,  # Better for notebooks
                mininterval=0.5,  # Update at least every 0.5 seconds
                maxinterval=1.0,  # But no more than every 1 second
            )
            sys.stdout.flush()  # Initial flush
            sys.stdout.flush()  # Initial flush
        elif progress and not TQDM_AVAILABLE:
            logger.warning("tqdm not available - install with 'pip install tqdm' for progress bars")
        
        try:
            # Process in batches
            current_domain = None
            for batch_start in range(0, total, batch_size):
                # Check for interruption at batch boundaries
                # This allows cleaner interruption between batches
                batch_end = min(batch_start + batch_size, total)
                batch = sorted_identifiers[batch_start:batch_end]
                batch_num = (batch_start // batch_size) + 1
                total_batches = (total + batch_size - 1) // batch_size
                
                if pbar:
                    pbar.set_description(f"Batch {batch_num}/{total_batches}")
                    pbar.refresh()
                    sys.stdout.flush()
                else:
                    logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} items)")
                
                # Force flush logs in notebooks
                sys.stdout.flush()
                sys.stderr.flush()
                
                for i, identifier in enumerate(batch, 1):
                    # Track domain changes for logging and delay optimization
                    domain_changed = False
                    previous_domain = current_domain
                    identifier_domain = None
                    
                    # Check for postponement before download
                    try:
                        kind, doi, url = IdentifierNormalizer.normalize(identifier)
                        
                        # For DOIs: Check if DOI prefix has hit Cloudflare
                        # Use prefix + '/' to avoid false matches (e.g., 10.1103 shouldn't match 10.11035)
                        if kind in ('doi', 'doi_url') and doi:
                            should_postpone_doi = False
                            matching_prefix = None
                            for postponed_prefix in self._cloudflare_doi_prefixes:
                                # Check if DOI starts with prefix followed by '/' (exact prefix match)
                                if doi.startswith(postponed_prefix + '/'):
                                    should_postpone_doi = True
                                    matching_prefix = postponed_prefix
                                    break  # Found matching prefix, no need to check others
                            
                            if should_postpone_doi:
                                postponed_identifiers.append(identifier)
                                if pbar:
                                    pbar.set_postfix_str(f"Postponed (Cloudflare): {matching_prefix}")
                                else:
                                    logger.info(f"Postponing {identifier} - DOI prefix '{matching_prefix}' hit Cloudflare")
                                if pbar:
                                    pbar.update(1)
                                continue  # Skip this identifier for now
                        
                        # For resource URLs: Check if domain has hit Cloudflare
                        elif kind == 'resource_url':
                            identifier_domain = urlparse(url).netloc
                            should_postpone = False
                            for cloudflare_domain in self._cloudflare_domains:
                                if self._domains_match(identifier_domain, cloudflare_domain):
                                    should_postpone = True
                                    break
                            
                            if should_postpone:
                                postponed_identifiers.append(identifier)
                                if pbar:
                                    pbar.set_postfix_str(f"Postponed (Cloudflare): {identifier_domain}")
                                else:
                                    logger.info(f"Postponing {identifier} - domain '{identifier_domain}' matches Cloudflare domain")
                                if pbar:
                                    pbar.update(1)
                                continue  # Skip this identifier for now
                        
                        # Track domain for delay optimization (predict domain from DOI if needed)
                        if kind in ('doi', 'doi_url') and doi:
                            identifier_domain = self._predict_domain_from_doi(doi)
                        elif kind == 'resource_url':
                            identifier_domain = urlparse(url).netloc
                        
                        if identifier_domain and identifier_domain != current_domain:
                            previous_domain = current_domain
                            current_domain = identifier_domain
                            domain_changed = True
                            if pbar:
                                pbar.set_postfix_str(f"Domain: {identifier_domain}")
                            else:
                                logger.info(f"Switching to domain: {identifier_domain}")
                    except:
                        pass
                    
                    if pbar:
                        pbar.set_postfix_str(f"Downloading: {identifier[:50]}...")
                        pbar.refresh()  # Force refresh in notebooks
                        sys.stdout.flush()  # Force flush for Jupyter notebooks
                    else:
                        logger.info(f"[{batch_start + i}/{total}] Downloading: {identifier}")
                        # Force flush for Jupyter notebooks
                        sys.stdout.flush()
                        sys.stderr.flush()
                    
                    # Track if we used Crossref (for delay optimization)
                    used_crossref = False
                    if kind in ('doi', 'doi_url') and doi:
                        # Check if this DOI has Crossref PDF URL cached
                        if doi in self._crossref_pdf_cache and self._crossref_pdf_cache[doi]:
                            used_crossref = True
                    
                    # Download (this can take a while, especially with Selenium)
                    # Wrap in try/except to catch KeyboardInterrupt during download
                    try:
                        result = self.download(identifier)
                    except KeyboardInterrupt:
                        logger.warning(f"Download interrupted for {identifier}")
                        logger.warning("Cleaning up Selenium drivers...")
                        self._cleanup_domain_drivers()
                        if pbar:
                            pbar.close()
                        raise  # Re-raise to stop batch processing
                    
                    # Flush immediately after download to show progress
                    if pbar:
                        sys.stdout.flush()
                    results.append(result)
                    
                    # Update domain from result if we didn't know it before
                    if result.landing_url and not identifier_domain:
                        identifier_domain = urlparse(result.landing_url).netloc
                        # If this domain hit Cloudflare during download, it's already marked
                    
                    # Update used_crossref flag from result if available
                    # (We'll check this in the delay logic below)
                    
                    # Update current_domain from result if we didn't know it before
                    if result.landing_url:
                        new_domain = urlparse(result.landing_url).netloc
                        if new_domain != current_domain:
                            previous_domain = current_domain
                            current_domain = new_domain
                            domain_changed = True
                            if not pbar:
                                logger.debug(f"Detected domain change to: {current_domain}")
                    
                    # Update progress bar
                    if pbar:
                        status_emoji = {
                            DownloadStatus.SUCCESS: "✓",
                            DownloadStatus.ALREADY_EXISTS: "○",
                            DownloadStatus.FAILURE: "✗",
                            DownloadStatus.PAYWALL: "🔒",
                        }.get(result.status, "?")
                        pbar.set_postfix_str(f"{status_emoji} {result.status.value}")
                        pbar.update(1)
                        pbar.refresh()  # Force refresh
                        sys.stdout.flush()  # Force flush for Jupyter notebooks
                    
                    # Delay between requests within batch
                    # OPTIMIZATION: Zero delay if:
                    # 1. We just switched domains (different site = no rate limit concern)
                    # 2. We got PDF URL from Crossref (direct download, no landing page navigation)
                    should_delay = True
                    delay_reason = None
                    
                    if i < len(batch):
                        # Check if we used Crossref (direct PDF URL, no landing page)
                        if result.pdf_url and used_crossref:
                            should_delay = False
                            delay_reason = "direct PDF URL from Crossref"
                        elif domain_changed and previous_domain is not None:
                            should_delay = False
                            delay_reason = f"domain changed from {previous_domain} to {current_domain}"
                        
                        if should_delay:
                            # Same domain - apply delay to avoid rate limiting
                            time.sleep(self.delay_between_requests)
                        else:
                            if not pbar:
                                logger.debug(f"Skipping delay: {delay_reason}")
                
                # Delay between batches
                # Check if next batch is from a different domain - if so, zero delay
                if batch_end < total:
                    next_batch_start = batch_end
                    next_identifier = sorted_identifiers[next_batch_start] if next_batch_start < len(sorted_identifiers) else None
                    next_domain = None
                    
                    if next_identifier:
                        try:
                            kind, doi, url = IdentifierNormalizer.normalize(next_identifier)
                            if kind == 'resource_url':
                                next_domain = urlparse(url).netloc
                        except:
                            pass
                    
                    # If next batch is from different domain, skip delay
                    if next_domain and next_domain != current_domain:
                        if pbar:
                            pbar.set_postfix_str("Switching domain - no delay")
                        else:
                            logger.info(f"Batch {batch_num} complete. Next batch is different domain ({next_domain}) - skipping delay")
                    else:
                        if pbar:
                            pbar.set_postfix_str(f"Waiting {self.delay_between_batches}s...")
                        else:
                            logger.info(f"Batch {batch_num} complete. Waiting {self.delay_between_batches}s before next batch...")
                        time.sleep(self.delay_between_batches)
            
            # Process postponed identifiers (from domains that hit Cloudflare)
            if postponed_identifiers:
                logger.info(f"Processing {len(postponed_identifiers)} postponed identifiers from Cloudflare-protected domains...")
                logger.info(f"Postponed domains: {sorted(self._cloudflare_domains)}")
                if self._cloudflare_doi_prefixes:
                    logger.info(f"Postponed DOI prefixes: {sorted(self._cloudflare_doi_prefixes)}")
                
                # Wait a bit before processing postponed items (give Cloudflare time to cool down)
                wait_time = self.delay_between_batches * 3  # Longer wait for postponed items
                logger.info(f"Waiting {wait_time}s before processing postponed items...")
                # Add periodic heartbeat during long wait
                elapsed = 0
                while elapsed < wait_time:
                    sleep_chunk = min(5, wait_time - elapsed)  # Check every 5 seconds
                    time.sleep(sleep_chunk)
                    elapsed += sleep_chunk
                    remaining = wait_time - elapsed
                    if remaining > 0:
                        logger.info(f"Still waiting... {remaining:.0f}s remaining")
                
                # Create progress bar for postponed items
                postponed_pbar = None
                if progress and TQDM_AVAILABLE:
                    postponed_pbar = tqdm(
                        total=len(postponed_identifiers),
                        desc=f"Processing {len(postponed_identifiers)} postponed",
                        unit="PDF",
                        leave=True
                    )
                
                try:
                    for i, identifier in enumerate(postponed_identifiers, 1):
                        if postponed_pbar:
                            postponed_pbar.set_postfix_str(f"{i}/{len(postponed_identifiers)}: {identifier[:40]}...")
                        else:
                            logger.info(f"Processing postponed {i}/{len(postponed_identifiers)}: {identifier}")
                        
                        # Try to download with longer delays
                        result = self.download(identifier)
                        results.append(result)
                        
                        if postponed_pbar:
                            status_emoji = {
                                DownloadStatus.SUCCESS: "✓",
                                DownloadStatus.FAILURE: "✗",
                                DownloadStatus.PAYWALL: "🔒",
                            }.get(result.status, "?")
                            postponed_pbar.set_postfix_str(f"{status_emoji} {result.status.value}")
                            postponed_pbar.update(1)
                        
                        # Longer delay for postponed items (they're from problematic domains)
                        time.sleep(self.delay_between_requests * 3)
                finally:
                    if postponed_pbar:
                        postponed_pbar.close()
                
                logger.info(f"Completed processing {len(postponed_identifiers)} postponed identifiers")
            
            # Retry failures if requested
            if retry_failures:
                # Include failures from both main batch and postponed items
                # Only retry actual failures, not paywalls or invalid identifiers
                failures = [
                    r for r in results 
                    if r.status == DownloadStatus.FAILURE 
                    and r.error_reason  # Make sure it has an error reason
                ]
                
                # Debug: Log status breakdown
                status_breakdown = {}
                for r in results:
                    status_breakdown[r.status.value] = status_breakdown.get(r.status.value, 0) + 1
                logger.info(f"Results status breakdown: {status_breakdown}")
                logger.info(f"Found {len(failures)} failures to retry (out of {len(results)} total results)")
                
                # Log some example failure reasons
                if failures:
                    logger.info(f"Retry enabled: Will retry {len(failures)} failed downloads")
                    example_errors = [r.error_reason[:100] for r in failures[:3]]
                    logger.info(f"Example failure reasons: {example_errors}")
                    # Create a separate progress bar for retries
                    retry_pbar = None
                    if progress and TQDM_AVAILABLE:
                        retry_pbar = tqdm(
                            total=len(failures),
                            desc=f"Retrying {len(failures)} failures",
                            unit="retry",
                            leave=True  # Keep retry bar visible after completion
                        )
                    else:
                        logger.info(f"Retrying {len(failures)} failed downloads with longer delays...")
                    
                    time.sleep(self.delay_between_batches * 2)  # Longer delay before retries
                    
                    try:
                        for i, result in enumerate(failures, 1):
                            logger.info(f"Retry {i}/{len(failures)}: {result.identifier} (original error: {result.error_reason})")
                            if retry_pbar:
                                retry_pbar.set_postfix_str(f"{i}/{len(failures)}: {result.identifier[:40]}...")
                                retry_pbar.refresh()  # Force refresh before download
                            
                            # Temporarily suppress Cloudflare logging during retries
                            # (Cloudflare was already logged during initial attempt)
                            with self._suppress_cloudflare_logging():
                                retry_result = self.download(result.identifier)
                            
                            logger.info(f"Retry {i}/{len(failures)} result: {result.identifier} -> {retry_result.status.value}")
                            if retry_result.status == DownloadStatus.SUCCESS:
                                logger.info(f"✓ Retry succeeded for {result.identifier}")
                            else:
                                logger.info(f"✗ Retry still failed for {result.identifier}: {retry_result.error_reason}")
                            
                            # Update the original result
                            result.status = retry_result.status
                            result.error_reason = retry_result.error_reason
                            result.pdf_path = retry_result.pdf_path
                            result.last_successful = retry_result.last_successful
                            
                            if retry_pbar:
                                # Use retry_result.status (the new status from the retry attempt)
                                status_emoji = {
                                    DownloadStatus.SUCCESS: "✓",
                                    DownloadStatus.FAILURE: "✗",
                                    DownloadStatus.PAYWALL: "🔒",
                                }.get(retry_result.status, "?")
                                retry_pbar.set_postfix_str(f"{status_emoji} {retry_result.status.value}")
                                retry_pbar.update(1)
                                retry_pbar.refresh()  # Force refresh in notebooks
                                # Force stdout flush for Jupyter
                                sys.stdout.flush()
                            
                            time.sleep(self.delay_between_requests * 2)  # Longer delay for retries
                    finally:
                        if retry_pbar:
                            retry_pbar.close()
                    
                    # Log retry summary (check updated status after all retries)
                    retry_successes = sum(1 for r in failures if r.status == DownloadStatus.SUCCESS)
                    retry_failures = sum(1 for r in failures if r.status == DownloadStatus.FAILURE)
                    retry_paywalls = sum(1 for r in failures if r.status == DownloadStatus.PAYWALL)
                    logger.info(f"Retry summary: {retry_successes} succeeded, {retry_failures} still failed, {retry_paywalls} paywalled")
                    
                    # Log some example failure reasons for still-failed items
                    if retry_failures > 0:
                        still_failed = [r for r in failures if r.status == DownloadStatus.FAILURE]
                        example_errors = [r.error_reason[:100] if r.error_reason else "No error reason" for r in still_failed[:5]]
                        logger.info(f"Example retry failure reasons: {example_errors}")
                else:
                    logger.info("No failures to retry")
            else:
                logger.info("Retry disabled (retry_failures=False)")
            
            # Clean up domain-specific drivers
            self._cleanup_domain_drivers()
        
        except KeyboardInterrupt:
            logger.warning("=" * 60)
            logger.warning("INTERRUPTED BY USER (KeyboardInterrupt)")
            logger.warning("=" * 60)
            logger.warning("Cleaning up resources (Selenium drivers, etc.)...")
            # Clean up all drivers immediately
            self._cleanup_domain_drivers()
            if pbar:
                pbar.close()
            logger.warning("Cleanup complete. Execution stopped.")
            # Re-raise to properly stop execution
            raise
        finally:
            # Always clean up progress bar
            if pbar:
                pbar.close()
            # Note: We don't close drivers in finally because:
            # 1. If interrupted, we want to clean up immediately (done in except)
            # 2. If normal completion, drivers should remain open for potential reuse
            # 3. User should call fetcher.close() explicitly or use context manager
        
        # Summary
        success_count = sum(1 for r in results if r.status == DownloadStatus.SUCCESS)
        failure_count = sum(1 for r in results if r.status == DownloadStatus.FAILURE)
        already_exists = sum(1 for r in results if r.status == DownloadStatus.ALREADY_EXISTS)
        
        # Combine pre-filtered results with download results
        final_results = all_results + results
        
        success_count = sum(1 for r in final_results if r.status == DownloadStatus.SUCCESS)
        failure_count = sum(1 for r in final_results if r.status == DownloadStatus.FAILURE)
        already_exists = sum(1 for r in final_results if r.status == DownloadStatus.ALREADY_EXISTS)
        
        logger.info(f"Batch download complete: {success_count} succeeded, {already_exists} already existed, {failure_count} failed")
        
        # Try to create summary log (handle case where config might not be available)
        try:
            # Try to get log directory from config if available
            log_dir = None
            if hasattr(self, 'config') and self.config:
                log_dir = getattr(self.config, 'log_dir', None)
            
            # If no config, use pdf_dir as fallback
            if not log_dir:
                log_dir = self.pdf_dir
            
            summary_file = create_download_summary_log(final_results, log_dir)
            logger.info(f"Download summary saved to: {summary_file}")
        except Exception as e:
            logger.debug(f"Could not create summary log: {e}")
        
        return final_results


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    fetcher = PDFFetcher(pdf_dir="./pdfs", headless=False)
    
    # Test with a DOI
    result = fetcher.download("10.2138/am.2011.573")
    print(f"Status: {result.status.value}")
    print(f"PDF path: {result.pdf_path}")
    
    fetcher.close()

