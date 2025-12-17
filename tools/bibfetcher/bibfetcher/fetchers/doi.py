"""
DOI resolver fetcher for bibliographic metadata.

Fetches BibTeX directly from DOI content negotiation.
"""

from typing import Optional, Dict
import requests
import re
import bibtexparser

from .base import BaseFetcher


class DOIFetcher(BaseFetcher):
    """Fetch BibTeX directly from DOI resolution service."""
    
    def __init__(self):
        """Initialize DOI fetcher."""
        super().__init__()
        self.doi_base_url = "http://dx.doi.org"
    
    def validate_identifier(self, identifier: str) -> bool:
        """Validate DOI format.
        
        Args:
            identifier: DOI to validate
            
        Returns:
            True if valid DOI format
        """
        # Remove common prefixes
        doi = self._extract_doi(identifier)
        return re.match(r'^10\.\d{4,}/\S+$', doi) is not None
    
    def _extract_doi(self, identifier: str) -> str:
        """Extract clean DOI from various formats.
        
        Args:
            identifier: DOI string (possibly with URL prefix)
            
        Returns:
            Clean DOI (e.g., "10.1234/example")
        """
        identifier = identifier.strip()
        
        # Remove URL prefixes
        if identifier.startswith('https://doi.org/'):
            return identifier.replace('https://doi.org/', '')
        elif identifier.startswith('http://dx.doi.org/'):
            return identifier.replace('http://dx.doi.org/', '')
        elif identifier.startswith('http://doi.org/'):
            return identifier.replace('http://doi.org/', '')
        
        return identifier
    
    def fetch(self, identifier: str, **kwargs) -> Optional[Dict]:
        """Fetch BibTeX from DOI resolver.
        
        Args:
            identifier: DOI to fetch
            **kwargs: Additional arguments (ignored)
            
        Returns:
            BibTeX entry dictionary or None if not found
            
        Raises:
            ValueError: If DOI is invalid
            RuntimeError: If fetch fails
        """
        if not self.validate_identifier(identifier):
            raise ValueError(f"Invalid DOI format: {identifier}")
        
        doi = self._extract_doi(identifier)
        url = f"{self.doi_base_url}/{doi}"
        
        # Request BibTeX format via content negotiation
        headers = {'Accept': 'application/x-bibtex'}
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            bibtex_str = response.text
            
            # Parse the BibTeX string
            bib_db = bibtexparser.loads(bibtex_str, self.parser)
            
            if not bib_db.entries:
                return None
            
            # Return first entry
            return bib_db.entries[0]
        
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Timeout fetching DOI: {url}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch DOI: {e}")
        except Exception as e:
            raise RuntimeError(f"Error parsing BibTeX from DOI: {e}")
    
    def to_bibtex_entry(self, metadata: Dict) -> Dict:
        """DOI fetcher returns BibTeX directly.
        
        Args:
            metadata: Already a BibTeX entry
            
        Returns:
            Same dictionary (no conversion needed)
        """
        return metadata
