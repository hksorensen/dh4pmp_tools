# db_utils

Database utilities for pandas DataFrames with unified interfaces for SQLite and MySQL.

## Features

### Low-Level Database API
- **Unified API** - Same interface for SQLite and MySQL
- **UPSERT Support** - SQLite `INSERT OR REPLACE` / `ON CONFLICT UPDATE`
- **Schema Management** - Define custom column types
- **Bulk Operations** - Efficient batch inserts with transactions
- **Simple to Use** - Familiar pandas-like interface

### High-Level Table Storage API
- **ID-Based Operations** - Get/delete by primary key
- **Automatic Encoding** - JSON serialization for complex data types
- **GZIP Compression** - Compress large text fields automatically
- **Smart Deduplication** - `store()` method avoids inserting duplicate IDs
- **Backend Agnostic** - Same code works with SQLite or MySQL

## Installation

```bash
# Basic installation (SQLite only)
pip install -e .

# With MySQL support
pip install -e ".[mysql]"
```

## Quick Start

### SQLite

```python
from db_utils import SQLiteDB
import pandas as pd

# Initialize
db = SQLiteDB('papers.db')

# Write data
papers = pd.DataFrame({
    'doi': ['10.1234/paper1', '10.1234/paper2'],
    'title': ['First Paper', 'Second Paper'],
    'year': [2020, 2021]
})

db.write_sql(papers, 'papers')

# Read data
result = db.read_sql('SELECT * FROM papers WHERE year >= 2020')

# Upsert (update if exists, insert if not)
updates = pd.DataFrame({
    'doi': ['10.1234/paper1', '10.1234/paper3'],  # paper1 exists, paper3 new
    'title': ['First Paper UPDATED', 'Third Paper'],
    'year': [2020, 2022]
})

db.write_sql(updates, 'papers', upsert=True, conflict_keys=['doi'])
# → paper1 updated, paper3 inserted
```

### MySQL

```python
from db_utils import MySQL

# Initialize
db = MySQL('my_database', ip='localhost', port=3306)

# Same API as SQLiteDB
db.write_sql(papers, 'papers')
result = db.read_sql('SELECT * FROM papers')
```

### TableStorage - High-Level API

For ID-based operations with automatic JSON/GZIP encoding:

```python
from db_utils import SQLiteTableStorage
import pandas as pd

# Initialize with encoding options
storage = SQLiteTableStorage(
    db_path='research.db',
    table_name='papers',
    column_ID='doi',
    ID_type=str,
    json_columns=['authors', 'keywords'],      # Auto JSON encode/decode
    gzip_columns=['abstract', 'full_text'],   # Auto GZIP compress/decompress
    table_layout={
        'doi': 'TEXT PRIMARY KEY',
        'title': 'TEXT',
        'year': 'INTEGER'
    }
)

# Prepare data with complex types
papers = pd.DataFrame({
    'doi': ['10.1234/a', '10.1234/b'],
    'title': ['Paper A', 'Paper B'],
    'year': [2020, 2021],
    'authors': [['Alice', 'Bob'], ['Charlie']],          # Lists auto-encoded to JSON
    'keywords': [['AI', 'ML'], ['Data Science']],        # Lists auto-encoded to JSON
    'abstract': ['Long text...' * 100, 'More text...']  # Strings auto-compressed
})

# Store data (automatic encoding + timestamping)
storage.write(papers)

# Retrieve data (automatic decoding + decompression)
result = storage.get()
print(result['authors'])  # Returns: [['Alice', 'Bob'], ['Charlie']]

# Get specific IDs
papers = storage.get(IDs=['10.1234/a'])

# Smart store - only inserts new IDs
new_papers = pd.DataFrame({
    'doi': ['10.1234/a', '10.1234/c'],  # 'a' exists, 'c' is new
    'title': ['Paper A', 'Paper C'],
    # ...
})
count = storage.store(new_papers)  # Only inserts 'c', returns 1

# Delete by IDs
storage.delete(['10.1234/b'])

# Get all IDs
all_ids = storage.get_ID_list()

# Count rows
total = storage.size()
recent = storage.size(where_clause='year >= 2020')
```

**Backend-Agnostic:** Use `MySQLTableStorage` for MySQL with identical API!

