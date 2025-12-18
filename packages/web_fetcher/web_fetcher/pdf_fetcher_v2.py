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
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin, urlparse
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
        # Strategy 1: Publisher-specific (e.g., ScienceDirect PII extraction)
        if publisher == 'elsevier':
            pdf_url = self._try_sciencedirect_direct(landing_url)
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
            
            button_texts = ['download pdf', 'view pdf', 'pdf', 'download', 'get pdf']
            
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
                    logger.info(f"Trying Selenium fallback for {response.status_code} response...")
                    return self._download_with_selenium(pdf_url, output_path, selenium_driver, referer)
                
                # If no Selenium or not 403/401, raise error
                response.raise_for_status()
            
            # Normal download
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temp file first
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp_file.write(chunk)
            
            # Verify PDF header
            header = tmp_path.read_bytes()[:4]
            if header != b'%PDF':
                logger.error(f"Downloaded file is not a valid PDF (header: {header})")
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
            header = output_path.read_bytes()[:4]
            if header == b'%PDF':
                logger.info(f"Downloaded PDF via Selenium+requests: {output_path.stat().st_size} bytes")
                return True
            else:
                logger.error(f"Downloaded file is not a valid PDF (header: {header})")
                output_path.unlink()
                return False
            
        except Exception as e:
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


