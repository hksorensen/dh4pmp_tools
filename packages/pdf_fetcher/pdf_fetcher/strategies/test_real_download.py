#!/usr/bin/env python3
"""
Real-World Strategy Tester

Test publisher strategies with actual downloads.

Usage:
    python test_real_download.py 10.1007/s10623-024-01403-z
    python test_real_download.py 10.1016/j.example.2020.01.001
    python test_real_download.py --list-strategies
"""

import argparse
import requests
from pathlib import Path
import logging
import sys

# Import strategies
from elsevier import ElsevierStrategy
from springer import SpringerStrategy

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleDownloader:
    """
    Simple downloader to test strategies in real-world.
    
    This is a minimal fetcher just for testing strategies.
    NOT the full BasePDFFetcher (that comes in Phase 2).
    """
    
    def __init__(self, output_dir: str = 'test_downloads'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load all strategies
        self.strategies = [
            ElsevierStrategy(),
            SpringerStrategy(),
        ]
        self.strategies.sort(key=lambda s: s.get_priority())
        
        # Session for requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                         'AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/131.0.0.0 Safari/537.36'
        })
    
    def select_strategy(self, identifier: str, url: str = None):
        """Select best strategy for identifier."""
        for strategy in self.strategies:
            if strategy.can_handle(identifier, url):
                return strategy
        return None
    
    def download(self, identifier: str):
        """
        Download PDF for identifier.
        
        Returns:
            (success: bool, message: str, filepath: Path or None)
        """
        logger.info(f"Processing: {identifier}")
        
        # Step 1: Select strategy
        strategy = self.select_strategy(identifier)
        if not strategy:
            return False, "No strategy can handle this identifier", None
        
        logger.info(f"Selected strategy: {strategy.name}")
        
        # Step 2: Construct landing URL (assume DOI)
        if identifier.startswith('10.'):
            landing_url = f"https://doi.org/{identifier}"
        else:
            landing_url = identifier
        
        logger.info(f"Landing URL: {landing_url}")
        
        # Step 3: Get PDF URL using strategy
        try:
            # For DOI-based strategies, try direct URL construction first
            pdf_url = strategy.get_pdf_url(
                identifier=identifier,
                landing_url=landing_url
            )
            
            if not pdf_url:
                # If that fails, fetch landing page and try HTML parsing
                logger.info("Fetching landing page...")
                response = self.session.get(landing_url, timeout=30, allow_redirects=True)
                response.raise_for_status()
                
                html_content = response.text
                actual_landing_url = response.url  # After redirects
                
                logger.info(f"Landed at: {actual_landing_url}")
                
                # Try again with HTML
                pdf_url = strategy.get_pdf_url(
                    identifier=identifier,
                    landing_url=actual_landing_url,
                    html_content=html_content
                )
            
            if not pdf_url:
                msg = "Strategy could not find PDF URL"
                logger.error(msg)
                return False, msg, None
            
            logger.info(f"PDF URL: {pdf_url}")
            
        except requests.exceptions.RequestException as e:
            msg = f"Error fetching landing page: {e}"
            logger.error(msg)
            
            # Check if should postpone
            if strategy.should_postpone(str(e)):
                return False, f"POSTPONED: {e}", None
            else:
                return False, msg, None
        except Exception as e:
            msg = f"Error finding PDF URL: {e}"
            logger.error(msg)
            return False, msg, None
        
        # Step 4: Download PDF
        try:
            logger.info("Downloading PDF...")
            response = self.session.get(pdf_url, timeout=60)
            response.raise_for_status()
            
            # Check if actually PDF
            content = response.content
            if not content.startswith(b'%PDF'):
                msg = "Downloaded content is not a PDF"
                logger.error(msg)
                return False, msg, None
            
            # Save file
            import hashlib
            filename = hashlib.md5(identifier.encode()).hexdigest() + '.pdf'
            filepath = self.output_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(content)
            
            size_mb = len(content) / (1024 * 1024)
            msg = f"Success! Downloaded {size_mb:.2f} MB"
            logger.info(msg)
            
            return True, msg, filepath
            
        except requests.exceptions.RequestException as e:
            msg = f"Error downloading PDF: {e}"
            logger.error(msg)
            
            if strategy.should_postpone(str(e)):
                return False, f"POSTPONED: {e}", None
            else:
                return False, msg, None
        except Exception as e:
            msg = f"Unexpected error: {e}"
            logger.error(msg, exc_info=True)
            return False, msg, None
    
    def list_strategies(self):
        """List available strategies."""
        print("\nAvailable Strategies:")
        print("="*80)
        for strategy in self.strategies:
            print(f"\n{strategy.name} (priority={strategy.get_priority()})")
            print(f"  DOI prefixes: {', '.join(sorted(strategy.get_doi_prefixes()))}")
            print(f"  Domains: {', '.join(sorted(strategy.get_domains()))}")
        print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(description='Test publisher strategies with real downloads')
    parser.add_argument('identifier', nargs='?', help='DOI or URL to download')
    parser.add_argument('--list-strategies', action='store_true', help='List available strategies')
    parser.add_argument('--output-dir', default='test_downloads', help='Output directory for PDFs')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    downloader = SimpleDownloader(output_dir=args.output_dir)
    
    if args.list_strategies:
        downloader.list_strategies()
        return 0
    
    if not args.identifier:
        parser.print_help()
        print("\nExamples:")
        print("  python test_real_download.py 10.1007/s10623-024-01403-z")
        print("  python test_real_download.py 10.1016/j.example.2020.01.001")
        return 1
    
    # Run download
    print("\n" + "="*80)
    print("REAL-WORLD DOWNLOAD TEST")
    print("="*80)
    
    success, message, filepath = downloader.download(args.identifier)
    
    print("\n" + "="*80)
    if success:
        print(f"✅ SUCCESS")
        print(f"Message: {message}")
        print(f"File: {filepath}")
        print(f"Size: {filepath.stat().st_size / 1024:.2f} KB")
    else:
        print(f"❌ FAILED")
        print(f"Reason: {message}")
    print("="*80 + "\n")
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
