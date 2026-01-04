"""
Database utilities for pandas DataFrames.

Provides unified interfaces for SQLite and MySQL databases with:
- Simple read/write operations
- UPSERT support (SQLite INSERT OR REPLACE/UPDATE)
- Schema management
- Bulk operations with transactions
- Table-level storage with automatic JSON/GZIP encoding
"""

from .db import DB, SQLiteDB
from .storage import TableStorage, SQLiteTableStorage

# Optional MySQL support (requires sqlalchemy)
try:
    from .db import MySQL, CrossRef
    from .storage import MySQLTableStorage
    __all__ = ['DB', 'SQLiteDB', 'MySQL', 'CrossRef',
               'TableStorage', 'SQLiteTableStorage', 'MySQLTableStorage']
except ImportError:
    __all__ = ['DB', 'SQLiteDB', 'TableStorage', 'SQLiteTableStorage']

__version__ = '0.2.0'
