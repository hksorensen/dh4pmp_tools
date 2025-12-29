"""
Styling configuration for consistent plots.

Call setup_style() once at the beginning of your notebook.
"""

import matplotlib.pyplot as plt
import seaborn as sns


# Default style settings
DEFAULT_STYLE = {
    "figure.figsize": (10, 6),
    "figure.dpi": 100,
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 14,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#333333",
    "grid.color": "#cccccc",
}


# Color palettes
PALETTES = {
    "default": sns.color_palette("husl", 10),
    "categorical": sns.color_palette("Set2", 8),
    "sequential": sns.color_palette("Blues", 9),
    "diverging": sns.color_palette("RdBu", 11),
    "muted": sns.color_palette("muted", 10),
}


def setup_style(
    seaborn_style: str = "whitegrid",
    palette: str = "default",
    custom_rc: dict = None
):
    """
    Apply consistent styling to all plots.

    Call this ONCE at the beginning of your notebook:
        >>> from plotting_utils import setup_style
        >>> setup_style()

    Args:
        seaborn_style: Seaborn style preset
            Options: 'whitegrid', 'darkgrid', 'white', 'dark', 'ticks'
        palette: Color palette to use
            Options: 'default', 'categorical', 'sequential', 'diverging', 'muted'
        custom_rc: Additional matplotlib rcParams to override

    Example:
        >>> setup_style('white', 'categorical')
    """
    # Set seaborn style
    sns.set_style(seaborn_style)

    # Set color palette
    if palette in PALETTES:
        sns.set_palette(PALETTES[palette])
    else:
        raise ValueError(f"Unknown palette: {palette}. Choose from: {list(PALETTES.keys())}")

    # Apply default matplotlib settings
    plt.rcParams.update(DEFAULT_STYLE)

    # Apply custom overrides
    if custom_rc:
        plt.rcParams.update(custom_rc)

    print(f"✓ Style configured: {seaborn_style} + {palette} palette")


def reset_style():
    """Reset to matplotlib defaults."""
    plt.rcdefaults()
    sns.reset_defaults()
    print("✓ Style reset to defaults")


def get_color_palette(palette: str = "default", n_colors: int = None):
    """
    Get a color palette.

    Args:
        palette: Palette name
        n_colors: Number of colors to return (None = all)

    Returns:
        List of RGB tuples

    Example:
        >>> colors = get_color_palette('categorical', 5)
        >>> plt.bar(x, y, color=colors[0])
    """
    if palette not in PALETTES:
        raise ValueError(f"Unknown palette: {palette}. Choose from: {list(PALETTES.keys())}")

    pal = PALETTES[palette]
    if n_colors:
        return pal[:n_colors]
    return pal


def show_palettes():
    """Display all available color palettes."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(len(PALETTES), 1, figsize=(10, len(PALETTES) * 0.8))

    for ax, (name, palette) in zip(axes, PALETTES.items()):
        ax.imshow([palette], aspect='auto')
        ax.set_ylabel(name, rotation=0, ha='right', va='center', fontsize=11)
        ax.set_xticks([])
        ax.set_yticks([])

    plt.suptitle('Available Color Palettes', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.show()
