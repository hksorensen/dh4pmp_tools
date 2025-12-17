"""
BibTeX to formatted citation converter.

Main conversion logic integrating:
- BibTeX parsing and entry retrieval
- CSL style management
- Pandoc-based citation formatting
- Multiple output formats including clipboard support
"""

from pathlib import Path
import subprocess
import tempfile
import yaml
import bibtexparser
from typing import Literal, Optional

from .csl_manager import CSLStyleManager
from .bibtex_index import BibTeXIndex


def bibtex_to_citation(
    bibtex_string: str,
    style: str = 'chicago-author-date',
    output_format: Literal['docx', 'markdown', 'html', 'plain', 'rtf', 'clipboard'] = 'plain',
    cache_dir: Optional[Path] = None
) -> Optional[str]:
    """Convert BibTeX entry to formatted citation.
    
    Args:
        bibtex_string: BibTeX entry as string
        style: Citation style name. Options:
               - 'fund-og-forskning': Danish humanities style
               - 'chicago-note-bibliography': Chicago notes style
               - 'chicago-author-date' or 'authoryear': Chicago author-date
               - 'apa': APA style
        output_format: Output format
            - 'plain': Plain text (returned as string)
            - 'markdown': Markdown (returned as string)
            - 'html': HTML (returned as string)
            - 'rtf': Rich Text Format (returned as string)
            - 'docx': Word document (saved to temp file, path returned)
            - 'clipboard': Copy to clipboard (returns None)
        cache_dir: Custom cache directory for CSL files
        
    Returns:
        - For 'docx': Path to created Word document
        - For 'clipboard': None (content copied to clipboard)
        - For other formats: Formatted citation as string
        
    Raises:
        ValueError: If BibTeX parsing fails or style not found
        RuntimeError: If pandoc conversion fails
        
    Example:
        >>> bibtex = '@article{Doe2024, author={Doe, John}, ...}'
        >>> citation = bibtex_to_citation(bibtex, style='apa', output_format='plain')
        >>> print(citation)
    """
    # Get CSL style file
    style_manager = CSLStyleManager(cache_dir=cache_dir)
    csl_path = style_manager.get_style_path(style)
    
    # Parse BibTeX
    # Configure parser to accept non-standard entry types like @online
    parser = bibtexparser.bparser.BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parser.homogenize_fields = False
    
    bib_db = bibtexparser.loads(bibtex_string, parser=parser)
    if not bib_db.entries:
        raise ValueError("No BibTeX entries found in input")
    
    entry = bib_db.entries[0]
    
    # Convert to Pandoc YAML format
    pandoc_entry = _bibtex_to_pandoc_yaml(entry)
    
    # Create markdown with citation
    md_content = f"""---
references:
{yaml.dump([pandoc_entry], default_flow_style=False)}
---

[@{entry['ID']}]
"""
    
    # Convert with pandoc
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(md_content)
        temp_md = Path(f.name)
    
    try:
        if output_format == 'clipboard':
            return _convert_to_clipboard(temp_md, csl_path)
        elif output_format == 'docx':
            return _convert_to_docx(temp_md, csl_path)
        else:
            return _convert_to_text(temp_md, csl_path, output_format)
    
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Pandoc conversion failed: {e.stderr}")
    
    finally:
        temp_md.unlink(missing_ok=True)


def bibtex_to_citation_from_key(
    bibkey: str,
    bib_index: BibTeXIndex,
    style: str = 'chicago-author-date',
    output_format: Literal['docx', 'markdown', 'html', 'plain', 'rtf', 'clipboard'] = 'plain',
    cache_dir: Optional[Path] = None
) -> Optional[str]:
    """Convert BibTeX entry to citation using citation key lookup.
    
    Args:
        bibkey: BibTeX citation key
        bib_index: BibTeXIndex instance to lookup the entry
        style: Citation style name
        output_format: Output format
        cache_dir: Custom cache directory for CSL files
        
    Returns:
        Path to output file (if docx) or formatted citation text (or None for clipboard)
        
    Raises:
        ValueError: If bibkey not found in index
        
    Example:
        >>> index = BibTeXIndex(index_file=Path('~/my_index.json'))
        >>> citation = bibtex_to_citation_from_key(
        ...     'Doe2024', index, style='apa', output_format='plain'
        ... )
    """
    # Get BibTeX entry from index
    bibtex_string = bib_index.get_entry(bibkey)
    
    if bibtex_string is None:
        raise ValueError(
            f"Citation key '{bibkey}' not found in index. "
            f"Index contains {len(bib_index.index)} entries."
        )
    
    return bibtex_to_citation(bibtex_string, style, output_format, cache_dir)


