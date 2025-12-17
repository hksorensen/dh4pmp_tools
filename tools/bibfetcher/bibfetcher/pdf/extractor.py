"""
PDF text extraction for finding DOI and arXiv IDs.
"""

from pathlib import Path
import re
from typing import Optional, Tuple
import PyPDF2


def extract_first_page_text(pdf_path: Path) -> str:
    """Extract text from first page of PDF.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Text content of first page
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        ValueError: If PDF cannot be read
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    # Try multiple extraction strategies
    errors = []
    
    # Strategy 1: Normal extraction
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            
            if len(reader.pages) == 0:
                raise ValueError(f"PDF has no pages: {pdf_path}")
            
            # Extract text from first page
            first_page = reader.pages[0]
            text = first_page.extract_text()
            
            if text and len(text.strip()) > 10:  # Got useful text
                return text
            
    except Exception as e:
        errors.append(f"Normal extraction: {e}")
    
    # Strategy 2: Try with strict=False (more lenient)
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file, strict=False)
            
            if len(reader.pages) > 0:
                first_page = reader.pages[0]
                text = first_page.extract_text()
                
                if text and len(text.strip()) > 10:
                    return text
    
    except Exception as e:
        errors.append(f"Lenient extraction: {e}")
    
    # Strategy 3: Try multiple pages (DOI might be on second page)
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file, strict=False)
            
            # Try first 3 pages
            combined_text = ""
            for i in range(min(3, len(reader.pages))):
                try:
                    page_text = reader.pages[i].extract_text()
                    if page_text:
                        combined_text += page_text + "\n"
                except:
                    continue
            
            if combined_text and len(combined_text.strip()) > 10:
                return combined_text
    
    except Exception as e:
        errors.append(f"Multi-page extraction: {e}")
    
    # All strategies failed
    error_msg = "Cannot extract text from PDF. Tried: " + "; ".join(errors)
    raise ValueError(error_msg)


def find_doi_in_text(text: str) -> Optional[str]:
    """Find DOI in text using pattern matching.
    
    Looks for DOI patterns like:
    - doi: 10.1234/example
    - DOI: 10.1234/example
    - https://doi.org/10.1234/example
    - 10.1234/example (standalone)
    
    Handles spaces that PDF extraction sometimes inserts (e.g., "10. 1234 /example").
    
    Stops matching at:
    - Two or more consecutive spaces (common in PDF extraction)
    - Newline
    - Punctuation: comma, semicolon
    - Period followed by space/capital/year
    - End of string
    
    Limitation: If a DOI suffix has letters AND PDF extraction inserts a single space
    in the middle AND there's only a single space before the next word, the DOI may
    be truncated. Example: "10.1038/nat ure article" → "10.1038/nat"
    In practice, PDFs usually have multiple spaces/newlines after DOIs, so this is rare.
    
    Args:
        text: Text to search
        
    Returns:
        DOI string if found, None otherwise
    """
    if not text:
        return None
    
    # DOI structure: 10.digits/suffix
    # Allow spaces (PDF extraction bug) and various DOI characters including periods
    # Stop at: double space, space+lowercase word (2+ chars), punctuation,
    #          period+space+capital/digit, parenthesis, newline, or end
    doi_pattern = r'10\.[\d\s]+/[a-zA-Z0-9.\-_/\s]+?(?=\s{2,}|\s+[a-z][a-z]+\b|[,;)\]]\s*|\.\s+[A-Z\d]|$|\n)'
    
    # Pattern 1: DOI (with or without colon) - e.g., "DOI 10.xxxx" or "doi: 10.xxxx"
    match = re.search(rf'doi\s*[::\s]+\s*({doi_pattern})', text, re.IGNORECASE)
    if match:
        doi = re.sub(r'\s+', '', match.group(1))
        return doi
    
    # Pattern 2: https://doi.org/10.xxxx/...
    match = re.search(rf'https?://(?:dx\.)?doi\.org/({doi_pattern})', text, re.IGNORECASE)
    if match:
        doi = re.sub(r'\s+', '', match.group(1))
        return doi
    
    # Pattern 3: standalone DOI (10.xxxx/...)
    match = re.search(rf'\b({doi_pattern})', text)
    if match:
        doi = re.sub(r'\s+', '', match.group(1))
        return doi
    
    return None


def find_arxiv_in_text(text: str) -> Optional[str]:
    """Find arXiv ID in text using pattern matching.
    
    Looks for arXiv patterns like:
    - arXiv:2404.12345
    - arXiv: 2404.12345
    - 2404.12345 (standalone, with caution)
    
    Args:
        text: Text to search
        
    Returns:
        arXiv ID if found, None otherwise
    """
    if not text:
        return None
    
    # Pattern 1: arXiv:YYMM.NNNNN
    match = re.search(r'arXiv\s*:\s*(\d{4}\.\d{4,6})', text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Pattern 2: standalone YYMM.NNNNN (more restrictive)
    # Only match if it appears to be a reference (near common keywords)
    arxiv_context = r'(?:preprint|archive|arxiv|identifier)\s*[:\-]?\s*(\d{4}\.\d{4,6})'
    match = re.search(arxiv_context, text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None


def extract_identifier_from_pdf(pdf_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """Extract DOI or arXiv ID from first page of PDF.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Tuple of (identifier_type, identifier_value)
        identifier_type is 'doi', 'arxiv', or None
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        ValueError: If PDF cannot be read
    """
    text = extract_first_page_text(pdf_path)
    
    # Try to find DOI first (more specific)
    doi = find_doi_in_text(text)
    if doi:
        return ('doi', doi)
    
    # Try arXiv
    arxiv_id = find_arxiv_in_text(text)
    if arxiv_id:
        return ('arxiv', arxiv_id)
    
    return (None, None)
