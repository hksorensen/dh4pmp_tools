"""
Example: Using pdf_fetcher with automatic VPN checking.

This example shows how to enable VPN checking so downloads only
proceed when connected to your university network.
"""

from pdf_fetcher import BasePDFFetcher


def example_with_vpn_check():
    """Download PDFs with automatic VPN verification."""
    print("=" * 60)
    print("Example: PDF Download with VPN Check")
    print("=" * 60)
    print()

    # Initialize fetcher with VPN requirement
    # Replace with your university's IP prefix(es)
    fetcher = BasePDFFetcher(
        output_dir="./pdfs", require_vpn=["130.225", "130.226"]  # KU Copenhagen IP ranges
    )

    # Test with a few DOIs
    dois = ["10.1007/s10623-024-01403-z", "10.1090/mcom/3962", "10.1137/23M1545835"]

    print(f"Fetching {len(dois)} PDFs...")
    print("VPN check will run automatically before downloads")
    print()

    # VPN check happens automatically:
    # - Only if there are actual downloads to perform
    # - Not if all PDFs are already cached
    results = fetcher.fetch_batch(dois)

    # Show results
    print("\nResults:")
    for result in results:
        print(f"  {result}")

    # Show stats
    stats = fetcher.get_stats()
    if stats:
        print(f"\nOverall stats:")
        print(f"  Successful: {stats.get('success_count', 0)}")
        print(f"  Failed: {stats.get('failure_count', 0)}")


def example_without_vpn_check():
    """Normal usage without VPN checking."""
    print("=" * 60)
    print("Example: Normal Usage (No VPN Check)")
    print("=" * 60)
    print()

    # Without require_vpn parameter, no VPN check is performed
    fetcher = BasePDFFetcher(output_dir="./pdfs")

    result = fetcher.fetch("10.1007/s10623-024-01403-z")
    print(result)


if __name__ == "__main__":
    # Run example with VPN check
    try:
        example_with_vpn_check()
    except RuntimeError as e:
        print(f"\nVPN Error: {e}")
        print("\nPlease connect to VPN and try again.")

    print("\n" * 2)

    # Run example without VPN check
    example_without_vpn_check()
