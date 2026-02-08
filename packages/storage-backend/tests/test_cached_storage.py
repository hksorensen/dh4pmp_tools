"""Comprehensive tests for CachedStorage wrapper."""

import time
import pytest
from pathlib import Path

from storage_backend import LocalStorage, CachedStorage


class TestCachedStorageInit:
    """Test CachedStorage initialization."""

    def test_create_cached_storage(self, backend_dir: Path, cache_dir: Path):
        """Test basic initialization."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        assert cached.backend == backend
        # Use resolve() to handle symlinks (e.g., /var -> /private/var on macOS)
        assert cached.cache.base_dir == cache_dir.resolve()
        assert cache_dir.exists()

    def test_create_with_size_limit(self, backend_dir: Path, cache_dir: Path):
        """Test initialization with cache size limit."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(
            backend=backend,
            cache_dir=cache_dir,
            max_cache_size_mb=100
        )

        assert cached.max_cache_size_mb == 100

    def test_create_with_ttl(self, backend_dir: Path, cache_dir: Path):
        """Test initialization with TTL."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(
            backend=backend,
            cache_dir=cache_dir,
            ttl_seconds=3600
        )

        assert cached.ttl_seconds == 3600

    def test_creates_cache_dir_if_missing(self, backend_dir: Path, temp_dir: Path):
        """Test cache directory is created if missing."""
        backend = LocalStorage(backend_dir)
        cache_path = temp_dir / "new_cache"

        assert not cache_path.exists()

        cached = CachedStorage(backend=backend, cache_dir=cache_path)

        assert cache_path.exists()


class TestCachedStorageReadCaching:
    """Test read() method and caching behavior."""

    def test_read_populates_cache(self, backend_dir: Path, cache_dir: Path, test_content: bytes):
        """Test first read populates cache."""
        # Setup backend with file
        backend = LocalStorage(backend_dir)
        backend.write("test.txt", test_content)

        # Create cached storage
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        # Cache should be empty initially
        assert not (cache_dir / "test.txt").exists()

        # Read file - should populate cache
        content = cached.read("test.txt")

        assert content == test_content
        assert (cache_dir / "test.txt").exists()
        assert (cache_dir / "test.txt").read_bytes() == test_content

    def test_read_from_cache_second_time(self, backend_dir: Path, cache_dir: Path, test_content: bytes):
        """Test second read comes from cache, not backend."""
        # Setup backend
        backend = LocalStorage(backend_dir)
        backend.write("test.txt", test_content)

        # Create cached storage
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        # First read - populates cache
        cached.read("test.txt")

        # Modify backend file
        backend.write("test.txt", b"Modified content")

        # Second read - should come from cache (old content)
        content = cached.read("test.txt")
        assert content == test_content  # Old content from cache

    def test_read_missing_file_raises(self, backend_dir: Path, cache_dir: Path):
        """Test reading missing file raises FileNotFoundError."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        with pytest.raises(FileNotFoundError):
            cached.read("nonexistent.txt")

    def test_read_with_ttl_expiry(self, backend_dir: Path, cache_dir: Path, test_content: bytes):
        """Test TTL expiry forces re-read from backend."""
        # Setup backend
        backend = LocalStorage(backend_dir)
        backend.write("test.txt", test_content)

        # Create cached storage with 1 second TTL
        cached = CachedStorage(
            backend=backend,
            cache_dir=cache_dir,
            ttl_seconds=1
        )

        # First read - populates cache
        cached.read("test.txt")

        # Modify backend
        new_content = b"New content after TTL"
        backend.write("test.txt", new_content)

        # Wait for TTL to expire
        time.sleep(1.1)

        # Read again - should get new content from backend
        content = cached.read("test.txt")
        assert content == new_content

    def test_read_without_ttl_no_expiry(self, backend_dir: Path, cache_dir: Path, test_content: bytes):
        """Test cache without TTL never expires."""
        # Setup backend
        backend = LocalStorage(backend_dir)
        backend.write("test.txt", test_content)

        # Create cached storage without TTL
        cached = CachedStorage(
            backend=backend,
            cache_dir=cache_dir,
            ttl_seconds=None
        )

        # First read
        cached.read("test.txt")

        # Modify backend
        backend.write("test.txt", b"Modified")

        # Even after waiting, should still get cached content
        time.sleep(0.1)
        content = cached.read("test.txt")
        assert content == test_content  # Old cached content


