"""
ArXiv S3 Strategy - Downloads from AWS S3 bucket using boto3

Requires: pip install boto3
Setup: aws configure (for credentials)
Note: Requester-pays bucket - you pay for data transfer
"""
from typing import Optional, Set
import re
import logging
import time
import threading
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    from .base import DownloadStrategy
except ImportError:
    from base import DownloadStrategy

logger = logging.getLogger(__name__)


class ArxivS3Strategy(DownloadStrategy):
    """Strategy for downloading PDFs from ArXiv AWS S3 bucket."""
    
    ARXIV_NEW_PATTERN = re.compile(r'(\d{4}\.\d{4,5})(v\d+)?')
    ARXIV_OLD_PATTERN = re.compile(r'([a-z\-]+(?:\.[A-Z]{2})?/\d{7})')
    ARXIV_DOI_PATTERN = re.compile(r'10\.48550/arXiv\.(\d{4}\.\d{4,5})(v\d+)?')
    
    _last_request_time = 0
    _rate_limit_lock = threading.Lock()
    _cooldown = 0.1
    
    def __init__(self, bucket_name: str = "arxiv", cooldown: float = 0.1, request_payer: str = "requester"):
        super().__init__(name="ArXiv-S3")
        
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 required: pip install boto3")
        
        self.bucket_name = bucket_name
        self.request_payer = request_payer
        
        try:
            self.s3_client = boto3.client('s3')
        except NoCredentialsError:
            raise NoCredentialsError("AWS credentials not configured. Run 'aws configure'")
    
    def can_handle(self, identifier: str, url: Optional[str] = None) -> bool:
        """Check if identifier is from ArXiv."""
        if identifier.lower().startswith('arxiv:'):
            return True
        if self.ARXIV_DOI_PATTERN.search(identifier):
            return True
        if 'arxiv.org' in identifier.lower():
            return True
        if self.ARXIV_NEW_PATTERN.match(identifier):
            return True
        return False
    
    def extract_arxiv_id(self, identifier: str) -> Optional[str]:
        """Extract clean ArXiv ID."""
        identifier = identifier.replace('arxiv:', '').replace('arXiv:', '')
        doi_match = self.ARXIV_DOI_PATTERN.search(identifier)
        if doi_match:
            return doi_match.group(1) + (doi_match.group(2) or '')
        new_match = self.ARXIV_NEW_PATTERN.match(identifier)
        if new_match:
            return new_match.group(1) + (new_match.group(2) or '')
        return None
    
    def get_s3_key(self, arxiv_id: str) -> str:
        """Construct S3 key from ArXiv ID."""
        if '.' in arxiv_id:
            year_month = arxiv_id.split('.')[0]
            if len(year_month) >= 4:
                year = f"20{year_month[:2]}"
                month = year_month[2:4]
                return f"pdf/{year}/{month}/{arxiv_id}.pdf"
        return f"pdf/{arxiv_id}.pdf"
    
    def get_pdf_url(self, identifier: str, landing_url: str, html_content: str = "", driver=None) -> Optional[str]:
        """Return S3 URL format for fetcher to handle."""
        arxiv_id = self.extract_arxiv_id(identifier)
        if not arxiv_id:
            return None
        key = self.get_s3_key(arxiv_id)
        return f"s3://{self.bucket_name}/{key}"
    
    def download_from_s3(self, arxiv_id: str, output_path: Path) -> bool:
        """Download PDF directly from S3."""
        key = self.get_s3_key(arxiv_id)
        try:
            self.s3_client.download_file(
                self.bucket_name, key, str(output_path),
                ExtraArgs={'RequestPayer': self.request_payer}
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                alt_key = f"pdf/{arxiv_id}.pdf"
                try:
                    self.s3_client.download_file(
                        self.bucket_name, alt_key, str(output_path),
                        ExtraArgs={'RequestPayer': self.request_payer}
                    )
                    return True
                except:
                    return False
            return False
    
    def should_postpone(self, error_msg: str, html: str = "") -> bool:
        """Postpone on network errors, fail on 404."""
        error_lower = error_msg.lower()
        if any(x in error_lower for x in ['timeout', 'connection', '503', '502', '500']):
            return True
        if '404' in error_lower or 'nosuchkey' in error_lower:
            return False
        return False
    
    def get_priority(self) -> int:
        return 4  # Higher priority than regular ArXiv (5)
    
    def get_domains(self) -> Set[str]:
        return {'arxiv.org'}
    
    def get_doi_prefixes(self) -> Set[str]:
        return {'10.48550'}
