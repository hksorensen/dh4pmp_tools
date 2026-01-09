#!/usr/bin/env python3
"""
Migrate LocalCache (JSON metadata) to SQLiteLocalCache.

This script converts existing LocalCache metadata from JSON format
to SQLite format for faster performance. Pickle files remain unchanged.

Usage:
    python migrate_to_sqlite.py /path/to/cache_dir
    python migrate_to_sqlite.py /path/to/cache_dir --backup
    python migrate_to_sqlite.py /path/to/cache_dir --dry-run
"""

import argparse
import json
import shutil
from pathlib import Path
import pandas as pd
import sys

def migrate_cache(cache_dir: Path, backup: bool = False, dry_run: bool = False):
    """
    Migrate LocalCache JSON metadata to SQLite.

    Args:
        cache_dir: Path to cache directory
        backup: If True, create backup of _metadata.json
        dry_run: If True, only show what would be done
    """
    cache_dir = Path(cache_dir).expanduser()

    if not cache_dir.exists():
        print(f"Error: Cache directory does not exist: {cache_dir}")
        return False

    metadata_json = cache_dir / "_metadata.json"
    metadata_db = cache_dir / "_metadata.db"

    # Check if JSON metadata exists
    if not metadata_json.exists():
        print(f"No _metadata.json found in {cache_dir}")
        print("This cache may already be using SQLite or is empty.")
        return True

    # Load JSON metadata
    print(f"Loading metadata from: {metadata_json}")
    with open(metadata_json, 'r') as f:
        metadata = json.load(f)

    num_entries = len(metadata)
    print(f"Found {num_entries} cached entries")

    if dry_run:
        print("\nDRY RUN - No changes will be made")
        print("\nSample entries:")
        for i, (key, value) in enumerate(list(metadata.items())[:3]):
            print(f"  {key}: {value}")
        if num_entries > 3:
            print(f"  ... and {num_entries - 3} more")
        return True

    # Convert to DataFrame for SQLiteTableStorage
    rows = []
    for cache_key, meta in metadata.items():
        # Extract standard fields
        row = {
            'cache_key': cache_key,
            'query': meta.get('query', ''),
            'timestamp': meta.get('timestamp', ''),
            'num_rows': meta.get('num_rows', 0),
        }

        # Store extra fields as JSON
        extra_fields = {k: v for k, v in meta.items()
                       if k not in ['query', 'timestamp', 'num_rows', 'cache_key']}
        row['extra_metadata'] = extra_fields

        rows.append(row)

    df = pd.DataFrame(rows)

    # Create SQLiteTableStorage
    print(f"Creating SQLite database: {metadata_db}")
    from db_utils import SQLiteTableStorage

    storage = SQLiteTableStorage(
        db_path=str(metadata_db),
        table_name="cache_metadata",
        column_ID="cache_key",
        ID_type=str,
        json_columns=["extra_metadata"],
        table_layout={
            "cache_key": "TEXT PRIMARY KEY",
            "query": "TEXT",
            "timestamp": "TEXT",
            "num_rows": "INTEGER",
            "extra_metadata": "TEXT"
        }
    )

    # Write metadata to SQLite
    print("Writing metadata to SQLite...")
    storage.write(df, timestamp=False)

    # Create index on timestamp
    print("Creating indexes...")
    try:
        storage._execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON cache_metadata(timestamp)"
        )
    except Exception as e:
        print(f"Warning: Could not create index: {e}")

    # Verify migration
    stored = storage.get()
    if stored is None or len(stored) != num_entries:
        print(f"ERROR: Migration verification failed!")
        print(f"Expected {num_entries} entries, got {len(stored) if stored is not None else 0}")
        return False

    print(f"✓ Successfully migrated {num_entries} entries")

    # Backup original JSON
    if backup:
        backup_path = cache_dir / "_metadata.json.backup"
        print(f"Creating backup: {backup_path}")
        shutil.copy2(metadata_json, backup_path)

    # Optionally remove JSON file
    print("\nMigration complete!")
    print(f"Old file: {metadata_json}")
    print(f"New file: {metadata_db}")
    print("\nYou can now use SQLiteLocalCache with this cache directory.")

    response = input("\nRemove old _metadata.json file? [y/N]: ")
    if response.lower() == 'y':
        metadata_json.unlink()
        print("✓ Removed _metadata.json")
    else:
        print("Kept _metadata.json (you can remove it manually later)")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Migrate LocalCache JSON metadata to SQLite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate cache with backup
  python migrate_to_sqlite.py ~/.cache/my_cache --backup

  # Dry run to see what would be done
  python migrate_to_sqlite.py ~/.cache/my_cache --dry-run

  # Migrate multiple caches
  python migrate_to_sqlite.py ~/.cache/cache1
  python migrate_to_sqlite.py ~/.cache/cache2
        """
    )

    parser.add_argument(
        'cache_dir',
        type=Path,
        help='Path to cache directory containing _metadata.json'
    )

    parser.add_argument(
        '--backup',
        action='store_true',
        help='Create backup of _metadata.json before migration'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("LocalCache → SQLiteLocalCache Migration")
    print("=" * 70)
    print()

    success = migrate_cache(args.cache_dir, backup=args.backup, dry_run=args.dry_run)

    if not success:
        sys.exit(1)

    print()
    print("=" * 70)
    print("Migration completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
