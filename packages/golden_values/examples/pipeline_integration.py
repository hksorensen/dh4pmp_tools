#!/usr/bin/env python3
"""
Example: Integration with diagrams_in_arxiv pipeline.

This shows how to integrate GoldenValues into your actual pipeline.
"""

from pathlib import Path
from golden_values import GoldenValues


def example_pipeline_step_integration():
    """
    Example showing how to integrate with pipeline steps.

    This pattern matches your diagrams_in_arxiv pipeline structure.
    """

    # Simulated config
    class Config:
        class paths:
            data_dir = Path("/tmp/pipeline_data")

    config = Config()
    config.paths.data_dir.mkdir(exist_ok=True)

    # Golden values file location
    golden_file = config.paths.data_dir / "golden_values.yaml"

    print("=" * 70)
    print("PIPELINE INTEGRATION EXAMPLE")
    print("=" * 70)
    print()

    # ========================================================================
    # OPTION 1: Manual management (if you want fine control)
    # ========================================================================
    print("Option 1: Manual management")
    print("-" * 70)

    def run_pipeline_manual(config, update_golden=False):
        """Pipeline with manual golden values management."""
        golden = GoldenValues(
            golden_file=config.paths.data_dir / "golden_values.yaml",
            update_mode=update_golden,
        )

        # Create context to pass between steps
        context = {
            "golden": golden,
            "output_dir": config.paths.data_dir,
        }

        # Run steps
        print("Running fetch_corpus step...")
        fetch_corpus_run(config, context)

        print("Running detect_diagrams step...")
        detect_diagrams_run(config, context)

        print("Running visualize step...")
        visualize_run(config, context)

        # Save golden values
        golden.save()

        return True

    def fetch_corpus_run(config, context):
        """Example pipeline step: fetch_corpus."""
        golden = context["golden"]

        # Simulate fetching
        papers_downloaded = 8523
        papers_with_doi = 8234

        # Check golden values
        golden.check("papers_downloaded", papers_downloaded)
        golden.check("papers_with_doi", papers_with_doi)

        print(f"  ✓ Downloaded {papers_downloaded} papers")
        return True

    def detect_diagrams_run(config, context):
        """Example pipeline step: detect_diagrams."""
        golden = context["golden"]

        # Simulate detection
        diagrams_detected = 12340
        avg_diagrams_per_paper = 1.45

        # Check golden values with tolerance for floats
        golden.check("diagrams_detected", diagrams_detected)
        golden.check("avg_diagrams_per_paper", avg_diagrams_per_paper, tolerance=0.02)

        print(f"  ✓ Detected {diagrams_detected} diagrams")
        return True

    def visualize_run(config, context):
        """Example pipeline step: visualize."""
        golden = context["golden"]

        # Simulate stats
        num_plots = 12

        golden.check("num_plots_created", num_plots)

        print(f"  ✓ Created {num_plots} plots")
        return True

    # First run: establish golden values
    print("\nFirst run (establishing golden values):")
    run_pipeline_manual(config, update_golden=True)

    print("\nSecond run (validation - should pass):")
    run_pipeline_manual(config, update_golden=False)

    print("\n✓ Manual management example complete")
    print()

    # ========================================================================
    # OPTION 2: Context manager (automatic save)
    # ========================================================================
    print("\nOption 2: Context manager (auto-save)")
    print("-" * 70)

    def run_pipeline_context_manager(config, update_golden=False):
        """Pipeline with context manager for auto-save."""
        with GoldenValues(
            golden_file=config.paths.data_dir / "golden_values.yaml",
            update_mode=update_golden,
        ) as golden:
            context = {"golden": golden}

            # Run steps (same as before)
            print("Running pipeline steps...")
            fetch_corpus_run(config, context)
            detect_diagrams_run(config, context)
            visualize_run(config, context)

            # Automatically saves on exit

        return True

    print("\nRun with context manager:")
    run_pipeline_context_manager(config, update_golden=False)

    print("\n✓ Context manager example complete")
    print()

    # ========================================================================
    # CLI INTEGRATION
    # ========================================================================
    print("\nCLI Integration Pattern")
    print("-" * 70)
    print("""
Add to your pipeline.py argparser:

    parser.add_argument(
        "--update-golden",
        action="store_true",
        help="Update golden values instead of validating"
    )

Then in main():

    success = run_pipeline(
        config,
        steps=steps_to_run,
        from_step=from_step,
        update_golden=args.update_golden  # <-- Pass flag
    )

Usage:
    # Normal validation mode
    python pipeline.py --config config.yaml

    # Update mode (after verifying changes)
    python pipeline.py --config config.yaml --update-golden
""")

    # Show golden values file
    print("\nGenerated golden_values.yaml:")
    print("-" * 70)
    with open(golden_file) as f:
        print(f.read())

    # Cleanup
    golden_file.unlink()


if __name__ == "__main__":
    example_pipeline_step_integration()
