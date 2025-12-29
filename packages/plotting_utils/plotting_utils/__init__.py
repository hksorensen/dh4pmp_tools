"""
Plotting utilities with consistent styling.

Usage:
    from plotting_utils import setup_style, histogram, bar_plot, pie_chart

    # Set up style once
    setup_style()

    # Create plots
    fig, ax = histogram(df, 'values', title='My Data')
    fig, ax = bar_plot(counts, title='Categories')
"""

from .style import setup_style, reset_style, get_color_palette, show_palettes
from .plots import histogram, pie_chart, bar_plot, hbar_plot, save_plot

__version__ = "0.1.0"
__author__ = "Henrik Kragh Sørensen"

__all__ = [
    # Style functions
    "setup_style",
    "reset_style",
    "get_color_palette",
    "show_palettes",
    # Plot functions
    "histogram",
    "pie_chart",
    "bar_plot",
    "hbar_plot",
    "save_plot",
]
