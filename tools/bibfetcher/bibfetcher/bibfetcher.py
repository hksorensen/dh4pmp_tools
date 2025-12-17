"""
Main bibfetcher coordinator.

Orchestrates the fetching, key generation, and output process.
"""

from pathlib import Path
from typing import Optional, Tuple
import sys
import subprocess

from .input_identifier import identify_input, validate_input, InputType, arxiv_to_doi
from .fetchers import CrossrefFetcher, DOIFetcher
from .pdf import extract_identifier_from_pdf
from .utils import generate_bibkey, get_existing_keys_from_index, write_clipboard
from .utils.latex import text_to_latex
from .index import load_citation_tools_index, check_doi_exists, get_all_keys
from .user_config import get_user_config
from .postprocessor import process_entry


class BibFetcher:
    """Main coordinator for fetching bibliographic metadata."""
    
    def __init__(self, verbose: bool = False):
        """Initialize BibFetcher.
        
        Args:
            verbose: Enable verbose output
        """
        self.verbose = verbose
        self.crossref = CrossrefFetcher()
        self.doi_fetcher = DOIFetcher()
        self.config = get_user_config()
        
        # Load citation_tools index if available
        self.index_data = load_citation_tools_index()
        if self.index_data and self.verbose:
            print(f"Loaded citation_tools index with {len(self.index_data.get('index', {}))} entries")
    
    def _rebuild_index_quietly(self):
        """Rebuild citation_tools index with progress bar."""
        import subprocess
        import sys
        import time
        
        try:
            # Start the rebuild process
            # Redirect output to /dev/null to avoid buffer issues
            start_time = time.time()
            process = subprocess.Popen(
                ['cite', 'index', 'rebuild'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Show progress bar while waiting
            # Estimate: ~0.25s per file, typical = 50 files = ~12.5s
            # We'll show a progress bar that fills over estimated time
            estimated_duration = 12.0  # seconds
            bar_width = 30
            
            while process.poll() is None:
                elapsed = time.time() - start_time
                progress = min(elapsed / estimated_duration, 0.99)  # Cap at 99% until done
                filled = int(bar_width * progress)
                bar = '█' * filled + '░' * (bar_width - filled)
                percent = int(progress * 100)
                
                print(f"\rRebuilding index [{bar}] {percent}% ({elapsed:.1f}s)", 
                      end='', flush=True, file=sys.stderr)
                time.sleep(0.1)
            
            # Process finished, get elapsed time
            elapsed = time.time() - start_time
            
            # Show final result
            if process.returncode == 0:
                bar = '█' * bar_width
                print(f"\rRebuilding index [{bar}] 100% ({elapsed:.1f}s) ✓", file=sys.stderr)
            else:
                print(f"\rRebuilding index failed after {elapsed:.1f}s ✗       ", file=sys.stderr)
                    
        except FileNotFoundError:
            print("Rebuilding index ⊘ (cite not found)", file=sys.stderr)
        except Exception as e:
            print(f"Rebuilding index ✗ (error: {e})", file=sys.stderr)
    
    def fetch(self, input_str: str) -> Optional[Tuple[str, str]]:
        """Fetch bibliographic metadata and generate BibTeX entry.
        
        Args:
            input_str: Input identifier (DOI, ISBN, arXiv ID, or PDF path)
            
        Returns:
            Tuple of (bibkey, bibtex_string), or None if failed
            
        Raises:
            ValueError: If input is invalid
            RuntimeError: If fetch fails
        """
        # Identify input type and normalize
        try:
            input_type, normalized_value = validate_input(input_str)
        except ValueError as e:
            raise ValueError(f"Invalid input: {e}")
        
        if self.verbose:
            print(f"Input type: {input_type.value}")
            print(f"Normalized value: {normalized_value}")
        
        # Handle PDF files
        if input_type == InputType.PDF_FILE:
            return self._handle_pdf(Path(normalized_value))
        
        # Handle other identifiers
        elif input_type == InputType.DOI or input_type == InputType.ARXIV:
            return self._handle_doi(normalized_value)
        
        elif input_type == InputType.ISBN:
            return self._handle_isbn(normalized_value)
        
        else:
            raise ValueError(f"Unsupported input type: {input_type}")
    
    def _handle_pdf(self, pdf_path: Path) -> Optional[Tuple[str, str]]:
        """Handle PDF file input.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (bibkey, bibtex_string), or None if no identifier found
        """
        if self.verbose:
            print(f"Extracting identifier from PDF: {pdf_path}")
        
        try:
            id_type, identifier = extract_identifier_from_pdf(pdf_path)
        except Exception as e:
            raise RuntimeError(f"Failed to extract identifier from PDF: {e}")
        
        if id_type is None:
            raise ValueError(f"No DOI or arXiv ID found in PDF: {pdf_path}")
        
        if self.verbose:
            print(f"Found {id_type}: {identifier}")
        
        # Convert arXiv to DOI if needed
        if id_type == 'arxiv':
            identifier = arxiv_to_doi(identifier)
        
        return self._handle_doi(identifier)
    
    def _handle_doi(self, doi: str) -> Optional[Tuple[str, str, bool]]:
        """Handle DOI input.
        
        Args:
            doi: DOI to fetch
            
        Returns:
            Tuple of (bibkey, bibtex_string, is_duplicate), or None if fetch failed
        """
        # Rebuild citation_tools index to ensure it's up-to-date
        self._rebuild_index_quietly()
        
        # Reload index after rebuild
        self.index_data = load_citation_tools_index()
        
        # Check if DOI already exists in index
        if self.index_data:
            existing_key = check_doi_exists(doi, self.index_data)
            if existing_key:
                if self.verbose:
                    print(f"DOI {doi} already exists as {existing_key}")
                # Return the existing key with a flag indicating it's a duplicate
                # We don't have the full entry, but we have the key
                return (existing_key, None, True)
        
        # Try DOI fetcher first (faster, returns BibTeX directly)
        if self.verbose:
            print(f"Fetching from DOI resolver: {doi}")
        
        try:
            metadata = self.doi_fetcher.fetch(doi)
            if metadata:
                return self._process_entry(metadata, doi)
        except Exception as e:
            if self.verbose:
                print(f"DOI fetch failed: {e}")
                print("Trying Crossref...")
        
        # Fallback to Crossref
        if self.verbose:
            print(f"Fetching from Crossref: {doi}")
        
        try:
            crossref_data = self.crossref.fetch(doi, mode='doi')
            if crossref_data:
                entry = self.crossref.to_bibtex_entry(crossref_data)
                return self._process_entry(entry, doi)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch from Crossref: {e}")
        
        return None
    
    def _handle_isbn(self, isbn: str) -> Optional[Tuple[str, str, bool]]:
        """Handle ISBN input.
        
        Args:
            isbn: ISBN to fetch
            
        Returns:
            Tuple of (bibkey, bibtex_string, is_duplicate), or None if failed
        """
        if self.verbose:
            print(f"Fetching from Crossref (ISBN): {isbn}")
        
        try:
            crossref_data = self.crossref.fetch(isbn, mode='isbn')
            
            # ISBN search returns a list of items
            if isinstance(crossref_data, dict) and 'items' in crossref_data:
                items = crossref_data['items']
                if not items:
                    raise ValueError(f"No results found for ISBN: {isbn}")
                
                # Use first result
                entry = self.crossref.to_bibtex_entry(items[0])
                doi = entry.get('doi')
                return self._process_entry(entry, doi)
            else:
                entry = self.crossref.to_bibtex_entry(crossref_data)
                doi = entry.get('doi')
                return self._process_entry(entry, doi)
        
        except Exception as e:
            raise RuntimeError(f"Failed to fetch ISBN: {e}")
    
    def _process_entry(self, entry: dict, doi: Optional[str] = None) -> Tuple[str, str, bool]:
        """Process fetched entry: generate key and format BibTeX.
        
        Args:
            entry: BibTeX entry dictionary
            doi: Optional DOI for the entry
            
        Returns:
            Tuple of (bibkey, bibtex_string, is_duplicate)
        """
        # Apply post-processing (arXiv fields, cleanup, etc.)
        entry = process_entry(entry)
        
        # Get existing keys for uniqueness checking
        existing_keys = get_all_keys(self.index_data)
        
        # Generate unique BibTeX key
        bibkey = generate_bibkey(entry, existing_keys)
        entry['ID'] = bibkey
        
        if self.verbose:
            print(f"Generated key: {bibkey}")
        
        # Format as BibTeX string
        bibtex_str = self.doi_fetcher.to_bibtex_string([entry])
        
        return (bibkey, bibtex_str, False)
    
    def fetch_and_copy(self, input_str: str) -> Optional[str]:
        """Fetch metadata and copy to clipboard.
        
        Args:
            input_str: Input identifier
            
        Returns:
            BibTeX key if successful, None otherwise
        """
        result = self.fetch(input_str)
        
        if result is None:
            return None
        
        bibkey, bibtex_str = result
        
        # Copy to clipboard if configured
        if self.config.get('clipboard_output', True):
            try:
                write_clipboard(bibtex_str)
                if self.verbose:
                    print(f"Copied to clipboard: {bibkey}")
            except Exception as e:
                print(f"Warning: Failed to copy to clipboard: {e}")
        
        # Also print to stdout
        print(bibtex_str)
        
        return bibkey
