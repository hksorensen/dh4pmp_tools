"""
Golden Values - Track and validate key statistics for reproducibility

Usage:
    from golden_values import GoldenValues

    # Validation mode (default)
    golden = GoldenValues("golden_values.yaml")
    golden.check("num_papers", 1234)
    golden.check("avg_score", 0.85, tolerance=0.01)
    golden.save()

    # Update mode (blessing new values)
    golden = GoldenValues("golden_values.yaml", update_mode=True)
    golden.check("num_papers", 1250)  # New value will be saved
    golden.save()

    # Context manager (auto-saves)
    with GoldenValues("golden_values.yaml") as golden:
        golden.check("value", 42)
"""

from .golden_values import GoldenValues

__version__ = "0.1.0"
__author__ = "Henrik Kragh Sørensen"

__all__ = ["GoldenValues"]
