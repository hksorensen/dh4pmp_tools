"""
Storage abstraction layer for unified file operations across backends.

Provides a clean interface for file storage that works with:
- Local filesystems (LocalStorage)
- Remote servers via SSH/SFTP (RemoteStorage)
- With caching for performance (CachedStorage)
- Fallback between storages (FallbackStorage)
- Extensible for future backends (APIStorage, CloudStorage, etc.)

Example usage:
    ```python
    from diagram_detector.storage import LocalStorage, RemoteStorage, CachedStorage

    # Local storage
    local = LocalStorage("/data/pdfs")
    if local.exists("paper.pdf"):
        content = local.read("paper.pdf")

    # Remote storage
    remote = RemoteStorage(
        ssh_config={"user": "username", "endpoints": [["host", 22]]},
        remote_base_dir="~/pdfs"
    )
    remote.write("paper.pdf", pdf_bytes)

    # Cached remote storage
    cached = CachedStorage(
        backend=remote,
        cache_dir="/tmp/cache",
        max_cache_size_mb=1000
    )
    content = cached.read("paper.pdf")  # Caches for future reads
    ```
"""

from .base import StorageBackend
from .local import LocalStorage
from .remote import RemoteStorage
from .cached import CachedStorage
from .fallback import FallbackStorage

__all__ = [
    "StorageBackend",
    "LocalStorage",
    "RemoteStorage",
    "CachedStorage",
    "FallbackStorage",
]

__version__ = "0.1.0"
