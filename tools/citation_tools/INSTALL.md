# Installation Instructions

## Where to Place the Files

You have **two options** for where to place this package in your monorepo:

### Option 1: As a top-level package (Recommended)

```
your-monorepo/
├── citation_tools/              # ← Place the entire citation_tools folder here
│   ├── __init__.py
│   ├── bibtex_index.py
│   ├── citation_converter.py
│   ├── cli.py
│   ├── config.py
│   ├── csl_manager.py
│   ├── pyproject.toml
│   ├── README.md
│   └── styles/
│       └── fund-og-forskning.csl
├── .cache/                      # ← Will be created automatically
│   └── citation_tools/
│       ├── *.csl (cached styles)
│       └── bibtex_index.json
├── config/                      # ← Add to .gitignore if needed
│   └── citation_tools/
├── .git/
├── .gitignore                   # ← Update this (see below)
└── other_packages/
```

### Option 2: Inside a packages/tools directory

```
your-monorepo/
├── packages/
│   └── tools/
│       └── citation_tools/      # ← Place it here
│           ├── __init__.py
│           ├── ...
│           └── pyproject.toml
├── .cache/                      # ← Created at monorepo root
└── .git/
```

## Step-by-Step Installation

### 1. Copy Files

From your terminal:

```bash
# Navigate to your monorepo root
cd /path/to/your/monorepo

# Copy the citation_tools directory
cp -r /tmp/citation_tools ./citation_tools

# Or if using Option 2:
# mkdir -p packages/tools
# cp -r /tmp/citation_tools ./packages/tools/citation_tools
```

### 2. Update .gitignore

Add these lines to your `.gitignore`:

```gitignore
# Citation tools cache (local, don't commit)
/.cache/citation_tools/

# But DO commit config if you want shared settings
# Uncomment the next line if you want config to be per-user:
# /config/citation_tools/
```

### 3. Install the Package

```bash
# Install in development mode (from monorepo root)
pip install -e ./citation_tools

# Or with optional dependencies:
pip install -e ./citation_tools[clipboard,dev]
```

### 4. Verify Installation

```bash
# Check that the CLI works
cite --help

# Check that styles are available
cite styles list
```

You should see:
```
Bundled styles:
  fund-og-forskning

Remote styles (will be downloaded on first use):
  apa
  authoryear
  chicago-author-date
  chicago-note-bibliography
```

### 5. Configure Your Bibliography Directories

```bash
# Set up your bibliography directory (defaults to ~/Documents/bibfiles)
cite config add-bibdir ~/Documents/bibfiles

# View configuration
cite config show
```

### 6. Build Your BibTeX Index

```bash
# Now build index using configured directories
cite index build --recursive

# Or specify a directory explicitly
cite index build --directory ~/Documents/bibliography --recursive
```

## Test It Out

Try converting a citation:

```bash
# Using a raw BibTeX string
cite convert '@article{Test2024, author={Test, User}, title={Example}, year={2024}, journal={Test}}' \
  --style fund-og-forskning --format plain

# Using a citation key (after building index)
cite convert --key YourCitationKey --style fund-og-forskning --format clipboard
```

## Troubleshooting

### "pandoc: command not found"

Install Pandoc:
- **macOS**: `brew install pandoc`
- **Ubuntu/Debian**: `sudo apt install pandoc`
- **Windows**: Download from https://pandoc.org/installing.html

### "Index file not found"

You need to build the index first:
```bash
cite index build --directory ~/path/to/your/bib/files --recursive
```

### "Module 'citation_tools' not found"

Make sure you installed it:
```bash
pip install -e ./citation_tools
```

And check you're in the right Python environment.

### Clipboard not working

Install pyperclip:
```bash
pip install pyperclip
```

## Next Steps

1. **Build your index** with all your .bib files
2. **Test the Danish style** with one of your entries
3. **Set up aliases** if you want shorter commands:
   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   alias cite-da='cite convert --style fund-og-forskning --format clipboard --key'
   
   # Then use like:
   # cite-da Kondrup2010
   ```

## Questions?

Check the README.md in the citation_tools folder for more detailed usage examples.
