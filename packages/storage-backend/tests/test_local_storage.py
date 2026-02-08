"""Comprehensive tests for LocalStorage backend."""

import pytest
from pathlib import Path

from storage_backend import LocalStorage


class TestLocalStorageInit:
    """Test LocalStorage initialization."""

    def test_create_with_string_path(self, temp_dir: Path):
        """Test initialization with string path."""
        storage = LocalStorage(str(temp_dir))
        # Use resolve() to handle symlinks (e.g., /var -> /private/var on macOS)
        assert storage.base_dir == temp_dir.resolve()

    def test_create_with_path_object(self, temp_dir: Path):
        """Test initialization with Path object."""
        storage = LocalStorage(temp_dir)
        # Use resolve() to handle symlinks
        assert storage.base_dir == temp_dir.resolve()

    def test_create_missing_dir_auto(self, temp_dir: Path):
        """Test automatic creation of missing directory."""
        new_dir = temp_dir / "new_storage"
        storage = LocalStorage(new_dir, create_if_missing=True)
        assert new_dir.exists()
        # Use resolve() to handle symlinks
        assert storage.base_dir == new_dir.resolve()

    def test_create_missing_dir_raises(self, temp_dir: Path):
        """Test error when directory missing and create_if_missing=False."""
        new_dir = temp_dir / "nonexistent"
        with pytest.raises(ValueError, match="does not exist"):
            LocalStorage(new_dir, create_if_missing=False)

    def test_path_is_file_raises(self, temp_dir: Path):
        """Test error when path points to a file, not directory."""
        file_path = temp_dir / "file.txt"
        file_path.write_text("test")
        with pytest.raises(ValueError, match="not a directory"):
            LocalStorage(file_path)

    def test_expanduser_tilde_path(self, temp_dir: Path, monkeypatch):
        """Test that ~ is expanded to home directory."""
        # Can't directly test ~ expansion without affecting real home,
        # but we can verify it doesn't crash
        storage = LocalStorage(temp_dir)
        assert storage.base_dir.is_absolute()


class TestLocalStorageExists:
    """Test exists() method."""

    def test_exists_true_for_existing_file(self, backend_dir: Path):
        """Test exists returns True for existing file."""
        test_file = backend_dir / "test.txt"
        test_file.write_text("content")

        storage = LocalStorage(backend_dir)
        assert storage.exists("test.txt") is True

    def test_exists_false_for_missing_file(self, backend_dir: Path):
        """Test exists returns False for missing file."""
        storage = LocalStorage(backend_dir)
        assert storage.exists("nonexistent.txt") is False

    def test_exists_false_for_directory(self, backend_dir: Path):
        """Test exists returns False for directory (only files)."""
        subdir = backend_dir / "subdir"
        subdir.mkdir()

        storage = LocalStorage(backend_dir)
        assert storage.exists("subdir") is False

    def test_exists_with_nested_path(self, backend_dir: Path):
        """Test exists with nested directory path."""
        nested = backend_dir / "a" / "b" / "c"
        nested.mkdir(parents=True)
        (nested / "file.txt").write_text("content")

        storage = LocalStorage(backend_dir)
        assert storage.exists("a/b/c/file.txt") is True

    def test_exists_rejects_path_traversal(self, backend_dir: Path, temp_dir: Path):
        """Test security: exists rejects path traversal attempts."""
        # Create file outside base_dir
        outside_file = temp_dir / "outside.txt"
        outside_file.write_text("outside")

        storage = LocalStorage(backend_dir)
        # Attempt to access file outside base_dir should return False
        assert storage.exists("../outside.txt") is False


