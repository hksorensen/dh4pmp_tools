"""
Crossref API fetcher for bibliographic metadata.

Fetches metadata from the Crossref API using DOI or ISBN.
"""

from typing import Optional, Dict, List
import requests
import re
import html

from .base import BaseFetcher
from ..utils.latex import text_to_latex, text_to_latex_preserve_danish, ucfirst


class CrossrefFetcher(BaseFetcher):
    """Fetch bibliographic metadata from Crossref API."""
    
    def __init__(self):
        """Initialize Crossref fetcher."""
        super().__init__()
        self.base_url = "https://api.crossref.org/works"
    
    def validate_identifier(self, identifier: str) -> bool:
        """Validate DOI or ISBN format.
        
        Args:
            identifier: DOI or ISBN to validate
            
        Returns:
            True if valid DOI or ISBN
        """
        # Check for DOI
        if re.match(r'^10\.\d{4,}/\S+$', identifier):
            return True
        
        # Check for ISBN
        isbn_clean = re.sub(r'[-\s]', '', identifier)
        if re.match(r'^(978|979)?\d{9}[\dXx]$', isbn_clean):
            return True
        
        return False
    
    def fetch(self, identifier: str, mode: str = 'doi') -> Optional[Dict]:
        """Fetch metadata from Crossref.
        
        Args:
            identifier: DOI or ISBN to fetch
            mode: 'doi' or 'isbn'
            
        Returns:
            Crossref metadata dictionary or None if not found
            
        Raises:
            ValueError: If identifier is invalid
            RuntimeError: If API request fails
        """
        if mode == 'doi':
            url = f"{self.base_url}/{identifier}"
        elif mode == 'isbn':
            # ISBN bibliographic search
            if isinstance(identifier, list):
                isbn_list = identifier
            else:
                isbn_list = [identifier]
            query_params = "&".join([f"query.bibliographic={isbn}" for isbn in isbn_list])
            url = f"{self.base_url}?rows=100&{query_params}"
        else:
            raise ValueError(f"Invalid mode: {mode} (must be 'doi' or 'isbn')")
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if 'message' not in data:
                return None
            
            return data['message']
        
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Timeout fetching from Crossref: {url}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch from Crossref: {e}")
    
    def to_bibtex_entry(self, metadata: Dict, entry_type: Optional[str] = None) -> Dict:
        """Convert Crossref metadata to BibTeX entry.
        
        Args:
            metadata: Crossref API response
            entry_type: Optional override for entry type
            
        Returns:
            BibTeX entry dictionary
        """
        if entry_type is None:
            entry_type = metadata.get('type', 'article')
        
        # Helper function for formatting authors
        def format_authors(author_list):
            if not author_list:
                return None
            authors = []
            for author in author_list:
                given = author.get('given', '')
                family = author.get('family', '')
                if given and family:
                    authors.append(f"{given} {family}")
                elif family:
                    authors.append(family)
            return " and ".join(authors) if authors else None
        
        # Common fields
        entry = {}
        
        # Title (join if list)
        title = metadata.get('title', [])
        if isinstance(title, list):
            title = ": ".join(title)
        entry['title'] = html.unescape(title) if title else None
        
        # Subtitle
        subtitle = metadata.get('subtitle', [])
        if isinstance(subtitle, list) and subtitle:
            entry['subtitle'] = html.unescape(" ".join(subtitle))
        
        # Authors
        entry['author'] = format_authors(metadata.get('author', []))
        
        # Editors (for books)
        entry['editor'] = format_authors(metadata.get('editor', []))
        
        # Year
        published = metadata.get('published', {}).get('date-parts', [[]])[0]
        if published:
            entry['year'] = str(published[0])
        
        # DOI
        entry['doi'] = metadata.get('DOI')
        
        # Type-specific fields
        if entry_type in ['book', 'monograph']:
            entry['ENTRYTYPE'] = 'book'
            entry['publisher'] = metadata.get('publisher')
            entry['address'] = metadata.get('publisher-location')
            
            isbn = metadata.get('ISBN', [])
            if isbn:
                entry['isbn'] = ", ".join(isbn)
            
            entry['volume'] = metadata.get('volume')
        
        elif entry_type == 'journal-article':
            entry['ENTRYTYPE'] = 'article'
            
            # Journal name
            container = metadata.get('container-title', [])
            if isinstance(container, list) and container:
                entry['journal'] = ": ".join(container)
            
            entry['volume'] = metadata.get('volume')
            entry['number'] = metadata.get('issue')
            entry['pages'] = metadata.get('page')
        
        elif entry_type == 'book-chapter':
            entry['ENTRYTYPE'] = 'incollection'
            
            # Book title
            container = metadata.get('container-title', [])
            if isinstance(container, list) and container:
                entry['booktitle'] = " ".join(container)
            
            entry['pages'] = metadata.get('page')
            entry['volume'] = metadata.get('volume')
        
        else:
            # Default to misc
            entry['ENTRYTYPE'] = 'misc'
        
        # Clean up None values
        entry = {k: v for k, v in entry.items() if v is not None}
        
        # Apply LaTeX formatting to text fields
        text_fields = ['title', 'subtitle', 'journal', 'booktitle', 'publisher']
        for field in text_fields:
            if field in entry and entry[field]:
                entry[field] = text_to_latex(entry[field])

        # Apply Danish-preserving LaTeX formatting to name fields (for proper sorting)
        name_fields = ['author', 'editor']
        for field in name_fields:
            if field in entry and entry[field]:
                entry[field] = text_to_latex_preserve_danish(entry[field])
        
        # Split title/subtitle if colon present and subtitle not already set
        if 'title' in entry and 'subtitle' not in entry:
            if ':' in entry['title'] or '?' in entry['title']:
                parts = re.split(r'[:\?]', entry['title'], maxsplit=1)
                if len(parts) == 2:
                    entry['title'] = parts[0].strip()
                    if '?' in entry['title']:
                        entry['title'] += '?'
                    if parts[1].strip():
                        entry['subtitle'] = ucfirst(parts[1].strip())
        
        return entry
