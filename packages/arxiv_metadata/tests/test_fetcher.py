"""Unit tests for fetcher module."""

import pytest
from pathlib import Path
import json
import tempfile
from arxiv_metadata.fetcher import ArxivMetadata
from arxiv_metadata.filters import Category


class TestArxivMetadata:
    """Test ArxivMetadata class."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def sample_metadata_file(self, temp_cache_dir):
        """Create a sample metadata file for testing."""
        sample_papers = [
            {
                'id': '2301.12345',
                'title': 'Test Paper 1',
                'authors_parsed': [['Smith', 'John', ''], ['Doe', 'Jane', '']],
                'categories': 'math.AG math.NT',
                'abstract': 'This is about algebraic geometry',
                'versions': [{'created': '2023-01-01'}],
                'doi': '10.1234/test1'
            },
            {
                'id': '2302.54321',
                'title': 'Test Paper 2',
                'authors_parsed': [['Jones', 'Bob', '']],
                'categories': 'cs.LG',
                'abstract': 'This is about machine learning',
                'versions': [{'created': '2023-02-01'}],
                'doi': ''
            },
            {
                'id': '2401.11111',
                'title': 'Test Paper 3',
                'authors_parsed': [['White', 'Alice', ''], ['Black', 'Charlie', '']],
                'categories': 'math.CO cs.DM',
                'abstract': 'This is about combinatorics',
                'versions': [{'created': '2024-01-01'}],
                'doi': '10.5678/test3'
            }
        ]
        
        filepath = Path(temp_cache_dir) / 'arxiv_metadata.jsonl'
        with open(filepath, 'w') as f:
            for paper in sample_papers:
                f.write(json.dumps(paper) + '\n')
        
        return filepath
    
    def test_init(self, temp_cache_dir):
        """Test initialization."""
        fetcher = ArxivMetadata(cache_dir=temp_cache_dir)
        assert fetcher.cache_dir == Path(temp_cache_dir)
        assert fetcher.use_cache is True
        assert fetcher.cache_expiry_days == 30
    
    def test_parse_year_from_id_new_format(self):
        """Test year parsing from new format arXiv ID."""
        fetcher = ArxivMetadata()
        assert fetcher._parse_year_from_id('2301.12345') == 2023
        assert fetcher._parse_year_from_id('2012.54321') == 2020
        assert fetcher._parse_year_from_id('1501.98765') == 2015
    
    def test_parse_year_from_id_old_format(self):
        """Test year parsing from old format arXiv ID."""
        fetcher = ArxivMetadata()
        assert fetcher._parse_year_from_id('math/0601001') == 2006
        assert fetcher._parse_year_from_id('hep-th/9901001') == 1999
        assert fetcher._parse_year_from_id('cs/0001001') == 2000
    
    def test_process_paper(self):
        """Test paper processing."""
        fetcher = ArxivMetadata()
        
        paper = {
            'id': '2301.12345',
            'categories': 'math.AG math.NT',
            'versions': [{'v1': 1}, {'v2': 2}],
            'authors_parsed': [['Smith'], ['Jones']]
        }
        
        processed = fetcher._process_paper(paper)
        
        assert processed['arxiv_id'] == '2301.12345'
        assert processed['year'] == 2023
        assert processed['categories'] == ['math.AG', 'math.NT']
        assert processed['primary_category'] == 'math.AG'
        assert processed['num_versions'] == 2
        assert processed['num_authors'] == 2
    
    def test_stream(self, temp_cache_dir, sample_metadata_file, monkeypatch):
        """Test streaming papers."""
        fetcher = ArxivMetadata(cache_dir=temp_cache_dir)
        
        # Mock the metadata path
        monkeypatch.setattr(fetcher, '_get_metadata_path', lambda: sample_metadata_file)
        
        papers = list(fetcher.stream())
        
        assert len(papers) == 3
        assert papers[0]['arxiv_id'] == '2301.12345'
        assert papers[0]['year'] == 2023
        assert papers[0]['num_authors'] == 2
    
    def test_stream_with_category_filter(self, temp_cache_dir, sample_metadata_file, monkeypatch):
        """Test streaming with category filter."""
        fetcher = ArxivMetadata(cache_dir=temp_cache_dir)
        monkeypatch.setattr(fetcher, '_get_metadata_path', lambda: sample_metadata_file)
        
        papers = list(fetcher.stream(categories=Category.MATH))
        
        assert len(papers) == 2  # Two papers have math.* categories
        assert all('math' in p['primary_category'] for p in papers)
    
    def test_stream_with_year_filter(self, temp_cache_dir, sample_metadata_file, monkeypatch):
        """Test streaming with year filter."""
        fetcher = ArxivMetadata(cache_dir=temp_cache_dir)
        monkeypatch.setattr(fetcher, '_get_metadata_path', lambda: sample_metadata_file)
        
        papers = list(fetcher.stream(years=2024))
        
        assert len(papers) == 1
        assert papers[0]['year'] == 2024
    
    def test_stream_with_author_filter(self, temp_cache_dir, sample_metadata_file, monkeypatch):
        """Test streaming with author count filter."""
        fetcher = ArxivMetadata(cache_dir=temp_cache_dir)
        monkeypatch.setattr(fetcher, '_get_metadata_path', lambda: sample_metadata_file)
        
        papers = list(fetcher.stream(min_authors=2))
        
        assert len(papers) == 2  # Two papers have 2 authors
        assert all(p['num_authors'] >= 2 for p in papers)
    
    def test_stream_with_doi_filter(self, temp_cache_dir, sample_metadata_file, monkeypatch):
        """Test streaming with DOI filter."""
        fetcher = ArxivMetadata(cache_dir=temp_cache_dir)
        monkeypatch.setattr(fetcher, '_get_metadata_path', lambda: sample_metadata_file)
        
        papers = list(fetcher.stream(has_doi=True))
        
        assert len(papers) == 2  # Two papers have DOIs
        assert all(p.get('doi', '').strip() for p in papers)
    
    def test_stream_with_custom_filter(self, temp_cache_dir, sample_metadata_file, monkeypatch):
        """Test streaming with custom filter."""
        fetcher = ArxivMetadata(cache_dir=temp_cache_dir)
        monkeypatch.setattr(fetcher, '_get_metadata_path', lambda: sample_metadata_file)
        
        papers = list(fetcher.stream(
            filter_fn=lambda p: 'learning' in p['abstract'].lower()
        ))
        
        assert len(papers) == 1
        assert 'learning' in papers[0]['abstract'].lower()
    
    def test_fetch_returns_dataframe(self, temp_cache_dir, sample_metadata_file, monkeypatch):
        """Test that fetch returns a DataFrame."""
        fetcher = ArxivMetadata(cache_dir=temp_cache_dir)
        monkeypatch.setattr(fetcher, '_get_metadata_path', lambda: sample_metadata_file)
        
        df = fetcher.fetch(show_progress=False)
        
        assert len(df) == 3
        assert 'arxiv_id' in df.columns
        assert 'title' in df.columns
        assert 'year' in df.columns
    
    def test_fetch_with_limit(self, temp_cache_dir, sample_metadata_file, monkeypatch):
        """Test fetch with limit."""
        fetcher = ArxivMetadata(cache_dir=temp_cache_dir)
        monkeypatch.setattr(fetcher, '_get_metadata_path', lambda: sample_metadata_file)
        
        df = fetcher.fetch(limit=2, show_progress=False)
        
        assert len(df) == 2
    
    def test_fetch_with_columns(self, temp_cache_dir, sample_metadata_file, monkeypatch):
        """Test fetch with specific columns."""
        fetcher = ArxivMetadata(cache_dir=temp_cache_dir)
        monkeypatch.setattr(fetcher, '_get_metadata_path', lambda: sample_metadata_file)
        
        df = fetcher.fetch(
            columns=['arxiv_id', 'title', 'year'],
            show_progress=False
        )
        
        assert list(df.columns) == ['arxiv_id', 'title', 'year']
    
    def test_combined_filters(self, temp_cache_dir, sample_metadata_file, monkeypatch):
        """Test combining multiple filters."""
        fetcher = ArxivMetadata(cache_dir=temp_cache_dir)
        monkeypatch.setattr(fetcher, '_get_metadata_path', lambda: sample_metadata_file)
        
        df = fetcher.fetch(
            categories=Category.MATH,
            years=2024,
            min_authors=2,
            show_progress=False
        )
        
        assert len(df) == 1  # Only one paper matches all criteria
        assert df.iloc[0]['arxiv_id'] == '2401.11111'
