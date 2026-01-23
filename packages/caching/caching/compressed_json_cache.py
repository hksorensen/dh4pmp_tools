"""
Compressed JSON cache - stores Python objects as gzip-compressed JSON strings.

Useful for caching large structured data (like ML model outputs) where:
- Data is JSON-serializable (dicts, lists, etc.)
- Compression saves significant space (~70% reduction typical)
- Read performance is acceptable (decompression overhead is small)

Built on top of StringCache for status tracking and persistence.
"""

import gzip
import json
from typing import Any, Optional, List, Dict
from pathlib import Path

from .string_cache import StringCache


class CompressedJSONCache:
    """
    Cache that stores Python objects as gzip-compressed JSON.

    Features:
    - Automatic JSON serialization/deserialization
    - Gzip compression (~70% space savings)
    - Status tracking (pending, completed, failed, etc.)
    - Timestamp tracking
    - Built on StringCache for persistence

    Example:
        >>> cache = CompressedJSONCache("results_cache.json")
        >>>
        >>> # Store results
        >>> results = [{"page": 1, "detections": [...]}, {"page": 2, "detections": [...]}]
        >>> cache.set("paper.pdf", results)
        >>>
        >>> # Retrieve results
        >>> cached = cache.get("paper.pdf")
        >>> if cached:
        ...     print(f"Found {len(cached)} pages in cache")
    """

    def __init__(
        self,
        cache_file: Optional[str] = None,
        max_age_days: Optional[int] = None,
        auto_save: bool = True,
    ):
        """
        Initialize compressed JSON cache.

        Args:
            cache_file: Path to cache file (None = use default cache dir)
            max_age_days: Expire entries after this many days (None = never)
            auto_save: Save to disk after each modification
        """
        self.cache = StringCache(
            cache_file=cache_file,
            max_age_days=max_age_days,
            auto_save=auto_save,
        )

    @staticmethod
    def _compress(obj: Any) -> str:
        """
        Compress Python object to hex-encoded gzip string.

        Args:
            obj: JSON-serializable Python object

        Returns:
            Hex-encoded gzip-compressed JSON string
        """
        # Serialize to JSON
        json_str = json.dumps(obj)

        # Compress with gzip
        compressed = gzip.compress(json_str.encode('utf-8'))

        # Hex encode for storage in JSON (StringCache stores strings)
        return compressed.hex()

    @staticmethod
    def _decompress(hex_value: str) -> Any:
        """
        Decompress hex-encoded gzip string to Python object.

        Args:
            hex_value: Hex-encoded gzip-compressed JSON string

        Returns:
            Deserialized Python object
        """
        # Decode from hex
        compressed_bytes = bytes.fromhex(hex_value)

        # Decompress with gzip
        json_bytes = gzip.decompress(compressed_bytes)

        # Parse JSON
        return json.loads(json_bytes.decode('utf-8'))

    def has(self, key: str, status: Optional[str] = None) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key
            status: If provided, only return True if status matches

        Returns:
            True if key exists and is not expired
        """
        return self.cache.has(key, status=status)

    def get(
        self,
        key: str,
        default: Optional[Any] = None,
        status: Optional[str] = None
    ) -> Optional[Any]:
        """
        Get cached value.

        Args:
            key: Cache key
            default: Return this if key not found
            status: If provided, only return if status matches

        Returns:
            Cached Python object or default
        """
        hex_value = self.cache.get(key, default=None, status=status)

        if hex_value is None:
            return default

        try:
            return self._decompress(hex_value)
        except Exception as e:
            # Decompression failed - corrupted cache entry
            import logging
            logging.warning(f"Failed to decompress cache entry '{key}': {e}")
            return default

    def set(
        self,
        key: str,
        value: Any,
        status: str = "completed",
        **extra_fields
    ):
        """
        Store value in cache.

        Args:
            key: Cache key
            value: JSON-serializable Python object to cache
            status: Status indicator (default: "completed")
            **extra_fields: Additional fields to store
        """
        hex_value = self._compress(value)
        self.cache.set(key, hex_value, status=status, **extra_fields)

    def update_status(self, key: str, status: str):
        """Update status for an existing entry."""
        self.cache.update_status(key, status)

    def delete(self, key: str) -> bool:
        """
        Remove key from cache.

        Returns:
            True if key was deleted, False if not found
        """
        return self.cache.delete(key)

    def list_keys(
        self,
        status: Optional[str] = None,
        include_expired: bool = False
    ) -> List[str]:
        """
        List all keys in cache.

        Args:
            status: Filter by status
            include_expired: Include expired entries

        Returns:
            List of cache keys
        """
        return self.cache.list_keys(status=status, include_expired=include_expired)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache_file, num_entries, size_kb, etc.
        """
        # Get basic stats from StringCache
        cache_file = self.cache.cache_file
        num_entries = len(self.cache.data)

        # Count by status
        status_counts = {}
        for entry in self.cache.data.values():
            status = entry.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1

        # Calculate file size
        size_kb = 0
        if cache_file.exists():
            size_kb = cache_file.stat().st_size / 1024

        return {
            'cache_file': str(cache_file),
            'num_entries': num_entries,
            'status_counts': status_counts,
            'size_kb': size_kb,
        }

    def clear_expired(self) -> int:
        """
        Remove expired entries.

        Returns:
            Number of entries removed
        """
        return self.cache.clear_expired()

    def clear_status(self, status: str) -> int:
        """
        Remove all entries with given status.

        Returns:
            Number of entries removed
        """
        return self.cache.clear_status(status)

    def clear_all(self):
        """Remove all cached data."""
        self.cache.clear_all()

    def save(self):
        """Explicitly save cache to disk (if auto_save is False)."""
        self.cache._save()


if __name__ == "__main__":
    # Demo usage
    import tempfile

    print("CompressedJSONCache Demo\n")

    # Create temporary cache
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        cache_file = f.name

    cache = CompressedJSONCache(cache_file=cache_file)

    # Store some data
    test_data = {
        "results": [
            {"page": 1, "detections": [{"bbox": [0, 0, 100, 100], "confidence": 0.95}]},
            {"page": 2, "detections": []},
            {"page": 3, "detections": [{"bbox": [50, 50, 150, 150], "confidence": 0.88}]},
        ],
        "metadata": {
            "total_pages": 3,
            "total_detections": 2,
        }
    }

    cache.set("test_document.pdf", test_data)
    print(f"Stored test data")

    # Retrieve
    retrieved = cache.get("test_document.pdf")
    print(f"Retrieved: {retrieved['metadata']['total_detections']} detections across {retrieved['metadata']['total_pages']} pages")

    # Check cache stats
    stats = cache.get_stats()
    print(f"\nCache stats:")
    print(f"  File: {stats['cache_file']}")
    print(f"  Entries: {stats['num_entries']}")
    print(f"  Size: {stats['size_kb']:.2f} KB")

    # Show compression savings
    import json as json_module
    uncompressed_size = len(json_module.dumps(test_data).encode('utf-8'))
    compressed_size = len(cache.cache.data["test_document.pdf"]["value"]) // 2  # Hex encoding doubles size
    print(f"\nCompression:")
    print(f"  Uncompressed: {uncompressed_size} bytes")
    print(f"  Compressed: {compressed_size} bytes")
    print(f"  Savings: {(1 - compressed_size/uncompressed_size)*100:.1f}%")

    # Cleanup
    import os
    os.unlink(cache_file)
    print(f"\nCleaned up {cache_file}")
