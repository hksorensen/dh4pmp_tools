# bibfetcher Installation Guide

## Prerequisites

- Python 3.8 or higher
- pip package manager
- (Optional) citation_tools for duplicate detection

## Installation Steps

### 1. Extract to Monorepo

```bash
# Create tools directory if it doesn't exist
mkdir -p ~/Documents/dh4pmp/tools

# Extract the package
cd ~/Downloads
tar -xzf bibfetcher.tar.gz

# Move to monorepo
mv bibfetcher ~/Documents/dh4pmp/tools/

# Verify structure
ls ~/Documents/dh4pmp/tools/bibfetcher
# Should see: bibfetcher/ tests/ pyproject.toml README.md INSTALL.md
```

### 2. Install Package

```bash
cd ~/Documents/dh4pmp
pip install -e ./tools/bibfetcher
```

The `-e` flag installs in "editable" mode, meaning changes to the code take effect immediately.

### 3. Verify Installation

```bash
# Check that bibfetch command is available
bibfetch --help

# Should see usage information
```

### 4. Test Basic Functionality

```bash
# Try fetching a DOI (uses arXiv which should always work)
bibfetch 10.48550/ARXIV.2404.12345

# Should output BibTeX and copy to clipboard
```

## Directory Structure After Installation

```
~/Documents/dh4pmp/
├── tools/
│   ├── bibfetcher/                    # ← Package source
│   │   ├── bibfetcher/
│   │   │   ├── __init__.py
│   │   │   ├── bibfetcher.py
│   │   │   ├── cli.py
│   │   │   ├── config.py
│   │   │   ├── user_config.py
│   │   │   ├── input_identifier.py
│   │   │   ├── index.py
│   │   │   ├── fetchers/
│   │   │   ├── utils/
│   │   │   └── pdf/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   └── citation_tools/                # ← Optional, for integration
├── config/
│   └── bibfetcher/                    # ← Created on first run
│       └── user_config.json
└── .cache/
    ├── bibfetcher/                    # ← Created on first run
    └── citation_tools/                # ← If citation_tools installed
        └── bibtex_index.json
```

## Configuration

### First Run Setup

On first run, bibfetcher will create default configuration:

```bash
bibfetch config show
```

### Customize Settings

```bash
# Enable/disable clipboard output
bibfetch config set clipboard_output true

# Enable verbose mode by default
bibfetch config set verbose true
```

### Configuration File Location

- **In monorepo**: `~/Documents/dh4pmp/config/bibfetcher/user_config.json`
- **Standalone**: `~/.config/bibfetcher/user_config.json`

## Optional: citation_tools Integration

If you have citation_tools installed, bibfetcher will automatically:
- Check for existing entries before fetching
- Ensure unique BibTeX keys

No additional setup needed – bibfetcher finds the index automatically.

## Updating .gitignore

Add these lines to your monorepo's `.gitignore`:

```gitignore
# Cache directories
/.cache/

# Optional: keep config per-user
# /config/
```

## Troubleshooting Installation

### "Command not found: bibfetch"

The `pip install -e` may not have added the script to your PATH.

**Solution**:
```bash
# Find where pip installed it
pip show -f bibfetcher | grep bin

# Add that directory to your PATH, or reinstall:
pip uninstall bibfetcher
pip install -e ./tools/bibfetcher
```

### "ImportError: No module named 'bibfetcher'"

The package wasn't installed correctly.

**Solution**:
```bash
cd ~/Documents/dh4pmp
pip install -e ./tools/bibfetcher --force-reinstall
```

### "bibtexparser version 2 is not supported"

You have bibtexparser v2 installed, but bibfetcher requires v1.

**Solution**:
```bash
pip install 'bibtexparser>=1.2.0,<2.0'
```

### Permission Errors

**Solution**:
```bash
# Install for user only (no sudo needed)
pip install -e ./tools/bibfetcher --user
```

## Uninstallation

```bash
# Uninstall package
pip uninstall bibfetcher

# Optionally remove files
rm -rf ~/Documents/dh4pmp/tools/bibfetcher
rm -rf ~/Documents/dh4pmp/config/bibfetcher
rm -rf ~/Documents/dh4pmp/.cache/bibfetcher

# Or in standalone mode
rm -rf ~/.config/bibfetcher
rm -rf ~/.cache/bibfetcher
```

## Development Installation

For development with all optional dependencies:

```bash
cd ~/Documents/dh4pmp/tools/bibfetcher
pip install -e '.[dev]'

# This installs:
# - pytest (testing)
# - pytest-cov (coverage)
# - black (formatting)
# - ruff (linting)
```

## Next Steps

After installation:

1. **Read the README**: `cat ~/Documents/dh4pmp/tools/bibfetcher/README.md`
2. **Try examples**: See README examples section
3. **Configure**: Run `bibfetch config show` to see settings
4. **Integrate with citation_tools**: Install citation_tools if you haven't already

## Getting Help

- Check README.md for usage examples
- Run `bibfetch --help` for command reference
- Run `bibfetch -v <identifier>` for verbose output to debug issues
