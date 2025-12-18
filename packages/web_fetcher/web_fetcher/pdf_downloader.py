"""
PDF Downloader - Specialized web fetcher for downloading PDFs from DOIs.

This module provides a PDFDownloader class that extends SeleniumWebFetcher
to handle the complex process of resolving DOIs to PDF files, including:
- Publisher landing page navigation
- PDF link/button detection
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
    from .selenium_fetcher import SeleniumWebFetcher
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
            ],
            'button_texts': ['download pdf', 'view pdf', 'pdf'],
        },
        'elsevier': {
            'domains': ['sciencedirect.com', 'elsevier.com'],
            'pdf_selectors': [
                'a.download-pdf-link',
                'a[pdfurl]',
                'a[href*=".pdf"]',
                'a[data-pdf-url]',
                'button[data-pdf-url]',
                'a[href*="/science/article/pii/"]',
                'a[class*="download"]',
                'a[class*="pdf"]',
                'button[class*="download"]',
                'button[class*="pdf"]',
                'a[title*="PDF"]',
                'button[title*="PDF"]',
            ],
            'button_texts': ['download pdf', 'view pdf', 'pdf', 'get pdf', 'open pdf'],
        },
        'springer': {
            'domains': ['springer.com', 'link.springer.com'],
            'pdf_selectors': [
                'a.c-pdf-download__link',
                'a[href*="/content/pdf/"]',
            ],
            'button_texts': ['download pdf', 'view pdf', 'pdf'],
        },
        'wiley': {
            'domains': ['onlinelibrary.wiley.com'],
            'pdf_selectors': [
                'a.pdf-download',
                'a[href*=".pdf"]',
                'a[title*="PDF"]',
            ],
            'button_texts': ['download pdf', 'view pdf', 'pdf'],
        },
        'arxiv': {
            'domains': ['arxiv.org'],
            'pdf_selectors': [
                'a[href*="/pdf/"]',
            ],
            'button_texts': ['pdf'],
        },
        'plos': {
            'domains': ['plos.org', 'plosone.org', 'journals.plos.org'],
            'pdf_selectors': [
                'a[href*="manuscript?id="]',
                'a.download',
                'a[href*="/article/file?id="]',
                'a[href*=".pdf"]',
                'button[aria-label*="PDF"]',
                'a[aria-label*="PDF"]',
                'button[aria-label*="Download PDF"]',
                'a[aria-label*="Download PDF"]',
                'a[href*="/download"]',
                'button[class*="download"]',
                'a[class*="download"]',
            ],
            'button_texts': ['download pdf', 'view pdf', 'pdf'],
        },
        'ieee': {
            'domains': ['ieeexplore.ieee.org', 'ieee.org'],
            'pdf_selectors': [
                'a[href*="/pdf"]',
                'a.pdf',
                'button.pdf',
                'a[title*="PDF"]',
                'button[title*="PDF"]',
                'a[aria-label*="PDF"]',
                'button[aria-label*="PDF"]',
                'a[href*=".pdf"]',
                'button[class*="pdf"]',
                'a[class*="pdf"]',
                'a[href*="/document/"]',
            ],
            'button_texts': ['pdf', 'download pdf', 'view pdf'],
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
        # Clean DOI - remove trailing punctuation and whitespace
        # DOIs should be in format 10.xxxx/xxxxx
        doi = doi.strip()
        # Remove trailing punctuation (common when DOIs are copied from text)
        doi = re.sub(r'[.,;:!?)\]]+$', '', doi)
        # Remove leading punctuation
        doi = re.sub(r'^[.,;:!?(\[]+', '', doi)
        # Remove any whitespace
        doi = doi.strip()
        
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
    
    def _is_pdf_page(self, driver) -> bool:
        """
        Check if the current page is a PDF file.
        
        Args:
            driver: Selenium WebDriver instance
        
        Returns:
            True if current page is a PDF
        """
        try:
            # Check content-type via JavaScript
            try:
                content_type = driver.execute_script(
                    "return document.contentType || ''"
                )
                if content_type and 'application/pdf' in content_type.lower():
                    return True
            except Exception:
                pass
            
            # Check URL for PDF indicators
            current_url = driver.current_url.lower()
            if current_url.endswith('.pdf') or '.pdf?' in current_url:
                return True
            
            # Check if URL contains PDF indicators
            if '/pdf' in current_url or 'format=pdf' in current_url:
                return True
            
            # Check page source for PDF header
            try:
                page_source = driver.page_source
                # PDFs loaded in browser typically have very short HTML
                # and may contain PDF-specific markers
                if len(page_source) < 500 and (
                    '%pdf' in page_source[:100].lower() or
                    'application/pdf' in page_source.lower()
                ):
                    return True
            except Exception:
                pass
            
            return False
        except Exception as e:
            logger.debug(f"Error checking if page is PDF: {e}")
            return False
    
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
        
            # Try button text matching for all publishers
            if not pdf_url and 'button_texts' in config:
                button_texts = config['button_texts']
                logger.info(f"Trying button text matching for {publisher} with patterns: {button_texts}")
                
                try:
                    # Find all buttons and links on the page
                    all_elements = driver.find_elements(
                        By.XPATH,
                        "//button | //a | //*[@role='button']"
                    )
                    
                    for element in all_elements:
                        try:
                            # Get text from various sources
                            element_text = ""
                            # Try visible text (includes text from child elements)
                            try:
                                element_text = element.text.strip().lower()
                            except Exception:
                                pass
                            
                            # If no text, try getting text from child elements (for icon buttons with text in spans)
                            if not element_text:
                                try:
                                    child_texts = []
                                    # Check common child elements that might contain text
                                    for child_tag in ['span', 'div', 'i', 'svg', 'label']:
                                        try:
                                            children = element.find_elements(By.TAG_NAME, child_tag)
                                            for child in children:
                                                child_text = child.text.strip()
                                                if child_text:
                                                    child_texts.append(child_text.lower())
                                        except Exception:
                                            continue
                                    if child_texts:
                                        element_text = " ".join(child_texts)
                                except Exception:
                                    pass
                            
                            # Try aria-label if text is still empty
                            if not element_text:
                                try:
                                    element_text = element.get_attribute('aria-label') or ""
                                    element_text = element_text.strip().lower()
                                except Exception:
                                    pass
                            
                            # Try title attribute
                            if not element_text:
                                try:
                                    element_text = element.get_attribute('title') or ""
                                    element_text = element_text.strip().lower()
                                except Exception:
                                    pass
                            
                            # Try data attributes that might contain PDF URLs
                            pdf_data_url = None
                            for attr in ['data-pdf-url', 'data-href', 'data-url', 'data-link', 'data-pdf']:
                                try:
                                    pdf_data_url = element.get_attribute(attr)
                                    if pdf_data_url:
                                        break
                                except Exception:
                                    continue
                            
                            # Normalize element text for matching (remove extra whitespace, normalize case)
                            element_text_normalized = re.sub(r'\s+', ' ', element_text).strip()
                            
                            # Check if element text matches any button text pattern
                            for button_text in button_texts:
                                button_text_normalized = button_text.lower().strip()
                                # Try exact match, substring match, and word boundary match
                                if (button_text_normalized in element_text_normalized or
                                    element_text_normalized in button_text_normalized or
                                    any(word in element_text_normalized for word in button_text_normalized.split() if len(word) > 2)):
                                    logger.info(f"Found button/link with text matching '{button_text}': element_text='{element_text[:100]}' normalized='{element_text_normalized[:100]}'")
                                    
                                    # First check if there's a data attribute with PDF URL
                                    if pdf_data_url:
                                        pdf_url = urljoin(url, pdf_data_url)
                                        logger.info(f"Found PDF URL from data attribute: {pdf_url}")
                                        break
                                    
                                    # If it's a link, get the href
                                    if element.tag_name.lower() == 'a':
                                        href = element.get_attribute('href')
                                        if href:
                                            pdf_url = urljoin(url, href)
                                            logger.info(f"Found PDF URL from link: {pdf_url}")
                                            break
                                    # If it's a button, try clicking it
                                    else:
                                        try:
                                            # Get current window handles before clicking
                                            current_windows = driver.window_handles
                                            main_window = driver.current_window_handle
                                            
                                            # Quick check: skip if element is not displayed
                                            try:
                                                if not element.is_displayed():
                                                    logger.debug("Element is not displayed, skipping...")
                                                    continue
                                            except Exception:
                                                pass  # If we can't check, try anyway
                                            
                                            # Scroll element into view
                                            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
                                            time.sleep(0.5)
                                            
                                            # Check if button has onclick or data attributes that might contain PDF URL
                                            onclick = element.get_attribute('onclick') or ""
                                            if onclick and ('.pdf' in onclick.lower() or 'pdf' in onclick.lower()):
                                                # Try to extract URL from onclick
                                                url_match = re.search(r'["\']([^"\']*\.pdf[^"\']*)["\']', onclick, re.IGNORECASE)
                                                if url_match:
                                                    pdf_url = urljoin(url, url_match.group(1))
                                                    logger.info(f"Found PDF URL from onclick: {pdf_url}")
                                                    break
                                            
                                            # Try to click the button with multiple strategies
                                            clicked = False
                                            
                                            # Strategy 1: Wait for element to be clickable, then regular click
                                            try:
                                                wait = WebDriverWait(driver, 3)  # Reduced timeout
                                                wait.until(EC.element_to_be_clickable(element))
                                                element.click()
                                                clicked = True
                                                logger.info("Clicked button using regular click")
                                            except Exception as e1:
                                                # Strategy 2: JavaScript click (works even if element is not "clickable")
                                                try:
                                                    driver.execute_script("arguments[0].click();", element)
                                                    clicked = True
                                                    logger.info("Clicked button using JavaScript click")
                                                except Exception as e2:
                                                    # Both failed, skip this element
                                                    logger.debug(f"Could not click element (regular: {type(e1).__name__}, JS: {type(e2).__name__}), skipping...")
                                                    continue  # Skip immediately, don't try to process further
                                            
                                            if not clicked:
                                                logger.debug("Button click did not register, skipping...")
                                                continue
                                            
                                            logger.info("Button clicked, waiting for navigation...")
                                            time.sleep(3)  # Wait longer for navigation/new tabs
                                            
                                            # Check if a new window/tab was opened
                                            new_windows = driver.window_handles
                                            if len(new_windows) > len(current_windows):
                                                # Switch to the new window
                                                for window in new_windows:
                                                    if window not in current_windows:
                                                        driver.switch_to.window(window)
                                                        new_url = driver.current_url
                                                        logger.info(f"New window opened: {new_url}")
                                                        
                                                        # Check if it's a PDF
                                                        if '.pdf' in new_url.lower() or '/pdf' in new_url.lower() or self._is_pdf_page(driver):
                                                            pdf_url = new_url
                                                            logger.info(f"Found PDF in new window: {pdf_url}")
                                                            # Close the new window and switch back
                                                            driver.close()
                                                            driver.switch_to.window(main_window)
                                                            break
                                                        else:
                                                            # Not a PDF, close and continue
                                                            driver.close()
                                                            driver.switch_to.window(main_window)
                                                if pdf_url:
                                                    break
                                            
                                            # Check if URL changed to a PDF (same window)
                                            new_url = driver.current_url
                                            if new_url != url:
                                                # Check if it's a PDF URL
                                                if '.pdf' in new_url.lower() or '/pdf' in new_url.lower():
                                                    pdf_url = new_url
                                                    logger.info(f"Navigated to PDF URL: {pdf_url}")
                                                    break
                                                # Or check if current page is a PDF
                                                elif self._is_pdf_page(driver):
                                                    pdf_url = new_url
                                                    logger.info(f"Current page is PDF: {pdf_url}")
                                                    break
                                            
                                            # Check if PDF loaded in current page (some buttons load PDF inline)
                                            if self._is_pdf_page(driver):
                                                pdf_url = driver.current_url
                                                logger.info(f"PDF loaded in current page: {pdf_url}")
                                                break
                                                
                                        except Exception as e:
                                            logger.debug(f"Error clicking button: {e}")
                                            continue
                            
                            if pdf_url:
                                break
                        except Exception as e:
                            logger.debug(f"Error processing element: {e}")
                            continue
                    
                except Exception as e:
                    logger.debug(f"Button text matching failed for {publisher}: {e}")
        
        # Generic button text fallback (for publishers without button_texts or when publisher-specific matching failed)
        if not pdf_url:
            # Common button text patterns as fallback
            generic_button_texts = ['download pdf', 'view pdf', 'pdf', 'download', 'get pdf']
            logger.info("Trying generic button text matching as fallback...")
            
            try:
                # Find all buttons and links on the page
                all_elements = driver.find_elements(
                    By.XPATH,
                    "//button | //a | //*[@role='button']"
                )
                
                for element in all_elements:
                    try:
                        # Get text from various sources
                        element_text = ""
                        # Try visible text
                        try:
                            element_text = element.text.strip().lower()
                        except Exception:
                            pass
                        
                        # Try aria-label if text is empty
                        if not element_text:
                            try:
                                element_text = element.get_attribute('aria-label') or ""
                                element_text = element_text.strip().lower()
                            except Exception:
                                pass
                        
                        # Try title attribute
                        if not element_text:
                            try:
                                element_text = element.get_attribute('title') or ""
                                element_text = element_text.strip().lower()
                            except Exception:
                                pass
                        
                        # Try data attributes that might contain PDF URLs
                        pdf_data_url = None
                        for attr in ['data-pdf-url', 'data-href', 'data-url', 'data-link', 'data-pdf']:
                            try:
                                pdf_data_url = element.get_attribute(attr)
                                if pdf_data_url:
                                    break
                            except Exception:
                                continue
                        
                        # Normalize element text for matching (remove extra whitespace, normalize case)
                        element_text_normalized = re.sub(r'\s+', ' ', element_text).strip()
                        
                        # Check if element text matches any generic button text pattern
                        for button_text in generic_button_texts:
                            button_text_normalized = button_text.lower().strip()
                            # Try exact match, substring match, and word boundary match
                            if (button_text_normalized in element_text_normalized or
                                element_text_normalized in button_text_normalized or
                                any(word in element_text_normalized for word in button_text_normalized.split() if len(word) > 2)):
                                logger.info(f"Found button/link with text matching '{button_text}': {element_text[:50]}")
                                
                                # First check if there's a data attribute with PDF URL
                                if pdf_data_url:
                                    pdf_url = urljoin(url, pdf_data_url)
                                    logger.info(f"Found PDF URL from data attribute: {pdf_url}")
                                    break
                                
                                # If it's a link, get the href
                                if element.tag_name.lower() == 'a':
                                    href = element.get_attribute('href')
                                    if href:
                                        pdf_url = urljoin(url, href)
                                        logger.info(f"Found PDF URL from link: {pdf_url}")
                                        break
                                # If it's a button, try clicking it
                                else:
                                    try:
                                        # Get current window handles before clicking
                                        current_windows = driver.window_handles
                                        main_window = driver.current_window_handle
                                        
                                        # Quick check: skip if element is not displayed
                                        try:
                                            if not element.is_displayed():
                                                logger.debug("Element is not displayed, skipping...")
                                                continue
                                        except Exception:
                                            pass  # If we can't check, try anyway
                                        
                                        # Scroll element into view
                                        driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
                                        time.sleep(0.5)
                                        
                                        # Check if button has onclick or data attributes that might contain PDF URL
                                        onclick = element.get_attribute('onclick') or ""
                                        if onclick and ('.pdf' in onclick.lower() or 'pdf' in onclick.lower()):
                                            # Try to extract URL from onclick
                                            url_match = re.search(r'["\']([^"\']*\.pdf[^"\']*)["\']', onclick, re.IGNORECASE)
                                            if url_match:
                                                pdf_url = urljoin(url, url_match.group(1))
                                                logger.info(f"Found PDF URL from onclick: {pdf_url}")
                                                break
                                        
                                        # Try to click the button with multiple strategies
                                        clicked = False
                                        
                                        # Strategy 1: Wait for element to be clickable, then regular click
                                        try:
                                            wait = WebDriverWait(driver, 3)  # Reduced timeout
                                            wait.until(EC.element_to_be_clickable(element))
                                            element.click()
                                            clicked = True
                                            logger.info("Clicked button using regular click")
                                        except Exception as e1:
                                            # Strategy 2: JavaScript click (works even if element is not "clickable")
                                            try:
                                                driver.execute_script("arguments[0].click();", element)
                                                clicked = True
                                                logger.info("Clicked button using JavaScript click")
                                            except Exception as e2:
                                                # Both failed, skip this element
                                                logger.debug(f"Could not click element (regular: {type(e1).__name__}, JS: {type(e2).__name__}), skipping...")
                                                continue  # Skip immediately, don't try to process further
                                        
                                        if not clicked:
                                            logger.debug("Button click did not register, skipping...")
                                            continue
                                        
                                        logger.info("Button clicked, waiting for navigation...")
                                        time.sleep(3)  # Wait longer for navigation/new tabs
                                        
                                        # Check if a new window/tab was opened
                                        new_windows = driver.window_handles
                                        if len(new_windows) > len(current_windows):
                                            # Switch to the new window
                                            for window in new_windows:
                                                if window not in current_windows:
                                                    driver.switch_to.window(window)
                                                    new_url = driver.current_url
                                                    logger.info(f"New window opened: {new_url}")
                                                    
                                                    # Check if it's a PDF
                                                    if '.pdf' in new_url.lower() or '/pdf' in new_url.lower() or self._is_pdf_page(driver):
                                                        pdf_url = new_url
                                                        logger.info(f"Found PDF in new window: {pdf_url}")
                                                        # Close the new window and switch back
                                                        driver.close()
                                                        driver.switch_to.window(main_window)
                                                        break
                                                    else:
                                                        # Not a PDF, close and continue
                                                        driver.close()
                                                        driver.switch_to.window(main_window)
                                            if pdf_url:
                                                break
                                        
                                        # Check if URL changed to a PDF (same window)
                                        new_url = driver.current_url
                                        if new_url != url:
                                            # Check if it's a PDF URL
                                            if '.pdf' in new_url.lower() or '/pdf' in new_url.lower():
                                                pdf_url = new_url
                                                logger.info(f"Navigated to PDF URL: {pdf_url}")
                                                break
                                            # Or check if current page is a PDF
                                            elif self._is_pdf_page(driver):
                                                pdf_url = new_url
                                                logger.info(f"Current page is PDF: {pdf_url}")
                                                break
                                        
                                        # Check if PDF loaded in current page (some buttons load PDF inline)
                                        if self._is_pdf_page(driver):
                                            pdf_url = driver.current_url
                                            logger.info(f"PDF loaded in current page: {pdf_url}")
                                            break
                                            
                                    except Exception as e:
                                        logger.debug(f"Error clicking button: {e}")
                                        continue
                        
                        if pdf_url:
                            break
                    except Exception as e:
                        logger.debug(f"Error processing element: {e}")
                        continue
                
            except Exception as e:
                logger.debug(f"Generic button text matching failed: {e}")
        
        # Generic PDF link detection - also check page source for PDF URLs
        if not pdf_url:
            # Look for links with .pdf extension
            try:
                pdf_links = driver.find_elements(
                    By.CSS_SELECTOR,
                    'a[href*=".pdf"], a[href*="/pdf/"], a[href*="pdf"]'
                )
                
                for link in pdf_links:
                    href = link.get_attribute('href')
                    text = link.text.lower()
                    
                    # Prefer links with "download" or "pdf" in text
                    if href and ('download' in text or 'pdf' in text):
                        pdf_url = urljoin(url, href)
                        logger.info(f"Found PDF link via generic detection: {pdf_url}")
                        break
                
                # If no preferred link, take first .pdf link
                if not pdf_url and pdf_links:
                    href = pdf_links[0].get_attribute('href')
                    if href:
                        pdf_url = urljoin(url, href)
                        logger.info(f"Found PDF link (first match): {pdf_url}")
                        
            except NoSuchElementException:
                pass
            
            # Last resort: Search page source for PDF URLs
            if not pdf_url:
                logger.info("Trying to find PDF URL in page source...")
                try:
                    page_source = driver.page_source
                    logger.debug(f"Page source length: {len(page_source)} characters")
                    
                    # Extract PII from ScienceDirect URLs
                    pii_match = re.search(r'/science/article/pii/([A-Z0-9]+)', url, re.IGNORECASE)
                    if pii_match:
                        pii = pii_match.group(1)
                        # ScienceDirect PDF URL format
                        pdf_url = f"https://www.sciencedirect.com/science/article/pii/{pii}/pdfft?isDTMRedir=true&download=true"
                        logger.info(f"Constructed ScienceDirect PDF URL from PII in landing URL: {pdf_url}")
                    else:
                        # Look for PDF URLs in the HTML
                        pdf_url_patterns = [
                            (r'href=["\']([^"\']*\.pdf[^"\']*)["\']', 'href with .pdf'),
                            (r'["\']([^"\']*\/pdf\/[^"\']*)["\']', 'path with /pdf/'),
                            (r'data-pdf-url=["\']([^"\']*)["\']', 'data-pdf-url'),
                            (r'pdfurl=["\']([^"\']*)["\']', 'pdfurl attribute'),
                            (r'["\']([^"\']*\/science\/article\/pii\/[^"\']*\/pdfft[^"\']*)["\']', 'ScienceDirect PDF link'),
                            (r'\/science\/article\/pii\/([A-Z0-9]+)', 'ScienceDirect PII pattern'),
                        ]
                        
                        for pattern, desc in pdf_url_patterns:
                            matches = re.findall(pattern, page_source, re.IGNORECASE)
                            logger.debug(f"Pattern '{desc}' found {len(matches)} matches")
                            for match in matches[:5]:  # Check first 5 matches
                                if isinstance(match, tuple):
                                    match = match[0] if match else ""
                                if match and ('pdf' in match.lower() or match.endswith('.pdf') or '/pdfft' in match.lower()):
                                    if '/pdfft' in match.lower() or 'pdfft' in match.lower():
                                        pdf_url = urljoin(url, match) if not match.startswith('http') else match
                                        logger.info(f"Found PDF URL in page source ({desc}): {pdf_url}")
                                        break
                                elif match and len(match) > 5:  # Potential PII
                                    # Try constructing ScienceDirect PDF URL
                                    pdf_url = f"https://www.sciencedirect.com/science/article/pii/{match}/pdfft?isDTMRedir=true&download=true"
                                    logger.info(f"Constructed ScienceDirect PDF URL from PII ({desc}): {pdf_url}")
                                    break
                            if pdf_url:
                                break
                except Exception as e:
                    logger.warning(f"Error searching page source: {e}", exc_info=True)
        
        # Look for PDF buttons
        if not pdf_url:
            # logger.info(f"No PDF link found, looking for buttons")
            # logger.info(f"{driver is None}: Driver is None")
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
            logger.info(f"Downloading PDF from: {pdf_url}")
            
            # Transfer cookies from Selenium driver to requests session
            # This is important for sites that require authentication cookies
            if fetcher.driver is not None:
                try:
                    selenium_cookies = fetcher.driver.get_cookies()
                    for cookie in selenium_cookies:
                        # Convert Selenium cookie format to requests cookie format
                        fetcher.session.cookies.set(
                            cookie['name'],
                            cookie['value'],
                            domain=cookie.get('domain', ''),
                            path=cookie.get('path', '/')
                        )
                    if selenium_cookies:
                        logger.debug(f"Transferred {len(selenium_cookies)} cookies from Selenium to requests session")
                except Exception as e:
                    logger.warning(f"Could not transfer cookies from Selenium: {e}")
            
            # Use requests session directly to get binary content
            # This is more reliable than fetch() which returns text
            # Allow redirects (default) and don't raise on status errors yet
            response = fetcher.session.get(
                pdf_url,
                stream=True,
                timeout=self.timeout,
                headers={'User-Agent': fetcher.user_agent} if fetcher.user_agent else {},
                allow_redirects=True  # Explicitly allow redirects
            )
            
            # For 403/401 errors, some servers still return PDF content
            # Check if response might be a PDF even with error status
            status_code = response.status_code
            if status_code >= 400:
                logger.warning(f"Got HTTP {status_code} for {pdf_url}, but checking if response body is PDF...")
                # Check if response body might be PDF (peek at first bytes)
                # Save response to temp location first to check
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            tmp_file.write(chunk)
                    tmp_path = Path(tmp_file.name)
                
                # Check if it's actually a PDF
                if tmp_path.stat().st_size >= 4:
                    header = tmp_path.read_bytes()[:4]
                    if header == b'%PDF':
                        logger.info(f"Got {status_code} but response body is PDF ({tmp_path.stat().st_size} bytes), proceeding...")
                        # Move temp file to output
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        tmp_path.rename(output_path)
                        logger.info(f"Downloaded {output_path.stat().st_size} bytes to {output_path}")
                        logger.info(f"PDF verified successfully: {output_path}")
                        return True
                
                # Not a PDF, clean up and return False
                tmp_path.unlink()
                logger.error(f"Got HTTP {status_code} and response is not a PDF (header: {tmp_path.read_bytes()[:20] if tmp_path.exists() else b'empty'})")
                return False
            
            # Normal case: status code is OK
            response.raise_for_status()
            
            # Check content-type
            content_type = response.headers.get('content-type', '').lower()
            if 'application/pdf' not in content_type:
                # Still try to save if URL suggests it's a PDF
                if not (pdf_url.lower().endswith('.pdf') or '.pdf?' in pdf_url.lower()):
                    logger.warning(f"Content-type is not PDF: {content_type} for URL: {pdf_url}")
                    # Don't return False yet - some servers don't set content-type correctly
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download PDF in chunks
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"Downloaded {output_path.stat().st_size} bytes to {output_path}")
            
            # Verify it's a PDF
            header = output_path.read_bytes()[:4]
            if header != b'%PDF':
                logger.error(f"Downloaded file is not a valid PDF (header: {header})")
                output_path.unlink()  # Delete invalid file
                return False
            
            logger.info(f"PDF verified successfully: {output_path}")
            return True
                
        except Exception as e:
            logger.error(f"Error downloading PDF from {pdf_url}: {e}", exc_info=True)
            if output_path.exists():
                output_path.unlink()
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
            logger.info(f"Resolved DOI to: {doi_url}")
            fetcher = self._get_fetcher()
            
            # For ScienceDirect (10.1016), try direct navigation to get PII
            if '10.1016' in doi or 'sciencedirect' in doi_url.lower():
                logger.info("Detected ScienceDirect DOI, navigating to extract PII...")
                # Ensure driver is initialized
                if not fetcher._driver_initialized:
                    fetcher._init_driver()
                
                # Clear any bad cache first
                try:
                    fetcher.clear_cache(doi_url)
                except Exception:
                    pass
                
                # Navigate directly (bypass cache)
                logger.info(f"Navigating directly to: {doi_url}")
                fetcher.driver.get(doi_url)
                time.sleep(5)  # Wait for page to load and redirect
                
                # Wait for page to actually load (check for empty page)
                page_source = fetcher.driver.page_source
                if len(page_source) < 100:
                    logger.warning("Page still empty after 5s, waiting longer...")
                    time.sleep(5)
                    page_source = fetcher.driver.page_source
                
                final_url = fetcher.driver.current_url
                logger.info(f"Final URL after navigation: {final_url}")
                
                # Extract PII from URL
                pii_match = re.search(r'/science/article/pii/([A-Z0-9]+)', final_url, re.IGNORECASE)
                if pii_match:
                    pii = pii_match.group(1)
                    pdf_url = f"https://www.sciencedirect.com/science/article/pii/{pii}/pdfft?isDTMRedir=true&download=true"
                    logger.info(f"Extracted PII: {pii}, constructed PDF URL: {pdf_url}")
                    
                    # Try downloading directly
                    if self._download_pdf(pdf_url, pdf_path):
                        result['success'] = True
                        result['pdf_path'] = pdf_path
                        result['status'] = 'success'
                        result['url'] = pdf_url
                        self._save_metadata(
                            doi=doi,
                            status='success',
                            url=pdf_url,
                            pdf_path=pdf_path
                        )
                        return result
                    else:
                        logger.warning(f"Direct PDF download from {pdf_url} failed, falling back to page detection...")
                else:
                    logger.warning(f"Could not extract PII from URL: {final_url}. Pattern '/science/article/pii/([A-Z0-9]+)' not found. Falling back to page detection...")
            
            # Navigate to landing page (use_selenium=True to ensure Selenium is used)
            # Force refresh to avoid bad cache entries
            page_result = fetcher.fetch(doi_url, use_selenium=True, force_refresh=True)
            
            if page_result['status_code'] != 200:
                raise PDFDownloadError(
                    f"Failed to load landing page: {page_result['status_code']}"
                )
            
            # Wait for page to actually load
            time.sleep(3)
            
            landing_url = fetcher.driver.current_url
            logger.info(f"Landing URL: {landing_url}")
            result['url'] = landing_url
            
            # Check if page actually loaded (not empty or data: URL)
            page_source = fetcher.driver.page_source
            if landing_url == 'data:,' or len(page_source) < 100 or page_source.strip() in ['<html><head></head><body></body></html>', '<html></html>']:
                logger.warning("Page appears to be empty or not loaded properly, trying to reload...")
                # Clear cache and reload
                try:
                    fetcher.clear_cache(doi_url)
                except Exception:
                    pass
                fetcher.driver.get(doi_url)
                time.sleep(5)  # Wait longer for page to load
                landing_url = fetcher.driver.current_url
                page_source = fetcher.driver.page_source
                logger.info(f"After reload - Landing URL: {landing_url}, Page source length: {len(page_source)}")
                
                if len(page_source) < 100:
                    raise PDFDownloadError("Page failed to load properly - page source is empty")
            
            # Check for paywall
            page_text = fetcher.driver.page_source
            if self._detect_paywall(page_text):
                raise PaywallError("Content is behind paywall")
            
            # Detect publisher
            publisher = self._detect_publisher(landing_url)
            if publisher:
                logger.info(f"Detected publisher: {publisher}")
            else:
                logger.info("Publisher not detected, using generic PDF detection")
            
            # Wait a bit for dynamic content to load
            time.sleep(2)
            
            # Scroll down to ensure all content is loaded (some buttons load on scroll)
            try:
                fetcher.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1)
                fetcher.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
            except Exception:
                pass
            
            # Find PDF link
            logger.info("Searching for PDF link on page...")
            
            # Debug: Log all buttons and links on the page for troubleshooting
            try:
                all_buttons = fetcher.driver.find_elements(By.XPATH, "//button | //a | //*[@role='button']")
                logger.info(f"Found {len(all_buttons)} buttons/links on page")
                pdf_related = []
                for i, btn in enumerate(all_buttons[:100]):  # Check more elements
                    try:
                        btn_text = btn.text.strip()[:100] if btn.text else ""
                        btn_tag = btn.tag_name
                        btn_href = btn.get_attribute('href') or ""
                        btn_aria = btn.get_attribute('aria-label') or ""
                        btn_title = btn.get_attribute('title') or ""
                        btn_class = btn.get_attribute('class') or ""
                        btn_id = btn.get_attribute('id') or ""
                        
                        # Check if this looks PDF-related
                        combined = f"{btn_text} {btn_aria} {btn_title} {btn_class} {btn_id}".lower()
                        if 'pdf' in combined or 'download' in combined or 'view' in combined:
                            pdf_related.append((i, btn_tag, btn_text, btn_href[:100], btn_aria[:100], btn_class[:50]))
                            logger.info(f"  PDF-RELATED [{i}] {btn_tag}: text='{btn_text}' href='{btn_href[:100]}' aria='{btn_aria[:100]}' class='{btn_class[:50]}'")
                    except Exception as e:
                        logger.debug(f"Error processing element {i}: {e}")
                        pass
                
                if not pdf_related:
                    logger.warning("No PDF-related buttons/links found on page")
                    # Log a few sample elements to help debug
                    logger.info("Sample elements on page (first 10):")
                    for i, btn in enumerate(all_buttons[:10]):
                        try:
                            btn_text = btn.text.strip()[:50] if btn.text else ""
                            btn_tag = btn.tag_name
                            btn_href = btn.get_attribute('href') or ""
                            logger.info(f"  [{i}] {btn_tag}: text='{btn_text}' href='{btn_href[:80]}'")
                        except Exception:
                            pass
                else:
                    logger.info(f"Found {len(pdf_related)} PDF-related elements")
            except Exception as e:
                logger.warning(f"Could not log page elements: {e}", exc_info=True)
            
            pdf_url = self._find_pdf_link(
                fetcher.driver,
                landing_url,
                publisher
            )
            
            if not pdf_url:
                logger.warning("Could not find PDF link on page")
                # Log page source snippet for debugging
                page_snippet = fetcher.driver.page_source[:500] if fetcher.driver.page_source else "No page source"
                logger.debug(f"Page source snippet: {page_snippet}")
                raise PDFNotFoundError("Could not find PDF link on page")
            
            # Validate that the URL looks like a PDF URL
            pdf_url_lower = pdf_url.lower()
            
            # Check if it's a ScienceDirect URL (these have special patterns)
            is_sciencedirect = 'sciencedirect.com' in pdf_url_lower
            
            # Reject obvious non-PDF URLs (homepages, etc.)
            is_invalid_url = (
                pdf_url_lower.endswith('/') and pdf_url_lower.count('/') <= 4 or  # Domain homepage
                pdf_url_lower.endswith('/index.html') or
                pdf_url_lower.endswith('/index') or
                (not is_sciencedirect and pdf_url_lower.count('/') <= 3)  # Too few path segments suggests homepage
            )
            
            # Check if it looks like a valid PDF URL
            is_valid_pdf_url = (
                pdf_url_lower.endswith('.pdf') or
                '/pdf' in pdf_url_lower or
                '/pdfft' in pdf_url_lower or
                'application/pdf' in pdf_url_lower or
                (is_sciencedirect and ('/pii/' in pdf_url_lower or '/pdfft' in pdf_url_lower or '/article/' in pdf_url_lower))
            )
            
            if is_invalid_url:
                logger.warning(f"Found URL appears to be a homepage or invalid: {pdf_url}")
                logger.warning("Rejecting and raising PDFNotFoundError.")
                raise PDFNotFoundError(f"Found URL appears to be invalid (homepage?): {pdf_url}")
            
            if not is_valid_pdf_url:
                logger.warning(f"Found URL does not appear to be a valid PDF URL: {pdf_url}")
                logger.warning("URL does not contain PDF indicators. Rejecting and raising PDFNotFoundError.")
                raise PDFNotFoundError(f"Found URL does not appear to be a valid PDF URL: {pdf_url}")
            
            logger.info(f"Found PDF URL: {pdf_url}")
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
            logger.warning(f"Paywall detected for DOI {doi}: {e}")
            result['error'] = str(e)
            result['status'] = 'paywall'
            self._save_metadata(
                doi=doi,
                status='paywall',
                url=result.get('url'),
                error=str(e)
            )
            
        except PDFNotFoundError as e:
            # Silently handle PDF not found - this is expected for some articles
            logger.debug(f"PDF not found for DOI {doi}: {e}")
            result['error'] = str(e)
            result['status'] = 'failure'
            self._save_metadata(
                doi=doi,
                status='failure',
                url=result.get('url'),
                error=str(e)
            )
            
        except PDFDownloadError as e:
            logger.warning(f"Download failed for DOI {doi}: {e}")
            result['error'] = str(e)
            result['status'] = 'failure'
            self._save_metadata(
                doi=doi,
                status='failure',
                url=result.get('url'),
                error=str(e)
            )
            
        except Exception as e:
            logger.error(f"Unexpected error downloading DOI {doi}: {e}", exc_info=True)
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
