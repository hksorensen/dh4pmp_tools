"""Main fetcher class for arXiv metadata."""

import json
import gzip
import os
from pathlib import Path
from typing import Iterator, Callable, Any
from datetime import datetime, timedelta
import requests
from tqdm.auto import tqdm
import pandas as pd

from .filters import (
    Category,
    normalize_categories,
    normalize_years,
    matches_categories,
)
from .exceptions import DownloadError, CacheError, ParseError


class ArxivMetadata:
    """Main class for fetching and filtering arXiv metadata.
    
    This class handles downloading metadata from arXiv's S3 bucket,
    caching it locally, and providing convenient filtering methods.
    
    Attributes:
        cache_dir: Directory for storing cached metadata
        use_cache: Whether to use local cache
        cache_expiry_days: Number of days before cache expires
    """
    
    # arXiv metadata sources:
    # 1. Kaggle dataset: https://www.kaggle.com/datasets/Cornell-University/arxiv
    # 2. AWS S3 bucket: s3://arxiv/arxiv/arxiv-metadata-oai-snapshot.json
    # 3. Direct download: https://www.kaggle.com/datasets/download/Cornell-University/arxiv (requires auth)
    #
    # Note: Automatic download is not implemented to avoid API key management.
    # Users should download manually or use kagglehub with their own credentials.
    
    def __init__(
        self,
        cache_dir: str = "~/.cache/arxiv",
        use_cache: bool = True,
        cache_expiry_days: int = 30,
    ):
        """Initialize ArxivMetadata fetcher.
        
        Args:
            cache_dir: Directory for caching downloaded metadata (default: ~/.cache/arxiv)
            use_cache: Whether to use local cache
            cache_expiry_days: Days before cache expires
        """
        self.cache_dir = Path(cache_dir).expanduser()
        self.use_cache = use_cache
        self.cache_expiry_days = cache_expiry_days
        
        if self.use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self) -> Path:
        """Get path to cached metadata file."""
        return self.cache_dir / "arxiv_metadata.jsonl"
    
    def _is_cache_valid(self) -> bool:
        """Check if cached metadata is still valid."""
        if not self.use_cache:
            return False
        
        cache_path = self._get_cache_path()
        if not cache_path.exists():
            return False
        
        # Check if cache has expired
        cache_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        expiry_time = cache_time + timedelta(days=self.cache_expiry_days)
        
        return datetime.now() < expiry_time
    
    def clear_cache(self):
        """Clear cached metadata."""
        cache_path = self._get_cache_path()
        if cache_path.exists():
            cache_path.unlink()
            print(f"Cache cleared: {cache_path}")
    
    def _get_dataset_version(self) -> dict:
        """Get version information about the arXiv dataset from Kaggle.
        
        Returns:
            Dictionary with 'version' and 'lastUpdated' keys, or empty dict if unavailable
        """
        try:
            import requests
            
            # Use Kaggle API to get dataset metadata
            api_url = "https://www.kaggle.com/api/v1/datasets/view/Cornell-University/arxiv"
            
            # Try to use credentials if available
            username = os.environ.get('KAGGLE_USERNAME')
            key = os.environ.get('KAGGLE_KEY')
            
            if username and key:
                response = requests.get(api_url, auth=(username, key))
            else:
                # Try without auth (may have limited info)
                response = requests.get(api_url)
            
            if response.ok:
                data = response.json()
                return {
                    'version': data.get('currentVersionNumber', 'unknown'),
                    'lastUpdated': data.get('lastUpdated', 'unknown'),
                    'title': data.get('title', ''),
                }
            
        except Exception as e:
            # Silently fail - version info is nice to have but not critical
            pass
        
        return {}
    
    def _save_version_info(self, cache_path: Path):
        """Save version info alongside cached file.
        
        Args:
            cache_path: Path to cached metadata file
        """
        version_info = self._get_dataset_version()
        if version_info:
            version_file = cache_path.parent / 'version.json'
            try:
                import json
                with open(version_file, 'w') as f:
                    json.dump({
                        'dataset_version': version_info.get('version'),
                        'last_updated': version_info.get('lastUpdated'),
                        'cached_at': datetime.now().isoformat(),
                    }, f, indent=2)
            except Exception:
                pass  # Not critical
    
    def _check_version_info(self) -> dict:
        """Check version info of cached file.
        
        Returns:
            Dictionary with cached version info, or empty dict if unavailable
        """
        version_file = self.cache_dir / 'version.json'
        if version_file.exists():
            try:
                import json
                with open(version_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def get_cache_info(self) -> dict:
        """Get information about the cached dataset.
        
        Returns:
            Dictionary with cache status, version, size, age, etc.
        """
        cache_path = self._get_cache_path()
        
        info = {
            'cache_exists': cache_path.exists(),
            'cache_path': str(cache_path),
            'cache_valid': self._is_cache_valid(),
        }
        
        if cache_path.exists():
            stat = cache_path.stat()
            info['size_gb'] = stat.st_size / (1024**3)
            info['modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            
            # Calculate age
            age = datetime.now() - datetime.fromtimestamp(stat.st_mtime)
            info['age_days'] = age.days
            
            # Check version info if available
            version_info = self._check_version_info()
            if version_info:
                info['dataset_version'] = version_info.get('dataset_version')
                info['last_updated'] = version_info.get('last_updated')
                info['cached_at'] = version_info.get('cached_at')
        
        return info
    
    def _setup_kaggle_credentials(self) -> bool:
        """Setup Kaggle credentials from various sources.
        
        Looks for credentials in order:
        1. Environment variables (KAGGLE_USERNAME, KAGGLE_KEY)
        2. ~/.kaggle/kaggle.json
        3. Custom path from KAGGLE_CONFIG_DIR env variable
        
        Returns:
            True if credentials found and set, False otherwise
        """
        import os
        
        # Check if already set in environment
        if os.environ.get('KAGGLE_USERNAME') and os.environ.get('KAGGLE_KEY'):
            return True
        
        # Try standard Kaggle location
        kaggle_json = Path('~/.kaggle/kaggle.json').expanduser()
        
        # Try custom location from environment
        if not kaggle_json.exists():
            config_dir = os.environ.get('KAGGLE_CONFIG_DIR')
            if config_dir:
                kaggle_json = Path(config_dir) / 'kaggle.json'
        
        if kaggle_json.exists():
            try:
                import json
                creds = json.loads(kaggle_json.read_text())
                os.environ['KAGGLE_USERNAME'] = creds['username']
                os.environ['KAGGLE_KEY'] = creds['key']
                return True
            except Exception as e:
                print(f"Warning: Could not read Kaggle credentials from {kaggle_json}: {e}")
                return False
        
        return False
    
    def download_metadata(self, force: bool = False, stream_process: bool = True) -> Path:
        """Download arXiv metadata snapshot from Kaggle.
        
        This downloads the complete metadata snapshot and optionally processes
        it on-the-fly to save only filtered results.
        
        Args:
            force: Force re-download even if cache is valid
            stream_process: If True, process and filter during download (memory efficient)
            
        Returns:
            Path to downloaded/cached metadata file
            
        Raises:
            DownloadError: If download fails or Kaggle credentials not found
        """
        cache_path = self._get_cache_path()
        
        # Check if we can use cache
        if not force and self._is_cache_valid():
            print(f"Using cached metadata from {cache_path}")
            return cache_path
        
        # Check if cache directory exists and is writable
        if not cache_path.parent.exists():
            print(f"Cache directory does not exist: {cache_path.parent}")
            print("Creating cache directory...")
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                print(f"✓ Created: {cache_path.parent}")
            except Exception as e:
                raise DownloadError(f"Cannot create cache directory {cache_path.parent}: {e}")
        
        if not os.access(cache_path.parent, os.W_OK):
            raise DownloadError(
                f"Cache directory is not writable: {cache_path.parent}\n"
                f"Please check permissions or choose a different cache_dir"
            )
        
        print("Downloading arXiv metadata snapshot from Kaggle...")
        print("Note: File is approximately 1.5 GB and will take several minutes to download.")
        
        # Setup Kaggle credentials
        if not self._setup_kaggle_credentials():
            raise DownloadError(
                "Kaggle credentials not found. Please set up credentials using one of:\n\n"
                "1. Create ~/.kaggle/kaggle.json with:\n"
                "   {\"username\":\"your_username\",\"key\":\"your_api_key\"}\n\n"
                "2. Set environment variables:\n"
                "   export KAGGLE_USERNAME=your_username\n"
                "   export KAGGLE_KEY=your_api_key\n\n"
                "3. Set KAGGLE_CONFIG_DIR to directory containing kaggle.json\n\n"
                "Get your API key from: https://www.kaggle.com/settings/account\n\n"
                "Alternatively, download manually from:\n"
                "https://www.kaggle.com/datasets/Cornell-University/arxiv\n"
                "and place at: " + str(cache_path)
            )
        
        try:
            import kagglehub
        except ImportError:
            raise DownloadError(
                "kagglehub not installed. Install with:\n"
                "pip install kagglehub\n\n"
                "Or download manually from:\n"
                "https://www.kaggle.com/datasets/Cornell-University/arxiv"
            )
        
        try:
            print("Downloading dataset via kagglehub...")
            dataset_path = kagglehub.dataset_download('Cornell-University/arxiv')
            source_file = Path(dataset_path) / 'arxiv-metadata-oai-snapshot.json'
            
            if not source_file.exists():
                raise DownloadError(f"Downloaded dataset but file not found at {source_file}")
            
            # Copy to cache location
            print(f"Copying to cache: {cache_path}")
            import shutil
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source_file, cache_path)
            
            # Save version information
            self._save_version_info(cache_path)
            
            print(f"✓ Metadata cached at: {cache_path}")
            
            # Show version info if available
            version_info = self._check_version_info()
            if version_info.get('dataset_version'):
                print(f"  Dataset version: {version_info['dataset_version']}")
            
            return cache_path
            
        except Exception as e:
            raise DownloadError(f"Failed to download metadata: {e}")
    
    def _get_metadata_path(self) -> Path:
        """Get path to metadata file, checking cache and environment."""
        import os
        
        # Check environment variable first
        env_path = os.environ.get('ARXIV_METADATA_PATH')
        if env_path:
            path = Path(env_path).expanduser()
            if path.exists():
                return path
        
        # Check cache
        cache_path = self._get_cache_path()
        if cache_path.exists():
            return cache_path
        
        # Try to download
        try:
            return self.download_metadata()
        except DownloadError:
            raise DownloadError(
                f"No metadata file found. Please:\n"
                f"1. Download arxiv-metadata-oai-snapshot.json\n"
                f"2. Place it at: {cache_path}\n"
                f"   OR set ARXIV_METADATA_PATH environment variable"
            )
    
    def _parse_year_from_id(self, arxiv_id: str) -> int:
        """Extract year from arXiv ID.
        
        Args:
            arxiv_id: arXiv identifier (e.g., "2301.12345" or "math/0601001")
            
        Returns:
            Year as integer
        """
        if '/' in arxiv_id:
            # Old format: category/YYMMNNN
            year_str = arxiv_id.split('/')[1][:2]
            year = int(year_str)
            return 1900 + year if year > 50 else 2000 + year
        else:
            # New format: YYMM.NNNNN
            year_str = arxiv_id[:2]
            year = int(year_str)
            return 1900 + year if year > 50 else 2000 + year
    
    def _process_paper(self, paper: dict) -> dict:
        """Process a paper entry, adding computed fields.
        
        Args:
            paper: Raw paper metadata dict
            
        Returns:
            Processed paper dict with additional fields
        """
        # Rename id to arxiv_id
        if 'id' in paper:
            paper['arxiv_id'] = paper.pop('id')
        
        # Extract year
        if 'arxiv_id' in paper:
            paper['year'] = self._parse_year_from_id(paper['arxiv_id'])
        
        # Parse categories
        if 'categories' in paper and isinstance(paper['categories'], str):
            paper['categories'] = paper['categories'].split()
        
        # Set primary category
        if 'categories' in paper and len(paper['categories']) > 0:
            paper['primary_category'] = paper['categories'][0]
        
        # Add derived fields
        if 'versions' in paper:
            paper['num_versions'] = len(paper['versions'])
        
        if 'authors_parsed' in paper:
            paper['num_authors'] = len(paper['authors_parsed'])
        
        return paper
    
    def stream(
        self,
        categories: Category | list[str] | str | None = None,
        years: int | range | list[int] | None = None,
        min_authors: int | None = None,
        max_authors: int | None = None,
        has_doi: bool | None = None,
        filter_fn: Callable[[dict], bool] | None = None,
    ) -> Iterator[dict]:
        """Stream papers one at a time (memory efficient).
        
        This method processes the metadata file line by line, yielding
        papers that match the specified filters. This is memory efficient
        for large datasets.
        
        Args:
            categories: Category filter (enum, string, or list)
            years: Year filter (int, range, or list)
            min_authors: Minimum number of authors
            max_authors: Maximum number of authors
            has_doi: Filter for papers with DOI
            filter_fn: Custom filter function taking paper dict
            
        Yields:
            Paper metadata dicts matching the filters
            
        Example:
            >>> fetcher = ArxivMetadata()
            >>> for paper in fetcher.stream(categories=Category.MATH, years=2024):
            ...     print(paper['title'])
        """
        metadata_path = self._get_metadata_path()
        
        # Normalize inputs
        cat_list = normalize_categories(categories)
        year_list = normalize_years(years)
        
        # Determine if we're reading gzipped or plain file
        open_fn = gzip.open if metadata_path.suffix == '.gz' else open
        mode = 'rt' if metadata_path.suffix == '.gz' else 'r'
        
        with open_fn(metadata_path, mode, encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                
                try:
                    paper = json.loads(line)
                except json.JSONDecodeError as e:
                    continue  # Skip malformed lines
                
                # Process paper
                paper = self._process_paper(paper)
                
                # Apply filters
                if cat_list and not matches_categories(paper, cat_list):
                    continue
                
                if year_list and paper.get('year') not in year_list:
                    continue
                
                if min_authors is not None:
                    num_authors = paper.get('num_authors', len(paper.get('authors_parsed', [])))
                    if num_authors < min_authors:
                        continue
                
                if max_authors is not None:
                    num_authors = paper.get('num_authors', len(paper.get('authors_parsed', [])))
                    if num_authors > max_authors:
                        continue
                
                if has_doi is not None:
                    paper_has_doi = bool(paper.get('doi', '').strip())
                    if paper_has_doi != has_doi:
                        continue
                
                if filter_fn and not filter_fn(paper):
                    continue
                
                yield paper
    
    def download_and_fetch(
        self,
        categories: Category | list[str] | str | None = None,
        years: int | range | list[int] | None = None,
        min_authors: int | None = None,
        max_authors: int | None = None,
        has_doi: bool | None = None,
        filter_fn: Callable[[dict], bool] | None = None,
        columns: list[str] | None = None,
        limit: int | None = None,
        show_progress: bool = True,
        force_download: bool = False,
    ) -> pd.DataFrame:
        """Download from Kaggle and process/filter on-the-fly (memory efficient).
        
        This method downloads the metadata from Kaggle and processes it line-by-line,
        applying filters during download rather than after. This is much more memory
        efficient than downloading the full file first.
        
        Args:
            categories: Category filter (Category enum, string, or list)
            years: Year filter (int, range, or list of ints)
            min_authors: Minimum number of authors
            max_authors: Maximum number of authors
            has_doi: Filter for papers with DOI (True/False)
            filter_fn: Custom filter function taking paper dict and returning bool
            columns: List of columns to include (None for all)
            limit: Maximum number of papers to return
            show_progress: Whether to show progress bar
            force_download: Force fresh download even if cache exists
            
        Returns:
            DataFrame with filtered papers
            
        Example:
            >>> fetcher = ArxivMetadata()
            >>> # Download and filter in one step (memory efficient)
            >>> df = fetcher.download_and_fetch(
            ...     categories=Category.MATH,
            ...     years=range(2020, 2025),
            ...     min_authors=2
            ... )
        """
        # Setup Kaggle credentials
        if not self._setup_kaggle_credentials():
            raise DownloadError(
                "Kaggle credentials required. See download_metadata() for setup instructions."
            )
        
        try:
            import kagglehub
        except ImportError:
            raise DownloadError("kagglehub not installed. Install with: pip install kagglehub")
        
        print("Downloading and processing arXiv metadata from Kaggle...")
        print("Filtering on-the-fly (memory efficient)")
        
        # Download to temporary location
        try:
            dataset_path = kagglehub.dataset_download('Cornell-University/arxiv')
            source_file = Path(dataset_path) / 'arxiv-metadata-oai-snapshot.json'
            
            if not source_file.exists():
                raise DownloadError(f"Downloaded dataset but file not found at {source_file}")
            
            # Normalize filters
            cat_list = normalize_categories(categories)
            year_list = normalize_years(years)
            
            # Process line-by-line with filters
            papers = []
            
            with open(source_file, 'r', encoding='utf-8') as f:
                iterator = f
                if show_progress:
                    # Estimate total lines for progress bar
                    iterator = tqdm(f, desc="Processing papers", unit=" papers")
                
                for line in iterator:
                    if not line.strip():
                        continue
                    
                    try:
                        paper = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    
                    # Process paper
                    paper = self._process_paper(paper)
                    
                    # Apply filters (same as stream method)
                    if cat_list and not matches_categories(paper, cat_list):
                        continue
                    
                    if year_list and paper.get('year') not in year_list:
                        continue
                    
                    if min_authors is not None:
                        num_authors = paper.get('num_authors', len(paper.get('authors_parsed', [])))
                        if num_authors < min_authors:
                            continue
                    
                    if max_authors is not None:
                        num_authors = paper.get('num_authors', len(paper.get('authors_parsed', [])))
                        if num_authors > max_authors:
                            continue
                    
                    if has_doi is not None:
                        paper_has_doi = bool(paper.get('doi', '').strip())
                        if paper_has_doi != has_doi:
                            continue
                    
                    if filter_fn and not filter_fn(paper):
                        continue
                    
                    # Passed all filters
                    papers.append(paper)
                    
                    if limit and len(papers) >= limit:
                        break
            
            # Convert to DataFrame
            if not papers:
                return pd.DataFrame()
            
            df = pd.DataFrame(papers)
            
            # Select columns if specified
            if columns:
                available_cols = [c for c in columns if c in df.columns]
                df = df[available_cols]
            
            print(f"\n✓ Downloaded and filtered: {len(df)} papers matched criteria")
            
            # Also cache the full file for future use
            cache_path = self._get_cache_path()
            if not cache_path.exists():
                print(f"Caching full metadata to: {cache_path}")
                import shutil
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(source_file, cache_path)
                
                # Save version information
                self._save_version_info(cache_path)
                
                version_info = self._check_version_info()
                if version_info.get('dataset_version'):
                    print(f"  Dataset version: {version_info['dataset_version']}")
            
            return df
            
        except Exception as e:
            raise DownloadError(f"Failed to download and process metadata: {e}")
    
    def fetch(
        self,
        categories: Category | list[str] | str | None = None,
        years: int | range | list[int] | None = None,
        min_authors: int | None = None,
        max_authors: int | None = None,
        has_doi: bool | None = None,
        filter_fn: Callable[[dict], bool] | None = None,
        columns: list[str] | None = None,
        limit: int | None = None,
        show_progress: bool = True,
    ) -> pd.DataFrame:
        """Fetch arXiv metadata as a pandas DataFrame.
        
        Downloads and filters metadata according to specified criteria.
        Results are returned as a pandas DataFrame for easy analysis.
        
        Args:
            categories: Category filter (Category enum, string, or list)
            years: Year filter (int, range, or list of ints)
            min_authors: Minimum number of authors
            max_authors: Maximum number of authors
            has_doi: Filter for papers with DOI (True/False)
            filter_fn: Custom filter function taking paper dict and returning bool
            columns: List of columns to include (None for all)
            limit: Maximum number of papers to return
            show_progress: Whether to show progress bar
            
        Returns:
            DataFrame with filtered papers
            
        Example:
            >>> fetcher = ArxivMetadata()
            >>> df = fetcher.fetch(
            ...     categories=Category.MATH,
            ...     years=range(2020, 2025),
            ...     min_authors=2
            ... )
        """
        papers = []
        
        # Stream papers and collect
        stream = self.stream(
            categories=categories,
            years=years,
            min_authors=min_authors,
            max_authors=max_authors,
            has_doi=has_doi,
            filter_fn=filter_fn,
        )
        
        # Add progress bar if requested
        if show_progress:
            stream = tqdm(stream, desc="Filtering papers")
        
        for paper in stream:
            papers.append(paper)
            if limit and len(papers) >= limit:
                break
        
        # Convert to DataFrame
        if not papers:
            return pd.DataFrame()
        
        df = pd.DataFrame(papers)
        
        # Select columns if specified
        if columns:
            available_cols = [c for c in columns if c in df.columns]
            df = df[available_cols]
        
        return df
    
    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about the metadata.
        
        Returns:
            Dictionary with statistics like total papers, categories, years
        """
        metadata_path = self._get_metadata_path()
        
        stats = {
            'total_papers': 0,
            'categories': set(),
            'years': set(),
            'cache_path': str(metadata_path),
            'cache_valid': self._is_cache_valid(),
        }
        
        # Sample first 10000 papers for statistics
        for i, paper in enumerate(self.stream()):
            if i >= 10000:
                break
            
            stats['total_papers'] += 1
            
            if 'categories' in paper:
                for cat in paper['categories']:
                    stats['categories'].add(cat.split('.')[0])  # Add main category
            
            if 'year' in paper:
                stats['years'].add(paper['year'])
        
        stats['categories'] = sorted(stats['categories'])
        stats['years'] = sorted(stats['years'])
        
        return stats