```python
from db_utils import MySQLTableStorage

storage = MySQLTableStorage(
    database_name='research',
    table_name='papers',
    column_ID='doi',
    # ... same parameters as SQLiteTableStorage
)
```

## API Reference

### Common Methods (DB, SQLiteDB, MySQL)

#### `write_sql(df, table_name, replace=False, **kwargs)`

Write DataFrame to database table.

**Parameters:**
- `df` (DataFrame): Data to write
- `table_name` (str): Name of table
- `replace` (bool): Replace entire table if True (default: False)

**SQLiteDB Additional Parameters:**
- `upsert` (bool): Use INSERT OR REPLACE/UPDATE (default: False)
- `conflict_keys` (list): Columns for conflict resolution (required if upsert=True)
- `table_layout` (dict): Custom column types {'col': 'TYPE'}
- `batch_size` (int): Rows per transaction (default: 1000)

**Example:**
```python
# Simple append
db.write_sql(df, 'papers')

# Replace table
db.write_sql(df, 'papers', replace=True)

# Upsert by DOI
db.write_sql(df, 'papers', upsert=True, conflict_keys=['doi'])

# Custom schema
db.write_sql(df, 'papers', table_layout={
    'doi': 'TEXT PRIMARY KEY',
    'year': 'INTEGER'
})
```

#### `read_sql(sql)`

Execute SQL query and return DataFrame.

**Parameters:**
- `sql` (str): SQL query

**Returns:**
- DataFrame with query results

**Example:**
```python
df = db.read_sql('SELECT * FROM papers WHERE year >= 2020')
```

#### `check_if_table_exists(table_name)`

Check if table exists in database.

**Parameters:**
- `table_name` (str): Name of table

**Returns:**
- bool: True if table exists

#### `get_tables()`

Get list of all tables in database.

**Returns:**
- list: Table names

### SQLiteDB-Specific Methods

#### `upsert(df, table_name, conflict_keys, batch_size=1000)`

Convenience method for upserting data.

**Parameters:**
- `df` (DataFrame): Data to upsert
- `table_name` (str): Table name
- `conflict_keys` (list): Columns to check for conflicts (e.g., ['doi'])
- `batch_size` (int): Rows per batch (default: 1000)

**Example:**
```python
db.upsert(updates_df, 'papers', conflict_keys=['doi'])
```

#### `execute(command)`

Execute arbitrary SQL command.

**Parameters:**
- `command` (str): SQL command

**Example:**
```python
db.execute('CREATE INDEX idx_year ON papers(year)')
```

#### `get_schema(table_name)`

Get table schema information.

**Parameters:**
- `table_name` (str): Table name

**Returns:**
- DataFrame with columns: name, type, notnull, dflt_value, pk

**Example:**
```python
schema = db.get_schema('papers')
print(schema[['name', 'type', 'pk']])
```

#### `create_index(table_name, columns, unique=False)`

Create index on table columns.

**Parameters:**
- `table_name` (str): Table name
- `columns` (list): Column names
- `unique` (bool): Create unique index (default: False)

**Example:**
```python
db.create_index('papers', ['year'])
db.create_index('papers', ['doi'], unique=True)
```

#### `table_layout(table_name, df, types)`

Create or modify table schema.

**Note:** SQLite has limited ALTER TABLE support, so this recreates the table.

**Parameters:**
- `table_name` (str): Table name
- `df` (DataFrame): DataFrame with column structure
- `types` (dict): Column types {'column': 'TYPE'}

**Example:**
```python
db.table_layout('papers', df, {
    'doi': 'TEXT PRIMARY KEY',
    'title': 'TEXT NOT NULL',
    'year': 'INTEGER',
    'citations': 'INTEGER DEFAULT 0'
})
```

## UPSERT Modes

SQLiteDB supports two UPSERT strategies:

### INSERT OR REPLACE

Simple replacement of entire row when conflict detected:

```python
db.write_sql(df, 'papers', upsert=True, conflict_keys=['doi'])
```

Generates:
```sql
INSERT INTO papers (doi, title, year) VALUES (?, ?, ?)
ON CONFLICT(doi) DO UPDATE SET title=excluded.title, year=excluded.year
```

### How It Works

1. **New rows**: Inserted normally
2. **Existing rows** (matching conflict_keys):
   - Non-conflict columns are updated
   - Conflict key columns remain unchanged

