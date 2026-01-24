"""
Golden Values Tracker

Track and validate key statistics against golden reference values.
Useful for ensuring reproducibility in data pipelines and scientific computing.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union
import yaml

logger = logging.getLogger(__name__)


class GoldenValues:
    """
    Track and validate computed values against golden reference values.

    This class helps ensure reproducibility by:
    1. Tracking important computed values during pipeline execution
    2. Comparing them against previously validated "golden" values
    3. Alerting when values change unexpectedly
    4. Providing a mechanism to update golden values when changes are intentional

    Typical workflow:
    1. Normal runs: validate against golden values (halts on mismatch)
    2. After verified changes: run with update_mode=True to bless new values
    3. Commit golden_values.yaml to version control for reproducibility

    Example:
        >>> golden = GoldenValues("golden_values.yaml", update_mode=False)
        >>> golden.check("num_papers", 1234)  # Validates
        >>> golden.check("avg_score", 0.85, tolerance=0.01)  # 1% tolerance
        >>> golden.save()  # Save if update_mode=True
    """

    def __init__(
        self,
        golden_file: Union[str, Path],
        update_mode: bool = False,
        strict: bool = True,
    ):
        """
        Initialize golden values tracker.

        Args:
            golden_file: Path to YAML file storing golden values
            update_mode: If True, update golden values instead of validating
            strict: If True, raise ValueError on mismatch (if False, just log warning)
        """
        self.golden_file = Path(golden_file)
        self.update_mode = update_mode
        self.strict = strict
        self.current_values: Dict[str, Any] = {}
        self.mismatches: Dict[str, tuple] = {}  # key -> (expected, got)

        # Load existing golden values
        if self.golden_file.exists():
            with open(self.golden_file) as f:
                self.golden = yaml.safe_load(f) or {}
            logger.info(f"Loaded {len(self.golden)} golden values from {self.golden_file}")
        else:
            self.golden = {}
            logger.info(f"No existing golden values file found at {self.golden_file}")

    def check(
        self,
        key: str,
        value: Union[int, float, str, bool],
        tolerance: Optional[float] = None,
        absolute_tolerance: Optional[float] = None,
    ) -> bool:
        """
        Check a value against its golden reference.

        Args:
            key: Identifier for this value (e.g., "num_papers_downloaded")
            value: Computed value to check
            tolerance: For numeric values, acceptable relative difference (e.g., 0.01 = 1%)
            absolute_tolerance: For numeric values, acceptable absolute difference

        Returns:
            True if value matches golden value (or no golden value exists), False otherwise

        Raises:
            ValueError: If mismatch and strict=True and not update_mode

        Example:
            >>> golden.check("count", 100)  # Exact match for integers
            >>> golden.check("ratio", 0.523, tolerance=0.01)  # 1% relative tolerance
            >>> golden.check("delta", 0.001, absolute_tolerance=0.0001)  # Absolute tolerance
        """
        self.current_values[key] = value

        # New golden value
        if key not in self.golden:
            logger.warning(f"⚠ NEW golden value: {key} = {value}")
            if self.update_mode:
                logger.info(f"  → Will be added to golden values")
            else:
                logger.warning(f"  → Run with update_mode=True to save")
            return True

        golden_value = self.golden[key]

        # Compare values
        matches = self._values_match(
            value, golden_value, tolerance=tolerance, absolute_tolerance=absolute_tolerance
        )

        if not matches:
            self.mismatches[key] = (golden_value, value)
            self._handle_mismatch(key, golden_value, value)
            return False
        else:
            logger.debug(f"✓ {key} = {value} (matches golden)")
            return True

    def _values_match(
        self,
        value: Any,
        golden_value: Any,
        tolerance: Optional[float] = None,
        absolute_tolerance: Optional[float] = None,
    ) -> bool:
        """Check if two values match within specified tolerance."""
        # Type mismatch
        if type(value) != type(golden_value):
            return False

        # Exact comparison for non-numeric types
        if not isinstance(value, (int, float)):
            return value == golden_value

        # Numeric comparison with tolerances
        if absolute_tolerance is not None:
            diff = abs(value - golden_value)
            return diff <= absolute_tolerance

        if tolerance is not None:
            if golden_value == 0:
                # For zero golden value, use absolute difference
                return abs(value) <= tolerance
            else:
                # Relative difference
                rel_diff = abs(value - golden_value) / abs(golden_value)
                return rel_diff <= tolerance

        # Default: exact match
        return value == golden_value

    def _handle_mismatch(self, key: str, expected: Any, got: Any):
        """Handle a golden value mismatch."""
        logger.error("=" * 70)
        logger.error(f"❌ GOLDEN VALUE MISMATCH: {key}")
        logger.error(f"   Expected: {expected}")
        logger.error(f"   Got:      {got}")

        if isinstance(expected, (int, float)) and isinstance(got, (int, float)):
            diff = got - expected
            if expected != 0:
                pct_change = 100 * diff / abs(expected)
                logger.error(f"   Diff:     {diff:+.4g} ({pct_change:+.2f}%)")
            else:
                logger.error(f"   Diff:     {diff:+.4g}")

        logger.error("=" * 70)

        if self.update_mode:
            logger.warning(f"  → Will update golden value (update_mode=True)")
        else:
            msg = (
                f"Golden value mismatch for '{key}'. "
                f"Expected {expected}, got {got}. "
                f"Run with update_mode=True to accept new value."
            )
            if self.strict:
                raise ValueError(msg)
            else:
                logger.warning(f"  → Continuing despite mismatch (strict=False)")

    def save(self) -> None:
        """
        Save current values to golden values file.

        In update_mode: Updates golden values with current values
        Otherwise: Only logs a message
        """
        if not self.update_mode:
            if self.current_values:
                logger.info(
                    f"Golden values tracked: {len(self.current_values)} values "
                    f"(not saving, update_mode=False)"
                )
            return

        # Merge: keep existing values, update checked ones
        self.golden.update(self.current_values)

        # Ensure directory exists
        self.golden_file.parent.mkdir(parents=True, exist_ok=True)

        # Save as YAML
        with open(self.golden_file, 'w') as f:
            yaml.dump(
                self.golden,
                f,
                sort_keys=True,
                default_flow_style=False,
                allow_unicode=True,
            )

        logger.info(f"✓ Updated golden values file: {self.golden_file}")
        logger.info(f"  Total values: {len(self.golden)}")
        logger.info(f"  New/updated: {len(self.current_values)}")

    def get_all(self) -> Dict[str, Any]:
        """
        Get all golden values.

        Returns:
            Dictionary of all golden values
        """
        return self.golden.copy()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a specific golden value.

        Args:
            key: Key to look up
            default: Default value if key not found

        Returns:
            Golden value or default
        """
        return self.golden.get(key, default)

    def summary(self) -> str:
        """
        Get a summary of golden values status.

        Returns:
            Formatted summary string
        """
        lines = []
        lines.append("=" * 70)
        lines.append("GOLDEN VALUES SUMMARY")
        lines.append("=" * 70)
        lines.append(f"Golden file: {self.golden_file}")
        lines.append(f"Update mode: {self.update_mode}")
        lines.append(f"Strict mode: {self.strict}")
        lines.append(f"")
        lines.append(f"Total golden values: {len(self.golden)}")
        lines.append(f"Values checked this run: {len(self.current_values)}")

        if self.mismatches:
            lines.append(f"")
            lines.append(f"❌ Mismatches: {len(self.mismatches)}")
            for key, (expected, got) in self.mismatches.items():
                lines.append(f"  {key}: {expected} → {got}")
        else:
            if self.current_values:
                lines.append(f"✓ All values matched")

        lines.append("=" * 70)
        return "\n".join(lines)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - automatically save if no exception."""
        if exc_type is None:
            self.save()
        return False
