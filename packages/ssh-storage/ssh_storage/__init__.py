"""
SSH Storage - Generic storage backends for local, remote (SSH), and fallback storage.

Simple, production-grade storage abstraction for managing files across
local and remote systems via SSH.
"""

from .storage import (
    Storage,
    LocalStorage,
    RemoteStorage,
    FallbackStorage,
    create_storage_from_config,
)

__version__ = "0.1.0"

__all__ = [
    "Storage",
    "LocalStorage",
    "RemoteStorage",
    "FallbackStorage",
    "create_storage_from_config",
]
