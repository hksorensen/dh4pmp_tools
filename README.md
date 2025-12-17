# dh4pmp_tools

Research tools for digital humanities, philosophy, mathematics, and history.

**Author**: Henrik Kragh Sørensen  
**Institution**: University of Copenhagen  
**License**: MIT (or your preferred license)

## Overview

This repository contains reusable Python tools and packages developed for academic research workflows, with a focus on bibliography management, citation formatting, and metadata extraction.

## Tools

Command-line utilities for research workflows:

### bibfetcher
Fetch bibliographic metadata from DOI, ISBN, arXiv IDs, or PDF files.

```bash
pip install -e ./tools/bibfetcher
bibfetch 10.1234/example  # Fetch by DOI
bibfetch paper.pdf         # Extract from PDF
```

**Features:**
- Multiple input sources (DOI, ISBN, arXiv, PDF)
- Automatic BibTeX generation
- Duplicate detection
- LaTeX normalization
- Title/subtitle splitting
- Auto-append to bibliography files

[Full documentation](tools/bibfetcher/README.md)

### citation_tools
Bibliography management and citation formatting system.

```bash
pip install -e ./tools/citation_tools
cite index build           # Build bibliography index
cite convert input.bib     # Convert citations
```

**Features:**
- BibTeX index management
- CSL style handling
- Danish humanities formatting ("Fund og Forskning")
- Search and lookup functions

[Full documentation](tools/citation_tools/README.md)

## Packages

Python libraries for common tasks:

### api_clients
Client libraries for various APIs (Anthropic, OpenAI, etc.)

### arxiv_metadata
Fetch and process arXiv paper metadata

### caching
Caching utilities and helpers

### web_fetcher
Web content fetching utilities

## Installation

Each tool/package can be installed independently:

```bash
# Install a tool
cd tools/bibfetcher
pip install -e .

# Or install a package
cd packages/api_clients
pip install -e .
```

## Requirements

- Python 3.8+
- See individual `pyproject.toml` or `requirements.txt` for specific dependencies

## Development

### For Contributors

See [CLAUDE_WORKFLOW.md](CLAUDE_WORKFLOW.md) for detailed development workflow, especially if collaborating with Claude AI.

### Project Structure

```
dh4pmp_tools/
├── tools/              # Command-line utilities
├── packages/           # Python libraries
├── CLAUDE_WORKFLOW.md  # Development workflow
└── README.md          # This file
```

### Running Tests

```bash
# Each project has its own tests
cd tools/bibfetcher
pytest

cd tools/citation_tools
pytest
```

## Documentation

- Each tool/package has its own README.md with detailed documentation
- See CLAUDE_WORKFLOW.md for development workflow
- Check individual CHANGELOG.md files for version history

## Use Cases

**For Researchers:**
- Automate bibliography management
- Extract metadata from PDFs
- Format citations for publications
- Manage large reference libraries

**For Developers:**
- Reusable components for academic tools
- API clients for AI services
- Caching and web fetching utilities

## Citation

If you use these tools in your research, please cite:

```bibtex
@software{sorensen_dh4pmp_tools,
  author = {Sørensen, Henrik Kragh},
  title = {dh4pmp_tools: Research Tools for Digital Humanities},
  year = {2024},
  url = {https://github.com/hksorensen/dh4pmp_tools}
}
```

## License

MIT License - see LICENSE file for details

## Contact

- GitHub: [@hksorensen](https://github.com/hksorensen)
- Issues: [Report bugs or request features](https://github.com/hksorensen/dh4pmp_tools/issues)

## Acknowledgments

Developed at the University of Copenhagen for digital humanities research in philosophy, mathematics, and history.

---

**Note**: This repository contains only the tools and packages. Research-specific code and data are maintained separately.
