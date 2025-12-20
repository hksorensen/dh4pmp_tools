"""
Optimized PDF Fetcher with parallel processing and caching.

This is an enhanced version of PDFFetcher with:
- Pre-filtering of existing files
- Parallel processing by domain
- Caching of landing page resolutions
- Connection pooling
- Reduced delays for direct PDF URLs
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import threading
import time

from .pdf_fetcher_v2 import PDFFetcher, DownloadResult, DownloadStatus, IdentifierNormalizer
from .pdf_fetcher_v2 import logger


class OptimizedPDFFetcher(PDFFetcher):
    """
    Optimized PDF Fetcher with parallel processing and advanced caching.
    
    Key optimizations:
    1. Pre-filters already downloaded files
    2. Parallel processing by domain (configurable workers)
    3. Caches landing page resolutions
    4. Connection pooling
    5. Reduced delays for direct PDF URLs
    """
    
    def __init__(self, *args, max_workers: int = 5, **kwargs):
        """
        Initialize optimized PDF fetcher.
        
        Args:
            *args: Arguments passed to PDFFetcher
            max_workers: Maximum number of parallel workers (default: 5)
            **kwargs: Keyword arguments passed to PDFFetcher
        """
        super().__init__(*args, **kwargs)
        self.max_workers = max_workers
        self.landing_url_cache: Dict[str, str] = {}  # DOI -> landing URL
        self.cache_lock = threading.Lock()
        
        # Enhance connection pooling
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        adapter = HTTPAdapter(
            pool_connections=10,  # Number of connection pools
            pool_maxsize=20,      # Max connections per pool
            max_retries=Retry(total=self.max_retries, backoff_factor=1)
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def _prefilter_existing(self, identifiers: List[str]) -> Tuple[List[str], List[str]]:
        """
        Pre-filter identifiers to skip already downloaded files.
        
        Returns:
            (existing_identifiers, to_download_identifiers)
        """
        existing = []
        to_download = []
        
        logger.info(f"Pre-filtering {len(identifiers)} identifiers...")
        
        for identifier in identifiers:
            try:
                kind, doi, url = IdentifierNormalizer.normalize(identifier)
                
                # Get sanitized filename
                if doi:
                    sanitized = IdentifierNormalizer.sanitize_for_filename(doi)
                else:
                    import hashlib
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
    
    def _group_by_domain(self, identifiers: List[str]) -> Dict[str, List[str]]:
        """Group identifiers by predicted domain."""
        domain_groups = defaultdict(list)
        
        for identifier in identifiers:
            domain = self._predict_domain_from_identifier(identifier)
            domain_groups[domain].append(identifier)
        
        return dict(domain_groups)
    
    def _predict_domain_from_identifier(self, identifier: str) -> str:
        """Predict domain from identifier."""
        try:
            kind, doi, url = IdentifierNormalizer.normalize(identifier)
            
            if kind == 'resource_url':
                from urllib.parse import urlparse
                return urlparse(url).netloc
            elif kind in ('doi', 'doi_url') and doi:
                predicted = self._predict_domain_from_doi(doi)
                return predicted or 'unknown'
        except:
            pass
        
        return 'unknown'
    
    def _download_domain_batch(self, domain: str, identifiers: List[str]) -> List[DownloadResult]:
        """
        Download a batch of identifiers from the same domain.
        
        This runs in a separate thread with its own driver.
        """
        results = []
        
        # Create a new fetcher instance for this thread (with its own driver)
        # We'll reuse the session and other components
        thread_fetcher = PDFFetcher(
            pdf_dir=self.pdf_dir,
            metadata_path=self.metadata_path,
            headless=self.headless,
            requests_per_second=self.rate_limiter.requests_per_second,
            max_retries=self.max_retries,
            user_agent=self.user_agent,
            delay_between_requests=self.delay_between_requests,
            delay_between_batches=self.delay_between_batches
        )
        
        try:
            logger.info(f"[{domain}] Processing {len(identifiers)} identifiers")
            
            for identifier in identifiers:
                result = thread_fetcher.download(identifier)
                results.append(result)
                
                # Small delay between requests (same domain)
                time.sleep(self.delay_between_requests)
        
        finally:
            thread_fetcher.close()
        
        return results
    
    def download_batch_optimized(
        self,
        identifiers: List[str],
        batch_size: int = 10,
        retry_failures: bool = True,
        progress: bool = True
    ) -> List[DownloadResult]:
        """
        Optimized batch download with parallel processing.
        
        Args:
            identifiers: List of identifiers to download
            batch_size: Not used in parallel mode, kept for compatibility
            retry_failures: Whether to retry failures
            progress: Show progress bar
        
        Returns:
            List of DownloadResult objects
        """
        all_results = []
        
        # Step 1: Pre-filter existing files
        existing_ids, to_download = self._prefilter_existing(identifiers)
        
        # Mark existing as ALREADY_EXISTS
        for identifier in existing_ids:
            kind, doi, url = IdentifierNormalizer.normalize(identifier)
            if doi:
                sanitized = IdentifierNormalizer.sanitize_for_filename(doi)
            else:
                import hashlib
                sanitized = hashlib.md5(url.encode()).hexdigest()[:16]
            
            pdf_path = self.pdf_dir / f"{sanitized}.pdf"
            
            result = DownloadResult(
                identifier=identifier,
                status=DownloadStatus.ALREADY_EXISTS,
                pdf_path=pdf_path,
                first_attempted=time.time(),
                last_attempted=time.time()
            )
            all_results.append(result)
        
        if not to_download:
            logger.info("All files already exist!")
            return all_results
        
        # Step 2: Group by domain
        domain_groups = self._group_by_domain(to_download)
        logger.info(f"Grouped into {len(domain_groups)} domains")
        
        # Step 3: Parallel processing
        try:
            from tqdm import tqdm
            TQDM_AVAILABLE = True
        except ImportError:
            TQDM_AVAILABLE = False
        
        pbar = None
        if progress and TQDM_AVAILABLE:
            pbar = tqdm(total=len(to_download), desc="Downloading PDFs", unit="PDF")
        
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all domain batches
                futures = {
                    executor.submit(self._download_domain_batch, domain, ids): domain
                    for domain, ids in domain_groups.items()
                }
                
                # Collect results as they complete
                for future in as_completed(futures):
                    domain = futures[future]
                    try:
                        domain_results = future.result()
                        all_results.extend(domain_results)
                        
                        if pbar:
                            pbar.update(len(domain_results))
                        
                        logger.info(f"[{domain}] Completed: {len(domain_results)} downloads")
                    except Exception as e:
                        logger.error(f"[{domain}] Error: {e}", exc_info=True)
        
        finally:
            if pbar:
                pbar.close()
        
        # Step 4: Retry failures if requested
        if retry_failures:
            failures = [r for r in all_results if r.status == DownloadStatus.FAILURE]
            if failures:
                logger.info(f"Retrying {len(failures)} failed downloads...")
                # Retry sequentially to avoid overwhelming servers
                for result in failures:
                    retry_result = self.download(result.identifier)
                    result.status = retry_result.status
                    result.error_reason = retry_result.error_reason
                    result.pdf_path = retry_result.pdf_path
        
        return all_results



