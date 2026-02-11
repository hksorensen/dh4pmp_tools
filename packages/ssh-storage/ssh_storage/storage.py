"""
PDF Storage Backends

Provides unified interface for storing PDFs locally, remotely, or with fallback.

Architecture:
    Storage (ABC)
    ├── LocalStorage - local filesystem
    ├── RemoteStorage - SSH-based remote storage
    └── FallbackStorage - primary/secondary with configurable write

Design principles:
- All operations return Path or raise exception (fail fast)
- Remote operations use existing SSH infrastructure
- FallbackStorage composes any two Storage backends
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Union
import subprocess
import logging

logger = logging.getLogger(__name__)


class Storage(ABC):
    """Abstract base class for PDF storage backends."""

    @abstractmethod
    def exists(self, identifier: str) -> bool:
        """
        Check if PDF exists in storage.

        Args:
            identifier: PDF identifier (e.g., "2001.00001v1.pdf" or DOI-based name)

        Returns:
            True if file exists
        """
        pass

    @abstractmethod
    def get_path(self, identifier: str) -> Path:
        """
        Get path to PDF file.

        Args:
            identifier: PDF identifier

        Returns:
            Path to file (may be local or remote mount point)

        Raises:
            FileNotFoundError: If file doesn't exist

        Note:
            For remote storage, this may return a path that requires
            SSH access to read. Use read() for actual content access.
        """
        pass

    @abstractmethod
    def write(self, identifier: str, source_path: Path) -> Path:
        """
        Write PDF to storage.

        Args:
            identifier: PDF identifier
            source_path: Local path to PDF file to write

        Returns:
            Path where file was written

        Raises:
            IOError: If write fails
        """
        pass

    @abstractmethod
    def delete(self, identifier: str) -> bool:
        """
        Delete PDF from storage.

        Args:
            identifier: PDF identifier

        Returns:
            True if deleted, False if didn't exist
        """
        pass

    @abstractmethod
    def list(self, pattern: Optional[str] = None) -> List[str]:
        """
        List PDF identifiers in storage.

        Args:
            pattern: Optional glob pattern to filter (e.g., "2001.*")

        Returns:
            List of identifiers
        """
        pass

    @abstractmethod
    def size(self, identifier: str) -> int:
        """
        Get file size in bytes.

        Args:
            identifier: PDF identifier

        Returns:
            Size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        pass

    @abstractmethod
    def read(self, identifier: str) -> bytes:
        """
        Read file content as bytes.

        Args:
            identifier: PDF identifier

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class LocalStorage(Storage):
    """Store PDFs on local filesystem."""

    def __init__(self, base_dir: Union[str, Path]):
        """
        Initialize local storage.

        Args:
            base_dir: Base directory for PDF storage
        """
        self.base_dir = Path(base_dir).expanduser().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"LocalStorage initialized: {self.base_dir}")

    def exists(self, identifier: str) -> bool:
        return (self.base_dir / identifier).exists()

    def get_path(self, identifier: str) -> Path:
        path = self.base_dir / identifier
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {identifier}")
        return path

    def write(self, identifier: str, source_path: Path) -> Path:
        dest_path = self.base_dir / identifier
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        import shutil
        shutil.copy2(source_path, dest_path)

        logger.debug(f"Written to local storage: {identifier}")
        return dest_path

    def delete(self, identifier: str) -> bool:
        path = self.base_dir / identifier
        if path.exists():
            path.unlink()
            logger.debug(f"Deleted from local storage: {identifier}")
            return True
        return False

    def list(self, pattern: Optional[str] = None) -> List[str]:
        if pattern:
            files = self.base_dir.glob(pattern)
        else:
            files = self.base_dir.glob("*.pdf")
        return [f.name for f in files if f.is_file()]

    def size(self, identifier: str) -> int:
        path = self.base_dir / identifier
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {identifier}")
        return path.stat().st_size

    def read(self, identifier: str) -> bytes:
        path = self.base_dir / identifier
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {identifier}")
        return path.read_bytes()

    def __repr__(self) -> str:
        return f"LocalStorage(base_dir={self.base_dir})"


class RemoteStorage(Storage):
    """Store PDFs on remote server via SSH."""

    def __init__(
        self,
        ssh_user: str,
        ssh_host: str,
        ssh_port: int,
        remote_base_dir: str,
        ssh_identity_file: Optional[str] = None,
    ):
        """
        Initialize remote storage.

        Args:
            ssh_user: SSH username
            ssh_host: SSH hostname
            ssh_port: SSH port
            remote_base_dir: Base directory on remote server (tilde will be expanded remotely)
            ssh_identity_file: Optional SSH key file (limits auth attempts)
        """
        self.ssh_user = ssh_user
        self.ssh_host = ssh_host
        self.ssh_port = ssh_port
        self.ssh_identity_file = ssh_identity_file

        self.ssh_target = f"{ssh_user}@{ssh_host}"
        self._ssh_args = self._build_ssh_args()

        # Expand tilde on remote machine if present
        if '~' in remote_base_dir:
            expanded = self._expand_remote_path(remote_base_dir)
            self.remote_base_dir = expanded
            logger.debug(f"RemoteStorage expanded {remote_base_dir} -> {expanded}")
        else:
            self.remote_base_dir = remote_base_dir

        logger.debug(f"RemoteStorage initialized: {self.ssh_target}:{self.remote_base_dir}")

    def _build_ssh_args(self) -> List[str]:
        """Build SSH command arguments."""
        args = []

        if self.ssh_port != 22:
            args.extend(["-p", str(self.ssh_port)])

        if self.ssh_identity_file:
            identity_path = Path(self.ssh_identity_file).expanduser()
            args.extend(["-o", "IdentitiesOnly=yes", "-i", str(identity_path)])

        # Connection settings
        args.extend([
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
        ])

        return args

    def _expand_remote_path(self, path: str) -> str:
        """Expand tilde in path on the remote machine.

        Args:
            path: Path that may contain tilde (e.g., "~/pdfs")

        Returns:
            Expanded absolute path on remote (e.g., "/home/user/pdfs")

        Note:
            This runs a Python command on the remote to expand the tilde,
            ensuring it expands to the remote user's home directory.
        """
        # Use Python on remote to expand the tilde
        cmd = f"python3 -c \"from pathlib import Path; print(Path('{path}').expanduser())\""
        result = self._run_ssh(cmd, check=True)
        expanded = result.stdout.strip()
        return expanded

    def _run_ssh(self, command: str, check: bool = True) -> subprocess.CompletedProcess:
        """Run SSH command on remote server."""
        cmd = ["ssh"] + self._ssh_args + [self.ssh_target, command]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if check and result.returncode != 0:
            raise RuntimeError(
                f"SSH command failed: {command}\n"
                f"Return code: {result.returncode}\n"
                f"Stderr: {result.stderr}"
            )

        return result

    def exists(self, identifier: str) -> bool:
        remote_path = f"{self.remote_base_dir}/{identifier}"
        result = self._run_ssh(f"test -f {remote_path}", check=False)
        return result.returncode == 0

    def get_path(self, identifier: str) -> Path:
        """
        Get remote path (for reference only).

        Note: This returns a remote path string wrapped in a Path object.
        The path is not accessible locally - use with remote operations only.
        """
        remote_path = f"{self.remote_base_dir}/{identifier}"

        # Check if exists
        if not self.exists(identifier):
            raise FileNotFoundError(f"PDF not found on remote: {identifier}")

        # Return as Path (but it's a remote path!)
        return Path(remote_path)

    def write(self, identifier: str, source_path: Path) -> Path:
        """
        Upload PDF to remote storage.

        Args:
            identifier: PDF identifier
            source_path: Local path to PDF file

        Returns:
            Remote path (as Path object)
        """
        remote_path = f"{self.remote_base_dir}/{identifier}"

        # Ensure remote directory exists
        remote_dir = str(Path(remote_path).parent)
        self._run_ssh(f"mkdir -p {remote_dir}")

        # Upload via rsync (more efficient than scp)
        rsync_cmd = [
            "rsync",
            "-az",
            "--progress",
        ]

        # Add SSH options for rsync
        ssh_cmd = "ssh " + " ".join(self._ssh_args)
        rsync_cmd.extend(["-e", ssh_cmd])

        rsync_cmd.extend([
            str(source_path),
            f"{self.ssh_target}:{remote_path}",
        ])

        result = subprocess.run(rsync_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise IOError(
                f"Failed to upload {identifier} to remote\n"
                f"Return code: {result.returncode}\n"
                f"Stderr: {result.stderr}"
            )

        logger.debug(f"Written to remote storage: {identifier}")
        return Path(remote_path)

    def delete(self, identifier: str) -> bool:
        remote_path = f"{self.remote_base_dir}/{identifier}"
        result = self._run_ssh(f"rm -f {remote_path}", check=False)

        if result.returncode == 0:
            logger.debug(f"Deleted from remote storage: {identifier}")
            return True
        return False

    def list(self, pattern: Optional[str] = None) -> List[str]:
        """
        List files on remote.

        Note: Returns basenames only, not full paths.
        """
        # Use find instead of ls for reliable tilde expansion and pattern matching
        if pattern:
            cmd = f"find {self.remote_base_dir}/ -maxdepth 1 -type f -name '{pattern}' -exec basename {{}} \\;"
        else:
            cmd = f"find {self.remote_base_dir}/ -maxdepth 1 -type f -name '*.pdf' -exec basename {{}} \\;"

        result = self._run_ssh(cmd, check=False)

        if result.returncode != 0:
            return []

        return [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]

    def size(self, identifier: str) -> int:
        """Get remote file size in bytes."""
        remote_path = f"{self.remote_base_dir}/{identifier}"

        # Use stat command (cross-platform: try Linux, fallback to macOS)
        cmd = f"stat -c '%s' {remote_path} 2>/dev/null || stat -f '%z' {remote_path}"
        result = self._run_ssh(cmd, check=False)

        if result.returncode != 0:
            raise FileNotFoundError(f"PDF not found on remote: {identifier}")

        return int(result.stdout.strip())

    def read(self, identifier: str) -> bytes:
        """Download and read file content from remote."""
        import tempfile

        remote_path = f"{self.remote_base_dir}/{identifier}"

        # Check if file exists first
        if not self.exists(identifier):
            raise FileNotFoundError(f"PDF not found on remote: {identifier}")

        # Download to temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Build scp command
            scp_cmd = ["scp"]

            # Add port if not default
            if self.ssh_port != 22:
                scp_cmd.extend(["-P", str(self.ssh_port)])

            # Add identity file if specified
            if self.ssh_identity_file:
                identity_path = Path(self.ssh_identity_file).expanduser()
                scp_cmd.extend(["-o", "IdentitiesOnly=yes", "-i", str(identity_path)])

            # Add connection settings
            scp_cmd.extend([
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=10",
            ])

            # Source and destination
            scp_cmd.extend([
                f"{self.ssh_target}:{remote_path}",
                str(tmp_path),
            ])

            # Download
            result = subprocess.run(scp_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise IOError(
                    f"Failed to download {identifier} from remote\n"
                    f"Return code: {result.returncode}\n"
                    f"Stderr: {result.stderr}"
                )

            # Read content
            content = tmp_path.read_bytes()
            logger.debug(f"Read {len(content):,} bytes from remote: {identifier}")
            return content

        finally:
            # Clean up temp file
            tmp_path.unlink(missing_ok=True)

    def __repr__(self) -> str:
        return f"RemoteStorage(ssh_target={self.ssh_target}, remote_base_dir={self.remote_base_dir})"


class FallbackStorage(Storage):
    """
    Storage with primary/secondary fallback and configurable write strategy.

    Read operations: Try primary first, fall back to secondary.
    Write operations: Configurable (primary, secondary, or both).
    """

    def __init__(
        self,
        primary: Storage,
        secondary: Storage,
        write_to: str = "primary",
    ):
        """
        Initialize fallback storage.

        Args:
            primary: Primary storage backend
            secondary: Secondary (fallback) storage backend
            write_to: Where to write new files:
                - "primary": Write to primary only
                - "secondary": Write to secondary only
                - "both": Write to both (redundant storage)

        Example:
            # Local primary, remote fallback (during migration)
            storage = FallbackStorage(
                primary=LocalStorage("data/pdfs"),
                secondary=RemoteStorage(...),
                write_to="both"  # Write to both during migration
            )
        """
        if write_to not in ("primary", "secondary", "both"):
            raise ValueError(f"Invalid write_to: {write_to}")

        self.primary = primary
        self.secondary = secondary
        self.write_to = write_to

        logger.debug(
            f"FallbackStorage initialized: primary={primary}, secondary={secondary}, write_to={write_to}"
        )

    def exists(self, identifier: str) -> bool:
        """Check primary first, then secondary."""
        return self.primary.exists(identifier) or self.secondary.exists(identifier)

    def get_path(self, identifier: str) -> Path:
        """Get path from primary first, then secondary."""
        if self.primary.exists(identifier):
            return self.primary.get_path(identifier)
        if self.secondary.exists(identifier):
            return self.secondary.get_path(identifier)
        raise FileNotFoundError(f"PDF not found in primary or secondary: {identifier}")

    def write(self, identifier: str, source_path: Path) -> Path:
        """
        Write to configured target(s).

        Returns:
            Path from primary write (if writing to primary or both)
        """
        written_path = None

        if self.write_to in ("primary", "both"):
            written_path = self.primary.write(identifier, source_path)
            logger.debug(f"Written to primary: {identifier}")

        if self.write_to in ("secondary", "both"):
            secondary_path = self.secondary.write(identifier, source_path)
            if written_path is None:
                written_path = secondary_path
            logger.debug(f"Written to secondary: {identifier}")

        return written_path

    def delete(self, identifier: str) -> bool:
        """
        Delete from both primary and secondary.

        Returns:
            True if deleted from at least one backend
        """
        deleted_primary = self.primary.delete(identifier)
        deleted_secondary = self.secondary.delete(identifier)
        return deleted_primary or deleted_secondary

    def list(self, pattern: Optional[str] = None) -> List[str]:
        """
        List files from both primary and secondary (deduplicated).

        Returns:
            Combined list of unique identifiers
        """
        primary_files = set(self.primary.list(pattern))
        secondary_files = set(self.secondary.list(pattern))
        return sorted(primary_files | secondary_files)

    def size(self, identifier: str) -> int:
        """Get size from primary first, then secondary."""
        if self.primary.exists(identifier):
            return self.primary.size(identifier)
        if self.secondary.exists(identifier):
            return self.secondary.size(identifier)
        raise FileNotFoundError(f"PDF not found in primary or secondary: {identifier}")

    def read(self, identifier: str) -> bytes:
        """Read from primary first, then secondary."""
        if self.primary.exists(identifier):
            return self.primary.read(identifier)
        if self.secondary.exists(identifier):
            return self.secondary.read(identifier)
        raise FileNotFoundError(f"PDF not found in primary or secondary: {identifier}")

    def __repr__(self) -> str:
        return (
            f"FallbackStorage(primary={self.primary}, secondary={self.secondary}, "
            f"write_to={self.write_to})"
        )


# ============================================================================
# Factory Functions
# ============================================================================

def create_storage_from_config(config) -> Storage:
    """
    Create storage backend from pipeline config.

    Args:
        config: Config object with storage settings

    Returns:
        Storage backend instance

    Example config.yaml:
        storage:
          backend: "fallback"  # or "local", "remote"

          local:
            arxiv_dir: "~/data/pdfs/arxiv"
            published_dir: "~/data/pdfs/published"

          remote:
            ssh_user: "user"
            ssh_endpoints:
              - ["192.168.1.183", 22]
              - ["remote.server.com", 8022]
            remote_base_dir: "~/pdfs"
            arxiv_subdir: "arxiv"
            published_subdir: "published"

          fallback:
            primary: "local"
            secondary: "remote"
            write_to: "both"
    """
    backend_type = config.storage.backend

    if backend_type == "local":
        # For now, return local storage for arxiv (can extend for published)
        return LocalStorage(config.storage.local.arxiv_dir)

    elif backend_type == "remote":
        # Use first working endpoint
        ssh_config = config.storage.remote
        ssh_host, ssh_port = ssh_config.ssh_endpoints[0]

        return RemoteStorage(
            ssh_user=ssh_config.ssh_user,
            ssh_host=ssh_host,
            ssh_port=ssh_port,
            remote_base_dir=f"{ssh_config.remote_base_dir}/{ssh_config.arxiv_subdir}",
            ssh_identity_file=getattr(ssh_config, 'ssh_identity_file', None),
        )

    elif backend_type == "fallback":
        fallback_config = config.storage.fallback

        # Create primary storage
        if fallback_config.primary == "local":
            primary = LocalStorage(config.storage.local.arxiv_dir)
        elif fallback_config.primary == "remote":
            ssh_config = config.storage.remote
            ssh_host, ssh_port = ssh_config.ssh_endpoints[0]
            primary = RemoteStorage(
                ssh_user=ssh_config.ssh_user,
                ssh_host=ssh_host,
                ssh_port=ssh_port,
                remote_base_dir=f"{ssh_config.remote_base_dir}/{ssh_config.arxiv_subdir}",
                ssh_identity_file=getattr(ssh_config, 'ssh_identity_file', None),
            )
        else:
            raise ValueError(f"Unknown primary storage type: {fallback_config.primary}")

        # Create secondary storage
        if fallback_config.secondary == "local":
            secondary = LocalStorage(config.storage.local.arxiv_dir)
        elif fallback_config.secondary == "remote":
            ssh_config = config.storage.remote
            ssh_host, ssh_port = ssh_config.ssh_endpoints[0]
            secondary = RemoteStorage(
                ssh_user=ssh_config.ssh_user,
                ssh_host=ssh_host,
                ssh_port=ssh_port,
                remote_base_dir=f"{ssh_config.remote_base_dir}/{ssh_config.arxiv_subdir}",
                ssh_identity_file=getattr(ssh_config, 'ssh_identity_file', None),
            )
        else:
            raise ValueError(f"Unknown secondary storage type: {fallback_config.secondary}")

        return FallbackStorage(
            primary=primary,
            secondary=secondary,
            write_to=fallback_config.write_to,
        )

    else:
        raise ValueError(f"Unknown storage backend: {backend_type}")
