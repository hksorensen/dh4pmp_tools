"""Setup script for db_utils package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="db_utils",
    version="0.1.0",
    author="Henrik Kragh Sørensen",
    description="Database utilities for pandas DataFrames with SQLite and MySQL support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "pandas>=1.0.0",
    ],
    extras_require={
        "mysql": [
            "sqlalchemy>=1.4.0",
            "mysql-connector-python>=8.0.0",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
