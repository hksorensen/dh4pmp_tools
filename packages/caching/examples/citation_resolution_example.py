"""
Example: Using StringCache for LLM-based citation resolution.

StringCache is perfect for tracking citation resolution status:
- pending: Citation needs resolution
- completed: Citation successfully resolved
- failed: Resolution failed (after retries)

This allows resuming interrupted batch processing.
"""

from caching import StringCache
import json

# ============================================================================
# Setup StringCache for Citation Resolution
# ============================================================================

# Create cache for tracking citation resolution status
citation_cache = StringCache(
    cache_file="citation_resolution.json",
    # Or let it use default: get_cache_dir() / "string_cache.json"
)

# ============================================================================
# Workflow 1: Track Resolution Status
# ============================================================================

# List of citations to resolve
citations = [
    "Smith, J. (2020). Machine Learning. Nature, 123, 45-67.",
    "Jones, A. et al. Deep Learning. Science 2021.",
    "Wang, L. (2019). Neural Networks. arXiv:1234.5678",
]

print("="*60)
print("Workflow 1: Track Resolution Status")
print("="*60)

# Mark citations as pending
for citation in citations:
    citation_cache.set_pending(citation)
    print(f"Pending: {citation}")

# Simulate resolution process
for citation in citations:
    status = citation_cache.get_status(citation)
    
    if status == "pending":
        try:
            # Call your LLM here to resolve citation
            # resolved = resolve_citation_with_llm(citation)
            
            # Mark as completed
            citation_cache.set_completed(citation)
            print(f"✓ Resolved: {citation}")
            
        except Exception as e:
            # Mark as failed
            citation_cache.set_failed(citation)
            print(f"✗ Failed: {citation}")

# Show final status
print("\nFinal Status:")
print(f"  Pending: {len(citation_cache.get_pending())}")
print(f"  Completed: {len(citation_cache.get_completed())}")
print(f"  Failed: {len(citation_cache.get_failed())}")

# ============================================================================
# Workflow 2: Resume Interrupted Processing
# ============================================================================

print("\n" + "="*60)
print("Workflow 2: Resume Interrupted Processing")
print("="*60)

# Clear cache for demo
citation_cache.clear()

# Simulate interrupted batch processing
batch = [f"Citation {i}" for i in range(100)]

# Process first 50, then "crash"
for i, citation in enumerate(batch[:50]):
    citation_cache.set_pending(citation)
    # Simulate processing...
    citation_cache.set_completed(citation)
    
print(f"Processed 50 citations, then crashed!")
print(f"Completed: {len(citation_cache.get_completed())}")

# Resume processing
print("\nResuming...")
remaining = batch[50:]
for citation in remaining:
    if citation_cache.get_status(citation) is None:  # Not processed yet
        citation_cache.set_pending(citation)
        # Process...
        citation_cache.set_completed(citation)

print(f"Completed: {len(citation_cache.get_completed())}")

# ============================================================================
# Workflow 3: Combine with Result Cache
# ============================================================================

print("\n" + "="*60)
print("Workflow 3: Status + Results (Two-Cache Pattern)")
print("="*60)

# Status cache: tracks what needs doing
status_cache = StringCache(cache_file="citation_status.json")

# Result cache: stores actual resolved citations (use JSON or LocalCache)
import json
from pathlib import Path

results_cache_file = Path("citation_results.json")

def save_result(citation_string, resolved_data):
    """Save resolved citation data."""
    if results_cache_file.exists():
        results = json.loads(results_cache_file.read_text())
    else:
        results = {}
    
    results[citation_string] = resolved_data
    results_cache_file.write_text(json.dumps(results, indent=2))

def get_result(citation_string):
    """Get resolved citation data."""
    if results_cache_file.exists():
        results = json.loads(results_cache_file.read_text())
        return results.get(citation_string)
    return None

# Example usage
citation = "Smith, J. (2020). AI. Nature."

# Check status
status = status_cache.get_status(citation)

