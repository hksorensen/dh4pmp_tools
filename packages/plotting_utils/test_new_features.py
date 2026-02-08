"""
Test script for new stacked bars and overlapping histograms features.

Tests:
1. Backward compatibility - existing usage patterns must work
2. New multi-column features - stacked/grouped bars and overlapping histograms
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
from pathlib import Path

# Add the package to path
sys.path.insert(0, str(Path(__file__).parent))

from plotting_utils import histogram, bar_plot, hbar_plot

# Create test data
np.random.seed(42)

# Test data for histograms
df_hist = pd.DataFrame({
    'group_a': np.random.normal(100, 15, 200),
    'group_b': np.random.normal(110, 12, 200),
    'group_c': np.random.normal(105, 18, 200),
})

# Test data for bar plots
df_bars = pd.DataFrame({
    'category': ['A', 'B', 'C', 'D', 'E'],
    'val1': [23, 45, 56, 78, 34],
    'val2': [34, 67, 45, 23, 56],
    'val3': [12, 34, 45, 56, 23],
})

series_data = pd.Series([10, 20, 30, 40, 50], index=['Cat1', 'Cat2', 'Cat3', 'Cat4', 'Cat5'])

print("=" * 80)
print("BACKWARD COMPATIBILITY TESTS")
print("=" * 80)

# Test 1: Series histogram (backward compatibility)
print("\n1. Testing histogram with Series (backward compatibility)...")
try:
    fig, ax = histogram(series_data, title='Series Histogram Test')
    plt.close(fig)
    print("   ✓ Series histogram works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 2: DataFrame single column histogram (backward compatibility)
print("\n2. Testing histogram with single DataFrame column (backward compatibility)...")
try:
    fig, ax = histogram(df_hist, 'group_a', bins=30, title='Single Column Histogram')
    plt.close(fig)
    print("   ✓ Single column histogram works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 3: Series bar plot (backward compatibility)
print("\n3. Testing bar_plot with Series (backward compatibility)...")
try:
    fig, ax = bar_plot(series_data, title='Series Bar Plot Test')
    plt.close(fig)
    print("   ✓ Series bar plot works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 4: DataFrame single column bar plot (backward compatibility)
print("\n4. Testing bar_plot with single DataFrame column (backward compatibility)...")
try:
    fig, ax = bar_plot(df_bars, x='category', y='val1', title='Single Column Bar Plot')
    plt.close(fig)
    print("   ✓ Single column bar plot works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 5: Series horizontal bar plot (backward compatibility)
print("\n5. Testing hbar_plot with Series (backward compatibility)...")
try:
    fig, ax = hbar_plot(series_data, title='Series Horizontal Bar Plot Test')
    plt.close(fig)
    print("   ✓ Series horizontal bar plot works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 6: DataFrame single column horizontal bar plot (backward compatibility)
print("\n6. Testing hbar_plot with single DataFrame column (backward compatibility)...")
try:
    fig, ax = hbar_plot(df_bars, x='val1', y='category', title='Single Column HBar Plot')
    plt.close(fig)
    print("   ✓ Single column horizontal bar plot works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

print("\n" + "=" * 80)
print("NEW MULTI-COLUMN FEATURES TESTS")
print("=" * 80)

# Test 7: Overlapping histograms (2 columns)
print("\n7. Testing overlapping histograms with 2 columns...")
try:
    fig, ax = histogram(
        df_hist,
        column=['group_a', 'group_b'],
        bins=25,
        title='Overlapping Histograms (2 groups)',
        alpha=0.6
    )
    plt.close(fig)
    print("   ✓ Overlapping histograms (2 columns) works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 8: Overlapping histograms (3 columns)
print("\n8. Testing overlapping histograms with 3 columns...")
try:
    fig, ax = histogram(
        df_hist,
        column=['group_a', 'group_b', 'group_c'],
        bins=30,
        title='Overlapping Histograms (3 groups)',
        alpha=0.5
    )
    plt.close(fig)
    print("   ✓ Overlapping histograms (3 columns) works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 9: Overlapping histograms with custom labels
print("\n9. Testing overlapping histograms with custom labels...")
try:
    fig, ax = histogram(
        df_hist,
        column=['group_a', 'group_b'],
        labels=['Group Alpha', 'Group Beta'],
        bins=20,
        title='Custom Labels Test'
    )
    plt.close(fig)
    print("   ✓ Overlapping histograms with custom labels works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 10: Overlapping histograms with custom colors
print("\n10. Testing overlapping histograms with custom colors...")
try:
    fig, ax = histogram(
        df_hist,
        column=['group_a', 'group_b'],
        color=['steelblue', 'coral'],
        alpha=0.7,
        bins=25,
        title='Custom Colors Test'
    )
    plt.close(fig)
    print("   ✓ Overlapping histograms with custom colors works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 11: Overlapping histograms with legend disabled
print("\n11. Testing overlapping histograms with legend=False...")
try:
    fig, ax = histogram(
        df_hist,
        column=['group_a', 'group_b'],
        legend=False,
        bins=25,
        title='No Legend Test'
    )
    plt.close(fig)
    print("   ✓ Overlapping histograms with legend=False works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 12: Stacked bars
print("\n12. Testing stacked bar plot...")
try:
    fig, ax = bar_plot(
        df_bars,
        x='category',
        y=['val1', 'val2', 'val3'],
        stacked=True,
        title='Stacked Bar Chart'
    )
    plt.close(fig)
    print("   ✓ Stacked bar plot works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 13: Grouped bars (side-by-side)
print("\n13. Testing grouped bar plot...")
try:
    fig, ax = bar_plot(
        df_bars,
        x='category',
        y=['val1', 'val2'],
        stacked=False,
        title='Grouped Bar Chart'
    )
    plt.close(fig)
    print("   ✓ Grouped bar plot works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 14: Stacked bars with legend disabled
print("\n14. Testing stacked bars with legend=False...")
try:
    fig, ax = bar_plot(
        df_bars,
        x='category',
        y=['val1', 'val2'],
        stacked=True,
        legend=False,
        title='Stacked Bars (No Legend)'
    )
    plt.close(fig)
    print("   ✓ Stacked bars with legend=False works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 15: Stacked horizontal bars
print("\n15. Testing stacked horizontal bar plot...")
try:
    fig, ax = hbar_plot(
        df_bars,
        x=['val1', 'val2', 'val3'],
        y='category',
        stacked=True,
        title='Stacked Horizontal Bars'
    )
    plt.close(fig)
    print("   ✓ Stacked horizontal bar plot works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# Test 16: Grouped horizontal bars
print("\n16. Testing grouped horizontal bar plot...")
try:
    fig, ax = hbar_plot(
        df_bars,
        x=['val1', 'val2'],
        y='category',
        stacked=False,
        title='Grouped Horizontal Bars'
    )
    plt.close(fig)
    print("   ✓ Grouped horizontal bar plot works")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

print("\n" + "=" * 80)
print("EDGE CASE TESTS")
print("=" * 80)

# Test 17: Empty list validation
print("\n17. Testing empty list validation for bar_plot...")
try:
    fig, ax = bar_plot(df_bars, x='category', y=[], title='Empty List Test')
    plt.close(fig)
    print("   ✗ FAILED: Should have raised ValueError for empty list")
except ValueError as e:
    print(f"   ✓ Empty list validation works: {e}")
except Exception as e:
    print(f"   ✗ FAILED with unexpected error: {e}")

# Test 18: Empty list validation for histogram
print("\n18. Testing empty list validation for histogram...")
try:
    fig, ax = histogram(df_hist, column=[], bins=25)
    plt.close(fig)
    print("   ✗ FAILED: Should have raised ValueError for empty list")
except ValueError as e:
    print(f"   ✓ Empty list validation works: {e}")
except Exception as e:
    print(f"   ✗ FAILED with unexpected error: {e}")

# Test 19: List column with Series (should error)
print("\n19. Testing list column with Series (should error)...")
try:
    fig, ax = histogram(series_data, column=['a', 'b'])
    plt.close(fig)
    print("   ✗ FAILED: Should have raised error for Series with list column")
except ValueError as e:
    print(f"   ✓ Series with list validation works: {e}")
except Exception as e:
    print(f"   ✗ FAILED with unexpected error: {e}")

print("\n" + "=" * 80)
print("VISUAL EXAMPLES (saved to /tmp/)")
print("=" * 80)

# Create visual examples
output_dir = Path('/tmp')

# Example 1: Overlapping histograms
print("\n20. Creating visual example: overlapping histograms...")
fig, ax = histogram(
    df_hist,
    column=['group_a', 'group_b', 'group_c'],
    labels=['Group A (μ=100)', 'Group B (μ=110)', 'Group C (μ=105)'],
    bins=30,
    alpha=0.6,
    title='Distribution Comparison',
    xlabel='Score',
    figsize=(12, 6)
)
fig.savefig(output_dir / 'example_overlapping_histograms.png', dpi=150, bbox_inches='tight')
plt.close(fig)
print(f"   ✓ Saved to {output_dir / 'example_overlapping_histograms.png'}")

# Example 2: Stacked bars
print("\n21. Creating visual example: stacked bars...")
fig, ax = bar_plot(
    df_bars,
    x='category',
    y=['val1', 'val2', 'val3'],
    stacked=True,
    title='Sales by Category (Stacked)',
    ylabel='Total Sales',
    figsize=(10, 6)
)
fig.savefig(output_dir / 'example_stacked_bars.png', dpi=150, bbox_inches='tight')
plt.close(fig)
print(f"   ✓ Saved to {output_dir / 'example_stacked_bars.png'}")

# Example 3: Grouped bars
print("\n22. Creating visual example: grouped bars...")
fig, ax = bar_plot(
    df_bars,
    x='category',
    y=['val1', 'val2'],
    stacked=False,
    title='Sales Comparison (Grouped)',
    ylabel='Sales',
    figsize=(10, 6)
)
fig.savefig(output_dir / 'example_grouped_bars.png', dpi=150, bbox_inches='tight')
plt.close(fig)
print(f"   ✓ Saved to {output_dir / 'example_grouped_bars.png'}")

# Example 4: Stacked horizontal bars
print("\n23. Creating visual example: stacked horizontal bars...")
fig, ax = hbar_plot(
    df_bars,
    x=['val1', 'val2', 'val3'],
    y='category',
    stacked=True,
    title='Category Performance (Stacked)',
    xlabel='Performance Score',
    figsize=(10, 6)
)
fig.savefig(output_dir / 'example_stacked_hbars.png', dpi=150, bbox_inches='tight')
plt.close(fig)
print(f"   ✓ Saved to {output_dir / 'example_stacked_hbars.png'}")

print("\n" + "=" * 80)
print("ALL TESTS COMPLETED!")
print("=" * 80)
print("\nSummary:")
print("- All backward compatibility tests should pass")
print("- All new multi-column features should work")
print("- Edge cases should be properly validated")
print("- Visual examples saved to /tmp/")
print("\nCheck the generated plots in /tmp/ to verify visual styling.")
