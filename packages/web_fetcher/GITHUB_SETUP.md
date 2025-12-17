# GitHub Setup Guide for web_fetcher

## Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `web_fetcher`
3. Description: "Web page fetcher with caching, retry logic, and Selenium support"
4. Choose **Private** or **Public**
5. **Do NOT** initialize with README, .gitignore, or license (we have them)
6. Click "Create repository"

## Step 2: Initialize Local Git Repository

```bash
cd /path/to/web_fetcher_package

# Initialize git
git init

# Add all files
git add .

# Create first commit
git commit -m "Initial commit: web_fetcher package v0.1.0"
```

## Step 3: Push to GitHub

```bash
# Add remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/web_fetcher.git

# Rename branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

## Step 4: Install in Development Mode

### Option A: From GitHub (after pushing)

```bash
# Activate your environment
conda activate sciec

# Install directly from GitHub
pip install git+https://github.com/YOUR_USERNAME/web_fetcher.git

# Or with Selenium support
pip install "git+https://github.com/YOUR_USERNAME/web_fetcher.git#egg=web-fetcher[selenium]"
```

### Option B: Clone and Install Locally

```bash
# Clone the repository
cd ~/Documents/codebase/
git clone https://github.com/YOUR_USERNAME/web_fetcher.git

# Install in development mode
conda activate sciec
pip install -e web_fetcher/

# Or with Selenium support
pip install -e "web_fetcher/[selenium]"
```

## Step 5: Add to sciec Requirements

In your sciec project's `requirements.txt`:

```
# requirements.txt
api-clients @ git+https://github.com/hksorensen/api_clients.git
web-fetcher @ git+https://github.com/YOUR_USERNAME/web_fetcher.git
```

Or if using local development installs:

```bash
cd ~/Documents/codebase/api_clients
pip install -e .

cd ~/Documents/codebase/web_fetcher
pip install -e .
```

## Usage in sciec

```python
from web_fetcher import WebPageFetcher
from api_clients import ScopusClient, CrossrefClient

# Use both together
scopus = ScopusClient(api_key="your_key")
web_fetcher = WebPageFetcher(cache_dir="./cache/web")

# Get metadata from API
paper = scopus.get_abstract("SCOPUS_ID:12345")

# Fetch full text from publisher
if 'link' in paper:
    webpage = web_fetcher.fetch(paper['link'])
```

## Future Updates

When you make changes:

```bash
cd ~/Documents/codebase/web_fetcher

# Make your changes...

# Commit and push
git add .
git commit -m "Description of changes"
git push origin main

# If using GitHub install, reinstall to get updates
pip install --upgrade --force-reinstall git+https://github.com/YOUR_USERNAME/web_fetcher.git

# If using local editable install, changes are immediate (no reinstall needed)
```

## Package Structure

```
web_fetcher/
├── README.md                    # Documentation
├── LICENSE                      # MIT License
├── .gitignore                   # Git ignore rules
├── setup.py                     # Package configuration
├── requirements.txt             # Dependencies
├── web_fetcher/                 # Package code
│   ├── __init__.py             # Package exports
│   ├── core.py                 # WebPageFetcher
│   ├── selenium_fetcher.py     # SeleniumWebFetcher
│   └── py.typed                # Type hints marker
├── tests/                       # Unit tests
│   ├── __init__.py
│   ├── test_core.py
│   └── test_selenium.py
└── examples/                    # Usage examples
    ├── basic_usage.py
    └── selenium_usage.py
```

## Tips

1. **Keep it separate**: Don't include this in sciec uploads to Claude
2. **Version control**: Increment version in `setup.py` for releases
3. **Testing**: Add tests in `tests/` directory
4. **Documentation**: Keep README.md updated with changes
5. **Dependencies**: Keep requirements minimal in `setup.py`
