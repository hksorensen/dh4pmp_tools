"""
Status Tracker - Track processing status of individual items.

Useful for tracking progress through large datasets and enabling resumability.
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Optional
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ItemStatus(Enum):
    """Status of an individual item."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StatusTracker:
    """
    Track processing status of individual items.
    
    Useful for:
    - Resuming from failures
    - Progress tracking
    - Identifying what still needs processing
    """
    
    def __init__(self, status_file: Path):
        """
        Initialize status tracker.
        
        Args:
            status_file: Path to JSON file storing status
        """
        self.status_file = Path(status_file)
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        self._status: Dict[str, str] = {}
        self._load()
    
    def _load(self):
        """Load status from file."""
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r') as f:
                    data = json.load(f)
                    self._status = data.get('items', {})
                logger.debug(f"Loaded status for {len(self._status)} items")
            except Exception as e:
                logger.warning(f"Could not load status file: {e}, starting fresh")
                self._status = {}
        else:
            self._status = {}
    
    def _save(self):
        """Save status to file."""
        data = {
            'items': self._status,
            'last_updated': datetime.now().isoformat()
        }
        with open(self.status_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def mark_pending(self, item_id: str):
        """Mark item as pending."""
        self._status[item_id] = ItemStatus.PENDING.value
        self._save()
    
    def mark_processing(self, item_id: str):
        """Mark item as currently processing."""
        self._status[item_id] = ItemStatus.PROCESSING.value
        self._save()
    
    def mark_completed(self, item_id: str):
        """Mark item as completed."""
        self._status[item_id] = ItemStatus.COMPLETED.value
        self._save()
    
    def mark_failed(self, item_id: str):
        """Mark item as failed."""
        self._status[item_id] = ItemStatus.FAILED.value
        self._save()
    
    def mark_skipped(self, item_id: str):
        """Mark item as skipped."""
        self._status[item_id] = ItemStatus.SKIPPED.value
        self._save()
    
    def get_status(self, item_id: str) -> Optional[ItemStatus]:
        """Get status of an item."""
        status_str = self._status.get(item_id)
        if status_str:
            return ItemStatus(status_str)
        return None
    
    def get_pending(self) -> List[str]:
        """Get list of pending item IDs."""
        return [
            item_id for item_id, status in self._status.items()
            if status == ItemStatus.PENDING.value
        ]
    
    def get_processing(self) -> List[str]:
        """Get list of currently processing item IDs."""
        return [
            item_id for item_id, status in self._status.items()
            if status == ItemStatus.PROCESSING.value
        ]
    
    def get_completed(self) -> List[str]:
        """Get list of completed item IDs."""
        return [
            item_id for item_id, status in self._status.items()
            if status == ItemStatus.COMPLETED.value
        ]
    
    def get_failed(self) -> List[str]:
        """Get list of failed item IDs."""
        return [
            item_id for item_id, status in self._status.items()
            if status == ItemStatus.FAILED.value
        ]
    
    def get_skipped(self) -> List[str]:
        """Get list of skipped item IDs."""
        return [
            item_id for item_id, status in self._status.items()
            if status == ItemStatus.SKIPPED.value
        ]
    
    def get_summary(self) -> Dict[str, int]:
        """Get summary counts by status."""
        summary = {
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0,
            'total': len(self._status)
        }
        
        for status in self._status.values():
            if status in summary:
                summary[status] = summary.get(status, 0) + 1
        
        return summary
    
    def initialize_items(self, item_ids: List[str], reset: bool = False):
        """
        Initialize tracking for a list of items.
        
        Args:
            item_ids: List of item IDs to track
            reset: If True, reset existing items to pending
        """
        for item_id in item_ids:
            if item_id not in self._status or reset:
                self.mark_pending(item_id)
        
        logger.info(f"Initialized tracking for {len(item_ids)} items")
    
    def clear(self):
        """Clear all status tracking."""
        self._status = {}
        self._save()
        logger.info("Cleared all status tracking")



