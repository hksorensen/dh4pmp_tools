"""Remote storage backend using SSH/SFTP."""

import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .base import StorageBackend


class RemoteStorage(StorageBackend):
    """Storage backend for remote filesystem via SSH/SFTP.

    Stores files on a remote server accessible via SSH.
    Uses SFTP for file operations and SSH for shell commands.

    Example:
        ```python
        storage = RemoteStorage(
            ssh_config={
                "user": "username",
                "endpoints": [["192.168.1.100", 22], ["example.com", 22]]
            },
            remote_base_dir="~/pdfs"
        )

        # Check if file exists on remote
        if storage.exists("paper.pdf"):
            content = storage.read("paper.pdf")

        # Write to remote
        storage.write("new_paper.pdf", pdf_bytes)
        ```

    Args:
        ssh_config: SSH configuration dict with keys:
            - user: SSH username (required)
            - endpoints: List of [host, port] pairs to try (required)
            - connection_timeout: Connection timeout in seconds (default: 2.0)
        remote_base_dir: Base directory on remote server
        auto_connect: Test connection on initialization (default: True)
    """

    def __init__(
        self,
        ssh_config: Dict,
        remote_base_dir: str,
        auto_connect: bool = True
    ):
        """Initialize remote storage backend.

        Args:
            ssh_config: SSH configuration dictionary
            remote_base_dir: Base directory on remote server
            auto_connect: Test connection on initialization

        Raises:
            ValueError: If required SSH config is missing
            ConnectionError: If auto_connect=True and connection fails
        """
        # Validate SSH config
        if not isinstance(ssh_config, dict):
            raise ValueError("ssh_config must be a dictionary")

        if "user" not in ssh_config:
            raise ValueError("ssh_config must contain 'user' key")

        if "endpoints" not in ssh_config or not ssh_config["endpoints"]:
            raise ValueError("ssh_config must contain 'endpoints' list")

        self.user = ssh_config["user"]
        self.endpoints = ssh_config["endpoints"]
        self.connection_timeout = ssh_config.get("connection_timeout", 2.0)
        self.remote_base_dir = remote_base_dir

        # Track working endpoint
        self.host: Optional[str] = None
        self.port: Optional[int] = None

        if auto_connect:
            if not self._find_working_endpoint():
                raise ConnectionError(
                    f"Failed to connect to any endpoint: {self.endpoints}"
                )

    def _find_working_endpoint(self) -> bool:
        """Find a working SSH endpoint from the configured list.

        Returns:
            True if a working endpoint was found, False otherwise
        """
        for host, port in self.endpoints:
            if self._test_connection(host, port):
                self.host = host
                self.port = port
                return True
        return False

    def _test_connection(self, host: str, port: int) -> bool:
        """Test SSH connection to host:port.

        Args:
            host: SSH host
            port: SSH port

        Returns:
            True if connection succeeds, False otherwise
        """
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-p", str(port),
                    "-o", "ConnectTimeout=2",
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "BatchMode=yes",
                    f"{self.user}@{host}",
                    "echo ok"
                ],
                capture_output=True,
                timeout=self.connection_timeout + 1,
                text=True
            )
            return result.returncode == 0 and "ok" in result.stdout
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False

    def _ensure_connection(self):
        """Ensure we have a working SSH connection.

        Raises:
            ConnectionError: If no working endpoint is available
        """
        if self.host is None or self.port is None:
            if not self._find_working_endpoint():
                raise ConnectionError(
                    f"No working SSH endpoint available: {self.endpoints}"
                )

    def _get_ssh_target(self) -> str:
        """Get SSH connection string.

        Returns:
            SSH target string (user@host)
        """
        self._ensure_connection()
        return f"{self.user}@{self.host}"

    def _get_ssh_port_args(self) -> List[str]:
        """Get SSH port arguments.

        Returns:
            List of SSH port arguments
        """
        self._ensure_connection()
        return ["-p", str(self.port)] if self.port != 22 else []

    def _run_ssh_command(self, command: str) -> subprocess.CompletedProcess:
        """Run a command on the remote server via SSH.

        Args:
            command: Shell command to run

        Returns:
            CompletedProcess object

        Raises:
            ConnectionError: If SSH connection fails
        """
        self._ensure_connection()

        ssh_cmd = [
            "ssh",
            *self._get_ssh_port_args(),
            "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=no",
            self._get_ssh_target(),
            command
        ]

        result = subprocess.run(ssh_cmd, capture_output=True, text=True)
        return result

    def _remote_path(self, identifier: str) -> str:
        """Get full remote path for an identifier.

        Args:
            identifier: File identifier

        Returns:
            Full remote path
        """
        # Remove leading slash if present to ensure it's relative
        identifier = identifier.lstrip("/")
        return f"{self.remote_base_dir}/{identifier}"

    def exists(self, identifier: str) -> bool:
        """Check if file exists on remote server.

        Args:
            identifier: File identifier

        Returns:
            True if file exists, False otherwise
        """
        try:
            remote_path = self._remote_path(identifier)
            result = self._run_ssh_command(f"test -f '{remote_path}' && echo exists")
            return result.returncode == 0 and "exists" in result.stdout
        except (ConnectionError, subprocess.SubprocessError):
            return False

    def read(self, identifier: str) -> bytes:
        """Read file from remote server.

        Uses SCP to download the file to a temporary location.

        Args:
            identifier: File identifier

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If read fails
        """
        if not self.exists(identifier):
            raise FileNotFoundError(f"Remote file not found: {identifier}")

        self._ensure_connection()
        remote_path = self._remote_path(identifier)

        # Use temporary file for download
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Download via SCP
            scp_cmd = [
                "scp",
                *self._get_ssh_port_args(),
                "-o", "ConnectTimeout=10",
                "-o", "StrictHostKeyChecking=no",
                f"{self._get_ssh_target()}:{remote_path}",
                tmp_path
            ]

            result = subprocess.run(scp_cmd, capture_output=True)
            if result.returncode != 0:
                raise IOError(f"Failed to download file: {result.stderr.decode()}")

            # Read downloaded file
            return Path(tmp_path).read_bytes()

        finally:
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

    def write(self, identifier: str, content: bytes) -> bool:
        """Write file to remote server.

        Uses SCP to upload the file from a temporary location.

        Args:
            identifier: File identifier
            content: File content as bytes

        Returns:
            True if write succeeded

        Raises:
            IOError: If write fails
        """
        self._ensure_connection()
        remote_path = self._remote_path(identifier)

        # Write to temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Create parent directory on remote if needed
            remote_dir = str(Path(remote_path).parent)
            mkdir_result = self._run_ssh_command(f"mkdir -p '{remote_dir}'")
            if mkdir_result.returncode != 0:
                raise IOError(f"Failed to create remote directory: {mkdir_result.stderr}")

            # Upload via SCP
            scp_cmd = [
                "scp",
                *self._get_ssh_port_args(),
                "-o", "ConnectTimeout=10",
                "-o", "StrictHostKeyChecking=no",
                tmp_path,
                f"{self._get_ssh_target()}:{remote_path}"
            ]

            result = subprocess.run(scp_cmd, capture_output=True)
            if result.returncode != 0:
                raise IOError(f"Failed to upload file: {result.stderr.decode()}")

            return True

        finally:
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

    def delete(self, identifier: str) -> bool:
        """Delete file from remote server.

        Args:
            identifier: File identifier

        Returns:
            True if delete succeeded

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If delete fails
        """
        if not self.exists(identifier):
            raise FileNotFoundError(f"Remote file not found: {identifier}")

        remote_path = self._remote_path(identifier)
        result = self._run_ssh_command(f"rm '{remote_path}'")

        if result.returncode != 0:
            raise IOError(f"Failed to delete file: {result.stderr}")

        return True

    def list(self, pattern: Optional[str] = None) -> List[str]:
        """List files on remote server, optionally filtered by pattern.

        Args:
            pattern: Optional shell glob pattern (e.g., "*.pdf")

        Returns:
            List of file identifiers (relative to remote_base_dir)

        Raises:
            IOError: If list operation fails
        """
        # Build find command
        if pattern:
            # Use find with -name pattern
            cmd = f"cd '{self.remote_base_dir}' && find . -type f -name '{pattern}' 2>/dev/null | sed 's|^./||'"
        else:
            # List all files recursively
            cmd = f"cd '{self.remote_base_dir}' && find . -type f 2>/dev/null | sed 's|^./||'"

        result = self._run_ssh_command(cmd)

        if result.returncode != 0:
            raise IOError(f"Failed to list files: {result.stderr}")

        # Parse output (one file per line)
        files = [
            line.strip()
            for line in result.stdout.strip().split("\n")
            if line.strip()
        ]

        return files

    def get_path(self, identifier: str) -> str:
        """Get remote path for a file.

        Args:
            identifier: File identifier

        Returns:
            Full remote path (for reference only - not directly accessible)
        """
        return self._remote_path(identifier)

    def size(self, identifier: str) -> int:
        """Get file size on remote server.

        Args:
            identifier: File identifier

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If size check fails
        """
        if not self.exists(identifier):
            raise FileNotFoundError(f"Remote file not found: {identifier}")

        remote_path = self._remote_path(identifier)
        result = self._run_ssh_command(f"stat -f%z '{remote_path}' 2>/dev/null || stat -c%s '{remote_path}'")

        if result.returncode != 0:
            raise IOError(f"Failed to get file size: {result.stderr}")

        try:
            return int(result.stdout.strip())
        except ValueError:
            raise IOError(f"Invalid size output: {result.stdout}")
