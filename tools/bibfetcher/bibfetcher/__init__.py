"""
bibfetcher - Fetch bibliographic metadata from DOI, ISBN, arXiv, or PDF files.

Main exports:
- BibFetcher: Main coordinator class
- CrossrefFetcher: Fetch from Crossref API
- DOIFetcher: Fetch from DOI resolver
- EntryProcessor: Post-process entries with custom hooks
"""

from .bibfetcher import BibFetcher
from .fetchers import CrossrefFetcher, DOIFetcher
from .input_identifier import identify_input, InputType
from .postprocessor import EntryProcessor, get_processor

__version__ = '0.4.1'

__all__ = [
    'BibFetcher',
    'CrossrefFetcher',
    'DOIFetcher',
    'identify_input',
    'InputType',
    'EntryProcessor',
    'get_processor',
]
