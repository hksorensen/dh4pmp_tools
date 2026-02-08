"""Quick test/example of storage_backend usage."""

from pathlib import Path
import tempfile

from storage_backend import LocalStorage, CachedStorage


def test_local_storage():
    """Test basic local storage operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(tmpdir)

        # Write a file
        test_content = b"Hello, World!"
        storage.write("test.txt", test_content)

        # Check it exists
        assert storage.exists("test.txt")

        # Read it back
        content = storage.read("test.txt")
        assert content == test_content

        # Check size
        size = storage.size("test.txt")
        assert size == len(test_content)

        # List files
        files = storage.list()
        assert "test.txt" in files

        # Delete
        storage.delete("test.txt")
        assert not storage.exists("test.txt")

        print("✓ LocalStorage test passed")


def test_cached_storage():
    """Test cached storage wrapper."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend_dir = Path(tmpdir) / "backend"
        cache_dir = Path(tmpdir) / "cache"

        backend = LocalStorage(backend_dir)
        cached = CachedStorage(
            backend=backend,
            cache_dir=cache_dir,
            max_cache_size_mb=10
        )

        # Write through cache
        test_content = b"Cached content"
        cached.write("test.pdf", test_content)

        # Verify in both backend and cache
        assert backend.exists("test.pdf")
        assert Path(cache_dir, "test.pdf").exists()

        # Read from cache
        content = cached.read("test.pdf")
        assert content == test_content

        # Check cache stats
        stats = cached.get_cache_stats()
        assert stats["file_count"] == 1
        assert stats["size_mb"] > 0

        print("✓ CachedStorage test passed")


if __name__ == "__main__":
    test_local_storage()
    test_cached_storage()
    print("\n✓ All tests passed!")
