"""
Web page fetcher with local caching and retry logic.

This module provides a class for fetching and caching web pages with robust
error handling and retry mechanisms similar to the api_clients package.
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, Union
from urllib.parse import urlparse, urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)


class WebPageFetcher:
    """
    Fetch and cache web pages with retry logic.
    
    This class provides functionality to fetch web pages with automatic retries,
    local file-based caching, and error handling. It's designed to work similarly
    to the Scopus and Crossref API clients in the api_clients package.
    
    Parameters
    ----------
    cache_dir : str or Path, optional
        Directory for storing cached responses. Defaults to './cache/web_pages'
    max_retries : int, optional
        Maximum number of retry attempts for failed requests. Default is 3.
    backoff_factor : float, optional
        Backoff factor for retry delays (delay = backoff_factor * (2 ** retry_count)).
        Default is 1.0 (delays: 1s, 2s, 4s, ...)
    timeout : int or tuple, optional
        Request timeout in seconds. Can be a single value or (connect, read) tuple.
        Default is (10, 30).
    user_agent : str, optional
        User agent string for requests. Default is a generic browser user agent.
    force_refresh : bool, optional
        If True, bypass cache and always fetch fresh content. Default is False.
    """
    
    def __init__(
        self,
        cache_dir: Union[str, Path] = "./cache/web_pages",
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        timeout: Union[int, tuple] = (10, 30),
        user_agent: Optional[str] = None,
        force_refresh: bool = False,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.force_refresh = force_refresh
        
        # Set up user agent - use a more recent and realistic one
        if user_agent is None:
            self.user_agent = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
        else:
            self.user_agent = user_agent
        
        # Set up session with retry logic
        self.session = self._create_session()
        
        logger.info(f"WebPageFetcher initialized with cache dir: {self.cache_dir}")
    
    def _create_session(self) -> requests.Session:
        """
        Create a requests session with retry logic.
        
        Returns
        -------
        requests.Session
            Configured session with retry adapter.
        """
        session = requests.Session()
        
        # Enable cookie handling (default, but explicit is better)
        # Session automatically handles cookies via requests.cookies
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
            # Don't retry on 403 - it's likely a permanent block
            # But allow retries for 429 (rate limiting)
        )
        
        # Mount adapter with retry strategy
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers to mimic a real browser more closely
        session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
        
        return session
    
    def _get_cache_key(self, url: str, params: Optional[Dict] = None) -> str:
        """
        Generate a cache key for a URL and parameters.
        
        Parameters
        ----------
        url : str
            The URL to generate a key for.
        params : dict, optional
            Query parameters to include in the key.
            
        Returns
        -------
        str
            MD5 hash to use as cache key.
        """
        # Include params in the cache key
        if params:
            cache_str = f"{url}?{urlencode(sorted(params.items()))}"
        else:
            cache_str = url
        
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """
        Get the file path for a cache key.
        
        Parameters
        ----------
        cache_key : str
            The cache key (MD5 hash).
            
        Returns
        -------
        Path
            Path to the cache file.
        """
        # Use subdirectories to avoid too many files in one directory
        subdir = cache_key[:2]
        cache_subdir = self.cache_dir / subdir
        cache_subdir.mkdir(exist_ok=True)
        
        return cache_subdir / f"{cache_key}.json"
    
    def _load_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Load response from cache if it exists.
        
        Parameters
        ----------
        cache_key : str
            The cache key to load.
            
        Returns
        -------
        dict or None
            Cached response data, or None if not found.
        """
        cache_path = self._get_cache_path(cache_key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Loaded from cache: {cache_key}")
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cache file {cache_path}: {e}")
            return None
    
    def _save_to_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """
        Save response to cache.
        
        Parameters
        ----------
        cache_key : str
            The cache key to save under.
        data : dict
            The data to cache.
        """
        cache_path = self._get_cache_path(cache_key)
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved to cache: {cache_key}")
        except IOError as e:
            logger.warning(f"Failed to save cache file {cache_path}: {e}")
    
    def fetch(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        method: str = "GET",
        data: Optional[Dict] = None,
        referer: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch a web page with caching and retry logic.
        
        Parameters
        ----------
        url : str
            The URL to fetch.
        params : dict, optional
            Query parameters to include in the request.
        headers : dict, optional
            Additional headers to include in the request.
        method : str, optional
            HTTP method to use. Default is "GET".
        data : dict, optional
            Data to send in the request body (for POST requests).
        referer : str, optional
            Referer header value. If not provided and URL is a DOI link,
            will automatically set to the domain's homepage.
        **kwargs
            Additional arguments to pass to requests.request().
            
        Returns
        -------
        dict
            Dictionary containing:
            - 'url': The final URL (after redirects)
            - 'status_code': HTTP status code
            - 'content': Page content as string
            - 'headers': Response headers as dict
            - 'encoding': Content encoding
            - 'cached': Boolean indicating if response was from cache
            
        Raises
        ------
        requests.RequestException
            If the request fails after all retries.
        """
        # Generate cache key
        cache_key = self._get_cache_key(url, params)
        
        # Try to load from cache (unless force_refresh is True or method is not GET)
        if not self.force_refresh and method == "GET":
            cached_data = self._load_from_cache(cache_key)
            if cached_data is not None:
                cached_data['cached'] = True
                return cached_data
        
        # Merge custom headers with session headers
        request_headers = dict(self.session.headers)
        
        # Add Referer header if provided or auto-generate from URL
        if referer:
            request_headers['Referer'] = referer
        elif not headers or 'Referer' not in headers:
            # Auto-generate referer from URL domain
            try:
                parsed = urlparse(url)
                if parsed.scheme and parsed.netloc:
                    request_headers['Referer'] = f"{parsed.scheme}://{parsed.netloc}/"
            except Exception:
                pass  # If URL parsing fails, just skip referer
        
        if headers:
            request_headers.update(headers)
        
        # Set default timeout if not provided in kwargs
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
        
        # Make the request
        try:
            logger.info(f"Fetching {method} {url}")
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                headers=request_headers,
                data=data,
                **kwargs
            )
            
            # Raise for bad status codes
            response.raise_for_status()
            
            # Prepare response data
            result = {
                'url': response.url,
                'status_code': response.status_code,
                'content': response.text,
                'headers': dict(response.headers),
                'encoding': response.encoding,
                'cached': False,
                'timestamp': time.time(),
            }
            
            # Cache successful GET requests
            if method == "GET" and response.status_code == 200:
                self._save_to_cache(cache_key, result)
            
            return result
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise
    
    def fetch_multiple(
        self,
        urls: list,
        delay: float = 0.5,
        stop_on_error: bool = False,
        **kwargs
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch multiple URLs with rate limiting.
        
        Parameters
        ----------
        urls : list
            List of URLs to fetch.
        delay : float, optional
            Delay between requests in seconds. Default is 0.5.
        stop_on_error : bool, optional
            If True, stop fetching on first error. Default is False.
        **kwargs
            Additional arguments to pass to fetch().
            
        Returns
        -------
        dict
            Dictionary mapping URLs to their responses or error information.
        """
        results = {}
        
        for i, url in enumerate(urls):
            try:
                results[url] = self.fetch(url, **kwargs)
                
                # Add delay between requests (except after last request)
                if i < len(urls) - 1:
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                results[url] = {
                    'error': str(e),
                    'cached': False,
                }
                
                if stop_on_error:
                    break
        
        return results
    
    def establish_session(self, base_url: str) -> None:
        """
        Visit the homepage/base URL first to establish cookies and session.
        
        This can help avoid 403 errors by making the request look more like
        a real browser session that visited the site first.
        
        Parameters
        ----------
        base_url : str
            The base URL or homepage to visit first (e.g., "https://www.science.org")
        """
        try:
            logger.info(f"Establishing session by visiting {base_url}")
            # Make a simple GET request to establish cookies
            self.session.get(base_url, timeout=self.timeout)
            logger.debug(f"Session established with {len(self.session.cookies)} cookies")
        except Exception as e:
            logger.warning(f"Failed to establish session at {base_url}: {e}")
    
    def get_cache_filename(self, url: str, params: Optional[Dict] = None) -> Optional[Path]:
        """
        Get the cache filename for a URL if it exists.
        
        Parameters
        ----------
        url : str
            The URL to get the cache filename for.
        params : dict, optional
            Query parameters that were used when caching.
            
        Returns
        -------
        Path or None
            Path to the cache file if it exists, None otherwise.
        """
        cache_key = self._get_cache_key(url, params)
        cache_path = self._get_cache_path(cache_key)
        
        if cache_path.exists():
            return cache_path
        else:
            return None
    
    def clear_cache(self, url: Optional[str] = None, params: Optional[Dict] = None) -> None:
        """
        Clear cached responses.
        
        Parameters
        ----------
        url : str, optional
            If provided, clear cache for this specific URL.
            If None, clear entire cache.
        params : dict, optional
            Query parameters (only used if url is provided).
        """
        if url is not None:
            # Clear specific URL
            cache_key = self._get_cache_key(url, params)
            cache_path = self._get_cache_path(cache_key)
            if cache_path.exists():
                cache_path.unlink()
                logger.info(f"Cleared cache for {url}")
        else:
            # Clear entire cache
            import shutil
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                logger.info("Cleared entire cache")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self.session.close()


# Example usage
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create fetcher with custom cache directory
    fetcher = WebPageFetcher(
        cache_dir="./cache/example",
        max_retries=3,
        backoff_factor=1.0,
    )
    
    # Fetch a single page
    try:
        result = fetcher.fetch("https://example.com")
        print(f"Status: {result['status_code']}")
        print(f"From cache: {result['cached']}")
        print(f"Content length: {len(result['content'])}")
        print(f"First 200 chars: {result['content'][:200]}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Fetch multiple pages
    urls = [
        "https://example.com",
        "https://www.python.org",
    ]
    results = fetcher.fetch_multiple(urls, delay=1.0)
    for url, result in results.items():
        if 'error' not in result:
            print(f"{url}: {result['status_code']} (cached: {result['cached']})")
        else:
            print(f"{url}: Error - {result['error']}")
