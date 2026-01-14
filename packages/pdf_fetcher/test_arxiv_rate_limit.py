#!/usr/bin/env python3
"""
Test ArXiv Rate Limit Batch Pause

This script demonstrates the new ArXiv rate limiting feature:
- When one ArXiv paper hits a rate limit (captcha, HTML response, etc.)
- ALL subsequent ArXiv downloads in the batch are automatically paused
- This prevents hammering ArXiv servers when rate limited

Usage:
    python test_arxiv_rate_limit.py
"""

from pdf_fetcher import PDFFetcher
from pdf_fetcher.strategies.arxiv import ArxivStrategy
from pathlib import Path
import tempfile


def test_rate_limit_simulation():
    """Simulate rate limit detection and verify batch pause behavior."""

    print("=" * 70)
    print("ARXIV RATE LIMIT TEST")
    print("=" * 70)
    print()

    # Create temporary output directory
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Initialize fetcher
        fetcher = PDFFetcher(
            output_dir=output_dir,
            max_workers=2,
            timeout=10,
        )

        # Test identifiers (mix of ArXiv and non-ArXiv)
        test_ids = [
            "2301.12345",  # ArXiv (new format)
            "2301.12346",  # ArXiv
            "10.1007/s00285-023-01234-5",  # Springer (non-ArXiv)
            "2301.12347",  # ArXiv
            "10.1016/j.jmaa.2023.127123",  # Elsevier (non-ArXiv)
            "2301.12348",  # ArXiv
        ]

        print("Test scenario:")
        print("  6 papers: 4 ArXiv, 2 non-ArXiv")
        print("  Manually triggering rate limit after first paper")
        print()

        # Check initial state
        print(f"ArXiv rate limited: {ArxivStrategy.is_rate_limited()}")
        print()

        # Manually trigger rate limit (simulating what happens when rate limit detected)
        print("→ Simulating rate limit detection...")
        ArxivStrategy.set_rate_limited("Test: Manual simulation")
        print(f"ArXiv rate limited: {ArxivStrategy.is_rate_limited()}")
        print()

        # Try to download batch
        print("→ Attempting batch download...")
        print()
        results = fetcher.fetch_batch(test_ids, show_progress=False)

        # Analyze results
        print()
        print("=" * 70)
        print("RESULTS")
        print("=" * 70)

        arxiv_postponed = 0
        non_arxiv_attempted = 0

        for result in results:
            is_arxiv = any(x in result.identifier for x in ["2301", "arxiv"])
            status_icon = "⏸" if result.status == "postponed" else "✗" if result.status == "failure" else "✓"

            print(f"{status_icon} {result.identifier:30s} ({result.status:10s}) - {result.error_reason or ''}")

            if is_arxiv and result.status == "postponed":
                arxiv_postponed += 1
            elif not is_arxiv:
                non_arxiv_attempted += 1

        print()
        print(f"ArXiv papers postponed: {arxiv_postponed}/4")
        print(f"Non-ArXiv papers attempted: {non_arxiv_attempted}/2")
        print()

        # Reset rate limit
        print("→ Resetting rate limit...")
        ArxivStrategy.reset_rate_limit()
        print(f"ArXiv rate limited: {ArxivStrategy.is_rate_limited()}")
        print()

        # Verify expected behavior
        if arxiv_postponed == 4:
            print("✓ TEST PASSED: All ArXiv papers were postponed when rate limited")
        else:
            print(f"✗ TEST FAILED: Expected 4 ArXiv postponed, got {arxiv_postponed}")

        if non_arxiv_attempted == 2:
            print("✓ TEST PASSED: Non-ArXiv papers were still attempted")
        else:
            print(f"✗ TEST FAILED: Expected 2 non-ArXiv attempted, got {non_arxiv_attempted}")

        print()


def test_manual_reset():
    """Test manual reset of rate limit."""

    print("=" * 70)
    print("MANUAL RESET TEST")
    print("=" * 70)
    print()

    # Trigger rate limit
    print("→ Setting rate limit...")
    ArxivStrategy.set_rate_limited("Test")
    print(f"  Rate limited: {ArxivStrategy.is_rate_limited()}")

    # Reset
    print()
    print("→ Resetting rate limit...")
    ArxivStrategy.reset_rate_limit()
    print(f"  Rate limited: {ArxivStrategy.is_rate_limited()}")
    print()

    if not ArxivStrategy.is_rate_limited():
        print("✓ TEST PASSED: Rate limit successfully reset")
    else:
        print("✗ TEST FAILED: Rate limit still active after reset")

    print()


if __name__ == "__main__":
    # Run tests
    test_rate_limit_simulation()
    test_manual_reset()

    print("=" * 70)
    print("USAGE IN PRODUCTION")
    print("=" * 70)
    print()
    print("The rate limit is automatically detected when ArXiv returns:")
    print("  - HTML instead of PDF")
    print("  - Captcha page")
    print("  - 'Too many requests' error")
    print()
    print("To manually reset after waiting:")
    print("  from pdf_fetcher.strategies.arxiv import ArxivStrategy")
    print("  ArxivStrategy.reset_rate_limit()")
    print()
    print("To check status:")
    print("  ArxivStrategy.is_rate_limited()  # Returns True/False")
    print()
