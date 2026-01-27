"""
Download Metadata Database

SQLite-based metadata tracking for PDF downloads.
Replaces metadata.json with proper database.

Features:
- Skip already downloaded PDFs
- Track failures and errors
- Retry logic (attempt count, should_retry flag)
- Publisher/strategy tracking
- Import from old metadata.json
- Export back to JSON (backward compatibility)
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
import json
import logging

logger = logging.getLogger(__name__)


class DownloadMetadataDB:
    """
    SQLite database for download metadata.

    Schema based on Henrik's requirements:
    - Keep all current metadata.json fields
    - Add attempt_count (prevent infinite retries)
    - Add should_retry (mark permanent failures)
    - Add strategy_used (debugging)
    - Use sanitized_filename (readable filenames)
    """

    def __init__(self, db_path: str = "download_metadata.db"):
        """
        Initialize metadata database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper settings."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, isolation_level="DEFERRED")
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrency
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
        """Create tables if they don't exist."""
        with self._get_connection() as conn:
            # Main table - preserves all metadata.json fields + new ones
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS download_results (
                    -- Primary key
                    identifier TEXT PRIMARY KEY,
                    
                    -- Status tracking (from metadata.json)
                    status TEXT NOT NULL,
                    first_attempted DATETIME NOT NULL,
                    last_attempted DATETIME NOT NULL,
                    
                    -- NEW: Retry logic
                    attempt_count INTEGER NOT NULL DEFAULT 1,
                    should_retry BOOLEAN DEFAULT 1,
                    
                    -- Publisher info (from metadata.json + new)
                    publisher TEXT,
                    strategy_used TEXT,
                    
                    -- URLs (from metadata.json)
                    landing_url TEXT,
                    pdf_url TEXT,
                    
                    -- File info (from metadata.json)
                    sanitized_filename TEXT,
                    local_path TEXT,
                    file_exists BOOLEAN DEFAULT 1,

                    -- Archive support (for moved files)
                    archived BOOLEAN DEFAULT 0,
                    archive_location TEXT,
                    archive_date DATETIME,

                    -- Error tracking (from metadata.json)
                    error_reason TEXT,
                    cloudflare_detected BOOLEAN DEFAULT 0,

                    -- Timestamps
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Indexes for fast queries
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_status
                ON download_results(status)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_should_retry
                ON download_results(should_retry)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_publisher
                ON download_results(publisher)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_last_attempted
                ON download_results(last_attempted)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_archived
                ON download_results(archived)
            """
            )

            # Migration: Add new columns to existing databases
            self._migrate_schema(conn)

    def _migrate_schema(self, conn):
        """Add new columns to existing databases if they don't exist."""
        # Get existing columns
        cursor = conn.execute("PRAGMA table_info(download_results)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Define new columns with their definitions
        new_columns = {
            "file_exists": "BOOLEAN DEFAULT 1",
            "archived": "BOOLEAN DEFAULT 0",
            "archive_location": "TEXT",
            "archive_date": "DATETIME",
        }

        # Add missing columns
        for column_name, column_def in new_columns.items():
            if column_name not in existing_columns:
                logger.info(f"Migrating database: adding column '{column_name}'")
                conn.execute(f"ALTER TABLE download_results ADD COLUMN {column_name} {column_def}")

    def get_result(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Get download result for identifier.

        Returns:
            Dict with all fields, or None if not found
        """
        with self._get_connection() as conn:
            result = conn.execute(
                "SELECT * FROM download_results WHERE identifier = ?", (identifier,)
            ).fetchone()

            if result:
                return dict(result)
            return None

    def record_success(
        self,
        identifier: str,
        local_path: str,
        publisher: Optional[str] = None,
        strategy_used: Optional[str] = None,
        landing_url: Optional[str] = None,
        pdf_url: Optional[str] = None,
        sanitized_filename: Optional[str] = None,
    ):
        """
        Record successful download.

        Args:
            identifier: DOI or other identifier
            local_path: Path to downloaded PDF
            publisher: Publisher name (e.g., 'springer')
            strategy_used: Strategy class name (e.g., 'SpringerStrategy')
            landing_url: Landing page URL
            pdf_url: PDF URL
            sanitized_filename: Sanitized filename
        """
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            # Check if exists
            existing = conn.execute(
                "SELECT identifier, first_attempted FROM download_results WHERE identifier = ?",
                (identifier,),
            ).fetchone()

            if existing:
                # Update existing
                conn.execute(
                    """
                    UPDATE download_results
                    SET status = 'success',
                        last_attempted = ?,
                        attempt_count = attempt_count + 1,
                        publisher = COALESCE(?, publisher),
                        strategy_used = ?,
                        landing_url = COALESCE(?, landing_url),
                        pdf_url = ?,
                        local_path = ?,
                        sanitized_filename = COALESCE(?, sanitized_filename),
                        error_reason = NULL,
                        should_retry = 1,
                        updated_at = ?
                    WHERE identifier = ?
                """,
                    (
                        now,
                        publisher,
                        strategy_used,
                        landing_url,
                        pdf_url,
                        local_path,
                        sanitized_filename,
                        now,
                        identifier,
                    ),
                )
            else:
                # Insert new
                conn.execute(
                    """
                    INSERT INTO download_results (
                        identifier, status, first_attempted, last_attempted,
                        attempt_count, publisher, strategy_used, landing_url,
                        pdf_url, local_path, sanitized_filename, updated_at
                    ) VALUES (?, 'success', ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        identifier,
                        now,
                        now,
                        publisher,
                        strategy_used,
                        landing_url,
                        pdf_url,
                        local_path,
                        sanitized_filename,
                        now,
                    ),
                )

        logger.info(f"Recorded success for {identifier}")

    def record_failure(
        self,
        identifier: str,
        error_reason: str,
        publisher: Optional[str] = None,
        strategy_used: Optional[str] = None,
        landing_url: Optional[str] = None,
        pdf_url: Optional[str] = None,
        cloudflare_detected: bool = False,
        should_retry: bool = True,
    ):
        """
        Record failed download.

        Args:
            identifier: DOI or other identifier
            error_reason: Why it failed
            publisher: Publisher name
            strategy_used: Strategy class name
            landing_url: Landing page URL
            pdf_url: PDF URL (if found but download failed)
            cloudflare_detected: Was Cloudflare detected?
            should_retry: Should we retry later? (False for paywalls)
        """
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            existing = conn.execute(
                "SELECT identifier, first_attempted, attempt_count FROM download_results WHERE identifier = ?",
                (identifier,),
            ).fetchone()

            if existing:
                # Update existing
                conn.execute(
                    """
                    UPDATE download_results
                    SET status = 'failure',
                        last_attempted = ?,
                        attempt_count = attempt_count + 1,
                        publisher = COALESCE(?, publisher),
                        strategy_used = ?,
                        landing_url = COALESCE(?, landing_url),
                        pdf_url = COALESCE(?, pdf_url),
                        error_reason = ?,
                        cloudflare_detected = ?,
                        should_retry = ?,
                        file_exists = 0,
                        updated_at = ?
                    WHERE identifier = ?
                """,
                    (
                        now,
                        publisher,
                        strategy_used,
                        landing_url,
                        pdf_url,
                        error_reason,
                        cloudflare_detected,
                        should_retry,
                        now,
                        identifier,
                    ),
                )
            else:
                # Insert new
                conn.execute(
                    """
                    INSERT INTO download_results (
                        identifier, status, first_attempted, last_attempted,
                        attempt_count, publisher, strategy_used, landing_url,
                        pdf_url, error_reason, cloudflare_detected, should_retry,
                        file_exists, updated_at
                    ) VALUES (?, 'failure', ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                    (
                        identifier,
                        now,
                        now,
                        publisher,
                        strategy_used,
                        landing_url,
                        pdf_url,
                        error_reason,
                        cloudflare_detected,
                        should_retry,
                        now,
                    ),
                )

        logger.info(f"Recorded failure for {identifier}: {error_reason}")

    def should_download(self, identifier: str, max_attempts: int = 3) -> tuple:
        """
        Check if we should attempt download.

        Args:
            identifier: DOI or other identifier
            max_attempts: Maximum retry attempts

        Returns:
            (should_download: bool, reason: str or None)
        """
        result = self.get_result(identifier)

        if not result:
            return (True, None)  # Never tried - download

        if result["status"] == "success":
            return (False, "Already downloaded successfully")  # Already have it - skip

        if not result["should_retry"]:
            return (
                False,
                f"Permanent failure: {result['error_reason']}",
            )  # Marked as permanent failure - skip

        if result["attempt_count"] >= max_attempts:
            return (
                False,
                f"Max attempts reached ({result['attempt_count']}/{max_attempts})",
            )  # Too many attempts - skip

        return (True, None)  # Can retry

    def get_batch_status(
        self, identifiers: List[str], max_attempts: int = 3, min_retry_delay_hours: int = 24
    ) -> Dict[str, tuple]:
        """
        Batch check download status for multiple identifiers.

        Much faster than calling should_download() for each identifier individually.

        Args:
            identifiers: List of DOIs or other identifiers
            max_attempts: Maximum retry attempts
            min_retry_delay_hours: Minimum hours to wait before retrying a failure (default: 24)

        Returns:
            Dict mapping identifier -> (should_download: bool, reason: str or None)
        """
        if not identifiers:
            return {}

        # Query all identifiers at once
        placeholders = ",".join("?" * len(identifiers))
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"""
                SELECT identifier, status, should_retry, attempt_count, error_reason, last_attempted
                FROM download_results
                WHERE identifier IN ({placeholders})
            """,
                identifiers,
            )

            results = {row["identifier"]: dict(row) for row in cursor.fetchall()}

        # Build status dict
        from datetime import datetime, timedelta

        now = datetime.now()
        min_retry_delay = timedelta(hours=min_retry_delay_hours)

        status_dict = {}
        for identifier in identifiers:
            result = results.get(identifier)

            if not result:
                status_dict[identifier] = (True, None)  # Never tried
            elif result["status"] == "success":
                status_dict[identifier] = (False, "Already downloaded successfully")
            elif not result["should_retry"]:
                status_dict[identifier] = (False, f"Permanent failure: {result['error_reason']}")
            elif result["attempt_count"] >= max_attempts:
                status_dict[identifier] = (
                    False,
                    f"Max attempts reached ({result['attempt_count']}/{max_attempts})",
                )
            else:
                # Check if enough time has passed since last attempt
                last_attempted = datetime.fromisoformat(result["last_attempted"])
                time_since_last = now - last_attempted
                if time_since_last < min_retry_delay:
                    hours_to_wait = (min_retry_delay - time_since_last).total_seconds() / 3600
                    status_dict[identifier] = (
                        False,
                        f"Too soon to retry (wait {hours_to_wait:.1f}h more)",
                    )
                else:
                    status_dict[identifier] = (True, None)  # Can retry now

        return status_dict

    def import_from_metadata_json(self, identifier: str, record: Dict[str, Any]):
        """
        Import single record from old metadata.json format.

        Args:
            identifier: DOI
            record: Dict from metadata.json
        """
        with self._get_connection() as conn:
            # Map old format to new schema
            conn.execute(
                """
                INSERT OR REPLACE INTO download_results (
                    identifier, status, first_attempted, last_attempted,
                    attempt_count, publisher, landing_url, pdf_url,
                    sanitized_filename, error_reason, cloudflare_detected,
                    should_retry, updated_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    identifier,
                    record.get("status", "failure"),
                    record.get("first_attempted"),
                    record.get("last_attempted"),
                    record.get("publisher"),
                    record.get("landing_url"),
                    record.get("pdf_url"),
                    record.get("sanitized_filename"),
                    record.get("error_reason"),
                    record.get("cloudflare_detected", False),
                    record.get("status") != "success",  # Retry failures
                    datetime.now().isoformat(),
                ),
            )

    def export_to_json(self, output_file: str):
        """
        Export to metadata.json format (backward compatibility).

        Args:
            output_file: Path to output JSON file
        """
        with self._get_connection() as conn:
            results = conn.execute("SELECT * FROM download_results").fetchall()

        # Convert to old format
        data = {}
        for row in results:
            data[row["identifier"]] = {
                "first_attempted": row["first_attempted"],
                "last_attempted": row["last_attempted"],
                "status": row["status"],
                "publisher": row["publisher"],
                "landing_url": row["landing_url"],
                "pdf_url": row["pdf_url"],
                "sanitized_filename": row["sanitized_filename"],
                "error_reason": row["error_reason"],
                "cloudflare_detected": bool(row["cloudflare_detected"]),
            }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(data)} results to {output_file}")

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive download statistics."""
        with self._get_connection() as conn:
            # Overall stats
            total = conn.execute("SELECT COUNT(*) as count FROM download_results").fetchone()[
                "count"
            ]
            success = conn.execute(
                "SELECT COUNT(*) as count FROM download_results WHERE status = 'success'"
            ).fetchone()["count"]
            failure = conn.execute(
                "SELECT COUNT(*) as count FROM download_results WHERE status = 'failure'"
            ).fetchone()["count"]
            postponed = conn.execute(
                "SELECT COUNT(*) as count FROM download_results WHERE status = 'postponed'"
            ).fetchone()["count"]
            skipped = conn.execute(
                "SELECT COUNT(*) as count FROM download_results WHERE status = 'skipped'"
            ).fetchone()["count"]

            # File status
            archived = conn.execute(
                "SELECT COUNT(*) as count FROM download_results WHERE archived = 1"
            ).fetchone()["count"]
            missing = conn.execute(
                "SELECT COUNT(*) as count FROM download_results WHERE file_exists = 0 AND archived = 0 AND status = 'success'"
            ).fetchone()["count"]

            # Attempt counts
            avg_attempts = conn.execute(
                "SELECT AVG(attempt_count) as avg FROM download_results"
            ).fetchone()["avg"] or 0

            # By publisher (with totals)
            by_publisher = {}
            for row in conn.execute(
                """
                SELECT publisher, status, COUNT(*) as count
                FROM download_results
                WHERE publisher IS NOT NULL
                GROUP BY publisher, status
            """
            ).fetchall():
                pub = row["publisher"]
                if pub not in by_publisher:
                    by_publisher[pub] = {"success": 0, "failure": 0, "postponed": 0, "total": 0}
                by_publisher[pub][row["status"]] = row["count"]
                by_publisher[pub]["total"] = by_publisher[pub].get("total", 0) + row["count"]

            # Top publishers by volume
            top_publishers = sorted(
                [(pub, stats["total"]) for pub, stats in by_publisher.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10]

            # Recent activity (last 7 days)
            recent_downloads = conn.execute(
                """
                SELECT DATE(last_attempted) as date, COUNT(*) as count
                FROM download_results
                WHERE last_attempted >= date('now', '-7 days')
                GROUP BY DATE(last_attempted)
                ORDER BY date DESC
                """
            ).fetchall()

            # Error reasons breakdown
            error_reasons = {}
            for row in conn.execute(
                """
                SELECT error_reason, COUNT(*) as count
                FROM download_results
                WHERE status = 'failure' AND error_reason IS NOT NULL
                GROUP BY error_reason
                ORDER BY count DESC
                LIMIT 10
                """
            ).fetchall():
                error_reasons[row["error_reason"]] = row["count"]

            # Strategy usage
            strategy_stats = {}
            for row in conn.execute(
                """
                SELECT strategy_used, COUNT(*) as count
                FROM download_results
                WHERE strategy_used IS NOT NULL
                GROUP BY strategy_used
                ORDER BY count DESC
                """
            ).fetchall():
                strategy_stats[row["strategy_used"]] = row["count"]

            return {
                "total": total,
                "success": success,
                "failure": failure,
                "postponed": postponed,
                "skipped": skipped,
                "success_rate": (success / total * 100) if total > 0 else 0,
                "archived": archived,
                "missing": missing,
                "avg_attempts": avg_attempts,
                "by_publisher": by_publisher,
                "top_publishers": top_publishers,
                "recent_activity": [dict(row) for row in recent_downloads],
                "error_reasons": error_reasons,
                "strategy_stats": strategy_stats,
            }

    def get_retry_stats(self, max_attempts: int = 3) -> Dict[str, Any]:
        """
        Get statistics on papers that will retry downloading.

        Shows how many papers will be retried within 1 day and 1 week.

        Args:
            max_attempts: Maximum retry attempts (default: 3)

        Returns:
            Dictionary with retry statistics:
            - total_retry: Total papers that will retry
            - retry_1_day: Papers eligible for retry within 1 day
            - retry_1_week: Papers eligible for retry within 1 week
            - never_retry: Papers marked as should_retry=False
            - max_attempts_reached: Papers that hit max attempts
        """
        from datetime import timedelta

        with self._get_connection() as conn:
            now = datetime.now()
            one_day_ago = now - timedelta(days=1)
            one_week_ago = now - timedelta(weeks=1)

            # Total papers that can retry (should_retry=1 and attempt_count < max_attempts)
            total_retry = conn.execute(
                """
                SELECT COUNT(*) as count FROM download_results
                WHERE status = 'failure'
                AND should_retry = 1
                AND attempt_count < ?
                """,
                (max_attempts,)
            ).fetchone()["count"]

            # Papers that will retry within 1 day (failed in last day)
            retry_1_day = conn.execute(
                """
                SELECT COUNT(*) as count FROM download_results
                WHERE status = 'failure'
                AND should_retry = 1
                AND attempt_count < ?
                AND last_attempted >= ?
                """,
                (max_attempts, one_day_ago.isoformat())
            ).fetchone()["count"]

            # Papers that will retry within 1 week (failed in last week)
            retry_1_week = conn.execute(
                """
                SELECT COUNT(*) as count FROM download_results
                WHERE status = 'failure'
                AND should_retry = 1
                AND attempt_count < ?
                AND last_attempted >= ?
                """,
                (max_attempts, one_week_ago.isoformat())
            ).fetchone()["count"]

            # Papers marked as never retry
            never_retry = conn.execute(
                """
                SELECT COUNT(*) as count FROM download_results
                WHERE status = 'failure'
                AND should_retry = 0
                """
            ).fetchone()["count"]

            # Papers that hit max attempts
            max_attempts_reached = conn.execute(
                """
                SELECT COUNT(*) as count FROM download_results
                WHERE status = 'failure'
                AND attempt_count >= ?
                """,
                (max_attempts,)
            ).fetchone()["count"]

            return {
                "total_retry": total_retry,
                "retry_1_day": retry_1_day,
                "retry_1_week": retry_1_week,
                "never_retry": never_retry,
                "max_attempts_reached": max_attempts_reached,
                "summary": (
                    f"{retry_1_day} papers will retry within 1 day, "
                    f"{retry_1_week} within 1 week (out of {total_retry} retryable papers)"
                )
            }

    def mark_archived(self, identifier: str, archive_location: str):
        """
        Mark a PDF as archived to remote location.

        Args:
            identifier: DOI or identifier
            archive_location: Remote location (e.g., 'sftp://server/path', 's3://bucket/key')

        Example:
            db.mark_archived('10.1007/xxx', 'sftp://archive.edu/pdfs/10.1007_xxx.pdf')
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE download_results
                SET archived = 1,
                    archive_location = ?,
                    archive_date = ?,
                    file_exists = 0,
                    updated_at = ?
                WHERE identifier = ?
            """,
                (
                    archive_location,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    identifier,
                ),
            )

        logger.info(f"Marked {identifier} as archived at {archive_location}")

    def mark_file_missing(self, identifier: str):
        """
        Mark a PDF file as missing (deleted but not archived).

        Args:
            identifier: DOI or identifier
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE download_results
                SET file_exists = 0,
                    updated_at = ?
                WHERE identifier = ?
            """,
                (datetime.now().isoformat(), identifier),
            )

        logger.info(f"Marked {identifier} as file missing")

    def mark_for_retry(self, identifier: str):
        """
        Mark an entry for retry by resetting attempt count and enabling retry.

        Useful for forcing a re-download of a failed or problematic PDF.
        Resets attempt_count to 0 and sets should_retry to True.

        Args:
            identifier: DOI or identifier to mark for retry

        Example:
            >>> db = DownloadMetadataDB("metadata.db")
            >>> db.mark_for_retry("2302.00754v3")
            >>> # Now re-run fetcher - it will retry this identifier
        """
        with self._get_connection() as conn:
            # Check if entry exists
            existing = conn.execute(
                "SELECT identifier FROM download_results WHERE identifier = ?",
                (identifier,)
            ).fetchone()

            if not existing:
                logger.warning(f"Cannot mark for retry - identifier not found: {identifier}")
                return

            # Reset for retry
            conn.execute(
                """
                UPDATE download_results
                SET attempt_count = 0,
                    should_retry = 1,
                    updated_at = ?
                WHERE identifier = ?
            """,
                (datetime.now().isoformat(), identifier),
            )

        logger.info(f"Marked {identifier} for retry (reset attempt count)")

    def delete_entry(self, identifier: str) -> bool:
        """
        Delete an entry from the database.

        Useful for completely removing a download record to force a fresh attempt.
        Note: This does NOT delete the PDF file itself, only the database entry.

        Args:
            identifier: DOI or identifier to delete

        Returns:
            True if entry was deleted, False if not found

        Example:
            >>> db = DownloadMetadataDB("metadata.db")
            >>> db.delete_entry("2302.00754v3")
            >>> # Entry removed - fetcher will treat as never attempted
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM download_results WHERE identifier = ?",
                (identifier,)
            )
            deleted_count = cursor.rowcount

        if deleted_count > 0:
            logger.info(f"Deleted entry for {identifier}")
            return True
        else:
            logger.warning(f"No entry found to delete: {identifier}")
            return False

    def verify_files(self) -> Dict[str, List[str]]:
        """
        Verify that all successful downloads still exist on disk.

        Returns:
            Dict with:
                'verified': List of identifiers with existing files
                'missing': List of identifiers with missing files
                'archived': List of identifiers marked as archived
        """
        verified = []
        missing = []
        archived = []

        with self._get_connection() as conn:
            results = conn.execute(
                """
                SELECT identifier, local_path, archived, file_exists
                FROM download_results
                WHERE status = 'success'
            """
            ).fetchall()

            for row in results:
                identifier = row["identifier"]
                local_path = row["local_path"]
                is_archived = row["archived"]
                file_exists_flag = row["file_exists"]

                if is_archived:
                    archived.append(identifier)
                elif local_path and Path(local_path).exists():
                    verified.append(identifier)
                    # Update file_exists if it was marked missing
                    if not file_exists_flag:
                        conn.execute(
                            """
                            UPDATE download_results
                            SET file_exists = 1, updated_at = ?
                            WHERE identifier = ?
                        """,
                            (datetime.now().isoformat(), identifier),
                        )
                else:
                    missing.append(identifier)
                    # Mark as missing in DB
                    if file_exists_flag:
                        conn.execute(
                            """
                            UPDATE download_results
                            SET file_exists = 0, updated_at = ?
                            WHERE identifier = ?
                        """,
                            (datetime.now().isoformat(), identifier),
                        )

        logger.info(
            f"Verified files: {len(verified)} exist, {len(missing)} missing, {len(archived)} archived"
        )

        return {"verified": verified, "missing": missing, "archived": archived}

    def get_archived(self) -> List[Dict[str, Any]]:
        """
        Get all archived downloads.

        Returns:
            List of dicts with identifier, archive_location, archive_date
        """
        with self._get_connection() as conn:
            results = conn.execute(
                """
                SELECT identifier, archive_location, archive_date, sanitized_filename
                FROM download_results
                WHERE archived = 1
                ORDER BY archive_date DESC
            """
            ).fetchall()

            return [dict(row) for row in results]

    def get_missing(self) -> List[Dict[str, Any]]:
        """
        Get all downloads with missing files (deleted but not archived).

        Returns:
            List of dicts with identifier, local_path, last_attempted
        """
        with self._get_connection() as conn:
            results = conn.execute(
                """
                SELECT identifier, local_path, sanitized_filename, last_attempted
                FROM download_results
                WHERE status = 'success' AND file_exists = 0 AND archived = 0
                ORDER BY last_attempted DESC
            """
            ).fetchall()

            return [dict(row) for row in results]

    def merge_from(
        self,
        source_db_path: str,
        source_pdf_dir: Optional[str] = None,
        target_pdf_dir: Optional[str] = None,
        move_files: bool = True,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Merge another metadata database into this one.

        Conflict resolution strategy:
        - Keep successful downloads over failed ones
        - For same status: keep entry with most recent last_attempted
        - Optionally move/copy PDF files from source to target directory

        Args:
            source_db_path: Path to source database file to merge from
            source_pdf_dir: Source PDF directory (if None, extracted from local_path entries)
            target_pdf_dir: Target PDF directory (if None, extracted from local_path entries)
            move_files: If True, move PDFs; if False, copy PDFs
            dry_run: If True, show what would happen without making changes

        Returns:
            Dict with merge statistics

        Example:
            # Merge database from another folder
            db = DownloadMetadataDB("pdfs/downloads.db")
            stats = db.merge_from(
                source_db_path="data/results/pdfs/downloads.db",
                source_pdf_dir="data/results/pdfs",
                target_pdf_dir="pdfs",
                move_files=True
            )
            print(f"Merged: {stats['added']} added, {stats['updated']} updated")
        """
        import shutil
        from pathlib import Path

        source_db_path = Path(source_db_path)
        if not source_db_path.exists():
            raise FileNotFoundError(f"Source database not found: {source_db_path}")

        logger.info(f"Merging from {source_db_path} into {self.db_path}")
        if dry_run:
            logger.info("DRY RUN MODE - no changes will be made")

        stats = {
            'total_source_entries': 0,
            'added': 0,
            'updated': 0,
            'kept_existing': 0,
            'conflicts_resolved': 0,
            'files_moved': 0,
            'files_copied': 0,
            'files_skipped': 0,
            'errors': []
        }

        # Connect to source database
        source_conn = sqlite3.connect(str(source_db_path), timeout=30.0)
        source_conn.row_factory = sqlite3.Row

        try:
            # Get all entries from source database
            source_results = source_conn.execute("SELECT * FROM download_results").fetchall()
            stats['total_source_entries'] = len(source_results)

            logger.info(f"Found {len(source_results)} entries in source database")

            for source_row in source_results:
                source_data = dict(source_row)
                identifier = source_data['identifier']

                # Check if identifier exists in target database
                existing = self.get_result(identifier)

                # Determine which entry to keep
                should_update = False
                action = None

                if not existing:
                    # New entry - add it
                    should_update = True
                    action = 'add'
                    stats['added'] += 1
                else:
                    # Conflict resolution: successful over failed
                    source_status = source_data['status']
                    existing_status = existing['status']

                    if source_status == 'success' and existing_status != 'success':
                        # Source succeeded, target didn't - use source
                        should_update = True
                        action = 'update_success_over_failure'
                        stats['updated'] += 1
                        stats['conflicts_resolved'] += 1
                    elif source_status != 'success' and existing_status == 'success':
                        # Target succeeded, source didn't - keep target
                        should_update = False
                        action = 'keep_existing_success'
                        stats['kept_existing'] += 1
                    else:
                        # Same status - use most recent
                        source_time = source_data.get('last_attempted', '')
                        existing_time = existing.get('last_attempted', '')

                        if source_time > existing_time:
                            should_update = True
                            action = 'update_newer'
                            stats['updated'] += 1
                        else:
                            should_update = False
                            action = 'keep_existing_newer'
                            stats['kept_existing'] += 1

                if dry_run:
                    logger.info(f"[DRY RUN] {identifier}: {action}")
                    continue

                # Update database if needed
                if should_update:
                    # Handle PDF file movement/copying
                    source_path = source_data.get('local_path')
                    new_local_path = source_path

                    if source_path and source_data['status'] == 'success':
                        source_pdf = Path(source_path)

                        # Auto-detect source PDF directory if not provided
                        if source_pdf_dir:
                            # Use provided source directory
                            detected_source_dir = Path(source_pdf_dir)
                            # Make absolute path from source_pdf_dir + filename
                            source_pdf = detected_source_dir / source_pdf.name
                        elif not source_pdf.is_absolute():
                            # Relative path - need to resolve from source DB location
                            detected_source_dir = source_db_path.parent
                            source_pdf = detected_source_dir / source_pdf
                        # else: already absolute, use as-is

                        # Determine target path
                        if target_pdf_dir:
                            target_pdf = Path(target_pdf_dir) / source_pdf.name
                        else:
                            # No target dir specified - keep relative to target DB
                            target_pdf = self.db_path.parent / source_pdf.name

                        # Move or copy file if it exists and target is different
                        if source_pdf.exists():
                            if source_pdf.resolve() == target_pdf.resolve():
                                # Same file - no need to move
                                stats['files_skipped'] += 1
                                new_local_path = str(target_pdf)
                            else:
                                try:
                                    target_pdf.parent.mkdir(parents=True, exist_ok=True)

                                    if move_files:
                                        shutil.move(str(source_pdf), str(target_pdf))
                                        stats['files_moved'] += 1
                                        logger.info(f"Moved: {source_pdf.name}")
                                    else:
                                        shutil.copy2(str(source_pdf), str(target_pdf))
                                        stats['files_copied'] += 1
                                        logger.info(f"Copied: {source_pdf.name}")

                                    new_local_path = str(target_pdf)
                                except Exception as e:
                                    error_msg = f"Failed to move/copy {source_pdf.name}: {e}"
                                    logger.error(error_msg)
                                    stats['errors'].append(error_msg)
                        else:
                            # Source file doesn't exist - just update metadata
                            logger.warning(f"Source file not found: {source_pdf}")
                            new_local_path = str(target_pdf)  # Update path anyway

                    # Insert/update database entry
                    with self._get_connection() as conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO download_results (
                                identifier, status, first_attempted, last_attempted,
                                attempt_count, should_retry, publisher, strategy_used,
                                landing_url, pdf_url, sanitized_filename, local_path,
                                file_exists, archived, archive_location, archive_date,
                                error_reason, cloudflare_detected, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            identifier,
                            source_data['status'],
                            source_data['first_attempted'],
                            source_data['last_attempted'],
                            source_data.get('attempt_count', 1),
                            source_data.get('should_retry', 1),
                            source_data.get('publisher'),
                            source_data.get('strategy_used'),
                            source_data.get('landing_url'),
                            source_data.get('pdf_url'),
                            source_data.get('sanitized_filename'),
                            new_local_path,
                            source_data.get('file_exists', 1),
                            source_data.get('archived', 0),
                            source_data.get('archive_location'),
                            source_data.get('archive_date'),
                            source_data.get('error_reason'),
                            source_data.get('cloudflare_detected', 0),
                            datetime.now().isoformat()
                        ))

                    logger.debug(f"Merged {identifier}: {action}")

        finally:
            source_conn.close()

        logger.info(f"Merge complete: {stats['added']} added, {stats['updated']} updated, "
                   f"{stats['kept_existing']} kept existing")
        logger.info(f"Files: {stats['files_moved']} moved, {stats['files_copied']} copied, "
                   f"{stats['files_skipped']} skipped")

        if stats['errors']:
            logger.warning(f"{len(stats['errors'])} errors occurred during merge")

        return stats

    def scan_for_orphaned_pdfs(self, pdf_dirs: List[str]) -> List[Dict[str, Any]]:
        """
        Scan directories for PDF files not in the database.

        Args:
            pdf_dirs: List of directories to scan for PDFs

        Returns:
            List of dicts with orphaned PDF info:
                - 'path': Full path to PDF file
                - 'filename': Base filename
                - 'inferred_doi': DOI extracted from filename (if possible)
                - 'size_mb': File size in MB
        """
        orphaned = []

        # Get all identifiers currently in database
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT identifier, local_path FROM download_results")
            db_identifiers = {row['identifier'] for row in cursor.fetchall()}
            db_paths = {Path(row['local_path']).resolve() for row in cursor.fetchall() if row['local_path']}

        logger.info(f"Database contains {len(db_identifiers)} identifiers")

        # Scan each directory
        for pdf_dir in pdf_dirs:
            pdf_path = Path(pdf_dir)
            if not pdf_path.exists():
                logger.warning(f"Directory not found: {pdf_dir}")
                continue

            logger.info(f"Scanning {pdf_dir} for orphaned PDFs...")

            # Find all PDF files
            for pdf_file in pdf_path.glob("*.pdf"):
                # Skip if this exact file path is already in database
                if pdf_file.resolve() in db_paths:
                    continue

                # Try to extract DOI from filename
                inferred_doi = self._infer_doi_from_filename(pdf_file.name)

                # Skip if we have this DOI in database (different path)
                if inferred_doi and inferred_doi in db_identifiers:
                    logger.debug(f"Found DOI in DB but different path: {pdf_file.name}")
                    continue

                # This is an orphaned file
                file_size_mb = pdf_file.stat().st_size / (1024 * 1024)
                orphaned.append({
                    'path': str(pdf_file),
                    'filename': pdf_file.name,
                    'inferred_doi': inferred_doi,
                    'size_mb': file_size_mb
                })

        logger.info(f"Found {len(orphaned)} orphaned PDF files")
        return orphaned

    def _infer_doi_from_filename(self, filename: str) -> Optional[str]:
        """
        Try to extract DOI from PDF filename.

        Common patterns:
        - 10.1007_s10623-024-01403-z.pdf
        - 10.1016-j.ecresq.2020.04.004.pdf
        - doi_10.1234_abcd.pdf

        Args:
            filename: PDF filename

        Returns:
            DOI string or None if not found
        """
        import re

        # Remove .pdf extension
        name = filename.replace('.pdf', '').replace('.PDF', '')

        # Pattern: 10.XXXX followed by various separators
        # DOIs start with "10." followed by 4+ digits, then a slash or separator
        pattern = r'10\.\d{4,}[/_\-.][\w\-._/]+'

        match = re.search(pattern, name)
        if match:
            doi = match.group(0)
            # Convert underscores and dashes back to slashes where appropriate
            # DOI format: 10.XXXX/rest
            parts = doi.split('.')
            if len(parts) >= 2:
                # Find the first separator after 10.XXXX
                prefix_match = re.match(r'(10\.\d{4,})[/_\-](.+)', doi)
                if prefix_match:
                    prefix = prefix_match.group(1)
                    suffix = prefix_match.group(2)
                    # Replace remaining underscores/dashes with standard separators
                    suffix = suffix.replace('_', '-').replace('--', '-')
                    return f"{prefix}/{suffix}"
            return doi.replace('_', '/').replace('--', '/')

        return None

    def add_orphaned_pdf(
        self,
        pdf_path: str,
        inferred_doi: Optional[str] = None,
        use_filename_as_identifier: bool = True
    ) -> str:
        """
        Add an orphaned PDF to the database with minimal metadata.

        Args:
            pdf_path: Path to the PDF file
            inferred_doi: DOI extracted from filename (optional)
            use_filename_as_identifier: If no DOI, use filename as identifier

        Returns:
            The identifier used for this entry

        Raises:
            ValueError: If no identifier can be determined
        """
        pdf_path_obj = Path(pdf_path)

        # Determine identifier
        if inferred_doi:
            identifier = inferred_doi
        elif use_filename_as_identifier:
            # Use filename without extension as identifier
            identifier = pdf_path_obj.stem
        else:
            raise ValueError(f"Cannot determine identifier for {pdf_path}")

        # Check if already exists
        existing = self.get_result(identifier)
        if existing:
            logger.warning(f"Identifier {identifier} already exists in database")
            return identifier

        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO download_results (
                    identifier, status, first_attempted, last_attempted,
                    attempt_count, local_path, sanitized_filename,
                    file_exists, should_retry, updated_at
                ) VALUES (?, 'success', ?, ?, 1, ?, ?, 1, 1, ?)
                """,
                (
                    identifier,
                    now,
                    now,
                    str(pdf_path_obj),
                    pdf_path_obj.name,
                    now,
                ),
            )

        logger.info(f"Added orphaned PDF to database: {identifier}")
        return identifier


