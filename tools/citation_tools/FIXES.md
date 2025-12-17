# Version Updates - Three Major Fixes

## Issues Fixed

### 1. Removed --key Requirement
- Old: `cite convert --key Lin2014a`
- New: `cite convert Lin2014a` (positional argument)

### 2. Non-Standard Entry Types Supported
- Now accepts @online, @software, @dataset, etc.
- No more "Entry type X not standard" warnings

### 3. Exclude Files from Indexing
```bash
cite config exclude-file "*.backup.bib"
cite config exclude-file "temp_*.bib"
cite config show
cite index rebuild
```

See USAGE.md for complete details.
