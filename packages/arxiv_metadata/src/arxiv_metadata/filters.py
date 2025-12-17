"""Filtering utilities and category definitions for arXiv metadata."""

from enum import Enum
from typing import Callable, Any


class Category(str, Enum):
    """Predefined arXiv category filters.
    
    Each enum value represents a category prefix that matches all subcategories.
    For example, Category.MATH matches math.AG, math.NT, math.CO, etc.
    """
    
    # Major categories
    MATH = "math"
    CS = "cs"
    PHYSICS = "physics"
    STAT = "stat"
    EESS = "eess"
    ECON = "econ"
    QUANT_BIO = "q-bio"
    QUANT_FIN = "q-fin"
    
    # Physics subcategories (commonly used)
    ASTRO_PH = "astro-ph"
    COND_MAT = "cond-mat"
    GR_QC = "gr-qc"
    HEP_EX = "hep-ex"
    HEP_LAT = "hep-lat"
    HEP_PH = "hep-ph"
    HEP_TH = "hep-th"
    MATH_PH = "math-ph"
    NUCL_EX = "nucl-ex"
    NUCL_TH = "nucl-th"
    QUANT_PH = "quant-ph"
    
    def matches(self, category: str) -> bool:
        """Check if a category string matches this filter.
        
        Args:
            category: Category string from arXiv paper (e.g., "math.AG")
            
        Returns:
            True if category matches this filter
            
        Examples:
            >>> Category.MATH.matches("math.AG")
            True
            >>> Category.MATH.matches("cs.LG")
            False
        """
        return category.startswith(self.value)


class FilterBuilder:
    """Builder class for creating complex filter functions.
    
    Examples:
        >>> filter_fn = (FilterBuilder()
        ...     .categories(["math.AG", "math.NT"])
        ...     .years([2023, 2024])
        ...     .min_authors(2)
        ...     .has_doi()
        ...     .build())
    """
    
    def __init__(self):
        self._filters = []
    
    def categories(self, cats: list[str] | str | Category):
        """Filter by categories."""
        if isinstance(cats, (str, Category)):
            cats = [cats]
        
        def filter_fn(paper: dict) -> bool:
            paper_cats = paper.get('categories', [])
            if isinstance(paper_cats, str):
                paper_cats = paper_cats.split()
            
            for cat in cats:
                if isinstance(cat, Category):
                    if any(cat.matches(pc) for pc in paper_cats):
                        return True
                else:
                    if cat in paper_cats or any(pc.startswith(cat) for pc in paper_cats):
                        return True
            return False
        
        self._filters.append(filter_fn)
        return self
    
    def years(self, years: int | range | list[int]):
        """Filter by publication years."""
        if isinstance(years, int):
            years = [years]
        elif isinstance(years, range):
            years = list(years)
        
        def filter_fn(paper: dict) -> bool:
            return paper.get('year') in years
        
        self._filters.append(filter_fn)
        return self
    
    def min_authors(self, min_count: int):
        """Filter by minimum number of authors."""
        def filter_fn(paper: dict) -> bool:
            authors = paper.get('authors_parsed', [])
            return len(authors) >= min_count
        
        self._filters.append(filter_fn)
        return self
    
    def max_authors(self, max_count: int):
        """Filter by maximum number of authors."""
        def filter_fn(paper: dict) -> bool:
            authors = paper.get('authors_parsed', [])
            return len(authors) <= max_count
        
        self._filters.append(filter_fn)
        return self
    
    def has_doi(self):
        """Filter for papers with DOI."""
        def filter_fn(paper: dict) -> bool:
            doi = paper.get('doi')
            return doi is not None and doi.strip() != ''
        
        self._filters.append(filter_fn)
        return self
    
    def custom(self, fn: Callable[[dict], bool]):
        """Add a custom filter function."""
        self._filters.append(fn)
        return self
    
    def build(self) -> Callable[[dict], bool]:
        """Build the final filter function that combines all filters with AND logic."""
        def combined_filter(paper: dict) -> bool:
            return all(f(paper) for f in self._filters)
        
        return combined_filter


def normalize_categories(categories: Category | list[str] | str | None) -> list[str] | None:
    """Normalize category input to a list of category strings.
    
    Args:
        categories: Can be a Category enum, string, list of strings, or None
        
    Returns:
        List of category strings or None
    """
    if categories is None:
        return None
    
    if isinstance(categories, Category):
        return [categories.value]
    
    if isinstance(categories, str):
        return [categories]
    
    if isinstance(categories, list):
        return [c.value if isinstance(c, Category) else c for c in categories]
    
    return [categories]


def normalize_years(years: int | range | list[int] | None) -> list[int] | None:
    """Normalize year input to a list of years.
    
    Args:
        years: Can be an int, range, list of ints, or None
        
    Returns:
        List of years or None
    """
    if years is None:
        return None
    
    if isinstance(years, int):
        return [years]
    
    if isinstance(years, range):
        return list(years)
    
    return years


def matches_categories(paper: dict, categories: list[str]) -> bool:
    """Check if paper matches any of the specified categories.
    
    Args:
        paper: Paper metadata dict
        categories: List of category strings or prefixes
        
    Returns:
        True if paper matches any category
    """
    paper_cats = paper.get('categories', [])
    if isinstance(paper_cats, str):
        paper_cats = paper_cats.split()
    
    for cat in categories:
        # Exact match
        if cat in paper_cats:
            return True
        # Prefix match (e.g., "math" matches "math.AG")
        if any(pc.startswith(f"{cat}.") for pc in paper_cats):
            return True
    
    return False