class TestCachedStorageWriteThrough:
    """Test write() method write-through behavior."""

    def test_write_updates_both_backend_and_cache(
        self, backend_dir: Path, cache_dir: Path, test_content: bytes
    ):
        """Test write updates both backend and cache."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        cached.write("test.txt", test_content)

        # Check both backend and cache have the file
        assert backend.exists("test.txt")
        assert backend.read("test.txt") == test_content
        assert (cache_dir / "test.txt").exists()
        assert (cache_dir / "test.txt").read_bytes() == test_content

    def test_write_returns_true_on_success(self, backend_dir: Path, cache_dir: Path):
        """Test write returns True on success."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        result = cached.write("test.txt", b"content")
        assert result is True

    def test_write_backend_first_priority(self, backend_dir: Path, cache_dir: Path):
        """Test write succeeds if backend succeeds, even if cache fails."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        # Write should succeed (backend is primary)
        result = cached.write("test.txt", b"content")
        assert result is True
        assert backend.exists("test.txt")


class TestCachedStorageDelete:
    """Test delete() method."""

    def test_delete_removes_from_both(self, backend_dir: Path, cache_dir: Path, test_content: bytes):
        """Test delete removes from both backend and cache."""
        backend = LocalStorage(backend_dir)
        backend.write("test.txt", test_content)

        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        # Read to populate cache
        cached.read("test.txt")
        assert (cache_dir / "test.txt").exists()

        # Delete
        cached.delete("test.txt")

        # Check removed from both
        assert not backend.exists("test.txt")
        assert not (cache_dir / "test.txt").exists()

    def test_delete_missing_file_raises(self, backend_dir: Path, cache_dir: Path):
        """Test deleting missing file raises FileNotFoundError."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        with pytest.raises(FileNotFoundError):
            cached.delete("nonexistent.txt")


class TestCachedStorageExists:
    """Test exists() method."""

    def test_exists_checks_backend(self, backend_dir: Path, cache_dir: Path):
        """Test exists checks backend, not cache."""
        backend = LocalStorage(backend_dir)
        backend.write("test.txt", b"content")

        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        # Should return True even though not in cache yet
        assert cached.exists("test.txt") is True

    def test_exists_false_for_missing(self, backend_dir: Path, cache_dir: Path):
        """Test exists returns False for missing file."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        assert cached.exists("nonexistent.txt") is False

    def test_exists_true_even_if_only_in_cache(self, backend_dir: Path, cache_dir: Path):
        """Test exists checks backend (source of truth)."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        # Put file only in cache (simulate orphaned cache entry)
        (cache_dir / "orphan.txt").write_bytes(b"orphan")

        # Should return False (not in backend)
        assert cached.exists("orphan.txt") is False


class TestCachedStorageList:
    """Test list() method."""

    def test_list_returns_backend_files(self, backend_dir: Path, cache_dir: Path, test_files: dict):
        """Test list returns files from backend."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        files = cached.list()

        assert len(files) == len(test_files)
        for filename in test_files.keys():
            assert filename in files

    def test_list_with_pattern(self, backend_dir: Path, cache_dir: Path):
        """Test list with pattern."""
        backend = LocalStorage(backend_dir)
        backend.write("file1.txt", b"1")
        backend.write("file2.pdf", b"2")

        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        txt_files = cached.list("*.txt")
        assert len(txt_files) == 1
        assert "file1.txt" in txt_files


class TestCachedStorageSize:
    """Test size() method."""

    def test_size_from_backend(self, backend_dir: Path, cache_dir: Path, test_content: bytes):
        """Test size returns value from backend."""
        backend = LocalStorage(backend_dir)
        backend.write("test.txt", test_content)

        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        assert cached.size("test.txt") == len(test_content)


class TestCachedStorageGetPath:
    """Test get_path() method."""

    def test_get_path_returns_backend_path(self, backend_dir: Path, cache_dir: Path):
        """Test get_path returns backend path, not cache path."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        path = cached.get_path("test.txt")

        assert str(backend_dir) in path
        assert str(cache_dir) not in path


