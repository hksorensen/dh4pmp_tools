"""Tests for FallbackStorage."""

import pytest
from pathlib import Path
from storage_backend import LocalStorage, FallbackStorage


@pytest.fixture
def primary_dir(tmp_path):
    """Primary storage directory."""
    return tmp_path / "primary"


@pytest.fixture
def secondary_dir(tmp_path):
    """Secondary storage directory."""
    return tmp_path / "secondary"


@pytest.fixture
def primary_storage(primary_dir):
    """Primary LocalStorage instance."""
    return LocalStorage(primary_dir)


@pytest.fixture
def secondary_storage(secondary_dir):
    """Secondary LocalStorage instance."""
    return LocalStorage(secondary_dir)


@pytest.fixture
def fallback_storage(primary_storage, secondary_storage):
    """FallbackStorage with default write_to='primary'."""
    return FallbackStorage(primary_storage, secondary_storage)


class TestFallbackStorageInit:
    """Test FallbackStorage initialization."""

    def test_init_valid(self, primary_storage, secondary_storage):
        """Test valid initialization."""
        storage = FallbackStorage(primary_storage, secondary_storage)
        assert storage.primary == primary_storage
        assert storage.secondary == secondary_storage
        assert storage.write_to == "primary"

    def test_init_custom_write_to(self, primary_storage, secondary_storage):
        """Test initialization with custom write_to."""
        storage = FallbackStorage(primary_storage, secondary_storage, write_to="secondary")
        assert storage.write_to == "secondary"

        storage = FallbackStorage(primary_storage, secondary_storage, write_to="both")
        assert storage.write_to == "both"

    def test_init_invalid_write_to(self, primary_storage, secondary_storage):
        """Test initialization with invalid write_to raises ValueError."""
        with pytest.raises(ValueError, match="write_to must be"):
            FallbackStorage(primary_storage, secondary_storage, write_to="invalid")


class TestFallbackStorageExists:
    """Test FallbackStorage.exists()."""

    def test_exists_in_primary(self, fallback_storage, primary_storage):
        """Test exists when file is in primary."""
        primary_storage.write("test.txt", b"primary")
        assert fallback_storage.exists("test.txt")

    def test_exists_in_secondary(self, fallback_storage, secondary_storage):
        """Test exists when file is in secondary only."""
        secondary_storage.write("test.txt", b"secondary")
        assert fallback_storage.exists("test.txt")

    def test_exists_in_both(self, fallback_storage, primary_storage, secondary_storage):
        """Test exists when file is in both storages."""
        primary_storage.write("test.txt", b"primary")
        secondary_storage.write("test.txt", b"secondary")
        assert fallback_storage.exists("test.txt")

    def test_exists_in_neither(self, fallback_storage):
        """Test exists returns False when file not found."""
        assert not fallback_storage.exists("nonexistent.txt")


class TestFallbackStorageRead:
    """Test FallbackStorage.read()."""

    def test_read_from_primary(self, fallback_storage, primary_storage):
        """Test read prefers primary when file exists there."""
        primary_storage.write("test.txt", b"primary content")
        content = fallback_storage.read("test.txt")
        assert content == b"primary content"

    def test_read_from_secondary(self, fallback_storage, secondary_storage):
        """Test read falls back to secondary when not in primary."""
        secondary_storage.write("test.txt", b"secondary content")
        content = fallback_storage.read("test.txt")
        assert content == b"secondary content"

    def test_read_prefers_primary_over_secondary(
        self, fallback_storage, primary_storage, secondary_storage
    ):
        """Test read prefers primary when file exists in both."""
        primary_storage.write("test.txt", b"primary content")
        secondary_storage.write("test.txt", b"secondary content")
        content = fallback_storage.read("test.txt")
        assert content == b"primary content"

    def test_read_not_found(self, fallback_storage):
        """Test read raises FileNotFoundError when file not in either storage."""
        with pytest.raises(FileNotFoundError, match="not found in primary or secondary"):
            fallback_storage.read("nonexistent.txt")


