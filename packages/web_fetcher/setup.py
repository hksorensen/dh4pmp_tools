"""
Setup configuration for web_fetcher package.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="web_fetcher",
    version="0.1.0",
    author="Henrik Sørensen",
    author_email="your.email@example.com",  # Update this
    description="Web page fetcher with caching, retry logic, and Selenium support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hksorensen/web_fetcher",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.31.0",
        "urllib3>=2.0.0",
    ],
    extras_require={
        "selenium": [
            "selenium>=4.15.0",
        ],
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.1.0",
            "mypy>=1.5.0",
        ],
    },
    package_data={
        "web_fetcher": ["py.typed"],
    },
    include_package_data=True,
    zip_safe=False,
)
