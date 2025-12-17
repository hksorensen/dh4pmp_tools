"""
Configuration and cache management for citation tools.

Provides monorepo-aware cache and config directories, preferring project-local
locations when inside a monorepo, falling back to user directories otherwise.
"""

from pathlib import Path
from typing import Optional
import os


def get_project_root() -> Optional[Path]:
    """Find monorepo root by looking for .git or pyproject.toml.
    
    Returns:
        Path to project root, or None if not in a project
    """
    current = Path.cwd()
    
    for parent in [current] + list(current.parents):
        if (parent / '.git').exists() or (parent / 'pyproject.toml').exists():
            return parent
    
    return None


def get_cache_dir(
    app_name: str = 'citation_tools',
    use_project_cache: bool = True
) -> Path:
    """Get cache directory, preferring project-local cache in monorepo.
    
    Args:
        app_name: Application name for cache subdirectory
        use_project_cache: If True and in monorepo, use .cache/ in project root
        
    Returns:
        Path to cache directory (created if doesn't exist)
    """
    # Try to use project-local cache if in monorepo
    if use_project_cache:
        project_root = get_project_root()
        if project_root:
            cache_dir = project_root / '.cache' / app_name
            cache_dir.mkdir(parents=True, exist_ok=True)
            return cache_dir
    
    # Fall back to user cache directory
    if os.name == 'nt':  # Windows
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:  # macOS, Linux
        base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
    
    cache_dir = base / app_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_config_dir(
    app_name: str = 'citation_tools',
    use_project_config: bool = True
) -> Path:
    """Get config directory, preferring project-local config in monorepo.
    
    Args:
        app_name: Application name for config subdirectory
        use_project_config: If True and in monorepo, use config/ in project root
        
    Returns:
        Path to config directory (created if doesn't exist)
    """
    # Try to use project-local config if in monorepo
    if use_project_config:
        project_root = get_project_root()
        if project_root:
            config_dir = project_root / 'config' / app_name
            config_dir.mkdir(parents=True, exist_ok=True)
            return config_dir
    
    # Fall back to user config directory
    if os.name == 'nt':  # Windows
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    else:  # macOS, Linux
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    
    config_dir = base / app_name
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_default_index_path() -> Path:
    """Get default path for BibTeX index file.
    
    Returns:
        Path to index file in cache directory
    """
    cache_dir = get_cache_dir()
    return cache_dir / 'bibtex_index.json'
