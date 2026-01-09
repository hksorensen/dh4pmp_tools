"""DB interfaces
hkragh, January 2023
"""

import pandas as pd
import sqlite3
import csv
import tempfile


class DB():
    _filename = None
    def __init__(self, filename):
        self._filename = filename
    def get_conn(self):
        return sqlite3.connect(self._filename)
    def check_if_table_exists(self, table_name):
        conn = self.get_conn()
        df = pd.read_sql(f'SELECT name FROM sqlite_master WHERE type="table" AND name="{table_name}";', conn)
        conn.close()
        if len(df) == 0:
            return False
        elif len(df) == 1:
            return True
        else:
            raise ValueError(len(df))
    def get_tables(self):
        conn = self.get_conn()
        df_tables = pd.read_sql(f'SELECT name FROM sqlite_master WHERE type="table";', conn)
        conn.close()
        return df_tables['name'].to_list()
    def read_sql(self, sql, params=None):
        """
        Execute SQL query and return results as DataFrame.

        Args:
            sql: SQL query string
            params: Optional parameters for parameterized query (tuple, list, or dict)
                   Use ? placeholders in SQL for SQLite, %s for MySQL

        Returns:
            DataFrame with query results

        Examples:
            # Simple query
            df = db.read_sql("SELECT * FROM papers")

            # Parameterized query (prevents SQL injection)
            df = db.read_sql("SELECT * FROM papers WHERE year = ?", params=(2020,))
            df = db.read_sql("SELECT * FROM papers WHERE year = ? AND type = ?", params=(2020, 'article'))
        """
        cnx = self.get_conn()
        df = pd.read_sql(sql, cnx, params=params)
        cnx.close()
        return df
    def write_sql(self, df, table_name, replace:bool=False, **kwargs):
        cnx = self.get_conn()
        df.to_sql(table_name, cnx, if_exists='replace' if replace else 'append', index=False)
        cnx.close()


