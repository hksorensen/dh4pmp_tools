"""Pytest configuration and fixtures for storage_backend tests."""

import tempfile
import shutil
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory that's cleaned up after the test."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def backend_dir(temp_dir: Path) -> Path:
    """Create a directory for backend storage."""
    backend = temp_dir / "backend"
    backend.mkdir()
    return backend


@pytest.fixture
def cache_dir(temp_dir: Path) -> Path:
    """Create a directory for cache storage."""
    cache = temp_dir / "cache"
    cache.mkdir()
    return cache


@pytest.fixture
def test_content() -> bytes:
    """Generate test file content."""
    return b"This is test content for storage backend testing."


@pytest.fixture
def large_test_content() -> bytes:
    """Generate large test file content (1 MB)."""
    return b"X" * (1024 * 1024)


@pytest.fixture
def test_files(backend_dir: Path) -> dict:
    """Create several test files and return their paths."""
    files = {
        "small.txt": b"Small file",
        "medium.txt": b"Medium " * 100,
        "subdir/nested.txt": b"Nested file",
    }

    for filename, content in files.items():
        filepath = backend_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(content)

    return files
