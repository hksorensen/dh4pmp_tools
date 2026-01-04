# Database Merge Guide

## Overview

The `pdf_fetcher` package now includes a powerful merge tool to combine two `downloads.db` files from different PDF folders.

**Use case:** You have PDFs and download metadata in two separate folders and want to merge them into one.

---

## Your Specific Case

You have:
- **Folder 1:** `/Users/fvb832/Documents/dh4pmp/research/diagrams_in_arxiv/pdfs/`
  - `downloads.db` (7.9 MB, 17,292 records: 13,967 success, 3,325 failure)
- **Folder 2:** `/Users/fvb832/Documents/dh4pmp/research/diagrams_in_arxiv/data/results/pdfs/`
  - `downloads.db` (7.2 MB)

---

## Merge Strategy

The merge tool uses this conflict resolution:

1. **Success over Failure:** If the same DOI exists in both databases:
   - ✅ One succeeded, one failed → Keep the successful one

2. **Most Recent:** If both have the same status:
   - ⏱️ Keep the entry with the most recent `last_attempted` timestamp

3. **File Handling:**
   - 📦 Moves PDF files from source to target directory
   - ⚠️ Skips if file already exists in target

---

## Step-by-Step Instructions

### Step 1: Dry Run (Safe Preview)

First, run a **dry run** to see what would happen:

```bash
pdf_fetcher \
  --db /Users/fvb832/Documents/dh4pmp/research/diagrams_in_arxiv/pdfs/downloads.db \
  --merge-db \
    /Users/fvb832/Documents/dh4pmp/research/diagrams_in_arxiv/data/results/pdfs/downloads.db \
    /Users/fvb832/Documents/dh4pmp/research/diagrams_in_arxiv/data/results/pdfs \
    /Users/fvb832/Documents/dh4pmp/research/diagrams_in_arxiv/pdfs \
  --dry-run
```

**What this does:**
- Shows what would be added/updated/kept
- Shows how many files would be moved
- **Does NOT make any changes**

**Output example:**
```
================================================================================
MERGING DATABASES
================================================================================
Source DB:      .../data/results/pdfs/downloads.db
Source PDF dir: .../data/results/pdfs
Target DB:      .../pdfs/downloads.db
Target PDF dir: .../pdfs
Mode:           DRY RUN (no changes)
================================================================================

[DRY RUN] 10.1007/xxx: add
[DRY RUN] 10.1016/yyy: update_success_over_failure
[DRY RUN] 10.1090/zzz: keep_existing_success
...

================================================================================
MERGE RESULTS
================================================================================
Source entries:        15234
✓ Added:               2456
⟳ Updated:             543
  - Success over fail: 123
⊙ Kept existing:       12235

Files moved:           0
Files copied:          0
Files skipped:         0
================================================================================

This was a dry run. Re-run without --dry-run to apply changes.
```

### Step 2: Review Output

Check the dry run output for:
- ✅ **Added:** New entries from source (good!)
- ✅ **Updated:** Conflicts resolved (check "Success over fail")
- ✅ **Kept existing:** Existing entries preserved (good!)
- ⚠️ **Errors:** Any file operation errors

### Step 3: Run Actual Merge

If everything looks good, run the **actual merge**:

```bash
pdf_fetcher \
  --db /Users/fvb832/Documents/dh4pmp/research/diagrams_in_arxiv/pdfs/downloads.db \
  --merge-db \
    /Users/fvb832/Documents/dh4pmp/research/diagrams_in_arxiv/data/results/pdfs/downloads.db \
    /Users/fvb832/Documents/dh4pmp/research/diagrams_in_arxiv/data/results/pdfs \
    /Users/fvb832/Documents/dh4pmp/research/diagrams_in_arxiv/pdfs
```

**What happens:**
1. Prompts for confirmation: `Continue? [y/N]:`
2. Merges database entries
3. **Moves PDF files** from source to target
4. Updates file paths in database

**Output:**
```
This will merge databases and move PDF files. Continue? [y/N]: y

...

================================================================================
MERGE RESULTS
================================================================================
Source entries:        15234
✓ Added:               2456
⟳ Updated:             543
  - Success over fail: 123
⊙ Kept existing:       12235

Files moved:           2999
Files copied:          0
Files skipped:         13967  (already in target)
================================================================================

✓ Merge complete! You can now delete the source database and PDF directory if desired.
```

### Step 4: Verify

After merge, verify the results:

```bash
# Check merged database stats
pdf_fetcher --db /Users/fvb832/Documents/dh4pmp/research/diagrams_in_arxiv/pdfs/downloads.db --stats

# Verify files exist
pdf_fetcher --db /Users/fvb832/Documents/dh4pmp/research/diagrams_in_arxiv/pdfs/downloads.db --verify
```

