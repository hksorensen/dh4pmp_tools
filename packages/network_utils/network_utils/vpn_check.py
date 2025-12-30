"""VPN and network connectivity checks for university access."""

import requests
import subprocess
from typing import Tuple, Optional, Union, List


def check_vpn_status(
    university_ip_prefix: Union[str, List[str]] = "130.225",
    timeout: int = 5
) -> Tuple[bool, Optional[str], str]:
    """
    Check if connected to university VPN by comparing public IP.

    This function determines whether you're connected to your university's
    VPN by checking if your public IP address starts with one of the expected
    university IP prefixes.

    Args:
        university_ip_prefix: Start of your university's IP range(s).
                             Can be a string or list of strings.
                             Examples:
                             - Single: "130.225"
                             - Multiple: ["130.225", "130.226"]
        timeout: Request timeout in seconds

    Returns:
        Tuple of (is_connected, current_ip, message):
            - is_connected (bool): True if on university network
            - current_ip (str or None): Your current public IP, or None if check failed
            - message (str): Human-readable status message

    Examples:
        >>> # Single prefix
        >>> is_vpn, ip, msg = check_vpn_status("130.225")
        >>> print(msg)
        ✓ Connected to university network (130.225.x.x)

        >>> # Multiple prefixes (KU has multiple ranges)
        >>> is_vpn, ip, msg = check_vpn_status(["130.225", "130.226"])
        >>> print(msg)
        ✓ Connected to university network (130.226.x.x)

        >>> if not is_vpn:
        ...     raise RuntimeError("Please connect to VPN!")
    """
    try:
        # Get public IP using ipify API
        response = requests.get(
            'https://api.ipify.org?format=json',
            timeout=timeout
        )
        response.raise_for_status()
        current_ip = response.json()['ip']

        # Normalize to list
        if isinstance(university_ip_prefix, str):
            prefixes = [university_ip_prefix]
        else:
            prefixes = university_ip_prefix

        # Check if IP starts with any university prefix
        matched_prefix = None
        for prefix in prefixes:
            if current_ip.startswith(prefix):
                matched_prefix = prefix
                break

        if matched_prefix:
            message = f"✓ Connected to university network ({current_ip})"
            return True, current_ip, message
        else:
            message = f"✗ NOT on university network (current IP: {current_ip})"
            return False, current_ip, message

    except requests.Timeout:
        return False, None, "✗ VPN check timed out (network issue?)"
    except requests.RequestException as e:
        return False, None, f"✗ Could not check VPN status: {e}"
    except Exception as e:
        return False, None, f"✗ Unexpected error checking VPN: {e}"


def get_current_ip(timeout: int = 5) -> Optional[str]:
    """
    Get your current public IP address.

    Useful for determining what IP prefix to use for VPN checks.

    Args:
        timeout: Request timeout in seconds

    Returns:
        Your public IP address as a string, or None if check failed

    Examples:
        >>> ip = get_current_ip()
        >>> if ip:
        ...     prefix = '.'.join(ip.split('.')[:2])
        ...     print(f"Your IP prefix: {prefix}")
    """
    try:
        response = requests.get(
            'https://api.ipify.org?format=json',
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()['ip']
    except Exception:
        return None


def check_vpn_interface(interface_name: str = "utun") -> bool:
    """
    Check if VPN network interface is active (macOS/Linux).

    This is an alternative to IP-based checking. It looks for active
    network interfaces that match VPN naming patterns.

    Args:
        interface_name: VPN interface name prefix to look for
                       - "utun" for most macOS VPNs
                       - "tun0" for many Linux VPNs
                       - "ppp0" for some PPP-based VPNs

    Returns:
        True if interface found, False otherwise

    Examples:
        >>> if check_vpn_interface("utun"):
        ...     print("VPN interface detected")

    Note:
        This method is less reliable than IP-based checking because:
        - Interface names vary by VPN software
        - Interface might exist but not be routing traffic
        - Requires ifconfig to be available
    """
    try:
        result = subprocess.run(
            ['ifconfig'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return interface_name in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def require_vpn(
    university_ip_prefix: Union[str, List[str]] = "130.225",
    error_message: Optional[str] = None
) -> None:
    """
    Require VPN connection or raise an error.

    Convenient function to ensure VPN is connected before proceeding
    with operations that require university network access.

    Args:
        university_ip_prefix: Expected university IP prefix(es).
                             Can be a string or list of strings.
        error_message: Custom error message (optional)

    Raises:
        RuntimeError: If not connected to VPN

    Examples:
        >>> # At start of notebook or script
        >>> require_vpn("130.225")
        >>> # Continues only if on VPN, otherwise raises error

        >>> # Multiple IP ranges (KU has several)
        >>> require_vpn(["130.225", "130.226"])

        >>> # With custom message
        >>> require_vpn("130.225", "MDPI downloads require university VPN!")
    """
    is_vpn, ip, msg = check_vpn_status(university_ip_prefix)

    if not is_vpn:
        if error_message:
            raise RuntimeError(f"{error_message}\n{msg}")
        else:
            raise RuntimeError(
                f"University VPN required but not connected.\n"
                f"{msg}\n"
                f"Please connect to VPN before proceeding."
            )