class TestLocalStorageRead:
    """Test read() method."""

    def test_read_existing_file(self, backend_dir: Path):
        """Test reading existing file content."""
        content = b"Test content"
        test_file = backend_dir / "test.txt"
        test_file.write_bytes(content)

        storage = LocalStorage(backend_dir)
        assert storage.read("test.txt") == content

    def test_read_missing_file_raises(self, backend_dir: Path):
        """Test reading missing file raises FileNotFoundError."""
        storage = LocalStorage(backend_dir)
        with pytest.raises(FileNotFoundError):
            storage.read("nonexistent.txt")

    def test_read_directory_raises(self, backend_dir: Path):
        """Test reading directory raises IOError."""
        subdir = backend_dir / "subdir"
        subdir.mkdir()

        storage = LocalStorage(backend_dir)
        with pytest.raises(IOError, match="Not a regular file"):
            storage.read("subdir")

    def test_read_nested_file(self, backend_dir: Path):
        """Test reading nested file."""
        content = b"Nested content"
        nested = backend_dir / "a" / "b"
        nested.mkdir(parents=True)
        (nested / "file.txt").write_bytes(content)

        storage = LocalStorage(backend_dir)
        assert storage.read("a/b/file.txt") == content

    def test_read_binary_content(self, backend_dir: Path):
        """Test reading binary content preserves bytes."""
        content = bytes(range(256))  # All byte values
        test_file = backend_dir / "binary.dat"
        test_file.write_bytes(content)

        storage = LocalStorage(backend_dir)
        assert storage.read("binary.dat") == content

    def test_read_large_file(self, backend_dir: Path, large_test_content: bytes):
        """Test reading large file (1 MB)."""
        test_file = backend_dir / "large.bin"
        test_file.write_bytes(large_test_content)

        storage = LocalStorage(backend_dir)
        assert storage.read("large.bin") == large_test_content


class TestLocalStorageWrite:
    """Test write() method."""

    def test_write_new_file(self, backend_dir: Path):
        """Test writing new file."""
        content = b"New content"
        storage = LocalStorage(backend_dir)

        assert storage.write("new.txt", content) is True
        assert (backend_dir / "new.txt").read_bytes() == content

    def test_write_overwrites_existing(self, backend_dir: Path):
        """Test writing overwrites existing file."""
        test_file = backend_dir / "test.txt"
        test_file.write_bytes(b"Old content")

        storage = LocalStorage(backend_dir)
        storage.write("test.txt", b"New content")

        assert test_file.read_bytes() == b"New content"

    def test_write_creates_parent_dirs(self, backend_dir: Path):
        """Test write creates parent directories if needed."""
        content = b"Nested content"
        storage = LocalStorage(backend_dir)

        storage.write("a/b/c/file.txt", content)

        nested_file = backend_dir / "a" / "b" / "c" / "file.txt"
        assert nested_file.exists()
        assert nested_file.read_bytes() == content

    def test_write_empty_file(self, backend_dir: Path):
        """Test writing empty file."""
        storage = LocalStorage(backend_dir)
        storage.write("empty.txt", b"")

        assert (backend_dir / "empty.txt").read_bytes() == b""

    def test_write_large_file(self, backend_dir: Path, large_test_content: bytes):
        """Test writing large file (1 MB)."""
        storage = LocalStorage(backend_dir)
        storage.write("large.bin", large_test_content)

        assert (backend_dir / "large.bin").read_bytes() == large_test_content


class TestLocalStorageDelete:
    """Test delete() method."""

    def test_delete_existing_file(self, backend_dir: Path):
        """Test deleting existing file."""
        test_file = backend_dir / "test.txt"
        test_file.write_text("content")

        storage = LocalStorage(backend_dir)
        assert storage.delete("test.txt") is True
        assert not test_file.exists()

    def test_delete_missing_file_raises(self, backend_dir: Path):
        """Test deleting missing file raises FileNotFoundError."""
        storage = LocalStorage(backend_dir)
        with pytest.raises(FileNotFoundError):
            storage.delete("nonexistent.txt")

    def test_delete_directory_raises(self, backend_dir: Path):
        """Test deleting directory raises IOError."""
        subdir = backend_dir / "subdir"
        subdir.mkdir()

        storage = LocalStorage(backend_dir)
        with pytest.raises(IOError, match="Not a regular file"):
            storage.delete("subdir")

    def test_delete_nested_file(self, backend_dir: Path):
        """Test deleting nested file."""
        nested = backend_dir / "a" / "b"
        nested.mkdir(parents=True)
        test_file = nested / "file.txt"
        test_file.write_text("content")

        storage = LocalStorage(backend_dir)
        storage.delete("a/b/file.txt")
        assert not test_file.exists()
        # Parent directories still exist
        assert nested.exists()


