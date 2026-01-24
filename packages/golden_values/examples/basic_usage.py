#!/usr/bin/env python3
"""
Basic usage example for golden_values package.

This demonstrates how to use GoldenValues for tracking and validating
key statistics in a data pipeline.
"""

import sys
from pathlib import Path
import tempfile

# Add package to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent))

from golden_values import GoldenValues


def simulate_pipeline_step_1():
    """Simulate first pipeline step that computes some values."""
    return {
        "papers_downloaded": 8523,
        "papers_with_doi": 8234,
        "download_time_sec": 123.4,
    }


def simulate_pipeline_step_2():
    """Simulate second pipeline step."""
    return {
        "diagrams_detected": 12340,
        "avg_diagrams_per_paper": 1.45,
    }


def example_validation_mode():
    """Example: Normal validation mode (checks against golden values)."""
    print("=" * 70)
    print("EXAMPLE 1: Validation Mode")
    print("=" * 70)
    print()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        golden_file = Path(f.name)

    try:
        # First run: establish golden values
        print("First run - establishing golden values...")
        with GoldenValues(golden_file, update_mode=True) as golden:
            results = simulate_pipeline_step_1()
            golden.check("papers_downloaded", results["papers_downloaded"])
            golden.check("papers_with_doi", results["papers_with_doi"])
            golden.check("download_time_sec", results["download_time_sec"], tolerance=0.1)

        print(f"✓ Golden values saved to {golden_file}")
        print()

        # Second run: validate (should pass)
        print("Second run - validation (should pass)...")
        with GoldenValues(golden_file) as golden:
            results = simulate_pipeline_step_1()
            golden.check("papers_downloaded", results["papers_downloaded"])
            golden.check("papers_with_doi", results["papers_with_doi"])

        print("✓ All values matched!")
        print()

        # Third run: value changed (should fail)
        print("Third run - value changed (should fail)...")
        try:
            with GoldenValues(golden_file) as golden:
                golden.check("papers_downloaded", 9000)  # Changed!
        except ValueError as e:
            print(f"✓ Caught expected error: {str(e)[:80]}...")
        print()

    finally:
        golden_file.unlink(missing_ok=True)


def example_tolerance():
    """Example: Using tolerance for floating point values."""
    print("=" * 70)
    print("EXAMPLE 2: Tolerance for Floats")
    print("=" * 70)
    print()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        golden_file = Path(f.name)

    try:
        # Establish golden value
        with GoldenValues(golden_file, update_mode=True) as golden:
            golden.check("avg_score", 0.8500)

        print("Golden value: avg_score = 0.8500")
        print()

        # Test relative tolerance
        print("Testing with tolerance=0.01 (1% = [0.8415, 0.8585]):")
        with GoldenValues(golden_file) as golden:
            # These should pass
            golden.check("avg_score", 0.8520, tolerance=0.01)  # +0.24% - OK
            print("  ✓ 0.8520 passed (+0.24%)")

            golden.check("avg_score", 0.8480, tolerance=0.01)  # -0.24% - OK
            print("  ✓ 0.8480 passed (-0.24%)")

        print()

        # Test absolute tolerance
        print("Testing with absolute_tolerance=0.01 (±0.01):")
        with GoldenValues(golden_file) as golden:
            golden.check("avg_score", 0.8550, absolute_tolerance=0.01)  # +0.005 - OK
            print("  ✓ 0.8550 passed (Δ +0.005)")

            golden.check("avg_score", 0.8450, absolute_tolerance=0.01)  # -0.005 - OK
            print("  ✓ 0.8450 passed (Δ -0.005)")

        print()

    finally:
        golden_file.unlink(missing_ok=True)


def example_pipeline_integration():
    """Example: Integration with multi-step pipeline."""
    print("=" * 70)
    print("EXAMPLE 3: Multi-Step Pipeline Integration")
    print("=" * 70)
    print()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        golden_file = Path(f.name)

    try:
        print("Running pipeline in update mode (first run)...")
        with GoldenValues(golden_file, update_mode=True) as golden:
            # Step 1
            print("  Step 1: Downloading papers...")
            results_1 = simulate_pipeline_step_1()
            golden.check("papers_downloaded", results_1["papers_downloaded"])
            golden.check("papers_with_doi", results_1["papers_with_doi"])

            # Step 2
            print("  Step 2: Detecting diagrams...")
            results_2 = simulate_pipeline_step_2()
            golden.check("diagrams_detected", results_2["diagrams_detected"])
            golden.check("avg_diagrams_per_paper", results_2["avg_diagrams_per_paper"], tolerance=0.02)

        print("✓ Pipeline complete, golden values saved")
        print()

        print("Running pipeline in validation mode (second run)...")
        with GoldenValues(golden_file) as golden:
            # Step 1
            print("  Step 1: Downloading papers...")
            results_1 = simulate_pipeline_step_1()
            golden.check("papers_downloaded", results_1["papers_downloaded"])
            golden.check("papers_with_doi", results_1["papers_with_doi"])

            # Step 2
            print("  Step 2: Detecting diagrams...")
            results_2 = simulate_pipeline_step_2()
            golden.check("diagrams_detected", results_2["diagrams_detected"])
            golden.check("avg_diagrams_per_paper", results_2["avg_diagrams_per_paper"], tolerance=0.02)

        print("✓ All checks passed!")
        print()

        # Show summary
        golden = GoldenValues(golden_file)
        print(golden.summary())

    finally:
        golden_file.unlink(missing_ok=True)


def example_non_strict_mode():
    """Example: Non-strict mode (warnings instead of errors)."""
    print("=" * 70)
    print("EXAMPLE 4: Non-Strict Mode")
    print("=" * 70)
    print()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        golden_file = Path(f.name)

    try:
        # Establish golden value
        with GoldenValues(golden_file, update_mode=True) as golden:
            golden.check("count", 100)

        print("Golden value: count = 100")
        print()

        # Strict mode (default) - raises error
        print("Strict mode (default):")
        try:
            with GoldenValues(golden_file, strict=True) as golden:
                golden.check("count", 200)
        except ValueError:
            print("  ✓ ValueError raised (as expected)")
        print()

        # Non-strict mode - only warning
        print("Non-strict mode:")
        with GoldenValues(golden_file, strict=False) as golden:
            golden.check("count", 200)
            print("  ✓ Continued execution despite mismatch")
        print()

    finally:
        golden_file.unlink(missing_ok=True)


def main():
    """Run all examples."""
    print("\n")
    print("*" * 70)
    print("GOLDEN VALUES - USAGE EXAMPLES")
    print("*" * 70)
    print("\n")

    example_validation_mode()
    print("\n")

    example_tolerance()
    print("\n")

    example_pipeline_integration()
    print("\n")

    example_non_strict_mode()
    print("\n")

    print("*" * 70)
    print("ALL EXAMPLES COMPLETED")
    print("*" * 70)
    print()


if __name__ == "__main__":
    main()
