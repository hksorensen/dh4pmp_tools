"""
High-level plotting functions with consistent styling.

All the things you always have to look up - now in one place!
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from typing import Optional, Tuple, Union, List


def histogram(
    data: Union[pd.Series, pd.DataFrame],
    column: Optional[str] = None,
    bins: Union[int, str] = 30,
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    ylabel: str = "Frequency",
    figsize: Tuple[int, int] = (10, 6),
    color: Optional[str] = None,
    xlim: Optional[Tuple[float, float]] = None,
    ylim: Optional[Tuple[float, float]] = None,
    **kwargs,
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Create a histogram with sensible defaults.

    Args:
        data: DataFrame or Series
        column: Column name if DataFrame (required for DataFrame)
        bins: Number of bins or 'auto', 'sturges', 'fd', 'scott'
        title: Plot title
        xlabel: X-axis label (defaults to column name)
        ylabel: Y-axis label
        figsize: Figure size (width, height)
        color: Bar color (uses default palette if None)
        xlim: X-axis limits (min, max)
        ylim: Y-axis limits (min, max)
        **kwargs: Additional args passed to plt.hist()

    Returns:
        (fig, ax) tuple

    Example:
        >>> fig, ax = histogram(df, 'values', bins=50, title='My Distribution')
        >>> fig, ax = histogram(series, xlabel='Score', ylabel='Count')
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Extract data
    if isinstance(data, pd.DataFrame):
        if column is None:
            raise ValueError("Must specify 'column' when data is DataFrame")
        values = data[column].dropna()
        xlabel = xlabel or column
    else:
        values = data.dropna()
        xlabel = xlabel or (data.name if hasattr(data, "name") else "Value")

    # Plot
    ax.hist(values, bins=bins, color=color, edgecolor="white", linewidth=0.7, **kwargs)

    # Labels
    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold")

    # Use integer ticks if data contains only integers
    if all(values.apply(lambda x: float(x).is_integer())):
        from matplotlib.ticker import MaxNLocator

        ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    # Limits
    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)

    # Style
    ax.grid(True, alpha=0.3)
    sns.despine(ax=ax)
    plt.tight_layout()

    return fig, ax


def pie_chart(
    data: Union[pd.Series, dict],
    title: Optional[str] = None,
    labels: Optional[List[str]] = None,
    colors: Optional[List[str]] = None,
    figsize: Tuple[int, int] = (8, 8),
    show_percentages: bool = True,
    startangle: int = 90,
    legend: bool = False,
    top_n: Optional[int] = None,
    other_threshold: Optional[float] = None,
    other_callback: Optional[callable] = None,
    other_label: str = "Other",
    label_order: Optional[List[str]] = None,
    **kwargs,
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Create a pie chart with nice labels.

    Args:
        data: Series or dict with values (e.g., category counts)
        title: Plot title
        labels: Custom labels (uses data.index or dict.keys if None)
        colors: Custom colors (uses palette if None)
        figsize: Figure size
        show_percentages: If True, show percentages on slices
        startangle: Rotation angle for first slice
        legend: If True, show labels in legend instead of on slices (better for long labels)
        top_n: If set, show only top N items, group rest as "Other"
        other_threshold: If set, group items with value < threshold as "Other"
        other_callback: Custom function (label, value) -> bool to determine if item goes to "Other"
        other_label: Label for grouped items (default: "Other")
        label_order: Custom order for labels (list of label names). Labels not in list are appended at end.
        **kwargs: Additional args passed to plt.pie()

    Returns:
        (fig, ax) tuple

    Examples:
        >>> counts = df['category'].value_counts()
        >>> fig, ax = pie_chart(counts, title='Category Distribution')
        >>> fig, ax = pie_chart(counts, title='Distribution', legend=True)  # For long labels

        >>> # Show only top 5 categories, group rest as "Other"
        >>> fig, ax = pie_chart(counts, title='Top 5 Categories', top_n=5)

        >>> # Custom order for slices
        >>> fig, ax = pie_chart(counts, label_order=['Category A', 'Category C', 'Category B'])

        >>> # Group categories with < 10 items as "Other"
        >>> fig, ax = pie_chart(counts, other_threshold=10)

        >>> # Custom grouping logic
        >>> fig, ax = pie_chart(counts, other_callback=lambda label, value: value < 5 or 'misc' in label.lower())
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Extract data and labels
    if isinstance(data, pd.Series):
        values = data.values
        label_list = labels or data.index.tolist()
    elif isinstance(data, dict):
        label_list = labels or list(data.keys())
        values = list(data.values())
    else:
        values = data
        label_list = labels

    # Reorder data if custom order specified
    if label_order:
        # Convert to lists
        values = list(values)
        label_list = list(label_list)

        # Create dict for easy lookup
        data_dict = dict(zip(label_list, values))

        # Build new ordered lists
        new_labels = []
        new_values = []

        # First, add items in the specified order
        for label in label_order:
            if label in data_dict:
                new_labels.append(label)
                new_values.append(data_dict[label])

        # Then, add any remaining items not in label_order
        for label, value in zip(label_list, values):
            if label not in label_order:
                new_labels.append(label)
                new_values.append(value)

        label_list = new_labels
        values = new_values

    # Group items into "Other" if requested
    if top_n is not None or other_threshold is not None or other_callback is not None:
        # Convert to list for easier manipulation
        values = list(values)
        label_list = list(label_list)

        # Determine which items should be grouped as "Other"
        keep_indices = []
        other_indices = []

        for i, (label, value) in enumerate(zip(label_list, values)):
            should_group = False

            # Check grouping criteria (priority order: callback, top_n, threshold)
            if other_callback is not None:
                should_group = other_callback(label, value)
            elif top_n is not None:
                # For top_n, sort by value and keep only top N
                # We'll handle this differently below
                pass
            elif other_threshold is not None:
                should_group = value < other_threshold

            if should_group:
                other_indices.append(i)
            else:
                keep_indices.append(i)

        # Special handling for top_n: sort by value and take top N
        if top_n is not None and other_callback is None:
            # Create list of (index, value) and sort by value descending
            indexed_values = [(i, values[i]) for i in range(len(values))]
            indexed_values.sort(key=lambda x: x[1], reverse=True)

            keep_indices = [i for i, _ in indexed_values[:top_n]]
            other_indices = [i for i, _ in indexed_values[top_n:]]

        # Create new values and labels with "Other" group
        if other_indices:
            new_values = [values[i] for i in keep_indices]
            new_labels = [label_list[i] for i in keep_indices]

            # Sum up "Other" values
            other_sum = sum(values[i] for i in other_indices)
            new_values.append(other_sum)
            new_labels.append(other_label)

            values = new_values
            label_list = new_labels

    # Plot with or without labels on slices
    autopct = "%1.1f%%" if show_percentages else None

    if legend:
        # Don't show labels on slices, will use legend instead
        # Move percentages closer to edge when no labels
        wedges, texts, autotexts = ax.pie(
            values,
            labels=None,
            colors=colors,
            autopct=autopct,
            pctdistance=0.85,  # Move percentages outward (closer to edge)
            startangle=startangle,
            **kwargs,
        )

        # Add legend below the pie (better for long labels)
        ax.legend(
            wedges,
            label_list,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.02),  # Very close to pie edge
            ncol=min(3, len(label_list)),  # Max 3 columns
            frameon=False,
        )
    else:
        # Show labels on slices
        wedges, texts, autotexts = ax.pie(
            values,
            labels=label_list,
            colors=colors,
            autopct=autopct,
            startangle=startangle,
            **kwargs,
        )

    # Style percentage text
    if show_percentages and autotexts:
        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontweight("bold")
            autotext.set_fontsize(10)

    ax.axis("equal")

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=10)

    plt.tight_layout(pad=0.5)

    return fig, ax


def bar_plot(
    data: Union[pd.Series, pd.DataFrame],
    x: Optional[str] = None,
    y: Optional[str] = None,
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 6),
    color: Optional[str] = None,
    rotation: int = 0,
    xlim: Optional[Tuple[float, float]] = None,
    ylim: Optional[Tuple[float, float]] = None,
    **kwargs,
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Create a vertical bar plot.

    Args:
        data: Series or DataFrame
        x: Column for x-axis (if DataFrame)
        y: Column for y-axis (if DataFrame)
        title: Plot title
        xlabel: X-axis label (auto-detected if None)
        ylabel: Y-axis label (auto-detected if None)
        figsize: Figure size
        color: Bar color
        rotation: Rotation angle for x-axis labels (e.g., 45, 90)
        xlim: X-axis limits (for numeric x-axis)
        ylim: Y-axis limits
        **kwargs: Additional args passed to pandas plot()

    Returns:
        (fig, ax) tuple

    Examples:
        >>> # From Series
        >>> counts = df['category'].value_counts()
        >>> fig, ax = bar_plot(counts, title='Category Counts', rotation=45)

        >>> # From DataFrame
        >>> fig, ax = bar_plot(df, x='name', y='value', title='Values by Name')
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Plot based on data type
    if isinstance(data, pd.Series):
        data.plot(
            kind="bar", ax=ax, color=color, edgecolor="white", linewidth=0.7, **kwargs
        )
        xlabel = xlabel or data.index.name or "Category"
        ylabel = ylabel or data.name or "Value"

    elif isinstance(data, pd.DataFrame):
        if x and y:
            data.plot(
                x=x,
                y=y,
                kind="bar",
                ax=ax,
                color=color,
                edgecolor="white",
                linewidth=0.7,
                legend=False,
                **kwargs,
            )
            xlabel = xlabel or x
            ylabel = ylabel or y
        else:
            raise ValueError("Must specify both 'x' and 'y' for DataFrame")

    # Labels
    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold")

    # Rotate x-axis labels
    if rotation:
        ax.set_xticklabels(ax.get_xticklabels(), rotation=rotation, ha="right")

    # Limits
    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)

    # Style
    ax.grid(True, alpha=0.3, axis="y")
    sns.despine(ax=ax)
    plt.tight_layout()

    return fig, ax


def hbar_plot(
    data: Union[pd.Series, pd.DataFrame],
    x: Optional[str] = None,
    y: Optional[str] = None,
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 6),
    color: Optional[str] = None,
    xlim: Optional[Tuple[float, float]] = None,
    ylim: Optional[Tuple[float, float]] = None,
    **kwargs,
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Create a horizontal bar plot.

    Args:
        data: Series or DataFrame
        x: Column for x-axis/values (if DataFrame)
        y: Column for y-axis/categories (if DataFrame)
        title: Plot title
        xlabel: X-axis label (auto-detected if None)
        ylabel: Y-axis label (auto-detected if None)
        figsize: Figure size
        color: Bar color
        xlim: X-axis limits
        ylim: Y-axis limits (for numeric y-axis)
        **kwargs: Additional args passed to pandas plot()

    Returns:
        (fig, ax) tuple

    Examples:
        >>> # From Series (useful for sorted value_counts)
        >>> counts = df['category'].value_counts().head(10)
        >>> fig, ax = hbar_plot(counts, title='Top 10 Categories')

        >>> # From DataFrame
        >>> fig, ax = hbar_plot(df, x='value', y='name', title='Values by Name')
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Plot based on data type
    if isinstance(data, pd.Series):
        data.plot(
            kind="barh", ax=ax, color=color, edgecolor="white", linewidth=0.7, **kwargs
        )
        ylabel = ylabel or data.index.name or "Category"
        xlabel = xlabel or data.name or "Value"

    elif isinstance(data, pd.DataFrame):
        if x and y:
            data.plot(
                x=y,
                y=x,
                kind="barh",
                ax=ax,
                color=color,
                edgecolor="white",
                linewidth=0.7,
                legend=False,
                **kwargs,
            )
            ylabel = ylabel or y
            xlabel = xlabel or x
        else:
            raise ValueError(
                "Must specify both 'x' (values) and 'y' (categories) for DataFrame"
            )

    # Labels
    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold")

    # Limits
    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)

    # Style
    ax.grid(True, alpha=0.3, axis="x")
    sns.despine(ax=ax)
    plt.tight_layout()

    return fig, ax


def save_plot(fig: plt.Figure, filepath: str, dpi: int = 300, **kwargs):
    """
    Save plot with high quality.

    Args:
        fig: Figure to save
        filepath: Output path (extension determines format: .png, .pdf, .svg)
        dpi: Resolution for raster formats
        **kwargs: Additional args passed to fig.savefig()

    Example:
        >>> fig, ax = histogram(df, 'values')
        >>> save_plot(fig, 'my_histogram.png')
    """
    fig.savefig(filepath, dpi=dpi, bbox_inches="tight", **kwargs)
    print(f"✓ Saved: {filepath}")