**Example:**
```python
# Initial data
papers = pd.DataFrame({
    'doi': ['10.1234/paper1'],
    'title': ['First Paper'],
    'year': [2020],
    'citations': [10]
})
db.write_sql(papers, 'papers', table_layout={'doi': 'TEXT PRIMARY KEY'})

# Update
updates = pd.DataFrame({
    'doi': ['10.1234/paper1'],  # Same DOI
    'title': ['First Paper UPDATED'],  # Changed
    'year': [2020],  # Same
    'citations': [15]  # Changed
})
db.write_sql(updates, 'papers', upsert=True, conflict_keys=['doi'])

# Result: title and citations updated, year unchanged
```

## Examples

### Example 1: Research Paper Database

```python
from db_utils import SQLiteDB
import pandas as pd

db = SQLiteDB('research.db')

# Define schema
schema = {
    'doi': 'TEXT PRIMARY KEY',
    'title': 'TEXT NOT NULL',
    'year': 'INTEGER',
    'citations': 'INTEGER DEFAULT 0',
    'pdf_path': 'TEXT'
}

# Create table with custom schema
papers = pd.DataFrame({
    'doi': ['10.1234/a', '10.1234/b'],
    'title': ['Paper A', 'Paper B'],
    'year': [2020, 2021],
    'citations': [10, 5]
})

db.write_sql(papers, 'papers', table_layout=schema)

# Add index for fast year queries
db.create_index('papers', ['year'])

# Update citation counts (upsert)
citations_update = pd.DataFrame({
    'doi': ['10.1234/a', '10.1234/c'],  # a exists, c is new
    'title': ['Paper A', 'Paper C'],
    'year': [2020, 2022],
    'citations': [15, 3]  # a: 10→15, c: new
})

db.upsert(citations_update, 'papers', conflict_keys=['doi'])

# Query
recent = db.read_sql('SELECT * FROM papers WHERE year >= 2021 ORDER BY citations DESC')
print(recent)
```

### Example 2: Incremental Data Loading

```python
from db_utils import SQLiteDB
import pandas as pd

db = SQLiteDB('data.db')

# Initial load
batch1 = pd.DataFrame({'id': [1, 2, 3], 'value': ['a', 'b', 'c']})
db.write_sql(batch1, 'data', table_layout={'id': 'INTEGER PRIMARY KEY'})

# Incremental updates (later batches may contain updates)
batch2 = pd.DataFrame({'id': [2, 4, 5], 'value': ['B', 'd', 'e']})  # id=2 updated
db.upsert(batch2, 'data', conflict_keys=['id'])

# Result: id=2 updated to 'B', id=4,5 added
result = db.read_sql('SELECT * FROM data ORDER BY id')
# id  value
#  1    a
#  2    B      <- updated
#  3    c
#  4    d      <- new
#  5    e      <- new
```

## Performance Tips

1. **Use batching** for large datasets:
   ```python
   db.write_sql(large_df, 'table', batch_size=5000, upsert=True, conflict_keys=['id'])
   ```

2. **Create indexes** on frequently queried columns:
   ```python
   db.create_index('papers', ['year'])
   db.create_index('papers', ['doi'], unique=True)
   ```

3. **Use transactions** (automatic in write_sql/upsert)

4. **Define schema upfront** with `table_layout` for better type handling

## Comparison: SQLiteDB vs MySQL

| Feature | SQLiteDB | MySQL |
|---------|----------|-------|
| Setup | File-based, no server | Requires MySQL server |
| UPSERT | ✅ Built-in | ❌ Manual via write_sql |
| Transactions | ✅ Automatic | ✅ Automatic |
| Bulk Loading | ✅ executemany | ✅ LOAD DATA INFILE |
| Concurrent Writes | ⚠️ Limited | ✅ Full support |
| Schema Changes | ⚠️ Recreates table | ✅ ALTER TABLE |

## License

Part of dh4pmp_tools package.

## Author

Henrik Kragh Sørensen

## TableStorage API Reference

### Initialization

