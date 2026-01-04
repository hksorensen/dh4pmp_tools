"""
Database utilities for pandas DataFrames.

Provides unified interfaces for SQLite and MySQL databases with:
- Simple read/write operations
- UPSERT support (SQLite INSERT OR REPLACE/UPDATE)
- Schema management
- Bulk operations with transactions
"""

from .db import DB, SQLiteDB

# Optional MySQL support (requires sqlalchemy)
try:
    from .db import MySQL, CrossRef
    __all__ = ['DB', 'SQLiteDB', 'MySQL', 'CrossRef']
except ImportError:
    __all__ = ['DB', 'SQLiteDB']

__version__ = '0.1.0'
