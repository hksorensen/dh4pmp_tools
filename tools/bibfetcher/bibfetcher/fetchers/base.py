"""
Base class for bibliographic metadata fetchers.

Provides abstract interface that all fetchers must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List
import bibtexparser


class BaseFetcher(ABC):
    """Abstract base class for metadata fetchers.
    
    All fetcher implementations (Crossref, DOI, arXiv, Scopus) should inherit
    from this class and implement the fetch() method.
    """
    
    def __init__(self):
        """Initialize the fetcher."""
        # Setup bibtexparser (pin to v1)
        if int(bibtexparser.__version__[0]) == 1:
            self.parser = bibtexparser.bparser.BibTexParser()
            self.parser.ignore_nonstandard_types = False
            self.parser.expect_multiple_parse = True
            
            self.writer = bibtexparser.bwriter.BibTexWriter()
            self.writer.display_order = [
                'author', 'title', 'subtitle', 'year', 'journal',
                'crossref', 'booktitle', 'editor', 'volume', 'number',
                'pages', 'doi', 'isbn', 'publisher'
            ]
            self.writer.add_trailing_comma = True
        else:
            raise NotImplementedError(
                f"bibtexparser version {bibtexparser.__version__} is not supported. "
                "Please install bibtexparser v1: pip install 'bibtexparser>=1.2.0,<2.0'"
            )
    
    @abstractmethod
    def fetch(self, identifier: str, **kwargs) -> Optional[Dict]:
        """Fetch bibliographic metadata for an identifier.
        
        Args:
            identifier: The identifier to fetch (DOI, ISBN, etc.)
            **kwargs: Additional fetcher-specific parameters
            
        Returns:
            Dictionary with bibliographic metadata, or None if not found
            
        Raises:
            ValueError: If identifier is invalid
            RuntimeError: If fetch fails
        """
        pass
    
    @abstractmethod
    def validate_identifier(self, identifier: str) -> bool:
        """Validate that an identifier is in the correct format.
        
        Args:
            identifier: The identifier to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    def to_bibtex_entry(self, metadata: Dict) -> Dict:
        """Convert fetched metadata to BibTeX entry format.
        
        Args:
            metadata: Raw metadata dictionary
            
        Returns:
            BibTeX entry dictionary with standardized fields
        """
        # Default implementation - subclasses should override if needed
        return metadata
    
    def to_bibtex_string(self, entries: List[Dict]) -> str:
        """Convert BibTeX entries to formatted string.
        
        Args:
            entries: List of BibTeX entry dictionaries
            
        Returns:
            Formatted BibTeX string
        """
        # Create a temporary database with the entries
        bib_db = bibtexparser.bibdatabase.BibDatabase()
        bib_db.entries = entries
        
        # Write to string
        return bibtexparser.dumps(bib_db, self.writer)