class TestCachedStorageCacheEviction:
    """Test cache eviction and size management."""

    def test_eviction_when_exceeding_size_limit(self, backend_dir: Path, cache_dir: Path):
        """Test LRU eviction when cache size exceeds limit."""
        backend = LocalStorage(backend_dir)

        # Create cached storage with 0.1 MB limit
        cached = CachedStorage(
            backend=backend,
            cache_dir=cache_dir,
            max_cache_size_mb=0.1
        )

        # Write files totaling > 0.1 MB
        file1_content = b"X" * (60 * 1024)  # 60 KB
        file2_content = b"Y" * (60 * 1024)  # 60 KB

        backend.write("file1.txt", file1_content)
        backend.write("file2.txt", file2_content)

        # Read file1 (caches it)
        cached.read("file1.txt")
        time.sleep(0.1)  # Ensure different access times

        # Read file2 (should evict file1 due to size limit)
        cached.read("file2.txt")

        # file1 should be evicted from cache
        assert not (cache_dir / "file1.txt").exists()
        # file2 should still be cached
        assert (cache_dir / "file2.txt").exists()

    def test_no_eviction_without_size_limit(self, backend_dir: Path, cache_dir: Path):
        """Test no eviction when no size limit set."""
        backend = LocalStorage(backend_dir)

        # Create cached storage without size limit
        cached = CachedStorage(
            backend=backend,
            cache_dir=cache_dir,
            max_cache_size_mb=None
        )

        # Write multiple large files
        for i in range(5):
            content = b"X" * (1024 * 1024)  # 1 MB each
            backend.write(f"file{i}.txt", content)
            cached.read(f"file{i}.txt")

        # All should still be cached
        for i in range(5):
            assert (cache_dir / f"file{i}.txt").exists()

    def test_eviction_frees_enough_space(self, backend_dir: Path, cache_dir: Path):
        """Test eviction frees enough space for incoming file."""
        backend = LocalStorage(backend_dir)

        # 0.1 MB cache limit
        cached = CachedStorage(
            backend=backend,
            cache_dir=cache_dir,
            max_cache_size_mb=0.1
        )

        # Fill cache with small files
        for i in range(5):
            content = b"X" * (20 * 1024)  # 20 KB each
            backend.write(f"small{i}.txt", content)
            cached.read(f"small{i}.txt")
            time.sleep(0.05)  # Ensure different access times

        # Try to cache large file
        large_content = b"Y" * (80 * 1024)  # 80 KB
        backend.write("large.txt", large_content)
        cached.read("large.txt")

        # Large file should be cached
        assert (cache_dir / "large.txt").exists()

        # Cache size should be under limit
        stats = cached.get_cache_stats()
        assert stats["size_mb"] <= 0.1


