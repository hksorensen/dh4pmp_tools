from setuptools import setup, find_packages
import os

setup(
    name='latex_utils',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        # pdflatex/texlive is external, installed via brew
    ],
    python_requires='>=3.8',
    author='Henrik Kragh Sorensen',
    description='Utilities for working with LaTeX',
    long_description=open('README.md').read() if os.path.exists('README.md') else '',
    long_description_content_type='text/markdown',
)
