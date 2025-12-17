"""
Configuration management for bibfetcher.

Provides monorepo-aware configuration and cache directory detection,
following the same pattern as citation_tools.
"""

from pathlib import Path
from typing import Optional
import os


def find_monorepo_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find monorepo root by looking for .git directory.
    
    Args:
        start_path: Starting directory. Defaults to current working directory.
        
    Returns:
        Path to monorepo root, or None if not in a monorepo
    """
    if start_path is None:
        start_path = Path.cwd()
    
    current = Path(start_path).resolve()
    
    # Walk up the directory tree
    for parent in [current] + list(current.parents):
        if (parent / '.git').exists():
            return parent
    
    return None


def get_cache_dir(package_name: str = 'bibfetcher') -> Path:
    """Get cache directory, monorepo-aware.
    
    Priority:
    1. {monorepo_root}/.cache/{package_name}/
    2. ~/.cache/{package_name}/
    
    Args:
        package_name: Name of the package
        
    Returns:
        Path to cache directory (created if doesn't exist)
    """
    monorepo_root = find_monorepo_root()
    
    if monorepo_root:
        cache_dir = monorepo_root / '.cache' / package_name
    else:
        cache_dir = Path.home() / '.cache' / package_name
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_config_dir(package_name: str = 'bibfetcher') -> Path:
    """Get config directory, monorepo-aware.
    
    Priority:
    1. {monorepo_root}/config/{package_name}/
    2. ~/.config/{package_name}/
    
    Args:
        package_name: Name of the package
        
    Returns:
        Path to config directory (created if doesn't exist)
    """
    monorepo_root = find_monorepo_root()
    
    if monorepo_root:
        config_dir = monorepo_root / 'config' / package_name
    else:
        config_dir = Path.home() / '.config' / package_name
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_citation_tools_index_path() -> Optional[Path]:
    """Get path to citation_tools index if available.
    
    Looks for citation_tools index in:
    1. {monorepo_root}/.cache/citation_tools/bibtex_index.json
    2. ~/.cache/citation_tools/bibtex_index.json
    
    Returns:
        Path to index file if it exists, None otherwise
    """
    monorepo_root = find_monorepo_root()
    
    # Try monorepo location first
    if monorepo_root:
        index_path = monorepo_root / '.cache' / 'citation_tools' / 'bibtex_index.json'
        if index_path.exists():
            return index_path
    
    # Try user home location
    index_path = Path.home() / '.cache' / 'citation_tools' / 'bibtex_index.json'
    if index_path.exists():
        return index_path
    
    return None