class SQLiteDB(DB):
    """
    Enhanced SQLite database interface matching MySQL API.

    Extends the basic DB class with:
    - Schema management (table_layout)
    - UPSERT operations (INSERT OR REPLACE/UPDATE)
    - Bulk operations with transactions
    - execute() for arbitrary SQL

    Usage:
        db = SQLiteDB('data.db')
        db.write_sql(df, 'table', upsert=True, conflict_keys=['id'])
    """

    def __init__(self, filename):
        super().__init__(filename)

    def execute(self, command: str):
        """
        Execute arbitrary SQL command.

        Args:
            command: SQL command to execute
        """
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute(command)
        conn.commit()
        conn.close()

    def write_sql(
        self,
        df: pd.DataFrame,
        table_name: str,
        replace: bool = False,
        if_exists: str = None,
        upsert: bool = False,
        conflict_keys: list = None,
        table_layout: dict = None,
        batch_size: int = 1000,
        **kwargs
    ):
        """
        Write DataFrame to SQLite table with advanced options.

        Args:
            df: DataFrame to write
            table_name: Name of table
            replace: If True, replace entire table (default: False)
            if_exists: How to behave if table exists ('replace', 'append', 'fail').
                      For compatibility with pandas/MySQL API (overrides replace param)
            upsert: If True, use INSERT OR REPLACE/UPDATE (default: False)
            conflict_keys: Columns to use for conflict resolution (required if upsert=True)
            table_layout: Dict of column types {column_name: sqlite_type}
            batch_size: Number of rows per transaction (default: 1000)
            **kwargs: Additional arguments (for compatibility)

        Examples:
            # Simple append
            db.write_sql(df, 'papers')

            # Replace table
            db.write_sql(df, 'papers', replace=True)

            # Upsert by DOI (INSERT OR REPLACE)
            db.write_sql(df, 'papers', upsert=True, conflict_keys=['doi'])

            # Custom schema
            db.write_sql(df, 'papers', table_layout={'doi': 'TEXT PRIMARY KEY', 'year': 'INTEGER'})
        """
        # Handle if_exists parameter for compatibility
        if if_exists is not None:
            replace = (if_exists == 'replace')

        conn = self.get_conn()

        # Create/replace table if needed
        if replace or not self.check_if_table_exists(table_name):
            if table_layout is not None:
                self._create_table_with_layout(table_name, df, table_layout, conn)
            else:
                # Use pandas default
                df[:0].to_sql(table_name, conn, if_exists='replace', index=False)

        # Write data
        if upsert:
            self._upsert_dataframe(df, table_name, conflict_keys, conn, batch_size)
        else:
            # Standard append
            df.to_sql(table_name, conn, if_exists='append', index=False)

        conn.commit()
        conn.close()

    def _create_table_with_layout(
        self,
        table_name: str,
        df: pd.DataFrame,
        types: dict,
        conn
    ):
        """
        Create table with custom column types.

        Args:
            table_name: Name of table
            df: DataFrame (for column names)
            types: Dict mapping column names to SQLite types
            conn: Database connection
        """
        # Build CREATE TABLE statement
        columns = []
        for col in df.columns:
            col_type = types.get(col, 'TEXT')  # Default to TEXT
            columns.append(f'"{col}" {col_type}')

        create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(columns)})'

        cursor = conn.cursor()
        cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        cursor.execute(create_sql)
        conn.commit()

    def _upsert_dataframe(
        self,
        df: pd.DataFrame,
        table_name: str,
        conflict_keys: list,
        conn,
        batch_size: int = 1000
    ):
        """
        Bulk upsert DataFrame using INSERT OR REPLACE or ON CONFLICT UPDATE.

        Args:
            df: DataFrame to upsert
            table_name: Table name
            conflict_keys: Columns to use for conflict detection
            conn: Database connection
            batch_size: Rows per transaction
        """
        if conflict_keys is None:
            raise ValueError("conflict_keys required for upsert mode")

        cursor = conn.cursor()
        columns = df.columns.tolist()

        # Check if table has UNIQUE/PRIMARY KEY constraints on conflict_keys
        schema_info = cursor.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        index_info = cursor.execute(f'PRAGMA index_list("{table_name}")').fetchall()

        # Get columns with PRIMARY KEY
        pk_columns = [row[1] for row in schema_info if row[5] == 1]  # row[5] is pk flag

        # Get columns with UNIQUE constraints
        unique_columns = set()
        for index_row in index_info:
            if index_row[2] == 1:  # unique flag
                index_name = index_row[1]
                index_cols = cursor.execute(f'PRAGMA index_info("{index_name}")').fetchall()
                unique_columns.update([row[2] for row in index_cols])  # row[2] is column name

        # Check if conflict_keys have constraints
        constraint_columns = set(pk_columns) | unique_columns
        has_constraints = all(key in constraint_columns for key in conflict_keys)

        placeholders = ', '.join(['?' for _ in columns])
        col_names = ', '.join([f'"{col}"' for col in columns])

        if has_constraints:
            # Use ON CONFLICT (requires existing constraints)
            conflict_cols = ', '.join([f'"{k}"' for k in conflict_keys])
            update_cols = [f'"{col}" = excluded."{col}"' for col in columns if col not in conflict_keys]

            if update_cols:
                insert_sql = f'''
                    INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})
                    ON CONFLICT({conflict_cols}) DO UPDATE SET {', '.join(update_cols)}
                '''
            else:
                # All columns are conflict keys
                insert_sql = f'INSERT OR IGNORE INTO "{table_name}" ({col_names}) VALUES ({placeholders})'
        else:
            # No constraints - need to manually handle upserts
            # Use DELETE + INSERT approach
            conflict_where = ' AND '.join([f'"{k}" = ?' for k in conflict_keys])

            for i in range(0, len(df), batch_size):
                batch = df.iloc[i:i+batch_size]

                for row in batch.values:
                    # Extract conflict key values
                    key_indices = [columns.index(k) for k in conflict_keys]
                    key_values = [row[idx] for idx in key_indices]

                    # Delete existing row
                    cursor.execute(f'DELETE FROM "{table_name}" WHERE {conflict_where}', key_values)

                    # Insert new row
                    cursor.execute(f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})', row)

                if (i + batch_size) % 10000 == 0:
                    conn.commit()

            conn.commit()
            return

        # Bulk insert in batches (when constraints exist)
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            cursor.executemany(insert_sql, batch.values.tolist())
            if (i + batch_size) % 10000 == 0:  # Commit every 10k rows
                conn.commit()

        conn.commit()

    def table_layout(self, table_name: str, df: pd.DataFrame, types: dict):
        """
        Create or modify table schema.

        Note: SQLite has limited ALTER TABLE support, so this recreates the table.

        Args:
            table_name: Name of table
            df: DataFrame with column structure
            types: Dict mapping column names to SQLite types
        """
        conn = self.get_conn()

        # Check if table exists and has data
        if self.check_if_table_exists(table_name):
            # Read existing data
            existing_df = pd.read_sql(f'SELECT * FROM "{table_name}"', conn)

            # Drop and recreate with new schema
            cursor = conn.cursor()
            cursor.execute(f'DROP TABLE "{table_name}"')

            # Create with new layout
            self._create_table_with_layout(table_name, df, types, conn)

            # Re-insert data if any existed
            if len(existing_df) > 0:
                existing_df.to_sql(table_name, conn, if_exists='append', index=False)
        else:
            # Create new table
            self._create_table_with_layout(table_name, df, types, conn)

        conn.commit()
        conn.close()

    def upsert(
        self,
        df: pd.DataFrame,
        table_name: str,
        conflict_keys: list,
        batch_size: int = 1000
    ):
        """
        Convenience method for upserting data.

        Equivalent to write_sql(..., upsert=True, conflict_keys=...)

        Args:
            df: DataFrame to upsert
            table_name: Table name
            conflict_keys: Columns to check for conflicts (e.g., ['doi'], ['id'])
            batch_size: Rows per batch
        """
        self.write_sql(
            df,
            table_name,
            upsert=True,
            conflict_keys=conflict_keys,
            batch_size=batch_size
        )

    def get_schema(self, table_name: str) -> pd.DataFrame:
        """
        Get table schema information.

        Args:
            table_name: Name of table

        Returns:
            DataFrame with columns: cid, name, type, notnull, dflt_value, pk
        """
        conn = self.get_conn()
        schema_df = pd.read_sql(f'PRAGMA table_info("{table_name}")', conn)
        conn.close()
        return schema_df

    def create_index(self, table_name: str, columns: list, unique: bool = False):
        """
        Create index on table columns.

        Args:
            table_name: Table name
            columns: List of column names
            unique: If True, create unique index
        """
        index_name = f"idx_{'_'.join(columns)}"
        unique_str = "UNIQUE" if unique else ""
        cols_str = ', '.join([f'"{col}"' for col in columns])

        sql = f'CREATE {unique_str} INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ({cols_str})'
        self.execute(sql)

    def read_table(self, table_name: str, columns: list = ['*']) -> pd.DataFrame:
        """
        Convenience method to read entire table or specific columns.

        Args:
            table_name: Name of table
            columns: List of column names or '*' for all columns.
                    Can also be comma-separated string.

        Returns:
            DataFrame with requested columns

        Examples:
            # Read entire table
            df = db.read_table('papers')

            # Read specific columns
            df = db.read_table('papers', columns=['title', 'year'])

            # Using string
            df = db.read_table('papers', columns='title, year')
        """
        if isinstance(columns, str):
            columns = [c.strip() for c in columns.split(',')]
        elif not isinstance(columns, list):
            raise TypeError(f"columns must be list or str, got {type(columns)}")

        # Build column list with proper quoting
        cols = ', '.join(f'"{c}"' if c != '*' else c for c in columns)
        return self.read_sql(f'SELECT {cols} FROM "{table_name}"')

    def delete(self, table_name: str, where_clause: str = 'FALSE'):
        """
        Delete rows from table matching WHERE clause.

        Args:
            table_name: Name of table
            where_clause: SQL WHERE clause (default: 'FALSE' deletes nothing)

        Examples:
            # Delete specific rows
            db.delete('papers', where_clause='year < 2020')

            # Delete all rows (use with caution!)
            db.delete('papers', where_clause='TRUE')

            # Delete by ID
            db.delete('papers', where_clause='id = 123')
        """
        sql = f'DELETE FROM "{table_name}" WHERE {where_clause}'
        self.execute(sql)


