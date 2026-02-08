"""Cached storage backend wrapper with local buffer."""

import time
from pathlib import Path
from typing import Dict, List, Optional, Union

from .base import StorageBackend
from .local import LocalStorage


class CachedStorage(StorageBackend):
    """Storage backend wrapper that adds local caching to any backend.

    Wraps another storage backend (e.g., RemoteStorage, APIStorage) and
    caches frequently accessed files locally to avoid repeated slow operations.

    This is especially useful for:
    - Remote storage over slow networks
    - API storage with rate limits
    - Cloud storage with egress costs

    The cache is write-through: writes go to both cache and backing storage.
    Reads check cache first, falling back to backing storage.

    Example:
        ```python
        # Cache remote storage locally
        remote = RemoteStorage(ssh_config={...}, remote_base_dir="~/pdfs")
        cached = CachedStorage(
            backend=remote,
            cache_dir="/tmp/pdf_cache",
            max_cache_size_mb=1000  # 1GB cache
        )

        # First read: downloads from remote and caches
        content = cached.read("paper.pdf")

        # Second read: served from cache (fast!)
        content = cached.read("paper.pdf")
        ```

    Args:
        backend: Underlying storage backend to cache
        cache_dir: Local directory for cache storage
        max_cache_size_mb: Maximum cache size in MB (None = unlimited)
        ttl_seconds: Time-to-live for cached files in seconds (None = no expiry)
    """

    def __init__(
        self,
        backend: StorageBackend,
        cache_dir: Union[str, Path],
        max_cache_size_mb: Optional[int] = None,
        ttl_seconds: Optional[int] = None
    ):
        """Initialize cached storage.

        Args:
            backend: Storage backend to wrap with caching
            cache_dir: Directory for local cache
            max_cache_size_mb: Max cache size in MB (None = unlimited)
            ttl_seconds: Cache entry TTL in seconds (None = no expiry)
        """
        self.backend = backend
        self.cache = LocalStorage(cache_dir, create_if_missing=True)
        self.max_cache_size_mb = max_cache_size_mb
        self.ttl_seconds = ttl_seconds

        # Metadata directory for tracking cache stats
        self.meta_dir = Path(cache_dir) / ".cache_meta"
        self.meta_dir.mkdir(exist_ok=True)

    def _is_cache_valid(self, identifier: str) -> bool:
        """Check if cached file is still valid (not expired).

        Args:
            identifier: File identifier

        Returns:
            True if cache entry is valid, False if expired
        """
        if not self.cache.exists(identifier):
            return False

        if self.ttl_seconds is None:
            return True  # No expiry

        # Check file age
        cache_path = Path(self.cache.get_path(identifier))
        age_seconds = time.time() - cache_path.stat().st_mtime

        return age_seconds < self.ttl_seconds

    def _get_cache_size_mb(self) -> float:
        """Get current cache size in MB.

        Returns:
            Cache size in megabytes
        """
        cache_dir = Path(self.cache.base_dir)
        total_bytes = sum(
            f.stat().st_size
            for f in cache_dir.rglob("*")
            if f.is_file()
        )
        return total_bytes / (1024 * 1024)

    def _evict_if_needed(self, incoming_size_bytes: int):
        """Evict old cache entries if cache size would exceed limit.

        Uses LRU (Least Recently Used) eviction strategy based on file access time.

        Args:
            incoming_size_bytes: Size of file about to be cached
        """
        if self.max_cache_size_mb is None:
            return  # No size limit

        incoming_size_mb = incoming_size_bytes / (1024 * 1024)
        current_size_mb = self._get_cache_size_mb()

        if current_size_mb + incoming_size_mb <= self.max_cache_size_mb:
            return  # Still have room

        # Need to evict - collect all cached files with access times
        cache_dir = Path(self.cache.base_dir)
        cached_files = [
            (f, f.stat().st_atime)  # (path, access_time)
            for f in cache_dir.rglob("*")
            if f.is_file() and not f.is_relative_to(self.meta_dir)
        ]

        # Sort by access time (oldest first)
        cached_files.sort(key=lambda x: x[1])

        # Evict oldest files until we have enough space
        space_needed_mb = current_size_mb + incoming_size_mb - self.max_cache_size_mb
        freed_mb = 0.0

        for file_path, _ in cached_files:
            if freed_mb >= space_needed_mb:
                break

            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            try:
                file_path.unlink()
                freed_mb += file_size_mb
            except OSError:
                pass  # Ignore errors during eviction

    def exists(self, identifier: str) -> bool:
        """Check if file exists (checks backend, not just cache).

        Args:
            identifier: File identifier

        Returns:
            True if file exists in backend, False otherwise
        """
        # Check backend (source of truth)
        return self.backend.exists(identifier)

    def read(self, identifier: str) -> bytes:
        """Read file content, using cache if available.

        Workflow:
        1. Check cache - if valid, return from cache
        2. Otherwise, read from backend
        3. Cache the result for future reads
        4. Return content

        Args:
            identifier: File identifier

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist in backend
            IOError: If read fails
        """
        # Check cache first
        if self._is_cache_valid(identifier):
            return self.cache.read(identifier)

        # Cache miss or expired - read from backend
        content = self.backend.read(identifier)

        # Cache the result
        try:
            self._evict_if_needed(len(content))
            self.cache.write(identifier, content)
        except Exception:
            # If caching fails, still return the content
            pass

        return content

    def write(self, identifier: str, content: bytes) -> bool:
        """Write file content (write-through to both cache and backend).

        Workflow:
        1. Write to backend (source of truth)
        2. If successful, update cache
        3. Return success

        Args:
            identifier: File identifier
            content: File content as bytes

        Returns:
            True if write succeeded

        Raises:
            IOError: If write to backend fails
        """
        # Write to backend first (source of truth)
        success = self.backend.write(identifier, content)

        if success:
            # Update cache
            try:
                self._evict_if_needed(len(content))
                self.cache.write(identifier, content)
            except Exception:
                # If caching fails, that's OK - backend write succeeded
                pass

        return success

    def delete(self, identifier: str) -> bool:
        """Delete file from both backend and cache.

        Args:
            identifier: File identifier

        Returns:
            True if delete succeeded

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If delete fails
        """
        # Delete from backend
        success = self.backend.delete(identifier)

        # Also remove from cache if present
        if self.cache.exists(identifier):
            try:
                self.cache.delete(identifier)
            except Exception:
                pass  # Cache cleanup is best-effort

        return success

    def list(self, pattern: Optional[str] = None) -> List[str]:
        """List files from backend (not cache).

        Args:
            pattern: Optional pattern filter

        Returns:
            List of file identifiers from backend

        Raises:
            IOError: If list operation fails
        """
        # List from backend (source of truth)
        return self.backend.list(pattern)

    def get_path(self, identifier: str) -> str:
        """Get path from backend.

        Note: Returns backend path, not cache path.

        Args:
            identifier: File identifier

        Returns:
            Path from backend
        """
        return self.backend.get_path(identifier)

    def size(self, identifier: str) -> int:
        """Get file size from backend.

        Args:
            identifier: File identifier

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If size check fails
        """
        return self.backend.size(identifier)

    def clear_cache(self):
        """Clear all cached files.

        Useful for:
        - Forcing fresh reads from backend
        - Reclaiming disk space
        - Testing
        """
        cache_dir = Path(self.cache.base_dir)
        for file_path in cache_dir.rglob("*"):
            if file_path.is_file() and not file_path.is_relative_to(self.meta_dir):
                try:
                    file_path.unlink()
                except OSError:
                    pass

    def get_cache_stats(self) -> Dict[str, float]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats:
            - size_mb: Current cache size in MB
            - file_count: Number of cached files
            - max_size_mb: Maximum cache size (None if unlimited)
        """
        cache_dir = Path(self.cache.base_dir)
        cached_files = [
            f for f in cache_dir.rglob("*")
            if f.is_file() and not f.is_relative_to(self.meta_dir)
        ]

        total_bytes = sum(f.stat().st_size for f in cached_files)

        return {
            "size_mb": total_bytes / (1024 * 1024),
            "file_count": len(cached_files),
            "max_size_mb": self.max_cache_size_mb
        }
