"""
Example: Check VPN status before running research tasks.

This example shows how to use network_utils to ensure you're connected
to your university VPN before performing tasks that require university
network access.
"""

from network_utils import check_vpn_status, require_vpn, get_current_ip


def example_basic_check():
    """Basic VPN check."""
    print("="*60)
    print("Example 1: Basic VPN Check")
    print("="*60)

    is_vpn, ip, msg = check_vpn_status("130.225")  # KU Copenhagen
    print(msg)

    if is_vpn:
        print("✓ Safe to proceed with university resources")
    else:
        print("⚠️  Connect to VPN for full access")
    print()


def example_require_vpn():
    """Require VPN or stop execution."""
    print("="*60)
    print("Example 2: Require VPN")
    print("="*60)

    try:
        require_vpn("130.225", "This task requires university network!")
        print("✓ VPN check passed, continuing...")
    except RuntimeError as e:
        print(f"Error: {e}")
    print()


def example_find_ip_prefix():
    """Find your university's IP prefix."""
    print("="*60)
    print("Example 3: Find Your IP Prefix")
    print("="*60)
    print("Connect to VPN, then run this to find your prefix:")
    print()

    ip = get_current_ip()
    if ip:
        prefix = '.'.join(ip.split('.')[:2])
        print(f"Current IP: {ip}")
        print(f"IP Prefix: {prefix}")
        print(f"\nUse in your code:")
        print(f"  require_vpn('{prefix}')")
    else:
        print("Could not determine IP")
    print()


def example_with_pdf_fetcher():
    """Example integration with pdf_fetcher."""
    print("="*60)
    print("Example 4: Integration with PDF Fetcher")
    print("="*60)
    print("""
# In your notebook or script:

from network_utils import require_vpn
from pdf_fetcher import BasePDFFetcher

# Ensure VPN is connected
require_vpn("130.225", "PDF downloads require university VPN!")

# Now safe to download
fetcher = BasePDFFetcher(output_dir="./pdfs")
results = fetcher.fetch_batch(dois)
    """)
    print()


if __name__ == "__main__":
    example_basic_check()
    example_require_vpn()
    example_find_ip_prefix()
    example_with_pdf_fetcher()
