from setuptools import setup, find_packages
from pathlib import Path

readme_file = Path(__file__).parent / 'README.md'
long_description = readme_file.read_text() if readme_file.exists() else ''

setup(
    name='bibtex_utils',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        # pandoc is external, installed via brew
    ],
    python_requires='>=3.8',
    author='Henrik Kragh Sorensen',
    description='Utilities for working with BibTeX entries',
    long_description=long_description,
    long_description_content_type='text/markdown',
)
