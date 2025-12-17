"""
Input identification and validation.

Identifies whether input is a DOI, ISBN, arXiv ID, or file path,
and validates the format.
"""

from pathlib import Path
from enum import Enum
import re


class InputType(Enum):
    """Types of input identifiers."""
    DOI = "doi"
    ISBN = "isbn"
    ARXIV = "arxiv"
    PDF_FILE = "pdf_file"
    UNKNOWN = "unknown"


def identify_input(input_str: str) -> InputType:
    """Identify what type of input we received.
    
    Args:
        input_str: Input string from CLI or clipboard
        
    Returns:
        InputType enum value
    """
    input_str = input_str.strip()
    
    # Check if it's a file path
    path = Path(input_str)
    
    # If file exists and is PDF, use it
    if path.exists() and path.suffix.lower() == '.pdf':
        return InputType.PDF_FILE
    
    # If file doesn't exist, try adding .pdf extension
    if not path.exists() and path.suffix.lower() != '.pdf':
        pdf_path = Path(str(path) + '.pdf')
        if pdf_path.exists():
            return InputType.PDF_FILE
    
    # Check for arXiv ID (format: YYMM.NNNNN or YYMM.NNNNNN)
    # Examples: 2404.12345, 1234.5678
    if re.match(r'^\d{4}\.\d{4,6}$', input_str):
        return InputType.ARXIV
    
    # Check for DOI (format: 10.NNNN/...)
    # Examples: 10.1234/example, 10.48550/ARXIV.2404.12345
    if re.match(r'^10\.\d{4,}/\S+$', input_str):
        return InputType.DOI
    
    # Check for DOI URL
    if input_str.startswith(('https://doi.org/', 'http://dx.doi.org/')):
        return InputType.DOI
    
    # Check for ISBN (10 or 13 digits with optional hyphens)
    # Examples: 978-0-123456-78-9, 9780123456789
    isbn_clean = re.sub(r'[-\s]', '', input_str)
    if re.match(r'^(978|979)?\d{9}[\dXx]$', isbn_clean):
        return InputType.ISBN
    
    return InputType.UNKNOWN


def extract_doi(input_str: str) -> str:
    """Extract DOI from various input formats.
    
    Args:
        input_str: Input string that may contain a DOI
        
    Returns:
        Clean DOI string (e.g., "10.1234/example")
        
    Raises:
        ValueError: If input is not a valid DOI
    """
    input_str = input_str.strip()
    
    # Remove URL prefix if present
    if input_str.startswith('https://doi.org/'):
        return input_str.replace('https://doi.org/', '')
    elif input_str.startswith('http://dx.doi.org/'):
        return input_str.replace('http://dx.doi.org/', '')
    elif input_str.startswith('http://doi.org/'):
        return input_str.replace('http://doi.org/', '')
    
    # Validate DOI format
    if not re.match(r'^10\.\d{4,}/\S+$', input_str):
        raise ValueError(f"Invalid DOI format: {input_str}")
    
    return input_str


def arxiv_to_doi(arxiv_id: str) -> str:
    """Convert arXiv ID to DOI.
    
    Args:
        arxiv_id: arXiv identifier (e.g., "2404.12345")
        
    Returns:
        DOI string (e.g., "10.48550/ARXIV.2404.12345")
    """
    arxiv_id = arxiv_id.strip()
    
    # Validate arXiv format
    if not re.match(r'^\d{4}\.\d{4,6}$', arxiv_id):
        raise ValueError(f"Invalid arXiv ID format: {arxiv_id}")
    
    return f"10.48550/ARXIV.{arxiv_id}"


def normalize_isbn(isbn: str) -> str:
    """Normalize ISBN by removing hyphens and spaces.
    
    Args:
        isbn: ISBN with or without hyphens
        
    Returns:
        Clean ISBN string with no separators
        
    Raises:
        ValueError: If ISBN is invalid
    """
    isbn_clean = re.sub(r'[-\s]', '', isbn.strip())
    
    # Validate
    if not re.match(r'^(978|979)?\d{9}[\dXx]$', isbn_clean):
        raise ValueError(f"Invalid ISBN format: {isbn}")
    
    return isbn_clean


def validate_input(input_str: str) -> tuple[InputType, str]:
    """Validate input and return type and normalized value.
    
    Args:
        input_str: Input string to validate
        
    Returns:
        Tuple of (InputType, normalized_value)
        
    Raises:
        ValueError: If input is invalid or unknown
    """
    input_type = identify_input(input_str)
    
    if input_type == InputType.UNKNOWN:
        raise ValueError(f"Could not identify input type: {input_str}")
    
    if input_type == InputType.DOI:
        return (input_type, extract_doi(input_str))
    
    elif input_type == InputType.ARXIV:
        # Convert to DOI for fetching
        doi = arxiv_to_doi(input_str)
        return (InputType.ARXIV, doi)
    
    elif input_type == InputType.ISBN:
        return (input_type, normalize_isbn(input_str))
    
    elif input_type == InputType.PDF_FILE:
        # Return the actual file path (may have .pdf added)
        path = Path(input_str)
        if path.exists() and path.suffix.lower() == '.pdf':
            return (input_type, str(path.resolve()))
        
        # Try with .pdf extension
        pdf_path = Path(str(path) + '.pdf')
        if pdf_path.exists():
            return (input_type, str(pdf_path.resolve()))
        
        # Shouldn't reach here since identify_input already checked
        return (input_type, str(path.resolve()))
    
    return (input_type, input_str)
