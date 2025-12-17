# StringCache Integration for Citation Resolution

Quick guide for adding StringCache to your LLM citation resolution package.

## Minimal Setup

### 1. Add StringCache to Your Package

```python
# In your citation resolver module
from caching import StringCache

class CitationResolver:
    def __init__(self):
        # Create status cache
        self.status = StringCache(cache_file="citations.json")
    
    def resolve(self, citation_string):
        # Check if already processed
        status = self.status.get_status(citation_string)
        
        if status == "completed":
            return self.get_cached_result(citation_string)
        
        if status == "failed":
            return None  # Skip previously failed
        
        # Mark as pending
        self.status.set_pending(citation_string)
        
        try:
            # Call your LLM
            result = self.call_llm(citation_string)
            
            # Save result somewhere
            self.save_result(citation_string, result)
            
            # Mark as completed
            self.status.set_completed(citation_string)
            
            return result
            
        except Exception as e:
            # Mark as failed
            self.status.set_failed(citation_string)
            return None
```

## What I Need From You

To give you specific integration code, please tell me:

### 1. Where is your code?
```bash
# Is it in research/?
research/citation_resolver/

# Or should we create a new package?
packages/citation_resolver/
```

### 2. What does your current code look like?
```python
# Show me your current citation resolution function
def resolve_citation(citation_string):
    # What does this look like?
    pass
```

### 3. What are you caching?

**Option A: Just track status**
```python
# Use StringCache for status only
status_cache = StringCache()
status_cache.set_completed(citation)
```

**Option B: Status + Results**
```python
# StringCache for status
status = StringCache(cache_file="status.json")

# Separate storage for results
results = {}  # Or JSON file, or LocalCache
```

### 4. What's your LLM setup?
```python
# Ollama?
import ollama
response = ollama.chat(...)

# Anthropic API?
import anthropic
response = client.messages.create(...)

# Both?
```

## Quick Integration Steps

### Step 1: Install caching package
```bash
cd packages/caching
pip install -e .
```

### Step 2: Import StringCache
```python
from caching import StringCache
```

### Step 3: Add to your resolver
```python
def __init__(self):
    self.cache = StringCache()
```

### Step 4: Check before processing
```python
if self.cache.get_status(citation) == "completed":
    return cached_result
```

### Step 5: Mark after processing
```python
self.cache.set_completed(citation)
```

## Example File Structure

If creating a new package:

```
packages/citation_resolver/
├── citation_resolver/
│   ├── __init__.py
│   ├── resolver.py          # Your main code
│   └── llm_backend.py       # LLM calls
├── setup.py
├── README.md
└── examples/
    └── basic_usage.py
```

In `resolver.py`:
```python
from caching import StringCache

class CitationResolver:
    def __init__(self, cache_dir=None):
        self.status_cache = StringCache(
            cache_file="citations.json" if not cache_dir
            else Path(cache_dir) / "citations.json"
        )
    
    # ... rest of your code
```

## Tell Me More!

Please share:
1. Path to your existing code (or say "I don't have it yet")
2. Which LLM backend you're using
3. What your input/output looks like
4. Where you want the cache files stored

Then I can give you exact integration code!
