"""Local filesystem storage backend."""

import fnmatch
import shutil
from pathlib import Path
from typing import List, Optional, Union

from .base import StorageBackend


class LocalStorage(StorageBackend):
    """Storage backend for local filesystem.

    Stores files in a local directory on the filesystem.
    All file identifiers are treated as paths relative to base_dir.

    Example:
        ```python
        storage = LocalStorage(base_dir="/data/pdfs")

        # Check if file exists
        if storage.exists("paper.pdf"):
            content = storage.read("paper.pdf")

        # Write new file
        storage.write("new_paper.pdf", pdf_bytes)

        # List all PDFs
        pdfs = storage.list("*.pdf")
        ```

    Args:
        base_dir: Base directory for storage. Will be created if it doesn't exist.
        create_if_missing: Create base_dir if it doesn't exist (default: True)
    """

    def __init__(
        self,
        base_dir: Union[str, Path],
        create_if_missing: bool = True
    ):
        """Initialize local storage backend.

        Args:
            base_dir: Base directory for storage
            create_if_missing: Create directory if it doesn't exist

        Raises:
            ValueError: If base_dir doesn't exist and create_if_missing=False
        """
        self.base_dir = Path(base_dir).expanduser().resolve()

        if not self.base_dir.exists():
            if create_if_missing:
                self.base_dir.mkdir(parents=True, exist_ok=True)
            else:
                raise ValueError(f"Base directory does not exist: {self.base_dir}")

        if not self.base_dir.is_dir():
            raise ValueError(f"Base path is not a directory: {self.base_dir}")

    def _resolve_path(self, identifier: str) -> Path:
        """Resolve identifier to full filesystem path.

        Args:
            identifier: File identifier (relative path)

        Returns:
            Full resolved path within base_dir
        """
        path = (self.base_dir / identifier).resolve()

        # Security check: ensure path is within base_dir
        try:
            path.relative_to(self.base_dir)
        except ValueError:
            raise ValueError(
                f"Invalid identifier: '{identifier}' resolves outside base directory"
            )

        return path

    def exists(self, identifier: str) -> bool:
        """Check if file exists.

        Args:
            identifier: File identifier (relative path)

        Returns:
            True if file exists, False otherwise
        """
        try:
            path = self._resolve_path(identifier)
            return path.exists() and path.is_file()
        except (ValueError, OSError):
            return False

    def read(self, identifier: str) -> bytes:
        """Read file content.

        Args:
            identifier: File identifier (relative path)

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If read fails
        """
        path = self._resolve_path(identifier)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {identifier}")

        if not path.is_file():
            raise IOError(f"Not a regular file: {identifier}")

        return path.read_bytes()

    def write(self, identifier: str, content: bytes) -> bool:
        """Write file content.

        Creates parent directories if they don't exist.

        Args:
            identifier: File identifier (relative path)
            content: File content as bytes

        Returns:
            True if write succeeded

        Raises:
            IOError: If write fails
        """
        path = self._resolve_path(identifier)

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_bytes(content)
        return True

    def delete(self, identifier: str) -> bool:
        """Delete a file.

        Args:
            identifier: File identifier (relative path)

        Returns:
            True if delete succeeded

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If delete fails
        """
        path = self._resolve_path(identifier)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {identifier}")

        if not path.is_file():
            raise IOError(f"Not a regular file: {identifier}")

        path.unlink()
        return True

    def list(self, pattern: Optional[str] = None) -> List[str]:
        """List files, optionally filtered by glob pattern.

        Args:
            pattern: Optional glob pattern (e.g., "*.pdf", "2024-*/*.txt")
                    If None, returns all files recursively.

        Returns:
            List of file identifiers (relative paths from base_dir)

        Raises:
            IOError: If list operation fails
        """
        try:
            if pattern:
                # Use glob pattern
                matches = self.base_dir.glob(pattern)
                # Return only files (not directories), as relative paths
                return [
                    str(p.relative_to(self.base_dir))
                    for p in matches
                    if p.is_file()
                ]
            else:
                # Return all files recursively
                return [
                    str(p.relative_to(self.base_dir))
                    for p in self.base_dir.rglob("*")
                    if p.is_file()
                ]
        except OSError as e:
            raise IOError(f"Failed to list files: {e}")

    def get_path(self, identifier: str) -> str:
        """Get absolute filesystem path for a file.

        Args:
            identifier: File identifier (relative path)

        Returns:
            Absolute filesystem path as string
        """
        path = self._resolve_path(identifier)
        return str(path)

    def size(self, identifier: str) -> int:
        """Get file size in bytes.

        Args:
            identifier: File identifier (relative path)

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If size check fails
        """
        path = self._resolve_path(identifier)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {identifier}")

        if not path.is_file():
            raise IOError(f"Not a regular file: {identifier}")

        return path.stat().st_size

    def copy(self, source_id: str, dest_id: str) -> bool:
        """Copy a file (optimized for local filesystem).

        Args:
            source_id: Source file identifier
            dest_id: Destination file identifier

        Returns:
            True if copy succeeded

        Raises:
            FileNotFoundError: If source doesn't exist
            IOError: If copy fails
        """
        source_path = self._resolve_path(source_id)
        dest_path = self._resolve_path(dest_id)

        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_id}")

        # Create parent directories if needed
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(source_path, dest_path)
        return True

    def move(self, source_id: str, dest_id: str) -> bool:
        """Move/rename a file (optimized for local filesystem).

        Args:
            source_id: Source file identifier
            dest_id: Destination file identifier

        Returns:
            True if move succeeded

        Raises:
            FileNotFoundError: If source doesn't exist
            IOError: If move fails
        """
        source_path = self._resolve_path(source_id)
        dest_path = self._resolve_path(dest_id)

        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_id}")

        # Create parent directories if needed
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(source_path), str(dest_path))
        return True
