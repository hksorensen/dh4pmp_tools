#!/usr/bin/env python3
"""
Check Retry Statistics for PDF Downloads

Simple utility to check how many papers will retry downloading
within 1 day and 1 week.

Usage:
    python check_retry_stats.py [database_path]

If database_path is not provided, uses default location.
"""

import sys
from pathlib import Path
from pdf_fetcher import PDFFetcher


def main():
    # Get database path from argument or use default
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])
    else:
        # Try common locations
        possible_paths = [
            Path.home() / ".pdf_fetcher" / "metadata.db",
            Path("download_metadata.db"),
            Path("data/pdf_downloads.db"),
        ]

        db_path = None
        for path in possible_paths:
            if path.exists():
                db_path = path
                break

        if db_path is None:
            print("Error: Could not find database file.")
            print("Please provide path as argument:")
            print(f"  python {sys.argv[0]} /path/to/database.db")
            sys.exit(1)

    print(f"\nUsing database: {db_path}")

    # Initialize fetcher
    fetcher = PDFFetcher(
        output_dir="/tmp/dummy",  # Not used for stats
        metadata_db_path=db_path
    )

    # Get retry statistics
    stats = fetcher.get_retry_stats()

    # Display results
    print("\n" + "="*70)
    print("PDF DOWNLOAD RETRY STATISTICS")
    print("="*70)
    print(f"\n{stats['summary']}\n")
    print(f"📊 Total papers eligible for retry: {stats['total_retry']}")
    print(f"   ├─ Will retry within 1 day:     {stats['retry_1_day']}")
    print(f"   └─ Will retry within 1 week:    {stats['retry_1_week']}")
    print(f"\n🚫 Papers that won't retry:")
    print(f"   ├─ Marked as never retry:       {stats['never_retry']} (timeouts, hangs, etc.)")
    print(f"   └─ Max attempts reached:        {stats['max_attempts_reached']}")
    print("="*70)
    print()

    # Get overall stats for context
    overall = fetcher.get_stats()
    if 'total' in overall:
        print(f"Context: {overall['success']} successful out of {overall['total']} total papers")
        print(f"         ({overall['success_rate']:.1f}% success rate)")

    print()


if __name__ == "__main__":
    main()
