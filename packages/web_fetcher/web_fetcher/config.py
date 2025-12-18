"""
Configuration management for PDF Fetcher.

YAML-only configuration for single source of truth.
"""

from pathlib import Path
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field, asdict

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    raise ImportError(
        "PyYAML is required for PDF Fetcher configuration. "
        "Install with: pip install pyyaml"
    )


@dataclass
class PDFFetcherConfig:
    """Configuration for PDFFetcher."""
    
    # Directory configuration
    pdf_dir: str = "./pdfs"
    log_dir: Optional[str] = None  # If None, logs to pdf_dir
    metadata_filename: str = "metadata.json"  # Relative to pdf_dir
    selenium_download_dir: Optional[str] = None  # If None, uses temp dir
    
    # Browser configuration
    headless: bool = True
    user_agent: Optional[str] = None
    
    # Rate limiting
    requests_per_second: float = 1.0
    delay_between_requests: float = 2.0
    delay_between_batches: float = 10.0
    
    # Network configuration
    max_retries: int = 3
    timeout: int = 30
    
    # Cloudflare handling
    cloudflare_skip: bool = True  # If True, skip pages with Cloudflare challenge
    cloudflare_wait_time: float = 10.0  # Seconds to wait for Cloudflare
    
    # Crossref integration
    use_crossref: bool = True  # Try to get PDF URLs from Crossref first
    
    def __post_init__(self):
        """Validate and resolve paths."""
        # Ensure pdf_dir is Path
        self.pdf_dir = str(Path(self.pdf_dir).resolve())
        
        # Resolve log_dir
        if self.log_dir:
            self.log_dir = str(Path(self.log_dir).resolve())
        else:
            self.log_dir = self.pdf_dir
    
    @property
    def metadata_path(self) -> Path:
        """Get full path to metadata file."""
        return Path(self.pdf_dir) / self.metadata_filename
    
    @property
    def log_file_path(self) -> Path:
        """Get full path to log file."""
        return Path(self.log_dir) / "pdf_fetcher.log"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def save(self, path: Union[str, Path]):
        """
        Save configuration to YAML file.
        
        Args:
            path: Path to save to (should end in .yaml or .yml)
        """
        path = Path(path)
        if path.suffix not in ['.yaml', '.yml']:
            raise ValueError(f"Config file must be .yaml or .yml, got: {path.suffix}")
        
        config_dict = self.to_dict()
        
        with open(path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
    
    @classmethod
    def from_file(cls, path: Union[str, Path]) -> 'PDFFetcherConfig':
        """
        Load configuration from YAML file.
        
        Args:
            path: Path to YAML config file (.yaml or .yml)
        
        Returns:
            PDFFetcherConfig instance
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        
        # Verify it's a YAML file
        if path.suffix not in ['.yaml', '.yml']:
            raise ValueError(
                f"Config file must be .yaml or .yml, got: {path.suffix}\n"
                f"PDF Fetcher uses YAML as single source of truth."
            )
        
        with open(path) as f:
            config_dict = yaml.safe_load(f)
        
        return cls(**config_dict)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'PDFFetcherConfig':
        """Create from dictionary."""
        return cls(**config_dict)


def load_config(
    config_file: Optional[Union[str, Path]] = None,
    **kwargs
) -> PDFFetcherConfig:
    """
    Load configuration with priority: kwargs > config_file > defaults.
    
    Args:
        config_file: Optional path to YAML config file
        **kwargs: Override parameters
    
    Returns:
        PDFFetcherConfig instance
    
    Examples:
        # From file
        config = load_config("fetcher_config.yaml")
        
        # From file with overrides
        config = load_config("config.yaml", pdf_dir="./test_pdfs")
        
        # From parameters only
        config = load_config(pdf_dir="./pdfs", log_dir="./logs")
    """
    if config_file:
        config = PDFFetcherConfig.from_file(config_file)
        # Override with kwargs
        for key, value in kwargs.items():
            if hasattr(config, key) and value is not None:
                setattr(config, key, value)
        return config
    else:
        return PDFFetcherConfig(**{k: v for k, v in kwargs.items() if v is not None})


# Example config for documentation
EXAMPLE_CONFIG_YAML = """# PDF Fetcher Configuration
# Save as: fetcher_config.yaml

# ============================================================================
# DIRECTORY CONFIGURATION
# ============================================================================

# Where to save downloaded PDFs
pdf_dir: ./pdfs

# Where to save log files (if null, uses pdf_dir)
log_dir: ./logs

# Metadata filename (relative to pdf_dir)
metadata_filename: metadata.json

# Selenium download directory (if null, uses temp directory)
selenium_download_dir: null

# ============================================================================
# BROWSER CONFIGURATION
# ============================================================================

# Run browser in headless mode (no visible window)
headless: true

# Custom user agent (if null, uses default Chrome user agent)
user_agent: null

# ============================================================================
# RATE LIMITING
# ============================================================================
# These settings help avoid triggering Cloudflare

# Base rate limit per domain (requests per second)
requests_per_second: 1.0

# Delay between individual requests (seconds)
delay_between_requests: 2.0

# Delay between batches (seconds)
delay_between_batches: 10.0

# ============================================================================
# NETWORK CONFIGURATION
# ============================================================================

# Maximum retry attempts for network errors
max_retries: 3

# Request timeout (seconds)
timeout: 30

# ============================================================================
# CLOUDFLARE HANDLING
# ============================================================================

# Skip pages with Cloudflare challenge (recommended: true)
cloudflare_skip: true

# How long to wait for Cloudflare challenge (seconds)
cloudflare_wait_time: 10.0

# ============================================================================
# CROSSREF INTEGRATION
# ============================================================================

# Try to get PDF URLs from Crossref API first (recommended: true)
# This bypasses publisher landing pages when possible
use_crossref: true
"""


def create_example_config(path: Union[str, Path] = "fetcher_config.yaml"):
    """
    Create an example configuration file.
    
    Args:
        path: Where to save the example config (default: fetcher_config.yaml)
    """
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"Config file already exists: {path}")
    
    with open(path, 'w') as f:
        f.write(EXAMPLE_CONFIG_YAML)
    
    print(f"Created example config: {path}")
    print("Edit this file and use with: PDFFetcher(config_file='fetcher_config.yaml')")
