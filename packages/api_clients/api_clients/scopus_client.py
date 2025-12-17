"""
Scopus API client - specialization of base API client.

Handles Scopus-specific:
- API key authentication
- Query string formatting
- Response parsing
- Cursor-based pagination
"""

from pathlib import Path
import yaml
import datetime
import time
import requests
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from urllib.parse import quote_plus
import logging
import pandas as pd

from .base_client import BaseAPIClient, APIConfig, RateLimiter, BaseSearchFetcher
from caching import LocalCache

logger = logging.getLogger(__name__)


@dataclass
class ScopusConfig(APIConfig):
    """Scopus-specific configuration."""
    api_key: str = ""
    base_url: str = "https://api.elsevier.com/content/search/scopus"
    view: str = "COMPLETE"
    
    # Scopus typically allows 2-3 requests per second for institutional access
    requests_per_second: float = 2.0
    burst_size: int = 5
    max_results_per_query: int = 5000
    
    def __post_init__(self):
        super().__post_init__()
        if not self.default_params:
            self.default_params = {'count': 25}


class ScopusRateLimiter(RateLimiter):
    """Scopus-specific rate limiter that reads X-RateLimit headers."""
    
    def update_from_headers(self, headers: Dict[str, str]):
        """Update rate limit state from Scopus API headers."""
        try:
            if 'X-RateLimit-Limit' in headers:
                self.api_rate_limit = int(headers['X-RateLimit-Limit'])
            if 'X-RateLimit-Remaining' in headers:
                self.api_remaining = int(headers['X-RateLimit-Remaining'])
                if self.api_remaining % 100 == 0:
                    logger.info(f"Scopus API rate limit: {self.api_remaining}/{self.api_rate_limit} remaining")
            if 'X-RateLimit-Reset' in headers:
                import datetime
                self.api_reset_time = datetime.datetime.fromtimestamp(int(headers['X-RateLimit-Reset']))
        except (ValueError, KeyError) as e:
            logger.warning(f"Error parsing Scopus rate limit headers: {e}")


