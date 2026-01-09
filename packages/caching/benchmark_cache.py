#!/usr/bin/env python3
"""
Benchmark LocalCache vs SQLiteLocalCache performance.

Tests the performance difference between JSON-based and SQLite-based
metadata storage with various cache sizes.
"""

import time
import pandas as pd
import tempfile
from pathlib import Path
from caching import LocalCache, SQLiteLocalCache


def create_test_data(n_rows=100):
    """Create a test DataFrame."""
    return pd.DataFrame({
        'id': range(n_rows),
        'value': [f'test_{i}' for i in range(n_rows)],
        'data': [{'key': f'value_{i}'} for i in range(n_rows)]
    })


def benchmark_store(cache_class, cache_dir, num_queries=100):
    """Benchmark storing multiple queries."""
    cache = cache_class(cache_dir=cache_dir, compression=True)

    start = time.time()
    for i in range(num_queries):
        query = f"query_{i:04d}"
        data = create_test_data(50)
        cache.store(query, data, source="benchmark")
    elapsed = time.time() - start

    return elapsed


def benchmark_has(cache_class, cache_dir, num_queries=100, num_checks=1000):
    """Benchmark checking if queries exist."""
    cache = cache_class(cache_dir=cache_dir, compression=True)

    # Populate cache first
    for i in range(num_queries):
        query = f"query_{i:04d}"
        data = create_test_data(50)
        cache.store(query, data)

    # Benchmark has() calls
    start = time.time()
    for i in range(num_checks):
        query = f"query_{i % num_queries:04d}"
        cache.has(query)
    elapsed = time.time() - start

    return elapsed


def benchmark_list_queries(cache_class, cache_dir, num_queries=100):
    """Benchmark listing all queries."""
    cache = cache_class(cache_dir=cache_dir, compression=True)

    # Populate cache
    for i in range(num_queries):
        query = f"query_{i:04d}"
        data = create_test_data(50)
        cache.store(query, data)

    # Benchmark list_queries()
    start = time.time()
    queries = cache.list_queries()
    elapsed = time.time() - start

    return elapsed, len(queries)


def benchmark_get_ID_list(cache_class, cache_dir, num_queries=100):
    """Benchmark getting list of all query IDs."""
    cache = cache_class(cache_dir=cache_dir, compression=True)

    # Populate cache
    for i in range(num_queries):
        query = f"query_{i:04d}"
        data = create_test_data(50)
        cache.store(query, data)

    # Benchmark get_ID_list() if available
    if not hasattr(cache, 'get_ID_list'):
        return None

    start = time.time()
    ids = cache.get_ID_list()
    elapsed = time.time() - start

    return elapsed, len(ids)


def run_benchmark(cache_sizes=[10, 100, 500, 1000]):
    """Run comprehensive benchmark."""
    print("=" * 80)
    print("LocalCache vs SQLiteLocalCache Performance Benchmark")
    print("=" * 80)
    print()

    results = []

    for size in cache_sizes:
        print(f"\nCache Size: {size} entries")
        print("-" * 80)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test LocalCache
            json_dir = Path(tmpdir) / "json_cache"
            json_dir.mkdir()

            print("\n  LocalCache (JSON metadata):")
            json_store = benchmark_store(LocalCache, json_dir, size)
            print(f"    Store {size} queries: {json_store:.3f}s ({json_store/size*1000:.2f}ms per query)")

            json_has = benchmark_has(LocalCache, json_dir, size, size * 10)
            print(f"    has() x{size*10}: {json_has:.3f}s ({json_has/(size*10)*1000:.2f}ms per call)")

            json_list_time, json_list_count = benchmark_list_queries(LocalCache, json_dir, size)
            print(f"    list_queries(): {json_list_time:.3f}s ({json_list_count} entries)")

            # Test SQLiteLocalCache
            sqlite_dir = Path(tmpdir) / "sqlite_cache"
            sqlite_dir.mkdir()

            print("\n  SQLiteLocalCache (SQLite metadata):")
            sqlite_store = benchmark_store(SQLiteLocalCache, sqlite_dir, size)
            print(f"    Store {size} queries: {sqlite_store:.3f}s ({sqlite_store/size*1000:.2f}ms per query)")

            sqlite_has = benchmark_has(SQLiteLocalCache, sqlite_dir, size, size * 10)
            print(f"    has() x{size*10}: {sqlite_has:.3f}s ({sqlite_has/(size*10)*1000:.2f}ms per call)")

            sqlite_list_time, sqlite_list_count = benchmark_list_queries(SQLiteLocalCache, sqlite_dir, size)
            print(f"    list_queries(): {sqlite_list_time:.3f}s ({sqlite_list_count} entries)")

            sqlite_id_result = benchmark_get_ID_list(SQLiteLocalCache, sqlite_dir, size)
            if sqlite_id_result:
                sqlite_id_time, sqlite_id_count = sqlite_id_result
                print(f"    get_ID_list(): {sqlite_id_time:.3f}s ({sqlite_id_count} entries)")

            # Calculate speedup
            print("\n  Speedup (JSON → SQLite):")
            print(f"    Store: {json_store/sqlite_store:.1f}x faster" if sqlite_store < json_store else f"    Store: {sqlite_store/json_store:.1f}x slower")
            print(f"    has(): {json_has/sqlite_has:.1f}x faster")
            print(f"    list_queries(): {json_list_time/sqlite_list_time:.1f}x faster")

            results.append({
                'size': size,
                'json_store': json_store,
                'sqlite_store': sqlite_store,
                'json_has': json_has,
                'sqlite_has': sqlite_has,
                'speedup_store': json_store / sqlite_store,
                'speedup_has': json_has / sqlite_has,
            })

    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print("\nSpeedup factors (higher = SQLite is faster):")
    print(f"{'Cache Size':<12} {'Store':<10} {'has()':<10} {'list_queries()':<15}")
    print("-" * 80)

    for r in results:
        print(f"{r['size']:<12} {r['speedup_store']:<10.1f}x {r['speedup_has']:<10.1f}x")

    print("\nRecommendation:")
    if results[-1]['speedup_has'] > 2:
        print("  ✓ Use SQLiteLocalCache for caches with 100+ entries")
        print(f"  ✓ Speedup increases with cache size (up to {results[-1]['speedup_has']:.0f}x faster)")
    else:
        print("  • Both caches perform similarly for small caches")


if __name__ == "__main__":
    import sys

    # Parse cache sizes from command line
    if len(sys.argv) > 1:
        sizes = [int(x) for x in sys.argv[1:]]
    else:
        sizes = [10, 100, 500, 1000]

    run_benchmark(sizes)