class TestFallbackStorageWrite:
    """Test FallbackStorage.write()."""

    def test_write_to_primary(self, primary_storage, secondary_storage):
        """Test write_to='primary' writes only to primary."""
        storage = FallbackStorage(primary_storage, secondary_storage, write_to="primary")
        storage.write("test.txt", b"content")

        assert primary_storage.exists("test.txt")
        assert not secondary_storage.exists("test.txt")

    def test_write_to_secondary(self, primary_storage, secondary_storage):
        """Test write_to='secondary' writes only to secondary."""
        storage = FallbackStorage(primary_storage, secondary_storage, write_to="secondary")
        storage.write("test.txt", b"content")

        assert not primary_storage.exists("test.txt")
        assert secondary_storage.exists("test.txt")

    def test_write_to_both(self, primary_storage, secondary_storage):
        """Test write_to='both' writes to both storages."""
        storage = FallbackStorage(primary_storage, secondary_storage, write_to="both")
        storage.write("test.txt", b"content")

        assert primary_storage.exists("test.txt")
        assert secondary_storage.exists("test.txt")
        assert primary_storage.read("test.txt") == b"content"
        assert secondary_storage.read("test.txt") == b"content"


class TestFallbackStorageDelete:
    """Test FallbackStorage.delete()."""

    def test_delete_from_primary(self, fallback_storage, primary_storage):
        """Test delete removes file from primary."""
        primary_storage.write("test.txt", b"content")
        assert fallback_storage.delete("test.txt")
        assert not primary_storage.exists("test.txt")

    def test_delete_from_secondary(self, fallback_storage, secondary_storage):
        """Test delete removes file from secondary."""
        secondary_storage.write("test.txt", b"content")
        assert fallback_storage.delete("test.txt")
        assert not secondary_storage.exists("test.txt")

    def test_delete_from_both(self, fallback_storage, primary_storage, secondary_storage):
        """Test delete removes file from both storages."""
        primary_storage.write("test.txt", b"content")
        secondary_storage.write("test.txt", b"content")
        assert fallback_storage.delete("test.txt")
        assert not primary_storage.exists("test.txt")
        assert not secondary_storage.exists("test.txt")

    def test_delete_not_found(self, fallback_storage):
        """Test delete returns False when file not found."""
        assert not fallback_storage.delete("nonexistent.txt")


class TestFallbackStorageList:
    """Test FallbackStorage.list()."""

    def test_list_combines_both_storages(
        self, fallback_storage, primary_storage, secondary_storage
    ):
        """Test list returns files from both storages, deduplicated."""
        primary_storage.write("file1.txt", b"content")
        primary_storage.write("file2.txt", b"content")
        secondary_storage.write("file2.txt", b"content")  # Duplicate
        secondary_storage.write("file3.txt", b"content")

        files = fallback_storage.list()
        assert set(files) == {"file1.txt", "file2.txt", "file3.txt"}

    def test_list_with_pattern(self, fallback_storage, primary_storage, secondary_storage):
        """Test list with glob pattern."""
        primary_storage.write("doc1.pdf", b"content")
        primary_storage.write("doc1.txt", b"content")
        secondary_storage.write("doc2.pdf", b"content")
        secondary_storage.write("doc2.txt", b"content")

        pdf_files = fallback_storage.list("*.pdf")
        assert set(pdf_files) == {"doc1.pdf", "doc2.pdf"}

    def test_list_empty(self, fallback_storage):
        """Test list returns empty list when no files."""
        assert fallback_storage.list() == []


class TestFallbackStorageGetPath:
    """Test FallbackStorage.get_path()."""

    def test_get_path_from_primary(self, fallback_storage, primary_storage, primary_dir):
        """Test get_path prefers primary."""
        primary_storage.write("test.txt", b"content")
        path = fallback_storage.get_path("test.txt")
        assert path == str(primary_dir / "test.txt")

    def test_get_path_from_secondary(
        self, fallback_storage, secondary_storage, secondary_dir
    ):
        """Test get_path falls back to secondary."""
        secondary_storage.write("test.txt", b"content")
        path = fallback_storage.get_path("test.txt")
        assert path == str(secondary_dir / "test.txt")

    def test_get_path_not_found(self, fallback_storage):
        """Test get_path raises FileNotFoundError when not found."""
        with pytest.raises(FileNotFoundError, match="not found in primary or secondary"):
            fallback_storage.get_path("nonexistent.txt")


class TestFallbackStorageSize:
    """Test FallbackStorage.size()."""

    def test_size_from_primary(self, fallback_storage, primary_storage):
        """Test size from primary storage."""
        primary_storage.write("test.txt", b"12345")
        assert fallback_storage.size("test.txt") == 5

    def test_size_from_secondary(self, fallback_storage, secondary_storage):
        """Test size from secondary storage."""
        secondary_storage.write("test.txt", b"123")
        assert fallback_storage.size("test.txt") == 3

    def test_size_not_found(self, fallback_storage):
        """Test size raises FileNotFoundError when not found."""
        with pytest.raises(FileNotFoundError, match="not found in primary or secondary"):
            fallback_storage.size("nonexistent.txt")


