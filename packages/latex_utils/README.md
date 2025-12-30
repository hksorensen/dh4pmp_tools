# LaTeX Utils

Utilities for working with LaTeX programmatically.

## Installation

```bash
pip install -e /path/to/dh4pmp_tools/packages/latex_utils

# Also requires LaTeX distribution
brew install texlive
```

## Usage

### Escape LaTeX special characters

```python
from latex_utils import escape_latex, sanitize_label

# Escape text for LaTeX
text = "Price: $100 & 50%"
safe = escape_latex(text)
# Output: 'Price: \\$100 \\& 50\\%'

# Create valid labels
label = sanitize_label("My Section #1")
# Output: 'my_section_1'
```

### Build LaTeX documents

```python
from latex_utils import LatexDocument, compile_latex

# Build document
doc = LatexDocument(documentclass='article', classoptions=['11pt', 'a4paper'])
doc.add_package('geometry', options='margin=1in')
doc.add_package('hyperref', options='colorlinks')

doc.add_content(r'\\section{Introduction}')
doc.add_content('This is my document.')
doc.add_content(r'\\section{Methods}')
doc.add_content('We did some science.')

# Get LaTeX source
latex_source = doc.build()

# Compile to PDF
pdf_path = compile_latex(latex_source, output_pdf='output.pdf')
print(f"Generated: {pdf_path}")
```

### Quick compilation

```python
from latex_utils import compile_latex

latex = r"""
\\documentclass{article}
\\begin{document}
Hello, World!
\\end{document}
"""

pdf = compile_latex(latex, output_pdf='hello.pdf')
```

## Features

- ✅ Escape/unescape LaTeX special characters
- ✅ Programmatic document building
- ✅ Compile LaTeX to PDF (pdflatex, xelatex, lualatex)
- ✅ Generate valid LaTeX labels from text
- ✅ Multiple compilation runs (for references, TOC)
