"""
Storage abstraction layer for managing files across different backends.

This module provides a unified interface for file storage operations that can
work with local filesystems, remote servers, APIs, or any other storage backend.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Union


class StorageBackend(ABC):
    """Abstract base class for storage backends.

    Defines a unified interface for file storage operations across different
    backends (local filesystem, remote SSH/SFTP, cloud storage, APIs, etc.).

    This abstraction enables:
    - Swapping storage backends without changing application code
    - Testing with mock storage backends
    - Caching layers on top of any backend
    - Future extensibility (API storage, cloud storage, etc.)

    Example:
        ```python
        # Use local storage
        storage = LocalStorage(base_dir="/data/pdfs")

        # Or use remote storage
        storage = RemoteStorage(ssh_config={...}, remote_base_dir="~/pdfs")

        # Application code works the same
        if storage.exists("paper.pdf"):
            content = storage.read("paper.pdf")
        ```
    """

    @abstractmethod
    def exists(self, identifier: str) -> bool:
        """Check if a file exists in storage.

        Args:
            identifier: File identifier (e.g., filename, path, key)

        Returns:
            True if file exists, False otherwise
        """
        pass

    @abstractmethod
    def read(self, identifier: str) -> bytes:
        """Read file content from storage.

        Args:
            identifier: File identifier to read

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If read operation fails
        """
        pass

    @abstractmethod
    def write(self, identifier: str, content: bytes) -> bool:
        """Write file content to storage.

        Args:
            identifier: File identifier to write
            content: File content as bytes

        Returns:
            True if write succeeded, False otherwise

        Raises:
            IOError: If write operation fails
        """
        pass

    @abstractmethod
    def delete(self, identifier: str) -> bool:
        """Delete a file from storage.

        Args:
            identifier: File identifier to delete

        Returns:
            True if delete succeeded, False otherwise

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If delete operation fails
        """
        pass

    @abstractmethod
    def list(self, pattern: Optional[str] = None) -> List[str]:
        """List files in storage, optionally filtered by pattern.

        Args:
            pattern: Optional glob pattern or regex to filter files.
                    Pattern syntax depends on backend implementation.
                    Examples: "*.pdf", "2024-*", "paper_[0-9]+.pdf"

        Returns:
            List of file identifiers matching the pattern

        Raises:
            IOError: If list operation fails
        """
        pass

    @abstractmethod
    def get_path(self, identifier: str) -> str:
        """Get the path/URL for a file.

        For local storage, returns filesystem path.
        For remote storage, may return remote path or URL.
        For API storage, may return API endpoint URL.

        Note: Not all backends support direct path access.
        Use exists() and read() for portable code.

        Args:
            identifier: File identifier

        Returns:
            Path, URL, or location string for the file
        """
        pass

    @abstractmethod
    def size(self, identifier: str) -> int:
        """Get file size in bytes.

        Args:
            identifier: File identifier

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If size check fails
        """
        pass

    def copy(self, source_id: str, dest_id: str) -> bool:
        """Copy a file within the same storage backend.

        Default implementation: read + write.
        Backends may override for more efficient native copy.

        Args:
            source_id: Source file identifier
            dest_id: Destination file identifier

        Returns:
            True if copy succeeded, False otherwise

        Raises:
            FileNotFoundError: If source file doesn't exist
            IOError: If copy operation fails
        """
        content = self.read(source_id)
        return self.write(dest_id, content)

    def move(self, source_id: str, dest_id: str) -> bool:
        """Move/rename a file within the same storage backend.

        Default implementation: copy + delete.
        Backends may override for more efficient native move.

        Args:
            source_id: Source file identifier
            dest_id: Destination file identifier

        Returns:
            True if move succeeded, False otherwise

        Raises:
            FileNotFoundError: If source file doesn't exist
            IOError: If move operation fails
        """
        if self.copy(source_id, dest_id):
            return self.delete(source_id)
        return False
