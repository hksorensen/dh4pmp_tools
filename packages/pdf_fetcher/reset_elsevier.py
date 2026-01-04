#!/usr/bin/env python3
"""
Delete all failed Elsevier download attempts from the database.

This allows you to retry them cleanly with the new TDM API strategy.
"""

import sqlite3
import sys
from pathlib import Path


def reset_elsevier_failures():
    """Delete all failed Elsevier downloads from database."""
    db_path = Path.home() / '.pdf_fetcher' / 'metadata.db'
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Count failed Elsevier downloads
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM download_results
        WHERE identifier LIKE '10.1016/%'
        AND status = 'failure'
    """)
    
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("No failed Elsevier downloads found in database.")
        conn.close()
        return
    
    print("=" * 80)
    print("Reset Elsevier Failed Downloads")
    print("=" * 80)
    print()
    print(f"Found {count} failed Elsevier download attempts")
    print(f"These will be DELETED from the database.")
    print(f"You can then re-download them using the TDM API.")
    print()
    
    response = input(f"Delete {count} failed Elsevier records? [y/N]: ").strip().lower()
    
    if response != 'y':
        print("Cancelled.")
        conn.close()
        return
    
    # Delete failed Elsevier downloads
    cursor.execute("""
        DELETE FROM download_results
        WHERE identifier LIKE '10.1016/%'
        AND status = 'failure'
    """)
    
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    print()
    print(f"✓ Deleted {deleted} failed Elsevier records")
    print()
    print("Next steps:")
    print("  1. Set up API key: python setup_elsevier_api.py YOUR_API_KEY")
    print("  2. Create DOI list: sqlite3 ~/.pdf_fetcher/metadata.db")
    print("     Or use your original DOI source file")
    print("  3. Run: pdf-fetcher --input dois.txt")
    print()


if __name__ == '__main__':
    reset_elsevier_failures()
