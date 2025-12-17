#!/usr/bin/env python3
"""
Utility script to download and setup arXiv metadata.

This script helps users download the arXiv metadata file and
set it up in the correct location for the package.
"""

import argparse
import sys
from pathlib import Path
import requests
from tqdm import tqdm


def download_file(url: str, destination: Path, chunk_size: int = 8192):
    """Download a file with progress bar.
    
    Args:
        url: URL to download from
        destination: Path to save the file
        chunk_size: Size of chunks to download
    """
    print(f"Downloading from {url}")
    print(f"Saving to {destination}")
    
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    total_size = int(response.headers.get('content-length', 0))
    
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    with open(destination, 'wb') as f:
        with tqdm(total=total_size, unit='B', unit_scale=True) as pbar:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
    
    print(f"\nDownload complete: {destination}")


def download_from_kaggle(destination: Path):
    """Download metadata from Kaggle using kagglehub.
    
    Args:
        destination: Path to save the metadata file
    """
    try:
        import kagglehub
    except ImportError:
        print("Error: kagglehub not installed.")
        print("Install it with: pip install kagglehub")
        sys.exit(1)
    
    print("Downloading from Kaggle...")
    print("Note: You need Kaggle credentials configured.")
    print("See: https://www.kaggle.com/docs/api")
    
    try:
        path = kagglehub.dataset_download('Cornell-University/arxiv')
        source_file = Path(path) / 'arxiv-metadata-oai-snapshot.json'
        
        if not source_file.exists():
            print(f"Error: Expected file not found at {source_file}")
            sys.exit(1)
        
        # Copy to destination
        import shutil
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source_file, destination)
        
        print(f"\nMetadata file ready at: {destination}")
        
    except Exception as e:
        print(f"Error downloading from Kaggle: {e}")
        sys.exit(1)


def check_setup():
    """Check if metadata is already set up."""
    from arxiv_metadata import ArxivMetadata
    
    fetcher = ArxivMetadata()
    try:
        path = fetcher._get_metadata_path()
        print(f"✓ Metadata file found at: {path}")
        
        # Try to read first line
        with open(path, 'r') as f:
            line = f.readline()
            if line.strip():
                print("✓ File appears to be valid")
                return True
    except Exception as e:
        print(f"✗ No metadata file found: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Download and setup arXiv metadata'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Check if metadata is already set up'
    )
    parser.add_argument(
        '--kaggle',
        action='store_true',
        help='Download from Kaggle (requires kagglehub and credentials)'
    )
    parser.add_argument(
        '--destination',
        type=str,
        default='~/.arxiv_cache/arxiv_metadata.jsonl',
        help='Destination path for metadata file (default: ~/.arxiv_cache/arxiv_metadata.jsonl)'
    )
    
    args = parser.parse_args()
    
    if args.check:
        check_setup()
        return
    
    destination = Path(args.destination).expanduser()
    
    if destination.exists():
        response = input(f"File already exists at {destination}. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    if args.kaggle:
        download_from_kaggle(destination)
    else:
        print("Please specify a download method:")
        print("  --kaggle    Download from Kaggle (requires setup)")
        print("\nAlternatively, manually download and place the file at:")
        print(f"  {destination}")
        print("\nDownload sources:")
        print("  - Kaggle: https://www.kaggle.com/datasets/Cornell-University/arxiv")
        print("  - Direct: https://info.arxiv.org/help/bulk_data_s3.html")


if __name__ == '__main__':
    main()
