# Plotting Utils

High-level plotting utilities with consistent styling - no more looking up matplotlib syntax!

## Installation

```bash
cd ~/Documents/dh4pmp_tools/packages/plotting_utils
pip install -e .
```

## Quick Start

```python
from plotting_utils import setup_style, histogram, bar_plot, pie_chart

# Set up style once at the beginning of your notebook
setup_style()

# Now create plots with simple, consistent syntax
fig, ax = histogram(df, 'column_name', bins=50, title='My Distribution')
fig, ax = bar_plot(counts, title='Category Counts', rotation=45)
fig, ax = pie_chart(value_counts, title='Distribution')
```

## Features

All the things you always have to look up:
- ✓ Axis labels (auto-detected from column names)
- ✓ Titles with consistent formatting
- ✓ Histogram bins and ranges
- ✓ Pie chart labels and percentages
- ✓ Bar plot rotation and styling
- ✓ Consistent colors and fonts
- ✓ Grid and spines handled automatically

## Usage

### Setup Style (Once Per Notebook)

```python
from plotting_utils import setup_style

# Use defaults
setup_style()

# Or customize
setup_style(seaborn_style='white', palette='categorical')

# Available styles: 'whitegrid', 'darkgrid', 'white', 'dark', 'ticks'
# Available palettes: 'default', 'categorical', 'sequential', 'diverging', 'muted'
```

### Histogram

```python
from plotting_utils import histogram

# From Series
fig, ax = histogram(df['values'], bins=30, title='Distribution')

# From DataFrame (specify column)
fig, ax = histogram(df, 'values', bins='auto', title='Distribution')

# Customize
fig, ax = histogram(
    df, 'values',
    bins=50,
    title='My Data',
    xlabel='Score',
    ylabel='Frequency',
    xlim=(0, 100),
    color='steelblue'
)
```

### Pie Chart

```python
from plotting_utils import pie_chart

# From value_counts
counts = df['category'].value_counts()
fig, ax = pie_chart(counts, title='Category Distribution')

# From dict
data = {'A': 30, 'B': 45, 'C': 25}
fig, ax = pie_chart(data, title='Distribution')

# Custom labels
fig, ax = pie_chart(
    counts,
    title='Categories',
    labels=['Type 1', 'Type 2', 'Type 3'],
    show_percentages=True
)
```

### Bar Plot (Vertical)

```python
from plotting_utils import bar_plot

# From Series (e.g., value_counts)
counts = df['category'].value_counts()
fig, ax = bar_plot(counts, title='Counts', rotation=45)

# From DataFrame
fig, ax = bar_plot(
    df, x='category', y='value',
    title='Values by Category',
    xlabel='Category',
    ylabel='Value',
    rotation=90
)
```

### Horizontal Bar Plot

```python
from plotting_utils import hbar_plot

# Great for sorted top-N
top10 = df['category'].value_counts().head(10)
fig, ax = hbar_plot(top10, title='Top 10 Categories')

# From DataFrame
fig, ax = hbar_plot(df, x='value', y='name', title='Values')
```

### Save Plots

```python
from plotting_utils import save_plot

fig, ax = histogram(df, 'values')
save_plot(fig, 'my_plot.png')  # High quality PNG
save_plot(fig, 'my_plot.pdf')  # Vector PDF
save_plot(fig, 'my_plot.svg')  # Vector SVG
```

## Advanced: Customize via **kwargs

All plot functions pass **kwargs down to the underlying matplotlib/pandas functions:

```python
# Pass any matplotlib hist() arguments
fig, ax = histogram(df, 'values', alpha=0.7, density=True, cumulative=True)

# Pass any pandas plot() arguments
fig, ax = bar_plot(df, x='cat', y='val', width=0.5, log=True)

# Pass any matplotlib pie() arguments
fig, ax = pie_chart(counts, explode=(0, 0.1, 0), shadow=True)
```

## Color Palettes

```python
from plotting_utils import show_palettes, get_color_palette

# View all available palettes
show_palettes()

# Get specific colors
colors = get_color_palette('categorical', n_colors=3)
fig, ax = bar_plot(counts, color=colors[0])
```

## Tips

1. **Call `setup_style()` once** at the beginning of your notebook
2. **Labels auto-detected** from column names and Series names
3. **All functions return `(fig, ax)`** so you can further customize:
   ```python
   fig, ax = histogram(df, 'values')
   ax.axvline(df['values'].mean(), color='red', linestyle='--')
   ```
4. **Use rotation for long labels**:
   ```python
   fig, ax = bar_plot(counts, rotation=45)
   ```

## License

MIT
