"""
BibTeX citation key generation.

Generates unique citation keys in the format: FirstAuthorLastName{Year}{suffix}
Example: Lin2014a
"""

from pathlib import Path
from typing import Optional, List
import re
import string
import bibtexparser

from .latex import normalize_bibkey_chars


def extract_first_author_lastname(entry: dict) -> str:
    """Extract last name of first author from BibTeX entry.
    
    Args:
        entry: BibTeX entry dictionary with 'author' or 'editor' field
        
    Returns:
        Last name of first author
        
    Raises:
        ValueError: If no author or editor found
    """
    # Try author first, then editor
    name_field = entry.get('author') or entry.get('editor')
    
    if not name_field:
        raise ValueError("No author or editor found in entry")
    
    # Split by 'and' to get individual authors
    authors = name_field.split(' and ')
    
    if not authors:
        raise ValueError("Could not parse author field")
    
    # Parse first author's name using bibtexparser
    first_author = authors[0].strip()
    
    # bibtexparser v1 API
    if int(bibtexparser.__version__[0]) == 1:
        try:
            parsed_names = bibtexparser.customization.getnames([first_author])
            name_parts = bibtexparser.customization.splitname(parsed_names[0])
            last_name = ' '.join(name_parts['last'])
        except (bibtexparser.customization.InvalidName, KeyError):
            # Fallback: take last word as last name
            last_name = first_author.split()[-1]
    else:
        # Fallback for v2 or parsing failure
        last_name = first_author.split()[-1]
    
    return last_name


def extract_year(entry: dict) -> str:
    """Extract year from BibTeX entry.
    
    Args:
        entry: BibTeX entry dictionary
        
    Returns:
        Year as string
        
    Raises:
        ValueError: If no year or date found
    """
    # Try 'year' field first
    if 'year' in entry:
        return str(entry['year'])
    
    # Try 'date' field (format: YYYY-MM-DD or YYYY)
    if 'date' in entry:
        date_str = entry['date']
        # Extract year (first 4 digits)
        year_match = re.match(r'(\d{4})', date_str)
        if year_match:
            return year_match.group(1)
    
    raise ValueError("No year or date found in entry")


def generate_bibkey_prefix(entry: dict) -> str:
    """Generate BibTeX key prefix (before suffix).
    
    Format: FirstAuthorLastName{Year}
    Example: Lin2014 (not lin2014 or LIN2014)
    
    Args:
        entry: BibTeX entry dictionary
        
    Returns:
        Key prefix (without suffix) in title case
        
    Raises:
        ValueError: If required fields are missing
    """
    last_name = extract_first_author_lastname(entry)
    year = extract_year(entry)
    
    # Remove non-alphanumeric characters
    pattern = re.compile(r'[\W_]+')
    last_name = pattern.sub('', last_name)
    
    # Normalize special characters (ö → o, etc.)
    last_name = normalize_bibkey_chars(last_name)
    
    # Ensure title case: First letter uppercase, rest lowercase
    # This handles SMITH → Smith and smith → Smith
    if last_name:
        last_name = last_name[0].upper() + last_name[1:].lower()
    
    return f"{last_name}{year}"


def find_unique_suffix(prefix: str, existing_keys: List[str]) -> str:
    """Find unique suffix for BibTeX key.
    
    Tries 'a', 'b', 'c', ... until an unused key is found.
    
    Args:
        prefix: Key prefix (e.g., "Lin2014")
        existing_keys: List of existing citation keys
        
    Returns:
        Single letter suffix ('a', 'b', 'c', ...)
    """
    for suffix in string.ascii_lowercase:
        candidate = f"{prefix}{suffix}"
        if candidate not in existing_keys:
            return suffix
    
    # If we've exhausted lowercase letters, raise an error
    raise ValueError(f"Cannot generate unique key for prefix {prefix} (all suffixes a-z used)")


def generate_bibkey(entry: dict, existing_keys: Optional[List[str]] = None) -> str:
    """Generate unique BibTeX citation key.
    
    Format: FirstAuthorLastName{Year}{suffix}
    Example: Lin2014a
    
    Args:
        entry: BibTeX entry dictionary with author/editor and year
        existing_keys: Optional list of existing keys to check for uniqueness
        
    Returns:
        Unique BibTeX citation key
        
    Raises:
        ValueError: If required fields are missing
    """
    if existing_keys is None:
        existing_keys = []
    
    prefix = generate_bibkey_prefix(entry)
    suffix = find_unique_suffix(prefix, existing_keys)
    
    return f"{prefix}{suffix}"


def check_key_exists(key: str, index_data: dict) -> bool:
    """Check if BibTeX key exists in citation_tools index.
    
    Args:
        key: BibTeX citation key to check
        index_data: citation_tools index data (loaded JSON)
        
    Returns:
        True if key exists, False otherwise
    """
    if not index_data or 'index' not in index_data:
        return False
    
    return key in index_data['index']


def get_existing_keys_from_index(index_data: dict, prefix: str) -> List[str]:
    """Get all existing keys matching a prefix from citation_tools index.
    
    Args:
        index_data: citation_tools index data (loaded JSON)
        prefix: Key prefix to match (e.g., "Lin2014")
        
    Returns:
        List of matching keys
    """
    if not index_data or 'index' not in index_data:
        return []
    
    return [key for key in index_data['index'].keys() if key.startswith(prefix)]
