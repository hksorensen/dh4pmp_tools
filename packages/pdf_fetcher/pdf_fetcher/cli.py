"""Command-line interface for PDF Fetcher."""

import argparse
import logging
import sys
from pathlib import Path
from typing import List

from pdf_fetcher import PDFFetcher, __version__


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='PDF Fetcher - Automated academic PDF downloader',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download a single PDF
  pdf-fetcher 10.1007/s10623-024-01403-z

  # Download multiple PDFs
  pdf-fetcher 10.1007/s10623-024-01403-z 10.1090/memo/1523

  # Download from a file with one DOI per line
  pdf-fetcher --input dois.txt

  # Specify output directory
  pdf-fetcher --output ./papers 10.1007/s10623-024-01403-z

  # Use custom database location
  pdf-fetcher --db ./my_project.db 10.1007/s10623-024-01403-z

  # Show statistics
  pdf-fetcher --stats

  # Verify all downloaded files still exist
  pdf-fetcher --verify

  # Clear all failed download attempts (useful after network issues)
  pdf-fetcher --clear-failures

  # List archived files
  pdf-fetcher --list-archived

  # List missing files
  pdf-fetcher --list-missing

  # Mark a file as archived to remote storage
  pdf-fetcher --mark-archived 10.1007/s10623-024-01403-z sftp://server/pdfs/file.pdf

  # Scan for orphaned PDF files and add them to database
  pdf-fetcher --scan-orphaned ./pdfs
  pdf-fetcher --scan-orphaned ./pdfs ./data/results/pdfs

  # Merge another database (with dry-run first)
  pdf-fetcher --merge-db /path/to/source.db /path/to/source/pdfs /path/to/target/pdfs --dry-run
  pdf-fetcher --merge-db /path/to/source.db /path/to/source/pdfs /path/to/target/pdfs
        """
    )

    parser.add_argument(
        'dois',
        nargs='*',
        help='DOIs to download'
    )

    parser.add_argument(
        '-i', '--input',
        type=str,
        help='Input file with one DOI per line'
    )

    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output directory for PDFs (default: ./pdfs)'
    )

    parser.add_argument(
        '-c', '--config',
        type=str,
        help='Path to config file (default: config.yaml)'
    )

    parser.add_argument(
        '-w', '--workers',
        type=int,
        help='Number of parallel workers (default: 4)'
    )

    parser.add_argument(
        '--email',
        type=str,
        help='Email for Unpaywall API (overrides config)'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show download statistics from database'
    )

    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify all downloaded files still exist and update database'
    )

    parser.add_argument(
        '--clear-failures',
        action='store_true',
        help='Clear all failed download attempts from database (preserves successes)'
    )

    parser.add_argument(
        '--list-archived',
        action='store_true',
        help='List all files marked as archived to remote storage'
    )

    parser.add_argument(
        '--list-missing',
        action='store_true',
        help='List all files marked as missing (deleted but not archived)'
    )

    parser.add_argument(
        '--mark-archived',
        nargs=2,
        metavar=('IDENTIFIER', 'LOCATION'),
        help='Mark a file as archived to remote location (e.g., sftp://server/path)'
    )

    parser.add_argument(
        '--scan-orphaned',
        nargs='+',
        metavar='PDF_DIR',
        help='Scan directories for PDF files not in database and add them with confirmation'
    )

    parser.add_argument(
        '--merge-db',
        nargs='+',
        metavar=('SOURCE_DB', 'SOURCE_PDF_DIR'),
        help='Merge another database into this one. Args: SOURCE_DB [SOURCE_PDF_DIR] [TARGET_PDF_DIR]'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would happen without making changes (use with --merge-db)'
    )

    parser.add_argument(
        '--db',
        type=str,
        help='Path to database file (default: ~/.pdf_fetcher/metadata.db)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'pdf-fetcher {__version__}'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Collect DOIs
    dois: List[str] = []

    if args.input:
        # Read from file
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)

        with open(input_path, 'r') as f:
            dois = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    if args.dois:
        dois.extend(args.dois)

    # Initialize fetcher
    fetcher_kwargs = {}
    if args.output:
        fetcher_kwargs['output_dir'] = args.output
    if args.config:
        fetcher_kwargs['config_path'] = args.config
    if args.workers:
        fetcher_kwargs['max_workers'] = args.workers
    if args.email:
        fetcher_kwargs['unpaywall_email'] = args.email
    if args.db:
        fetcher_kwargs['metadata_db_path'] = args.db

    fetcher = PDFFetcher(**fetcher_kwargs)

    # Show statistics
    if args.stats:
        stats = fetcher.get_stats()
        if stats:
            print("\n" + "="*80)
            print("PDF FETCHER STATISTICS")
            print("="*80)
            print(f"Database: {fetcher.db.db_path}")
            print("="*80)

            # Overall Summary
            print("\n📊 OVERALL SUMMARY")
            print("-"*80)
            total = stats['total']
            success = stats['success']
            failure = stats['failure']
            postponed = stats['postponed']
            skipped = stats['skipped']

            print(f"  Total entries:        {total:,}")
            print(f"  ✓ Success:            {success:,} ({success/total*100 if total > 0 else 0:.1f}%)")
            print(f"  ✗ Failure:            {failure:,} ({failure/total*100 if total > 0 else 0:.1f}%)")
            print(f"  ⏸ Postponed:          {postponed:,} ({postponed/total*100 if total > 0 else 0:.1f}%)")
            if skipped > 0:
                print(f"  ⊙ Skipped:            {skipped:,} ({skipped/total*100 if total > 0 else 0:.1f}%)")
            print(f"  Avg attempts/PDF:     {stats['avg_attempts']:.1f}")

            # File Status
            if stats['archived'] > 0 or stats['missing'] > 0:
                print("\n📁 FILE STATUS")
                print("-"*80)
                if stats['archived'] > 0:
                    print(f"  Archived:             {stats['archived']:,}")
                if stats['missing'] > 0:
                    print(f"  ⚠ Missing:            {stats['missing']:,} (files deleted)")

            # Top Publishers
            if stats['top_publishers']:
                print("\n📚 TOP PUBLISHERS")
                print("-"*80)
                for i, (publisher, count) in enumerate(stats['top_publishers'][:10], 1):
                    pub_stats = stats['by_publisher'].get(publisher, {})
                    success_count = pub_stats.get('success', 0)
                    success_pct = (success_count / count * 100) if count > 0 else 0
                    print(f"  {i:2d}. {publisher:30s} {count:5,} ({success_pct:5.1f}% success)")

            # Recent Activity
            if stats['recent_activity']:
                print("\n📅 RECENT ACTIVITY (Last 7 days)")
                print("-"*80)
                for activity in stats['recent_activity'][:7]:
                    date = activity['date']
                    count = activity['count']
                    print(f"  {date}:  {count:4,} downloads")

            # Top Error Reasons
            if stats['error_reasons']:
                print("\n❌ TOP FAILURE REASONS")
                print("-"*80)
                for i, (reason, count) in enumerate(list(stats['error_reasons'].items())[:5], 1):
                    # Truncate long error messages
                    short_reason = reason[:60] + "..." if len(reason) > 60 else reason
                    print(f"  {i}. {short_reason}")
                    print(f"     Count: {count:,}")

            # Strategy Usage
            if stats['strategy_stats']:
                print("\n🔧 DOWNLOAD STRATEGIES USED")
                print("-"*80)
                total_with_strategy = sum(stats['strategy_stats'].values())
                for strategy, count in sorted(stats['strategy_stats'].items(), key=lambda x: x[1], reverse=True)[:5]:
                    pct = (count / total_with_strategy * 100) if total_with_strategy > 0 else 0
                    print(f"  {strategy:30s} {count:5,} ({pct:5.1f}%)")

            print("="*80 + "\n")
        else:
            print("No statistics available (database not initialized)")
        return

    # Verify files
    if args.verify:
        if not fetcher.db:
            print("Error: Database not initialized", file=sys.stderr)
            sys.exit(1)

        print("\n" + "="*80)
        print("VERIFYING FILES")
        print("="*80)
        results = fetcher.db.verify_files()
        print(f"✓ Verified:  {len(results['verified'])} files exist")
        print(f"✗ Missing:   {len(results['missing'])} files deleted")
        print(f"⊙ Archived:  {len(results['archived'])} files archived")
        print("="*80 + "\n")

        if results['missing']:
            print("Missing files (first 20):")
            for identifier in results['missing'][:20]:
                print(f"  - {identifier}")
            if len(results['missing']) > 20:
                print(f"  ... and {len(results['missing']) - 20} more")
            print()
        return

    # Clear failures
    if args.clear_failures:
        if not fetcher.db:
            print("Error: Database not initialized", file=sys.stderr)
            sys.exit(1)

        print("\n" + "="*80)
        print("CLEARING FAILED DOWNLOADS")
        print("="*80)

        # Get count before deletion
        import sqlite3
        cursor = fetcher.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM downloads WHERE status = 'failure'")
        count_before = cursor.fetchone()[0]

        if count_before == 0:
            print("No failed downloads to clear.")
            print("="*80 + "\n")
            return

        # Delete failures
        cursor.execute("DELETE FROM downloads WHERE status = 'failure'")
        fetcher.db.conn.commit()

        print(f"✓ Cleared {count_before} failed download(s)")
        print("  Successful downloads preserved")
        print("  You can now retry those DOIs")
        print("="*80 + "\n")
        return

    # List archived files
    if args.list_archived:
        if not fetcher.db:
            print("Error: Database not initialized", file=sys.stderr)
            sys.exit(1)

        archived = fetcher.db.get_archived()
        print("\n" + "="*80)
        print(f"ARCHIVED FILES ({len(archived)} total)")
        print("="*80)

        if archived:
            for entry in archived:
                print(f"\nIdentifier: {entry['identifier']}")
                print(f"  Location: {entry['archive_location']}")
                print(f"  Archived: {entry['archive_date']}")
                print(f"  Filename: {entry['sanitized_filename']}")
        else:
            print("No archived files found")
        print("="*80 + "\n")
        return

    # List missing files
    if args.list_missing:
        if not fetcher.db:
            print("Error: Database not initialized", file=sys.stderr)
            sys.exit(1)

        missing = fetcher.db.get_missing()
        print("\n" + "="*80)
        print(f"MISSING FILES ({len(missing)} total)")
        print("="*80)

        if missing:
            for entry in missing:
                print(f"\nIdentifier: {entry['identifier']}")
                print(f"  Expected path: {entry['local_path']}")
                print(f"  Last attempted: {entry['last_attempted']}")
                print(f"  Filename: {entry['sanitized_filename']}")
        else:
            print("No missing files found")
        print("="*80 + "\n")
        return

    # Mark file as archived
    if args.mark_archived:
        if not fetcher.db:
            print("Error: Database not initialized", file=sys.stderr)
            sys.exit(1)

        identifier, location = args.mark_archived
        fetcher.db.mark_archived(identifier, location)
        print(f"\n✓ Marked {identifier} as archived at {location}\n")
        return

    # Scan for orphaned PDFs
    if args.scan_orphaned:
        if not fetcher.db:
            print("Error: Database not initialized", file=sys.stderr)
            sys.exit(1)

        pdf_dirs = args.scan_orphaned

        print("\n" + "="*80)
        print("SCANNING FOR ORPHANED PDF FILES")
        print("="*80)
        print(f"Database:       {fetcher.db.db_path}")
        print(f"Directories:    {', '.join(pdf_dirs)}")
        print("="*80 + "\n")

        # Scan for orphaned files
        orphaned = fetcher.db.scan_for_orphaned_pdfs(pdf_dirs)

        if not orphaned:
            print("✓ No orphaned PDF files found. All PDFs are already in the database.\n")
            return

        # Show orphaned files
        print(f"Found {len(orphaned)} orphaned PDF file(s) not in database:\n")

        # Group by whether DOI was inferred
        with_doi = [o for o in orphaned if o['inferred_doi']]
        without_doi = [o for o in orphaned if not o['inferred_doi']]

        if with_doi:
            print(f"With inferred DOI ({len(with_doi)}):")
            for i, orphan in enumerate(with_doi[:10], 1):
                print(f"  {i:3d}. {orphan['filename'][:60]}")
                print(f"       DOI: {orphan['inferred_doi']}")
                print(f"       Size: {orphan['size_mb']:.2f} MB")
            if len(with_doi) > 10:
                print(f"       ... and {len(with_doi) - 10} more")
            print()

        if without_doi:
            print(f"Without DOI (will use filename as identifier) ({len(without_doi)}):")
            for i, orphan in enumerate(without_doi[:10], 1):
                print(f"  {i:3d}. {orphan['filename'][:60]}")
                print(f"       Size: {orphan['size_mb']:.2f} MB")
            if len(without_doi) > 10:
                print(f"       ... and {len(without_doi) - 10} more")
            print()

        # Ask for confirmation
        confirm = input(f"Add all {len(orphaned)} orphaned PDF(s) to database? [y/N]: ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return

        # Add orphaned files to database
        print("\nAdding orphaned PDFs to database...")
        added_count = 0
        skipped_count = 0
        error_count = 0

        for orphan in orphaned:
            try:
                identifier = fetcher.db.add_orphaned_pdf(
                    pdf_path=orphan['path'],
                    inferred_doi=orphan['inferred_doi']
                )
                added_count += 1
                print(f"  ✓ Added: {identifier}")
            except ValueError as e:
                error_count += 1
                print(f"  ✗ Error: {orphan['filename']}: {e}")
            except Exception as e:
                # Check if it's a "already exists" warning
                if "already exists" in str(e):
                    skipped_count += 1
                    print(f"  ⊙ Skipped: {orphan['filename']} (already in database)")
                else:
                    error_count += 1
                    print(f"  ✗ Error: {orphan['filename']}: {e}")

        print("\n" + "="*80)
        print("SCAN RESULTS")
        print("="*80)
        print(f"Found:          {len(orphaned)} orphaned PDF(s)")
        print(f"✓ Added:        {added_count}")
        print(f"⊙ Skipped:      {skipped_count}")
        if error_count > 0:
            print(f"✗ Errors:       {error_count}")
        print("="*80 + "\n")

        return

    # Merge databases
    if args.merge_db:
        if not fetcher.db:
            print("Error: Database not initialized", file=sys.stderr)
            sys.exit(1)

        # Parse arguments: SOURCE_DB [SOURCE_PDF_DIR] [TARGET_PDF_DIR]
        source_db = args.merge_db[0]
        source_pdf_dir = args.merge_db[1] if len(args.merge_db) > 1 else None
        target_pdf_dir = args.merge_db[2] if len(args.merge_db) > 2 else None

        print("\n" + "="*80)
        print("MERGING DATABASES")
        print("="*80)
        print(f"Source DB:      {source_db}")
        print(f"Source PDF dir: {source_pdf_dir or '(auto-detect from database)'}")
        print(f"Target DB:      {fetcher.db.db_path}")
        print(f"Target PDF dir: {target_pdf_dir or str(fetcher.output_dir)}")
        print(f"Mode:           {'DRY RUN (no changes)' if args.dry_run else 'LIVE (will move files)'}")
        print("="*80 + "\n")

        if not args.dry_run:
            confirm = input("This will merge databases and move PDF files. Continue? [y/N]: ")
            if confirm.lower() != 'y':
                print("Aborted.")
                return

        try:
            stats = fetcher.db.merge_from(
                source_db_path=source_db,
                source_pdf_dir=source_pdf_dir,
                target_pdf_dir=target_pdf_dir or str(fetcher.output_dir),
                move_files=True,
                dry_run=args.dry_run
            )

            print("\n" + "="*80)
            print("MERGE RESULTS")
            print("="*80)
            print(f"Source entries:        {stats['total_source_entries']}")
            print(f"✓ Added:               {stats['added']}")
            print(f"⟳ Updated:             {stats['updated']}")
            print(f"  - Success over fail: {stats['conflicts_resolved']}")
            print(f"⊙ Kept existing:       {stats['kept_existing']}")
            print()
            print(f"Files moved:           {stats['files_moved']}")
            print(f"Files copied:          {stats['files_copied']}")
            print(f"Files skipped:         {stats['files_skipped']}")

            if stats['errors']:
                print(f"\n⚠ Errors:              {len(stats['errors'])}")
                print("\nFirst 5 errors:")
                for error in stats['errors'][:5]:
                    print(f"  - {error}")

            print("="*80 + "\n")

            if not args.dry_run:
                print("✓ Merge complete! You can now delete the source database and PDF directory if desired.\n")
            else:
                print("This was a dry run. Re-run without --dry-run to apply changes.\n")

        except Exception as e:
            print(f"\nError during merge: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)

        return

    # Check if we have DOIs to download
    if not dois:
        parser.print_help()
        sys.exit(1)

    # Download PDFs
    print(f"\n{'='*80}")
    print(f"PDF Fetcher v{__version__}")
    print(f"{'='*80}")
    print(f"DOIs to download: {len(dois)}")
    print(f"Output directory: {fetcher.output_dir}")
    print(f"Workers: {fetcher.max_workers}")
    print(f"{'='*80}\n")

    def progress_callback(completed, total):
        """Progress callback for batch downloads."""
        percentage = (completed / total) * 100
        print(f"Progress: {completed}/{total} ({percentage:.1f}%)", end='\r')

    # Download
    results = fetcher.fetch_batch(dois, progress_callback=progress_callback)

    # Print results
    print("\n\n" + "="*80)
    print("RESULTS")
    print("="*80)

    success_count = sum(1 for r in results if r.status == 'success')
    failed_count = sum(1 for r in results if r.status == 'failure')
    postponed_count = sum(1 for r in results if r.status == 'postponed')
    skipped_count = sum(1 for r in results if r.status == 'skipped')

    print(f"Total: {len(results)}")
    print(f"✓ Success:   {success_count} ({success_count/len(results)*100:.1f}%)")
    print(f"✗ Failed:    {failed_count} ({failed_count/len(results)*100:.1f}%)")
    print(f"⏸ Postponed: {postponed_count} ({postponed_count/len(results)*100:.1f}%)")
    print(f"⊙ Skipped:   {skipped_count} ({skipped_count/len(results)*100:.1f}%)")
    print("="*80)

    # Show sample failures
    failures = [r for r in results if r.status == 'failure']
    if failures:
        print("\nSample Failures (first 10):")
        print("-"*80)
        for i, result in enumerate(failures[:10], 1):
            print(f"{i:2d}. {result.identifier}")
            print(f"    Error: {result.error_reason}")

    print(f"\nAll files in: {fetcher.output_dir}\n")


if __name__ == '__main__':
    main()
