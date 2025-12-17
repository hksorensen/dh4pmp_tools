# Changelog

All notable changes to bibfetcher will be documented in this file.

## [0.4.1] - 2024-12-16

### Fixed
- **Progress bar hanging**: Fixed infinite loop where progress bar would get stuck at 99%
  - Issue: `cite index rebuild` outputs a LOT of text, pipe buffers were full
  - `communicate()` was blocking trying to read stdout/stderr
  - Solution: Redirect stdout/stderr to /dev/null instead of capturing them
  - Progress bar now completes properly and shows 100% ✓

## [0.4.0] - 2024-12-16

### Fixed
- **Bibkey generation**: Bibkeys are now always in title case (e.g., `Smith2024a` not `SMITH2024a` or `smith2024a`)
  - Converts ALL CAPS last names: `SMITH` → `Smith`
  - Handles lowercase: `smith` → `Smith`
  - Works because ALL CAPS conversion happens BEFORE bibkey generation

- **'and' stays lowercase**: When converting ALL CAPS author fields, 'and' stays lowercase
  - `JOHN SMITH AND JANE DOE` → `John Smith and Jane Doe`
  - Not `John Smith And Jane Doe`
  - Correct BibTeX/BibLaTeX convention

**Examples:**
```bibtex
# Input from DOI
author = {JOHN SMITH AND JANE DOE}

# After processing
author = {John Smith and Jane Doe}
# Generated key: Smith2024a (not SMITH2024a)
```

## [0.3.9] - 2024-12-16

### Improved
- **Real progress bar**: Shows actual progress with percentage and elapsed time
  - Visual bar: `[████████████░░░░░░] 75% (9.2s)`
  - Updates every 0.1 seconds
  - Estimates ~12 seconds total (0.25s per file × 50 files)
  - Shows actual completion time at end
  - Much better than spinner - you can see how long you have to wait!

### Added
- **ALL CAPS normalization**: Automatically converts ALL CAPS to Title Case
  - Applies to: `author`, `editor`, `title` fields
  - Only converts if >90% of letters are uppercase
  - Preserves LaTeX commands in curly braces

**Examples:**
```bibtex
# Before
author = {JOHN SMITH AND JANE DOE}
title = {A COMPREHENSIVE REVIEW OF MACHINE LEARNING}

# After
author = {John Smith And Jane Doe}
title = {A Comprehensive Review Of Machine Learning}
```

**Progress bar in action:**
```
Rebuilding index [████████████░░░░░░░░░░░░░░░░] 40% (5.1s)
...
Rebuilding index [██████████████████████████████] 100% (12.3s) ✓
```

## [0.3.8] - 2024-12-16

### Improved
- **Animated progress spinner**: Shows spinning animation during index rebuild instead of static text
  - Uses Unicode Braille spinner: ⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏
  - Shows final status with symbols: ✓ (success), ✗ (failed), ⊘ (not found), ⏱ (timeout)
  - Makes 5-15 second wait more pleasant

**What you'll see:**
```
Rebuilding citation_tools index ⠹  (animates while running)
Rebuilding citation_tools index ✓  (when done)
```

## [0.3.7] - 2024-12-16

### Added
- **Progress indicator**: Shows "Rebuilding citation_tools index... done." during index rebuild
  - Helps users know the tool is working (rebuild takes 5-15 seconds)
  - Displays status: done/failed/skipped/timeout/error
  
- **Additional title/subtitle separators**: Now splits titles at multiple separator types (in priority order):
  1. Colon: `Title: subtitle` → `title + subtitle`
  2. Question mark: `Title? subtitle` → `title + subtitle` (keeps `?` in title)
  3. Period + space + capital: `Title. Subtitle` → `title + subtitle`
  4. Triple dash: `Title --- subtitle` → `title + subtitle`

**Examples:**
```bibtex
# Colon
title = {AI in medicine: a review} → title = {AI in medicine}, subtitle = {A review}

# Question mark
title = {Who benefits? An analysis} → title = {Who benefits?}, subtitle = {An analysis}

# Period + space
title = {Introduction. Key concepts} → title = {Introduction}, subtitle = {Key concepts}

# Triple dash
title = {AI ethics --- challenges ahead} → title = {AI ethics}, subtitle = {Challenges ahead}
```

## [0.3.6] - 2024-12-16

