from setuptools import setup, find_packages

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
    long_description=open('README.md').read() if os.path.exists('README.md') else '',
    long_description_content_type='text/markdown',
)