```python
storage = SQLiteTableStorage(
    db_path='data.db',              # Path to SQLite database
    table_name='my_table',          # Name of table
    column_ID='id',                 # ID column name (default: 'ID')
    ID_type=str,                    # ID type: str or int (default: str)
    json_columns=['col1', 'col2'],  # Columns to JSON encode (default: [])
    gzip_columns=['col3'],          # Columns to GZIP compress (default: [])
    columns=None,                   # Specific columns to work with (default: all)
    table_layout={'id': 'TEXT PRIMARY KEY'}  # Column types (default: {})
)
```

### Core Methods

#### `write(df, timestamp=True)`
Replace entire table with DataFrame. Automatically encodes columns.

```python
storage.write(df)  # Adds timestamp column automatically
```

#### `store(df, timestamp=True)` → int
Insert only rows with new IDs (smart deduplication). Returns count of inserted rows.

```python
count = storage.store(df)  # Only inserts new IDs
```

#### `get(IDs=None, columns=None, where_clause='TRUE', offset=None, limit=None)` → DataFrame
Retrieve data with flexible filtering. Automatically decodes columns.

```python
# Get all rows
df = storage.get()

# Get specific IDs
df = storage.get(IDs=[123, 456])

# Get specific columns
df = storage.get(columns=['title', 'year'])

# Complex query
df = storage.get(where_clause='year >= 2020', limit=100, offset=10)
```

#### `delete(IDs)`
Delete rows by IDs.

```python
storage.delete([123, 456])
```

### Utility Methods

#### `exists()` → bool
Check if table exists.

```python
if storage.exists():
    print("Table found")
```

#### `get_ID_list()` → List
Get list of all IDs in table.

```python
all_ids = storage.get_ID_list()
```

#### `size(where_clause='TRUE')` → int
Count rows matching WHERE clause.

```python
total = storage.size()
recent = storage.size(where_clause='year >= 2020')
```

### Automatic Encoding/Decoding

**JSON Columns** - Automatically serialize/deserialize:
- Python lists → JSON strings (stored as TEXT)
- Python dicts → JSON strings
- NumPy arrays → JSON arrays

**GZIP Columns** - Automatically compress/decompress:
- Strings → Compressed bytes (stored as BLOB/LONGBLOB)
- Saves significant space for large text fields

**Example:**
```python
storage = SQLiteTableStorage(
    db_path='papers.db',
    table_name='papers',
    json_columns=['authors', 'metadata'],
    gzip_columns=['full_text', 'abstract']
)

# Writing
df = pd.DataFrame({
    'id': [1],
    'authors': [['Alice', 'Bob']],              # List → JSON
    'metadata': [{'year': 2020, 'venue': 'X'}], # Dict → JSON
    'full_text': ['Very long text...' * 1000]   # String → GZIP
})
storage.write(df)
# Stored as: authors='["Alice","Bob"]', full_text=b'\x1f\x8b...'

# Reading
result = storage.get()
print(result['authors'])   # Returns: [['Alice', 'Bob']]  (decoded)
print(result['metadata'])  # Returns: [{'year': 2020, ...}]  (decoded)
print(result['full_text']) # Returns: ['Very long text...'] (decompressed)
```

### Backend Comparison

| Feature | SQLiteTableStorage | MySQLTableStorage |
|---------|-------------------|-------------------|
| Setup | File-based | Requires MySQL server |
| ID Types | str, int | str, int |
| JSON Columns | TEXT | TEXT/JSON |
| GZIP Columns | BLOB | LONGBLOB |
| Performance | Fast for <100K rows | Scales to millions |
| Concurrent Writes | Limited | Full support |

### Migration from mysql_storage

If you're migrating from the old `mysql_storage` class:

```python
# Old (MySQL only)
from dh4pmp.db import mysql_storage

storage = mysql_storage(
    database_name='research',
    table_name='papers',
    column_ID='doi',
    ID_type=str,
    json_columns=['authors'],
    gzip_columns=['abstract']
)

# New (Backend-agnostic)
from db_utils import SQLiteTableStorage  # or MySQLTableStorage

storage = SQLiteTableStorage(
    db_path='research.db',  # Changed: db_path instead of database_name
    table_name='papers',
    column_ID='doi',
    ID_type=str,
    json_columns=['authors'],
    gzip_columns=['abstract']
)

# All methods work the same!
storage.write(df)
storage.store(df)
data = storage.get(IDs=['10.1234/a'])
```

**API is 100% compatible** - just change the import and initialization!

