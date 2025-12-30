"""
Network utilities for research workflows.

This package provides utilities for:
- VPN connectivity checks
- IP address utilities
- Network diagnostics

Usage:
    from network_utils import check_vpn_status, require_vpn

    # Check VPN before downloads
    require_vpn("130.225")

    # Or check with custom handling
    is_vpn, ip, msg = check_vpn_status("130.225")
    if not is_vpn:
        print(f"Warning: {msg}")
"""

from .vpn_check import (
    check_vpn_status,
    get_current_ip,
    check_vpn_interface,
    require_vpn,
)

__version__ = "0.1.0"
__author__ = "Henrik Kragh Sørensen"

__all__ = [
    # VPN utilities
    "check_vpn_status",
    "get_current_ip",
    "check_vpn_interface",
    "require_vpn",
    # Add new utilities here as you create them:
    # From ip_utils.py:
    # "parse_ip_range",
    # "ip_in_subnet",
    # From http_utils.py:
    # "check_url_accessible",
    # "get_with_retry",
]
