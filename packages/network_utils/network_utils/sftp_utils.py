"""
SFTP Upload Utilities with Progress Bar

Provides simple SFTP upload functionality with visual progress bars using tqdm.
"""

from pathlib import Path
from typing import List, Optional, Union
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

try:
    import paramiko
    from tqdm import tqdm
    SFTP_AVAILABLE = True
except ImportError:
    SFTP_AVAILABLE = False
    paramiko = None
    tqdm = None

logger = logging.getLogger(__name__)


class SFTPUploader:
    """
    SFTP uploader with progress bar support.

    Features:
    - Visual progress bar for bulk uploads
    - Connection reuse across multiple uploads
    - Automatic directory creation
    - Error handling with detailed logging

    Example:
        >>> with SFTPUploader('user@host', port=22) as uploader:
        ...     uploader.upload_files(
        ...         local_paths=['file1.jpg', 'file2.jpg'],
        ...         remote_dir='/remote/path/'
        ...     )
    """

    def __init__(
        self,
        host: str,
        user: str,
        port: int = 22,
        password: Optional[str] = None,
        key_filename: Optional[str] = None,
        timeout: float = 10.0,
        verbose: bool = True
    ):
        """
        Initialize SFTP uploader.

        Args:
            host: Remote hostname or IP
            user: SSH username
            port: SSH port (default: 22)
            password: SSH password (optional, uses SSH keys if not provided)
            key_filename: Path to SSH private key (optional)
            timeout: Connection timeout in seconds
            verbose: Show progress bar
        """
        if not SFTP_AVAILABLE:
            raise ImportError(
                "paramiko and tqdm are required for SFTP upload. "
                "Install with: pip install paramiko tqdm"
            )

        self.host = host
        self.user = user
        self.port = port
        self.password = password
        self.key_filename = key_filename
        self.timeout = timeout
        self.verbose = verbose

        self._ssh_client = None
        self._sftp_client = None
        self._sftp_lock = Lock()  # Thread-safe SFTP operations

    def __enter__(self):
        """Context manager entry - establish connection."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection."""
        self.close()
        return False

    def connect(self):
        """Establish SSH and SFTP connection."""
        if self._ssh_client is not None:
            return  # Already connected

        try:
            self._ssh_client = paramiko.SSHClient()
            self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Connect
            connect_kwargs = {
                'hostname': self.host,
                'port': self.port,
                'username': self.user,
                'timeout': self.timeout,
                'look_for_keys': True,  # Try SSH agent and default keys
            }

            if self.password:
                connect_kwargs['password'] = self.password
            if self.key_filename:
                connect_kwargs['key_filename'] = self.key_filename

            self._ssh_client.connect(**connect_kwargs)
            self._sftp_client = self._ssh_client.open_sftp()

        except Exception as e:
            logger.error(f"Failed to connect to {self.user}@{self.host}:{self.port}: {e}")
            self.close()
            raise

    def close(self):
        """Close SFTP and SSH connections."""
        if self._sftp_client:
            try:
                self._sftp_client.close()
            except Exception:
                pass
            self._sftp_client = None

        if self._ssh_client:
            try:
                self._ssh_client.close()
            except Exception:
                pass
            self._ssh_client = None

    def mkdir_p(self, remote_path: str):
        """
        Create remote directory (like mkdir -p).

        Args:
            remote_path: Remote directory path to create
        """
        if not self._sftp_client:
            raise RuntimeError("Not connected - call connect() first")

        # Normalize path
        remote_path = remote_path.rstrip('/')

        # Try to create directory
        try:
            self._sftp_client.stat(remote_path)
            return  # Already exists
        except FileNotFoundError:
            pass

        # Create parent directories recursively
        parent = str(Path(remote_path).parent)
        if parent != '/' and parent != remote_path:
            self.mkdir_p(parent)

        # Create this directory
        try:
            self._sftp_client.mkdir(remote_path)
        except Exception as e:
            # Ignore if directory was created by another process
            try:
                self._sftp_client.stat(remote_path)
            except:
                raise e

    def upload_files(
        self,
        local_paths: List[Union[str, Path]],
        remote_dir: str,
        desc: Optional[str] = None,
        show_progress: Optional[bool] = None,
        max_workers: int = 10
    ) -> int:
        """
        Upload multiple files to remote directory with progress bar (parallel).

        Args:
            local_paths: List of local file paths to upload
            remote_dir: Remote directory (will be created if doesn't exist)
            desc: Progress bar description (default: "Uploading")
            show_progress: Override verbose setting for this upload
            max_workers: Number of parallel upload threads (default: 10)

        Returns:
            Number of files successfully uploaded

        Raises:
            RuntimeError: If not connected
            FileNotFoundError: If local file doesn't exist
        """
        if not self._sftp_client:
            raise RuntimeError("Not connected - call connect() first")

        # Ensure remote directory exists
        logger.debug(f"Creating remote directory: {remote_dir}")
        with self._sftp_lock:  # Thread-safe directory creation
            self.mkdir_p(remote_dir)
        remote_dir = remote_dir.rstrip('/') + '/'

        # Convert to Path objects
        local_paths = [Path(p) for p in local_paths]

        # Filter out missing files
        existing_paths = []
        missing_paths = []
        for path in local_paths:
            if path.exists():
                existing_paths.append(path)
            else:
                missing_paths.append(path)

        if missing_paths:
            logger.warning(f"{len(missing_paths)}/{len(local_paths)} files don't exist locally")
            logger.warning(f"  First missing: {missing_paths[0]}")
            if len(missing_paths) > 1:
                logger.warning(f"  Last missing: {missing_paths[-1]}")

        if not existing_paths:
            logger.warning("No files to upload")
            return 0

        # Upload with progress bar (parallel)
        show_bar = show_progress if show_progress is not None else self.verbose
        uploaded_count = 0
        failed_uploads = []

        def upload_single_file(local_path: Path) -> tuple:
            """Upload single file, return (path, success, error)."""
            remote_path = remote_dir + local_path.name
            try:
                # Thread-safe SFTP operation (paramiko SFTP client is not thread-safe)
                with self._sftp_lock:
                    self._sftp_client.put(str(local_path), remote_path)
                return (local_path, True, None)
            except Exception as e:
                return (local_path, False, str(e))

        # Use ThreadPoolExecutor for parallel uploads
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all uploads
            futures = {
                executor.submit(upload_single_file, path): path
                for path in existing_paths
            }

            # Track progress with tqdm
            if show_bar:
                progress = tqdm(
                    total=len(existing_paths),
                    desc=desc or "Uploading",
                    unit="file",
                    ncols=80,
                    leave=False
                )

            # Collect results as they complete
            for future in as_completed(futures):
                local_path, success, error = future.result()

                if success:
                    uploaded_count += 1
                else:
                    logger.error(f"Failed to upload {local_path.name}: {error}")
                    failed_uploads.append((local_path, error))

                if show_bar:
                    progress.update(1)

            if show_bar:
                progress.close()

        if failed_uploads:
            logger.error(f"{len(failed_uploads)}/{len(existing_paths)} uploads failed")
            logger.error(f"  First error: {failed_uploads[0][0].name} - {failed_uploads[0][1]}")

        return uploaded_count


