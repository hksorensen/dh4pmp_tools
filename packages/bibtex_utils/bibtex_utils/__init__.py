"""
BibTeX Utilities

Tools for working with BibTeX entries:
- Citation formatting using pandoc
- BibTeX parsing and manipulation
"""

from .citation_formatter import CitationFormatter, format_citation

__version__ = '0.1.0'

__all__ = [
    'CitationFormatter',
    'format_citation',
]
