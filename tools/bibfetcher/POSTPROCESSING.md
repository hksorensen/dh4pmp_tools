# Custom Entry Post-Processing Hooks

This file documents how to add custom post-processing hooks to bibfetcher.

## Built-in Post-Processing

bibfetcher automatically applies these post-processors:

### 1. arXiv Entry Processing

For entries with arXiv DOIs (format: `10.48550/ARXIV.YYMM.NNNNN`):
- Adds `eprinttype = {arxiv}`
- Adds `eprint = {YYMM.NNNNN}` (extracted from DOI)
- Removes `copyright`, `keywords`, `publisher` fields

### 2. General Cleanup

- Removes `publisher` and `issn` from `@article` entries
- Removes `url` if `doi` is present (DOI is preferred)

## Adding Custom Hooks

### Method 1: Python API

```python
from bibfetcher import get_processor

# Get the global processor
processor = get_processor()

# Add a custom hook
def my_custom_hook(entry):
    """Add a custom field to all entries."""
    if entry.get('ENTRYTYPE') == 'article':
        entry['note'] = 'From bibfetcher'
    return entry

processor.register_hook(my_custom_hook)

# Now all entries will be processed with your hook
from bibfetcher import BibFetcher
fetcher = BibFetcher()
fetcher.fetch('10.1234/example')
```

### Method 2: Configuration File (Future)

In `config/bibfetcher/hooks.py`:

```python
def custom_journal_abbreviations(entry):
    """Replace journal names with abbreviations."""
    abbrevs = {
        'Physical Review Letters': 'Phys. Rev. Lett.',
        'Nature Communications': 'Nat. Commun.',
    }
    
    journal = entry.get('journal')
    if journal in abbrevs:
        entry['journal'] = abbrevs[journal]
    
    return entry

# This will be auto-loaded (future feature)
HOOKS = [custom_journal_abbreviations]
```

## Common Use Cases

### Remove Specific Fields

```python
def remove_abstract(entry):
    """Remove abstract field (often too long)."""
    entry.pop('abstract', None)
    return entry

processor.register_hook(remove_abstract)
```

### Add Custom Fields Based on Journal

```python
def tag_by_journal(entry):
    """Add tags based on journal."""
    journal = entry.get('journal', '').lower()
    
    if 'nature' in journal:
        entry['keywords'] = 'high-impact'
    elif 'arxiv' in journal:
        entry['keywords'] = 'preprint'
    
    return entry

processor.register_hook(tag_by_journal)
```

### Normalize Page Numbers

```python
def normalize_pages(entry):
    """Convert page format: 123-456 -> 123--456."""
    if 'pages' in entry:
        pages = entry['pages']
        # Replace single dash with double dash
        if '-' in pages and '--' not in pages:
            entry['pages'] = pages.replace('-', '--')
    return entry

processor.register_hook(normalize_pages)
```

### Add File Field for PDF Tracking

```python
def add_pdf_field(entry):
    """Add file field pointing to expected PDF location."""
    bibkey = entry.get('ID')
    if bibkey:
        entry['file'] = f':{bibkey}.pdf:PDF'
    return entry

processor.register_hook(add_pdf_field)
```

## Hook Function Signature

All hooks must follow this signature:

```python
def my_hook(entry: Dict) -> Dict:
    """Process a BibTeX entry.
    
    Args:
        entry: BibTeX entry dictionary with fields:
               - ID: citation key
               - ENTRYTYPE: article, book, etc.
               - author, title, year, etc.
    
    Returns:
        Modified entry dictionary
    """
    # Your processing here
    return entry
```

## Execution Order

Hooks are executed in registration order:

1. `process_arxiv_entries` (built-in)
2. `clean_unwanted_fields` (built-in)
3. Your custom hooks (in order registered)

## Disabling Built-in Hooks

If you want to start fresh:

```python
from bibfetcher.postprocessor import EntryProcessor

# Create a new processor without default hooks
processor = EntryProcessor()
processor.hooks = []  # Clear default hooks

# Add only your custom hooks
processor.register_hook(my_custom_hook)

# Use it
from bibfetcher import BibFetcher
fetcher = BibFetcher()
fetcher.processor = processor  # Replace default processor
```

## Examples from Your Workflow

### Your arXiv Processing (Already Built-in!)

```python
# This is already done automatically!
# For DOI: 10.48550/ARXIV.2404.12345
# 
# Automatically adds:
# eprinttype = {arxiv}
# eprint = {2404.12345}
#
# Automatically removes:
# copyright, keywords, publisher
```

### Additional Custom Processing

If you need more customization beyond the defaults:

```python
def my_arxiv_tweaks(entry):
    """Additional arXiv customization."""
    if entry.get('eprinttype') == 'arxiv':
        # Add primaryClass if missing
        if 'primaryclass' not in entry:
            entry['primaryclass'] = 'cs.AI'  # or extract from somewhere
        
        # Capitalize arXiv -> arXiv
        if 'journal' in entry and entry['journal'].lower() == 'arxiv':
            entry['journal'] = 'arXiv'
    
    return entry

processor.register_hook(my_arxiv_tweaks)
```

## Testing Your Hooks

```python
# Test a hook with a sample entry
sample_entry = {
    'ID': 'Test2024a',
    'ENTRYTYPE': 'article',
    'doi': '10.48550/ARXIV.2404.12345',
    'author': 'Test Author',
    'title': 'Test Title',
    'year': '2024',
    'keywords': 'should be removed',
    'copyright': 'should be removed',
}

from bibfetcher.postprocessor import process_entry
result = process_entry(sample_entry)

print(result)
# Should have: eprinttype, eprint
# Should NOT have: keywords, copyright
```
