# Working with Claude on dh4pmp

This file documents the workflow for collaborating with Claude (Anthropic's AI assistant) on this repository.

## Quick Start for Claude

**Always start coding sessions by running:**
```
web_fetch https://raw.githubusercontent.com/hksorensen/dh4pmp_tools/main/CLAUDE_WORKFLOW.md
```

Then check the relevant tool directory for current version.

## Repository Information

- **GitHub**: https://github.com/hksorensen/dh4pmp_tools
- **Type**: Public repository (tools and packages only)
- **Owner**: Henrik Kragh Sørensen (@hksorensen)
- **Purpose**: Reusable research tools for digital humanities
- **Main Language**: Python 3.8+

**Note**: This is the public tools repository. Research-specific work is maintained in a separate private repository.

## Current Projects

### Tools (`/tools/`)
Command-line utilities for research workflows:

#### bibfetcher
- **Location**: `/tools/bibfetcher/`
- **Current Version**: Check `bibfetcher/__init__.py`
- **Purpose**: Fetch bibliographic metadata from DOI, ISBN, arXiv, or PDF files
- **Key Features**: 
  - Auto-append to bibliography files
  - Duplicate detection via citation_tools index
  - LaTeX normalization
  - Title/subtitle splitting
  - Progress bars for index rebuilding

#### citation_tools
- **Location**: `/tools/citation_tools/`
- **Current Version**: Check `citation_tools/__init__.py`
- **Purpose**: Bibliography management and citation formatting
- **CLI Command**: `cite`
- **Key Features**:
  - BibTeX index management
  - CSL style handling
  - Danish humanities citation formatting
  - Search and lookup functions

### Packages (`/packages/`)
Python libraries and utilities:

#### api_clients
- **Location**: `/packages/api_clients/`
- **Purpose**: Client libraries for various APIs
- **Examples**: Anthropic, OpenAI, etc.

#### arxiv_metadata
- **Location**: `/packages/arxiv_metadata/`
- **Purpose**: Fetch and process arXiv paper metadata

#### caching
- **Location**: `/packages/caching/`
- **Purpose**: Caching utilities and helpers

#### web_fetcher
- **Location**: `/packages/web_fetcher/`
- **Purpose**: Web content fetching utilities

*Note: Check each directory's README.md for detailed documentation.*

## Workflow for Claude Sessions

### 1. Session Start
```markdown
1. Fetch this file: https://raw.githubusercontent.com/hksorensen/dh4pmp_tools/main/CLAUDE_WORKFLOW.md
2. Check relevant tool/package's current version
3. Ask Henrik: "Have you pushed your latest changes to GitHub?"
4. If yes: Fetch latest from GitHub to work from
5. If no: Remind to push, or work from provided files
```

### 2. During Development
- Work in `/tmp/` or Claude's workspace
- Create tarballs for distribution
- Keep version numbers in sync (pyproject.toml + __init__.py)
- Update CHANGELOG.md with changes
- Follow semantic versioning (MAJOR.MINOR.PATCH)

### 3. Testing & Installation
Henrik tests locally:
```bash
cd <local_workspace>/dh4pmp_tools/tools  # or /packages
rm -rf <project_name>/
tar -xzf ~/Downloads/<project_name>.tar.gz
pip install -e ./<project_name> --force-reinstall

# Or for packages that don't need installation:
# Just extract and use directly
```

### 4. Committing Changes
When satisfied, Henrik:
```bash
git add tools/<project_name>/  # or packages/<project_name>/
git commit -m "<project_name>: <description of changes>"
git push
```

## File Locations

### Configuration
- `~/.config/bibfetcher/` - bibfetcher user config
- `~/.config/citation_tools/` - citation_tools config  
- `~/.cache/citation_tools/bibtex_index.json` - shared bibliography index

### Bibliography Files
- User-specific locations (typically `~/Documents/bibfiles/` or similar)
- Configurable via tool settings

## Important Context

### Henrik's Preferences
- **Clean, documented code**: Comprehensive docstrings
- **Type hints**: Use typing annotations
- **Modular design**: Reusable components
- **Good UX**: Progress indicators, clear error messages
- **Standard LaTeX**: Convert Unicode → LaTeX commands
- **Local processing**: Prefer local over cloud when possible

### Bibliography Standards
- BibTeX/BibLaTeX format
- Danish humanities citations (Fund og Forskning style)
- Title case for author names (not ALL CAPS)
- Lowercase "and" between authors
- Automatic title/subtitle splitting

## Version History

### Checking Current Versions
Each project maintains its version in `__init__.py`:
- Tools: `tools/<tool_name>/<tool_name>/__init__.py`
- Packages: `packages/<package_name>/<package_name>/__init__.py`

Or check `pyproject.toml` in each project root.

### Recent Major Changes
- **bibfetcher v0.4.x**: Progress bars, ALL CAPS normalization, multiple title/subtitle separators
- **citation_tools**: Check CHANGELOG.md in project directory
- **Other projects**: See individual CHANGELOG.md or git history

## TODO Lists & Future Work
Check individual projects for planned improvements:
- `tools/bibfetcher/FUTURE_ENHANCEMENTS.md` - Planned bibfetcher features
- `tools/citation_tools/TODO.md` - Citation_tools improvements  
- Other projects may have TODO.md, ROADMAP.md, or issues documented in their README.md

Check these for context on planned work before starting new features.

## Debugging Tips

### Common Issues
1. **Index out of sync**: Delete `~/.cache/citation_tools/bibtex_index.json`, rebuild
2. **Duplicate detection not working**: Ensure only one index file (not both monorepo + home)
3. **Progress bar hanging**: Check for pipe buffer issues with subprocess
4. **Import errors**: Verify installation with `pip show bibfetcher`

### Testing
```bash
# Check version
bibfetch --version

# Test with known DOI
bibfetch 10.1234/example

# Verbose mode for debugging
bibfetch -v <identifier>
```

## Questions?

Ask Henrik! He's responsive and helpful. Key things he cares about:
- Code quality and documentation
- User experience (progress, feedback)
- Integration between tools
- Standards compliance (LaTeX, BibTeX)

---

**Last Updated**: 2024-12-16
**Claude Version Used**: Claude Sonnet 4.5
