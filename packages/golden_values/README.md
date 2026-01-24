# Golden Values

Track and validate key statistics against golden reference values for reproducibility in data pipelines and scientific computing.

## Purpose

When running data pipelines or generating scientific results, it's critical to know when computed values change. Golden Values helps you:

1. **Track important metrics** - Record key statistics during pipeline execution
2. **Validate against references** - Compare new runs against validated "golden" values
3. **Catch silent regressions** - Get alerted when values change unexpectedly
4. **Enable reproducibility** - Version control your golden values for scientific rigor

This is especially valuable when exporting values to papers/reports - you'll know immediately if a code change affected your published numbers.

## Installation

```bash
cd packages/golden_values
pip install -e .
```

## Quick Start

```python
from golden_values import GoldenValues

# Validation mode (normal pipeline runs)
golden = GoldenValues("golden_values.yaml")

# Check exact values
golden.check("papers_downloaded", 8523)
golden.check("papers_with_doi", 8234)

# Check with tolerance for floats
golden.check("avg_diagrams_per_paper", 1.45, tolerance=0.02)  # 2% relative tolerance
golden.check("processing_time_sec", 123.4, absolute_tolerance=5.0)  # ±5 seconds

golden.save()  # Does nothing in validation mode
```

## Update Mode (Blessing New Values)

After verifying that value changes are intentional:

```python
# Update mode - saves new values
golden = GoldenValues("golden_values.yaml", update_mode=True)

golden.check("papers_downloaded", 8600)  # New value
golden.check("avg_diagrams_per_paper", 1.48)

golden.save()  # Saves updated values
```

## Context Manager (Auto-save)

```python
with GoldenValues("golden_values.yaml", update_mode=True) as golden:
    golden.check("value", 42)
    # Automatically saves on exit
```

## Tolerance Types

```python
# Exact match (default for int/str)
golden.check("count", 100)

# Relative tolerance (percentage-based)
golden.check("ratio", 0.523, tolerance=0.01)  # 1% = [0.518, 0.528]

# Absolute tolerance (fixed range)
golden.check("delta", 0.001, absolute_tolerance=0.0001)  # [0.0009, 0.0011]
```

## Pipeline Integration

### Option 1: Manual Management

```python
# pipeline.py
def run_pipeline(config, update_golden=False):
    golden = GoldenValues(
        golden_file=config.paths.data_dir / "golden_values.yaml",
        update_mode=update_golden
    )

    # Pass to pipeline steps
    context = {"golden": golden}

    # Run steps...
    fetch_corpus(config, context)
    detect_diagrams(config, context)

    # Save at end
    golden.save()
```

```python
# Individual step (e.g., fetch_corpus.py)
def run(config, context):
    golden = context["golden"]

    # ... fetch papers ...

    golden.check("papers_downloaded", len(results))
    golden.check("papers_with_doi", len(df_with_doi))

    return True
```

### Option 2: Context Manager

```python
def run_pipeline(config, update_golden=False):
    with GoldenValues(config.paths.data_dir / "golden_values.yaml",
                      update_mode=update_golden) as golden:
        context = {"golden": golden}
        fetch_corpus(config, context)
        detect_diagrams(config, context)
        # Auto-saves on exit
```

## CLI Integration

Add to your pipeline CLI:

```python
parser.add_argument(
    "--update-golden",
    action="store_true",
    help="Update golden values instead of validating"
)

# Usage
python pipeline.py --config config.yaml                  # Validate
python pipeline.py --config config.yaml --update-golden  # Update
```

## LaTeX Export

Export validated golden values to LaTeX macros:

```python
from golden_values import GoldenValues
import yaml

# Read golden values
with open("golden_values.yaml") as f:
    values = yaml.safe_load(f)

# Export to LaTeX
with open("results.tex", 'w') as f:
    for key, value in values.items():
        macro_name = key.replace("_", "")
        f.write(f"\\newcommand{{\\{macro_name}}}{{{value}}}\n")
```

Then in your paper:
```latex
We analyzed \papersdownloaded{} papers and detected \totaldiagrams{} diagrams,
averaging \avgdiagramsperpaper{} diagrams per paper.
```

## Golden Values File Format

The golden values are stored in YAML:

```yaml
# golden_values.yaml
avg_diagrams_per_paper: 1.45
papers_downloaded: 8523
papers_with_doi: 8234
processing_time_sec: 123.4
total_diagrams: 12340
```

**Important**: Commit this file to version control to track how values evolve over time.

## Error Handling

By default, mismatches raise `ValueError`:

```python
golden = GoldenValues("golden_values.yaml")  # strict=True (default)
golden.check("count", 100)  # Raises ValueError if mismatch
```

For non-strict mode (warnings only):

```python
golden = GoldenValues("golden_values.yaml", strict=False)
golden.check("count", 100)  # Logs warning but continues
```

## Best Practices

1. **Version control** - Commit `golden_values.yaml` to git
2. **Review changes** - Always review why values changed before blessing them
3. **Use tolerances wisely** - Floats often have small variations (use relative tolerance)
4. **Document changes** - Add comments in git commits explaining why values changed
5. **Separate files** - Consider separate golden files for different environments (dev/prod)

## Example Workflow

```bash
# 1. Normal run - validates against golden values
python pipeline.py --config config.yaml
# ❌ ERROR: Golden value mismatch for 'papers_downloaded'
#    Expected: 8523, Got: 8600

# 2. Investigate - why did value change?
#    - New data source? ✓ Expected
#    - Bug fix? ✓ Expected
#    - Regression? ✗ Need to fix

# 3. After verifying change is correct, update golden values
python pipeline.py --config config.yaml --update-golden
# ✓ Updated golden values file: golden_values.yaml

# 4. Commit changes
git add golden_values.yaml
git commit -m "Update golden values after adding 2024 dataset"
```

## API Reference

### GoldenValues

```python
GoldenValues(
    golden_file: str | Path,
    update_mode: bool = False,
    strict: bool = True
)
```

**Methods:**
- `check(key, value, tolerance=None, absolute_tolerance=None)` - Check value against golden
- `save()` - Save golden values (only in update_mode)
- `get(key, default=None)` - Get specific golden value
- `get_all()` - Get all golden values as dict
- `summary()` - Get formatted summary string

## License

Part of the dh4pmp_tools package collection.
