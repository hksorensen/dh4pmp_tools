# Network Utils

Network utilities for university research workflows, including VPN connectivity checks and network diagnostics.

## Installation

```bash
cd ~/Documents/dh4pmp_tools/packages/network_utils
pip install -e .
```

## Features

### VPN Connectivity Checks

Check if you're connected to your university VPN before running tasks that require university network access (e.g., downloading paywalled papers).

## Usage

### Quick Start

```python
from network_utils import require_vpn

# Require VPN or raise error
require_vpn("130.225")  # Replace with your university's IP prefix

# Now safe to proceed with university-only tasks
```

### Check VPN Status

```python
from network_utils import check_vpn_status

# Check if on VPN
is_vpn, current_ip, message = check_vpn_status("130.225")
print(message)

if not is_vpn:
    print(f"Your current IP: {current_ip}")
    print("Please connect to VPN")
```

### In Jupyter Notebooks

```python
from network_utils import check_vpn_status, get_current_ip

# At the start of your notebook
is_vpn, ip, msg = check_vpn_status("130.225")
print(msg)

if not is_vpn:
    raise RuntimeError("❌ Connect to university VPN before running!")

# Continue with downloads, API access, etc.
```

### Find Your University's IP Prefix

```python
from network_utils import get_current_ip

# Run this WHILE connected to VPN
current_ip = get_current_ip()
if current_ip:
    prefix = '.'.join(current_ip.split('.')[:2])
    print(f"Your university IP prefix: {prefix}")
    print(f"Use: require_vpn('{prefix}')")
```

### Common Use Cases

**Before PDF downloads:**
```python
from network_utils import require_vpn
from pdf_fetcher import BasePDFFetcher

# Ensure VPN is connected
require_vpn("130.225", "PDF downloads require university access!")

# Proceed with downloads
fetcher = BasePDFFetcher(output_dir="./pdfs")
results = fetcher.fetch_batch(dois)
```

**In data collection scripts:**
```python
from network_utils import check_vpn_status

is_vpn, _, msg = check_vpn_status("130.225")
if not is_vpn:
    print(f"Warning: {msg}")
    print("Some resources may not be accessible")

# Continue with warning
```

## API Reference

### `check_vpn_status(university_ip_prefix, timeout=5)`

Check if connected to university VPN by comparing public IP.

**Parameters:**
- `university_ip_prefix` (str): Start of your university's IP range (e.g., "130.225" for KU)
- `timeout` (int): Request timeout in seconds

**Returns:**
- Tuple of `(is_connected, current_ip, message)`
  - `is_connected` (bool): True if on university network
  - `current_ip` (str or None): Your current public IP
  - `message` (str): Human-readable status message

### `require_vpn(university_ip_prefix, error_message=None)`

Require VPN connection or raise an error.

**Parameters:**
- `university_ip_prefix` (str): Expected university IP prefix
- `error_message` (str, optional): Custom error message

**Raises:**
- `RuntimeError`: If not connected to VPN

### `get_current_ip(timeout=5)`

Get your current public IP address.

**Returns:**
- Your public IP as a string, or None if check failed

### `check_vpn_interface(interface_name="utun")`

Check if VPN network interface is active (macOS/Linux).

**Parameters:**
- `interface_name` (str): VPN interface name prefix ("utun", "tun0", "ppp0")

**Returns:**
- `True` if interface found, `False` otherwise

**Note:** Less reliable than IP-based checking.

## University IP Prefixes

Common Danish universities:
- **KU (Copenhagen):** `130.225`
- **DTU:** `192.38`
- **AAU (Aalborg):** `130.226`
- **SDU (Southern Denmark):** `130.229`
- **AU (Aarhus):** `130.225` (some departments)

Run `get_current_ip()` while connected to find yours.

## Adding New Utilities

To add new network utilities:

1. Create a new module (e.g., `ip_utils.py`):
```python
# network_utils/ip_utils.py
def parse_ip_range(cidr: str):
    """Parse CIDR notation."""
    # Implementation
    pass
```

2. Export from `__init__.py`:
```python
# network_utils/__init__.py
from .ip_utils import parse_ip_range

__all__ = [
    "check_vpn_status",
    "parse_ip_range",  # New function
]
```

3. Use it:
```python
from network_utils import parse_ip_range
```

## Dependencies

- `requests>=2.25.0` (for IP checking)

## License

MIT