class ScopusSearchClient(BaseAPIClient):
    """Scopus search API client."""
    
    def __init__(self, config: ScopusConfig):
        self.config = config
        self.rate_limiter = ScopusRateLimiter(config)  # Use Scopus-specific rate limiter
        super().__init__(config)
    
    def _setup_session(self):
        """Setup Scopus session with API key."""
        if not self.config.api_key:
            raise ValueError(
                "Scopus API key is required. Set it in the config or load from scopus.yaml file. "
                "Get your API key from: https://dev.elsevier.com/"
            )
        self.session.headers.update({
            'Accept': 'application/json',
            'X-ELS-APIKey': self.config.api_key,
        })
        print (self.session.headers)
    
    def _build_search_url(self, query: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Build Scopus search URL."""
        url_params = {**self.config.default_params, **(params or {})}
        param_str = '&'.join(f'{k}={v}' for k, v in url_params.items())
        return f"{self.config.base_url}?query={quote_plus(query)}&view={self.config.view}&{param_str}"
    
    def _parse_page_response(self, response_data: Dict[str, Any], page: int) -> Dict[str, Any]:
        """Parse Scopus API response."""
        # Check for API errors
        if 'error' in response_data:
            return {
                'page': page,
                'total_results': 0,
                'results': None,
                'error': response_data.get('error')
            }
        
        # Check for search results
        if 'search-results' not in response_data:
            return {
                'page': page,
                'total_results': 0,
                'results': None,
                'error': 'no_search_results'
            }
        
        search_results = response_data['search-results']
        total_results = int(search_results.get('opensearch:totalResults', 0))
        entries = search_results.get('entry', [])
        
        return {
            'page': page,
            'total_results': total_results,
            'results': entries,
            'cursor': None,  # Scopus uses links for pagination, not cursor
        }
    
    def _get_next_page_url(self, response_data: Dict[str, Any], current_url: str) -> Optional[str]:
        """Get next page URL from Scopus response."""
        if 'search-results' not in response_data:
            return None
        
        links = response_data['search-results'].get('link', [])
        next_links = [link for link in links if link.get('@ref') == 'next']
        
        if next_links:
            return next_links[0]['@href']
        
        return None


class ScopusSearchFetcher(BaseSearchFetcher):
    """
    Scopus search fetcher with caching.
    
    Main interface for Scopus searches.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: str = "~/.cache/scopus/search",
        api_key_dir: str = "~/Documents/dh4pmp/api_keys",
        **kwargs
    ):
        """
        Initialize Scopus search fetcher.
        
        Args:
            api_key: Scopus API key (if None, tries to load from yaml)
            cache_dir: Directory for cache files
            api_key_dir: Directory containing API config files (default: ~/Documents/dh4pmp/api_keys)
            **kwargs: Additional configuration:
                - requests_per_second: Rate limit (default: 2.0)
                - max_results_per_query: Max results (default: 5000)
                - max_retries: Retry attempts (default: 3)
                - cache_max_age_days: Cache expiration (default: None/never)
        """
        # Load API key
        if api_key is None:
            api_key = self._load_api_key(api_key_dir)
        
        # Initialize configuration
        config = ScopusConfig(
            api_key=api_key,
            requests_per_second=kwargs.get('requests_per_second', 2.0),
            max_results_per_query=kwargs.get('max_hits', kwargs.get('max_results_per_query', 5000)),
            max_retries=kwargs.get('max_retries', 3),
        )
        
        # Initialize client and cache
        client = ScopusSearchClient(config)
        cache = LocalCache(
            cache_dir=cache_dir,
            compression=True,
            max_age_days=kwargs.get('cache_max_age_days', None)
        )
        
        super().__init__(client, cache)
        
        logger.info(f"Initialized Scopus fetcher with cache at {cache.cache_dir}")
    
    def _load_api_key(self, api_key_dir: str) -> str:
        """
        Load API key from YAML config file.
        
        File: scopus.yaml with required 'X-ELS-APIKey' field
        """
        import yaml
        
        api_key_dir = Path(api_key_dir).expanduser()
        key_paths = [
            Path('.') / 'scopus.yaml',
            api_key_dir / 'scopus.yaml',
        ]
        
        for path in key_paths:
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        key_data = yaml.safe_load(f)
                        
                        if key_data and 'X-ELS-APIKey' in key_data:
                            api_key = key_data['X-ELS-APIKey']
                            if api_key:  # Make sure it's not empty
                                logger.info(f"Loaded Scopus API key from {path}")
                                return api_key
                except Exception as e:
                    logger.warning(f"Error loading {path}: {e}")
        
        raise FileNotFoundError(
            f"Scopus API key not found. Create one of:\n"
            f"  - ./scopus.yaml\n"
            f"  - {api_key_dir}/scopus.yaml\n\n"
            f"With content:\n"
            f"  X-ELS-APIKey: your_api_key_here\n\n"
            f"Get your API key from: https://dev.elsevier.com/"
        )
    
    def fetch(self, query: str, force_refresh: bool = False, **params) -> Optional[pd.DataFrame]:
        """
        Fetch Scopus search results with optional parameters.
        
        Args:
            query: Scopus search query string
            force_refresh: If True, bypass cache
            **params: Additional Scopus API parameters
        
        Common Query Fields:
            TITLE(text)           - Search in title
            ABS(text)             - Search in abstract  
            KEY(text)             - Search in keywords
            TITLE-ABS-KEY(text)   - Search in title, abstract, or keywords
            AUTH(name)            - Author name
            AUTHFIRST(name)       - First author
            AUTHLASTNAME(name)    - Author last name
            AU-ID(id)             - Author ID
            AFFIL(name)           - Affiliation name
            AF-ID(id)             - Affiliation ID
            PUBYEAR(year)         - Publication year (e.g., PUBYEAR = 2024)
            PUBYEAR IS 2020       - Exact year
            PUBYEAR > 2020        - After year
            PUBYEAR < 2020        - Before year
            ISSN(issn)            - Journal ISSN
            ISBN(isbn)            - Book ISBN
            DOI(doi)              - Document DOI
            LANGUAGE(lang)        - Language (e.g., english)
            DOCTYPE(type)         - Document type (ar, re, cp, bk, ch)
            SUBJAREA(area)        - Subject area (COMP, MEDI, etc.)
            
        Common Parameters:
            count: int            - Results per page (default: 25, max: 200)
            start: int            - Starting index (for pagination)
            sort: str             - Sort field (e.g., '+coverDate', '-citedby-count')
            view: str             - Response view (STANDARD, COMPLETE)
            field: str            - Specific fields to return
            date: str             - Date range (YYYY or YYYY-YYYY)
            
        Examples:
            # Simple search
            results = fetcher.fetch("TITLE-ABS-KEY(machine learning)")
            
            # Author search
            results = fetcher.fetch("AUTH(Smith) AND PUBYEAR = 2024")
            
            # With parameters
            results = fetcher.fetch(
                "TITLE(neural networks)",
                count=50,
                sort="+coverDate"
            )
            
            # Complex query
            results = fetcher.fetch(
                "TITLE-ABS-KEY(AI) AND PUBYEAR > 2020 AND SUBJAREA(COMP)",
                count=100
            )
        
        Query Operators:
            AND, OR, AND NOT      - Boolean operators
            W/n                   - Within n words (e.g., neural W/3 network)
            PRE/n                 - Precedes within n words
            {phrase}              - Exact phrase (use quotes in query string)
            *                     - Wildcard (e.g., climat*)
            
        Returns:
            DataFrame with columns: ID, page, num_hits, data, error
            
        Reference:
            https://dev.elsevier.com/sc_search_tips.html
            https://dev.elsevier.com/guides/ScopusSearchGuide.pdf
        """
        # Use base fetch with params
        return super().fetch(query, force_refresh=force_refresh, **params)
    
    def clean_max_hits(self):
        """Remove cached queries that exceeded max_hits."""
        removed = 0
        for item in self.cache.list_queries():
            data = self.cache.get(item['query'])
            if data is not None:
                # Check if any row has data=None and num_hits > max_hits
                problematic = data[
                    (data['data'].isna()) & 
                    (data['num_hits'] > self.client.config.max_results_per_query)
                ]
                if len(problematic) > 0:
                    self.cache.delete(item['query'])
                    removed += 1
        
        if removed > 0:
            logger.info(f"Removed {removed} queries that exceeded max_hits")


