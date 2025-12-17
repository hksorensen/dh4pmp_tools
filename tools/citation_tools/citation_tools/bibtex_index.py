"""
Lightweight BibTeX file indexing system.

Maps citation keys to BibTeX file locations for on-demand parsing.
Avoids storing full entry data - just enough to locate and retrieve entries.
"""

from pathlib import Path
from typing import Optional, Dict, List
import json
from datetime import datetime
import bibtexparser


class BibTeXIndex:
    """Lightweight index mapping citation keys to BibTeX files."""
    
    def __init__(
        self,
        bib_files: Optional[List[Path]] = None,
        index_file: Optional[Path] = None,
        auto_rebuild: bool = True
    ):
        """Initialize BibTeX index.
        
        Args:
            bib_files: List of .bib file paths to index
            index_file: Path to index cache file (if None, no persistence)
            auto_rebuild: Automatically rebuild index if files have changed
        """
        self.bib_files = [Path(f) for f in (bib_files or [])]
        self.index_file = Path(index_file) if index_file else None
        self.auto_rebuild = auto_rebuild
        
        # Index structure: {bibkey: {file: path}}
        self.index: Dict[str, Dict] = {}
        
        # Load existing index
        if self.index_file:
            self._load_index()
        
        # Rebuild if needed
        if self.auto_rebuild and self._needs_rebuild():
            self.rebuild_index()
    
    def add_bib_file(self, bib_file: Path) -> None:
        """Add a BibTeX file to the index.
        
        Args:
            bib_file: Path to .bib file
        """
        bib_file = Path(bib_file)
        if bib_file not in self.bib_files:
            self.bib_files.append(bib_file)
            if self.auto_rebuild:
                self.rebuild_index()
    
    def add_bib_directory(self, directory: Path, recursive: bool = True) -> None:
        """Add all .bib files from a directory.
        
        Args:
            directory: Directory to scan
            recursive: Also scan subdirectories
        """
        from .user_config import get_user_config
        from fnmatch import fnmatch
        
        pattern = '**/*.bib' if recursive else '*.bib'
        bib_files = list(Path(directory).glob(pattern))
        
        # Get excluded patterns from config
        user_config = get_user_config()
        excluded_patterns = user_config.get_excluded_files()
        
        # Filter out excluded files and already-added files
        new_files = []
        excluded_count = 0
        
        for f in bib_files:
            if f in self.bib_files:
                continue
                
            # Check if file matches any exclusion pattern
            excluded = False
            for pattern_str in excluded_patterns:
                # Match against filename or full path
                if fnmatch(f.name, pattern_str) or fnmatch(str(f), pattern_str):
                    excluded = True
                    excluded_count += 1
                    break
            
            if not excluded:
                new_files.append(f)
        
        if new_files:
            self.bib_files.extend(new_files)
            print(f"Added {len(new_files)} BibTeX files to index")
            if excluded_count > 0:
                print(f"  (excluded {excluded_count} files matching exclusion patterns)")
            if self.auto_rebuild:
                self.rebuild_index()
    
    def get_entry(self, bibkey: str) -> Optional[str]:
        """Get BibTeX entry by key as formatted string.
        
        Args:
            bibkey: BibTeX citation key
            
        Returns:
            BibTeX entry as string, or None if not found
        """
        entry_dict = self.get_entry_dict(bibkey)
        if entry_dict:
            return self._format_bibtex_entry(entry_dict)
        return None
    
    def get_entry_dict(self, bibkey: str) -> Optional[Dict]:
        """Get parsed BibTeX entry as dictionary.
        
        Args:
            bibkey: BibTeX citation key
            
        Returns:
            Entry dictionary from bibtexparser, or None if not found
        """
        if bibkey not in self.index:
            return None
        
        entry_info = self.index[bibkey]
        bib_file = Path(entry_info['file'])
        
        if not bib_file.exists():
            print(f"Warning: BibTeX file not found: {bib_file}")
            return None
        
        # Parse the file and extract the specific entry
        # Configure parser to accept non-standard entry types
        parser = bibtexparser.bparser.BibTexParser(common_strings=True)
        parser.ignore_nonstandard_types = False
        parser.homogenize_fields = False
        
        with open(bib_file, 'r', encoding='utf-8') as f:
            bib_db = bibtexparser.load(f, parser=parser)
        
        for entry in bib_db.entries:
            if entry['ID'] == bibkey:
                return entry
        
        return None
    
    def search_keys(self, pattern: str) -> List[str]:
        """Search for citation keys matching pattern.
        
        Args:
            pattern: Search pattern (case-insensitive substring match)
            
        Returns:
            List of matching citation keys
        """
        pattern_lower = pattern.lower()
        return sorted([key for key in self.index.keys() if pattern_lower in key.lower()])
    
    def get_by_doi(self, doi: str) -> Optional[str]:
        """Get citation key by DOI.
        
        Args:
            doi: DOI to search for
            
        Returns:
            Citation key if found, None otherwise
        """
        # Normalize DOI (remove https://doi.org/ prefix if present)
        doi_clean = doi.replace('https://doi.org/', '').replace('http://doi.org/', '')
        
        for key, entry_info in self.index.items():
            if entry_info.get('doi') == doi_clean:
                return key
        return None
    
    def get_by_arxiv(self, arxiv_id: str) -> Optional[str]:
        """Get citation key by arXiv ID.
        
        Args:
            arxiv_id: arXiv ID to search for (e.g., '1405.0312' or 'arxiv:1405.0312')
            
        Returns:
            Citation key if found, None otherwise
        """
        # Normalize arXiv ID (remove arxiv: prefix if present)
        arxiv_clean = arxiv_id.replace('arxiv:', '').replace('arXiv:', '')
        
        for key, entry_info in self.index.items():
            if entry_info.get('arxiv') == arxiv_clean:
                return key
        return None
    
    def search_by_year(self, year: str) -> List[str]:
        """Search for entries by year.
        
        Args:
            year: Year to search for
            
        Returns:
            List of citation keys from that year
        """
        return sorted([
            key for key, entry_info in self.index.items()
            if entry_info.get('year') == str(year)
        ])
    
    def list_keys(self) -> List[str]:
        """Get all indexed citation keys.
        
        Returns:
            Sorted list of all citation keys
        """
        return sorted(self.index.keys())
    
    def get_statistics(self) -> Dict:
        """Get index statistics.
        
        Returns:
            Dictionary with index statistics
        """
        return {
            'total_keys': len(self.index),
            'total_files': len(self.bib_files),
            'index_file': str(self.index_file) if self.index_file else None,
        }
    
    def rebuild_index(self) -> None:
        """Rebuild the entire index from all BibTeX files."""
        print("Rebuilding BibTeX index...")
        self.index = {}
        
        # Try to use tqdm for progress bar
        try:
            from tqdm import tqdm
            use_progress = True
        except ImportError:
            use_progress = False
        
        # Iterate through files with optional progress bar
        file_iterator = tqdm(self.bib_files, desc="Indexing files", unit="file") if use_progress else self.bib_files
        
        total_entries = 0
        for bib_file in file_iterator:
            if not bib_file.exists():
                if use_progress:
                    tqdm.write(f"Warning: Skipping missing file: {bib_file}")
                else:
                    print(f"Warning: Skipping missing file: {bib_file}")
                continue
            
            try:
                # Configure parser to accept non-standard entry types
                parser = bibtexparser.bparser.BibTexParser(common_strings=True)
                parser.ignore_nonstandard_types = False
                parser.homogenize_fields = False
                
                with open(bib_file, 'r', encoding='utf-8') as f:
                    bib_db = bibtexparser.load(f, parser=parser)
                
                file_entries = 0
                for entry in bib_db.entries:
                    bibkey = entry['ID']
                    
                    if bibkey in self.index:
                        existing_file = self.index[bibkey]['file']
                        msg = f"Warning: Duplicate key '{bibkey}' in {bib_file} (already in {existing_file})"
                        if use_progress:
                            tqdm.write(msg)
                        else:
                            print(msg)
                    
                    # Store key → file mapping with optional metadata for future use
                    # This allows easy extension: add doi, year, authors, etc.
                    index_entry = {
                        'file': str(bib_file.resolve()),
                    }
                    
                    # Optional: Store DOI for future DOI-based lookup
                    if 'doi' in entry:
                        index_entry['doi'] = entry['doi']
                    
                    # Optional: Store arXiv ID for future arXiv-based lookup
                    if 'eprint' in entry:
                        index_entry['arxiv'] = entry['eprint']
                    
                    # Optional: Store year for temporal queries
                    if 'year' in entry:
                        index_entry['year'] = entry['year']
                    
                    self.index[bibkey] = index_entry
                    file_entries += 1
                
                total_entries += file_entries
                
                msg = f"  Indexed {file_entries} entries from {bib_file.name}"
                if use_progress:
                    tqdm.write(msg)
                else:
                    print(msg)
            
            except Exception as e:
                msg = f"Error reading {bib_file}: {e}"
                if use_progress:
                    tqdm.write(msg)
                else:
                    print(msg)
        
        # Save index to cache if path provided
        if self.index_file:
            self._save_index()
        
        print(f"✓ Index rebuilt: {len(self.index)} total entries from {len(self.bib_files)} files")
    
    def _load_index(self) -> None:
        """Load index from cache file."""
        if not self.index_file or not self.index_file.exists():
            return
        
        try:
            with open(self.index_file, 'r') as f:
                data = json.load(f)
                self.index = data.get('index', {})
                self.bib_files = [Path(p) for p in data.get('bib_files', [])]
        except Exception as e:
            print(f"Warning: Could not load index cache: {e}")
    
    def _save_index(self) -> None:
        """Save index to cache file."""
        if not self.index_file:
            return
        
        # Ensure parent directory exists
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'index': self.index,
            'bib_files': [str(f.resolve()) for f in self.bib_files],
            'timestamp': datetime.now().isoformat(),
        }
        
        with open(self.index_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _needs_rebuild(self) -> bool:
        """Check if index needs rebuilding based on file modification times."""
        if not self.index_file or not self.index_file.exists():
            return True
        
        index_mtime = self.index_file.stat().st_mtime
        
        for bib_file in self.bib_files:
            if bib_file.exists() and bib_file.stat().st_mtime > index_mtime:
                return True
        
        return False
    
    @staticmethod
    def _format_bibtex_entry(entry: Dict) -> str:
        """Format a parsed entry back to BibTeX string.
        
        Args:
            entry: Entry dictionary from bibtexparser
            
        Returns:
            Formatted BibTeX string
        """
        entry_type = entry.get('ENTRYTYPE', 'misc')
        bibkey = entry['ID']
        
        lines = [f"@{entry_type}{{{bibkey},"]
        
        for key, value in entry.items():
            if key not in ['ENTRYTYPE', 'ID']:
                lines.append(f" {key} = {{{value}}},")
        
        lines.append("}")
        
        return '\n'.join(lines)
