"""
Logging configuration for PDF Fetcher v2.

Provides structured logging to both file and console with configurable levels.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


def setup_logging(
    log_file: Optional[Path] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Setup logging for PDF Fetcher.
    
    Args:
        log_file: Path to log file (if None, only console logging)
        console_level: Logging level for console output
        file_level: Logging level for file output
        format_string: Custom format string (if None, uses default)
    
    Returns:
        Configured logger
    """
    logger = logging.getLogger('pdf_fetcher_v2')
    logger.setLevel(logging.DEBUG)  # Capture everything, handlers filter
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Default format
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    formatter = logging.Formatter(format_string)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        logger.info(f"Logging to file: {log_file}")
    
    return logger


def create_download_summary_log(results, log_dir: Path):
    """
    Create a summary log file for a batch download.
    
    Args:
        results: List of DownloadResult objects
        log_dir: Directory to save summary log
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    summary_file = log_dir / f"download_summary_{timestamp}.log"
    
    with open(summary_file, 'w') as f:
        f.write(f"PDF Fetcher v2 - Download Summary\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write("=" * 80 + "\n\n")
        
        # Statistics
        total = len(results)
        success = sum(1 for r in results if r.status.value == 'success')
        already_exists = sum(1 for r in results if r.status.value == 'already_exists')
        failure = sum(1 for r in results if r.status.value == 'failure')
        paywall = sum(1 for r in results if r.status.value == 'paywall')
        
        f.write(f"STATISTICS\n")
        f.write(f"-" * 80 + "\n")
        f.write(f"Total: {total}\n")
        f.write(f"Success: {success}\n")
        f.write(f"Already exists: {already_exists}\n")
        f.write(f"Failures: {failure}\n")
        f.write(f"Paywalls: {paywall}\n")
        f.write(f"Success rate: {(success / total * 100) if total > 0 else 0:.1f}%\n")
        f.write("\n")
        
        # Successful downloads
        if success > 0:
            f.write(f"SUCCESSFUL DOWNLOADS ({success})\n")
            f.write(f"-" * 80 + "\n")
            for r in results:
                if r.status.value == 'success':
                    f.write(f"✓ {r.identifier}\n")
                    f.write(f"  Path: {r.pdf_path}\n")
                    if r.publisher:
                        f.write(f"  Publisher: {r.publisher}\n")
                    f.write("\n")
        
        # Failures
        if failure > 0:
            f.write(f"FAILURES ({failure})\n")
            f.write(f"-" * 80 + "\n")
            for r in results:
                if r.status.value == 'failure':
                    f.write(f"✗ {r.identifier}\n")
                    f.write(f"  Reason: {r.error_reason}\n")
                    if r.landing_url:
                        f.write(f"  URL: {r.landing_url}\n")
                    f.write("\n")
        
        # Paywalls
        if paywall > 0:
            f.write(f"PAYWALLS ({paywall})\n")
            f.write(f"-" * 80 + "\n")
            for r in results:
                if r.status.value == 'paywall':
                    f.write(f"⚠ {r.identifier}\n")
                    if r.landing_url:
                        f.write(f"  URL: {r.landing_url}\n")
                    f.write("\n")
    
    return summary_file
