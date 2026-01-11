"""
Problem Papers Management

Track and blacklist papers that cause download issues (hangs, timeouts, etc.)
"""

from pathlib import Path
from typing import Set, Optional
import json
import logging

logger = logging.getLogger(__name__)


class ProblemPapersRegistry:
    """
    Registry of papers that cause download issues.

    Papers can be blacklisted due to:
    - Repeated timeouts
    - Download hangs
    - Malformed responses
    - Server issues

    The registry is stored in a JSON file and persists across runs.
    """

    def __init__(self, registry_path: Optional[Path] = None):
        """
        Initialize problem papers registry.

        Args:
            registry_path: Path to JSON file storing blacklist
                          (default: ~/.pdf_fetcher/problem_papers.json)
        """
        if registry_path is None:
            registry_path = Path.home() / ".pdf_fetcher" / "problem_papers.json"

        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        self.blacklist: Set[str] = set()
        self.reasons: dict = {}  # identifier -> reason
        self.load()

    def load(self):
        """Load blacklist from file."""
        if not self.registry_path.exists():
            return

        try:
            with open(self.registry_path, 'r') as f:
                data = json.load(f)
                self.blacklist = set(data.get('blacklist', []))
                self.reasons = data.get('reasons', {})
                logger.info(f"Loaded {len(self.blacklist)} problem papers from {self.registry_path}")
        except Exception as e:
            logger.warning(f"Could not load problem papers registry: {e}")

    def save(self):
        """Save blacklist to file."""
        try:
            data = {
                'blacklist': list(self.blacklist),
                'reasons': self.reasons,
            }
            with open(self.registry_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self.blacklist)} problem papers to {self.registry_path}")
        except Exception as e:
            logger.warning(f"Could not save problem papers registry: {e}")

    def is_blacklisted(self, identifier: str) -> bool:
        """
        Check if identifier is blacklisted.

        Args:
            identifier: DOI or identifier to check

        Returns:
            True if blacklisted
        """
        return identifier in self.blacklist

    def add(self, identifier: str, reason: str = "Unknown"):
        """
        Add identifier to blacklist.

        Args:
            identifier: DOI or identifier to blacklist
            reason: Reason for blacklisting
        """
        if identifier not in self.blacklist:
            self.blacklist.add(identifier)
            self.reasons[identifier] = reason
            self.save()
            logger.warning(f"🚫 Blacklisted: {identifier} (reason: {reason})")

    def remove(self, identifier: str):
        """
        Remove identifier from blacklist.

        Args:
            identifier: DOI or identifier to remove
        """
        if identifier in self.blacklist:
            self.blacklist.remove(identifier)
            self.reasons.pop(identifier, None)
            self.save()
            logger.info(f"✓ Removed from blacklist: {identifier}")

    def get_reason(self, identifier: str) -> Optional[str]:
        """
        Get blacklist reason for identifier.

        Args:
            identifier: DOI or identifier

        Returns:
            Reason string or None if not blacklisted
        """
        return self.reasons.get(identifier)

    def filter_batch(self, identifiers: list) -> tuple:
        """
        Filter out blacklisted identifiers from batch.

        Args:
            identifiers: List of identifiers to check

        Returns:
            (safe_identifiers, blacklisted_identifiers)
        """
        safe = [id for id in identifiers if not self.is_blacklisted(id)]
        blacklisted = [id for id in identifiers if self.is_blacklisted(id)]

        if blacklisted:
            logger.info(f"Filtered out {len(blacklisted)} blacklisted papers")

        return safe, blacklisted

    def get_stats(self) -> dict:
        """Get blacklist statistics."""
        return {
            'total_blacklisted': len(self.blacklist),
            'registry_path': str(self.registry_path),
        }

    def clear(self):
        """Clear all entries from blacklist."""
        self.blacklist.clear()
        self.reasons.clear()
        self.save()
        logger.info("Cleared all blacklisted papers")
