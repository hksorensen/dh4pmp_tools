"""
LaTeX Utilities

Tools for working with LaTeX:
- Escaping special characters
- Building LaTeX documents
- Running pdflatex/latexmk
"""

from .escaping import escape_latex, unescape_latex, sanitize_label
from .builder import LatexDocument, compile_latex

__version__ = '0.1.0'

__all__ = [
    'escape_latex',
    'unescape_latex',
    'sanitize_label',
    'LatexDocument',
    'compile_latex',
]