class MySQL():
    """MySQL database interface (requires sqlalchemy)."""
    _engine = None
    _engine_load = None
    _db_name = None

    def __init__(self, database_name: str, ip:str='db.henrikkragh.dk', port:int=3306):
        try:
            import sqlalchemy
            self._sqlalchemy = sqlalchemy  # Store for use in methods
        except ImportError:
            raise ImportError(
                "MySQL support requires sqlalchemy. "
                "Install with: pip install 'db_utils[mysql]'"
            )

        self._db_name = database_name
        self._engine = sqlalchemy.create_engine(f'mysql+mysqlconnector://dh4pmp:hkragh@{ip}:{port}/{self._db_name}', pool_pre_ping=True, connect_args={'connect_timeout':120})
        # self._engine_load = sqlalchemy.create_engine(f"mysql://dh4pmp:hkragh@{ip}:{port}/{self._db_name}?local_infile=1", pool_pre_ping=True, connect_args={'connect_timeout':120})
    def get_conn(self):
        return self._engine.connect()
    def check_if_table_exists(self, tablename) -> bool:
        _df = self.read_sql(f'SELECT TABLE_SCHEMA, TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA="{self._db_name}" AND TABLE_NAME="{tablename}";')
        return len(_df) != 0
    def read_sql(self, sql, params=None):
        """
        Execute SQL query and return results as DataFrame.

        Args:
            sql: SQL query string
            params: Optional parameters for parameterized query

        Returns:
            DataFrame with query results
        """
        cnx = self.get_conn()
        df = pd.read_sql(self._sqlalchemy.text(sql), cnx, params=params)
        cnx.close()
        return df
    def write_sql(self, df, table_name, replace:bool=False, direct:bool=False, table_layout:dict=None):
        if replace or not self.check_if_table_exists(tablename=table_name):
            cnx = self.get_conn()
            if table_layout is not None:
                # df[:0].to_sql(table_name, cnx, if_exists='replace', dtype=table_layout)
                self.table_layout(table_name=table_name, df=df, types=table_layout)
            else:
                # df[:0].to_sql(table_name, cnx, index=False, if_exists='replace')
                df[:0].to_sql(table_name, self._engine, index=False, if_exists='replace')
                cnx.commit()
            cnx.close()
        # elif not replace and table_layout is not None:
        #     raise Exception('Cannot change table layout without replacing table content.')

        if direct:
            # cnx = self.get_conn()
            # df.to_sql(table_name, cnx, if_exists='append', index=False)
            # cnx.commit()
            # cnx.close()
            df.to_sql(table_name, self._engine, if_exists='append', index=False)
        else:
            # load_options = "CHARACTER SET utf8 FIELDS ESCAPED BY '\\\\' OPTIONALLY ENCLOSED BY '\"' TERMINATED BY '\t' LINES TERMINATED BY '\n'"
            load_options = "FIELDS ESCAPED BY '\\\\' OPTIONALLY ENCLOSED BY '\"' TERMINATED BY '\t' LINES TERMINATED BY '\n'"
            with tempfile.NamedTemporaryFile() as f:
                df.to_csv(
                    f.name,
                    index=False, header=False, na_rep='NULL', sep='\t', lineterminator='\n',
                    doublequote=False, quoting=csv.QUOTE_NONNUMERIC, escapechar='\\'
                )
                sql = f'LOAD DATA LOCAL INFILE "{f.name}" INTO TABLE {table_name} {load_options};'
                cnx_load = self._engine_load.connect()
                cnx_load.execute(self._sqlalchemy.text(sql))
                cnx_load.commit()
                cnx_load.close()
    def get_tables(self):
        return self.read_sql('SHOW TABLES;')
    def table_layout(self, table_name:str, df:pd.DataFrame, types:dict):
        # print (df.info())
        cnx = self.get_conn()
        df[:0].to_sql(table_name, cnx, if_exists='replace', index=False)
        cnx.commit()
        for column, new_type in types.items():
            cnx.execute(self._sqlalchemy.text(f'ALTER TABLE `{table_name}` CHANGE COLUMN `{column}` `{column}` {new_type};'))
            # print (f'LAYOUT {table_name}: {column} --> {new_type}')
        cnx.commit()
        cnx.close()
    def execute(self, command:str):
        cnx = self.get_conn()
        cnx.execute(self._sqlalchemy.text(command))
        cnx.commit()
        cnx.close()


class CrossRef(MySQL):
    def __init__(self):
        super().__init__('crossref')
