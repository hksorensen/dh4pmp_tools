"""
Integration with citation_tools index for duplicate detection.

Reads citation_tools BibTeX index to check if entries already exist.
"""

from pathlib import Path
from typing import Optional, Dict
import json

from .config import get_citation_tools_index_path


def load_citation_tools_index() -> Optional[Dict]:
    """Load citation_tools index if available.
    
    Returns:
        Index data dictionary, or None if index not found
    """
    index_path = get_citation_tools_index_path()
    
    if index_path is None or not index_path.exists():
        return None
    
    try:
        with open(index_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def check_doi_exists(doi: str, index_data: Optional[Dict] = None) -> Optional[str]:
    """Check if DOI exists in citation_tools index.
    
    Args:
        doi: DOI to check
        index_data: Optional pre-loaded index data
        
    Returns:
        BibTeX key if found, None otherwise
    """
    if index_data is None:
        index_data = load_citation_tools_index()
    
    if not index_data or 'index' not in index_data:
        return None
    
    # Search through index for matching DOI
    for key, entry_info in index_data['index'].items():
        # If index has DOI field, check it
        if 'doi' in entry_info and entry_info['doi'] == doi:
            return key
    
    return None


def check_key_exists(bibkey: str, index_data: Optional[Dict] = None) -> bool:
    """Check if BibTeX key exists in citation_tools index.
    
    Args:
        bibkey: BibTeX citation key to check
        index_data: Optional pre-loaded index data
        
    Returns:
        True if key exists, False otherwise
    """
    if index_data is None:
        index_data = load_citation_tools_index()
    
    if not index_data or 'index' not in index_data:
        return False
    
    return bibkey in index_data['index']


def get_entry_info(bibkey: str, index_data: Optional[Dict] = None) -> Optional[Dict]:
    """Get entry information from citation_tools index.
    
    Args:
        bibkey: BibTeX citation key
        index_data: Optional pre-loaded index data
        
    Returns:
        Entry info dictionary, or None if not found
    """
    if index_data is None:
        index_data = load_citation_tools_index()
    
    if not index_data or 'index' not in index_data:
        return None
    
    return index_data['index'].get(bibkey)


def get_all_keys(index_data: Optional[Dict] = None) -> list:
    """Get all BibTeX keys from citation_tools index.
    
    Args:
        index_data: Optional pre-loaded index data
        
    Returns:
        List of all citation keys
    """
    if index_data is None:
        index_data = load_citation_tools_index()
    
    if not index_data or 'index' not in index_data:
        return []
    
    return list(index_data['index'].keys())
