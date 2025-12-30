"""
Format BibTeX entries as full citations using pandoc.

Requires: pandoc (install with: brew install pandoc)
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List
import re


class CitationFormatter:
    """
    Convert BibTeX to formatted citations using pandoc.

    Example:
        >>> formatter = CitationFormatter()
        >>> citation = formatter.format_bibtex(bibtex_str, style='apa')
        >>> print(citation)
        "Sorensen, H. K. (2024). Diagram Detector..."
    """

    def __init__(self, csl_style: str = 'apa'):
        """
        Initialize formatter.

        Args:
            csl_style: Citation style (apa, chicago, ieee, nature, etc.)
                      See: https://github.com/citation-style-language/styles
        """
        self.csl_style = csl_style
        self._check_pandoc()

    def _check_pandoc(self):
        """Check if pandoc is installed."""
        try:
            subprocess.run(['pandoc', '--version'],
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "pandoc not found. Install with: brew install pandoc"
            )

    def format_bibtex(self, bibtex: str, style: Optional[str] = None,
                     nocite: bool = True) -> str:
        """
        Convert BibTeX entry to formatted citation.

        Args:
            bibtex: BibTeX entry string
            style: Citation style (overrides default if provided)
            nocite: If True, format without in-text citation

        Returns:
            Formatted citation string

        Example:
            >>> bibtex = "@article{key2024, author={Doe, John}, ...}"
            >>> citation = formatter.format_bibtex(bibtex)
        """
        style = style or self.csl_style

        # Write BibTeX to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib',
                                        delete=False) as bib_file:
            bib_file.write(bibtex)
            bib_path = bib_file.name

        # Create minimal markdown file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md',
                                        delete=False) as md_file:
            if nocite:
                # Use nocite to render bibliography without citations
                md_file.write("---\nnocite: '@*'\n---\n")
            else:
                # Extract cite key from bibtex
                match = re.search(r'@\w+\{([^,]+),', bibtex)
                if match:
                    citekey = match.group(1)
                    md_file.write(f"[@{citekey}]")
            md_path = md_file.name

        try:
            # Run pandoc
            cmd = [
                'pandoc',
                md_path,
                '--citeproc',
                f'--bibliography={bib_path}',
                f'--csl={style}',
                '-t', 'plain',
                '--wrap=none'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            citation = result.stdout.strip()

            # Clean up output
            if nocite:
                # Remove "References" header if present
                lines = citation.split('\n')
                citation = '\n'.join(line for line in lines
                                   if line and not line.lower().startswith('reference'))
                citation = citation.strip()

            return citation

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Pandoc error: {e.stderr}")

        finally:
            # Cleanup temp files
            Path(bib_path).unlink(missing_ok=True)
            Path(md_path).unlink(missing_ok=True)

    def format_batch(self, bibtex_entries: List[str],
                    style: Optional[str] = None) -> List[str]:
        """
        Format multiple BibTeX entries.

        Args:
            bibtex_entries: List of BibTeX strings
            style: Citation style

        Returns:
            List of formatted citations

        Example:
            >>> entries = [bibtex1, bibtex2, bibtex3]
            >>> citations = formatter.format_batch(entries, style='chicago')
        """
        return [self.format_bibtex(bib, style=style) for bib in bibtex_entries]

    def format_doi(self, doi: str, style: Optional[str] = None) -> str:
        """
        Fetch BibTeX for DOI and format as citation.

        Args:
            doi: DOI string
            style: Citation style

        Returns:
            Formatted citation

        Example:
            >>> citation = formatter.format_doi('10.1007/s10623-024-01403-z')
        """
        from bibfetcher import BibFetcher

        fetcher = BibFetcher()
        result = fetcher.fetch(doi)

        if result.bibtex:
            return self.format_bibtex(result.bibtex, style=style)
        else:
            raise ValueError(f"Could not fetch BibTeX for DOI: {doi}")

    def get_available_styles(self) -> List[str]:
        """
        Get list of commonly used CSL styles.

        Returns:
            List of style names
        """
        return [
            'apa',           # American Psychological Association
            'chicago',       # Chicago Manual of Style
            'ieee',          # IEEE
            'nature',        # Nature
            'science',       # Science
            'vancouver',     # Vancouver
            'harvard',       # Harvard
            'mla',           # Modern Language Association
            'acm',           # Association for Computing Machinery
        ]


# Convenience function
def format_citation(bibtex_or_doi: str, style: str = 'apa') -> str:
    """
    Quick format a BibTeX entry or DOI.

    Args:
        bibtex_or_doi: BibTeX string or DOI
        style: Citation style

    Returns:
        Formatted citation

    Example:
        >>> from bibtex_utils import format_citation
        >>> citation = format_citation('10.1007/xxx', style='apa')
        >>> citation = format_citation(bibtex_str, style='chicago')
    """
    formatter = CitationFormatter(style)

    # Detect if input is DOI or BibTeX
    if bibtex_or_doi.strip().startswith('@'):
        return formatter.format_bibtex(bibtex_or_doi)
    else:
        return formatter.format_doi(bibtex_or_doi)