class PDFFetcher:
    """
    Main PDF fetcher class following the specification.
    """
    
    def __init__(
        self,
        pdf_dir: Union[str, Path] = "./pdfs",
        metadata_path: Union[str, Path] = "./pdfs/metadata.json",
        headless: bool = True,
        requests_per_second: float = 1.0,
        max_retries: int = 3,
        user_agent: Optional[str] = None,
        selenium_download_dir: Optional[Union[str, Path]] = None,
        delay_between_requests: float = 2.0,
        delay_between_batches: float = 10.0
    ):
        """
        Initialize PDF fetcher.
        
        Args:
            pdf_dir: Directory to store PDFs
            metadata_path: Path to metadata JSON file
            headless: Run browser in headless mode
            requests_per_second: Rate limit per domain
            max_retries: Max retry attempts for network errors
            user_agent: Custom user agent string
            selenium_download_dir: Directory for Selenium browser downloads (defaults to temp dir)
            delay_between_requests: Delay in seconds between individual requests (helps avoid Cloudflare)
            delay_between_batches: Delay in seconds between batches (for batch processing)
        """
        self.pdf_dir = Path(pdf_dir)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata_path = Path(metadata_path)
        self.metadata_store = MetadataStore(self.metadata_path)
        
        self.headless = headless
        self.max_retries = max_retries
        self.rate_limiter = RateLimiter(requests_per_second)
        self.delay_between_requests = delay_between_requests
        self.delay_between_batches = delay_between_batches
        
        # Setup Selenium download directory
        if selenium_download_dir:
            self.selenium_download_dir = Path(selenium_download_dir).resolve()
            self._selenium_download_dir_is_temp = False
        else:
            # Use a temp directory for Selenium downloads
            self.selenium_download_dir = Path(tempfile.mkdtemp(prefix='selenium_downloads_')).resolve()
            self._selenium_download_dir_is_temp = True
        self.selenium_download_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Selenium download directory: {self.selenium_download_dir} (temp: {self._selenium_download_dir_is_temp})")
        
        # Setup requests session
        self.session = requests.Session()
        if user_agent:
            self.user_agent = user_agent
        else:
            self.user_agent = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        self.session.headers.update({'User-Agent': self.user_agent})
        
        # Setup retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Selenium driver (lazy initialization)
        self._driver: Optional[webdriver.Chrome] = None
        self._driver_initialized = False
        
        # Components
        self.doi_resolver = DOIResolver(self.session, self.rate_limiter)
        self.download_manager = DownloadManager(self.session, self.rate_limiter, self.selenium_download_dir)
        
        # Optional Crossref support (for direct PDF URL lookup)
        self.crossref_fetcher = None
        if CROSSREF_AVAILABLE:
            try:
                self.crossref_fetcher = CrossrefBibliographicFetcher()
                logger.info("Crossref support enabled - will try Crossref for PDF URLs first")
            except Exception as e:
                logger.warning(f"Could not initialize Crossref fetcher: {e} - will skip Crossref lookup")
                self.crossref_fetcher = None
    
    def _get_driver(self) -> webdriver.Chrome:
        """Get or create Selenium driver."""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is not available")
        
        if not self._driver_initialized:
            options = ChromeOptions()
            if self.headless:
                options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument(f'--user-agent={self.user_agent}')
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
            
            self._driver = webdriver.Chrome(options=options)
            self._driver_initialized = True
            logger.info(f"Selenium driver initialized with download directory: {self.selenium_download_dir}")
        
        return self._driver
    
    def _is_cloudflare_challenge(self, driver) -> bool:
        """Check if current page is a Cloudflare challenge."""
        try:
            page_source = driver.page_source.lower()
            title = driver.title.lower()
            
            # Check for manual CAPTCHA checkbox
            has_checkbox = (
                'i am human' in page_source or
                'i\'m not a robot' in page_source or
                'verify you are human' in page_source or
                'cf-challenge' in page_source or
                'challenge-platform' in page_source
            )
            
            # Check for "Just a moment" page
            is_just_moment = 'just a moment' in title or 'just a moment' in page_source[:2000]
            
            # Check for challenge widgets
            has_challenge_widget = (
                'cf-chl-widget' in page_source or
                'cf-turnstile' in page_source
            )
            
            return has_checkbox or is_just_moment or has_challenge_widget
        except:
            return False
    
    def _close_driver(self):
        """Close Selenium driver."""
        if self._driver and self._driver_initialized:
            try:
                self._driver.quit()
            except:
                pass
            self._driver = None
            self._driver_initialized = False
        
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
            
            # Check if already exists
            if pdf_path.exists():
                # Verify it's a valid PDF
                try:
                    header = pdf_path.read_bytes()[:4]
                    if header == b'%PDF':
                        result.status = DownloadStatus.ALREADY_EXISTS
                        result.pdf_path = pdf_path
                        result.last_successful = datetime.utcnow().isoformat()
                        self.metadata_store.update(result)
                        logger.info(f"PDF already exists: {pdf_path}")
                        return result
                except:
                    pass  # File might be corrupted, re-download
            
            # Resolve to landing URL
            try:
                if kind in ('doi', 'doi_url'):
                    # Try requests first
                    try:
                        landing_url = self.doi_resolver.resolve(url, use_selenium=False)
                    except:
                        # Fall back to Selenium
                        driver = self._get_driver()
                        landing_url = self.doi_resolver.resolve(url, use_selenium=True, selenium_driver=driver)
                else:
                    landing_url = url
                
                result.landing_url = landing_url
            except Exception as e:
                result.status = DownloadStatus.INVALID_IDENTIFIER
                result.error_reason = f"Failed to resolve identifier: {e}"
                self.metadata_store.update(result)
                return result
            
            # Detect publisher
            publisher = PublisherDetector.detect(landing_url)
            result.publisher = publisher
            
            # Strategy 1: Try Crossref for direct PDF URL (if DOI and Crossref available)
            pdf_url = None
            if kind in ('doi', 'doi_url') and self.crossref_fetcher and doi:
                try:
                    logger.info(f"Trying Crossref for PDF URL: {doi}")
                    metadata = self.crossref_fetcher.fetch_by_doi(doi)
                    if metadata:
                        pdf_url = CrossrefPDFExtractor.extract_pdf_url(metadata)
                        if pdf_url:
                            logger.info(f"✓ Found PDF URL via Crossref: {pdf_url}")
                            # Use the Crossref PDF URL directly - bypass landing page
                            result.landing_url = landing_url  # Keep original landing URL for reference
                            # Skip landing page navigation - proceed directly to download
                        else:
                            logger.debug("Crossref metadata found but no PDF URL available")
                    else:
                        logger.debug("Crossref did not return metadata for this DOI")
                except Exception as e:
                    logger.debug(f"Crossref lookup failed: {e} - falling back to landing page")
                    pdf_url = None
            
            # Strategy 2: Find PDF URL from landing page (if Crossref didn't provide one)
            driver = None
            if not pdf_url:
                logger.info("Finding PDF URL from landing page...")
                driver = self._get_driver()
                driver.get(landing_url)
                time.sleep(2)  # Wait for page load
                
                # Check for Cloudflare challenge - if detected, log and skip
                if self._is_cloudflare_challenge(driver):
                    logger.warning("=" * 60)
                    logger.warning("CLOUDFLARE CHALLENGE DETECTED - SKIPPING")
                    logger.warning(f"Identifier: {identifier}")
                    logger.warning(f"Resource URL: {landing_url}")
                    logger.warning(f"Publisher: {publisher or 'unknown'}")
                    logger.warning("=" * 60)
                    
                    result.status = DownloadStatus.FAILURE
                    result.error_reason = f"Cloudflare challenge - Resource URL: {landing_url}, Publisher: {publisher or 'unknown'}"
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
                logger.debug("Using Crossref PDF URL - no landing page cookies available")
            
            success = self.download_manager.download(
                pdf_url, 
                pdf_path, 
                cookies=cookies,
                referer=landing_url if landing_url else None,  # Pass referer for watermarking services
                selenium_driver=driver_for_download  # Pass driver for Selenium fallback
            )
            
            if success:
                result.status = DownloadStatus.SUCCESS
                result.pdf_path = pdf_path
                result.last_successful = datetime.utcnow().isoformat()
            else:
                result.status = DownloadStatus.FAILURE
                result.error_reason = "Download failed or file is not a valid PDF"
            
            self.metadata_store.update(result)
            return result
            
        except Exception as e:
            logger.error(f"Error downloading PDF: {e}", exc_info=True)
            result.status = DownloadStatus.FAILURE
            result.error_reason = str(e)
            self.metadata_store.update(result)
            return result
    
    def download_batch(
        self, 
        identifiers: List[str], 
        batch_size: int = 10,
        retry_failures: bool = True
    ) -> List[DownloadResult]:
        """
        Download PDFs for multiple identifiers with batching and retry support.
        
        Args:
            identifiers: List of DOIs, DOI-URLs, or resource URLs
            batch_size: Number of downloads per batch (smaller = less likely to trigger Cloudflare)
            retry_failures: Whether to retry failed downloads at the end
        
        Returns:
            List of DownloadResult objects
        """
        results = []
        total = len(identifiers)
        
        logger.info(f"Starting batch download: {total} identifiers, batch size: {batch_size}")
        
        # Process in batches
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch = identifiers[batch_start:batch_end]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} items)")
            
            for i, identifier in enumerate(batch, 1):
                logger.info(f"[{batch_start + i}/{total}] Downloading: {identifier}")
                result = self.download(identifier)
                results.append(result)
                
                # Delay between requests within batch
                if i < len(batch):
                    time.sleep(self.delay_between_requests)
            
            # Delay between batches
            if batch_end < total:
                logger.info(f"Batch {batch_num} complete. Waiting {self.delay_between_batches}s before next batch...")
                time.sleep(self.delay_between_batches)
        
        # Retry failures if requested
        if retry_failures:
            failures = [r for r in results if r.status == DownloadStatus.FAILURE]
            if failures:
                logger.info(f"Retrying {len(failures)} failed downloads with longer delays...")
                time.sleep(self.delay_between_batches * 2)  # Longer delay before retries
                
                for result in failures:
                    logger.info(f"Retrying: {result.identifier}")
                    retry_result = self.download(result.identifier)
                    # Update the original result
                    result.status = retry_result.status
                    result.error_reason = retry_result.error_reason
                    result.pdf_path = retry_result.pdf_path
                    result.last_successful = retry_result.last_successful
                    time.sleep(self.delay_between_requests * 2)  # Longer delay for retries
        
        # Summary
        success_count = sum(1 for r in results if r.status == DownloadStatus.SUCCESS)
        failure_count = sum(1 for r in results if r.status == DownloadStatus.FAILURE)
        already_exists = sum(1 for r in results if r.status == DownloadStatus.ALREADY_EXISTS)
        
        logger.info(f"Batch download complete: {success_count} succeeded, {already_exists} already existed, {failure_count} failed")
        
        return results
    
    def close(self):
        """Close resources."""
        self._close_driver()
        self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    fetcher = PDFFetcher(pdf_dir="./pdfs", headless=False)
    
    # Test with a DOI
    result = fetcher.download("10.2138/am.2011.573")
    print(f"Status: {result.status.value}")
    print(f"PDF path: {result.pdf_path}")
    
    fetcher.close()

