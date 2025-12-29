"""
Basic usage examples for plotting_utils.
"""

import pandas as pd
import numpy as np
from plotting_utils import setup_style, histogram, bar_plot, hbar_plot, pie_chart, save_plot


def main():
    # Set up style (do this once per notebook/script)
    setup_style()

    # Create sample data
    np.random.seed(42)
    df = pd.DataFrame({
        'category': np.random.choice(['A', 'B', 'C', 'D'], 100),
        'values': np.random.randn(100) * 10 + 50,
        'scores': np.random.randint(0, 100, 100)
    })

    # 1. Histogram
    print("Creating histogram...")
    fig, ax = histogram(
        df, 'values',
        bins=20,
        title='Distribution of Values',
        xlabel='Value',
        color='steelblue'
    )
    save_plot(fig, 'histogram_example.png')

    # 2. Bar plot (vertical)
    print("Creating bar plot...")
    counts = df['category'].value_counts()
    fig, ax = bar_plot(
        counts,
        title='Category Counts',
        ylabel='Frequency',
        rotation=0
    )
    save_plot(fig, 'bar_example.png')

    # 3. Horizontal bar plot
    print("Creating horizontal bar plot...")
    fig, ax = hbar_plot(
        counts.sort_values(),  # Sorted looks nice in hbar
        title='Category Counts (Sorted)'
    )
    save_plot(fig, 'hbar_example.png')

    # 4. Pie chart
    print("Creating pie chart...")
    fig, ax = pie_chart(
        counts,
        title='Category Distribution',
        show_percentages=True
    )
    save_plot(fig, 'pie_example.png')

    print("\n✓ All examples created!")
    print("Check the generated PNG files.")


if __name__ == '__main__':
    main()
