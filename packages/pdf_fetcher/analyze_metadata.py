#!/usr/bin/env python3
"""Analyze pdf_fetcher metadata.db to find blind spots and improvement opportunities."""

import sqlite3
from pathlib import Path
from collections import defaultdict
import sys

# Publisher DOI prefix mapping
PUBLISHER_PREFIXES = {
    '10.1016': 'Elsevier',
    '10.1080': 'Taylor & Francis',
    '10.1007': 'Springer',
    '10.1002': 'Wiley',
    '10.1038': 'Nature',
    '10.1109': 'IEEE',
    '10.1177': 'SAGE',
    '10.1093': 'Oxford',
    '10.1017': 'Cambridge',
    '10.1111': 'Wiley (alternate)',
}

def get_publisher_from_identifier(identifier):
    """Extract publisher from DOI identifier."""
    if not identifier:
        return 'Unknown'

    # Extract DOI prefix (e.g., "10.1016" from "10.1016/j.cell.2020.01.001")
    parts = identifier.split('/')
    if len(parts) >= 2:
        prefix = parts[0] + '/' + parts[1].split('.')[0]
        return PUBLISHER_PREFIXES.get(prefix, f'Other ({prefix})')

    return 'Unknown'

def analyze_database(db_path):
    """Analyze pdf_fetcher database for blind spots."""

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 80)
    print("PDF FETCHER METADATA ANALYSIS")
    print("=" * 80)
    print()

    # 1. Overall status breakdown
    print("📊 OVERALL STATUS BREAKDOWN")
    print("-" * 80)
    cursor.execute("""
        SELECT status, COUNT(*) as count,
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM download_results), 2) as percentage
        FROM download_results
        GROUP BY status
        ORDER BY count DESC
    """)

    total = 0
    for row in cursor.fetchall():
        print(f"  {row['status']:20s}: {row['count']:6d} ({row['percentage']:5.2f}%)")
        total += row['count']

    print(f"\n  {'TOTAL':20s}: {total:6d}")
    print()

    # 2. Success rate by publisher (inferred from DOI)
    print("🏢 SUCCESS RATE BY PUBLISHER (Top 20)")
    print("-" * 80)

    cursor.execute("""
        SELECT identifier, status, publisher
        FROM download_results
    """)

    publisher_stats = defaultdict(lambda: {'success': 0, 'failed': 0, 'total': 0})

    for row in cursor.fetchall():
        # Use recorded publisher or infer from DOI
        publisher = row['publisher'] if row['publisher'] else get_publisher_from_identifier(row['identifier'])

        publisher_stats[publisher]['total'] += 1
        if row['status'] == 'success':
            publisher_stats[publisher]['success'] += 1
        elif row['status'] == 'failure':  # Fixed: database uses 'failure' not 'failed'
            publisher_stats[publisher]['failed'] += 1

    # Sort by total volume
    sorted_publishers = sorted(
        publisher_stats.items(),
        key=lambda x: x[1]['total'],
        reverse=True
    )[:20]

    print(f"  {'Publisher':30s} {'Total':>8s} {'Success':>8s} {'Failed':>8s} {'Rate':>8s}")
    print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    for publisher, stats in sorted_publishers:
        success_rate = stats['success'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"  {publisher:30s} {stats['total']:8d} {stats['success']:8d} {stats['failed']:8d} {success_rate:7.1f}%")

    print()

    # 3. BLIND SPOTS: High volume + Low success rate
    print("🎯 BLIND SPOTS (High volume, low success rate)")
    print("-" * 80)
    print(f"  Criteria: ≥20 attempts AND <40% success rate")
    print()

    blind_spots = [
        (pub, stats) for pub, stats in publisher_stats.items()
        if stats['total'] >= 20 and (stats['success'] / stats['total'] * 100 < 40)
    ]

    blind_spots.sort(key=lambda x: x[1]['total'], reverse=True)

    if blind_spots:
        print(f"  {'Publisher':30s} {'Total':>8s} {'Success':>8s} {'Failed':>8s} {'Rate':>8s}")
        print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

        for publisher, stats in blind_spots:
            success_rate = stats['success'] / stats['total'] * 100
            print(f"  {publisher:30s} {stats['total']:8d} {stats['success']:8d} {stats['failed']:8d} {success_rate:7.1f}%")
    else:
        print("  ✓ No major blind spots found!")

    print()

    # 4. Common failure reasons
    print("❌ TOP FAILURE REASONS")
    print("-" * 80)

    cursor.execute("""
        SELECT error_reason, COUNT(*) as count
        FROM download_results
        WHERE status = 'failed' AND error_reason IS NOT NULL
        GROUP BY error_reason
        ORDER BY count DESC
        LIMIT 10
    """)

    for row in cursor.fetchall():
        error = row['error_reason'][:60] + "..." if len(row['error_reason']) > 60 else row['error_reason']
        print(f"  {row['count']:6d}  {error}")

    print()

    # 5. Cloudflare detection
    print("☁️  CLOUDFLARE PROTECTION")
    print("-" * 80)

    cursor.execute("""
        SELECT COUNT(*) as count
        FROM download_results
        WHERE cloudflare_detected = 1
    """)

    cloudflare_count = cursor.fetchone()['count']
    cloudflare_pct = cloudflare_count / total * 100 if total > 0 else 0

    print(f"  Cloudflare detected: {cloudflare_count:6d} ({cloudflare_pct:5.2f}%)")
    print()

    # 6. Strategy effectiveness
    print("🎲 STRATEGY EFFECTIVENESS")
    print("-" * 80)

    cursor.execute("""
        SELECT strategy_used,
               COUNT(*) as total,
               SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success
        FROM download_results
        WHERE strategy_used IS NOT NULL
        GROUP BY strategy_used
        ORDER BY total DESC
    """)

    print(f"  {'Strategy':30s} {'Total':>8s} {'Success':>8s} {'Rate':>8s}")
    print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8}")

    for row in cursor.fetchall():
        success_rate = row['success'] / row['total'] * 100 if row['total'] > 0 else 0
        print(f"  {row['strategy_used']:30s} {row['total']:8d} {row['success']:8d} {success_rate:7.1f}%")

    print()

    # 7. Files that exist but marked as failed/missing
    print("📁 FILE STATUS AUDIT")
    print("-" * 80)

    cursor.execute("""
        SELECT
            status,
            file_exists,
            COUNT(*) as count
        FROM download_results
        GROUP BY status, file_exists
        ORDER BY status, file_exists
    """)

    print(f"  {'Status':20s} {'File Exists':12s} {'Count':>8s}")
    print(f"  {'-'*20} {'-'*12} {'-'*8}")

    for row in cursor.fetchall():
        file_exists = 'Yes' if row['file_exists'] else 'No'
        print(f"  {row['status']:20s} {file_exists:12s} {row['count']:8d}")

    # Check for potential orphans (files exist but status != success)
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM download_results
        WHERE file_exists = 1 AND status != 'success'
    """)

    orphan_count = cursor.fetchone()['count']
    if orphan_count > 0:
        print(f"\n  ⚠️  Found {orphan_count} files that exist but status != 'success'")
        print(f"      These might be files that were downloaded manually/externally")

    print()

    conn.close()

if __name__ == '__main__':
    db_path = Path.home() / '.pdf_fetcher' / 'metadata.db'

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    analyze_database(db_path)
