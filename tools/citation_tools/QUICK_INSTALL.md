# Installation Instructions

## Download Location
The tarball `citation_tools.tar.gz` will download to: **`~/Downloads/`**

## Installation Steps

```bash
# 1. Extract the tarball
cd ~/Downloads
tar -xzf citation_tools.tar.gz

# 2. Move to your monorepo
mkdir -p ~/Documents/dh4pmp/tools
mv citation_tools ~/Documents/dh4pmp/tools/

# 3. Install the package
cd ~/Documents/dh4pmp
pip install -e ./tools/citation_tools

# 4. Run first-time setup (initializes config)
cite-setup
```

## What `cite-setup` Does

The setup script will:
1. ✅ Check if `~/Documents/bibfiles` exists
2. ✅ Count how many .bib files are there
3. ✅ Create config file with:
   - Bibliography directory: `~/Documents/bibfiles`
   - Default style: `fund-og-forskning` (Danish)
   - Default format: `clipboard`
4. ✅ Show you next steps

## After Setup

```bash
# Build the index (uses ~/Documents/bibfiles automatically)
cite index build --recursive

# Use it! (uses fund-og-forskning + clipboard automatically)
cite convert --key YourCitationKey
# Then Ctrl+V into Word

# View configuration anytime
cite config show
```

## File Structure After Installation

```
~/Documents/dh4pmp/
├── tools/
│   └── citation_tools/           # ← Package code
│       ├── __init__.py
│       ├── cli.py
│       ├── setup_config.py       # ← NEW: Setup script
│       └── ...
├── config/citation_tools/         # ← Created by cite-setup
│   └── user_config.json          # ← Your preferences
├── .cache/citation_tools/         # ← Created on first use
│   ├── fund-og-forskning.csl
│   └── bibtex_index.json
├── .git/
└── .gitignore                     # ← Update this
```

## Update .gitignore

Add these lines to `~/Documents/dh4pmp/.gitignore`:

```gitignore
# Citation tools cache (don't commit)
/.cache/

# Optionally make config per-user (uncomment if you want):
# /config/
```

## Troubleshooting

### If ~/Documents/bibfiles doesn't exist:

```bash
# Create it
mkdir -p ~/Documents/bibfiles

# Or configure a different path
cite config add-bibdir ~/actual/path/to/bibfiles

# Then run setup again
cite-setup
```

### Manual configuration (without cite-setup):

```bash
cite config add-bibdir ~/Documents/bibfiles
cite config set-style fund-og-forskning
cite config set-format clipboard
cite config show
```

## Quick Reference

```bash
# Setup (once)
cite-setup
cite index build --recursive

# Daily usage
cite convert --key Kondrup2010          # Uses your defaults!
cite index search "pattern"             # Find citation keys
cite config show                        # View settings

# Override defaults when needed
cite convert --key Doe2024 --style apa --format docx
```

## Complete Workflow Example

```bash
# 1. Download & install
cd ~/Downloads
tar -xzf citation_tools.tar.gz
mkdir -p ~/Documents/dh4pmp/tools
mv citation_tools ~/Documents/dh4pmp/tools/
cd ~/Documents/dh4pmp
pip install -e ./tools/citation_tools

# 2. First-time setup
cite-setup

# 3. Build index
cite index build --recursive

# 4. Use it!
cite convert --key Arhiliuc2024a
# Citation copied to clipboard in Danish format!
# Paste into Word footnote with Ctrl+V
```

That's it! 🎉
