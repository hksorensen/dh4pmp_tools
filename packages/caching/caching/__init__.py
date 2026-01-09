"""
Caching utilities for API data and string-based tracking.

Provides two complementary caching systems:
- LocalCache: For DataFrame/heavy data with pickle storage (JSON metadata)
- SQLiteLocalCache: For DataFrame/heavy data with SQLite metadata (faster)
- StringCache: For lightweight string data with status tracking
- SQLiteStringCache: Thread-safe SQLite variant for string caching

Also provides centralized path configuration:
- get_cache_dir(), get_data_dir(), get_results_dir()
- Supports optional config.yaml override
- Uses XDG Base Directory defaults
"""

from .local_cache import LocalCache, MultiQueryCache
from .sqlite_local_cache import SQLiteLocalCache
from .string_cache import StringCache
from .sqlite_string_cache import SQLiteStringCache
from .path_config import (
    get_cache_dir,
    get_data_dir,
    get_results_dir,
    get_path,
    get_path_config,
    print_path_config,
)

__version__ = "0.1.0"

__all__ = [
    'LocalCache',
    'SQLiteLocalCache',
    'MultiQueryCache',
    'StringCache',
    'SQLiteStringCache',
    'get_cache_dir',
    'get_data_dir',
    'get_results_dir',
    'get_path',
    'get_path_config',
    'print_path_config',
]
