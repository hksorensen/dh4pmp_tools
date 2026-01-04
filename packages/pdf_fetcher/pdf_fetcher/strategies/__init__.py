"""Publisher-specific download strategies."""

from pdf_fetcher.strategies.base import DownloadStrategy
from pdf_fetcher.strategies.unpaywall import UnpaywallStrategy
from pdf_fetcher.strategies.elsevier_tdm import ElsevierTDMStrategy
from pdf_fetcher.strategies.elsevier import ElsevierStrategy
from pdf_fetcher.strategies.springer import SpringerStrategy
from pdf_fetcher.strategies.ams import AMSStrategy
from pdf_fetcher.strategies.mdpi import MDPIStrategy
from pdf_fetcher.strategies.generic import GenericStrategy

__all__ = [
    'DownloadStrategy',
    'UnpaywallStrategy',
    'ElsevierTDMStrategy',
    'ElsevierStrategy',
    'SpringerStrategy',
    'AMSStrategy',
    'MDPIStrategy',
    'GenericStrategy',
]

__version__ = '0.1.0'