if status == "completed":
    # Get from result cache
    result = get_result(citation)
    print(f"Already resolved: {result}")
    
elif status == "failed":
    print(f"Previously failed, skipping")
    
else:  # None or "pending"
    status_cache.set_pending(citation)
    
    try:
        # Resolve with LLM
        # resolved = resolve_citation_with_llm(citation)
        resolved = {
            "authors": ["Smith, J."],
            "year": 2020,
            "title": "AI",
            "journal": "Nature"
        }
        
        # Save result
        save_result(citation, resolved)
        
        # Mark as completed
        status_cache.set_completed(citation)
        print(f"✓ Resolved and cached: {citation}")
        
    except Exception as e:
        status_cache.set_failed(citation)
        print(f"✗ Failed: {citation}")

# ============================================================================
# Workflow 4: Integration with LLM Resolution
# ============================================================================

print("\n" + "="*60)
print("Workflow 4: Complete LLM Integration Pattern")
print("="*60)

class CitationResolver:
    """LLM-based citation resolver with caching."""
    
    def __init__(self, cache_dir=None):
        self.status_cache = StringCache(
            cache_file="citation_status.json" if not cache_dir 
            else Path(cache_dir) / "citation_status.json"
        )
        
        self.results_file = (
            Path("citation_results.json") if not cache_dir
            else Path(cache_dir) / "citation_results.json"
        )
        
        # Initialize results file if needed
        if not self.results_file.exists():
            self.results_file.write_text("{}")
    
    def resolve(self, citation_string, skip_failed=True):
        """Resolve a citation, using cache if available."""
        
        # Check status
        status = self.status_cache.get_status(citation_string)
        
        if status == "completed":
            return self._get_result(citation_string)
        
        if status == "failed" and skip_failed:
            return None
        
        # Mark as pending
        self.status_cache.set_pending(citation_string)
        
        try:
            # Call LLM to resolve
            # In real code, call your LLM function here:
            # resolved = call_llm_to_parse_citation(citation_string)
            
            resolved = {
                "citation_string": citation_string,
                "parsed": True
            }
            
            # Save result
            self._save_result(citation_string, resolved)
            
            # Mark as completed
            self.status_cache.set_completed(citation_string)
            
            return resolved
            
        except Exception as e:
            # Mark as failed
            self.status_cache.set_failed(citation_string)
            return None
    
    def resolve_batch(self, citations):
        """Resolve multiple citations."""
        results = []
        
        for citation in citations:
            result = self.resolve(citation)
            results.append(result)
        
        return results
    
    def _save_result(self, citation_string, data):
        """Save resolved citation."""
        results = json.loads(self.results_file.read_text())
        results[citation_string] = data
        self.results_file.write_text(json.dumps(results, indent=2))
    
    def _get_result(self, citation_string):
        """Get cached result."""
        results = json.loads(self.results_file.read_text())
        return results.get(citation_string)
    
    def get_statistics(self):
        """Get resolution statistics."""
        return {
            "pending": len(self.status_cache.get_pending()),
            "completed": len(self.status_cache.get_completed()),
            "failed": len(self.status_cache.get_failed())
        }

# Example usage
resolver = CitationResolver()

citations = [
    "Smith, J. (2020). AI. Nature.",
    "Jones, A. (2021). ML. Science."
]

# Resolve citations
for citation in citations:
    result = resolver.resolve(citation)
    if result:
        print(f"✓ Resolved: {citation}")
    else:
        print(f"✗ Failed: {citation}")

# Show statistics
stats = resolver.get_statistics()
print(f"\nStatistics:")
print(f"  Completed: {stats['completed']}")
print(f"  Failed: {stats['failed']}")
print(f"  Pending: {stats['pending']}")

print("\n" + "="*60)
print("StringCache is perfect for citation resolution!")
print("="*60)
print("""
Key benefits:
1. Track status: pending/completed/failed
2. Resume interrupted processing
3. Skip already-processed citations
4. Separate status tracking from results storage
5. Simple JSON-based persistence
""")