class ScopusAbstractClient:
    """
    Scopus abstract API client for fetching individual abstracts by EID.
    
    This client extends BaseAPIClient to provide proper rate limiting,
    error handling, and retry logic for abstract fetching.
    """
    
    def __init__(self, config: ScopusConfig):
        self.config = config
        self.rate_limiter = ScopusRateLimiter(config)
        self.session = requests.Session()
        self._setup_session()
        self.base_url = 'https://api.elsevier.com/content/abstract/eid'
    
    def _setup_session(self):
        """Setup Scopus session with API key."""
        if not self.config.api_key:
            raise ValueError(
                "Scopus API key is required. Set it in the config or load from scopus.yaml file. "
                "Get your API key from: https://dev.elsevier.com/"
            )
        self.session.headers.update({
            'Accept': 'application/json',
            'X-ELS-APIKey': self.config.api_key,
        })
    
    def fetch_abstract(
        self, 
        eid: str, 
        view: str = 'META_ABS',
        field: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch abstract data for a Scopus EID.
        
        Args:
            eid: Scopus EID (e.g., '2-s2.0-85012345678')
            view: Response view type (default: 'META_ABS')
                 Options: 'META_ABS', 'FULL', 'STANDARD', 'REF', 'CITESCORE'
            field: Specific fields to return (comma-separated, optional)
                  Example: 'citedby-count,prism:doi,dc:title'
        
        Returns:
            Full abstract data dict, or None if not found/error
        """
        # Build URL
        url = f'{self.base_url}/{eid}'
        
        # Build parameters
        params = {'view': view}
        if field:
            params['field'] = field
        
        # Add params to URL
        if params:
            param_str = '&'.join(f'{k}={v}' for k, v in params.items())
            url = f'{url}?{param_str}'
        
        # Make request with rate limiting and retry logic
        response = self._make_request(url)
        
        if response is None or not response.ok:
            logger.error(f"Failed to fetch abstract for EID: {eid}")
            return None
        
        try:
            data = response.json()
            return data
        except ValueError as e:
            logger.error(f"Invalid JSON response for EID {eid}: {e}")
            return None
    
    def _make_request(self, url: str, retry_count: int = 0) -> Optional[requests.Response]:
        """
        Make a request with retry logic (reuses BaseAPIClient logic).
        
        Returns None if request fails after all retries.
        """
        self.rate_limiter.wait_if_needed()
        
        try:
            response = self.session.get(url, timeout=self.config.timeout)
            self.rate_limiter.update_from_headers(response.headers)
            
            if response.ok:
                return response
            
            # Handle different error codes
            if response.status_code == 429:  # Too Many Requests
                logger.warning("Rate limit exceeded (429). Waiting before retry...")
                time.sleep(self.config.max_retry_delay)
                return self._retry_request(url, retry_count)
            
            elif response.status_code == 500:  # Server Error
                logger.warning(f"Server error (500). Retry {retry_count + 1}/{self.config.max_retries}")
                return self._retry_request(url, retry_count)
            
            elif response.status_code == 503:  # Service Unavailable
                logger.warning(f"Service unavailable (503). Retry {retry_count + 1}/{self.config.max_retries}")
                delay = min(
                    self.config.initial_retry_delay * (self.config.retry_backoff_factor ** retry_count) * 2,
                    self.config.max_retry_delay * 2
                )
                if retry_count < self.config.max_retries:
                    logger.info(f"Waiting {delay:.1f}s before retry...")
                    time.sleep(delay)
                    return self._make_request(url, retry_count + 1)
                else:
                    logger.error(f"Max retries ({self.config.max_retries}) reached for 503 error")
                    return None
            
            elif response.status_code == 400:  # Bad Request
                logger.error(f"Bad request (400): {response.text[:200]}")
                return None
            
            elif response.status_code == 401:  # Unauthorized
                logger.error("Authentication failed (401). Check API key.")
                raise RuntimeError("Invalid API key or unauthorized access")
            
            elif response.status_code == 404:  # Not Found
                logger.warning(f"Abstract not found (404) for URL: {url}")
                return None
            
            else:
                logger.error(f"Unexpected status code {response.status_code}")
                return self._retry_request(url, retry_count)
        
        except requests.Timeout:
            logger.warning(f"Request timeout. Retry {retry_count + 1}/{self.config.max_retries}")
            return self._retry_request(url, retry_count)
        
        except requests.RequestException as e:
            logger.error(f"Request exception: {e}")
            return self._retry_request(url, retry_count)
    
    def _retry_request(self, url: str, retry_count: int) -> Optional[requests.Response]:
        """Handle retry logic with exponential backoff."""
        if retry_count >= self.config.max_retries:
            logger.error(f"Max retries ({self.config.max_retries}) reached")
            return None
        
        delay = min(
            self.config.initial_retry_delay * (self.config.retry_backoff_factor ** retry_count),
            self.config.max_retry_delay
        )
        logger.info(f"Retrying in {delay:.1f}s...")
        time.sleep(delay)
        
        return self._make_request(url, retry_count + 1)
    
    def check_available_views(self, scopus_id: str) -> Dict[str, Any]:
        """
        Check which views are available for a Scopus ID.
        
        Tests different view types (META_ABS, FULL, COMPLETE, REF, ENTITLED)
        to determine which ones are accessible with the current API key.
        
        Args:
            scopus_id: Scopus ID in format "SCOPUS_ID:84950369843" or just "84950369843"
        
        Returns:
            Dictionary with view names as keys and status information as values:
            {
                'META_ABS': {'status_code': 200, 'accessible': True, 'error': None},
                'FULL': {'status_code': 403, 'accessible': False, 'error': '...'},
                ...
            }
        
        Example:
            >>> client = ScopusAbstractClient(config)
            >>> views = client.check_available_views("SCOPUS_ID:84950369843")
            >>> for view, info in views.items():
            ...     if info['accessible']:
            ...         print(f"✓ {view}: Access granted")
            ...     else:
            ...         print(f"✗ {view}: {info['status_code']} - {info.get('error', '')}")
        """
        # Normalize scopus_id format
        if not scopus_id.startswith('SCOPUS_ID:'):
            scopus_id = f"SCOPUS_ID:{scopus_id}"
        
        views = ["META_ABS", "FULL", "COMPLETE", "REF", "ENTITLED"]
        results = {}
        
        url = f"https://api.elsevier.com/content/abstract/scopus_id/{scopus_id}"
        
        for view in views:
            params = {"view": view}
            
            # Make request with rate limiting
            self.rate_limiter.wait_if_needed()
            
            try:
                response = self.session.get(url, headers=self.session.headers, params=params, timeout=self.config.timeout)
                self.rate_limiter.update_from_headers(response.headers)
                
                if response.status_code == 200:
                    results[view] = {
                        'status_code': 200,
                        'accessible': True,
                        'error': None
                    }
                    logger.debug(f"✓ {view}: Access granted")
                else:
                    # Try to extract error message
                    error_msg = None
                    try:
                        error_data = response.json()
                        if 'service-error' in error_data:
                            error_msg = str(error_data['service-error'])
                        elif 'error' in error_data:
                            error_msg = str(error_data['error'])
                    except (ValueError, KeyError):
                        error_msg = response.text[:200] if response.text else None
                    
                    results[view] = {
                        'status_code': response.status_code,
                        'accessible': False,
                        'error': error_msg
                    }
                    logger.debug(f"✗ {view}: {response.status_code} - {error_msg}")
                    
            except Exception as e:
                results[view] = {
                    'status_code': None,
                    'accessible': False,
                    'error': str(e)
                }
                logger.warning(f"Error checking {view}: {e}")
        
        return results
    
    def authenticate(self) -> Dict[str, Any]:
        """
        Authenticate with Scopus API and get entitlement information.
        
        This endpoint returns information about your API key's entitlements,
        including what access levels you have.
        
        Returns:
            Dictionary containing authentication and entitlement information.
            Typically includes:
            - 'authenticate-response': Authentication response data
            - 'entitlement': List of entitlements/access levels
            - Other authentication metadata
        
        Example:
            >>> client = ScopusAbstractClient(config)
            >>> auth_info = client.authenticate()
            >>> print(auth_info)
            >>> # Check entitlements
            >>> if 'entitlement' in auth_info:
            ...     print(f"Entitlements: {auth_info['entitlement']}")
        """
        url = "https://api.elsevier.com/authenticate"
        
        # Make request with rate limiting
        self.rate_limiter.wait_if_needed()
        
        try:
            response = self.session.get(url, headers=self.session.headers, timeout=self.config.timeout)
            self.rate_limiter.update_from_headers(response.headers)
            
            if response.ok:
                try:
                    data = response.json()
                    logger.info("Authentication successful")
                    return data
                except ValueError as e:
                    logger.error(f"Invalid JSON response from authenticate endpoint: {e}")
                    return {'error': 'Invalid JSON response', 'raw_response': response.text[:500]}
            else:
                logger.error(f"Authentication failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    return {'error': f"Status {response.status_code}", 'details': error_data}
                except ValueError:
                    return {'error': f"Status {response.status_code}", 'raw_response': response.text[:500]}
                    
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            return {'error': str(e)}


class ScopusAbstractFetcher:
    """
    Fetcher for individual Scopus abstracts by EID with caching.
    
    This class wraps ScopusAbstractClient with caching functionality.
    It follows the same pattern as other fetchers in the package.
    
    Usage:
        # Simple (auto-loads API key from config)
        fetcher = ScopusAbstractFetcher()
        
        # Fetch a single abstract
        abstract = fetcher.fetch('2-s2.0-85012345678')
        
        # Fetch with custom view and fields
        abstract = fetcher.fetch(
            '2-s2.0-85012345678',
            view='FULL',
            field='citedby-count,prism:doi,dc:title'
        )
        
        # Fetch multiple EIDs
        df = fetcher.provide(['2-s2.0-85012345678', '2-s2.0-85012345679'])
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: str = "~/.cache/scopus/abstracts",
        api_key_dir: str = "~/Documents/dh4pmp/api_keys",
        **kwargs
    ):
        """
        Initialize Scopus abstract fetcher.
        
        Args:
            api_key: Scopus API key (if None, tries to load from yaml)
            cache_dir: Directory for cache files
            api_key_dir: Directory containing API config files (default: ~/Documents/dh4pmp/api_keys)
            **kwargs: Additional configuration:
                - requests_per_second: Rate limit (default: 2.0)
                - max_retries: Retry attempts (default: 3)
                - cache_max_age_days: Cache expiration (default: None/never)
        """
        # Load API key
        if api_key is None:
            api_key = self._load_api_key(api_key_dir)
        
        # Initialize configuration
        config = ScopusConfig(
            api_key=api_key,
            requests_per_second=kwargs.get('requests_per_second', 2.0),
            max_retries=kwargs.get('max_retries', 3),
        )
        
        # Initialize client and cache
        self.client = ScopusAbstractClient(config)
        self.cache = LocalCache(
            cache_dir=cache_dir,
            compression=True,
            max_age_days=kwargs.get('cache_max_age_days', None)
        )
        
        logger.info(f"Initialized Scopus abstract fetcher with cache at {self.cache.cache_dir}")
    
    def _load_api_key(self, api_key_dir: str) -> str:
        """
        Load API key from YAML config file.
        
        File: scopus.yaml with required 'X-ELS-APIKey' field
        """
        api_key_dir = Path(api_key_dir).expanduser()
        key_paths = [
            Path('.') / 'scopus.yaml',
            api_key_dir / 'scopus.yaml',
        ]
        
        for path in key_paths:
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        key_data = yaml.safe_load(f)
                        
                        if key_data and 'X-ELS-APIKey' in key_data:
                            api_key = key_data['X-ELS-APIKey']
                            if api_key:  # Make sure it's not empty
                                logger.info(f"Loaded Scopus API key from {path}")
                                return api_key
                except Exception as e:
                    logger.warning(f"Error loading {path}: {e}")
        
        raise FileNotFoundError(
            f"Scopus API key not found. Create one of:\n"
            f"  - ./scopus.yaml\n"
            f"  - {api_key_dir}/scopus.yaml\n\n"
            f"With content:\n"
            f"  X-ELS-APIKey: your_api_key_here\n\n"
            f"Get your API key from: https://dev.elsevier.com/"
        )
    
    def fetch(
        self, 
        eid: str, 
        force_refresh: bool = False,
        view: str = 'META_ABS',
        field: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch abstract data for a Scopus EID.
        
        Args:
            eid: Scopus EID (e.g., '2-s2.0-85012345678')
            force_refresh: If True, bypass cache and fetch fresh data
            view: Response view type (default: 'META_ABS')
                 Options: 'META_ABS', 'FULL', 'STANDARD', 'REF', 'CITESCORE'
            field: Specific fields to return (comma-separated, optional)
                  Example: 'citedby-count,prism:doi,dc:title'
        
        Returns:
            Full abstract data dict, or None if not found/error
            
        Example:
            >>> fetcher = ScopusAbstractFetcher()
            >>> abstract = fetcher.fetch('2-s2.0-85012345678')
            >>> if abstract:
            ...     # Access data
            ...     title = abstract.get('abstracts-retrieval-response', {}).get('coredata', {}).get('dc:title')
            ...     doi = abstract.get('abstracts-retrieval-response', {}).get('coredata', {}).get('prism:doi')
        """
        # Build cache key that includes view and field
        cache_key = eid
        if view != 'META_ABS' or field:
            cache_key = f"{eid}|view={view}"
            if field:
                cache_key += f"|field={field}"
        
        # Check cache first
        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for EID: {eid}")
                # Cache stores as DataFrame with 'data' column
                if isinstance(cached, pd.DataFrame) and len(cached) > 0:
                    data = cached.iloc[0].get('data')
                    if data is not None:
                        return data
        
        # Fetch from API
        logger.info(f"Fetching abstract for EID: {eid}")
        data = self.client.fetch_abstract(eid, view=view, field=field)
        
        if data is None:
            return None
        
        # Cache it
        df = pd.DataFrame([{
            'ID': cache_key,
            'data': data
        }])
        self.cache.store(cache_key, df)
        
        return data
    
    def provide(
        self, 
        eids: List[str], 
        force_refresh: bool = False,
        view: str = 'META_ABS',
        field: Optional[str] = None,
        show_progress: bool = True
    ) -> pd.DataFrame:
        """
        Fetch multiple EIDs.
        
        Args:
            eids: List of Scopus EIDs
            force_refresh: If True, bypass cache for all EIDs
            view: Response view type (default: 'META_ABS')
            field: Specific fields to return (comma-separated, optional)
            show_progress: If True, show progress bar (default: True)
        
        Returns:
            DataFrame with columns: ID, data
            - ID: The EID (with view/field suffix if custom)
            - data: The full abstract data dict
        """
        # Try to import tqdm for progress bar
        if show_progress:
            try:
                from tqdm.auto import tqdm
                tqdm_available = True
            except ImportError:
                tqdm_available = False
                logger.debug("tqdm not available - install with: pip install tqdm")
        else:
            tqdm_available = False
        
        results = []
        
        # Use tqdm if available
        eid_iter = tqdm(eids, desc="Fetching abstracts", unit="abstract") if tqdm_available else eids
        
        for eid in eid_iter:
            data = self.fetch(eid, force_refresh=force_refresh, view=view, field=field)
            if data is not None:
                # Build cache key for ID
                cache_key = eid
                if view != 'META_ABS' or field:
                    cache_key = f"{eid}|view={view}"
                    if field:
                        cache_key += f"|field={field}"
                results.append({'ID': cache_key, 'data': data})
        
        if not results:
            return pd.DataFrame(columns=['ID', 'data'])
        
        return pd.DataFrame(results)
    
    def check_available_views(self, scopus_id: str) -> Dict[str, Any]:
        """
        Check which views are available for a Scopus ID.
        
        Convenience method that calls the client's check_available_views method.
        
        Args:
            scopus_id: Scopus ID in format "SCOPUS_ID:84950369843" or just "84950369843"
        
        Returns:
            Dictionary with view names as keys and status information as values.
        
        Example:
            >>> fetcher = ScopusAbstractFetcher()
            >>> views = fetcher.check_available_views("SCOPUS_ID:84950369843")
            >>> for view, info in views.items():
            ...     if info['accessible']:
            ...         print(f"✓ {view}: Access granted")
        """
        return self.client.check_available_views(scopus_id)
    
    def authenticate(self) -> Dict[str, Any]:
        """
        Authenticate with Scopus API and get entitlement information.
        
        Convenience method that calls the client's authenticate method.
        
        Returns:
            Dictionary containing authentication and entitlement information.
        
        Example:
            >>> fetcher = ScopusAbstractFetcher()
            >>> auth_info = fetcher.authenticate()
            >>> print(auth_info)
            >>> # Check entitlements
            >>> if 'entitlement' in auth_info:
            ...     print(f"Entitlements: {auth_info['entitlement']}")
        """
        return self.client.authenticate()
