"""
PDFFetcher - Generic PDF downloading infrastructure

This is the main orchestrator that:
- Manages publisher strategies
- Handles parallel downloads
- Tracks metadata in database
- Provides progress callbacks
- Never re-downloads successful PDFs
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Callable, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import signal
import threading
import requests
import yaml
from dataclasses import dataclass

from .utils import sanitize_doi_to_filename

logger = logging.getLogger(__name__)


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """
    Deep merge two dictionaries, with override taking precedence.
    
    Args:
        base: Base dictionary (defaults)
        override: Override dictionary (will overwrite base values)
    
    Returns:
        Merged dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = _deep_merge(result[key], value)
        else:
            # Override with new value (or add new key)
            result[key] = value
    
    return result


@dataclass
class DownloadResult:
    """Result of a PDF download attempt."""

    identifier: str
    status: str  # 'success', 'failure', 'postponed', 'skipped'
    local_path: Optional[Path] = None
    error_reason: Optional[str] = None
    strategy_used: Optional[str] = None
    publisher: Optional[str] = None

    def __repr__(self):
        if self.status == "success":
            return f"✓ {self.identifier} → {self.local_path.name}"
        elif self.status == "skipped":
            return f"⊙ {self.identifier} (already downloaded)"
        elif self.status == "postponed":
            return f"⏸ {self.identifier} ({self.error_reason})"
        else:
            return f"✗ {self.identifier} ({self.error_reason})"


