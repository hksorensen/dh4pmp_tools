"""
Table-level storage abstraction with automatic encoding/decoding.

Provides higher-level operations for storing and retrieving data with support
for JSON encoding, gzip compression, and ID-based record management.

Backend-agnostic: Works with SQLite, MySQL, or any database backend.
ATT: MySQLTableStorage is not completely agnostic as it uses a specific MySQL server per default.
"""

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
import json
import gzip
import datetime
from typing import Optional, List, Dict, Any, Union
from pathlib import Path


class TableStorage(ABC):
    """
    Abstract base class for table-level storage with encoding support.

    Provides ID-based operations, automatic JSON/GZIP encoding, and
    convenience methods for common data operations.

    Subclasses must implement backend-specific database operations.
    """

    def __init__(
        self,
        table_name: str,
        column_ID: str = 'ID',
        ID_type: type = str,
        json_columns: Optional[List[str]] = None,
        gzip_columns: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
        table_layout: Optional[Dict[str, str]] = None
    ):
        """
        Initialize TableStorage.

        Args:
            table_name: Name of the table
            column_ID: Name of the ID column (default: 'ID')
            ID_type: Data type of ID column (default: str)
            json_columns: Columns to JSON encode/decode (default: [])
            gzip_columns: Columns to gzip compress/decompress (default: [])
            columns: Specific columns to work with (default: None = all)
            table_layout: Column type specifications (default: {})

        Raises:
            ValueError: If ID column is in json_columns or gzip_columns
        """
        self._table_name = table_name
        self._column_ID = column_ID
        self._ID_type = ID_type
        self._columns = columns
        self._json_columns = json_columns or []
        self._gzip_columns = gzip_columns or []
        self._table_layout = table_layout or {}

        # Validation
        if self._column_ID in self._json_columns:
            raise ValueError(
                f'ID column {self._column_ID} cannot be json-encoded '
                f'({", ".join(self._json_columns)})'
            )
        if self._column_ID in self._gzip_columns:
            raise ValueError(
                f'ID column {self._column_ID} cannot be gzipped '
                f'({", ".join(self._gzip_columns)})'
            )

    # Abstract methods - must be implemented by subclasses

    @abstractmethod
    def _write_sql(self, df: pd.DataFrame, replace: bool, table_layout: dict):
        """Write DataFrame to database table."""
        pass

    @abstractmethod
    def _read_sql(self, sql: str) -> pd.DataFrame:
        """Execute SQL query and return DataFrame."""
        pass

    @abstractmethod
    def _execute(self, sql: str):
        """Execute SQL command."""
        pass

    @abstractmethod
    def _check_if_table_exists(self, table_name: str) -> bool:
        """Check if table exists."""
        pass

    # Concrete methods - shared logic across backends

    def _get_ID_list_sql(self, ID_list: List) -> str:
        """Convert Python list of IDs to SQL-compatible string."""
        if self._ID_type == int:
            return ", ".join([str(x) for x in ID_list])
        elif self._ID_type == str:
            return ", ".join([f'"{x}"' for x in ID_list])
        else:
            raise ValueError(f"Unsupported ID_type: {self._ID_type}")

    def _encode_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Encode JSON and GZIP columns in DataFrame.

        Args:
            df: DataFrame to encode

        Returns:
            DataFrame with encoded columns
        """
        df = df.copy()

        # Select specific columns if specified
        if self._columns is not None:
            df = df[self._columns]

        # JSON encode
        for col in [c for c in self._json_columns if c in df.columns]:
            df[col] = df[col].apply(
                lambda x: json.dumps(x.tolist()) if isinstance(x, np.ndarray)
                else json.dumps(x)
            )

        # GZIP compress
        for col in [c for c in self._gzip_columns if c in df.columns]:
            df[col] = df[col].apply(lambda x: gzip.compress(x.encode('utf-8')))

        return df

    def _decode_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Decode JSON and GZIP columns in DataFrame.

        Args:
            df: DataFrame to decode

        Returns:
            DataFrame with decoded columns
        """
        df = df.copy()

        # GZIP decompress
        for col in [c for c in self._gzip_columns if c in df.columns]:
            df[col] = df[col].apply(
                lambda data: gzip.decompress(data).decode('utf-8')
                if data is not None else None
            )

        # JSON decode
        for col in [c for c in self._json_columns if c in df.columns]:
            df[col] = df[col].apply(
                lambda data: json.loads(data) if data is not None else None
            )

        # Select specific columns if specified
        if self._columns is not None:
            df = df[[c for c in self._columns if c in df.columns]]

        return df

    def exists(self) -> bool:
        """Check if table exists in database."""
        return self._check_if_table_exists(self._table_name)

    def get_ID_list(self) -> List:
        """
        Get list of all IDs in table.

        Returns:
            List of IDs
        """
        if not self.exists():
            return []

        df = self.get(columns=self._column_ID)
        if df is None or len(df) == 0:
            return []

        return df[self._column_ID].tolist()

    def size(self, where_clause: str = 'TRUE') -> int:
        """
        Count rows in table matching WHERE clause.

        Args:
            where_clause: SQL WHERE clause (default: 'TRUE' = all rows)

        Returns:
            Number of rows
        """
        sql = f'SELECT COUNT(*) AS size FROM {self._table_name} WHERE {where_clause}'
        result = self._read_sql(sql)
        return result.iloc[0]['size']

    def write(self, df: pd.DataFrame, timestamp: bool = True):
        """
        Replace entire table with DataFrame.

        Args:
            df: DataFrame to write
            timestamp: If True, add timestamp column (default: True)
        """
        if len(df) == 0:
            return

        df = df.copy()

        # Add timestamp
        if timestamp and 'timestamp' not in df.columns:
            df['timestamp'] = datetime.datetime.now().isoformat()

        # Encode columns
        df = self._encode_columns(df)

        # Build table layout with LONGBLOB for gzip columns
        layout = self._table_layout.copy()
        for col in self._gzip_columns:
            layout[col] = 'LONGBLOB'  # MySQL
            # Note: SQLite will use BLOB automatically

        # Write to database (replace mode)
        self._write_sql(df, replace=True, table_layout=layout)

    def store(self, df: pd.DataFrame, timestamp: bool = True) -> int:
        """
        Store DataFrame, inserting only new IDs (avoids duplicates).

        Args:
            df: DataFrame to store
            timestamp: If True, add timestamp column (default: True)

        Returns:
            Number of rows stored (excluding duplicates)
        """
        if len(df) == 0:
            return 0

        df = df.copy()

        # Get existing IDs
        existing_IDs = []
        if self._check_if_table_exists(self._table_name):
            ID_list = self._get_ID_list_sql(df[self._column_ID].unique().tolist())
            if ID_list:
                sql = f'SELECT DISTINCT({self._column_ID}) FROM {self._table_name} WHERE {self._column_ID} IN ({ID_list})'
                result = self._read_sql(sql)
                existing_IDs = result[self._column_ID].tolist()

        # Filter to only new IDs
        df = df[~df[self._column_ID].isin(existing_IDs)].copy()

        if len(df) == 0:
            return 0

        # Add timestamp
        if timestamp and 'timestamp' not in df.columns:
            df['timestamp'] = datetime.datetime.now().isoformat()

        # Encode columns
        df = self._encode_columns(df)

        # Build table layout
        layout = self._table_layout.copy()
        for col in self._gzip_columns:
            layout[col] = 'LONGBLOB'

        # Write to database (append mode)
        self._write_sql(df, replace=False, table_layout=layout)

        return len(df)

    def get(
        self,
        IDs: Optional[List] = None,
        columns: Optional[List[str]] = None,
        where_clause: str = 'TRUE',
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve rows from table with flexible filtering.

        Args:
            IDs: List of IDs to retrieve (default: None = all)
            columns: Columns to retrieve (default: None = all)
            where_clause: SQL WHERE clause (default: 'TRUE')
            offset: Number of rows to skip (default: None)
            limit: Maximum rows to return (default: None)

        Returns:
            DataFrame with requested data, or None if table doesn't exist

        Examples:
            # Get specific IDs
            df = storage.get(IDs=[123, 456])

            # Get specific columns
            df = storage.get(columns=['title', 'year'])

            # Complex query
            df = storage.get(where_clause='year >= 2020', limit=100)
        """
        if not self._check_if_table_exists(self._table_name):
            print(f'Table `{self._table_name}` does not exist')
            return None

        # Build column list
        if columns is None:
            columns = ['*']
        elif isinstance(columns, str):
            columns = [c.strip() for c in columns.split(',')]

        def escape_column(c: str) -> str:
            if c == '*':
                return c
            if c.startswith('`') or c.startswith('"'):
                return c
            return f'`{c}`'

        cols = ", ".join(escape_column(c) for c in columns)

        # Build WHERE clause
        where_parts = []
        if isinstance(where_clause, str):
            where_parts.append(where_clause)
        elif isinstance(where_clause, list):
            where_parts.extend(where_clause)

        if IDs is not None:
            ID_list_sql = self._get_ID_list_sql(IDs)
            where_parts.append(f'{self._column_ID} IN ({ID_list_sql})')

        where_sql = " AND ".join(where_parts)

        # Build full query
        sql = f'SELECT {cols} FROM {self._table_name} WHERE {where_sql}'

        if limit is not None:
            sql += f' LIMIT {limit}'
        if offset is not None:
            sql += f' OFFSET {offset}'

        sql += ';'

        # Execute query
        df = self._read_sql(sql)

        # Decode columns
        df = self._decode_columns(df)

        return df

    def delete(self, IDs: List):
        """
        Delete rows by IDs.

        Args:
            IDs: List of IDs to delete
        """
        if len(IDs) == 0:
            return

        ID_list_sql = self._get_ID_list_sql(IDs)
        sql = f'DELETE FROM {self._table_name} WHERE {self._column_ID} IN ({ID_list_sql})'
        self._execute(sql)


class SQLiteTableStorage(TableStorage):
    """
    SQLite implementation of TableStorage.

    Uses SQLiteDB backend for all database operations.
    """

    def __init__(
        self,
        db_path: Union[str, Path],
        table_name: str,
        column_ID: str = 'ID',
        ID_type: type = str,
        json_columns: Optional[List[str]] = None,
        gzip_columns: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
        table_layout: Optional[Dict[str, str]] = None
    ):
        """
        Initialize SQLite table storage.

        Args:
            db_path: Path to SQLite database file
            table_name: Name of table
            column_ID: Name of ID column (default: 'ID')
            ID_type: Type of ID column (default: str)
            json_columns: Columns to JSON encode (default: [])
            gzip_columns: Columns to gzip compress (default: [])
            columns: Specific columns to work with (default: None)
            table_layout: Column type specifications (default: {})

        Example:
            storage = SQLiteTableStorage(
                db_path='papers.db',
                table_name='papers',
                column_ID='doi',
                ID_type=str,
                json_columns=['authors', 'metadata'],
                gzip_columns=['full_text']
            )
        """
        # Import here to avoid circular dependency
        from .db import SQLiteDB

        self._db = SQLiteDB(db_path)
        super().__init__(
            table_name=table_name,
            column_ID=column_ID,
            ID_type=ID_type,
            json_columns=json_columns,
            gzip_columns=gzip_columns,
            columns=columns,
            table_layout=table_layout
        )

    def _write_sql(self, df: pd.DataFrame, replace: bool, table_layout: dict):
        # SQLite uses BLOB instead of LONGBLOB
        layout = {k: v.replace('LONGBLOB', 'BLOB') for k, v in table_layout.items()}
        self._db.write_sql(df, self._table_name, replace=replace, table_layout=layout)

    def _read_sql(self, sql: str) -> pd.DataFrame:
        return self._db.read_sql(sql)

    def _execute(self, sql: str):
        self._db.execute(sql)

    def _check_if_table_exists(self, table_name: str) -> bool:
        return self._db.check_if_table_exists(table_name)


class MySQLTableStorage(TableStorage):
    """
    MySQL implementation of TableStorage.

    Uses MySQL backend for all database operations.
    """

    def __init__(
        self,
        database_name: str,
        table_name: str,
        column_ID: str = 'ID',
        ID_type: type = str,
        json_columns: Optional[List[str]] = None,
        gzip_columns: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
        table_layout: Optional[Dict[str, str]] = None,
        ip: str = 'db.henrikkragh.dk',
        port: int = 3306
    ):
        """
        Initialize MySQL table storage.

        Args:
            database_name: Name of MySQL database
            table_name: Name of table
            column_ID: Name of ID column (default: 'ID')
            ID_type: Type of ID column (default: str)
            json_columns: Columns to JSON encode (default: [])
            gzip_columns: Columns to gzip compress (default: [])
            columns: Specific columns to work with (default: None)
            table_layout: Column type specifications (default: {})
            ip: Database server IP (default: 'db.henrikkragh.dk')
            port: Database server port (default: 3306)

        Example:
            storage = MySQLTableStorage(
                database_name='research',
                table_name='papers',
                column_ID='doi',
                ID_type=str,
                json_columns=['authors'],
                gzip_columns=['full_text']
            )
        """
        # Import here to avoid circular dependency
        from .db import MySQL

        self._db = MySQL(database_name, ip=ip, port=port)
        super().__init__(
            table_name=table_name,
            column_ID=column_ID,
            ID_type=ID_type,
            json_columns=json_columns,
            gzip_columns=gzip_columns,
            columns=columns,
            table_layout=table_layout
        )

    def _write_sql(self, df: pd.DataFrame, replace: bool, table_layout: dict):
        self._db.write_sql(df, self._table_name, replace=replace, table_layout=table_layout)

    def _read_sql(self, sql: str) -> pd.DataFrame:
        return self._db.read_sql(sql)

    def _execute(self, sql: str):
        self._db.execute(sql)

    def _check_if_table_exists(self, table_name: str) -> bool:
        return self._db.check_if_table_exists(table_name)
