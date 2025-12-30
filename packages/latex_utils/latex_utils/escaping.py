"""
LaTeX character escaping utilities.
"""

import re


# LaTeX special characters that need escaping
LATEX_SPECIAL_CHARS = {
    '&': r'\&',
    '%': r'\%',
    '$': r'\$',
    '#': r'\#',
    '_': r'\_',
    '{': r'\{',
    '}': r'\}',
    '~': r'\textasciitilde{}',
    '^': r'\^{}',
    '\\': r'\textbackslash{}',
}


def escape_latex(text: str, math_mode: bool = False) -> str:
    """
    Escape special LaTeX characters in text.

    Args:
        text: Text to escape
        math_mode: If True, don't escape $, ^, _, {, }

    Returns:
        Escaped text safe for LaTeX

    Example:
        >>> escape_latex("Price: $100 & 50%")
        'Price: \\$100 \\& 50\\%'
        >>> escape_latex("x^2", math_mode=True)
        'x^2'
    """
    if math_mode:
        # In math mode, don't escape $ ^ _ { }
        chars_to_escape = {k: v for k, v in LATEX_SPECIAL_CHARS.items()
                          if k not in ['$', '^', '_', '{', '}']}
    else:
        chars_to_escape = LATEX_SPECIAL_CHARS

    # Escape backslash first, then others
    if '\\' in chars_to_escape and '\\' in text:
        text = text.replace('\\', chars_to_escape['\\'])

    # Escape other characters
    for char, replacement in chars_to_escape.items():
        if char != '\\' and char in text:
            text = text.replace(char, replacement)

    return text


def unescape_latex(text: str) -> str:
    """
    Unescape LaTeX special characters.

    Args:
        text: LaTeX text with escaped characters

    Returns:
        Plain text

    Example:
        >>> unescape_latex(r'Price: \$100 \& 50\%')
        'Price: $100 & 50%'
    """
    # Reverse mapping
    for char, escaped in LATEX_SPECIAL_CHARS.items():
        text = text.replace(escaped, char)

    return text


def sanitize_label(text: str) -> str:
    """
    Convert text to a valid LaTeX label.

    Args:
        text: Text to convert

    Returns:
        Valid LaTeX label (lowercase, no special chars)

    Example:
        >>> sanitize_label("My Section #1")
        'my_section_1'
    """
    # Lowercase
    text = text.lower()

    # Replace spaces and special chars with underscores
    text = re.sub(r'[^a-z0-9]+', '_', text)

    # Remove leading/trailing underscores
    text = text.strip('_')

    # Collapse multiple underscores
    text = re.sub(r'_+', '_', text)

    return text