class PDFFetcher:
    """
    Generic PDF fetcher with strategy pattern and database tracking.

    Features:
    - Automatic strategy selection
    - Parallel downloads
    - Progress tracking
    - Database integration
    - Never re-downloads
    """

    # DOI prefix to publisher mapping
    DOI_PREFIX_TO_PUBLISHER = {
        "10.1007": "Springer",
        "10.1016": "Elsevier",
        "10.1109": "IEEE",
        "10.1090": "AMS",  # American Mathematical Society
        "10.1137": "SIAM",  # Society for Industrial and Applied Mathematics
        "10.1080": "Taylor & Francis",
        "10.1093": "Oxford University Press",
        "10.1017": "Cambridge University Press",
        "10.3390": "MDPI",
        "10.1088": "IOP Publishing",
        "10.1038": "Nature Publishing Group",
        "10.1126": "Science/AAAS",
        "10.1145": "ACM",
        "10.1002": "Wiley",
        "10.1215": "Duke University Press",
        "10.4171": "EMS Press",
        "10.1201": "CRC Press",
        "10.1112": "London Mathematical Society",
        "10.2307": "JSTOR",
        "10.4213": "Russian Academy of Sciences",
        "10.1134": "Pleiades Publishing",
        "10.3842": "Institute of Mathematics of NAS of Ukraine",
    }

    # Class-level interrupt handling
    _interrupted = False
    _interrupt_count = 0
    _current_executor: Optional[ThreadPoolExecutor] = None
    _original_sigint_handler = None
    _original_sigterm_handler = None

    @classmethod
    def _signal_handler(cls, signum, frame):
        """Handle Ctrl+C and SIGTERM gracefully."""
        import os

        cls._interrupt_count += 1
        cls._interrupted = True

        if cls._interrupt_count == 1:
            signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
            logger.warning(f"\n⚠ {signal_name} received - shutting down gracefully...")
            logger.warning("  (Press Ctrl+C again to force quit)")

            # Shutdown executor immediately without waiting
            if cls._current_executor is not None:
                logger.warning("  Cancelling pending downloads...")
                cls._current_executor.shutdown(wait=False, cancel_futures=True)
        else:
            # Second interrupt - force quit immediately
            logger.warning(f"\n⚠ Force quit (interrupt #{cls._interrupt_count})")
            os._exit(1)

    @classmethod
    def _install_signal_handlers(cls):
        """Install signal handlers for graceful shutdown."""
        # Only install from main thread
        if threading.current_thread() is not threading.main_thread():
            return

        cls._interrupted = False
        cls._interrupt_count = 0
        cls._original_sigint_handler = signal.signal(signal.SIGINT, cls._signal_handler)
        cls._original_sigterm_handler = signal.signal(signal.SIGTERM, cls._signal_handler)

    @classmethod
    def _restore_signal_handlers(cls):
        """Restore original signal handlers."""
        if threading.current_thread() is not threading.main_thread():
            return

        if cls._original_sigint_handler is not None:
            signal.signal(signal.SIGINT, cls._original_sigint_handler)
            cls._original_sigint_handler = None
        if cls._original_sigterm_handler is not None:
            signal.signal(signal.SIGTERM, cls._original_sigterm_handler)
            cls._original_sigterm_handler = None

    @staticmethod
    def load_config(config_path: Optional[Union[str, Path]] = None) -> Dict:
        """
        Load configuration from YAML files with defaults and overrides.

        Configuration is loaded in layers, with later layers overriding earlier ones:
        1. Package default config (in pdf_fetcher package directory) - ALWAYS loaded as base defaults
        2. User global config (~/.config/pdf_fetcher/config.yaml) - Merged on top as user defaults
        3. Explicit config_path (if provided) or local config.yaml - Merged on top as final overrides

        This allows:
        - Package defaults to provide baseline configuration
        - User config to set personal preferences globally
        - Local/project config to override for specific projects

        Args:
            config_path: Path to config file (optional). If provided, used as final override.
                        If not provided, checks for ./config.yaml as final override.

        Returns:
            Dictionary with merged config values
        """
        config = {}
        
        # Step 1: Load package default config (always as base defaults)
        package_config_path = Path(__file__).parent / "config.yaml"
        if package_config_path.exists():
            try:
                with open(package_config_path, "r") as f:
                    package_config = yaml.safe_load(f) or {}
                config = _deep_merge(config, package_config)
                logger.debug(f"Loaded package defaults from {package_config_path.resolve()}")
            except Exception as e:
                logger.warning(f"Failed to load package default config from {package_config_path.resolve()}: {e}")
        
        # Step 2: Load user global config (merge on top as user defaults)
        user_config_path = Path.home() / ".config" / "pdf_fetcher" / "config.yaml"
        if user_config_path.exists():
            try:
                with open(user_config_path, "r") as f:
                    user_config = yaml.safe_load(f) or {}
                config = _deep_merge(config, user_config)
                logger.debug(f"Loaded user config from {user_config_path.resolve()}")
            except Exception as e:
                logger.warning(f"Failed to load user config from {user_config_path.resolve()}: {e}")
        
        # Step 3: Load override config (merge on top as final overrides)
        override_config_path = None
        if config_path:
            # Explicit path provided - use as override
            override_config_path = Path(config_path).expanduser()
        else:
            # Check for local config.yaml as override
            local_config_path = Path("./config.yaml").resolve()
            if local_config_path.exists():
                override_config_path = local_config_path
        
        if override_config_path and override_config_path.exists():
            try:
                with open(override_config_path, "r") as f:
                    override_config = yaml.safe_load(f) or {}
                config = _deep_merge(config, override_config)
                logger.info(f"Loaded override config from {override_config_path.resolve()}")
            except Exception as e:
                logger.error(f"Failed to load override config from {override_config_path.resolve()}: {e}")
        elif config_path:
            # Explicit path provided but doesn't exist
            logger.warning(f"Override config file {config_path} not found, using defaults only")
        
        return config

    @staticmethod
    def get_publisher_from_doi(doi: str) -> str:
        """
        Get publisher name from DOI prefix.

        Args:
            doi: DOI string (e.g., "10.1007/s11784-025-01219-x")

        Returns:
            Publisher name or "Unknown" if prefix not recognized

        Example:
            >>> PDFFetcher.get_publisher_from_doi("10.1007/s11784-025-01219-x")
            'Springer'
        """
        # Extract prefix (part before first slash)
        prefix = doi.split("/")[0] if "/" in doi else doi
        return PDFFetcher.DOI_PREFIX_TO_PUBLISHER.get(prefix, "Unknown")

    def __init__(
        self,
        output_dir: Optional[Union[str, Path]] = None,
        metadata_db_path: Optional[Union[str, Path]] = None,
        max_workers: Optional[int] = None,
        max_attempts: Optional[int] = None,
        timeout: Optional[int] = None,
        user_agent: Optional[str] = None,
        unpaywall_email: Optional[str] = None,
        config_path: Optional[Union[str, Path]] = None,
        require_vpn: Optional[Union[str, List[str]]] = None,
        arxiv_cooldown: Optional[float] = None,
    ):
        """
        Initialize PDF fetcher.

        Args:
            output_dir: Where to save PDFs (default: from config or './pdfs')
            metadata_db_path: SQLite database path (default: output_dir/metadata.db)
            max_workers: Parallel download threads (default: from config or 4)
            max_attempts: Max retry attempts per PDF (default: from config or 3)
            timeout: Download timeout in seconds (default: from config or 30)
            user_agent: User agent for requests (default: from config)
            unpaywall_email: Email for Unpaywall API (default: from config or 'research@example.org')
            config_path: Path to config file (default: searches standard locations)
            require_vpn: University IP prefix(es) to check before downloads.
                        Can be string ("130.225") or list (["130.225", "130.226"]).
                        If set, VPN will be checked before actual downloads.
            arxiv_cooldown: Minimum seconds between ArXiv requests (default: from config or 1.0)
                           Set to 0 to disable rate limiting (not recommended)
        """
        # Load config file
        config = self.load_config(config_path)
        self.config = config  # Store for later use (e.g., in _load_strategies)

        # Apply settings with priority: args > config > defaults
        self.output_dir = Path(output_dir or config.get("output_dir", "./pdfs"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.max_workers = max_workers or config.get("max_workers", 4)
        self.max_attempts = max_attempts or config.get("max_attempts", 3)
        self.timeout = timeout or config.get("timeout", 30)
        self.user_agent = user_agent or config.get(
            "user_agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        # Get Unpaywall email from config nested structure
        unpaywall_config = config.get("unpaywall", {})
        self.unpaywall_email = unpaywall_email or unpaywall_config.get(
            "email", "research@example.org"
        )

        # Warn if using default email
        if self.unpaywall_email == "research@example.org":
            logger.warning(
                "Using default email for Unpaywall. Please set your real email in config.yaml"
            )

        # Store VPN requirement
        self.require_vpn = require_vpn

        # Store ArXiv cooldown with priority: args > config > defaults
        arxiv_config = config.get("arxiv", {})
        self.arxiv_cooldown = arxiv_cooldown if arxiv_cooldown is not None else arxiv_config.get("cooldown", 1.0)

        # Load strategies
        self.strategies = self._load_strategies()
        logger.info(f"Loaded {len(self.strategies)} publisher strategies")

        # Initialize database with centralized default
        if metadata_db_path is None:
            # Default: centralized DB at ~/.pdf_fetcher/metadata.db
            metadata_db_path = Path.home() / ".pdf_fetcher" / "metadata.db"
            logger.info(f"Using centralized database: {metadata_db_path}")
        else:
            metadata_db_path = Path(metadata_db_path)

        # Import metadata database
        try:
            from .database import DownloadMetadataDB

            self.db = DownloadMetadataDB(metadata_db_path)
            logger.info(f"Database initialized: {metadata_db_path}")
        except ImportError:
            logger.warning("database module not found, operating without database")
            self.db = None

        # Initialize postponed domains cache (global cache in ~/.cache/pdffetcher)
        try:
            from .postponed_cache import PostponedDomainsCache

            self.postponed_cache = PostponedDomainsCache()
            stats = self.postponed_cache.get_stats()
            logger.info(
                f"Postponed cache initialized: "
                f"{stats['blocked_domains']} domains, "
                f"{stats['blocked_doi_prefixes']} prefixes, "
                f"{stats['blocked_papers']} papers"
            )
        except ImportError:
            logger.warning("postponed_cache module not found, skipping postponed filtering")
            self.postponed_cache = None

    def _load_strategies(self) -> List:
        """Load all available publisher strategies."""
        strategies = []

        try:
            from .strategies import (
                UnpaywallStrategy,
                ArxivStrategy,
                ElsevierTDMStrategy,
                ElsevierStrategy,
                SpringerStrategy,
                AMSStrategy,
                MDPIStrategy,
                GenericStrategy,
            )

            # Use ArXiv cooldown from instance (already resolved: args > config > defaults)
            strategies.extend(
                [
                    UnpaywallStrategy(email=self.unpaywall_email),  # Try OA first!
                    ArxivStrategy(cooldown=self.arxiv_cooldown),  # ArXiv preprints (priority 5)
                    ElsevierTDMStrategy(),  # TDM API (priority 5) - tries before scraping
                    ElsevierStrategy(),  # Scraping fallback (priority 10)
                    SpringerStrategy(),
                    AMSStrategy(),
                    MDPIStrategy(),
                    GenericStrategy(),  # Fallback for unknown publishers
                ]
            )
        except ImportError as e:
            logger.error(f"Could not import strategies: {e}")

        # Sort by priority (lower number = higher priority)
        strategies.sort(key=lambda s: s.get_priority())

        return strategies

    def _select_strategy(self, identifier: str):
        """Select best strategy for identifier."""
        for strategy in self.strategies:
            if strategy.can_handle(identifier):
                return strategy
        return None

    def _is_arxiv_identifier(self, identifier: str) -> bool:
        """
        Check if identifier is from ArXiv.

        Returns:
            True if this is an ArXiv paper
        """
        # Find ArXiv strategy and check if it can handle this identifier
        for strategy in self.strategies:
            if strategy.__class__.__name__ == "ArxivStrategy":
                return strategy.can_handle(identifier)
        return False

    def should_download(self, identifier: str) -> Tuple[bool, Optional[str]]:
        """
        Check if we should attempt to download this identifier.

        Returns:
            (should_download, reason)
        """
        if self.db is None:
            return (True, None)

        return self.db.should_download(identifier, max_attempts=self.max_attempts)

    def fetch(self, identifier: str, strategy_name: Optional[str] = None, force: bool = False) -> DownloadResult:
        """
        Fetch a single PDF.

        Args:
            identifier: DOI or URL
            strategy_name: Force specific strategy (optional)
            force: If True, bypass database checks and force re-download (default: False)

        Returns:
            DownloadResult with status and details
        """
        # Check if should download (skip check if force=True)
        if not force:
            should_dl, reason = self.should_download(identifier)
        else:
            should_dl, reason = True, None

        if not should_dl:
            # Double-check: if marked as success, verify file actually exists
            if self.db and reason == "Already downloaded successfully":
                result = self.db.get_result(identifier)
                if result and result.get("local_path"):
                    if not Path(result["local_path"]).exists():
                        logger.warning(f"File missing for {identifier}, re-downloading")
                        self.db.mark_file_missing(identifier)
                        # Continue to download
                    else:
                        logger.info(f"Skipping {identifier}: {reason}")
                        return DownloadResult(
                            identifier=identifier, status="skipped", error_reason=reason
                        )
                else:
                    logger.info(f"Skipping {identifier}: {reason}")
                    return DownloadResult(
                        identifier=identifier, status="skipped", error_reason=reason
                    )
            else:
                logger.info(f"Skipping {identifier}: {reason}")
                return DownloadResult(identifier=identifier, status="skipped", error_reason=reason)

        # Check if file already exists on filesystem but not in database
        # This handles copied PDFs or files from other sources
        sanitized_name = sanitize_doi_to_filename(identifier)
        expected_path = self.output_dir / sanitized_name

        if expected_path.exists() and not force:
            logger.info(f"Found existing file for {identifier}: {expected_path}")

            # Validate it's a real PDF
            try:
                with open(expected_path, "rb") as f:
                    if f.read(4) == b"%PDF":
                        # Register in database as pre-existing file
                        if self.db:
                            self.db.record_success(
                                identifier=identifier,
                                local_path=str(expected_path),
                                publisher="Unknown (pre-existing file)",
                                strategy_used="PreExistingFile",
                                landing_url=f"https://doi.org/{identifier}",
                                pdf_url="Pre-existing file",
                                sanitized_filename=sanitized_name,
                            )
                            logger.info(f"✓ Registered existing file: {identifier}")

                        return DownloadResult(
                            identifier=identifier,
                            status="success",
                            local_path=expected_path,
                            strategy_used="PreExistingFile",
                            publisher="Unknown (pre-existing file)",
                        )
                    else:
                        logger.warning(f"File exists but is not a valid PDF: {expected_path}")
            except Exception as e:
                logger.warning(f"Error validating existing file {expected_path}: {e}")

        # Select strategies to try
        if strategy_name:
            strategies_to_try = [
                s for s in self.strategies if s.__class__.__name__ == strategy_name
            ]
        else:
            # Try all strategies that can handle this identifier, in priority order
            strategies_to_try = [s for s in self.strategies if s.can_handle(identifier)]

        if not strategies_to_try:
            error = "No strategy can handle this identifier"
            logger.error(f"{identifier}: {error}")
            if self.db:
                self.db.record_failure(identifier, error, should_retry=False)
            return DownloadResult(identifier=identifier, status="failure", error_reason=error)

        # Construct landing URL via doi.org (works for all publishers)
        landing_url = f"https://doi.org/{identifier}"

        # Use realistic browser headers to avoid blocking
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # Create session to preserve cookies between requests (needed for MDPI and others)
        session = requests.Session()
        session.headers.update(headers)

        # Use tuple timeout: (connect_timeout, read_timeout)
        # Read timeout is per-chunk, so keep it shorter to detect stalls faster
        connect_timeout = min(self.timeout, 30)  # Max 30s to connect
        read_timeout = min(self.timeout, 30)  # Max 30s between chunks
        request_timeout = (connect_timeout, read_timeout)

        # Fetch landing page once (reuse for all strategies)
        html_content = None
        try:
            response = session.get(landing_url, timeout=request_timeout, allow_redirects=True)
            html_content = response.text if response.status_code == 200 else None
        except Exception as e:
            logger.warning(f"Failed to fetch landing page for {identifier}: {e}")

        # Try each strategy in order until one succeeds
        last_error = None
        last_strategy = None
        last_postpone_reason = None  # Track if any strategy wants to postpone

        for strategy in strategies_to_try:
            logger.debug(f"Trying {strategy.__class__.__name__} for {identifier}")
            last_strategy = strategy

            try:
                # Get PDF URL
                pdf_url = strategy.get_pdf_url(
                    identifier=identifier, landing_url=landing_url, html_content=html_content
                )

                if not pdf_url:
                    logger.debug(f"{strategy.__class__.__name__} could not find PDF URL")
                    last_error = "Could not find PDF URL"
                    continue  # Try next strategy

                # Download PDF using same session (preserves cookies from landing page)
                # Get strategy-specific headers (needed for API access like Elsevier TDM)
                custom_headers = strategy.get_custom_headers(identifier)
                pdf_response = session.get(
                    pdf_url,
                    headers=custom_headers,  # Add strategy headers (API keys, etc.)
                    timeout=request_timeout,  # Tuple: (connect, read) for faster stall detection
                    allow_redirects=True,
                    stream=True,  # Stream for large PDFs
                )

                if pdf_response.status_code != 200:
                    error = f"HTTP {pdf_response.status_code}"
                    logger.warning(
                        f"{strategy.__class__.__name__} got {error}, trying next strategy"
                    )
                    last_error = error
                    continue  # Try next strategy

                # Check for Elsevier TDM warning (first-page-only due to lack of entitlement)
                els_status = pdf_response.headers.get('X-ELS-Status', '')
                if 'limited to first page' in els_status.lower():
                    error = f"Elsevier TDM: {els_status} - need VPN or InstToken for full access"
                    logger.warning(f"{strategy.__class__.__name__}: {error}, trying next strategy")
                    last_error = error
                    continue  # Try next strategy

                # Download PDF content properly with streaming
                # IMPORTANT: Must iterate over chunks when stream=True to get complete file
                # Add timeout protection for slow chunk reads AND total download time
                pdf_content = bytearray()
                chunk_start_time = time.time()
                download_start_time = time.time()
                download_stalled = False
                max_total_time = self.timeout * 2  # Total download timeout (e.g., 60s)

                for chunk in pdf_response.iter_content(chunk_size=8192):
                    now = time.time()

                    # Check total download time (prevents slow-drip attacks)
                    if now - download_start_time > max_total_time:
                        error = f"Download too slow (exceeded {max_total_time}s total)"
                        logger.warning(f"{strategy.__class__.__name__}: {error}")
                        last_error = error
                        download_stalled = True
                        break

                    # Check if we've been downloading too long (per-chunk timeout)
                    if now - chunk_start_time > self.timeout:
                        error = f"Download stalled (no progress for {self.timeout}s)"
                        logger.warning(f"{strategy.__class__.__name__}: {error}")
                        last_error = error
                        download_stalled = True
                        break

                    if chunk:  # filter out keep-alive chunks
                        pdf_content.extend(chunk)
                        chunk_start_time = time.time()  # Reset timeout on progress

                # Skip this strategy if download stalled
                if download_stalled:
                    pdf_response.close()  # Close connection to free resources
                    continue  # Try next strategy

                pdf_content = bytes(pdf_content)

                # Validate PDF
                if not pdf_content.startswith(b"%PDF"):
                    # Check if we got HTML instead (common with captchas/rate limiting)
                    is_html = pdf_content.startswith(b"<!DOCTYPE") or pdf_content.startswith(b"<html")

                    if is_html:
                        # Try to decode HTML for captcha detection
                        try:
                            html_content = pdf_content[:5000].decode('utf-8', errors='ignore')
                        except:
                            html_content = ""

                        error = f"Downloaded file is HTML, not PDF (possible captcha/rate limiting)"

                        # Check if strategy wants to postpone (e.g., for captchas)
                        if strategy.should_postpone(error, html_content):
                            logger.warning(f"{strategy.__class__.__name__}: {error}, postponing")
                            last_error = error
                            last_postpone_reason = error
                            continue  # Try next strategy (or postpone if all fail)
                    else:
                        error = f"Downloaded file is not a PDF"

                    logger.warning(f"{strategy.__class__.__name__}: {error}, trying next strategy")
                    last_error = error
                    continue  # Try next strategy

                # Save PDF
                sanitized_name = sanitize_doi_to_filename(identifier)
                local_path = self.output_dir / sanitized_name

                with open(local_path, "wb") as f:
                    f.write(pdf_content)

                logger.info(f"✓ Downloaded: {identifier} → {local_path.name}")

                # Record success
                if self.db:
                    publisher = strategy.name
                    self.db.record_success(
                        identifier=identifier,
                        local_path=str(local_path),
                        publisher=publisher,
                        strategy_used=strategy.__class__.__name__,
                        landing_url=landing_url,
                        pdf_url=pdf_url,
                        sanitized_filename=sanitized_name,
                    )

                return DownloadResult(
                    identifier=identifier,
                    status="success",
                    local_path=local_path,
                    strategy_used=strategy.__class__.__name__,
                    publisher=publisher if self.db else None,
                )

            except requests.Timeout:
                error = f"Timeout after {self.timeout}s"
                logger.warning(f"{strategy.__class__.__name__}: {error}, trying next strategy")
                last_error = error
                continue  # Try next strategy

            except Exception as e:
                error = str(e)
                logger.warning(f"{strategy.__class__.__name__}: {error}, trying next strategy")
                last_error = error
                continue  # Try next strategy

        # All strategies failed
        logger.warning(f"All strategies failed for {identifier}. Last error: {last_error}")

        # Determine if should retry based on last strategy or postpone reason
        should_retry = False
        if last_postpone_reason:
            # A strategy explicitly wanted to postpone (e.g., detected captcha)
            should_retry = True
            logger.info(f"Postponing {identifier}: {last_postpone_reason}")
        elif last_strategy and last_error:
            # Check if last strategy thinks error is temporary
            should_retry = last_strategy.should_postpone(last_error)

        if self.db:
            self.db.record_failure(
                identifier, last_error or "All strategies failed", should_retry=should_retry
            )

        return DownloadResult(
            identifier=identifier,
            status="postponed" if should_retry else "failure",
            error_reason=last_error or "All strategies failed",
            strategy_used=last_strategy.__class__.__name__ if last_strategy else "None",
        )

    def fetch_batch(
        self,
        identifiers: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        show_progress: bool = True,
        force: bool = False,
        batch_size: int = 1000,
    ) -> List[DownloadResult]:
        """
        Fetch multiple PDFs in parallel.

        Args:
            identifiers: List of DOIs or URLs
            progress_callback: Optional callback(completed, total)
            show_progress: If True, show tqdm progress bar (default: True)
            force: If True, re-download PDFs even if already successfully downloaded (default: False)
            batch_size: Number of identifiers to process per batch (default: 1000).
                       Processing in batches helps avoid memory issues and thread pool exhaustion
                       when downloading large numbers of PDFs.

        Returns:
            List of DownloadResults
        """
        from tqdm import tqdm

        # Install signal handlers for graceful Ctrl+C handling
        self._install_signal_handlers()

        results = []
        total = len(identifiers)

        # Track status counts for progress bar
        status_counts = {
            'success': 0,
            'skipped': 0,
            'failure': 0,
            'postponed': 0,
            'pre_existing': 0,
        }

        # Set up progress bar if requested
        pbar = None
        if show_progress and progress_callback is None:
            pbar = tqdm(total=total, desc="Downloading PDFs", position=0)

            def progress_callback(completed, total):
                pbar.n = completed
                # Update postfix with status icons
                pbar.set_postfix_str(
                    f"✓ {status_counts['success']} "
                    f"⊙ {status_counts['skipped']} "
                    f"⊕ {status_counts['pre_existing']} "
                    f"✗ {status_counts['failure']} "
                    f"⏸ {status_counts['postponed']}",
                    refresh=False
                )
                pbar.refresh()

        # Pre-filter using postponed cache (skip known Cloudflare/blocked sources and problem papers)
        postponed_identifiers = []
        if self.postponed_cache:
            processable, blocked = self.postponed_cache.filter_batch(identifiers)
            postponed_identifiers = blocked

            # Create skipped results for postponed identifiers
            if postponed_identifiers:
                for identifier in postponed_identifiers:
                    results.append(
                        DownloadResult(
                            identifier=identifier,
                            status="postponed",
                            error_reason="Skipped: Domain/DOI prefix in postponed cache (known Cloudflare/access issues)",
                        )
                    )
                    status_counts['postponed'] += 1

            # Continue with processable identifiers only
            identifiers = processable
            total = len(identifiers) + len(postponed_identifiers)  # Update total for progress bar

        # Batch check download status (one DB query instead of N queries)
        # Skip status check if force=True (re-download everything)
        if force:
            batch_status = {id: (True, None) for id in identifiers}
            logger.info(f"Force mode enabled: re-downloading all {len(identifiers)} PDFs")
        elif self.db:
            batch_status = self.db.get_batch_status(identifiers, max_attempts=self.max_attempts)
            logger.info(
                f"Batch status check: {sum(1 for s, _ in batch_status.values() if s)} need download, "
                f"{sum(1 for s, _ in batch_status.values() if not s)} can skip"
            )
        else:
            batch_status = {id: (True, None) for id in identifiers}

        # Check VPN if required, but only if there are actual downloads to perform
        if self.require_vpn:
            needs_download = any(should_dl for should_dl, _ in batch_status.values())

            # Only check VPN if we actually have downloads to perform
            if needs_download:
                try:
                    from network_utils import check_vpn_status

                    is_vpn, current_ip, msg = check_vpn_status(self.require_vpn)

                    if not is_vpn:
                        raise RuntimeError(
                            f"VPN check failed: {msg}\n"
                            f"Please connect to university VPN before downloading PDFs."
                        )
                    else:
                        logger.info(f"VPN check passed: {msg}")
                except ImportError:
                    logger.warning(
                        "network_utils not installed, skipping VPN check. "
                        "Install with: pip install -e ~/Documents/dh4pmp_tools/packages/network_utils"
                    )

        # Separate identifiers into those needing download vs those to skip
        to_download = []
        completed_count = 0

        for identifier in identifiers:
            should_dl, reason = batch_status.get(identifier, (True, None))
            if not should_dl:
                # Create skipped result immediately (no download needed)
                results.append(
                    DownloadResult(identifier=identifier, status="skipped", error_reason=reason)
                )
                status_counts['skipped'] += 1
                completed_count += 1
                if progress_callback:
                    progress_callback(completed_count, total)
            else:
                to_download.append(identifier)

        # Download the remaining identifiers in parallel, processing in batches
        if to_download:
            logger.info(f"Starting parallel downloads for {len(to_download)} papers (batch size: {batch_size})")
            
            # Split into batches
            num_batches = (len(to_download) + batch_size - 1) // batch_size  # Ceiling division
            if num_batches > 1:
                logger.info(f"Processing {len(to_download)} identifiers in {num_batches} batches of up to {batch_size} each")
            
            for batch_num, batch_start in enumerate(range(0, len(to_download), batch_size), 1):
                # Check if interrupted by Ctrl+C
                if self._interrupted:
                    logger.warning(f"⚠ Interrupted - stopping after {batch_num - 1} batches")
                    break

                batch_end = min(batch_start + batch_size, len(to_download))
                batch_identifiers = to_download[batch_start:batch_end]

                if num_batches > 1:
                    logger.info(f"Processing batch {batch_num}/{num_batches} ({len(batch_identifiers)} identifiers)")
                
                # Check for ArXiv rate limiting and filter out ArXiv identifiers if needed
                # Import ArxivStrategy to check rate limit flag
                from .strategies.arxiv import ArxivStrategy

                batch_to_submit = []
                arxiv_skipped = []

                for identifier in batch_identifiers:
                    # Check if this is ArXiv and if ArXiv is rate limited
                    if self._is_arxiv_identifier(identifier) and ArxivStrategy.is_rate_limited():
                        # Skip this ArXiv paper - add to postponed results
                        arxiv_skipped.append(identifier)
                    else:
                        batch_to_submit.append(identifier)

                # Create postponed results for skipped ArXiv papers
                if arxiv_skipped:
                    logger.warning(f"⏸ Skipping {len(arxiv_skipped)} ArXiv papers (rate limit active)")
                    for identifier in arxiv_skipped:
                        results.append(
                            DownloadResult(
                                identifier=identifier,
                                status="postponed",
                                error_reason="ArXiv rate limited - batch paused to avoid hammering servers",
                            )
                        )
                        status_counts['postponed'] += 1
                        completed_count += 1
                        if progress_callback:
                            progress_callback(completed_count, total)

                # Use manual executor management (not context manager) to allow shutdown(wait=False) on timeout
                executor = ThreadPoolExecutor(max_workers=self.max_workers)
                PDFFetcher._current_executor = executor  # Store for signal handler
                timed_out = False
                try:
                    # Submit only identifiers that need downloading (and aren't rate-limited ArXiv)
                    future_to_id = {
                        executor.submit(self.fetch, identifier, force=force): identifier
                        for identifier in batch_to_submit
                    }
                    logger.debug(f"Submitted {len(future_to_id)} download tasks for batch {batch_num}")

                    # Collect results using polling instead of blocking as_completed()
                    # This allows us to respond to Ctrl+C immediately
                    batch_timeout = self.timeout * 3
                    batch_start_time = time.time()
                    pending_futures = set(future_to_id.keys())

                    while pending_futures and not self._interrupted:
                        # Check batch timeout
                        elapsed = time.time() - batch_start_time
                        if elapsed > batch_timeout:
                            timed_out = True
                            logger.error(f"⏱ Batch TIMEOUT after {batch_timeout}s (batch {batch_num})")
                            break

                        # Poll for completed futures (non-blocking check)
                        newly_done = {f for f in pending_futures if f.done()}

                        if not newly_done:
                            # No futures completed yet - short sleep and check again
                            time.sleep(0.1)
                            continue

                        # Process completed futures
                        for future in newly_done:
                            pending_futures.remove(future)
                            identifier = future_to_id[future]

                            try:
                                # Future is done, so result() should return immediately
                                # But add a small timeout just in case
                                result = future.result(timeout=1.0)
                                results.append(result)

                                # Track status for progress bar
                                if result.status == 'success':
                                    # Distinguish between newly downloaded and pre-existing files
                                    if result.strategy_used == 'PreExistingFile':
                                        status_counts['pre_existing'] += 1
                                    else:
                                        status_counts['success'] += 1
                                elif result.status == 'failure':
                                    status_counts['failure'] += 1
                                elif result.status == 'postponed':
                                    status_counts['postponed'] += 1
                                elif result.status == 'skipped':
                                    status_counts['skipped'] += 1

                            except TimeoutError:
                                # Shouldn't happen since future.done() was True
                                logger.error(f"⏱ TIMEOUT getting result for {identifier}")
                                result = DownloadResult(
                                    identifier=identifier,
                                    status="failure",
                                    error_reason="Timeout getting result",
                                )
                                results.append(result)
                                status_counts['failure'] += 1

                            except Exception as e:
                                logger.error(f"Error processing {identifier}: {e}")
                                result = DownloadResult(
                                    identifier=identifier, status="failure", error_reason=str(e)
                                )
                                results.append(result)
                                status_counts['failure'] += 1

                            completed_count += 1
                            if progress_callback:
                                progress_callback(completed_count, total)

                        # Brief pause to avoid busy-waiting
                        time.sleep(0.05)

                    # Handle remaining pending futures (timeout or interrupted)
                    if pending_futures:
                        if self._interrupted:
                            logger.warning(f"⚠ Interrupted - {len(pending_futures)} downloads still pending")
                        elif timed_out:
                            logger.warning(f"⏸ Timeout - {len(pending_futures)} downloads will be postponed for retry")
                            logger.info(f"   {len(future_to_id)} tasks submitted, {len(future_to_id) - len(pending_futures)} completed")

                        for future in pending_futures:
                            doi = future_to_id[future]
                            reason = "Interrupted by user" if self._interrupted else f"Download timeout (will retry)"

                            if not self._interrupted:
                                logger.debug(f"   ⏸ Postponed: {doi}")

                            # Don't add to postponed_cache for timeouts - they're likely temporary
                            # The postponed_cache is for known-bad domains/papers, not transient issues

                            # Create postponed result (will retry on next run)
                            result = DownloadResult(
                                identifier=doi,
                                status="postponed",
                                error_reason=reason,
                            )
                            results.append(result)
                            status_counts['postponed'] += 1

                            # Record in database with should_retry=True (timeouts are often temporary)
                            if self.db and not self._interrupted:
                                self.db.record_failure(doi, reason, should_retry=True)

                            completed_count += 1
                            if progress_callback:
                                progress_callback(completed_count, total)

                finally:
                    # ALWAYS use wait=False to avoid hanging on shutdown
                    # The threads may keep running but at least we can exit
                    logger.debug(f"Executor shutdown (batch {batch_num})")
                    executor.shutdown(wait=False, cancel_futures=True)
                    PDFFetcher._current_executor = None  # Clear executor reference
                
                # Brief pause between batches to avoid overwhelming the system
                if batch_num < num_batches:
                    time.sleep(0.5)

        # Close progress bar if we created one
        if pbar:
            pbar.close()
            # Print summary with icons
            logger.info(
                f"Download summary: "
                f"✓ {status_counts['success']} downloaded, "
                f"⊕ {status_counts['pre_existing']} pre-existing, "
                f"⊙ {status_counts['skipped']} skipped, "
                f"✗ {status_counts['failure']} failed, "
                f"⏸ {status_counts['postponed']} postponed"
            )

        # Analyze results to update postponed domains cache
        if self.postponed_cache and results:
            analysis = self.postponed_cache.analyze_batch(results)
            if analysis['domains_added'] > 0 or analysis['prefixes_added'] > 0:
                logger.info(
                    f"Updated postponed cache: +{analysis['domains_added']} domains, "
                    f"+{analysis['prefixes_added']} DOI prefixes "
                    f"(total: {analysis['total_domains']} domains, {analysis['total_prefixes']} prefixes)"
                )

        # Restore original signal handlers
        self._restore_signal_handlers()

        # Log if we were interrupted
        if self._interrupted:
            logger.warning(f"⚠ Fetch interrupted - returning {len(results)} partial results")

        return results

    def get_stats(self) -> Dict:
        """Get download statistics from database."""
        if self.db is None:
            return {}

        return self.db.get_stats()

    def get_retry_stats(self, max_attempts: int = None) -> Dict:
        """
        Get statistics on papers that will retry downloading.

        Shows how many papers will be retried within 1 day and 1 week.

        Args:
            max_attempts: Maximum retry attempts (default: uses fetcher's max_attempts)

        Returns:
            Dictionary with retry statistics including summary string

        Example:
            >>> fetcher = PDFFetcher(output_dir="pdfs")
            >>> stats = fetcher.get_retry_stats()
            >>> print(stats['summary'])
            5 papers will retry within 1 day, 12 within 1 week (out of 15 retryable papers)
        """
        if self.db is None:
            return {
                "error": "No database available",
                "total_retry": 0,
                "retry_1_day": 0,
                "retry_1_week": 0
            }

        if max_attempts is None:
            max_attempts = self.max_attempts

        return self.db.get_retry_stats(max_attempts=max_attempts)


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    fetcher = PDFFetcher(output_dir="./test_pdfs")

    # Test single download
    result = fetcher.fetch("10.1007/s10623-024-01403-z")
    print(result)

    # Get stats
    if fetcher.db:
        stats = fetcher.get_stats()
        print("\nStats:", stats)
