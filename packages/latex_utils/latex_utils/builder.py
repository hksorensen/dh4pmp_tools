"""
LaTeX document builder and compilation utilities.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List
import shutil


class LatexDocument:
    """
    Build LaTeX documents programmatically.

    Example:
        >>> doc = LatexDocument(documentclass='article')
        >>> doc.add_package('graphicx')
        >>> doc.add_package('hyperref', options='colorlinks')
        >>> doc.add_content(r'\\section{Introduction}')
        >>> doc.add_content('This is my document.')
        >>> latex_str = doc.build()
    """

    def __init__(self, documentclass: str = 'article',
                 classoptions: Optional[List[str]] = None):
        """
        Initialize document.

        Args:
            documentclass: LaTeX document class (article, report, book, etc.)
            classoptions: Class options like ['11pt', 'a4paper']
        """
        self.documentclass = documentclass
        self.classoptions = classoptions or []
        self.packages = []
        self.preamble = []
        self.content = []

    def add_package(self, package: str, options: Optional[str] = None):
        """
        Add a LaTeX package.

        Args:
            package: Package name
            options: Package options (comma-separated string)

        Example:
            >>> doc.add_package('geometry', options='margin=1in')
        """
        if options:
            self.packages.append(f"\\usepackage[{options}]{{{package}}}")
        else:
            self.packages.append(f"\\usepackage{{{package}}}")

    def add_preamble(self, content: str):
        """Add content to preamble (before \\begin{document})."""
        self.preamble.append(content)

    def add_content(self, content: str):
        """Add content to document body."""
        self.content.append(content)

    def build(self) -> str:
        """
        Build the complete LaTeX document.

        Returns:
            Complete LaTeX source code
        """
        lines = []

        # Document class
        if self.classoptions:
            options = ','.join(self.classoptions)
            lines.append(f"\\documentclass[{options}]{{{self.documentclass}}}")
        else:
            lines.append(f"\\documentclass{{{self.documentclass}}}")

        # Packages
        lines.extend(self.packages)

        # Preamble
        lines.extend(self.preamble)

        # Begin document
        lines.append("")
        lines.append("\\begin{document}")
        lines.append("")

        # Content
        lines.extend(self.content)

        # End document
        lines.append("")
        lines.append("\\end{document}")

        return '\n'.join(lines)


def compile_latex(latex_source: str, output_pdf: Optional[Path] = None,
                 engine: str = 'pdflatex',
                 runs: int = 2) -> Path:
    """
    Compile LaTeX source to PDF.

    Args:
        latex_source: LaTeX source code
        output_pdf: Output PDF path (if None, returns temp file)
        engine: LaTeX engine (pdflatex, xelatex, lualatex)
        runs: Number of compilation runs (for references, TOC, etc.)

    Returns:
        Path to generated PDF

    Example:
        >>> latex = doc.build()
        >>> pdf_path = compile_latex(latex, output_pdf='output.pdf')
        >>> print(f"Generated: {pdf_path}")

    Raises:
        RuntimeError: If compilation fails
    """
    # Check if engine is installed
    if not shutil.which(engine):
        raise RuntimeError(
            f"{engine} not found. Install with: brew install texlive"
        )

    # Create temp directory for compilation
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        tex_file = tmpdir / 'document.tex'

        # Write source
        tex_file.write_text(latex_source)

        # Compile (possibly multiple times for references)
        for i in range(runs):
            result = subprocess.run(
                [engine, '-interaction=nonstopmode', 'document.tex'],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                # Save log for debugging
                log_file = tmpdir / 'document.log'
                error_msg = f"LaTeX compilation failed:\n{result.stdout}\n{result.stderr}"
                if log_file.exists():
                    error_msg += f"\n\nLog file:\n{log_file.read_text()}"
                raise RuntimeError(error_msg)

        # Copy PDF to output location
        pdf_file = tmpdir / 'document.pdf'
        if not pdf_file.exists():
            raise RuntimeError("PDF was not generated")

        if output_pdf:
            output_pdf = Path(output_pdf)
            shutil.copy(pdf_file, output_pdf)
            return output_pdf
        else:
            # Return temp file (will be deleted when tmpdir is cleaned up)
            # So we copy to a new temp location
            temp_pdf = Path(tempfile.gettempdir()) / 'latex_output.pdf'
            shutil.copy(pdf_file, temp_pdf)
            return temp_pdf
