"""
Network utilities for research workflows.

This package provides utilities for:
- VPN connectivity checks
- IP address utilities
- Network diagnostics
- SFTP file upload with progress bars

Usage:
    from network_utils import check_vpn_status, require_vpn

    # Check VPN before downloads
    require_vpn("130.225")

    # Or check with custom handling
    is_vpn, ip, msg = check_vpn_status("130.225")
    if not is_vpn:
        print(f"Warning: {msg}")

    # SFTP upload with progress bar
    from network_utils import SFTPUploader, upload_files_sftp

    # One-shot upload
    upload_files_sftp(
        local_paths=['img1.jpg', 'img2.jpg'],
        remote_dir='/remote/path/',
        host='server.com',
        user='myuser'
    )

    # Or reuse connection for multiple uploads
    with SFTPUploader('server.com', 'myuser') as uploader:
        uploader.upload_files(batch1_files, '/remote/batch1/')
        uploader.upload_files(batch2_files, '/remote/batch2/')
"""

from .vpn_check import (
    check_vpn_status,
    get_current_ip,
    check_vpn_interface,
    require_vpn,
)

from .sftp_utils import (
    SFTPUploader,
    upload_files_sftp,
)

__version__ = "0.1.0"
__author__ = "Henrik Kragh Sørensen"

__all__ = [
    # VPN utilities
    "check_vpn_status",
    "get_current_ip",
    "check_vpn_interface",
    "require_vpn",
    # SFTP utilities
    "SFTPUploader",
    "upload_files_sftp",
    # Add new utilities here as you create them:
    # From ip_utils.py:
    # "parse_ip_range",
    # "ip_in_subnet",
    # From http_utils.py:
    # "check_url_accessible",
    # "get_with_retry",
]