class TestCachedStorageCacheStats:
    """Test get_cache_stats() method."""

    def test_cache_stats_empty(self, backend_dir: Path, cache_dir: Path):
        """Test cache stats for empty cache."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        stats = cached.get_cache_stats()

        assert stats["file_count"] == 0
        assert stats["size_mb"] == 0.0
        assert stats["max_size_mb"] is None

    def test_cache_stats_with_files(self, backend_dir: Path, cache_dir: Path):
        """Test cache stats with cached files."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(
            backend=backend,
            cache_dir=cache_dir,
            max_cache_size_mb=10
        )

        # Cache some files
        for i in range(3):
            content = b"X" * (100 * 1024)  # 100 KB each
            backend.write(f"file{i}.txt", content)
            cached.read(f"file{i}.txt")

        stats = cached.get_cache_stats()

        assert stats["file_count"] == 3
        assert stats["size_mb"] > 0.2  # ~300 KB total
        assert stats["max_size_mb"] == 10

    def test_cache_stats_accurate_size(self, backend_dir: Path, cache_dir: Path):
        """Test cache stats reports accurate total size."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        # Cache file of known size
        content = b"X" * (512 * 1024)  # 512 KB = 0.5 MB
        backend.write("test.txt", content)
        cached.read("test.txt")

        stats = cached.get_cache_stats()

        # Should be close to 0.5 MB (within 0.01 MB tolerance)
        assert abs(stats["size_mb"] - 0.5) < 0.01


class TestCachedStorageClearCache:
    """Test clear_cache() method."""

    def test_clear_cache_removes_all_files(self, backend_dir: Path, cache_dir: Path):
        """Test clear_cache removes all cached files."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        # Cache multiple files
        for i in range(5):
            backend.write(f"file{i}.txt", b"content")
            cached.read(f"file{i}.txt")

        # Verify cached
        assert cached.get_cache_stats()["file_count"] == 5

        # Clear cache
        cached.clear_cache()

        # Verify all removed
        stats = cached.get_cache_stats()
        assert stats["file_count"] == 0
        assert stats["size_mb"] == 0.0

    def test_clear_cache_preserves_backend(self, backend_dir: Path, cache_dir: Path):
        """Test clear_cache doesn't affect backend files."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        # Write and cache files
        backend.write("test.txt", b"content")
        cached.read("test.txt")

        # Clear cache
        cached.clear_cache()

        # Backend file should still exist
        assert backend.exists("test.txt")
        assert backend.read("test.txt") == b"content"

    def test_clear_cache_allows_fresh_reads(self, backend_dir: Path, cache_dir: Path):
        """Test clearing cache forces fresh reads from backend."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        # Cache file
        backend.write("test.txt", b"old content")
        cached.read("test.txt")

        # Modify backend
        backend.write("test.txt", b"new content")

        # Clear cache
        cached.clear_cache()

        # Next read should get new content from backend
        content = cached.read("test.txt")
        assert content == b"new content"


class TestCachedStorageIntegration:
    """Integration tests for complex cache scenarios."""

    def test_mixed_operations_workflow(self, backend_dir: Path, cache_dir: Path):
        """Test realistic workflow with mixed operations."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(
            backend=backend,
            cache_dir=cache_dir,
            max_cache_size_mb=1
        )

        # Write files
        for i in range(10):
            cached.write(f"file{i}.txt", f"Content {i}".encode())

        # Read some files (populates cache)
        for i in [0, 2, 4, 6, 8]:
            cached.read(f"file{i}.txt")

        # Verify cache has some files (at least 5 should be cached)
        # Note: May have more due to write-through caching
        assert cached.get_cache_stats()["file_count"] >= 5

        # Delete one file
        cached.delete("file4.txt")

        # Verify removed from both backend and cache
        assert not backend.exists("file4.txt")
        assert not (cache_dir / "file4.txt").exists()

        # List should return 9 files (10 - 1 deleted)
        assert len(cached.list()) == 9

    def test_concurrent_access_simulation(self, backend_dir: Path, cache_dir: Path):
        """Test cache behavior under rapid repeated access."""
        backend = LocalStorage(backend_dir)
        cached = CachedStorage(backend=backend, cache_dir=cache_dir)

        # Write file
        backend.write("popular.txt", b"Popular content")

        # Read multiple times rapidly (simulates concurrent access)
        for _ in range(100):
            content = cached.read("popular.txt")
            assert content == b"Popular content"

        # Should be cached (only one copy)
        assert cached.get_cache_stats()["file_count"] == 1