def _bibtex_to_pandoc_yaml(entry: dict) -> dict:
    """Convert BibTeX entry to Pandoc YAML format.
    
    Args:
        entry: Parsed BibTeX entry from bibtexparser
        
    Returns:
        Dictionary in Pandoc's YAML format
    """
    pandoc_entry = {
        'id': entry['ID'],
        'author': [],
        'issued': {'date-parts': [[int(entry.get('year', 0))]]},
    }
    
    # Determine type and add fields
    entry_type = entry.get('ENTRYTYPE', 'book')
    
    if entry_type == 'article':
        pandoc_entry['type'] = 'article-journal'
        pandoc_entry['container-title'] = entry.get('journal', '')
        pandoc_entry['volume'] = entry.get('volume', '')
        pandoc_entry['issue'] = entry.get('number', '')
        pandoc_entry['page'] = entry.get('pages', '').replace('--', '-')
        pandoc_entry['title'] = entry.get('title', '')
        if 'doi' in entry:
            pandoc_entry['DOI'] = entry['doi']
            pandoc_entry['URL'] = f"https://doi.org/{entry['doi']}"
        elif 'url' in entry:
            pandoc_entry['URL'] = entry['url']
    
    elif entry_type == 'incollection':
        pandoc_entry['type'] = 'chapter'
        pandoc_entry['container-title'] = entry.get('booktitle', '')
        pandoc_entry['title'] = entry.get('title', '')
        pandoc_entry['page'] = entry.get('pages', '').replace('--', '-')
        
        # Parse editors if available
        if 'editor' in entry:
            pandoc_entry['editor'] = _parse_names(entry['editor'])
    
    else:  # book or other
        pandoc_entry['type'] = 'book'
        pandoc_entry['title'] = entry.get('title', '')
        pandoc_entry['publisher'] = entry.get('publisher', '')
        pandoc_entry['publisher-place'] = entry.get('address', entry.get('location', ''))
        if 'pages' in entry:
            pandoc_entry['page'] = entry.get('pages', '').replace('--', '-')
    
    # Handle subtitle
    if 'subtitle' in entry:
        pandoc_entry['title'] = f"{entry.get('title', '')}. {entry['subtitle']}"
    
    # Parse authors
    if 'author' in entry:
        pandoc_entry['author'] = _parse_names(entry['author'])
    
    return pandoc_entry


def _parse_names(names_string: str) -> list:
    """Parse BibTeX name string into Pandoc format.
    
    Args:
        names_string: BibTeX names string (e.g., "Last, First and Last2, First2")
        
    Returns:
        List of name dictionaries with 'family' and 'given' keys
    """
    names = []
    for name in names_string.split(' and '):
        name = name.strip()
        
        # Handle "Last, First" format
        if ', ' in name:
            parts = name.split(', ', 1)
            names.append({'family': parts[0], 'given': parts[1]})
        else:
            # Handle "First Last" format
            parts = name.rsplit(' ', 1)
            if len(parts) == 2:
                names.append({'given': parts[0], 'family': parts[1]})
            else:
                names.append({'family': name})
    
    return names


def _convert_to_clipboard(temp_md: Path, csl_path: Path) -> None:
    """Convert markdown to clipboard format (RTF with formatting).
    
    Args:
        temp_md: Path to temporary markdown file
        csl_path: Path to CSL style file
    """
    # Generate RTF which preserves formatting when pasted into Word
    result = subprocess.run(
        ['pandoc', str(temp_md), '-t', 'rtf', '--citeproc', f'--csl={csl_path}'],
        capture_output=True,
        text=True,
        check=True
    )
    
    rtf_content = result.stdout
    
    # Copy to clipboard (cross-platform)
    try:
        import pyperclip
        pyperclip.copy(rtf_content)
        print("✓ Citation copied to clipboard (paste into Word with Ctrl+V/Cmd+V)")
    except ImportError:
        # Fallback: platform-specific clipboard
        import sys
        if sys.platform == 'darwin':  # macOS
            subprocess.run('pbcopy', input=rtf_content.encode(), check=True)
            print("✓ Citation copied to clipboard")
        elif sys.platform == 'win32':  # Windows
            subprocess.run('clip', input=rtf_content.encode(), check=True)
            print("✓ Citation copied to clipboard")
        else:
            print("Warning: pyperclip not installed. Install with: pip install pyperclip")
            print("\nRTF content:")
            print(rtf_content)


def _convert_to_docx(temp_md: Path, csl_path: Path) -> str:
    """Convert markdown to Word document.
    
    Args:
        temp_md: Path to temporary markdown file
        csl_path: Path to CSL style file
        
    Returns:
        Path to created Word document
    """
    output_file = temp_md.with_suffix('.docx')
    subprocess.run(
        ['pandoc', str(temp_md), '-o', str(output_file), '--citeproc', f'--csl={csl_path}'],
        check=True,
        capture_output=True,
        text=True
    )
    return str(output_file)


def _convert_to_text(temp_md: Path, csl_path: Path, output_format: str) -> str:
    """Convert markdown to text format.
    
    Args:
        temp_md: Path to temporary markdown file
        csl_path: Path to CSL style file
        output_format: Output format (plain, markdown, html, rtf)
        
    Returns:
        Formatted citation as string
    """
    result = subprocess.run(
        ['pandoc', str(temp_md), '-t', output_format, '--citeproc', f'--csl={csl_path}'],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()
