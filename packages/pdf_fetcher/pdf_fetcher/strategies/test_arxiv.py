#!/usr/bin/env python3
"""
Test ArXiv strategy with various identifier formats.

Run this to verify ArXiv strategy works correctly.
"""

from arxiv import ArxivStrategy


def test_can_handle():
    """Test that ArXiv strategy recognizes various identifier formats."""
    strategy = ArxivStrategy()

    test_cases = [
        # (identifier, should_handle, description)
        ("2301.12345", True, "New format ArXiv ID"),
        ("2301.12345v1", True, "New format with version"),
        ("math.GT/0309136", True, "Old format ArXiv ID"),
        ("arxiv:2301.12345", True, "Prefixed ArXiv ID"),
        ("arXiv:2301.12345", True, "Prefixed (capital X)"),
        ("10.48550/arXiv.2301.12345", True, "ArXiv DOI"),
        ("https://doi.org/10.48550/arXiv.2301.12345", True, "ArXiv DOI URL"),
        ("https://arxiv.org/abs/2301.12345", True, "ArXiv abstract URL"),
        ("https://arxiv.org/pdf/2301.12345.pdf", True, "ArXiv PDF URL"),
        ("10.1007/s00222-023-01234-5", False, "Non-ArXiv DOI"),
        ("https://springer.com/article/123", False, "Non-ArXiv URL"),
    ]

    print("Testing can_handle()...")
    print("=" * 80)

    passed = 0
    failed = 0

    for identifier, expected, description in test_cases:
        result = strategy.can_handle(identifier)
        status = "✓" if result == expected else "✗"

        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} {description:40s} | {identifier:45s} → {result}")

    print("=" * 80)
    print(f"Passed: {passed}/{len(test_cases)}")
    if failed > 0:
        print(f"Failed: {failed}/{len(test_cases)}")
        return False
    return True


def test_extract_arxiv_id():
    """Test ArXiv ID extraction from various formats."""
    strategy = ArxivStrategy()

    test_cases = [
        # (input, expected_output, description)
        ("2301.12345", "2301.12345", "Direct ArXiv ID"),
        ("2301.12345v1", "2301.12345v1", "With version"),
        ("arxiv:2301.12345", "2301.12345", "Prefixed"),
        ("arXiv:2301.12345v2", "2301.12345v2", "Prefixed with version"),
        ("10.48550/arXiv.2301.12345", "2301.12345", "From DOI"),
        ("10.48550/arXiv.2301.12345v1", "2301.12345v1", "From DOI with version"),
        ("https://arxiv.org/abs/2301.12345", "2301.12345", "From abstract URL"),
        ("https://arxiv.org/pdf/2301.12345v1.pdf", "2301.12345v1", "From PDF URL"),
        ("math.GT/0309136", "math.GT/0309136", "Old format"),
        ("https://doi.org/10.48550/arXiv.2301.12345", "2301.12345", "From doi.org URL"),
    ]

    print("\nTesting extract_arxiv_id()...")
    print("=" * 80)

    passed = 0
    failed = 0

    for input_id, expected, description in test_cases:
        result = strategy.extract_arxiv_id(input_id)
        status = "✓" if result == expected else "✗"

        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} {description:40s} | {input_id:45s} → {result}")
        if result != expected:
            print(f"   Expected: {expected}")

    print("=" * 80)
    print(f"Passed: {passed}/{len(test_cases)}")
    if failed > 0:
        print(f"Failed: {failed}/{len(test_cases)}")
        return False
    return True


def test_get_pdf_url():
    """Test PDF URL generation."""
    strategy = ArxivStrategy()

    test_cases = [
        # (identifier, expected_url, description)
        ("2301.12345", "https://arxiv.org/pdf/2301.12345.pdf", "Basic ID"),
        ("2301.12345v1", "https://arxiv.org/pdf/2301.12345v1.pdf", "With version"),
        ("arxiv:2301.12345", "https://arxiv.org/pdf/2301.12345.pdf", "Prefixed"),
        ("10.48550/arXiv.2301.12345", "https://arxiv.org/pdf/2301.12345.pdf", "From DOI"),
        ("math.GT/0309136", "https://arxiv.org/pdf/math.GT/0309136.pdf", "Old format"),
    ]

    print("\nTesting get_pdf_url()...")
    print("=" * 80)

    passed = 0
    failed = 0

    for identifier, expected, description in test_cases:
        result = strategy.get_pdf_url(identifier, landing_url="", html_content="")
        status = "✓" if result == expected else "✗"

        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} {description:40s}")
        print(f"   Input:    {identifier}")
        print(f"   Expected: {expected}")
        print(f"   Got:      {result}")

    print("=" * 80)
    print(f"Passed: {passed}/{len(test_cases)}")
    if failed > 0:
        print(f"Failed: {failed}/{len(test_cases)}")
        return False
    return True


if __name__ == "__main__":
    print("ArXiv Strategy Test Suite")
    print("=" * 80)
    print()

    all_passed = True
    all_passed &= test_can_handle()
    all_passed &= test_extract_arxiv_id()
    all_passed &= test_get_pdf_url()

    print()
    print("=" * 80)
    if all_passed:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
        exit(1)