class TestFallbackStorageMigration:
    """Test FallbackStorage migration methods."""

    def test_migrate_to_secondary(self, fallback_storage, primary_storage, secondary_storage):
        """Test migrate_to_secondary copies file from primary to secondary."""
        primary_storage.write("test.txt", b"content")

        success = fallback_storage.migrate_to_secondary("test.txt")
        assert success
        assert primary_storage.exists("test.txt")
        assert secondary_storage.exists("test.txt")
        assert secondary_storage.read("test.txt") == b"content"

    def test_migrate_to_secondary_with_delete(
        self, fallback_storage, primary_storage, secondary_storage
    ):
        """Test migrate_to_secondary with delete_primary=True."""
        primary_storage.write("test.txt", b"content")

        success = fallback_storage.migrate_to_secondary("test.txt", delete_primary=True)
        assert success
        assert not primary_storage.exists("test.txt")
        assert secondary_storage.exists("test.txt")

    def test_migrate_to_secondary_not_found(self, fallback_storage):
        """Test migrate_to_secondary raises error when file not in primary."""
        with pytest.raises(FileNotFoundError, match="not found in primary"):
            fallback_storage.migrate_to_secondary("nonexistent.txt")

    def test_migrate_to_primary(self, fallback_storage, primary_storage, secondary_storage):
        """Test migrate_to_primary copies file from secondary to primary."""
        secondary_storage.write("test.txt", b"content")

        success = fallback_storage.migrate_to_primary("test.txt")
        assert success
        assert primary_storage.exists("test.txt")
        assert secondary_storage.exists("test.txt")
        assert primary_storage.read("test.txt") == b"content"

    def test_migrate_to_primary_with_delete(
        self, fallback_storage, primary_storage, secondary_storage
    ):
        """Test migrate_to_primary with delete_secondary=True."""
        secondary_storage.write("test.txt", b"content")

        success = fallback_storage.migrate_to_primary("test.txt", delete_secondary=True)
        assert success
        assert primary_storage.exists("test.txt")
        assert not secondary_storage.exists("test.txt")

    def test_migrate_to_primary_not_found(self, fallback_storage):
        """Test migrate_to_primary raises error when file not in secondary."""
        with pytest.raises(FileNotFoundError, match="not found in secondary"):
            fallback_storage.migrate_to_primary("nonexistent.txt")


class TestFallbackStorageCopyMove:
    """Test FallbackStorage copy and move operations."""

    def test_copy_from_primary(self, fallback_storage, primary_storage):
        """Test copy uses primary when source is there."""
        primary_storage.write("source.txt", b"content")
        fallback_storage.copy("source.txt", "dest.txt")

        assert primary_storage.exists("source.txt")
        assert primary_storage.exists("dest.txt")
        assert primary_storage.read("dest.txt") == b"content"

    def test_copy_from_secondary(self, fallback_storage, secondary_storage):
        """Test copy uses secondary when source only there."""
        secondary_storage.write("source.txt", b"content")
        fallback_storage.copy("source.txt", "dest.txt")

        assert secondary_storage.exists("source.txt")
        assert secondary_storage.exists("dest.txt")
        assert secondary_storage.read("dest.txt") == b"content"

    def test_copy_not_found(self, fallback_storage):
        """Test copy raises error when source not found."""
        with pytest.raises(FileNotFoundError, match="Source file not found"):
            fallback_storage.copy("nonexistent.txt", "dest.txt")

    def test_move_from_primary(self, fallback_storage, primary_storage):
        """Test move uses primary when source is there."""
        primary_storage.write("source.txt", b"content")
        fallback_storage.move("source.txt", "dest.txt")

        assert not primary_storage.exists("source.txt")
        assert primary_storage.exists("dest.txt")
        assert primary_storage.read("dest.txt") == b"content"

    def test_move_from_secondary(self, fallback_storage, secondary_storage):
        """Test move uses secondary when source only there."""
        secondary_storage.write("source.txt", b"content")
        fallback_storage.move("source.txt", "dest.txt")

        assert not secondary_storage.exists("source.txt")
        assert secondary_storage.exists("dest.txt")
        assert secondary_storage.read("dest.txt") == b"content"

    def test_move_not_found(self, fallback_storage):
        """Test move raises error when source not found."""
        with pytest.raises(FileNotFoundError, match="Source file not found"):
            fallback_storage.move("nonexistent.txt", "dest.txt")