def upload_files_sftp(
    local_paths: List[Union[str, Path]],
    remote_dir: str,
    host: str,
    user: str,
    port: int = 22,
    password: Optional[str] = None,
    key_filename: Optional[str] = None,
    desc: Optional[str] = None,
    verbose: bool = True,
    max_workers: int = 10
) -> int:
    """
    Convenience function to upload files via SFTP (one-shot, parallel).

    Creates connection, uploads files in parallel, and closes connection.
    For multiple uploads, use SFTPUploader context manager instead.

    Args:
        local_paths: List of local file paths
        remote_dir: Remote directory path
        host: Remote hostname
        user: SSH username
        port: SSH port
        password: SSH password (optional)
        key_filename: SSH private key path (optional)
        desc: Progress bar description
        verbose: Show progress bar
        max_workers: Number of parallel upload threads (default: 10)

    Returns:
        Number of files successfully uploaded

    Example:
        >>> uploaded = upload_files_sftp(
        ...     local_paths=['img1.jpg', 'img2.jpg'],
        ...     remote_dir='/remote/images/',
        ...     host='server.com',
        ...     user='myuser',
        ...     max_workers=20  # Upload 20 files at once
        ... )
        >>> print(f"Uploaded {uploaded} files")
    """
    with SFTPUploader(
        host=host,
        user=user,
        port=port,
        password=password,
        key_filename=key_filename,
        verbose=verbose
    ) as uploader:
        return uploader.upload_files(local_paths, remote_dir, desc=desc, max_workers=max_workers)
