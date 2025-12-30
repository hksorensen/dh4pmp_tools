# BibTeX Utils

Utilities for working with BibTeX entries.

## Installation

```bash
pip install -e /path/to/dh4pmp_tools/packages/bibtex_utils

# Also requires pandoc
brew install pandoc
```

## Usage

### Format citations from BibTeX

```python
from bibtex_utils import format_citation

# From DOI
citation = format_citation('10.1007/s10623-024-01403-z', style='apa')
print(citation)

# From BibTeX string
bibtex = "@article{sorensen2024, ...}"
citation = format_citation(bibtex, style='chicago')
```

### Batch formatting

```python
from bibtex_utils import CitationFormatter

formatter = CitationFormatter(csl_style='apa')
citations = formatter.format_batch([bibtex1, bibtex2, bibtex3])
```

### Available citation styles

- `apa` - American Psychological Association
- `chicago` - Chicago Manual of Style
- `ieee` - IEEE
- `nature` - Nature
- `science` - Science
- `vancouver` - Vancouver
- `harvard` - Harvard
- `mla` - Modern Language Association
- `acm` - ACM

## Features

- ✅ Format BibTeX as full citations using pandoc
- ✅ Support for multiple citation styles (CSL)
- ✅ Batch processing
- ✅ Direct DOI-to-citation conversion
