"""
Extended web page fetcher with Selenium support for JavaScript rendering and CAPTCHA handling.

This module extends the basic WebPageFetcher with Selenium capabilities for cases
where JavaScript rendering is needed or CAPTCHAs must be handled.
"""

import logging
import time
import random
from pathlib import Path
from typing import Optional, Dict, Any, Union, Literal

from .core import WebPageFetcher

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    import undetected_chromedriver as uc
    UNDETECTED_CHROMEDRIVER_AVAILABLE = True
except ImportError:
    UNDETECTED_CHROMEDRIVER_AVAILABLE = False


logger = logging.getLogger(__name__)


class CloudflareRateLimitError(Exception):
    """Exception raised when Cloudflare rate limiting is detected."""
    pass


class SeleniumWebFetcher(WebPageFetcher):
    """
    Extended web page fetcher with Selenium support.
    
    This class extends WebPageFetcher to add Selenium-based fetching for pages
    that require JavaScript rendering or have CAPTCHAs. It maintains the same
    caching and retry logic as the base class.
    
    Parameters
    ----------
    use_selenium : bool, optional
        Whether to use Selenium by default. Default is False (use requests).
    headless : bool, optional
        Run browser in headless mode. Default is True.
    browser : {'chrome', 'firefox'}, optional
        Which browser to use with Selenium. Default is 'chrome'.
    executable_path : str or Path, optional
        Path to browser driver executable. If None, assumes driver is in PATH.
    wait_timeout : int, optional
        Maximum time to wait for page elements in seconds. Default is 10.
    page_load_wait : float, optional
        Time to wait after page load for dynamic content. Default is 2.0.
        Set to 0 to disable for faster operation when content is cached.
    use_undetected : bool, optional
        Use undetected-chromedriver instead of standard ChromeDriver. This can help
        bypass some bot detection. Requires: pip install undetected-chromedriver.
        Default is False.
    random_wait_min : float, optional
        Minimum random wait time in seconds between requests. Default is 0.0.
        Only used if random_wait_max > 0.
    random_wait_max : float, optional
        Maximum random wait time in seconds between requests. Default is 0.0.
        If > 0, adds a random wait between min and max before each request to
        avoid rate limiting. Example: random_wait_min=1.0, random_wait_max=3.0
        will wait 1-3 seconds randomly before each request.
    **kwargs
        Additional arguments passed to WebPageFetcher.__init__().
    """
    
    def __init__(
        self,
        use_selenium: bool = False,
        headless: bool = True,
        browser: Literal['chrome', 'firefox'] = 'chrome',
        executable_path: Optional[Union[str, Path]] = None,
        wait_timeout: int = 10,
        page_load_wait: float = 2.0,
        use_undetected: bool = False,
        random_wait_min: float = 0.0,
        random_wait_max: float = 0.0,
        **kwargs
    ):
        if use_selenium and not SELENIUM_AVAILABLE:
            raise ImportError(
                "Selenium is not installed. Install it with: pip install selenium"
            )
        
        if use_undetected and not UNDETECTED_CHROMEDRIVER_AVAILABLE:
            raise ImportError(
                "undetected-chromedriver is not installed. Install it with: pip install undetected-chromedriver"
            )
        
        super().__init__(**kwargs)
        
        self.use_selenium = use_selenium
        self.headless = headless
        self.browser = browser
        self.executable_path = executable_path
        self.wait_timeout = wait_timeout
        self.page_load_wait = page_load_wait
        self.use_undetected = use_undetected
        self.random_wait_min = random_wait_min
        self.random_wait_max = random_wait_max
        
        self.driver = None
        self._driver_initialized = False
        # Don't initialize driver here - do it lazily when needed
        # if self.use_selenium:
        #     self._init_driver()
    
    def _init_driver(self) -> None:
        """Initialize Selenium WebDriver (lazy initialization)."""
        if self._driver_initialized:
            return  # Already initialized
            
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is not installed")
        
        try:
            if self.browser == 'chrome':
                # Use undetected-chromedriver if requested
                if self.use_undetected:
                    if not UNDETECTED_CHROMEDRIVER_AVAILABLE:
                        raise ImportError("undetected-chromedriver is not installed")
                    
                    options = uc.ChromeOptions()
                    
                    if self.headless:
                        options.add_argument('--headless=new')
                    
                    # Common options for better compatibility
                    options.add_argument('--no-sandbox')
                    options.add_argument('--disable-dev-shm-usage')
                    options.add_argument(f'--user-agent={self.user_agent}')
                    options.add_argument('--window-size=1920,1080')
                    
                    # Set cookie preferences
                    prefs = {
                        'profile.default_content_setting_values.notifications': 2,
                        'profile.default_content_setting_values.cookies': 1,
                        'profile.cookie_controls_mode': 0,
                    }
                    options.add_experimental_option('prefs', prefs)
                    
                    # Use undetected-chromedriver
                    # Note: undetected-chromedriver may have different behavior
                    try:
                        self.driver = uc.Chrome(options=options, version_main=None)
                        # Navigate to blank page first to ensure clean state
                        # This prevents any initialization quirks from showing up
                        try:
                            self.driver.get("about:blank")
                        except Exception as e:
                            logger.debug(f"Could not navigate to about:blank after initialization: {e}")
                        logger.info("Initialized undetected Chrome WebDriver")
                    except Exception as e:
                        logger.error(f"Failed to initialize undetected-chromedriver: {e}")
                        logger.info("Falling back to standard ChromeDriver...")
                        # Fallback to standard ChromeDriver
                        self.use_undetected = False
                        options = Options()
                        if self.headless:
                            options.add_argument('--headless=new')
                        options.add_argument('--no-sandbox')
                        options.add_argument('--disable-dev-shm-usage')
                        options.add_argument('--disable-blink-features=AutomationControlled')
                        options.add_argument(f'user-agent={self.user_agent}')
                        options.add_argument('--disable-web-security')
                        options.add_argument('--disable-features=IsolateOrigins,site-per-process')
                        options.add_argument('--window-size=1920,1080')
                        options.add_experimental_option("excludeSwitches", ["enable-automation"])
                        options.add_experimental_option('useAutomationExtension', False)
                        prefs = {
                            'profile.default_content_setting_values.notifications': 2,
                            'profile.default_content_setting_values.cookies': 1,
                            'profile.cookie_controls_mode': 0,
                        }
                        options.add_experimental_option('prefs', prefs)
                        self.driver = webdriver.Chrome(options=options)
                        logger.info("Initialized standard Chrome WebDriver (fallback)")
                    
                else:
                    # Standard Selenium Chrome setup
                    options = Options()
                    
                    if self.headless:
                        options.add_argument('--headless=new')
                    
                    # Common options for better compatibility
                    options.add_argument('--no-sandbox')
                    options.add_argument('--disable-dev-shm-usage')
                    options.add_argument('--disable-blink-features=AutomationControlled')
                    options.add_argument(f'user-agent={self.user_agent}')
                    
                    # Additional options to avoid detection
                    options.add_argument('--disable-web-security')
                    options.add_argument('--disable-features=IsolateOrigins,site-per-process')
                    options.add_argument('--window-size=1920,1080')  # Set realistic window size
                    options.add_experimental_option("excludeSwitches", ["enable-automation"])
                    options.add_experimental_option('useAutomationExtension', False)
                    
                    # Set a realistic viewport and cookie preferences
                    prefs = {
                        'profile.default_content_setting_values.notifications': 2,
                        'profile.default_content_setting_values.cookies': 1,  # Allow all cookies
                        'profile.cookie_controls_mode': 0,  # Allow all cookies (bypass cookie controls)
                    }
                    options.add_experimental_option('prefs', prefs)
                    
                    # Disable images and CSS for faster loading (optional)
                    # prefs = {
                    #     'profile.managed_default_content_settings.images': 2,
                    #     'profile.managed_default_content_settings.stylesheets': 2,
                    # }
                    # options.add_experimental_option('prefs', prefs)
                    
                    if self.executable_path:
                        service = Service(executable_path=str(self.executable_path))
                        self.driver = webdriver.Chrome(service=service, options=options)
                    else:
                        self.driver = webdriver.Chrome(options=options)
                    
                    # Remove webdriver property to avoid detection
                    self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                        'source': '''
                            Object.defineProperty(navigator, 'webdriver', {
                                get: () => undefined
                            });
                            window.navigator.chrome = {
                                runtime: {}
                            };
                            Object.defineProperty(navigator, 'plugins', {
                                get: () => [1, 2, 3, 4, 5]
                            });
                            Object.defineProperty(navigator, 'languages', {
                                get: () => ['en-US', 'en']
                            });
                        '''
                    })
                
            elif self.browser == 'firefox':
                from selenium.webdriver.firefox.options import Options as FirefoxOptions
                from selenium.webdriver.firefox.service import Service as FirefoxService
                
                options = FirefoxOptions()
                
                if self.headless:
                    options.add_argument('--headless')
                
                options.set_preference('general.useragent.override', self.user_agent)
                
                if self.executable_path:
                    service = FirefoxService(executable_path=str(self.executable_path))
                    self.driver = webdriver.Firefox(service=service, options=options)
                else:
                    self.driver = webdriver.Firefox(options=options)
            
            else:
                raise ValueError(f"Unsupported browser: {self.browser}")
            
            # Set page load timeout
            self.driver.set_page_load_timeout(60)
            
            # Mark as initialized
            self._driver_initialized = True
            
            logger.info(f"Initialized {self.browser} WebDriver (headless={self.headless})")
            
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            self._driver_initialized = False
            raise
    
    def _log_cookie_button_info(self) -> None:
        """
        Log information about potential cookie consent buttons for debugging.
        """
        try:
            # Look for common cookie consent button patterns
            common_selectors = [
                (By.CLASS_NAME, 'osano-cm-acceptAll'),
                (By.CLASS_NAME, 'osano-cm-accept'),
                (By.CLASS_NAME, 'osano-cm-denyAll'),
                (By.CSS_SELECTOR, '[class*="cookie"]'),
                (By.CSS_SELECTOR, '[class*="accept"]'),
                (By.CSS_SELECTOR, 'button[id*="cookie"]'),
                (By.CSS_SELECTOR, 'button[id*="accept"]'),
            ]
            
            logger.debug("Searching for cookie consent buttons...")
            found_buttons = []
            for by, selector in common_selectors:
                try:
                    elements = self.driver.find_elements(by, selector)
                    if elements:
                        for elem in elements[:3]:  # Limit to first 3
                            text = elem.text or elem.get_attribute('textContent') or ''
                            classes = elem.get_attribute('class') or ''
                            elem_id = elem.get_attribute('id') or ''
                            found_buttons.append({
                                'selector': f"{by.__name__}: {selector}",
                                'text': text[:50],  # First 50 chars
                                'class': classes[:100],
                                'id': elem_id[:50]
                            })
                except Exception:
                    pass
            
            if found_buttons:
                logger.info(f"Found {len(found_buttons)} potential cookie buttons:")
                for btn in found_buttons:
                    logger.info(f"  - {btn['selector']} | text: '{btn['text']}' | class: '{btn['class']}' | id: '{btn['id']}'")
            else:
                logger.debug("No common cookie consent buttons found")
        except Exception as e:
            logger.debug(f"Error logging cookie button info: {e}")
    
    def _is_cloudflare_challenge(self) -> bool:
        """
        Check if current page is a Cloudflare challenge page.
        
        Returns
        -------
        bool
            True if Cloudflare challenge is detected, False otherwise.
        """
        try:
            page_source = self.driver.page_source.lower()
            title = self.driver.title.lower()
            current_url = self.driver.current_url.lower()
            
            # Check for "Just a moment..." page - this is a waiting page that auto-refreshes
            is_just_a_moment = (
                'just a moment' in title or
                'just a moment' in page_source[:2000]  # Check first 2k chars
            )
            
            if is_just_a_moment:
                # Check if it has auto-refresh meta tag (means it's waiting)
                if 'http-equiv="refresh"' in page_source or 'http-equiv=\'refresh\'' in page_source:
                    return True  # It's a waiting page, treat as challenge
            
            # Check for active challenge indicators (not just loading states)
            # The progress indicator means it's processing, not necessarily still a challenge
            has_challenge_text = (
                'verify you are human' in page_source or
                'checking your browser' in page_source or
                'www.science.org needs to review' in page_source
            )
            
            # Check for challenge platform/widget (but these might persist during loading)
            has_challenge_widget = (
                'challenge-platform' in page_source or
                'cf-chl-widget' in page_source or
                'cf-turnstile-response' in page_source
            )
            
            # Check for the loading/verifying state - this is transitional, not a challenge
            is_loading = (
                'loading-verifying' in page_source or
                'lds-ring' in page_source or  # Loading spinner
                'waiting for www.science.org to respond' in page_source
            )
            
            # If we're in loading state, it's processing - not a challenge anymore
            if is_loading:
                return False
            
            # If we have challenge text AND challenge widget, it's still a challenge
            if has_challenge_text and has_challenge_widget:
                return True
            
            # Also check if URL contains challenge parameters (but these might persist)
            if 'cf_chl' in current_url or '__cf_chl_tk' in current_url:
                # But if we also have real content indicators, it might be resolved
                if self._has_real_content_indicator():
                    return False
                return True
            
            return False
        except Exception:
            return False
    
    def _has_real_content_indicator(self) -> bool:
        """
        Quick check for indicators that real content is present.
        
        Returns
        -------
        bool
            True if there are signs of real content.
        """
        try:
            page_source = self.driver.page_source
            # Check for common Science.org content indicators
            return (
                len(page_source) > 100000 or  # Real pages are large
                'article' in page_source[:10000].lower() or
                'abstract' in page_source[:10000].lower() or
                'doi:' in page_source[:5000].lower() or
                'citation' in page_source[:10000].lower()
            )
        except Exception:
            return False
    
    def _has_real_content(self, url: str) -> bool:
        """
        Check if page has real content (not just a challenge page).
        
        Parameters
        ----------
        url : str
            Original URL that was requested.
        
        Returns
        -------
        bool
            True if page appears to have real content, False if it's still a challenge.
        """
        try:
            page_source = self.driver.page_source.lower()
            current_url = self.driver.current_url.lower()
            original_url = url.lower()
            
            # If we're on a different URL than requested (and it's not a challenge URL), likely resolved
            if current_url != original_url and 'cf_chl' not in current_url:
                # Check if new URL looks like the actual content
                if 'science.org' in current_url or 'doi.org' in current_url:
                    return True
            
            # Check for indicators of real Science.org content
            has_real_content = (
                'science.org' in current_url or
                'article' in page_source[:5000] or  # Check first 5k chars for article content
                'abstract' in page_source[:5000] or
                'doi.org' in current_url or
                len(page_source) > 50000  # Real pages are usually much larger than challenge pages
            )
            
            # Make sure it's NOT a challenge page
            is_challenge = self._is_cloudflare_challenge()
            
            return has_real_content and not is_challenge
        except Exception:
            return False
    
    def _wait_for_cloudflare_challenge(self, max_wait: int = 30) -> bool:
        """
        Wait for Cloudflare challenge to complete if present.
        
        Parameters
        ----------
        max_wait : int, optional
            Maximum time to wait for challenge to complete in seconds. Default is 30.
        
        Returns
        -------
        bool
            True if challenge was detected and may still be present, False otherwise.
        """
        try:
            # Cloudflare challenges are loaded via JavaScript after page load
            # They typically appear within 2-5 seconds, so we wait a bit before checking
            # This prevents false negatives where we check before the challenge appears
            time.sleep(3)  # Initial wait for CF challenge to appear
            
            # Check if we're on a Cloudflare challenge page
            if not self._is_cloudflare_challenge():
                # Double-check after a bit more time - CF challenges can be delayed
                # Some sites load them asynchronously
                time.sleep(3)
                if not self._is_cloudflare_challenge():
                    logger.debug("No Cloudflare challenge detected after waiting")
                    return False
            
            logger.info("Cloudflare challenge detected, waiting for completion...")
            
            # Check if it's a "Just a moment..." page (auto-refresh page)
            page_source = self.driver.page_source.lower()
            title = self.driver.title.lower()
            is_just_a_moment = 'just a moment' in title or 'just a moment' in page_source[:2000]
            
            if is_just_a_moment:
                logger.error("=" * 60)
                logger.error("CLOUDFLARE RATE LIMITING DETECTED")
                logger.error("'Just a moment...' page means too many requests too quickly.")
                logger.error("")
                logger.error("This page auto-refreshes after 360 seconds (6 minutes) - too long to wait.")
                logger.error("")
                logger.error("SOLUTION: Significantly increase wait times between requests:")
                logger.error(f"  Current: random_wait_min={getattr(self, 'random_wait_min', 0)}, random_wait_max={getattr(self, 'random_wait_max', 0)}")
                logger.error(f"  Recommended: random_wait_min=60.0, random_wait_max=120.0")
                logger.error("  (Or even higher: 120-180 seconds for 600+ requests)")
                logger.error("")
                logger.error("Alternative: Process in smaller batches (50-100 DOIs) with breaks.")
                logger.error("=" * 60)
                # Raise exception - rate limiting cannot be manually resolved
                raise CloudflareRateLimitError(
                    f"Cloudflare rate limiting detected. Increase wait times between requests. "
                    f"Current: random_wait_min={getattr(self, 'random_wait_min', 0)}, "
                    f"random_wait_max={getattr(self, 'random_wait_max', 0)}"
                )
            
            # Wait for challenge to complete
            # The progress indicator means Cloudflare is processing - we need to wait for it to finish
            start_time = time.time()
            initial_url = self.driver.current_url
            last_state = "challenge"
            
            while time.time() - start_time < max_wait:
                try:
                    current_url = self.driver.current_url
                    page_source = self.driver.page_source.lower()
                    
                    # Check for "Just a moment..." page - this is rate limiting
                    if is_just_a_moment:
                        # Check if it's still a "Just a moment..." page
                        current_title = self.driver.title.lower()
                        still_just_moment = 'just a moment' in current_title or 'just a moment' in page_source[:2000]
                        
                        if still_just_moment:
                            elapsed = time.time() - start_time
                            if elapsed < 60:
                                # Wait a bit to see if it resolves quickly
                                logger.debug(f"Waiting for 'Just a moment...' page (elapsed: {elapsed:.0f}s)...")
                                time.sleep(10)
                                continue
                            else:
                                # It's been more than a minute, this is rate limiting
                                logger.error("'Just a moment...' page persists - this is rate limiting.")
                                logger.error("The page will auto-refresh after 360 seconds, which is too long to wait.")
                                logger.error("Please significantly increase wait times between requests and try again.")
                                raise CloudflareRateLimitError(
                                    f"Cloudflare rate limiting detected after {elapsed:.0f} seconds. "
                                    f"Increase wait times between requests."
                                )
                        else:
                            # Page changed - might have resolved
                            logger.info("'Just a moment...' page changed - checking for content...")
                            time.sleep(5)
                            if not self._is_cloudflare_challenge():
                                logger.info("Rate limit page resolved - continuing...")
                                return False
                    
                    # Check for loading/processing state (circular progress indicator)
                    is_loading = (
                        'loading-verifying' in page_source or
                        'lds-ring' in page_source or
                        'waiting for www.science.org to respond' in page_source
                    )
                    
                    if is_loading and last_state != "loading":
                        logger.info("Cloudflare is processing (progress indicator visible) - waiting...")
                        last_state = "loading"
                        time.sleep(5)  # Wait longer when processing
                        continue
                    
                    # Check if we're past the loading state
                    if last_state == "loading" and not is_loading:
                        logger.info("Progress indicator disappeared - checking for content...")
                        time.sleep(3)  # Give it a moment to load content
                        if self._has_real_content_indicator():
                            logger.info("Cloudflare challenge completed - real content detected")
                            return False
                        last_state = "checking"
                    
                    # Check if challenge is gone
                    if not self._is_cloudflare_challenge():
                        if last_state != "resolved":
                            logger.info("Challenge elements disappeared - waiting for content...")
                            last_state = "resolved"
                        time.sleep(3)  # Wait for content to load
                        if self._has_real_content_indicator():
                            logger.info("Cloudflare challenge completed with real content")
                            return False
                        # Even without clear content indicators, if challenge is gone, assume resolved
                        if not self._is_cloudflare_challenge():
                            logger.info("Challenge resolved (no challenge elements found)")
                            return False
                    
                    time.sleep(2)  # Check every 2 seconds
                except WebDriverException as e:
                    if "target window already closed" in str(e).lower():
                        raise
                    logger.debug(f"Error during challenge wait: {e}")
                    time.sleep(1)
            
            logger.warning(f"Cloudflare challenge did not complete within {max_wait} seconds")
            if is_just_a_moment:
                logger.warning("'Just a moment...' page may require waiting up to 6 minutes for auto-refresh")
            return True  # Challenge still present
        except Exception as e:
            logger.debug(f"Error checking for Cloudflare challenge: {e}")
            return False
    
    def _handle_cloudflare_challenge_manual(self, url: str, timeout: int = 300) -> None:
        """
        Handle Cloudflare challenge by switching to visible mode for manual intervention.
        
        Parameters
        ----------
        url : str
            URL that triggered the challenge.
        timeout : int, optional
            Maximum time to wait for manual intervention in seconds. Default is 300 (5 minutes).
        """
        if self.driver is None or self.headless:
            # Need a visible browser for manual intervention
            old_headless = self.headless
            self.headless = False
            if self.driver:
                self.driver.quit()
            self._init_driver()
            # Keep headless as False for now, will restore later if needed
        
        # Ensure window is visible and in focus
        try:
            self.driver.switch_to.window(self.driver.current_window_handle)
            self.driver.maximize_window()
            # Bring window to front (platform-specific, may not work on all systems)
            self.driver.execute_script("window.focus();")
        except Exception as e:
            logger.debug(f"Could not focus window: {e}")
        
        logger.warning("=" * 60)
        logger.warning("CLOUDFLARE CHALLENGE DETECTED - MANUAL INTERVENTION REQUIRED")
        logger.warning(f"Browser window opened. Please complete the Cloudflare challenge.")
        logger.warning(f"")
        logger.warning(f"IMPORTANT:")
        logger.warning(f"  - Keep the browser window FOCUSED and VISIBLE (don't switch away)")
        logger.warning(f"  - Cloudflare monitors window focus - switching away may cause issues")
        logger.warning(f"  - After clicking the verification box:")
        logger.warning(f"    1. Wait for the page to fully load (you should see the actual article content)")
        logger.warning(f"    2. The script will AUTOMATICALLY detect when the challenge is resolved")
        logger.warning(f"    3. You can press Enter to confirm, but it's not required")
        logger.warning(f"")
        logger.warning(f"The script will automatically check every 3 seconds and continue when resolved.")
        logger.warning(f"Or press Enter if you want to manually confirm completion.")
        logger.warning("=" * 60)
        
        # Navigate to the URL if not already there
        try:
            if self.driver.current_url != url:
                self.driver.get(url)
            # Wait a moment for page to load
            time.sleep(2)
        except WebDriverException as e:
            logger.warning(f"Error navigating to URL: {e}")
        
        # Check if this is a "Just a moment..." rate limiting page
        # These cannot be manually resolved
        try:
            page_source = self.driver.page_source.lower()
            title = self.driver.title.lower()
            if 'just a moment' in title or 'just a moment' in page_source[:2000]:
                logger.error("=" * 60)
                logger.error("CLOUDFLARE RATE LIMITING DETECTED IN MANUAL MODE")
                logger.error("'Just a moment...' pages cannot be manually resolved.")
                logger.error("This is rate limiting - you must increase wait times between requests.")
                logger.error("=" * 60)
                raise CloudflareRateLimitError(
                    "Cloudflare rate limiting detected. Manual intervention cannot resolve this. "
                    "Increase wait times between requests."
                )
        except CloudflareRateLimitError:
            raise
        except Exception as e:
            logger.debug(f"Error checking for rate limiting: {e}")
        
        # Wait for user to solve challenge
        import select
        import sys
        
        start_time = time.time()
        last_check_time = start_time
        initial_url = self.driver.current_url
        url_history = [initial_url]  # Track URL changes to detect loops
        loop_detection_count = 0
        
        while time.time() - start_time < timeout:
            # Check if challenge is resolved (check every 3 seconds to avoid too frequent checks)
            if time.time() - last_check_time >= 3:
                try:
                    current_url = self.driver.current_url
                    page_source = self.driver.page_source.lower()
                    page_title = self.driver.title
                    
                    logger.info(f"Status check - URL: {current_url}, Title: {page_title[:50]}, Length: {len(page_source)} chars")
                    
                    # Check if this became a "Just a moment..." rate limiting page
                    if 'just a moment' in page_title.lower() or 'just a moment' in page_source[:2000]:
                        logger.error("=" * 60)
                        logger.error("CLOUDFLARE RATE LIMITING DETECTED DURING MANUAL INTERVENTION")
                        logger.error("'Just a moment...' page appeared - this is rate limiting.")
                        logger.error("Manual intervention cannot resolve rate limiting.")
                        logger.error("You must increase wait times between requests and restart.")
                        logger.error("=" * 60)
                        raise CloudflareRateLimitError(
                            "Cloudflare rate limiting detected during manual intervention. "
                            "Increase wait times between requests."
                        )
                    
                    # Detect redirect loops - if URL keeps changing back to challenge
                    if current_url != url_history[-1]:
                        logger.info(f"URL changed: {url_history[-1]} -> {current_url}")
                        url_history.append(current_url)
                        
                        # Wait for navigation to complete
                        time.sleep(5)
                        # Re-check after navigation
                        new_url = self.driver.current_url
                        new_page_source = self.driver.page_source.lower()
                        
                        # Check if URL changed again or if we're back to challenge
                        if new_url != current_url:
                            logger.info(f"URL changed again: {current_url} -> {new_url}")
                            url_history.append(new_url)
                            current_url = new_url
                            page_source = new_page_source
                        
                        # Check if we're back to a challenge page after URL change
                        if self._is_cloudflare_challenge():
                            loop_detection_count += 1
                            logger.warning(f"Challenge reappeared after URL change (loop count: {loop_detection_count})")
                            if loop_detection_count >= 2:
                                logger.error("=" * 60)
                                logger.error("REDIRECT LOOP DETECTED")
                                logger.error("Cloudflare redirects but then immediately re-challenges.")
                                logger.error("This indicates Cloudflare is detecting automation.")
                                logger.error("")
                                logger.error("URL history:")
                                for i, u in enumerate(url_history[-5:], 1):
                                    logger.error(f"  {i}. {u}")
                                logger.error("")
                                logger.error("The challenge cannot be resolved - Cloudflare is blocking automation.")
                                logger.error("")
                                logger.error("SOLUTIONS:")
                                logger.error("  1. Increase wait times dramatically: random_wait_min=60.0, random_wait_max=120.0")
                                logger.error("  2. Process in tiny batches: 10-20 DOIs at a time with 5+ minute breaks")
                                logger.error("  3. Consider using Science.org API if available")
                                logger.error("  4. This approach may not be viable for 600+ automated requests")
                                logger.error("=" * 60)
                                raise Exception("Cloudflare redirect loop - automation detected and blocked")
                        else:
                            # URL changed and challenge is gone - might be resolved
                            loop_detection_count = 0  # Reset counter
                    else:
                        # URL hasn't changed - check if we're stuck on challenge
                        if self._is_cloudflare_challenge():
                            # Check if we've been on challenge for a while
                            time_on_challenge = time.time() - start_time
                            if time_on_challenge > 60 and loop_detection_count == 0:
                                logger.warning(f"Stuck on challenge page for {time_on_challenge:.0f} seconds")
                                logger.warning("Challenge may not be resolving - Cloudflare might be blocking")
                    
                    # Check for loading/processing state
                    is_loading = (
                        'loading-verifying' in page_source or
                        'lds-ring' in page_source or
                        'waiting for www.science.org to respond' in page_source
                    )
                    
                    if is_loading:
                        logger.info("Cloudflare is still processing (progress indicator visible)...")
                        time.sleep(5)  # Wait longer when processing
                        last_check_time = time.time()
                        continue
                    
                    # Check if challenge is gone
                    if not self._is_cloudflare_challenge():
                        logger.info("Challenge elements disappeared - checking for content...")
                        # Wait longer for content to fully load after navigation
                        time.sleep(8)  # Increased wait time
                        
                        # Re-check after waiting
                        current_url = self.driver.current_url
                        page_source = self.driver.page_source.lower()
                        
                        # Double-check challenge is still gone
                        if not self._is_cloudflare_challenge():
                            # Check for real content
                            if self._has_real_content_indicator():
                                logger.info("Cloudflare challenge resolved - real content detected!")
                                return
                            else:
                                # Challenge is gone but content check uncertain
                                logger.warning("Challenge gone but content indicators not clear.")
                                logger.warning(f"URL: {current_url}, Title: {self.driver.title}")
                                logger.warning("Waiting a bit more for content to load...")
                                time.sleep(5)
                                if not self._is_cloudflare_challenge() and self._has_real_content_indicator():
                                    logger.info("Challenge resolved - content now detected!")
                                    return
                                elif not self._is_cloudflare_challenge():
                                    logger.warning("Challenge resolved but content unclear - continuing anyway...")
                                    return
                    else:
                        logger.debug("Challenge still present - waiting...")
                except WebDriverException as e:
                    if "target window already closed" in str(e).lower():
                        logger.error("Browser window was closed")
                        raise Exception("Browser window closed during manual intervention")
                    logger.debug(f"Error checking challenge status: {e}")
                last_check_time = time.time()
            
            # Check if user pressed Enter (non-blocking)
            try:
                if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                    sys.stdin.readline()
                    logger.info("User indicated challenge is complete - verifying...")
                    time.sleep(2)
                    # Verify challenge is actually resolved
                    if not self._is_cloudflare_challenge():
                        logger.info("Challenge confirmed resolved - continuing...")
                        return
                    else:
                        logger.warning("Challenge still present. Please complete it and press Enter again.")
            except (OSError, ValueError):
                # stdin might not be available in some environments (like Jupyter)
                pass
            
            time.sleep(0.5)
        
        # After timeout, check one more time
        logger.warning(f"Timeout reached ({timeout}s). Checking final status...")
        try:
            time.sleep(5)  # Give it a bit more time
            final_url = self.driver.current_url
            final_title = self.driver.title
            page_length = len(self.driver.page_source)
            
            logger.warning(f"Final URL: {final_url}")
            logger.warning(f"Final title: {final_title}")
            logger.warning(f"Page length: {page_length} chars")
            
            if not self._is_cloudflare_challenge() and self._has_real_content(url):
                logger.info("Challenge appears to be resolved - continuing...")
                return
            elif not self._is_cloudflare_challenge():
                logger.warning("Challenge text is gone but content may not be loaded yet. Continuing anyway...")
                return  # Continue anyway - might work
            else:
                error_msg = (
                    f"Cloudflare challenge not resolved after {timeout} seconds.\n"
                    f"Current URL: {final_url}\n"
                    f"Page title: {final_title}\n"
                    f"Page length: {page_length} chars\n"
                    "This may indicate Cloudflare is detecting automation.\n"
                    "Consider:\n"
                    "  1. Increasing wait times between requests (random_wait_min/max)\n"
                    "  2. Using a different approach (API access if available)\n"
                    "  3. Processing in smaller batches with longer delays"
                )
                logger.error(error_msg)
                raise Exception(error_msg)
        except WebDriverException as e:
            if "target window already closed" in str(e).lower():
                raise Exception("Browser window was closed during manual intervention")
            raise
    
    def _fetch_with_selenium(
        self,
        url: str,
        wait_for_element: Optional[tuple] = None,
        execute_script: Optional[str] = None,
        cookie_accept_selector: Optional[tuple] = None,
    ) -> Dict[str, Any]:
        """
        Fetch page using Selenium.
        
        Parameters
        ----------
        url : str
            URL to fetch.
        wait_for_element : tuple, optional
            (By, selector) tuple to wait for specific element.
            Example: (By.ID, 'content') or (By.CLASS_NAME, 'article')
        execute_script : str, optional
            JavaScript to execute after page load.
        cookie_accept_selector : tuple, optional
            (By, selector) tuple for cookie accept button. If provided, will check
            if element exists after page load and click it if present, then wait
            for page to reload. Example: (By.ID, 'accept-cookies') or 
            (By.CLASS_NAME, 'cookie-accept')
            
        Returns
        -------
        dict
            Response data similar to fetch() method.
        """
        if self.driver is None:
            self._init_driver()
        
        try:
            # Check if driver is still valid
            if self.driver is None:
                logger.warning("Driver is None, reinitializing...")
                self._init_driver()
            
            # Ensure window is in focus and visible (helps avoid detection)
            try:
                self.driver.switch_to.window(self.driver.current_window_handle)
                # Maximize window to ensure it's visible
                self.driver.maximize_window()
            except Exception as e:
                logger.debug(f"Could not maximize/focus window: {e}")
            
            # Navigate to URL
            # Validate URL format before navigating
            if not url or not isinstance(url, str):
                raise ValueError(f"Invalid URL: {url}")
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"URL must start with http:// or https://: {url}")
            
            logger.info(f"Fetching with Selenium: {url}")
            logger.debug(f"Current driver URL before navigation: {self.driver.current_url if self.driver else 'N/A'}")
            try:
                self.driver.get(url)
                logger.debug(f"Current driver URL after navigation: {self.driver.current_url}")
            except WebDriverException as e:
                if "target window already closed" in str(e).lower():
                    logger.warning("Window was closed, reinitializing driver...")
                    self._init_driver()
                    self.driver.get(url)
                else:
                    raise
            
            # Wait for page to load initially
            time.sleep(self.page_load_wait)
            
            # Wait for Cloudflare challenge to potentially appear
            # Cloudflare challenges are loaded via JavaScript AFTER the page loads
            # They typically appear within 2-5 seconds after page load
            # If we check too early, we'll miss them and they'll halt the process later
            logger.debug("Waiting for potential Cloudflare challenge to appear...")
            time.sleep(4)  # Wait for CF challenge to appear (if it's going to)
            
            # Handle cookie acceptance FIRST (before checking for Cloudflare)
            # This prevents cookie click from triggering Cloudflare re-challenge
            if cookie_accept_selector:
                by, selector = cookie_accept_selector
                try:
                    url_before_cookie = self.driver.current_url
                    logger.debug(f"URL before cookie click: {url_before_cookie}")
                    
                    # Wait for cookie banner to appear (it may load after page)
                    logger.debug(f"Waiting for cookie accept button: {selector}")
                    try:
                        WebDriverWait(self.driver, self.wait_timeout).until(
                            EC.presence_of_element_located((by, selector))
                        )
                    except TimeoutException:
                        logger.debug(f"Cookie accept button not found within {self.wait_timeout}s: {selector}")
                        self._log_cookie_button_info()
                    
                    # Check if cookie accept button is present
                    elements = self.driver.find_elements(by, selector)
                    if elements:
                        # Make sure element is visible and clickable
                        try:
                            WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((by, selector))
                            )
                        except TimeoutException:
                            logger.debug("Cookie button found but not clickable yet, trying anyway...")
                        
                        logger.info(f"Found cookie accept button: {selector}, clicking...")
                        # Click the first matching element
                        elements[0].click()
                        logger.debug("Clicked cookie accept button")
                        
                        # Wait for page to settle after cookie click
                        time.sleep(3)  # Wait for any redirects/updates
                        
                        url_after_cookie = self.driver.current_url
                        logger.debug(f"URL after cookie click: {url_after_cookie}")
                        if url_before_cookie != url_after_cookie:
                            logger.info(f"URL changed after cookie click: {url_before_cookie} -> {url_after_cookie}")
                            # Wait a bit more for redirect to complete
                            time.sleep(2)
                        
                        # Wait for cookie banner to disappear
                        try:
                            WebDriverWait(self.driver, self.wait_timeout).until_not(
                                EC.presence_of_element_located((by, selector))
                            )
                            logger.debug("Cookie accept button disappeared, page reloaded")
                        except TimeoutException:
                            logger.debug("Cookie accept button still present (may be normal)")
                    else:
                        logger.debug(f"Cookie accept button not found: {selector}")
                        self._log_cookie_button_info()
                except Exception as e:
                    logger.warning(f"Error handling cookie acceptance: {e}")
                    self._log_cookie_button_info()
            
            # Check for and wait for Cloudflare challenge to complete
            # Do this AFTER cookie handling to avoid conflicts
            try:
                challenge_still_present = self._wait_for_cloudflare_challenge()
                
                # If challenge is still present, switch to visible mode for manual intervention
                if challenge_still_present:
                    logger.warning("Cloudflare challenge still present. Switching to visible mode for manual intervention...")
                    self._handle_cloudflare_challenge_manual(url)
            except CloudflareRateLimitError as e:
                # Rate limiting cannot be manually resolved - re-raise to stop processing
                logger.error(f"Rate limiting error: {e}")
                raise
            
            
            # Wait for specific element if requested
            if wait_for_element:
                by, selector = wait_for_element
                try:
                    WebDriverWait(self.driver, self.wait_timeout).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    logger.debug(f"Found element: {selector}")
                except TimeoutException:
                    logger.warning(f"Timeout waiting for element: {selector}")
            
            # Execute custom JavaScript if provided
            if execute_script:
                try:
                    self.driver.execute_script(execute_script)
                    time.sleep(0.5)  # Brief wait after script execution
                except WebDriverException as e:
                    if "target window already closed" in str(e).lower():
                        logger.error("Browser window was closed unexpectedly")
                        raise Exception("Browser window closed - page may have closed it automatically")
                    raise
            
            # Check if window is still open before getting page source
            try:
                # Try to get window handles to verify window is still open
                _ = self.driver.window_handles
            except WebDriverException as e:
                if "target window already closed" in str(e).lower() or "web view not found" in str(e).lower():
                    logger.error("Browser window was closed before getting page content")
                    raise Exception("Browser window closed - page may have closed it automatically or redirected")
                raise
            
            # Wait for page to be fully loaded before getting content
            try:
                # Wait for document.readyState to be 'complete'
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                # Additional wait for any dynamic content
                time.sleep(1)
            except TimeoutException:
                logger.warning("Page did not reach 'complete' state within 10 seconds, continuing anyway...")
            except Exception as e:
                logger.debug(f"Error waiting for page load: {e}")
            
            # Get page source
            try:
                content = self.driver.page_source
                final_url = self.driver.current_url
                
                # Check if content is suspiciously empty
                if len(content) < 100:
                    logger.warning(f"Page content is very short ({len(content)} chars) - page may not have loaded")
                    # Wait a bit more and try again
                    time.sleep(3)
                    content = self.driver.page_source
                    if len(content) < 100:
                        logger.error(f"Page content still empty after additional wait ({len(content)} chars)")
                        logger.error(f"URL: {final_url}, Title: {self.driver.title}")
                        raise Exception(f"Page content is empty - page may not have loaded properly. URL: {final_url}")
            except WebDriverException as e:
                if "target window already closed" in str(e).lower() or "web view not found" in str(e).lower():
                    logger.error("Browser window was closed while getting page content")
                    raise Exception("Browser window closed - page may have closed it automatically")
                raise
            
            # Final check: if still on Cloudflare challenge page, check if it's rate limiting
            if self._is_cloudflare_challenge():
                # Check if this is a "Just a moment..." rate limiting page
                try:
                    page_source = self.driver.page_source.lower()
                    title = self.driver.title.lower()
                    if 'just a moment' in title or 'just a moment' in page_source[:2000]:
                        # This is rate limiting - don't try manual intervention
                        raise CloudflareRateLimitError(
                            "Cloudflare rate limiting detected. Increase wait times between requests."
                        )
                except CloudflareRateLimitError:
                    raise
                except Exception as e:
                    logger.debug(f"Error checking for rate limiting: {e}")
                
                # If it's a regular challenge (not rate limiting), try manual intervention
                logger.warning("Still on Cloudflare challenge page after automatic wait.")
                logger.warning("Attempting manual intervention...")
                try:
                    self._handle_cloudflare_challenge_manual(url, timeout=180)  # 3 minutes
                    # Check again after manual intervention
                    if self._is_cloudflare_challenge():
                        error_msg = (
                            "Still on Cloudflare challenge page after manual intervention. "
                            "The page may require more time or the challenge may have changed."
                        )
                        logger.error(error_msg)
                        raise Exception(error_msg)
                except CloudflareRateLimitError:
                    # Re-raise rate limiting errors
                    raise
                except Exception as e:
                    # If manual intervention also fails, raise the error
                    logger.error(f"Manual intervention failed: {e}")
                    raise
            
            result = {
                'url': final_url,
                'status_code': 200,  # Selenium doesn't provide status code
                'content': content,
                'headers': {},  # Selenium doesn't provide headers
                'encoding': 'utf-8',
                'cached': False,
                'timestamp': time.time(),
                'fetched_with_selenium': True,
            }
            
            return result
            
        except WebDriverException as e:
            logger.error(f"Selenium error fetching {url}: {e}")
            raise
    
    def fetch(
        self,
        url: str,
        use_selenium: Optional[bool] = None,
        wait_for_element: Optional[tuple] = None,
        execute_script: Optional[str] = None,
        cookie_accept_selector: Optional[tuple] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch a web page, optionally using Selenium.
        
        Parameters
        ----------
        url : str
            The URL to fetch.
        use_selenium : bool, optional
            Override default selenium usage for this request.
        wait_for_element : tuple, optional
            (By, selector) for Selenium to wait for. Only used with Selenium.
        execute_script : str, optional
            JavaScript to execute. Only used with Selenium.
        cookie_accept_selector : tuple, optional
            (By, selector) for cookie accept button. If provided, will check if
            element exists after page load and click it if present, then wait
            for page to reload. Only used with Selenium.
        **kwargs
            Additional arguments passed to parent fetch() method.
            
        Returns
        -------
        dict
            Response data.
        """
        # Determine whether to use Selenium for this request
        should_use_selenium = (
            use_selenium if use_selenium is not None else self.use_selenium
        )
        
        if should_use_selenium:
            # Initialize driver lazily if needed
            if not self._driver_initialized:
                self._init_driver()
            
            # Generate cache key
            cache_key = self._get_cache_key(url, kwargs.get('params'))
            
            # Check cache first (unless force_refresh)
            if not self.force_refresh:
                cached_data = self._load_from_cache(cache_key)
                if cached_data is not None:
                    cached_data['cached'] = True
                    return cached_data
            
            # Random wait between requests to avoid rate limiting
            if self.random_wait_max > 0:
                wait_time = random.uniform(self.random_wait_min, self.random_wait_max)
                logger.debug(f"Random wait: {wait_time:.2f} seconds before fetching {url}")
                time.sleep(wait_time)
            
            # Fetch with Selenium
            result = self._fetch_with_selenium(
                url,
                wait_for_element=wait_for_element,
                execute_script=execute_script,
                cookie_accept_selector=cookie_accept_selector,
            )
            
            # Cache the result
            self._save_to_cache(cache_key, result)
            
            return result
        else:
            # Use regular requests-based fetch
            return super().fetch(url, **kwargs)
    
    def handle_captcha_manual(self, url: str, timeout: int = 120) -> Dict[str, Any]:
        """
        Navigate to URL and wait for manual CAPTCHA solving.
        
        This method opens the page in a visible browser window and waits
        for the user to manually solve any CAPTCHA, then returns the page content.
        
        Parameters
        ----------
        url : str
            URL to fetch.
        timeout : int, optional
            Maximum time to wait for manual intervention in seconds. Default is 120.
            
        Returns
        -------
        dict
            Response data after CAPTCHA is solved.
        """
        if self.driver is None or self.headless:
            # Need a visible browser for manual intervention
            old_headless = self.headless
            self.headless = False
            if self.driver:
                self.driver.quit()
            self._init_driver()
            self.headless = old_headless
        
        logger.info(f"Opening {url} for manual CAPTCHA solving")
        logger.info(f"Please solve any CAPTCHA in the browser window within {timeout} seconds")
        
        self.driver.get(url)
        
        # Wait for user to solve CAPTCHA
        print(f"\n{'='*60}")
        print(f"MANUAL CAPTCHA SOLVING REQUIRED")
        print(f"Browser window opened. Please solve any CAPTCHA.")
        print(f"The script will continue automatically after {timeout} seconds")
        print(f"or press Enter in this terminal when done...")
        print(f"{'='*60}\n")
        
        # Wait for timeout or user input
        import select
        import sys
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check if user pressed Enter
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.readline()
                break
            time.sleep(1)
        
        # Get the page content after CAPTCHA
        content = self.driver.page_source
        final_url = self.driver.current_url
        
        result = {
            'url': final_url,
            'status_code': 200,
            'content': content,
            'headers': {},
            'encoding': 'utf-8',
            'cached': False,
            'timestamp': time.time(),
            'fetched_with_selenium': True,
            'captcha_solved_manually': True,
        }
        
        # Cache the result
        cache_key = self._get_cache_key(url)
        self._save_to_cache(cache_key, result)
        
        return result
    
    def _is_pdf_page(self) -> bool:
        """
        Check if the current page is a PDF file.
        
        Returns
        -------
        bool
            True if current page is a PDF, False otherwise.
        """
        try:
            if self.driver is None:
                return False
            
            # Check content-type header if available
            try:
                # Try to get response headers via JavaScript (limited in Selenium)
                content_type = self.driver.execute_script(
                    "return document.contentType || ''"
                )
                if content_type and 'application/pdf' in content_type.lower():
                    return True
            except Exception:
                pass
            
            # Check URL for PDF extension
            current_url = self.driver.current_url.lower()
            if current_url.endswith('.pdf') or '.pdf?' in current_url:
                return True
            
            # Check if URL contains PDF indicators
            if '/pdf' in current_url or 'format=pdf' in current_url:
                return True
            
            # Check page source for PDF indicators (PDFs often have minimal HTML)
            try:
                page_source = self.driver.page_source
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
    
    def _find_pdf_links(self) -> list:
        """
        Find links or buttons that likely lead to PDF files.
        
        Looks for elements with text containing "DOI", "Download", "PDF", etc.
        or links with .pdf extension.
        
        Returns
        -------
        list
            List of tuples (element, href) for potential PDF links.
        """
        if self.driver is None:
            return []
        
        pdf_links = []
        
        try:
            # Keywords to search for in link text
            pdf_keywords = [
                'doi', 'download', 'pdf', 'full text', 'fulltext',
                'article pdf', 'view pdf', 'get pdf', 'save pdf',
                'download pdf', 'pdf download', 'open pdf'
            ]
            
            # Find all links
            links = self.driver.find_elements(By.TAG_NAME, "a")
            
            for link in links:
                try:
                    href = link.get_attribute('href')
                    if not href:
                        continue
                    
                    text = (link.text or '').lower()
                    title = (link.get_attribute('title') or '').lower()
                    aria_label = (link.get_attribute('aria-label') or '').lower()
                    
                    # Check if link text contains PDF keywords
                    combined_text = f"{text} {title} {aria_label}"
                    if any(keyword in combined_text for keyword in pdf_keywords):
                        pdf_links.append((link, href))
                        logger.debug(f"Found PDF link by text: {href} (text: '{text[:50]}')")
                        continue
                    
                    # Check if href points to PDF
                    href_lower = href.lower()
                    if href_lower.endswith('.pdf') or '.pdf?' in href_lower:
                        pdf_links.append((link, href))
                        logger.debug(f"Found PDF link by extension: {href}")
                        continue
                    
                    # Check if href contains PDF indicators
                    if '/pdf' in href_lower or 'format=pdf' in href_lower or 'type=pdf' in href_lower:
                        pdf_links.append((link, href))
                        logger.debug(f"Found PDF link by URL pattern: {href}")
                        continue
                        
                except Exception as e:
                    logger.debug(f"Error processing link: {e}")
                    continue
            
            # Also check buttons that might trigger PDF downloads
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for button in buttons:
                try:
                    text = (button.text or '').lower()
                    title = (button.get_attribute('title') or '').lower()
                    aria_label = (button.get_attribute('aria-label') or '').lower()
                    onclick = (button.get_attribute('onclick') or '').lower()
                    
                    combined_text = f"{text} {title} {aria_label} {onclick}"
                    if any(keyword in combined_text for keyword in pdf_keywords):
                        # Try to find associated link or get button's data attributes
                        href = None
                        # Check if button has data-href or similar
                        for attr in ['data-href', 'data-url', 'data-link', 'href']:
                            href = button.get_attribute(attr)
                            if href:
                                break
                        
                        # If no direct href, try to find parent link
                        if not href:
                            try:
                                parent = button.find_element(By.XPATH, "./ancestor::a[1]")
                                href = parent.get_attribute('href')
                            except Exception:
                                pass
                        
                        if href:
                            pdf_links.append((button, href))
                            logger.debug(f"Found PDF button: {href} (text: '{text[:50]}')")
                except Exception as e:
                    logger.debug(f"Error processing button: {e}")
                    continue
            
            # Remove duplicates (same href)
            seen_hrefs = set()
            unique_links = []
            for element, href in pdf_links:
                if href not in seen_hrefs:
                    seen_hrefs.add(href)
                    unique_links.append((element, href))
            
            return unique_links
            
        except Exception as e:
            logger.error(f"Error finding PDF links: {e}")
            return []
    
    def _download_pdf_from_current_page(self, output_path: Path) -> bool:
        """
        Download PDF from current page if it's a PDF.
        
        Parameters
        ----------
        output_path : Path
            Path where PDF should be saved.
            
        Returns
        -------
        bool
            True if PDF was downloaded, False otherwise.
        """
        try:
            if not self._is_pdf_page():
                return False
            
            current_url = self.driver.current_url
            logger.info(f"Current page is a PDF, downloading from: {current_url}")
            
            # Use requests to download the PDF (more reliable than Selenium)
            response = self.session.get(current_url, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            # Check content-type
            content_type = response.headers.get('content-type', '').lower()
            if 'application/pdf' not in content_type:
                # Still try to save if URL suggests it's a PDF
                if not (current_url.lower().endswith('.pdf') or '.pdf?' in current_url.lower()):
                    logger.warning(f"Content-type is not PDF: {content_type}")
                    return False
            
            # Save PDF
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"PDF downloaded successfully to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading PDF from current page: {e}")
            return False
    
    def download_pdf(
        self,
        url: str,
        output_path: Optional[Union[str, Path]] = None,
        cookie_accept_selector: Optional[tuple] = None,
        max_redirects: int = 2,
    ) -> Optional[Path]:
        """
        Download PDF from a URL, handling CloudFlare and cookies.
        
        This method implements a 3-step process:
        1. If the page is itself a PDF file, download it
        2. If the page contains a button or link to a PDF file (with text like
           "DOI" or "Download"), click that link and go to step 1
        3. If neither works, report and return None
        
        Parameters
        ----------
        url : str
            URL to fetch PDF from.
        output_path : str or Path, optional
            Path where PDF should be saved. If None, generates a filename from URL.
        cookie_accept_selector : tuple, optional
            (By, selector) tuple for cookie accept button. If provided, will check
            if element exists after page load and click it if present.
        max_redirects : int, optional
            Maximum number of redirects to follow when clicking PDF links.
            Default is 2.
            
        Returns
        -------
        Path or None
            Path to downloaded PDF if successful, None otherwise.
        """
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is required for PDF downloading")
        
        if self.driver is None:
            self._init_driver()
        
        try:
            # Generate output path if not provided
            if output_path is None:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                filename = parsed.path.split('/')[-1] or 'document.pdf'
                if not filename.endswith('.pdf'):
                    filename = f"{filename}.pdf"
                output_path = Path(self.cache_dir) / "pdfs" / filename
            else:
                output_path = Path(output_path)
            
            logger.info(f"Attempting to download PDF from: {url}")
            
            # Step 1: Navigate to URL and handle CloudFlare/cookies
            logger.debug("Step 1: Navigating to URL...")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(self.page_load_wait)
            
            # Wait for potential CloudFlare challenge
            logger.debug("Waiting for potential CloudFlare challenge...")
            time.sleep(4)
            
            # Handle cookie acceptance FIRST (before checking for PDF)
            if cookie_accept_selector:
                by, selector = cookie_accept_selector
                try:
                    logger.debug(f"Checking for cookie accept button: {selector}")
                    WebDriverWait(self.driver, self.wait_timeout).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    elements = self.driver.find_elements(by, selector)
                    if elements:
                        logger.info(f"Found cookie accept button, clicking...")
                        elements[0].click()
                        time.sleep(3)  # Wait for page to settle
                except TimeoutException:
                    logger.debug("Cookie accept button not found (may not be needed)")
                except Exception as e:
                    logger.warning(f"Error handling cookie acceptance: {e}")
            
            # Check for and wait for CloudFlare challenge
            try:
                challenge_still_present = self._wait_for_cloudflare_challenge()
                if challenge_still_present:
                    logger.warning("CloudFlare challenge detected, attempting manual intervention...")
                    self._handle_cloudflare_challenge_manual(url, timeout=180)
            except CloudflareRateLimitError as e:
                logger.error(f"CloudFlare rate limiting: {e}")
                return None
            
            # Step 2: Check if current page is a PDF
            logger.debug("Step 2: Checking if current page is a PDF...")
            if self._is_pdf_page():
                logger.info("Current page is a PDF, downloading...")
                if self._download_pdf_from_current_page(output_path):
                    return output_path
                else:
                    logger.warning("Failed to download PDF from current page")
            
            # Step 3: Look for PDF links/buttons
            logger.debug("Step 3: Searching for PDF download links/buttons...")
            pdf_links = self._find_pdf_links()
            
            if not pdf_links:
                logger.warning(f"No PDF links found on page: {url}")
                return None
            
            logger.info(f"Found {len(pdf_links)} potential PDF link(s), trying first one...")
            
            # Try each PDF link (up to max_redirects)
            for i, (element, href) in enumerate(pdf_links[:max_redirects]):
                try:
                    logger.info(f"Attempting PDF link {i+1}/{min(len(pdf_links), max_redirects)}: {href}")
                    
                    # Click the link
                    element.click()
                    
                    # Wait for navigation
                    time.sleep(self.page_load_wait + 2)
                    
                    # Wait for potential CloudFlare challenge on new page
                    time.sleep(4)
                    
                    # Handle cookies on new page if needed
                    if cookie_accept_selector:
                        by, selector = cookie_accept_selector
                        try:
                            elements = self.driver.find_elements(by, selector)
                            if elements:
                                logger.debug("Found cookie button on new page, clicking...")
                                elements[0].click()
                                time.sleep(2)
                        except Exception:
                            pass
                    
                    # Check for CloudFlare challenge on new page
                    try:
                        challenge_still_present = self._wait_for_cloudflare_challenge()
                        if challenge_still_present:
                            logger.warning("CloudFlare challenge on PDF link page, attempting manual intervention...")
                            self._handle_cloudflare_challenge_manual(href, timeout=180)
                    except CloudflareRateLimitError as e:
                        logger.error(f"CloudFlare rate limiting on PDF link: {e}")
                        continue
                    
                    # Check if new page is a PDF
                    if self._is_pdf_page():
                        logger.info("PDF link led to PDF page, downloading...")
                        if self._download_pdf_from_current_page(output_path):
                            return output_path
                    
                    # If not a PDF, check if there are more PDF links on this page
                    # (recursive search, but limit depth)
                    if i < max_redirects - 1:
                        new_pdf_links = self._find_pdf_links()
                        if new_pdf_links:
                            logger.debug(f"Found {len(new_pdf_links)} more PDF links on new page")
                            # Add to our list (but don't exceed max_redirects total)
                            remaining = max_redirects - (i + 1)
                            pdf_links.extend(new_pdf_links[:remaining])
                    
                except Exception as e:
                    logger.warning(f"Error following PDF link {href}: {e}")
                    continue
            
            # If we get here, we couldn't download the PDF
            logger.warning(f"Could not download PDF from: {url}")
            logger.warning("Tried:")
            logger.warning("  1. Checking if page itself is a PDF")
            logger.warning(f"  2. Following {len(pdf_links)} PDF link(s)")
            return None
            
        except Exception as e:
            logger.error(f"Error in download_pdf: {e}")
            return None
    
    def close_driver(self) -> None:
        """Close the Selenium WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Closed WebDriver")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close driver and session."""
        self.close_driver()
        super().__exit__(exc_type, exc_val, exc_tb)


# Example usage
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Example 1: Using requests (default)")
    print("-" * 50)
    
    fetcher = SeleniumWebFetcher(
        cache_dir="./cache/selenium_example",
        use_selenium=False,
    )
    
    try:
        result = fetcher.fetch("https://example.com")
        print(f"Status: {result['status_code']}")
        print(f"From cache: {result['cached']}")
        print(f"Content length: {len(result['content'])}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        fetcher.close_driver()
    
    print("\n\nExample 2: Using Selenium")
    print("-" * 50)
    
    if SELENIUM_AVAILABLE:
        with SeleniumWebFetcher(
            cache_dir="./cache/selenium_example",
            use_selenium=True,
            headless=True,
        ) as fetcher:
            try:
                # Fetch with Selenium, waiting for a specific element
                from selenium.webdriver.common.by import By
                
                result = fetcher.fetch(
                    "https://example.com",
                    wait_for_element=(By.TAG_NAME, "h1"),
                )
                print(f"Status: {result['status_code']}")
                print(f"From cache: {result['cached']}")
                print(f"Fetched with Selenium: {result.get('fetched_with_selenium', False)}")
                print(f"Content length: {len(result['content'])}")
            except Exception as e:
                print(f"Error: {e}")
    else:
        print("Selenium not installed. Install with: pip install selenium")
    
    print("\n\nExample 3: Mixed usage (requests by default, Selenium when needed)")
    print("-" * 50)
    
    if SELENIUM_AVAILABLE:
        with SeleniumWebFetcher(
            cache_dir="./cache/selenium_example",
            use_selenium=False,  # Default to requests
        ) as fetcher:
            # This uses requests
            result1 = fetcher.fetch("https://example.com")
            print(f"Example.com - Selenium: {result1.get('fetched_with_selenium', False)}")
            
            # This uses Selenium (override)
            result2 = fetcher.fetch(
                "https://example.com",
                use_selenium=True,
            )
            print(f"Example.com with Selenium - Selenium: {result2.get('fetched_with_selenium', False)}")
