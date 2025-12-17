"""
BibTeX entry post-processing.

Provides hooks for cleaning up and customizing entries after fetching,
such as adding arXiv-specific fields or removing unwanted fields.
"""

from typing import Dict, List, Callable
import re
from .utils.latex import text_to_latex


class EntryProcessor:
    """Post-process BibTeX entries with customizable hooks."""
    
    def __init__(self):
        """Initialize processor with default hooks."""
        self.hooks: List[Callable] = []
        
        # Register default hooks
        self.register_hook(self.process_arxiv_entries)
        self.register_hook(self.clean_unwanted_fields)
        self.register_hook(self.normalize_month_field)
        self.register_hook(self.normalize_caps_to_titlecase)
        self.register_hook(self.split_title_subtitle)
        self.register_hook(self.latexify_fields)
    
    def register_hook(self, hook: Callable) -> None:
        """Register a post-processing hook.
        
        Args:
            hook: Function that takes a dict and returns a dict
        """
        self.hooks.append(hook)
    
    def process(self, entry: Dict) -> Dict:
        """Apply all registered hooks to an entry.
        
        Args:
            entry: BibTeX entry dictionary
            
        Returns:
            Processed entry dictionary
        """
        for hook in self.hooks:
            entry = hook(entry)
        return entry
    
    @staticmethod
    def process_arxiv_entries(entry: Dict) -> Dict:
        """Process arXiv entries with special fields.
        
        For arXiv papers:
        - Add eprinttype = {arxiv}
        - Add eprint = {arxiv_id} (extracted from DOI)
        - Remove copyright, keywords, publisher fields
        
        Args:
            entry: BibTeX entry dictionary
            
        Returns:
            Modified entry
        """
        # Check if this is an arXiv entry by DOI
        doi = entry.get('doi', '')
        
        # arXiv DOIs have format: 10.48550/ARXIV.YYMM.NNNNN
        arxiv_match = re.match(r'10\.48550/ARXIV\.(\d{4}\.\d{4,6})', doi, re.IGNORECASE)
        
        if arxiv_match:
            arxiv_id = arxiv_match.group(1)
            
            # Add arXiv fields
            entry['eprinttype'] = 'arxiv'
            entry['eprint'] = arxiv_id
            
            # Remove unwanted fields common in arXiv entries
            unwanted = ['copyright', 'keywords', 'publisher']
            for field in unwanted:
                entry.pop(field, None)
        
        return entry
    
    @staticmethod
    def clean_unwanted_fields(entry: Dict) -> Dict:
        """Remove generally unwanted fields.
        
        Args:
            entry: BibTeX entry dictionary
            
        Returns:
            Cleaned entry
        """
        # Fields to remove for specific entry types
        entry_type = entry.get('ENTRYTYPE', '')
        
        if entry_type == 'article':
            # Articles shouldn't have publisher or ISSN
            entry.pop('publisher', None)
            entry.pop('issn', None)
        
        # Remove URL if DOI is present (DOI is preferred)
        if 'doi' in entry and 'url' in entry:
            entry.pop('url', None)
        
        return entry
    
    @staticmethod
    def normalize_month_field(entry: Dict) -> Dict:
        """Convert month field to numeric format.
        
        Converts month names to numbers:
        - "January" or "jan" → "1"
        - "February" or "feb" → "2"
        - etc.
        
        Args:
            entry: BibTeX entry dictionary
            
        Returns:
            Modified entry with numeric month
        """
        if 'month' not in entry:
            return entry
        
        month_str = str(entry['month']).strip().lower()
        
        # Month name to number mapping
        month_map = {
            'january': '1', 'jan': '1',
            'february': '2', 'feb': '2',
            'march': '3', 'mar': '3',
            'april': '4', 'apr': '4',
            'may': '5',
            'june': '6', 'jun': '6',
            'july': '7', 'jul': '7',
            'august': '8', 'aug': '8',
            'september': '9', 'sep': '9', 'sept': '9',
            'october': '10', 'oct': '10',
            'november': '11', 'nov': '11',
            'december': '12', 'dec': '12',
        }
        
        # Check if already numeric
        if month_str.isdigit():
            month_num = int(month_str)
            if 1 <= month_num <= 12:
                entry['month'] = str(month_num)
            return entry
        
        # Try to convert name to number
        if month_str in month_map:
            entry['month'] = month_map[month_str]
        
        return entry
    
    @staticmethod
    def normalize_caps_to_titlecase(entry: Dict) -> Dict:
        """Convert ALL CAPS fields to Title Case.
        
        Converts author, editor, and title fields from ALL CAPS to proper title case.
        Only converts if the ENTIRE field is in ALL CAPS (with some tolerance for
        LaTeX commands and special characters).
        
        Args:
            entry: BibTeX entry dictionary
            
        Returns:
            Entry with normalized capitalization
        """
        def is_all_caps(text: str) -> bool:
            """Check if text is ALL CAPS (ignoring LaTeX commands, punctuation, etc.)"""
            if not text:
                return False
            # Extract only letters
            letters = ''.join(c for c in text if c.isalpha())
            if not letters:
                return False
            # Check if >90% of letters are uppercase
            upper_count = sum(1 for c in letters if c.isupper())
            return upper_count / len(letters) > 0.9
        
        def to_title_case(text: str) -> str:
            """Convert to title case, preserving LaTeX commands and keeping 'and' lowercase."""
            # Simple title case - capitalize first letter of each word
            # Preserve LaTeX commands in curly braces
            # Keep 'and' lowercase (it's a conjunction in author fields)
            words = text.split()
            result = []
            
            for word in words:
                # Skip if it's a LaTeX command or contains curly braces
                if '{' in word or '\\' in word:
                    result.append(word)
                # Keep 'and' lowercase (author separator)
                elif word.lower() == 'and':
                    result.append('and')
                else:
                    # Title case: capitalize first letter, lowercase rest
                    if word:
                        result.append(word[0].upper() + word[1:].lower())
                    else:
                        result.append(word)
            
            return ' '.join(result)
        
        # Fields to normalize
        fields_to_check = ['author', 'editor', 'title']
        
        for field in fields_to_check:
            if field in entry:
                value = entry[field]
                if isinstance(value, str) and is_all_caps(value):
                    entry[field] = to_title_case(value)
        
        return entry
    
    @staticmethod
    def split_title_subtitle(entry: Dict) -> Dict:
        """Split title at separator into title and subtitle fields.
        
        Handles both title/subtitle and booktitle/booksubtitle pairs.
        
        Separators (in priority order):
        1. Colon: "Title: subtitle"
        2. Question mark: "Title? subtitle"
        3. Period + space + uppercase: "Title. Subtitle"
        4. Triple dash with spaces: "Title --- subtitle"
        
        Rules:
        - Only splits if subtitle field doesn't already exist
        - Splits at first occurrence of separator
        - Capitalizes first character of subtitle if needed
        - Preserves existing capitalization if already uppercase
        
        Args:
            entry: BibTeX entry dictionary
            
        Returns:
            Modified entry with split title/subtitle
        """
        # Define field pairs to process
        field_pairs = [
            ('title', 'subtitle'),
            ('booktitle', 'booksubtitle')
        ]
        
        for title_field, subtitle_field in field_pairs:
            # Only process if title exists and subtitle doesn't
            if title_field not in entry or subtitle_field in entry:
                continue
            
            title = entry[title_field]
            main_title = None
            subtitle = None
            
            # Try separators in priority order
            # 1. Colon
            if ':' in title:
                parts = title.split(':', 1)
                main_title = parts[0].strip()
                subtitle = parts[1].strip()
            
            # 2. Question mark
            elif '?' in title:
                parts = title.split('?', 1)
                main_title = parts[0].strip() + '?'  # Keep the question mark
                subtitle = parts[1].strip()
            
            # 3. Period followed by space and uppercase letter
            elif re.search(r'\.\s+[A-Z]', title):
                match = re.search(r'^(.+?)\.\s+([A-Z].*)$', title)
                if match:
                    main_title = match.group(1).strip()
                    subtitle = match.group(2).strip()
            
            # 4. Triple dash with spaces
            elif ' --- ' in title:
                parts = title.split(' --- ', 1)
                main_title = parts[0].strip()
                subtitle = parts[1].strip()
            
            # If we found a split, apply it
            if main_title and subtitle:
                # Capitalize first character if not already
                if subtitle and not subtitle[0].isupper():
                    subtitle = subtitle[0].upper() + subtitle[1:]
                
                # Update entry
                entry[title_field] = main_title
                entry[subtitle_field] = subtitle
        
        return entry
    
    @staticmethod
    def latexify_fields(entry: Dict) -> Dict:
        """Convert Unicode characters to LaTeX equivalents in text fields.
        
        Applies text_to_latex() to all string fields in the entry to ensure
        standard LaTeX formatting:
        - Converts ' and ' to '
        - Converts – (en-dash) to --
        - Converts — (em-dash) to ---
        - Converts " and " to `` and ''
        - Handles accented characters (ó → {\\'{o}})
        - Escapes LaTeX special characters (#, &, %, $)
        
        Args:
            entry: BibTeX entry dictionary
            
        Returns:
            Entry with LaTeX-formatted text fields
        """
        # Fields that should NOT be latexified (URLs, raw LaTeX, etc.)
        skip_fields = {'url', 'doi', 'eprint', 'archiveprefix', 'primaryclass', 'file'}
        
        for key, value in entry.items():
            # Only process string values, skip special fields
            if isinstance(value, str) and key.lower() not in skip_fields:
                entry[key] = text_to_latex(value)
        
        return entry
    
    @staticmethod
    def add_custom_field(entry: Dict, field: str, value: str) -> Dict:
        """Add a custom field to entry.
        
        Useful for creating custom hooks. Example:
        
        processor.register_hook(
            lambda e: EntryProcessor.add_custom_field(e, 'myfield', 'myvalue')
        )
        
        Args:
            entry: BibTeX entry dictionary
            field: Field name
            value: Field value
            
        Returns:
            Modified entry
        """
        entry[field] = value
        return entry


# Global processor instance
_default_processor = EntryProcessor()


def get_processor() -> EntryProcessor:
    """Get the default entry processor.
    
    Returns:
        EntryProcessor instance
    """
    return _default_processor


def process_entry(entry: Dict) -> Dict:
    """Process an entry with the default processor.
    
    Args:
        entry: BibTeX entry dictionary
        
    Returns:
        Processed entry
    """
    return _default_processor.process(entry)
