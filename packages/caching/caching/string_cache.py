"""
String-based caching system with status tracking.

Complementary to local_cache.py for scenarios where you need to cache
string data with status information (e.g., API responses, processing states).

Features:
- Single JSON file storage (human-readable)
- Status tracking per entry
- Timestamp-based expiration
- Easy inspection and debugging
"""

from pathlib import Path
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class StringCache:
    """
    Simple JSON-based cache for string data with status tracking.
    
    Structure: {
        key: {
            "value": str,
            "timestamp": ISO datetime,
            "status": str (e.g., "pending", "completed", "failed")
        }
    }
    
    Uses configured cache directory by default (see caching.get_cache_dir()).
    """
    
    def __init__(
        self,
        cache_file: Optional[str] = None,
        max_age_days: Optional[int] = None,
        auto_save: bool = True,
    ):
        """
        Initialize string cache.
        
        Args:
            cache_file: Path to JSON cache file (None = use configured cache_dir/string_cache.json)
            max_age_days: Expire entries after this many days (None = never)
            auto_save: Save to disk after each modification
        """
        if cache_file is None:
            # Use configured cache directory
            from .paths import get_cache_dir
            cache_file = get_cache_dir() / "string_cache.json"
        
        self.cache_file = Path(cache_file).expanduser()
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.max_age_days = max_age_days
        self.auto_save = auto_save
        
        self._load()
    
    def _load(self):
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    self.data = json.load(f)
                logger.info(f"Loaded {len(self.data)} entries from {self.cache_file}")
            except json.JSONDecodeError as e:
                logger.error(f"Error loading cache: {e}")
                self.data = {}
        else:
            self.data = {}
    
    def _save(self):
        """Save cache to disk."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """Check if an entry is expired."""
        if self.max_age_days is None:
            return False
        
        timestamp = datetime.fromisoformat(entry['timestamp'])
        age = datetime.now() - timestamp
        return age > timedelta(days=self.max_age_days)
    
    def has(self, key: str, status: Optional[str] = None) -> bool:
        """
        Check if key exists in cache and is not expired.
        
        Args:
            key: Cache key
            status: If provided, only return True if status matches
        """
        if key not in self.data:
            return False
        
        entry = self.data[key]
        
        if self._is_expired(entry):
            return False
        
        if status is not None and entry.get('status') != status:
            return False
        
        return True
    
    def get(
        self,
        key: str,
        default: Optional[str] = None,
        status: Optional[str] = None
    ) -> Optional[str]:
        """
        Get cached value.
        
        Args:
            key: Cache key
            default: Return this if key not found
            status: If provided, only return if status matches
            
        Returns:
            Cached value or default
        """
        if not self.has(key, status=status):
            return default
        
        return self.data[key]['value']
    
    def get_entry(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get full entry including metadata.
        
        Returns:
            Dict with {value, timestamp, status} or None
        """
        if key not in self.data:
            return None
        
        entry = self.data[key]
        if self._is_expired(entry):
            return None
        
        return entry.copy()
    
    def set(
        self,
        key: str,
        value: str,
        status: str = "completed",
        **extra_fields
    ):
        """
        Store value in cache.
        
        Args:
            key: Cache key
            value: String value to cache
            status: Status indicator (default: "completed")
            **extra_fields: Additional fields to store
        """
        self.data[key] = {
            'value': value,
            'timestamp': datetime.now().isoformat(),
            'status': status,
            **extra_fields
        }
        
        if self.auto_save:
            self._save()
        
        logger.debug(f"Cached key '{key}' with status '{status}'")
    
    def update_status(self, key: str, status: str):
        """Update status for an existing entry."""
        if key not in self.data:
            raise KeyError(f"Key '{key}' not in cache")
        
        self.data[key]['status'] = status
        self.data[key]['timestamp'] = datetime.now().isoformat()
        
        if self.auto_save:
            self._save()
    
    def delete(self, key: str) -> bool:
        """
        Remove key from cache.
        
        Returns:
            True if key was deleted, False if not found
        """
        if key not in self.data:
            return False
        
        del self.data[key]
        
        if self.auto_save:
            self._save()
        
        return True
    
    def list_keys(
        self,
        status: Optional[str] = None,
        include_expired: bool = False
    ) -> List[str]:
        """
        List all keys in cache.
        
        Args:
            status: Filter by status
            include_expired: Include expired entries
        """
        keys = []
        for key, entry in self.data.items():
            if not include_expired and self._is_expired(entry):
                continue
            if status is not None and entry.get('status') != status:
                continue
            keys.append(key)
        
        return keys
    
    def list_entries(
        self,
        status: Optional[str] = None,
        include_expired: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """
        List all entries with metadata.
        
        Args:
            status: Filter by status
            include_expired: Include expired entries
            
        Returns:
            Dict mapping keys to entries
        """
        entries = {}
        for key in self.list_keys(status=status, include_expired=include_expired):
            entries[key] = self.data[key].copy()
        
        return entries
    
    def clear_expired(self) -> int:
        """
        Remove expired entries.
        
        Returns:
            Number of entries removed
        """
        if self.max_age_days is None:
            return 0
        
        expired_keys = [
            key for key, entry in self.data.items()
            if self._is_expired(entry)
        ]
        
        for key in expired_keys:
            del self.data[key]
        
        if expired_keys and self.auto_save:
            self._save()
        
        logger.info(f"Cleared {len(expired_keys)} expired entries")
        return len(expired_keys)
    
    def clear_status(self, status: str) -> int:
        """
        Remove all entries with given status.
        
        Returns:
            Number of entries removed
        """
        matching_keys = [
            key for key, entry in self.data.items()
            if entry.get('status') == status
        ]
        
        for key in matching_keys:
            del self.data[key]
        
        if matching_keys and self.auto_save:
            self._save()
        
        logger.info(f"Cleared {len(matching_keys)} entries with status '{status}'")
        return len(matching_keys)
    
    def clear_all(self):
        """Remove all cached data."""
        self.data = {}
        if self.auto_save:
            self._save()
        logger.info("Cleared all cache")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        status_counts = {}
        for entry in self.data.values():
            status = entry.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        size_bytes = self.cache_file.stat().st_size if self.cache_file.exists() else 0
        
        return {
            'num_entries': len(self.data),
            'status_counts': status_counts,
            'size_kb': size_bytes / 1024,
            'cache_file': str(self.cache_file),
        }
    
    def save(self):
        """Explicitly save to disk (useful when auto_save=False)."""
        self._save()


# Example usage
if __name__ == "__main__":
    # Create cache
    cache = StringCache(cache_file="/tmp/test_string_cache.json")
    
    # Store some values
    cache.set("task_1", "result data", status="completed")
    cache.set("task_2", "pending...", status="pending")
    cache.set("task_3", "error message", status="failed")
    
    # Retrieve
    print(f"Task 1: {cache.get('task_1')}")
    print(f"Task 1 entry: {cache.get_entry('task_1')}")
    
    # Update status
    cache.update_status("task_2", "completed")
    
    # List by status
    print(f"\nCompleted tasks: {cache.list_keys(status='completed')}")
    print(f"Failed tasks: {cache.list_keys(status='failed')}")
    
    # Stats
    stats = cache.get_stats()
    print(f"\nCache stats:")
    print(f"  Total entries: {stats['num_entries']}")
    print(f"  By status: {stats['status_counts']}")
    print(f"  Size: {stats['size_kb']:.2f} KB")
    
    # Clean up
    cache.clear_all()
