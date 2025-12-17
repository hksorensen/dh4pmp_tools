# Citation Tools

Convert BibTeX entries to formatted citations using CSL styles. Supports multiple output formats including Word documents and clipboard integration.

## Features

- **Multiple CSL styles**: Bundled Danish style (Fund og Forskning), downloadable standard styles (Chicago, APA, etc.)
- **BibTeX indexing**: Fast lookup of citations by key across multiple .bib files
- **Multiple output formats**: Plain text, Markdown, HTML, RTF, Word documents, clipboard
- **Monorepo-friendly**: Uses project-local cache when in a git repository

## Installation

### Prerequisites

- Python 3.7+
- Pandoc (install from https://pandoc.org/installing.html)

### Install package

```bash
# From your monorepo root (or wherever you want to place it)
pip install -e /path/to/citation_tools
```

Or for development with optional dependencies:

```bash
pip install -e /path/to/citation_tools[clipboard,dev]
```

## Configuration

### Initial Setup

On first use, configure your bibliography directories:

```bash
# Add your bibliography directory (uses ~/Documents/bibfiles by default)
cite config add-bibdir ~/Documents/bibfiles

# Or add multiple directories
cite config add-bibdir ~/research/papers
cite config add-bibdir ~/thesis/references

# Set your preferred defaults
cite config set-style fund-og-forskning
cite config set-format clipboard

# View current configuration
cite config show
```

### Configuration Files

Cache and config files are stored:
- **In monorepo**: `.cache/citation_tools/` and `config/citation_tools/`
- **Outside monorepo**: `~/.cache/citation_tools/` and `~/.config/citation_tools/`

### Default Configuration

The default config file (`user_config.json`) contains:
```json
{
  "bibliography_directories": [
    "~/Documents/bibfiles"
  ],
  "default_style": "chicago-author-date",
  "default_output_format": "plain",
  "index_auto_rebuild": true
}
```

### Config Commands

```bash
# View configuration
cite config show

# Set default citation style
cite config set-style fund-og-forskning

# Set default output format
cite config set-format clipboard

# Add bibliography directory
cite config add-bibdir ~/Documents/bibfiles

# Remove bibliography directory
cite config remove-bibdir ~/old-papers

# Reset to defaults
cite config reset --confirm
```

## Quick Start

### CLI Usage

```bash
# 1. Configure your bibliography directories (one-time)
cite config add-bibdir ~/Documents/bibfiles

# 2. Build an index (uses configured directories)
cite index build --recursive

# 3. Convert a citation by key (uses configured defaults)
cite convert --key Arhiliuc2024a

# 4. Or override defaults
cite convert --key Kondrup2010 --style fund-og-forskning --format clipboard
```

### Without Configuration

You can still use the tool without configuration:

```bash
# Build index with explicit directory
cite index build --directory ~/Documents/bibliography --recursive

# Convert with explicit style and format
cite convert --key Doe2024 --style apa --format plain
```

### Python API Usage

```python
from citation_tools import bibtex_to_citation, bibtex_to_citation_from_key, BibTeXIndex

# Direct conversion
bibtex = """@article{Doe2024,
    author = {Doe, John},
    title = {An Example},
    year = {2024},
    journal = {Example Journal}
}"""

citation = bibtex_to_citation(bibtex, style='apa', output_format='plain')
print(citation)

# Using index
from pathlib import Path

index = BibTeXIndex(index_file=Path('~/.cache/citation_tools/bibtex_index.json'))
index.add_bib_directory(Path('~/Documents/bibliography'), recursive=True)

citation = bibtex_to_citation_from_key(
    'Doe2024',
    index,
    style='chicago-author-date',
    output_format='plain'
)
```

## Available Styles

### Bundled
- `fund-og-forskning` - Danish humanities style (auto-installed)

### Downloadable (on first use)
- `chicago-note-bibliography` - Chicago notes with bibliography
- `chicago-author-date` - Chicago author-date
- `authoryear` - Alias for chicago-author-date
- `apa` - APA style

## Output Formats

- `plain` - Plain text
- `markdown` - Markdown format
- `html` - HTML format
- `rtf` - Rich Text Format
- `docx` - Microsoft Word document
- `clipboard` - Copy to clipboard (RTF format for Word compatibility)

## Configuration

Cache and config files are stored:
- **In monorepo**: `.cache/citation_tools/` and `config/citation_tools/`
- **Outside monorepo**: `~/.cache/citation_tools/` and `~/.config/citation_tools/`

View current configuration:
```bash
cite config show
```

## Index Management

```bash
# Build initial index
cite index build --directory ~/Documents/bibliography --recursive

# Add more files
cite index add-file ~/new-paper/references.bib
cite index add-dir ~/more-papers/ --recursive

# Rebuild entire index
cite index rebuild

# View statistics
cite index info

# List all keys
cite index list

# Search for specific keys
cite index search "Kondrup"

# Show BibTeX entry
cite index show Arhiliuc2024a
```

## Dependencies

Required:
- `bibtexparser` - BibTeX parsing
- `PyYAML` - YAML generation for Pandoc
- `pandoc` - Citation formatting (external tool)

Optional:
- `pyperclip` - Cross-platform clipboard support

## Development

```bash
# Install with dev dependencies
pip install -e .[dev]

# Run tests (when added)
pytest

# Format code
black citation_tools/
ruff check citation_tools/
```

## License

MIT
