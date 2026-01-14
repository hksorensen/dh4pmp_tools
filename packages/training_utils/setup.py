from setuptools import setup, find_packages
from pathlib import Path

readme_file = Path(__file__).parent / 'README.md'
long_description = readme_file.read_text() if readme_file.exists() else ''

setup(
    name='training_utils',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'PyYAML>=5.0',
    ],
    python_requires='>=3.8',
    author='Henrik Kragh Sorensen',
    description='Training utilities for diagram detection',
    long_description=long_description,
    long_description_content_type='text/markdown',
)
