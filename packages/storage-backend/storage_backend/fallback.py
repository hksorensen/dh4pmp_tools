"""
Fallback storage implementation.

Tries primary storage first, falls back to secondary if not found.
Useful for:
- Gradual migrations between storage systems
- Multi-location redundancy
- Load balancing (local primary, remote fallback)
"""

from pathlib import Path
from typing import List, Optional

from .base import StorageBackend


class FallbackStorage(StorageBackend):
    """
    Fallback storage: try primary first, use secondary if not found.

    This storage backend wraps two other backends and tries them in order.
    Reads always try primary first, falling back to secondary only if the
    file doesn't exist in primary. Writes can go to primary, secondary, or both.

    Common use cases:
    - **Migration**: Local primary during migration, remote fallback for migrated files
    - **Redundancy**: Multiple locations for resilience
    - **Performance**: Fast local cache as primary, slower remote as fallback

    Example:
        >>> local = LocalStorage("/local/pdfs")
        >>> remote = RemoteStorage(ssh_config, "/remote/pdfs")
        >>> storage = FallbackStorage(local, remote)
        >>> # Reads try local first, then remote
        >>> data = storage.read("paper.pdf")  # Fast if local, slower if remote-only

    Args:
        primary: Primary storage backend (tried first)
        secondary: Secondary storage backend (fallback)
        write_to: Where to write new files ("primary", "secondary", "both")
    """

    def __init__(
        self,
        primary: StorageBackend,
        secondary: StorageBackend,
        write_to: str = "primary"
    ):
        """
        Initialize fallback storage.

        Args:
            primary: Primary storage backend
            secondary: Secondary storage backend
            write_to: Where to write files ("primary", "secondary", or "both")

        Raises:
            ValueError: If write_to is not one of the valid options
        """
        if write_to not in ("primary", "secondary", "both"):
            raise ValueError(f"write_to must be 'primary', 'secondary', or 'both', got: {write_to}")

        self.primary = primary
        self.secondary = secondary
        self.write_to = write_to

    def exists(self, identifier: str) -> bool:
        """Check if file exists in either primary or secondary storage."""
        return self.primary.exists(identifier) or self.secondary.exists(identifier)

    def read(self, identifier: str) -> bytes:
        """
        Read file, trying primary first, then secondary.

        Args:
            identifier: File identifier

        Returns:
            File contents as bytes

        Raises:
            FileNotFoundError: If file not found in either storage
        """
        # Try primary first (usually faster)
        if self.primary.exists(identifier):
            return self.primary.read(identifier)

        # Fall back to secondary
        if self.secondary.exists(identifier):
            return self.secondary.read(identifier)

        # Not found in either
        raise FileNotFoundError(f"File not found in primary or secondary storage: {identifier}")

    def write(self, identifier: str, content: bytes) -> bool:
        """
        Write file according to write_to strategy.

        Args:
            identifier: File identifier
            content: File contents as bytes

        Returns:
            True if write succeeded to all configured targets

        Raises:
            Exception: If write fails to any configured target
        """
        success = True

        if self.write_to in ("primary", "both"):
            success = success and self.primary.write(identifier, content)

        if self.write_to in ("secondary", "both"):
            success = success and self.secondary.write(identifier, content)

        return success

    def delete(self, identifier: str) -> bool:
        """
        Delete file from both primary and secondary storage.

        Args:
            identifier: File identifier

        Returns:
            True if deleted from at least one location
        """
        deleted_primary = False
        deleted_secondary = False

        if self.primary.exists(identifier):
            deleted_primary = self.primary.delete(identifier)

        if self.secondary.exists(identifier):
            deleted_secondary = self.secondary.delete(identifier)

        return deleted_primary or deleted_secondary

    def list(self, pattern: Optional[str] = None) -> List[str]:
        """
        List files from both storages, deduplicated.

        Args:
            pattern: Optional glob pattern to filter results

        Returns:
            Sorted list of unique identifiers from both storages
        """
        primary_files = set(self.primary.list(pattern))
        secondary_files = set(self.secondary.list(pattern))
        all_files = primary_files | secondary_files
        return sorted(all_files)

    def get_path(self, identifier: str) -> str:
        """
        Get file path, preferring primary storage.

        Args:
            identifier: File identifier

        Returns:
            Path from primary if exists there, otherwise secondary

        Raises:
            FileNotFoundError: If file not found in either storage
        """
        if self.primary.exists(identifier):
            return self.primary.get_path(identifier)

        if self.secondary.exists(identifier):
            return self.secondary.get_path(identifier)

        raise FileNotFoundError(f"File not found in primary or secondary storage: {identifier}")

    def size(self, identifier: str) -> int:
        """
        Get file size, trying primary first.

        Args:
            identifier: File identifier

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file not found in either storage
        """
        if self.primary.exists(identifier):
            return self.primary.size(identifier)

        if self.secondary.exists(identifier):
            return self.secondary.size(identifier)

        raise FileNotFoundError(f"File not found in primary or secondary storage: {identifier}")

    def copy(self, source: str, destination: str) -> bool:
        """
        Copy file, using storage where source exists.

        Args:
            source: Source identifier
            destination: Destination identifier

        Returns:
            True if copy succeeded

        Raises:
            FileNotFoundError: If source not found in either storage
        """
        # Find where source exists
        if self.primary.exists(source):
            return self.primary.copy(source, destination)
        elif self.secondary.exists(source):
            return self.secondary.copy(source, destination)
        else:
            raise FileNotFoundError(f"Source file not found in either storage: {source}")

    def move(self, source: str, destination: str) -> bool:
        """
        Move file, using storage where source exists.

        Args:
            source: Source identifier
            destination: Destination identifier

        Returns:
            True if move succeeded

        Raises:
            FileNotFoundError: If source not found in either storage
        """
        # Find where source exists
        if self.primary.exists(source):
            return self.primary.move(source, destination)
        elif self.secondary.exists(source):
            return self.secondary.move(source, destination)
        else:
            raise FileNotFoundError(f"Source file not found in either storage: {source}")

    def migrate_to_secondary(self, identifier: str, delete_primary: bool = False) -> bool:
        """
        Migrate a file from primary to secondary storage.

        Useful for gradual migration workflows.

        Args:
            identifier: File identifier
            delete_primary: If True, delete from primary after successful copy

        Returns:
            True if migration succeeded

        Raises:
            FileNotFoundError: If file not found in primary
        """
        if not self.primary.exists(identifier):
            raise FileNotFoundError(f"File not found in primary storage: {identifier}")

        # Read from primary
        content = self.primary.read(identifier)

        # Write to secondary
        success = self.secondary.write(identifier, content)

        # Optionally delete from primary
        if success and delete_primary:
            self.primary.delete(identifier)

        return success

    def migrate_to_primary(self, identifier: str, delete_secondary: bool = False) -> bool:
        """
        Migrate a file from secondary to primary storage.

        Useful for bringing files back from remote to local.

        Args:
            identifier: File identifier
            delete_secondary: If True, delete from secondary after successful copy

        Returns:
            True if migration succeeded

        Raises:
            FileNotFoundError: If file not found in secondary
        """
        if not self.secondary.exists(identifier):
            raise FileNotFoundError(f"File not found in secondary storage: {identifier}")

        # Read from secondary
        content = self.secondary.read(identifier)

        # Write to primary
        success = self.primary.write(identifier, content)

        # Optionally delete from secondary
        if success and delete_secondary:
            self.secondary.delete(identifier)

        return success
