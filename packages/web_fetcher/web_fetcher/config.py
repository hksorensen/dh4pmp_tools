"""
Configuration management for PDF Fetcher v2.

Supports configuration via:
1. Constructor parameters (highest priority)
2. Config file (YAML or JSON)
3. Defaults (lowest priority)
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field, asdict

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


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
    
    def save(self, path: Union[str, Path], format: str = "yaml"):
        """
        Save configuration to file.
        
        Args:
            path: Path to save to
            format: 'yaml' or 'json'
        """
        path = Path(path)
        config_dict = self.to_dict()
        
        if format == "yaml":
            if not YAML_AVAILABLE:
                raise ImportError("PyYAML is required for YAML config files. Install with: pip install pyyaml")
            with open(path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False)
        elif format == "json":
            with open(path, 'w') as f:
                json.dump(config_dict, f, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'yaml' or 'json'")
    
    @classmethod
    def from_file(cls, path: Union[str, Path]) -> 'PDFFetcherConfig':
        """
        Load configuration from file.
        
        Args:
            path: Path to config file (.yaml, .yml, or .json)
        
        Returns:
            PDFFetcherConfig instance
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        
        # Determine format from extension
        ext = path.suffix.lower()
        
        if ext in ('.yaml', '.yml'):
            if not YAML_AVAILABLE:
                raise ImportError("PyYAML is required for YAML config files. Install with: pip install pyyaml")
            with open(path) as f:
                config_dict = yaml.safe_load(f)
        elif ext == '.json':
            with open(path) as f:
                config_dict = json.load(f)
        else:
            raise ValueError(f"Unsupported config file extension: {ext}. Use .yaml, .yml, or .json")
        
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
        config_file: Optional path to config file
        **kwargs: Override parameters
    
    Returns:
        PDFFetcherConfig instance
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


# Example config files for documentation
EXAMPLE_CONFIG_YAML = """
# PDF Fetcher v2 Configuration

# Directory configuration
pdf_dir: "./pdfs"
log_dir: "./logs"  # Optional: separate log directory
metadata_filename: "metadata.json"
selenium_download_dir: null  # null = use temp directory

# Browser configuration
headless: true
user_agent: null  # null = use default Chrome user agent

# Rate limiting (helps avoid Cloudflare triggers)
requests_per_second: 1.0
delay_between_requests: 2.0
delay_between_batches: 10.0

# Network configuration
max_retries: 3
timeout: 30

# Cloudflare handling
cloudflare_skip: true  # Skip pages with Cloudflare challenge
cloudflare_wait_time: 10.0

# Crossref integration
use_crossref: true  # Try Crossref for PDF URLs first
"""

EXAMPLE_CONFIG_JSON = """{
  "pdf_dir": "./pdfs",
  "log_dir": "./logs",
  "metadata_filename": "metadata.json",
  "selenium_download_dir": null,
  "headless": true,
  "user_agent": null,
  "requests_per_second": 1.0,
  "delay_between_requests": 2.0,
  "delay_between_batches": 10.0,
  "max_retries": 3,
  "timeout": 30,
  "cloudflare_skip": true,
  "cloudflare_wait_time": 10.0,
  "use_crossref": true
}
"""