class TestLocalStorageList:
    """Test list() method."""

    def test_list_all_files(self, backend_dir: Path, test_files: dict):
        """Test listing all files."""
        storage = LocalStorage(backend_dir)
        files = storage.list()

        assert len(files) == len(test_files)
        for filename in test_files.keys():
            assert filename in files

    def test_list_empty_directory(self, backend_dir: Path):
        """Test listing empty directory returns empty list."""
        storage = LocalStorage(backend_dir)
        assert storage.list() == []

    def test_list_with_glob_pattern(self, backend_dir: Path):
        """Test listing with glob pattern."""
        # Create test files
        (backend_dir / "file1.txt").write_text("1")
        (backend_dir / "file2.txt").write_text("2")
        (backend_dir / "file3.pdf").write_text("3")

        storage = LocalStorage(backend_dir)

        txt_files = storage.list("*.txt")
        assert len(txt_files) == 2
        assert "file1.txt" in txt_files
        assert "file2.txt" in txt_files
        assert "file3.pdf" not in txt_files

    def test_list_with_nested_pattern(self, backend_dir: Path):
        """Test listing with nested glob pattern."""
        # Create nested structure
        (backend_dir / "a").mkdir()
        (backend_dir / "a" / "file1.txt").write_text("1")
        (backend_dir / "b").mkdir()
        (backend_dir / "b" / "file2.txt").write_text("2")

        storage = LocalStorage(backend_dir)

        # List all txt files recursively
        txt_files = storage.list("**/*.txt")
        assert len(txt_files) == 2

    def test_list_returns_relative_paths(self, backend_dir: Path):
        """Test list returns paths relative to base_dir."""
        nested = backend_dir / "a" / "b"
        nested.mkdir(parents=True)
        (nested / "file.txt").write_text("content")

        storage = LocalStorage(backend_dir)
        files = storage.list()

        assert "a/b/file.txt" in files
        # Should not contain absolute path
        assert not any(str(backend_dir) in f for f in files)


class TestLocalStorageSize:
    """Test size() method."""

    def test_size_of_file(self, backend_dir: Path):
        """Test getting file size."""
        content = b"Test content"
        test_file = backend_dir / "test.txt"
        test_file.write_bytes(content)

        storage = LocalStorage(backend_dir)
        assert storage.size("test.txt") == len(content)

    def test_size_missing_file_raises(self, backend_dir: Path):
        """Test size of missing file raises FileNotFoundError."""
        storage = LocalStorage(backend_dir)
        with pytest.raises(FileNotFoundError):
            storage.size("nonexistent.txt")

    def test_size_directory_raises(self, backend_dir: Path):
        """Test size of directory raises IOError."""
        subdir = backend_dir / "subdir"
        subdir.mkdir()

        storage = LocalStorage(backend_dir)
        with pytest.raises(IOError, match="Not a regular file"):
            storage.size("subdir")

    def test_size_empty_file(self, backend_dir: Path):
        """Test size of empty file is 0."""
        test_file = backend_dir / "empty.txt"
        test_file.write_bytes(b"")

        storage = LocalStorage(backend_dir)
        assert storage.size("empty.txt") == 0

    def test_size_large_file(self, backend_dir: Path, large_test_content: bytes):
        """Test size of large file."""
        test_file = backend_dir / "large.bin"
        test_file.write_bytes(large_test_content)

        storage = LocalStorage(backend_dir)
        assert storage.size("large.bin") == len(large_test_content)


