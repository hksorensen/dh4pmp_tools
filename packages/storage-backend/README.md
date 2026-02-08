# Storage Backend

A unified storage abstraction layer for Python that provides a consistent interface for file operations across different backends: local filesystem, remote SSH/SFTP servers, APIs, and more.

## Features

- **Unified Interface**: Same API works with any storage backend
- **Multiple Backends**: Local filesystem, remote SSH/SFTP (more coming: S3, APIs, etc.)
- **Caching Layer**: Add local caching to any backend for performance
- **Type-Safe**: Full type hints for IDE support
- **Extensible**: Easy to add new storage backends
- **Production-Ready**: Used in data pipeline processing 100K+ files

## Installation

```bash
pip install -e ~/Documents/dh4pmp_tools/packages/storage-backend
```

## Quick Start

### Local Storage

```python
from storage_backend import LocalStorage

# Create local storage backend
storage = LocalStorage(base_dir="/data/pdfs")

# Check if file exists
if storage.exists("paper.pdf"):
    content = storage.read("paper.pdf")

# Write new file
storage.write("new_paper.pdf", pdf_bytes)

# List all PDFs
pdfs = storage.list("*.pdf")

# Get file size
size = storage.size("paper.pdf")
```

### Remote Storage (SSH/SFTP)

```python
from storage_backend import RemoteStorage

# Create remote storage backend
storage = RemoteStorage(
    ssh_config={
        "user": "username",
        "endpoints": [
            ["192.168.1.100", 22],  # Try local network first
            ["example.com", 22]      # Fallback to external
        ]
    },
    remote_base_dir="~/pdfs"
)

# Same API as local storage!
if storage.exists("paper.pdf"):
    content = storage.read("paper.pdf")

storage.write("new_paper.pdf", pdf_bytes)
```

### Cached Storage (Performance)

```python
from storage_backend import CachedStorage, RemoteStorage

# Wrap remote storage with local cache
remote = RemoteStorage(ssh_config={...}, remote_base_dir="~/pdfs")
storage = CachedStorage(
    backend=remote,
    cache_dir="/tmp/pdf_cache",
    max_cache_size_mb=1000,  # 1GB cache
    ttl_seconds=3600         # 1 hour cache lifetime
)

# First read: downloads from remote and caches
content = storage.read("paper.pdf")  # Slow

# Second read: served from local cache
content = storage.read("paper.pdf")  # Fast!

# Check cache stats
stats = storage.get_cache_stats()
print(f"Cache size: {stats['size_mb']:.1f} MB")
print(f"Cached files: {stats['file_count']}")
```

## API Reference

### StorageBackend (Abstract Base Class)

All storage backends implement these methods:

- `exists(identifier: str) -> bool` - Check if file exists
- `read(identifier: str) -> bytes` - Read file content
- `write(identifier: str, content: bytes) -> bool` - Write file content
- `delete(identifier: str) -> bool` - Delete file
- `list(pattern: Optional[str] = None) -> List[str]` - List files (optional pattern filter)
- `get_path(identifier: str) -> str` - Get path/URL for file
- `size(identifier: str) -> int` - Get file size in bytes
- `copy(source_id: str, dest_id: str) -> bool` - Copy file
- `move(source_id: str, dest_id: str) -> bool` - Move/rename file

### LocalStorage

**Constructor:**
```python
LocalStorage(
    base_dir: Union[str, Path],
    create_if_missing: bool = True
)
```

**Features:**
- Stores files in local filesystem directory
- Automatic parent directory creation
- Security: prevents path traversal outside base_dir
- Optimized copy/move operations using `shutil`

### RemoteStorage

**Constructor:**
```python
RemoteStorage(
    ssh_config: Dict,
    remote_base_dir: str,
    auto_connect: bool = True
)
```

**SSH Config:**
```python
{
    "user": "username",
    "endpoints": [["host1", port1], ["host2", port2]],
    "connection_timeout": 2.0  # optional
}
```

**Features:**
- Automatic endpoint failover (tries each endpoint until one works)
- Uses SCP for file transfers
- SSH command execution for file operations
- Connection testing and validation

### CachedStorage

**Constructor:**
```python
CachedStorage(
    backend: StorageBackend,
    cache_dir: Union[str, Path],
    max_cache_size_mb: Optional[int] = None,
    ttl_seconds: Optional[int] = None
)
```

**Features:**
- Write-through caching (writes go to both cache and backend)
- LRU eviction when cache size exceeds limit
- TTL-based expiration
- Cache statistics and management
- Works with any storage backend

**Additional Methods:**
- `clear_cache()` - Remove all cached files
- `get_cache_stats() -> Dict` - Get cache size and file count

## Use Cases

### Data Pipelines

```python
# Process large corpus on remote GPU machine
# Store PDFs directly on remote to avoid upload bottleneck

from storage_backend import RemoteStorage

storage = RemoteStorage(ssh_config=gpu_config, remote_base_dir="~/pdfs")

# Download PDFs directly to remote
for paper_id in papers:
    pdf = download_pdf(paper_id)
    storage.write(f"{paper_id}.pdf", pdf)

# GPU machine can now process locally (no upload needed!)
```

### API Data with Caching

```python
# Future: API storage backend with local cache

from storage_backend import APIStorage, CachedStorage

api = APIStorage(api_key="...", endpoint="https://api.example.com")
storage = CachedStorage(
    backend=api,
    cache_dir="/tmp/api_cache",
    ttl_seconds=3600  # Cache for 1 hour
)

# First call: fetches from API
data = storage.read("dataset/123")

# Subsequent calls within 1 hour: served from cache (no API call!)
data = storage.read("dataset/123")
```

### Multi-Location File Management

```python
# Migrate files from local to remote

from storage_backend import LocalStorage, RemoteStorage

local = LocalStorage("/data/pdfs")
remote = RemoteStorage(ssh_config=config, remote_base_dir="~/pdfs")

# Copy all PDFs to remote
for pdf in local.list("*.pdf"):
    content = local.read(pdf)
    remote.write(pdf, content)
    print(f"Uploaded: {pdf}")
```

## Extending with New Backends

Create a new backend by subclassing `StorageBackend`:

```python
from storage_backend import StorageBackend

class S3Storage(StorageBackend):
    def __init__(self, bucket: str, prefix: str):
        self.bucket = bucket
        self.prefix = prefix
        self.s3 = boto3.client('s3')

    def exists(self, identifier: str) -> bool:
        key = f"{self.prefix}/{identifier}"
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except:
            return False

    def read(self, identifier: str) -> bytes:
        key = f"{self.prefix}/{identifier}"
        response = self.s3.get_object(Bucket=self.bucket, Key=key)
        return response['Body'].read()

    # Implement other abstract methods...
```

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run with coverage
pytest --cov=storage_backend tests/
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## Future Backends

Planned storage backends:
- **APIStorage** - REST APIs with rate limiting and pagination
- **S3Storage** - Amazon S3 and S3-compatible storage
- **GCSStorage** - Google Cloud Storage
- **DatabaseStorage** - Store files in database BLOBs
- **HTTPStorage** - Read-only HTTP/HTTPS file access

## Version History

- **0.1.0** (2026-02-08)
  - Initial release
  - LocalStorage, RemoteStorage, CachedStorage
  - Full type hints and documentation
