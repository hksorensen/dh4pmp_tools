"""
Postponed Domains Cache

Tracks domains and DOI prefixes that hit Cloudflare or other access issues.
Allows batch pre-filtering to skip known problematic sources.

Uses db_utils for persistent storage between runs.
"""

import logging
from typing import List, Set, Tuple, Optional, Dict, Any
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path

logger = logging.getLogger(__name__)


class PostponedDomainsCache:
    """
    Cache for domains and DOI prefixes that should be postponed.

    Features:
    - Track blocked domains (e.g., 'cloudflare-protected.com')
    - Track blocked DOI prefixes (e.g., '10.1234')
    - Persist to SQLite database between runs
    - Pre-filter batches to skip known blocked sources
    - Extract blocked domains from DownloadResults

    Uses db_utils SQLiteTableStorage for persistence.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize postponed domains cache.

        Args:
            db_path: Path to SQLite database file (default: ~/.cache/pdffetcher/postponed_domains.db)
        """
        if db_path is None:
            # Use global cache directory
            cache_dir = Path.home() / ".cache" / "pdffetcher"
            cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(cache_dir / "postponed_domains.db")

        self.db_path = Path(db_path)

        # In-memory sets for fast lookups
        self.blocked_domains: Set[str] = set()
        self.blocked_doi_prefixes: Set[str] = set()
        self.blocked_papers: Set[str] = set()  # Individual papers that timeout/hang

        # Initialize database storage
        self._init_storage()

        # Load existing blocked domains/prefixes
        self._load_from_db()

    def _init_storage(self):
        """Initialize database storage using db_utils."""
        try:
            # Import db_utils from packages
            import sys
            db_utils_path = Path(__file__).parent.parent.parent / "db_utils"
            if str(db_utils_path) not in sys.path:
                sys.path.insert(0, str(db_utils_path))

            from db_utils import SQLiteTableStorage

            # Domain storage
            self.domain_storage = SQLiteTableStorage(
                db_path=str(self.db_path),
                table_name='postponed_domains',
                column_ID='domain',
                ID_type=str,
                table_layout={
                    'domain': 'TEXT PRIMARY KEY',
                    'reason': 'TEXT',
                    'first_detected': 'TEXT',
                    'last_detected': 'TEXT',
                    'detection_count': 'INTEGER DEFAULT 1'
                }
            )

            # DOI prefix storage
            self.prefix_storage = SQLiteTableStorage(
                db_path=str(self.db_path),
                table_name='postponed_doi_prefixes',
                column_ID='prefix',
                ID_type=str,
                table_layout={
                    'prefix': 'TEXT PRIMARY KEY',
                    'reason': 'TEXT',
                    'first_detected': 'TEXT',
                    'last_detected': 'TEXT',
                    'detection_count': 'INTEGER DEFAULT 1'
                }
            )

            # Individual paper storage (for papers that hang/timeout)
            self.paper_storage = SQLiteTableStorage(
                db_path=str(self.db_path),
                table_name='postponed_papers',
                column_ID='identifier',
                ID_type=str,
                table_layout={
                    'identifier': 'TEXT PRIMARY KEY',
                    'reason': 'TEXT',
                    'first_detected': 'TEXT',
                    'last_detected': 'TEXT',
                    'detection_count': 'INTEGER DEFAULT 1'
                }
            )

            logger.info(f"Initialized postponed domains cache: {self.db_path}")

        except ImportError as e:
            logger.warning(f"db_utils not available, using in-memory cache only: {e}")
            self.domain_storage = None
            self.prefix_storage = None
            self.paper_storage = None

    def _load_from_db(self):
        """Load existing blocked domains, prefixes, and papers from database."""
        if self.domain_storage is None:
            return

        try:
            # Load domains
            if self.domain_storage.exists():
                domains_df = self.domain_storage.get()
                if domains_df is not None and len(domains_df) > 0:
                    self.blocked_domains = set(domains_df['domain'].tolist())
                    logger.info(f"Loaded {len(self.blocked_domains)} postponed domains from cache")

            # Load DOI prefixes
            if self.prefix_storage.exists():
                prefixes_df = self.prefix_storage.get()
                if prefixes_df is not None and len(prefixes_df) > 0:
                    self.blocked_doi_prefixes = set(prefixes_df['prefix'].tolist())
                    logger.info(f"Loaded {len(self.blocked_doi_prefixes)} postponed DOI prefixes from cache")

            # Load individual papers
            if hasattr(self, 'paper_storage') and self.paper_storage.exists():
                papers_df = self.paper_storage.get()
                if papers_df is not None and len(papers_df) > 0:
                    self.blocked_papers = set(papers_df['identifier'].tolist())
                    logger.info(f"Loaded {len(self.blocked_papers)} postponed papers from cache")

        except Exception as e:
            logger.warning(f"Failed to load postponed domains from database: {e}")

    def add_domain(self, domain: str, reason: str = "Cloudflare/Access denied"):
        """
        Add domain to blocked list.

        Args:
            domain: Domain to block (e.g., 'example.com')
            reason: Reason for blocking
        """
        if not domain or domain in self.blocked_domains:
            return

        self.blocked_domains.add(domain)

        # Persist to database
        if self.domain_storage is not None:
            try:
                import pandas as pd
                timestamp = datetime.utcnow().isoformat()

                # Check if domain already exists
                existing = self.domain_storage.get(IDs=[domain])

                if existing is not None and len(existing) > 0:
                    # Update detection count
                    count = existing.iloc[0]['detection_count'] + 1
                    df = pd.DataFrame([{
                        'domain': domain,
                        'reason': reason,
                        'first_detected': existing.iloc[0]['first_detected'],
                        'last_detected': timestamp,
                        'detection_count': count
                    }])
                else:
                    # New domain
                    df = pd.DataFrame([{
                        'domain': domain,
                        'reason': reason,
                        'first_detected': timestamp,
                        'last_detected': timestamp,
                        'detection_count': 1
                    }])

                self.domain_storage.write(df, timestamp=False)
                logger.info(f"Added postponed domain: {domain} ({reason})")

            except Exception as e:
                logger.warning(f"Failed to persist postponed domain {domain}: {e}")

    def add_doi_prefix(self, prefix: str, reason: str = "Cloudflare/Access denied"):
        """
        Add DOI prefix to blocked list.

        Args:
            prefix: DOI prefix to block (e.g., '10.1234')
            reason: Reason for blocking
        """
        if not prefix or prefix in self.blocked_doi_prefixes:
            return

        self.blocked_doi_prefixes.add(prefix)

        # Persist to database
        if self.prefix_storage is not None:
            try:
                import pandas as pd
                timestamp = datetime.utcnow().isoformat()

                # Check if prefix already exists
                existing = self.prefix_storage.get(IDs=[prefix])

                if existing is not None and len(existing) > 0:
                    # Update detection count
                    count = existing.iloc[0]['detection_count'] + 1
                    df = pd.DataFrame([{
                        'prefix': prefix,
                        'reason': reason,
                        'first_detected': existing.iloc[0]['first_detected'],
                        'last_detected': timestamp,
                        'detection_count': count
                    }])
                else:
                    # New prefix
                    df = pd.DataFrame([{
                        'prefix': prefix,
                        'reason': reason,
                        'first_detected': timestamp,
                        'last_detected': timestamp,
                        'detection_count': 1
                    }])

                self.prefix_storage.write(df, timestamp=False)
                logger.info(f"Added postponed DOI prefix: {prefix} ({reason})")

            except Exception as e:
                logger.warning(f"Failed to persist postponed DOI prefix {prefix}: {e}")

    def add_paper(self, identifier: str, reason: str = "Download timeout/hang"):
        """
        Add individual paper to blocked list (for papers that hang/timeout).

        Args:
            identifier: Paper identifier (DOI, etc.)
            reason: Reason for blocking
        """
        if not identifier or identifier in self.blocked_papers:
            return

        self.blocked_papers.add(identifier)

        # Persist to database
        if hasattr(self, 'paper_storage') and self.paper_storage is not None:
            try:
                import pandas as pd
                timestamp = datetime.now().isoformat()

                # Check if paper already exists
                existing = self.paper_storage.get(IDs=[identifier])

                if existing is not None and len(existing) > 0:
                    # Update detection count
                    count = existing.iloc[0]['detection_count'] + 1
                    df = pd.DataFrame([{
                        'identifier': identifier,
                        'reason': reason,
                        'first_detected': existing.iloc[0]['first_detected'],
                        'last_detected': timestamp,
                        'detection_count': count
                    }])
                else:
                    # New paper
                    df = pd.DataFrame([{
                        'identifier': identifier,
                        'reason': reason,
                        'first_detected': timestamp,
                        'last_detected': timestamp,
                        'detection_count': 1
                    }])

                self.paper_storage.write(df, timestamp=False)
                logger.warning(f"🚫 Postponed paper (timeout): {identifier}")

            except Exception as e:
                logger.warning(f"Failed to persist postponed paper {identifier}: {e}")

    def should_skip_doi(self, doi: str) -> Tuple[bool, Optional[str]]:
        """
        Check if DOI should be skipped based on prefix.

        Args:
            doi: DOI to check (e.g., '10.1234/paper123')

        Returns:
            (should_skip, reason)
        """
        if not doi:
            return (False, None)

        # Extract DOI prefix
        # Handle both "10.xxx/yyy" and "https://doi.org/10.xxx/yyy"
        clean_doi = doi
        if 'doi.org/' in doi:
            clean_doi = doi.split('doi.org/')[-1]

        if clean_doi.startswith('10.') and '/' in clean_doi:
            prefix = clean_doi.split('/')[0]
            if prefix in self.blocked_doi_prefixes:
                return (True, f"DOI prefix {prefix} is postponed (Cloudflare/access issues)")

        return (False, None)

    def should_skip_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Check if URL should be skipped based on domain.

        Args:
            url: URL to check

        Returns:
            (should_skip, reason)
        """
        if not url:
            return (False, None)

        try:
            parsed = urlparse(url)
            domain = parsed.netloc

            if domain in self.blocked_domains:
                return (True, f"Domain {domain} is postponed (Cloudflare/access issues)")
        except:
            pass

        return (False, None)

    def filter_batch(self, identifiers: List[str]) -> Tuple[List[str], List[str]]:
        """
        Split identifiers into (processable, blocked) based on cache.

        Args:
            identifiers: List of DOIs or URLs to filter

        Returns:
            (processable, blocked) - Two lists of identifiers
        """
        processable = []
        blocked = []

        for identifier in identifiers:
            # Check if individual paper is blocked (timeout/hang)
            if identifier in self.blocked_papers:
                blocked.append(identifier)
                continue

            # Check if DOI prefix is blocked
            skip_doi, reason_doi = self.should_skip_doi(identifier)
            if skip_doi:
                blocked.append(identifier)
                continue

            # Check if URL domain is blocked
            skip_url, reason_url = self.should_skip_url(identifier)
            if skip_url:
                blocked.append(identifier)
                continue

            # Not blocked
            processable.append(identifier)

        if blocked:
            logger.info(
                f"Pre-filtered {len(blocked)}/{len(identifiers)} identifiers "
                f"(known postponed domains/prefixes)"
            )

        return processable, blocked

    def analyze_result(self, result) -> Dict[str, Any]:
        """
        Analyze a DownloadResult to detect new Cloudflare/access issues.

        Args:
            result: DownloadResult object

        Returns:
            Dict with 'domains_added', 'prefixes_added' counts
        """
        domains_added = 0
        prefixes_added = 0

        # Check if result indicates Cloudflare or access issues
        error_lower = (result.error_reason or '').lower()
        is_cloudflare = 'cloudflare' in error_lower or 'cf-ray' in error_lower
        is_403 = '403' in error_lower or 'forbidden' in error_lower
        is_access_issue = is_cloudflare or is_403

        if not is_access_issue:
            return {'domains_added': 0, 'prefixes_added': 0}

        # Extract domain from identifier if it's a URL
        try:
            if result.identifier.startswith('http'):
                parsed = urlparse(result.identifier)
                domain = parsed.netloc
                if domain and domain not in self.blocked_domains:
                    reason = "Cloudflare" if is_cloudflare else "403 Forbidden"
                    self.add_domain(domain, reason)
                    domains_added += 1
        except:
            pass

        # Extract DOI prefix
        doi = result.identifier
        if 'doi.org/' in doi:
            doi = doi.split('doi.org/')[-1]

        if doi.startswith('10.') and '/' in doi:
            prefix = doi.split('/')[0]
            if prefix and prefix not in self.blocked_doi_prefixes:
                reason = "Cloudflare" if is_cloudflare else "403 Forbidden"
                self.add_doi_prefix(prefix, reason)
                prefixes_added += 1

        return {
            'domains_added': domains_added,
            'prefixes_added': prefixes_added
        }

    def analyze_batch(self, results: List) -> Dict[str, Any]:
        """
        Analyze a batch of DownloadResults to update cache.

        Args:
            results: List of DownloadResult objects

        Returns:
            Summary dict with statistics
        """
        total_domains_added = 0
        total_prefixes_added = 0

        for result in results:
            analysis = self.analyze_result(result)
            total_domains_added += analysis['domains_added']
            total_prefixes_added += analysis['prefixes_added']

        if total_domains_added > 0 or total_prefixes_added > 0:
            logger.info(
                f"Analyzed batch: added {total_domains_added} domains, "
                f"{total_prefixes_added} DOI prefixes to postponed cache"
            )

        return {
            'domains_added': total_domains_added,
            'prefixes_added': total_prefixes_added,
            'total_domains': len(self.blocked_domains),
            'total_prefixes': len(self.blocked_doi_prefixes)
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'blocked_domains': len(self.blocked_domains),
            'blocked_doi_prefixes': len(self.blocked_doi_prefixes),
            'blocked_papers': len(self.blocked_papers),
            'domains': sorted(list(self.blocked_domains)),
            'doi_prefixes': sorted(list(self.blocked_doi_prefixes))
        }

    def clear(self):
        """Clear all postponed domains, prefixes, and papers (use with caution)."""
        self.blocked_domains.clear()
        self.blocked_doi_prefixes.clear()
        self.blocked_papers.clear()

        # Also clear from database
        if self.domain_storage is not None:
            try:
                # Delete all rows
                all_domains = self.domain_storage.get_ID_list()
                if all_domains:
                    self.domain_storage.delete(all_domains)

                all_prefixes = self.prefix_storage.get_ID_list()
                if all_prefixes:
                    self.prefix_storage.delete(all_prefixes)

                if hasattr(self, 'paper_storage') and self.paper_storage is not None:
                    all_papers = self.paper_storage.get_ID_list()
                    if all_papers:
                        self.paper_storage.delete(all_papers)

                logger.info("Cleared postponed cache (domains, prefixes, papers)")
            except Exception as e:
                logger.warning(f"Failed to clear database cache: {e}")