### Step 5: Cleanup (Optional)

If merge was successful, you can delete the source folder:

```bash
# CAREFUL! Only do this after verifying merge was successful
rm -rf /Users/fvb832/Documents/dh4pmp/research/diagrams_in_arxiv/data/results/pdfs/
```

---

## Programmatic Usage (Python)

You can also use the merge functionality from Python:

```python
from pdf_fetcher.database import DownloadMetadataDB

# Open target database
target_db = DownloadMetadataDB(
    "pdfs/downloads.db"
)

# Merge from source
stats = target_db.merge_from(
    source_db_path="data/results/pdfs/downloads.db",
    source_pdf_dir="data/results/pdfs",
    target_pdf_dir="pdfs",
    move_files=True,
    dry_run=False  # Set to True for preview
)

# Check results
print(f"Added: {stats['added']}")
print(f"Updated: {stats['updated']}")
print(f"Files moved: {stats['files_moved']}")
```

---

## Command-Line Options

### Basic Syntax

```bash
pdf_fetcher --db TARGET_DB --merge-db SOURCE_DB [SOURCE_PDF_DIR] [TARGET_PDF_DIR] [--dry-run]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--db TARGET_DB` | Yes | Target database to merge INTO |
| `SOURCE_DB` | Yes | Source database to merge FROM |
| `SOURCE_PDF_DIR` | No | Source PDF directory (auto-detected if omitted) |
| `TARGET_PDF_DIR` | No | Target PDF directory (defaults to output_dir) |
| `--dry-run` | No | Preview mode (no changes) |

### Examples

**Simplest (auto-detect directories):**
```bash
pdf_fetcher --db target.db --merge-db source.db
```

**With explicit directories:**
```bash
pdf_fetcher --db target.db --merge-db source.db /source/pdfs /target/pdfs
```

**Dry run first:**
```bash
pdf_fetcher --db target.db --merge-db source.db /source/pdfs /target/pdfs --dry-run
```

---

## Conflict Resolution Details

### Example: Same DOI in Both Databases

**Scenario 1: Different Status**
- Source: `10.1007/xxx` → **success** (downloaded)
- Target: `10.1007/xxx` → **failure** (not downloaded)
- **Result:** Keep source (success over failure)
- **Action:** Move PDF from source to target

**Scenario 2: Same Status, Different Timestamp**
- Source: `10.1016/yyy` → success (2024-12-30)
- Target: `10.1016/yyy` → success (2024-12-25)
- **Result:** Keep source (more recent)
- **Action:** Replace target with source

**Scenario 3: Target Better**
- Source: `10.1090/zzz` → failure
- Target: `10.1090/zzz` → success
- **Result:** Keep target
- **Action:** No changes

---

## Safety Features

1. **Dry Run Mode:** Preview changes without modifying anything
2. **Confirmation Prompt:** Asks for confirmation before proceeding
3. **Error Tracking:** Reports any file operation errors
4. **No Data Loss:** Never deletes from target database
5. **Atomic Operations:** Uses SQLite transactions for safety

---

## FAQ

**Q: What if I have PDFs with the same filename in both folders?**
- A: The merge tool skips files that already exist in target (no overwrite)

**Q: Can I undo a merge?**
- A: No automatic undo, but you can restore from backup (make a backup first!)

**Q: What if merge fails halfway?**
- A: SQLite transactions ensure database consistency. Files may be partially moved.

**Q: Can I merge multiple databases at once?**
- A: No, merge one at a time. But you can chain merges.

**Q: Will this slow down my system?**
- A: File moves are fast (same filesystem). Copying is slower.

---

## Troubleshooting

### Error: "Source database not found"
- Check the path to source database
- Use absolute paths or ensure you're in correct directory

### Error: "Failed to move/copy file"
- Check file permissions
- Ensure target directory is writable
- Check disk space

### "Skipped" count is very high
- Normal! Means many PDFs already exist in target
- Check `files_moved` to see how many were actually moved

---

## Best Practices

1. **Always dry-run first** to preview changes
2. **Backup** your target database before merging
3. **Use absolute paths** to avoid confusion
4. **Verify after merge** using `--stats` and `--verify`
5. **Test with small subset** if you're nervous

---

## Next Steps

After merging:
1. ✅ Run `--stats` to see combined statistics
2. ✅ Run `--verify` to ensure all files exist
3. ✅ Update your notebooks to point to merged database
4. ✅ Delete old source folder (after verification!)
