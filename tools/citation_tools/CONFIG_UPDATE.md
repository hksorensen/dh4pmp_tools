# Configuration System Update Summary

## What Changed

### ✅ Added User Configuration System

**New file:** `user_config.py`

This adds a proper user configuration system that:
- Stores your bibliography directories (defaults to `~/Documents/bibfiles`)
- Remembers your preferred citation style
- Remembers your preferred output format
- Auto-creates config file on first use

### ✅ Updated CLI

**Modified:** `cli.py`

New `config` subcommands:
```bash
cite config show                      # View all settings
cite config add-bibdir <dir>         # Add bibliography directory
cite config remove-bibdir <dir>      # Remove bibliography directory  
cite config set-style <style>        # Set default style
cite config set-format <format>      # Set default output format
cite config reset --confirm          # Reset to defaults
```

Updated existing commands:
- `cite index build` - Now uses configured directories by default (no --directory needed)
- `cite convert` - Now uses configured default style and format (optional args)

### ✅ Default Configuration

When you first run any command, it creates:
```
config/citation_tools/user_config.json
```

With these defaults:
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

## Your Setup: ~/Documents/bibfiles

Perfect! The default configuration already points to `~/Documents/bibfiles`, so you can:

### Option 1: Use the defaults (easiest)

```bash
# Install
pip install -e ./citation_tools

# Just build the index (uses ~/Documents/bibfiles automatically)
cite index build --recursive

# Done! Now use it
cite convert --key YourKey
```

### Option 2: Customize if needed

```bash
# If your path is different
cite config add-bibdir ~/Documents/bibfiles
cite config add-bibdir ~/research/papers  # Add more if needed

# Build index from all configured directories
cite index build --recursive
```

## Example Workflow

```bash
# 1. Install
pip install -e ./citation_tools

# 2. (Optional) Customize configuration
cite config set-style fund-og-forskning
cite config set-format clipboard
cite config show  # Verify

# 3. Build index (uses ~/Documents/bibfiles by default)
cite index build --recursive

# 4. Use it (uses configured defaults)
cite convert --key Kondrup2010
# This uses fund-og-forskning style and clipboard format automatically!

# 5. Or override defaults when needed
cite convert --key Doe2024 --style apa --format docx
```

## Configuration Files Location

### In your monorepo:
```
your-monorepo/
├── config/citation_tools/
│   └── user_config.json          # Your settings
├── .cache/citation_tools/
│   ├── *.csl                      # Downloaded styles
│   └── bibtex_index.json          # BibTeX index
```

### Outside monorepo:
```
~/.config/citation_tools/user_config.json
~/.cache/citation_tools/
```

## Updated Files

1. **NEW:** `user_config.py` - User configuration management
2. **MODIFIED:** `cli.py` - Config commands and default handling
3. **MODIFIED:** `__init__.py` - Exports UserConfig
4. **MODIFIED:** `README.md` - Configuration documentation
5. **MODIFIED:** `INSTALL.md` - Setup with configuration

## Migration for Existing Users

If you already had the tool installed without configuration:

```bash
# Your existing index still works
# Just add configuration for easier usage:
cite config add-bibdir ~/Documents/bibfiles
cite config set-style fund-og-forskning
cite config set-format clipboard

# Now you can use shorter commands:
cite convert --key MyKey
# instead of:
cite convert --key MyKey --style fund-og-forskning --format clipboard
```

All existing commands still work exactly as before!
