"""
Citation Tools - BibTeX to formatted citation converter.

Convert BibTeX entries to formatted citations using CSL styles.
Supports multiple output formats including Word documents and clipboard.

Main functions:
    - bibtex_to_citation: Convert BibTeX string to citation
    - bibtex_to_citation_from_key: Convert using citation key lookup
    - BibTeXIndex: Manage BibTeX file index
    - CSLStyleManager: Manage CSL styles

Example:
    >>> from citation_tools import bibtex_to_citation
    >>> bibtex = '@article{Doe2024, author={Doe, John}, ...}'
    >>> citation = bibtex_to_citation(bibtex, style='apa', output_format='plain')
"""

__version__ = '0.1.0'

from .citation_converter import (
    bibtex_to_citation,
    bibtex_to_citation_from_key,
)
from .bibtex_index import BibTeXIndex
from .csl_manager import CSLStyleManager
from .config import (
    get_cache_dir,
    get_config_dir,
    get_default_index_path,
)
from .user_config import UserConfig, get_user_config

__all__ = [
    'bibtex_to_citation',
    'bibtex_to_citation_from_key',
    'BibTeXIndex',
    'CSLStyleManager',
    'UserConfig',
    'get_user_config',
    'get_cache_dir',
    'get_config_dir',
    'get_default_index_path',
]
