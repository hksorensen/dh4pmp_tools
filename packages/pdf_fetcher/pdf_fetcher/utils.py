"""Utility functions for PDF fetcher."""

# DOI prefix to publisher mapping
DOI_PREFIX_TO_PUBLISHER = {
    "10.1007": "Springer",
    "10.1016": "Elsevier",
    "10.1109": "IEEE",
    "10.1090": "AMS",
    "10.1137": "SIAM",
    "10.1080": "Taylor & Francis",
    "10.1093": "Oxford University Press",
    "10.1017": "Cambridge University Press",
    "10.3390": "MDPI",
    "10.1088": "IOP Publishing",
    "10.1038": "Nature Publishing Group",
    "10.1126": "Science/AAAS",
    "10.1145": "ACM",
    "10.1002": "Wiley",
    "10.1215": "Duke University Press",
    "10.4171": "EMS Press",
    "10.1201": "CRC Press",
    "10.1112": "London Mathematical Society",
    "10.2307": "JSTOR",
    "10.4213": "Russian Academy of Sciences",
    "10.1134": "Pleiades Publishing",
    "10.3842": "Institute of Mathematics of NAS of Ukraine",
}


def get_doi_prefix(doi: str) -> str:
    """
    Extract DOI prefix from DOI.

    Args:
        doi: DOI string (e.g., '10.1007/s10623-024-01403-z')

    Returns:
        DOI prefix (e.g., '10.1007')

    Examples:
        >>> get_doi_prefix('10.1007/s10623-024-01403-z')
        '10.1007'

        >>> get_doi_prefix('10.1093/imrn/rnaf173')
        '10.1093'
    """
    # DOI prefix is everything before the first slash
    parts = doi.split('/')
    if len(parts) >= 1:
        return parts[0]
    return doi


def get_publisher(doi: str) -> str:
    """
    Get publisher name from DOI.

    Args:
        doi: DOI string (e.g., '10.1007/s10623-024-01403-z')

    Returns:
        Publisher name or 'Unknown' if not in mapping

    Examples:
        >>> get_publisher('10.1007/s10623-024-01403-z')
        'Springer'

        >>> get_publisher('10.1093/imrn/rnaf173')
        'Oxford University Press'

        >>> get_publisher('10.9999/unknown')
        'Unknown'

    Usage in pandas:
        >>> import pandas as pd
        >>> from pdf_fetcher.utils import get_publisher
        >>> df['publisher'] = df['doi'].apply(get_publisher)
    """
    prefix = get_doi_prefix(doi)
    return DOI_PREFIX_TO_PUBLISHER.get(prefix, "Unknown")


def sanitize_doi_to_filename(identifier: str) -> str:
    """
    Convert DOI or identifier to safe filename.

    Args:
        identifier: DOI or other identifier (e.g., '10.1234/abcd.5678')

    Returns:
        Safe filename with .pdf extension (e.g., '10.1234_abcd.5678.pdf')

    Examples:
        >>> sanitize_doi_to_filename('10.1007/s10623-024-01403-z')
        '10.1007_s10623-024-01403-z.pdf'

        >>> sanitize_doi_to_filename('10.1234/abc:def/xyz')
        '10.1234_abc_def_xyz.pdf'
    """
    # Replace / and : with _
    safe = identifier.replace('/', '_').replace(':', '_')

    # Remove other problematic characters (keep only alphanumeric, ., _, -)
    safe = ''.join(c for c in safe if c.isalnum() or c in '._-')

    return f"{safe}.pdf"
