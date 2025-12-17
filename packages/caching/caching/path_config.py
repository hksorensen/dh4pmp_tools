"""
Path configuration management for DH4PMP monorepo.

Provides centralized path configuration with:
- XDG Base Directory defaults (Unix standard)
- Optional config.yaml override at repo root
- Automatic directory creation

This allows machine-specific paths without committing them to git.
"""

from pathlib import Path
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Try to import yaml, but make it optional
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    logger.debug("PyYAML not installed, config.yaml support disabled")


def get_repo_root() -> Optional[Path]:
    """
    Find repo root by looking for .git directory.
    
    Returns:
        Path to repo root, or None if not in a git repo
    """
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / '.git').exists():
            return current
        current = current.parent
    return None


def get_default_paths() -> dict:
    """
    Get default paths following XDG Base Directory specification.
    
    Returns:
        Dict with default paths for cache, data, and results
    """
    xdg_cache = Path(os.getenv('XDG_CACHE_HOME', '~/.cache')).expanduser()
    xdg_data = Path(os.getenv('XDG_DATA_HOME', '~/.local/share')).expanduser()
    
    return {
        'paths': {
            'cache_dir': xdg_cache / 'dh4pmp',
            'data_dir': xdg_data / 'dh4pmp',
            'results_dir': Path.home() / 'results/dh4pmp',
        }
    }


def get_path_config() -> dict:
    """
    Load path configuration from config.yaml if it exists, otherwise use defaults.
    
    Looks for config.yaml in the repo root. If found, loads it.
    If not found or if PyYAML is not installed, uses XDG defaults.
    
    Returns:
        Configuration dictionary with 'paths' section
    """
    # Try to load from config.yaml
    if HAS_YAML:
        repo_root = get_repo_root()
        if repo_root:
            config_file = repo_root / 'config.yaml'
            if config_file.exists():
                try:
                    with open(config_file) as f:
                        config = yaml.safe_load(f)
                        logger.debug(f"Loaded configuration from {config_file}")
                        return config
                except Exception as e:
                    logger.warning(f"Error loading config.yaml: {e}, using defaults")
    
    # Fall back to defaults
    return get_default_paths()


def get_path(key: str, create: bool = True) -> Path:
    """
    Get configured path by key.
    
    Args:
        key: Path key (e.g., 'cache_dir', 'data_dir', 'results_dir')
        create: If True, create directory if it doesn't exist
        
    Returns:
        Configured path as Path object
        
    Raises:
        KeyError: If key is not found in configuration
    """
    config = get_path_config()
    
    if 'paths' not in config or key not in config['paths']:
        raise KeyError(f"Path '{key}' not found in configuration")
    
    path = Path(config['paths'][key])
    
    if create:
        try:
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured path exists: {path}")
        except Exception as e:
            logger.warning(f"Could not create directory {path}: {e}")
    
    return path


# Convenience functions for common paths
def get_cache_dir(create: bool = True) -> Path:
    """Get cache directory path."""
    return get_path('cache_dir', create=create)


def get_data_dir(create: bool = True) -> Path:
    """Get data directory path."""
    return get_path('data_dir', create=create)


def get_results_dir(create: bool = True) -> Path:
    """Get results directory path."""
    return get_path('results_dir', create=create)


def print_path_config():
    """Print current path configuration for debugging."""
    config = get_path_config()
    print("Current path configuration:")
    print("-" * 50)
    for key, value in config.get('paths', {}).items():
        print(f"  {key:20s}: {value}")
    print("-" * 50)
    
    repo_root = get_repo_root()
    if repo_root:
        config_file = repo_root / 'config.yaml'
        if config_file.exists():
            print(f"Loaded from: {config_file}")
        else:
            print(f"Using defaults (no config.yaml found at {repo_root})")
    else:
        print("Using defaults (not in a git repository)")


# Example usage
if __name__ == "__main__":
    # Print current configuration
    print_path_config()
    print()
    
    # Test path retrieval
    print("Testing path retrieval:")
    cache = get_cache_dir(create=False)
    data = get_data_dir(create=False)
    results = get_results_dir(create=False)
    
    print(f"Cache:   {cache}")
    print(f"Data:    {data}")
    print(f"Results: {results}")
