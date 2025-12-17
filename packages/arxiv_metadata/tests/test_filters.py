"""Unit tests for filters module."""

import pytest
from arxiv_metadata.filters import (
    Category,
    FilterBuilder,
    normalize_categories,
    normalize_years,
    matches_categories,
)


class TestCategory:
    """Test Category enum."""
    
    def test_category_values(self):
        """Test that categories have correct values."""
        assert Category.MATH.value == "math"
        assert Category.CS.value == "cs"
        assert Category.PHYSICS.value == "physics"
    
    def test_category_matches(self):
        """Test category matching."""
        assert Category.MATH.matches("math.AG")
        assert Category.MATH.matches("math.NT")
        assert not Category.MATH.matches("cs.LG")
        assert not Category.CS.matches("math.AG")
    
    def test_category_prefix_matching(self):
        """Test that categories match their prefixes."""
        assert Category.ASTRO_PH.matches("astro-ph.CO")
        assert Category.ASTRO_PH.matches("astro-ph.GA")


class TestNormalizeFunctions:
    """Test normalization functions."""
    
    def test_normalize_categories_enum(self):
        """Test normalizing Category enum."""
        result = normalize_categories(Category.MATH)
        assert result == ["math"]
    
    def test_normalize_categories_string(self):
        """Test normalizing string category."""
        result = normalize_categories("math.AG")
        assert result == ["math.AG"]
    
    def test_normalize_categories_list(self):
        """Test normalizing list of categories."""
        result = normalize_categories(["math.AG", "math.NT"])
        assert result == ["math.AG", "math.NT"]
    
    def test_normalize_categories_mixed_list(self):
        """Test normalizing mixed list with enums and strings."""
        result = normalize_categories([Category.MATH, "cs.LG"])
        assert result == ["math", "cs.LG"]
    
    def test_normalize_categories_none(self):
        """Test normalizing None."""
        result = normalize_categories(None)
        assert result is None
    
    def test_normalize_years_int(self):
        """Test normalizing single year."""
        result = normalize_years(2024)
        assert result == [2024]
    
    def test_normalize_years_range(self):
        """Test normalizing year range."""
        result = normalize_years(range(2020, 2023))
        assert result == [2020, 2021, 2022]
    
    def test_normalize_years_list(self):
        """Test normalizing year list."""
        result = normalize_years([2020, 2022, 2024])
        assert result == [2020, 2022, 2024]
    
    def test_normalize_years_none(self):
        """Test normalizing None."""
        result = normalize_years(None)
        assert result is None


class TestMatchesCategories:
    """Test category matching function."""
    
    def test_exact_match(self):
        """Test exact category match."""
        paper = {'categories': ['math.AG', 'math.NT']}
        assert matches_categories(paper, ['math.AG'])
    
    def test_prefix_match(self):
        """Test prefix matching."""
        paper = {'categories': ['math.AG', 'cs.LG']}
        assert matches_categories(paper, ['math'])
        assert matches_categories(paper, ['cs'])
    
    def test_no_match(self):
        """Test when categories don't match."""
        paper = {'categories': ['math.AG']}
        assert not matches_categories(paper, ['cs'])
    
    def test_string_categories(self):
        """Test with space-separated string categories."""
        paper = {'categories': 'math.AG math.NT'}
        assert matches_categories(paper, ['math.AG'])


class TestFilterBuilder:
    """Test FilterBuilder class."""
    
    def test_category_filter(self):
        """Test building category filter."""
        builder = FilterBuilder()
        filter_fn = builder.categories(["math.AG"]).build()
        
        paper1 = {'categories': ['math.AG', 'math.NT']}
        paper2 = {'categories': ['cs.LG']}
        
        assert filter_fn(paper1)
        assert not filter_fn(paper2)
    
    def test_year_filter(self):
        """Test building year filter."""
        builder = FilterBuilder()
        filter_fn = builder.years([2023, 2024]).build()
        
        paper1 = {'year': 2023}
        paper2 = {'year': 2022}
        
        assert filter_fn(paper1)
        assert not filter_fn(paper2)
    
    def test_min_authors_filter(self):
        """Test minimum authors filter."""
        builder = FilterBuilder()
        filter_fn = builder.min_authors(2).build()
        
        paper1 = {'authors_parsed': [['Smith'], ['Jones']]}
        paper2 = {'authors_parsed': [['Smith']]}
        
        assert filter_fn(paper1)
        assert not filter_fn(paper2)
    
    def test_max_authors_filter(self):
        """Test maximum authors filter."""
        builder = FilterBuilder()
        filter_fn = builder.max_authors(2).build()
        
        paper1 = {'authors_parsed': [['Smith']]}
        paper2 = {'authors_parsed': [['A'], ['B'], ['C']]}
        
        assert filter_fn(paper1)
        assert not filter_fn(paper2)
    
    def test_has_doi_filter(self):
        """Test DOI filter."""
        builder = FilterBuilder()
        filter_fn = builder.has_doi().build()
        
        paper1 = {'doi': '10.1234/example'}
        paper2 = {'doi': ''}
        paper3 = {'doi': None}
        
        assert filter_fn(paper1)
        assert not filter_fn(paper2)
        assert not filter_fn(paper3)
    
    def test_custom_filter(self):
        """Test custom filter function."""
        builder = FilterBuilder()
        filter_fn = builder.custom(
            lambda p: 'neural' in p.get('title', '').lower()
        ).build()
        
        paper1 = {'title': 'Neural Networks in Topology'}
        paper2 = {'title': 'Algebraic Geometry'}
        
        assert filter_fn(paper1)
        assert not filter_fn(paper2)
    
    def test_combined_filters(self):
        """Test combining multiple filters with AND logic."""
        builder = FilterBuilder()
        filter_fn = (builder
                     .categories(["math"])
                     .years([2023, 2024])
                     .min_authors(2)
                     .build())
        
        paper1 = {
            'categories': ['math.AG'],
            'year': 2023,
            'authors_parsed': [['A'], ['B']]
        }
        
        paper2 = {
            'categories': ['math.AG'],
            'year': 2023,
            'authors_parsed': [['A']]  # Only 1 author - fails filter
        }
        
        paper3 = {
            'categories': ['cs.LG'],  # Wrong category
            'year': 2023,
            'authors_parsed': [['A'], ['B']]
        }
        
        assert filter_fn(paper1)
        assert not filter_fn(paper2)
        assert not filter_fn(paper3)