### Fixed
- **Index rebuild now works**: Removed `--quiet` flag from `cite index rebuild` command (citation_tools doesn't support this flag yet)
- This fixes duplicate detection - the index is now properly rebuilt before checking for duplicates
- Output is already suppressed via `capture_output=True`, so no verbose output

### Removed
- Cleaned up rogue `{fetchers,utils,pdf}` directory from package

**Important:** This version actually rebuilds the index (v0.3.0-v0.3.5 failed silently). Duplicate detection should now work correctly!

## [0.3.5] - 2024-12-16

### Added
- **Automatic LaTeX formatting**: All text fields are now automatically converted to standard LaTeX format
  - Smart quotes (`'` `'`) → `'` (single quote)
  - En-dash (`–`) → `--` (double dash)
  - Em-dash (`—`) → `---` (triple dash)
  - Curly quotes (`"` `"`) → ` `` ` and `''`
  - Accented characters → LaTeX commands (e.g., `ó` → `{\\'{o}}`)
  - Escapes LaTeX special characters (`#`, `&`, `%`, `$`)
  - Skips URL and DOI fields (keeps them as-is)

This ensures all BibTeX entries use standard LaTeX conventions that compile correctly.

## [0.3.4] - 2024-12-16

### Added
- **Automatic title/subtitle splitting**: If `title` or `booktitle` contains a colon and no `subtitle`/`booksubtitle` exists, automatically splits at first colon
  - Main title stays in `title` field
  - Part after colon moves to `subtitle` field
  - First character of subtitle is capitalized
  - Preserves existing subtitle fields (doesn't overwrite)
  - Future-ready: commented code for " --- " splitting (em dash alternative)

**Example:**
```bibtex
# Before
title = {Machine learning in medicine: a comprehensive review}

# After
title = {Machine learning in medicine}
subtitle = {A comprehensive review}
```

## [0.3.3] - 2024-12-16

### Fixed
- **DOI pattern matching**: Now handles `DOI 10.xxxx` format (without colon) in addition to `doi: 10.xxxx`
- Matches patterns like: `DOI 10.3389/frai.2025.1558696` commonly found in academic papers

## [0.3.2] - 2024-12-16

### Fixed
- **Robust PDF extraction**: Added multiple fallback strategies for PDFs with encoding issues
  - First tries normal extraction
  - Falls back to lenient mode (`strict=False`)
  - Finally tries extracting from first 3 pages
  - Handles corrupted PDFs and non-standard encodings (e.g., LZWDecode errors)

## [0.3.1] - 2024-12-16

### Added
- **Automatic .pdf extension**: If a file doesn't exist, bibfetcher now tries adding `.pdf` automatically
  - Example: `bibfetch myfile` will try `myfile.pdf` if `myfile` doesn't exist
  - Works from both command line AND clipboard input
  - Makes it easier to reference PDFs without typing the extension

## [0.3.0] - 2024-12-16

### Changed
- **Automatic index rebuild before duplicate check**: Now runs `cite index rebuild --quiet` before checking for duplicates
- This ensures the citation_tools index is always up-to-date, catching entries added by any method (manual edits, other tools, etc.)
- Rebuild is quiet by default (only shows errors in verbose mode)

### Why This Change
Previous approach relied on citation_tools having the correct configuration and files indexed. This was fragile and required manual synchronization. Now bibfetcher ensures the index is fresh on every run, making duplicate detection reliable regardless of how entries were added.

## [0.2.3] - 2024-12-16

### Fixed
- **Correct citation_tools command**: Now calls `cite index add-file` instead of `citation_tools index update` (which doesn't exist)
- This was preventing the index from being updated automatically after appending entries

## [0.2.2] - 2024-12-15

### Fixed
- **Index reload after append**: After appending to a file and updating citation_tools index, the index is now reloaded so duplicate detection works immediately for the same DOI in the same session

## [0.2.1] - 2024-12-15

### Changed
- **Default to "yes" for append prompt**: Now `[Y/n]` instead of `[y/N]` - just press Enter to append
- **Month field normalized to numeric**: Converts "January"/"jan" → "1", etc. automatically
- **Config shows append target**: `bibfetch config show` now displays the full path where entries will be appended

### Added
- Month normalization hook in post-processor (converts month names to numbers)
- Clearer configuration display showing bibliography filename and append target

## [0.2.0] - 2024-12-15

### Added
- **Interactive file append workflow**: After fetching, prompts whether to append to bibliography file
  - If yes: appends entry to file, updates citation_tools index, copies key only to clipboard
  - If no: copies full BibTeX to clipboard (previous behavior)
- **Automatic citation_tools index updates**: When appending to file, automatically runs `citation_tools index update`
- **Improved duplicate detection**: 
  - Shows existing key and file location
  - Copies key to clipboard (no need to re-fetch)
  - Exits with success code (not an error)
- **Version flag**: `bibfetch --version` now works
- **Better PDF DOI extraction**:
  - Handles spaces inserted by PDF extraction (e.g., "10. 1234 /example")
  - More robust pattern matching with 15 test cases
  - Stops at appropriate boundaries (punctuation, spaces + lowercase words)
  - Handles periods within DOI suffixes
- **Configuration options**:
  - `bibliography_filename`: Which .bib file to append to (default: references.bib)
- **Non-interactive mode**: `bibfetch -n` or `--no-interactive` skips prompts
- **Test suite**: Added `tests/test_doi_extraction.py` with comprehensive DOI extraction tests
- **Documentation**: Added `FUTURE_ENHANCEMENTS.md` with ideas for future versions

### Changed
- Duplicate detection now exits with code 0 (success) instead of 1 (error)
- BibTeX entries are printed to stdout before the interactive prompt
- Improved CLI help text and examples
- Better error messages for configuration issues

### Fixed
- PDF extraction now correctly handles DOIs with spaces from PyPDF2
- DOI pattern matching no longer stops prematurely on:
  - All-caps words (e.g., ARXIV)
  - Periods within DOI suffix (e.g., 10.1234/example.test)
  - Letters in DOI suffix (e.g., 10.1007/s11192-024-05217-7)
- Parentheses now correctly terminate DOI matching

### Technical
- Return signature changed: `fetch()` now returns `(key, bibtex, is_duplicate)` tuple
- Added subprocess integration for citation_tools index updates
- Improved pattern matching with lookahead assertions

## [0.1.1] - 2024-12-14

### Added
- Post-processing system with hooks
- Automatic arXiv field handling (eprinttype, eprint)
- Automatic field cleanup (removes publisher/issn from articles, url when doi present)

### Fixed
- CLI now accepts both `bibfetch 10.1234/example` and `bibfetch fetch 10.1234/example`

## [0.1.0] - 2024-12-13

### Added
- Initial release
- DOI, ISBN, arXiv ID, and PDF file support
- Automatic input type detection
- Citation key generation with uniqueness checking
- Integration with citation_tools index (read-only)
- Clipboard integration
- Crossref and DOI resolver fetchers
- Configurable bibliography directories
- Cache system
- Monorepo-aware configuration
