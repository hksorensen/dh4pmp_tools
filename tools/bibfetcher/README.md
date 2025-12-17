# bibfetcher

Fetch bibliographic metadata from DOI, ISBN, arXiv ID, or PDF files and generate BibTeX entries with unique citation keys.

## Features

- **Multiple Input Methods**: DOI, ISBN, arXiv ID, or PDF file path
- **Automatic Input Detection**: Paste any identifier – bibfetcher figures out what it is
- **PDF Extraction**: Extract DOI/arXiv ID from first page of PDF files
- **Unique Citation Keys**: Generates keys like `Lin2014a` (FirstAuthor + Year + suffix)
- **Duplicate Detection**: Checks citation_tools index to avoid re-fetching
- **Clipboard Integration**: Automatically copies BibTeX to clipboard
- **Multiple Sources**: Fetches from DOI resolver and Crossref API

## Quick Start

```bash
# Install
cd ~/Documents/dh4pmp
pip install -e ./tools/bibfetcher

# Fetch from DOI
bibfetch 10.1234/example

# Fetch from arXiv
bibfetch 2404.12345

# Extract from PDF
bibfetch paper.pdf

# Use clipboard (copy DOI/ISBN/arXiv first)
bibfetch
```

The BibTeX entry is automatically copied to your clipboard and printed to stdout.

## Installation

See [INSTALL.md](INSTALL.md) for detailed installation instructions.

## Usage

### Basic Usage

```bash
# Fetch using any identifier
bibfetch <identifier>

# Where identifier can be:
#   - DOI: 10.1234/example
#   - arXiv ID: 2404.12345
#   - ISBN: 978-0-123456-78-9
#   - PDF file: path/to/paper.pdf (or just path/to/paper - .pdf is added automatically)
#   - (or copy to clipboard and run: bibfetch)
```

**PDF file handling:**
- `bibfetch myfile.pdf` - works if file exists
- `bibfetch myfile` - automatically tries `myfile.pdf` if `myfile` doesn't exist
- Works from command line AND clipboard
```

**Interactive workflow:**
```bash
$ bibfetch 10.1234/example

@article{Smith2024a,
 author = {John Smith},
 title = {Example Article},
 ...
}

Generated key: Smith2024a

Append to bibliography file? [Y/n]: 

✓ Appended to: ~/Documents/bibfiles/references.bib
✓ Updated citation_tools index
✓ Copied key to clipboard: Smith2024a
```

**Default is YES** - just press Enter to append!

If you answer **yes** (or just press Enter): 
- Entry is appended to your bibliography file
- **citation_tools index is automatically updated** (if citation_tools is installed)
- The **key only** is copied to clipboard

If you answer **no**: Full BibTeX is copied to clipboard.

### Non-Interactive Mode

For scripts or when you don't want prompts:

```bash
bibfetch -n 10.1234/example     # No prompt, copies full BibTeX
bibfetch --no-interactive ...   # Same
```

### PDF Files

```bash
# Extract DOI from PDF and fetch metadata
bibfetch ~/Downloads/paper.pdf

# bibfetcher will:
# 1. Extract text from first page
# 2. Find DOI or arXiv ID
# 3. Fetch metadata
# 4. Generate BibTeX with unique key
# 5. Copy to clipboard
```

### Configuration

```bash
# Show current configuration (including append target)
bibfetch config show

# Configure where to append entries
bibfetch config set bibliography_directories ~/Documents/bibfiles

# Configure which file to append to (default: references.bib)
bibfetch config set bibliography_filename main.bib

# Result: entries will be appended to ~/Documents/bibfiles/main.bib

# Disable clipboard output
bibfetch config set clipboard_output false

# Enable verbose mode by default
bibfetch config set verbose true
```

**Configuration file location:**
- In monorepo: `{monorepo_root}/config/bibfetcher/user_config.json`
- Standalone: `~/.config/bibfetcher/user_config.json`

**Current append target:** Run `bibfetch config show` to see where entries will be appended.

### Verbose Mode

```bash
# See what bibfetcher is doing
bibfetch -v 10.1234/example

