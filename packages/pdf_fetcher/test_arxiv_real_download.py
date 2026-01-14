#!/usr/bin/env python3
"""
Test ArXiv strategy with a real download.

This script tests the ArXiv strategy by:
1. Testing identifier recognition (can_handle)
2. Testing ID extraction (extract_arxiv_id)
3. Testing PDF URL construction (get_pdf_url)
4. Actually downloading a PDF to verify it works end-to-end
"""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from pdf_fetcher.strategies.arxiv import ArxivStrategy
from pdf_fetcher import PDFFetcher


def test_strategy_methods():
    """Test the strategy's core methods."""
    print("=" * 80)
    print("Testing ArxivStrategy Methods")
    print("=" * 80)
    
    strategy = ArxivStrategy()
    
    # Test identifiers that your pipeline uses (with versions)
    test_cases = [
        "2301.12345",           # Basic ID
        "2301.12345v1",         # With version (like your pipeline creates)
        "2301.12345v2",         # Version 2
        "math.GT/0309136",      # Old format
        "10.48550/arXiv.2301.12345",  # ArXiv DOI
    ]
    
    print("\n1. Testing can_handle():")
    for identifier in test_cases:
        can_handle = strategy.can_handle(identifier)
        status = "✓" if can_handle else "✗"
        print(f"   {status} {identifier:40s} → {can_handle}")
    
    print("\n2. Testing extract_arxiv_id():")
    for identifier in test_cases:
        extracted = strategy.extract_arxiv_id(identifier)
        status = "✓" if extracted else "✗"
        print(f"   {status} {identifier:40s} → {extracted}")
    
    print("\n3. Testing get_pdf_url():")
    for identifier in test_cases:
        pdf_url = strategy.get_pdf_url(identifier, landing_url="", html_content="")
        status = "✓" if pdf_url else "✗"
        print(f"   {status} {identifier:40s}")
        if pdf_url:
            print(f"      → {pdf_url}")
    
    print("\n" + "=" * 80)


def test_real_download():
    """Test downloading a real ArXiv PDF."""
    print("\n" + "=" * 80)
    print("Testing Real PDF Download")
    print("=" * 80)
    
    # Use a real ArXiv ID that's known to exist
    # This is a recent paper from 2024 (you can change it to any ArXiv ID)
    test_arxiv_ids = [
        "2401.00001",        # Example: Use a real ArXiv ID from 2024
        "2401.00001v1",      # With version
        # Add more real IDs if you want to test multiple
    ]
    
    # Create temporary directory for downloads
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "test_pdfs"
        output_dir.mkdir()
        
        print(f"\nDownload directory: {output_dir}")
        print(f"Testing with ArXiv IDs: {test_arxiv_ids}")
        
        fetcher = PDFFetcher(output_dir=str(output_dir), max_workers=2)
        
        for arxiv_id in test_arxiv_ids:
            print(f"\n📄 Testing download: {arxiv_id}")
            try:
                result = fetcher.fetch(arxiv_id)
                
                print(f"   Status: {result.status}")
                if result.status == "success":
                    print(f"   ✓ Downloaded: {result.local_path}")
                    if result.local_path and result.local_path.exists():
                        file_size = result.local_path.stat().st_size
                        print(f"   ✓ File size: {file_size:,} bytes")
                        
                        # Quick validation: check if it's a PDF
                        with open(result.local_path, 'rb') as f:
                            header = f.read(4)
                            if header == b'%PDF':
                                print(f"   ✓ Valid PDF file")
                            else:
                                print(f"   ✗ File is not a valid PDF (header: {header})")
                    else:
                        print(f"   ✗ File path doesn't exist: {result.local_path}")
                else:
                    print(f"   ✗ Download failed: {result.error_reason}")
                    
            except Exception as e:
                print(f"   ✗ Exception: {e}")
                import traceback
                traceback.print_exc()
    
    print("\n" + "=" * 80)


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("ArXiv Strategy Real Download Test")
    print("=" * 80)
    
    # Test strategy methods first
    test_strategy_methods()
    
    # Test real download
    print("\n⚠️  Note: This will download a real PDF from ArXiv.")
    print("   Make sure you have internet connectivity.")
    response = input("\nContinue with real download test? [y/N]: ").strip().lower()
    
    if response in ('y', 'yes'):
        test_real_download()
    else:
        print("\nSkipping real download test.")
    
    print("\n✅ Test suite complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