class TestLocalStorageCopy:
    """Test copy() method."""

    def test_copy_file(self, backend_dir: Path):
        """Test copying file."""
        content = b"Original content"
        (backend_dir / "source.txt").write_bytes(content)

        storage = LocalStorage(backend_dir)
        assert storage.copy("source.txt", "dest.txt") is True

        assert (backend_dir / "source.txt").exists()
        assert (backend_dir / "dest.txt").exists()
        assert (backend_dir / "dest.txt").read_bytes() == content

    def test_copy_missing_file_raises(self, backend_dir: Path):
        """Test copying missing file raises FileNotFoundError."""
        storage = LocalStorage(backend_dir)
        with pytest.raises(FileNotFoundError):
            storage.copy("nonexistent.txt", "dest.txt")

    def test_copy_creates_parent_dirs(self, backend_dir: Path):
        """Test copy creates parent directories for destination."""
        (backend_dir / "source.txt").write_bytes(b"content")

        storage = LocalStorage(backend_dir)
        storage.copy("source.txt", "a/b/c/dest.txt")

        assert (backend_dir / "a" / "b" / "c" / "dest.txt").exists()

    def test_copy_overwrites_existing(self, backend_dir: Path):
        """Test copy overwrites existing destination file."""
        (backend_dir / "source.txt").write_bytes(b"new")
        (backend_dir / "dest.txt").write_bytes(b"old")

        storage = LocalStorage(backend_dir)
        storage.copy("source.txt", "dest.txt")

        assert (backend_dir / "dest.txt").read_bytes() == b"new"


class TestLocalStorageMove:
    """Test move() method."""

    def test_move_file(self, backend_dir: Path):
        """Test moving/renaming file."""
        content = b"Content to move"
        (backend_dir / "source.txt").write_bytes(content)

        storage = LocalStorage(backend_dir)
        assert storage.move("source.txt", "dest.txt") is True

        assert not (backend_dir / "source.txt").exists()
        assert (backend_dir / "dest.txt").exists()
        assert (backend_dir / "dest.txt").read_bytes() == content

    def test_move_missing_file_raises(self, backend_dir: Path):
        """Test moving missing file raises FileNotFoundError."""
        storage = LocalStorage(backend_dir)
        with pytest.raises(FileNotFoundError):
            storage.move("nonexistent.txt", "dest.txt")

    def test_move_creates_parent_dirs(self, backend_dir: Path):
        """Test move creates parent directories for destination."""
        (backend_dir / "source.txt").write_bytes(b"content")

        storage = LocalStorage(backend_dir)
        storage.move("source.txt", "a/b/c/dest.txt")

        assert not (backend_dir / "source.txt").exists()
        assert (backend_dir / "a" / "b" / "c" / "dest.txt").exists()


class TestLocalStorageGetPath:
    """Test get_path() method."""

    def test_get_path_returns_absolute(self, backend_dir: Path):
        """Test get_path returns absolute path."""
        storage = LocalStorage(backend_dir)
        path = storage.get_path("file.txt")

        assert Path(path).is_absolute()
        assert str(backend_dir) in path
        assert path.endswith("file.txt")

    def test_get_path_nested(self, backend_dir: Path):
        """Test get_path for nested file."""
        storage = LocalStorage(backend_dir)
        path = storage.get_path("a/b/file.txt")

        assert "a" in path
        assert "b" in path
        assert path.endswith("file.txt")


class TestLocalStorageSecurity:
    """Test security features."""

    def test_path_traversal_blocked_in_resolve(self, backend_dir: Path, temp_dir: Path):
        """Test path traversal is blocked in _resolve_path."""
        # Create file outside base_dir
        outside = temp_dir / "outside.txt"
        outside.write_text("outside")

        storage = LocalStorage(backend_dir)

        # Attempt to access via path traversal
        with pytest.raises(ValueError, match="outside base directory"):
            storage._resolve_path("../outside.txt")

    def test_absolute_path_blocked(self, backend_dir: Path, temp_dir: Path):
        """Test absolute path outside base_dir is blocked."""
        outside = temp_dir / "outside.txt"
        outside.write_text("outside")

        storage = LocalStorage(backend_dir)

        # Attempt to access via absolute path
        with pytest.raises(ValueError, match="outside base directory"):
            storage._resolve_path(str(outside))
