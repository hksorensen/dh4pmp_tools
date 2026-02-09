# ssh-storage

Generic storage backends for managing files across local and remote (SSH) systems.

## Features

- **LocalStorage** - local filesystem operations
- **RemoteStorage** - remote filesystem via SSH (rsync + SSH commands)
- **FallbackStorage** - primary/secondary with configurable write strategy
- **Zero external dependencies** - uses only Python stdlib
- **Production-grade** - proper error handling, logging, cross-platform

## Installation

```bash
pip install -e .
```

## Quick Start

### Local Storage

```python
from ssh_storage import LocalStorage

storage = LocalStorage("~/pdfs")

# Write file
storage.write("paper.pdf", Path("/tmp/paper.pdf"))

# Check existence
if storage.exists("paper.pdf"):
    path = storage.get_path("paper.pdf")

# List files
files = storage.list("*.pdf")
```

### Remote Storage (SSH)

```python
from ssh_storage import RemoteStorage

storage = RemoteStorage(
    ssh_user="user",
    ssh_host="remote.server.com",
    ssh_port=22,
    remote_base_dir="~/pdfs",
    ssh_identity_file="~/.ssh/id_ed25519"  # Optional
)

# Same interface as LocalStorage
storage.write("paper.pdf", Path("/tmp/paper.pdf"))
if storage.exists("paper.pdf"):
    size = storage.size("paper.pdf")
```

### Fallback Storage

```python
from ssh_storage import LocalStorage, RemoteStorage, FallbackStorage

local = LocalStorage("~/pdfs")
remote = RemoteStorage(...)

# Try local first, fall back to remote
storage = FallbackStorage(
    primary=local,
    secondary=remote,
    write_to="both"  # or "primary" or "secondary"
)

# Reads from primary first, falls back to secondary
# Writes go to configured target(s)
storage.write("paper.pdf", Path("/tmp/paper.pdf"))
```

## Architecture

All backends implement the `Storage` abstract base class:

```python
class Storage(ABC):
    def exists(self, identifier: str) -> bool
    def get_path(self, identifier: str) -> Path
    def write(self, identifier: str, source_path: Path) -> Path
    def delete(self, identifier: str) -> bool
    def list(self, pattern: Optional[str] = None) -> List[str]
    def size(self, identifier: str) -> int
```

## Use Cases

- **Research data management** - store papers/datasets locally or on compute servers
- **Backup systems** - write to local + remote simultaneously
- **Migration** - fallback during transition (local→remote or vice versa)
- **Distributed computing** - access files on remote GPU/HPC systems

## Requirements

- Python 3.8+
- SSH access to remote servers (for RemoteStorage)
- rsync (for RemoteStorage uploads)

## Design Principles

- **Simple** - identifier = filename, no database/index layer
- **Composable** - FallbackStorage wraps any two Storage backends
- **Fail fast** - exceptions on errors, no silent failures
- **Production-grade** - proper logging, error messages, cross-platform

## License

MIT