# Output will show:
#   Input type: doi
#   Normalized value: 10.1234/example
#   Loaded citation_tools index with 1234 entries
#   Fetching from DOI resolver: 10.1234/example
#   Generated key: Smith2024a
#   Copied to clipboard: Smith2024a
```

## How It Works

1. **Input Identification**: Automatically detects DOI, ISBN, arXiv ID, or PDF file
2. **Duplicate Check**: Checks citation_tools index to see if already fetched
   - If **found**: Shows existing key, location, copies key to clipboard ✓
   - If **not found**: Proceeds to fetch...
3. **Metadata Fetch**: Retrieves from DOI resolver or Crossref API
4. **Key Generation**: Creates unique BibTeX key (e.g., `Lin2014a`)
5. **Output**: Copies BibTeX to clipboard and prints to stdout

## Input Types

### DOI (Digital Object Identifier)
```
10.1234/example
https://doi.org/10.1234/example
http://dx.doi.org/10.1234/example
```

### arXiv ID
```
2404.12345
1234.5678
```
Automatically converted to DOI: `10.48550/ARXIV.2404.12345`

### ISBN (International Standard Book Number)
```
978-0-123456-78-9
9780123456789
```

### PDF Files
```
~/Downloads/paper.pdf
./research/article.pdf
```
Extracts DOI or arXiv ID from first page.

## Configuration

Configuration is stored in:
- **Monorepo**: `{monorepo_root}/config/bibfetcher/user_config.json`
- **Standalone**: `~/.config/bibfetcher/user_config.json`

### Default Settings

```json
{
  "bibliography_directories": ["~/Documents/bibfiles"],
  "bibliography_filename": "references.bib",
  "clipboard_output": true,
  "pdf_preview_enabled": true,
  "verbose": false
}
```

**bibliography_directories**: Where to append entries when you choose "yes"  
**bibliography_filename**: Which .bib file to append to (in first directory)  
**clipboard_output**: Whether to copy to clipboard  
**pdf_preview_enabled**: Enable PDF Preview.app integration (future)  
**verbose**: Show detailed output

## Integration with citation_tools

bibfetcher automatically integrates with citation_tools if available:

**During fetching:**
- **Duplicate Detection**: Checks citation_tools index before fetching
- **Key Uniqueness**: Ensures generated keys don't conflict with existing entries

**When appending to file:**
- **Automatic Index Update**: Runs `citation_tools index update <file.bib>` after appending
- **Keeps Index in Sync**: Your citation_tools index stays up-to-date automatically

The citation_tools index is automatically found in:
1. `{monorepo_root}/.cache/citation_tools/bibtex_index.json`
2. `~/.cache/citation_tools/bibtex_index.json`

**Note:** Index updates only happen when you choose to append to a file (answer "yes" to prompt). If you just copy to clipboard, the index is not modified.

## Examples

### Fetch a Paper

```bash
$ bibfetch 10.1007/s11192-024-05217-7

@article{Arhiliuc2024a,
 author = {Cristina Arhiliuc and Raf Guns and Walter Daelemans and Tim C. E. Engels},
 title = {Journal article classification using abstracts},
 subtitle = {A comparison of classical and transformer-based machine learning methods},
 year = {2024},
 journal = {Scientometrics},
 volume = {130},
 number = {1},
 pages = {313--342},
 doi = {10.1007/s11192-024-05217-7},
}

Generated key: Arhiliuc2024a
```

### Fetch from PDF

```bash
# With full filename
$ bibfetch ~/Downloads/interesting-paper.pdf

# Or without .pdf extension (added automatically)
$ bibfetch ~/Downloads/interesting-paper

Input type: pdf_file
Extracting identifier from PDF: /Users/you/Downloads/interesting-paper.pdf
Found doi: 10.1234/example
Fetching from DOI resolver: 10.1234/example
Generated key: Smith2024a
Copied to clipboard: Smith2024a

@article{Smith2024a,
 ...
}
```

### Use Clipboard

```bash
# 1. Copy DOI to clipboard: 10.1234/example
# 2. Run bibfetch
$ bibfetch

# BibTeX entry copied to clipboard
```

### Duplicate Detection

```bash
$ bibfetch 10.1234/example

✓ Entry already exists in citation_tools index
✓ Key: Smith2024a
✓ Location: ~/Documents/bibfiles/references.bib
✓ Copied key to clipboard: Smith2024a
```

If the DOI/arXiv ID is already in your bibliography:
- Shows you the existing key
- Shows you which file it's in
- Copies the key to clipboard (no need to re-fetch!)
- Exits successfully (not an error)

## Dependencies

- Python 3.8+
- bibtexparser (v1.x, pinned)
- requests
- PyPDF2
- pyperclip

## Troubleshooting

### "No DOI or arXiv ID found in PDF"

The PDF text extraction might not find identifiers if:
- The PDF is scanned/image-based (not text)
- The DOI is on a later page
- The DOI format is non-standard

**Solution**: Copy the DOI manually and use `bibfetch <doi>`

### "bibtexparser version 2 is not supported"

bibfetcher requires bibtexparser v1.x.

**Solution**: `pip install 'bibtexparser>=1.2.0,<2.0'`

### "Failed to copy to clipboard"

Clipboard access may require additional setup on some systems.

**Solution**: The BibTeX is still printed to stdout, so you can copy manually.

## Development

```bash
# Install in development mode
cd ~/Documents/dh4pmp/tools/bibfetcher
pip install -e .

# Run tests (when available)
pytest

# Format code
black bibfetcher/
```

## License

MIT License

## Credits

Developed by Henrik Holm Justesen

Based on functionality from the original `from_doi.py` script, with improvements:
- Unified input handling (CLI + clipboard)
- PDF extraction
- Monorepo-aware configuration
- citation_tools integration
- Proper packaging
