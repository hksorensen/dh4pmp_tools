# Citation Tools - Quick Usage Guide

## ✨ New Simplified Syntax

### Convert by Citation Key (Most Common)

```bash
# NEW: Just the key as a positional argument!
cite convert Lin2014a

# OLD way (still works):
cite convert --key Lin2014a
```

### Other Input Methods

```bash
# From BibTeX string
cite convert --bibtex '@article{Doe2024, title={My Paper}, ...}'

# From file
cite convert --file my-references.bib
```

## 🎯 Complete Examples

```bash
# Default output (uses your config: fund-og-forskning + clipboard)
cite convert Kondrup2010

# Override style
cite convert Kondrup2010 --style apa

# Override format
cite convert Kondrup2010 --format docx

# Override both
cite convert Kondrup2010 --style chicago-note-bibliography --format html

# Show in terminal (plain text)
cite convert Kondrup2010 --format plain
```

## 🔍 Finding Citations

```bash
# Search for a key by pattern
cite index search "Kondrup"

# Lookup by DOI
cite index lookup-doi 10.1007/s11192-024-05217-7

# Lookup by arXiv ID
cite index lookup-arxiv 1405.0312

# Find all from a year
cite index search-year 2024

# Show full BibTeX entry
cite index show Kondrup2010
```

## ⚙️ Configuration

```bash
# View current settings
cite config show

# Set defaults (then you never need --style or --format!)
cite config set-style fund-og-forskning
cite config set-format clipboard

# Add bibliography directories
cite config add-bibdir ~/Documents/bibfiles
cite config add-bibdir ~/research/papers
```

## 📊 Index Management

```bash
# Auto-built on first use, but you can also:
cite index build --recursive           # Build from config directories
cite index rebuild                     # Force rebuild
cite index info                        # Show statistics
```

## 🚀 Daily Workflow

```bash
# 1. Find what you need (optional)
cite index search "neural"

# 2. Convert!
cite convert Smith2024a

# 3. Paste into Word with Ctrl+V
# Done! Citation is perfectly formatted with italics.
```

## 💡 Pro Tips

1. **Set your defaults once:**
   ```bash
   cite config set-style fund-og-forskning
   cite config set-format clipboard
   ```
   Then just: `cite convert MyKey` - uses your defaults!

2. **Quick lookup:**
   ```bash
   cite index lookup-doi 10.1007/...
   # Output: DOI 10.1007/... → Arhiliuc2024a
   
   cite convert Arhiliuc2024a
   ```

3. **Check before converting:**
   ```bash
   cite index show Lin2014a
   # Shows full BibTeX entry to verify it's the right one
   ```

4. **Search patterns work:**
   ```bash
   cite index search "2024"        # All 2024 entries
   cite index search "machine"     # All with "machine" in key
   ```

## 📝 Output Format Examples

```bash
# Plain text (console output)
cite convert Doe2024 --format plain

# Markdown (for markdown docs)
cite convert Doe2024 --format markdown

# HTML (for web)
cite convert Doe2024 --format html

# RTF (preserves italics)
cite convert Doe2024 --format rtf

# Word document
cite convert Doe2024 --format docx

# Clipboard (best for Word - preserves formatting!)
cite convert Doe2024 --format clipboard
```

## 🎨 Style Examples

```bash
# Danish humanities style (default for Henrik)
cite convert Kondrup2010 --style fund-og-forskning

# Chicago notes
cite convert Kondrup2010 --style chicago-note-bibliography

# Chicago author-date
cite convert Kondrup2010 --style chicago-author-date

# APA
cite convert Kondrup2010 --style apa
```

## 🔧 Troubleshooting

```bash
# Key not found?
cite index search "partial-key-name"
cite index info    # Check if index is populated

# Need to rebuild?
cite index rebuild

# Check config?
cite config show
```

That's it! The most common command is simply:
```bash
cite convert YourKey
```

Everything else is already configured! 🎉
