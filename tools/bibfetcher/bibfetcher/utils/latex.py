"""
LaTeX character conversion utilities.

Handles conversion between Unicode characters and LaTeX representations,
based on the latexify function from from_doi.py.
"""


def text_to_latex(text: str, preserve_danish: bool = False) -> str:
    """Convert Unicode text to LaTeX-safe format.

    Converts special characters to their LaTeX equivalents and escapes
    characters that have special meaning in LaTeX.

    Args:
        text: Unicode text string
        preserve_danish: If True, preserve æ, ø, å for proper Danish sorting

    Returns:
        LaTeX-formatted string
    """
    if text is None:
        return None

    # HTML entities to Unicode
    text = text.replace('&amp;', '&')

    # Unicode to LaTeX special characters
    text = text.replace('ó', "{\\'{o}}")
    text = text.replace('á', "{\\'{a}}")
    text = text.replace('é', "{\\'{e}}")
    text = text.replace('í', "{\\'{\\i}}")
    text = text.replace('ñ', "{\\~{n}}")

    # Danish characters (only escape if not preserving)
    if not preserve_danish:
        text = text.replace('æ', "{\\ae}")
        text = text.replace('ø', "{\\o}")
        text = text.replace('å', "{\\a}")

    text = text.replace('ü', "{\\\"u}")
    text = text.replace('ö', "{\\\"o}")
    text = text.replace('ä', "{\\\"a}")
    text = text.replace('ç', "{\\c{c}}")
    text = text.replace('ć', "{\\'c}")
    text = text.replace('ß', "{\\ss}")
    
    # Escape LaTeX special characters
    text = text.replace('#', '\\#')
    text = text.replace('&', '{\\&}')
    text = text.replace('%', '\\%')
    text = text.replace('$', '\\$')
    
    # Typographic quotes to LaTeX
    if '{\\textquotedblleft}' in text and '{\\textquotedblright}' in text:
        text = text.replace('{\\textquotedblleft}', '\\enquote{')
        text = text.replace('{\\textquotedblright}', '}')
    
    # Dashes
    text = text.replace('{\\textendash}', '--')
    text = text.replace('{\\textquotesingle}', "'")
    text = text.replace('–', '--')  # en-dash
    text = text.replace('—', '---')  # em-dash
    
    # Unicode quotes
    text = text.replace(''', "'")
    text = text.replace(''', "'")
    text = text.replace('"', "``")
    text = text.replace('"', "''")
    
    # Clean up spacing
    text = text.replace(' ', ' ')  # Non-breaking space to regular space
    
    return text


def text_to_latex_preserve_danish(text: str) -> str:
    """Convert Unicode text to LaTeX-safe format, preserving Danish characters.

    Wrapper around text_to_latex(preserve_danish=True) for convenience.
    Use this for author/editor fields in BibTeX to preserve proper sorting.

    Args:
        text: Unicode text string

    Returns:
        LaTeX-formatted string with Danish characters (æ, ø, å) preserved
    """
    return text_to_latex(text, preserve_danish=True)


def latex_to_text(latex: str) -> str:
    """Convert LaTeX formatting to Unicode text.
    
    Converts LaTeX special character commands to their Unicode equivalents.
    This is the inverse of text_to_latex().
    
    Args:
        latex: LaTeX-formatted string
        
    Returns:
        Unicode text string
    """
    if latex is None:
        return None
    
    # LaTeX special characters to Unicode
    latex = latex.replace("{\\'{o}}", 'ó')
    latex = latex.replace("{\\'{a}}", 'á')
    latex = latex.replace("{\\'{e}}", 'é')
    latex = latex.replace("{\\'{\\i}}", 'í')
    latex = latex.replace("{\\~{n}}", 'ñ')
    latex = latex.replace("{\\ae}", 'æ')
    latex = latex.replace("{\\o}", 'ø')
    latex = latex.replace("{\\a}", 'å')
    latex = latex.replace("{\\\"u}", 'ü')
    latex = latex.replace("{\\\"o}", 'ö')
    latex = latex.replace("{\\\"a}", 'ä')
    latex = latex.replace("{\\c{c}}", 'ç')
    latex = latex.replace("{\\'c}", 'ć')
    latex = latex.replace("{\\ss}", 'ß')
    
    # Unescape LaTeX special characters
    latex = latex.replace('{\\&}', '&')
    latex = latex.replace('\\#', '#')
    latex = latex.replace('\\%', '%')
    latex = latex.replace('\\$', '$')
    
    # LaTeX quotes to Unicode
    latex = latex.replace('\\enquote{', '"')
    latex = latex.replace("``", '"')
    latex = latex.replace("''", '"')
    
    # Dashes
    latex = latex.replace('---', '—')  # em-dash
    latex = latex.replace('--', '–')   # en-dash
    
    return latex


def normalize_bibkey_chars(text: str) -> str:
    """Normalize special characters for BibTeX keys.
    
    Converts accented characters to their ASCII equivalents for use in
    BibTeX citation keys (e.g., Müller -> Muller).
    
    Args:
        text: Text to normalize
        
    Returns:
        ASCII-normalized text suitable for BibTeX keys
    """
    if text is None:
        return None
    
    # Map of special characters to ASCII equivalents
    normalize_map = {
        'ć': 'c',
        "{\\'c}": 'c',
        'ç': 'c',
        'ø': 'o',
        'ö': 'o',
        'ü': 'u',
        'å': 'aa',
        'æ': 'ae',
        'ä': 'a',
        'ï': 'i',
        'á': 'a',
        'ó': 'o',
        'é': 'e',
        'í': 'i',
        'ñ': 'n',
        'ß': 'ss',
        'Œ': 'OE',
        'œ': 'oe',
        'Š': 'S',
        'š': 's',
        'Ž': 'Z',
        'ž': 'z',
        'Ö': 'O',
    }
    
    for char, replacement in normalize_map.items():
        text = text.replace(char, replacement)
    
    return text


def ucfirst(s: str) -> str:
    """Capitalize first character of string.
    
    Args:
        s: Input string
        
    Returns:
        String with first character capitalized
    """
    if s is None or len(s) == 0:
        return ''
    s = s.strip()
    return s[0].upper() + s[1:]
