"""
SQLite-backed StringCache - Drop-in replacement for caching.StringCache

This is a parallel-safe alternative to the JSON-based StringCache from
dh4pmp_tools/packages/caching. It maintains the same API but uses SQLite
for thread-safe and process-safe operations.

Drop-in usage:
    # Instead of:
    from caching import StringCache
    
    # Use:
    from sqlite_string_cache import SQLiteStringCache as StringCache
    
    # Rest of your code stays exactly the same!
    cache = StringCache(cache_file="status.json")
    cache.set("key", "value", status="completed")
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class SQLiteStringCache:
    """
    SQLite-backed string cache with status tracking.
    
    API-compatible with caching.StringCache but thread-safe and process-safe.
    
    Structure per entry:
        - key: str (unique identifier)
        - value: str (cached data)
        - status: str (e.g., "pending", "completed", "failed")
        - timestamp: datetime (when created/updated)
        - extra: JSON blob for additional metadata
    """
    
    def __init__(
        self,
        cache_file: Optional[str] = None,
        max_age_days: Optional[int] = None,
        auto_save: bool = True,  # Ignored (SQLite always saves), kept for API compat
    ):
        """
        Initialize SQLite string cache.
        
        Args:
            cache_file: Path to cache file (defaults to configured cache_dir/string_cache.db)
            max_age_days: Expire entries after this many days (None = never)
            auto_save: Ignored (kept for API compatibility with StringCache)
        """
        if cache_file is None:
            # Try to use configured cache directory if available
            try:
                from caching import get_cache_dir
                cache_file = get_cache_dir() / "string_cache.db"
            except ImportError:
                cache_file = Path.home() / ".cache" / "dh4pmp" / "string_cache.db"
        
        # Handle .json extension for compatibility - change to .db
        cache_file = Path(cache_file).expanduser()
        if cache_file.suffix == '.json':
            cache_file = cache_file.with_suffix('.db')
        
        self.cache_file = cache_file
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.max_age_days = max_age_days
        
        self._initialize_db()
        logger.info(f"SQLiteStringCache initialized: {self.cache_file}")
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper settings for concurrency."""
        conn = sqlite3.connect(
            str(self.cache_file),
            timeout=30.0,
            isolation_level='DEFERRED'
        )
        conn.row_factory = sqlite3.Row  # Access columns by name
        
        # Enable Write-Ahead Logging for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _initialize_db(self):
        """Create table if it doesn't exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS string_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    status TEXT DEFAULT '',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    extra TEXT DEFAULT '{}'
                )
            """)
            
            # Index for status queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status 
                ON string_cache(status)
            """)
            
            # Index for timestamp (for expiry)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON string_cache(timestamp)
            """)
    
    def has(self, key: str, status: Optional[str] = None) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: String key to check
            status: Optional status filter
        
        Returns:
            True if key exists (with given status if specified)
        """
        with self._get_connection() as conn:
            if status is not None:
                result = conn.execute(
                    "SELECT 1 FROM string_cache WHERE key = ? AND status = ? LIMIT 1",
                    (key, status)
                ).fetchone()
            else:
                result = conn.execute(
                    "SELECT 1 FROM string_cache WHERE key = ? LIMIT 1",
                    (key,)
                ).fetchone()
            
            return result is not None
    
    def get(self, key: str, default: Optional[str] = None, status: Optional[str] = None) -> Optional[str]:
        """
        Get cached value for key.
        
        Args:
            key: String key
            default: Value to return if key not found
            status: Optional status filter
        
        Returns:
            Cached value or default
        """
        with self._get_connection() as conn:
            if status is not None:
                result = conn.execute(
                    "SELECT value FROM string_cache WHERE key = ? AND status = ?",
                    (key, status)
                ).fetchone()
            else:
                result = conn.execute(
                    "SELECT value FROM string_cache WHERE key = ?",
                    (key,)
                ).fetchone()
            
            return result['value'] if result else default
    
    def get_entry(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get full entry with metadata.
        
        Args:
            key: String key
        
        Returns:
            Dict with 'value', 'status', 'timestamp', 'extra' or None
        """
        with self._get_connection() as conn:
            result = conn.execute(
                "SELECT value, status, timestamp, extra FROM string_cache WHERE key = ?",
                (key,)
            ).fetchone()
            
            if result:
                import json
                return {
                    'value': result['value'],
                    'status': result['status'],
                    'timestamp': result['timestamp'],
                    'extra': json.loads(result['extra']) if result['extra'] else {}
                }
            return None
    
    def set(self, key: str, value: str, status: str = "", **extra) -> None:
        """
        Store value with optional status and extra metadata.
        
        Args:
            key: String key
            value: String value to store
            status: Status string (e.g., "completed", "pending", "failed")
            **extra: Additional metadata to store
        """
        import json
        extra_json = json.dumps(extra) if extra else '{}'
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO string_cache (key, value, status, timestamp, extra)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    status = excluded.status,
                    timestamp = CURRENT_TIMESTAMP,
                    extra = excluded.extra
            """, (key, value, status, extra_json))
    
    def update_status(self, key: str, status: str) -> bool:
        """
        Update status for existing entry.
        
        Args:
            key: String key
            status: New status
        
        Returns:
            True if entry was updated, False if key didn't exist
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE string_cache SET status = ?, timestamp = CURRENT_TIMESTAMP WHERE key = ?",
                (status, key)
            )
            return cursor.rowcount > 0
    
    def delete(self, key: str) -> bool:
        """
        Remove key from cache.
        
        Args:
            key: String key to delete
        
        Returns:
            True if entry was deleted, False if it didn't exist
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM string_cache WHERE key = ?",
                (key,)
            )
            return cursor.rowcount > 0
    
    def list_keys(self, status: Optional[str] = None) -> List[str]:
        """
        List all keys, optionally filtered by status.
        
        Args:
            status: Optional status filter
        
        Returns:
            List of keys
        """
        with self._get_connection() as conn:
            if status is not None:
                results = conn.execute(
                    "SELECT key FROM string_cache WHERE status = ? ORDER BY key",
                    (status,)
                ).fetchall()
            else:
                results = conn.execute(
                    "SELECT key FROM string_cache ORDER BY key"
                ).fetchall()
            
            return [row['key'] for row in results]
    
    def list_entries(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all entries with full metadata.
        
        Args:
            status: Optional status filter
        
        Returns:
            List of entry dicts
        """
        import json
        
        with self._get_connection() as conn:
            if status is not None:
                results = conn.execute(
                    "SELECT key, value, status, timestamp, extra FROM string_cache WHERE status = ? ORDER BY key",
                    (status,)
                ).fetchall()
            else:
                results = conn.execute(
                    "SELECT key, value, status, timestamp, extra FROM string_cache ORDER BY key"
                ).fetchall()
            
            entries = []
            for row in results:
                entries.append({
                    'key': row['key'],
                    'value': row['value'],
                    'status': row['status'],
                    'timestamp': row['timestamp'],
                    'extra': json.loads(row['extra']) if row['extra'] else {}
                })
            
            return entries
    
    def clear_expired(self) -> int:
        """
        Remove expired entries.
        
        Returns:
            Number of entries deleted
        """
        if self.max_age_days is None:
            return 0
        
        cutoff = datetime.now() - timedelta(days=self.max_age_days)
        cutoff_str = cutoff.isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM string_cache WHERE timestamp < ?",
                (cutoff_str,)
            )
            return cursor.rowcount
    
    def clear_status(self, status: str) -> int:
        """
        Remove all entries with given status.
        
        Args:
            status: Status to clear
        
        Returns:
            Number of entries deleted
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM string_cache WHERE status = ?",
                (status,)
            )
            return cursor.rowcount
    
    def clear_all(self) -> int:
        """
        Clear entire cache.
        
        Returns:
            Number of entries deleted
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM string_cache")
            return cursor.rowcount
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache stats
        """
        with self._get_connection() as conn:
            # Total entries
            total = conn.execute("SELECT COUNT(*) as count FROM string_cache").fetchone()['count']
            
            # Status breakdown
            status_counts = {}
            results = conn.execute(
                "SELECT status, COUNT(*) as count FROM string_cache GROUP BY status"
            ).fetchall()
            for row in results:
                status_counts[row['status']] = row['count']
            
            # File size
            size_bytes = self.cache_file.stat().st_size if self.cache_file.exists() else 0
            
            return {
                'total_entries': total,
                'status_counts': status_counts,
                'file_size_kb': size_bytes / 1024,
                'cache_file': str(self.cache_file),
                'max_age_days': self.max_age_days,
            }
    
    # Convenience methods matching StringCache API
    def set_pending(self, key: str, value: str = "") -> None:
        """Mark as pending."""
        self.set(key, value, status="pending")
    
    def set_completed(self, key: str, value: str) -> None:
        """Mark as completed."""
        self.set(key, value, status="completed")
    
    def set_failed(self, key: str, error: str = "") -> None:
        """Mark as failed."""
        self.set(key, error, status="failed")
    
    def get_status(self, key: str) -> Optional[str]:
        """Get status for key."""
        entry = self.get_entry(key)
        return entry['status'] if entry else None
    
    def __len__(self) -> int:
        """Return number of cached entries."""
        return self.get_stats()['total_entries']
    
    def __contains__(self, key: str) -> bool:
        """Support 'in' operator."""
        return self.has(key)
    
    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_stats()
        return f"SQLiteStringCache('{self.cache_file}', entries={stats['total_entries']})"


# Example usage
if __name__ == '__main__':
    print("=== SQLite StringCache Demo ===\n")
    
    cache = SQLiteStringCache('demo_cache.db')
    
    # Matches StringCache API exactly
    cache.set("doi:123", "abstract text", status="completed")
    cache.set("doi:456", "", status="pending")
    cache.set("doi:789", "404 error", status="failed")
    
    # Retrieve
    print(f"Get completed: {cache.get('doi:123', status='completed')}")
    print(f"Has pending: {cache.has('doi:456', status='pending')}")
    
    # List by status
    print(f"\nCompleted entries: {cache.list_keys(status='completed')}")
    print(f"Failed entries: {cache.list_keys(status='failed')}")
    
    # Full entry
    entry = cache.get_entry('doi:123')
    print(f"\nFull entry: {entry}")
    
    # Stats
    print(f"\nStats: {cache.get_stats()}")
    
    # Cleanup
    cache.clear_all()
    print("\nCache cleared")