if __name__ == "__main__":
    # Demo usage
    print("=" * 80)
    print("Download Metadata Database Demo")
    print("=" * 80)

    db = DownloadMetadataDB("test_metadata.db")

    # Record success
    print("\n1. Recording successful download...")
    db.record_success(
        identifier="10.1007/s10623-024-01403-z",
        local_path="pdfs/10.1007_s10623-024-01403-z.pdf",
        publisher="springer",
        strategy_used="SpringerStrategy",
        landing_url="https://link.springer.com/article/10.1007/s10623-024-01403-z",
        pdf_url="https://link.springer.com/content/pdf/10.1007/s10623-024-01403-z.pdf",
        sanitized_filename="10.1007_s10623-024-01403-z.pdf",
    )

    # Record failure
    print("\n2. Recording failed download...")
    db.record_failure(
        identifier="10.1016/j.ecresq.2020.04.004",
        error_reason="Could not find PDF link",
        publisher="elsevier",
        strategy_used="ElsevierStrategy",
        should_retry=False,  # Paywall - don't retry
    )

    # Check should_download
    print("\n3. Testing should_download...")
    test_cases = [
        ("10.1007/s10623-024-01403-z", False, "already success"),
        ("10.1016/j.ecresq.2020.04.004", False, "marked no-retry"),
        ("10.1234/new-paper", True, "never tried"),
    ]

    for doi, expected, reason in test_cases:
        result = db.should_download(doi)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {doi[:40]:40s} -> {result} ({reason})")

    # Stats
    print("\n4. Statistics:")
    stats = db.get_stats()
    print(f"  Total: {stats['total']}")
    print(f"  Success: {stats['success']}")
    print(f"  Failure: {stats['failure']}")
    print(f"  Success rate: {stats['success_rate']:.1f}%")

    print("\n" + "=" * 80)
    print("Database ready!")
