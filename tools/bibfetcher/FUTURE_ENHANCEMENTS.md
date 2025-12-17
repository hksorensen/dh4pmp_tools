# Future Enhancements for bibfetcher

## 1. DOI Validation via API (Instead of Pattern Matching)

### Problem
Current approach uses regex patterns to extract DOIs from PDF text. This is fragile because:
- PDF extraction inserts random spaces
- Pattern must balance inclusiveness vs. precision
- Edge cases are hard to predict

### Proposed Solution
**Validate DOIs by actually resolving them:**

```python
def extract_doi_by_validation(text: str) -> Optional[str]:
    """
    Extract DOI by progressive validation against DOI resolver.
    
    Algorithm:
    1. Find DOI prefix: 10.xxxxx (digits after 10.)
    2. Find suffix start: first / after prefix
    3. Progressively build suffix, checking each version:
       - Start: "10.1234/"
       - Try: "10.1234/a" → validate
       - Try: "10.1234/ab" → validate
       - Try: "10.1234/abc" → validate
       - Continue until:
         * Get 200 response → DOI is valid!
         * Hit character limit (e.g., 100 chars)
         * Hit obvious stop (comma, semicolon, etc.)
    
    Returns:
        Validated DOI string
    """
    import requests
    
    # Extract prefix
    prefix_match = re.search(r'10\.[\d\s]+/', text)
    if not prefix_match:
        return None
    
    prefix = re.sub(r'\s+', '', prefix_match.group(0))  # "10.1234/"
    
    # Find starting position of suffix
    start_pos = prefix_match.end()
    
    # Build suffix progressively
    max_length = 100  # Safety limit
    last_valid = None
    
    for length in range(1, max_length):
        # Extract candidate suffix
        candidate_suffix = text[start_pos:start_pos + length]
        
        # Stop at obvious delimiters
        if any(char in candidate_suffix for char in [',', ';', '\n\n']):
            break
        
        # Clean spaces
        clean_suffix = re.sub(r'\s+', '', candidate_suffix)
        candidate_doi = prefix + clean_suffix
        
        # Validate by resolving
        try:
            response = requests.head(
                f"https://doi.org/{candidate_doi}",
                timeout=1,
                allow_redirects=True
            )
            if response.status_code == 200:
                last_valid = candidate_doi
                # Continue to find longest valid DOI
        except:
            pass
    
    return last_valid
```

### Advantages
- **Robust**: Doesn't depend on pattern matching
- **Accurate**: Only returns DOIs that actually resolve
- **Handles spaces**: Automatically removes them during validation
- **Self-correcting**: Finds the longest valid DOI

### Disadvantages
- **Slower**: Makes multiple HTTP requests (can be 20-50 requests per PDF)
- **Network dependent**: Requires internet connection
- **Rate limiting**: Could hit DOI resolver rate limits

### Implementation Strategy
1. **Hybrid approach**: Try pattern matching first (fast), fall back to validation if uncertain
2. **Caching**: Cache validation results to avoid repeated requests
3. **Batch mode**: For processing many PDFs, use pattern matching only
4. **Configuration**: Let users choose approach via config

### When to Implement
- After initial release is stable
- When we see pattern matching failing frequently
- If users request it

### Estimated Effort
- 2-3 hours to implement
- 1-2 hours for testing with various PDFs
- May need throttling/rate limiting

---

## 2. Other Future Enhancements

### JSTOR Link Support
- Add JSTOR URL detection: `https://www.jstor.org/stable/12345678`
- Extract DOI from JSTOR page metadata
- Add `InputType.JSTOR_LINK`
- Fetch DOI from `<meta name="citation_doi">` tags

**Example workflow:**
```bash
bibfetch https://www.jstor.org/stable/12345678
# → Fetches JSTOR page HTML
# → Extracts DOI from meta tags: 10.2307/12345678
# → Proceeds with normal DOI fetch
```

**Implementation:**
```python
def fetch_doi_from_jstor(jstor_url: str) -> str:
    import requests
    response = requests.get(jstor_url)
    
    # Look for DOI in meta tags
    match = re.search(r'<meta name="citation_doi" content="([^"]+)"', response.text)
    if match:
        return match.group(1)
    
    raise ValueError("Could not find DOI on JSTOR page")
```

**Notes:**
- Some JSTOR pages require authentication
- Should handle gracefully with clear error message
- Could be expanded to other repositories (ERIC, ProQuest, etc.)

### Scopus Integration
- Add `ScopusFetcher` class
- Fetch additional metadata
- Better book chapter handling

### macOS Preview Integration
- Detect PDF open in Preview.app
- Auto-fetch without specifying filename

### Book Chapter Auto-Fetch
- Detect @incollection entries
- Automatically fetch parent book via ISBN
- Create both entries with crossref

### Smart Bibfile Suggestions
- Analyze existing .bib files
- Suggest appropriate file based on topic/journal
- Learn from user choices

### Citation Key Customization
- Allow custom key formats
- User-defined patterns
- Per-project key styles
