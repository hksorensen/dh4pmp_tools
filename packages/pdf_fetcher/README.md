# PDF Fetcher

Automated academic PDF downloader with intelligent publisher-specific strategies and open access discovery.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **🎯 61%+ Success Rate** - Tested on 100 diverse DOIs
- **🔓 Open Access First** - Prioritizes Unpaywall API to find legal OA versions
- **🎨 Publisher-Specific Strategies** - Optimized for Springer, AMS, MDPI, and more
- **🔄 Multi-Strategy Fallback** - Automatically tries multiple approaches
- **💾 Smart Caching** - SQLite database prevents re-downloads
- **⚡ Parallel Downloads** - Configurable worker threads
- **📊 Progress Tracking** - Real-time progress with ETA
- **🛡️ Retry Logic** - Distinguishes temporary vs permanent failures
- **🔐 VPN Checking** - Optional automatic VPN verification for university access

## Quick Start

### Installation

\`\`\`bash
# Clone the repository
git clone https://github.com/yourusername/pdf-fetcher.git
cd pdf-fetcher

# Install the package
pip install -e .
\`\`\`

### Configuration (Optional)

PDF Fetcher works out of the box with sensible defaults, but you can customize settings via `config.yaml`.

**Config file locations** (searched in this order):
1. `./config.yaml` (current directory)
2. `~/.config/pdf_fetcher/config.yaml` (user config)
3. Package default config (fallback)

**To customize settings:**

\`\`\`bash
# Option 1: Copy template to user config directory (recommended)
mkdir -p ~/.config/pdf_fetcher
cp pdf_fetcher/config.yaml ~/.config/pdf_fetcher/config.yaml
# Edit with your settings
nano ~/.config/pdf_fetcher/config.yaml

# Option 2: Copy to current project directory
cp pdf_fetcher/config.yaml ./config.yaml
# Edit with your settings
nano config.yaml
\`\`\`

**Important settings to configure:**

\`\`\`yaml
# Unpaywall API Settings (RECOMMENDED)
unpaywall:
  email: "your.email@university.edu"  # Use your real email!

# Download Settings
max_workers: 4          # Parallel download threads
timeout: 30             # Download timeout in seconds
output_dir: "./pdfs"    # Where to save PDFs
\`\`\`

### Usage

\`\`\`bash
# Download a single PDF
pdf-fetcher 10.1007/s10623-024-01403-z

# Download from a file
pdf-fetcher --input dois.txt --output ./papers

# Show statistics
pdf-fetcher --stats

# Verify all downloaded files still exist
pdf-fetcher --verify

# Show help
pdf-fetcher --help
\`\`\`

### Database Management

PDF Fetcher uses a centralized SQLite database at `~/.pdf_fetcher/metadata.db` to track all downloads across projects. This prevents re-downloading the same PDF multiple times.

**File Verification:** If you delete a PDF file, pdf-fetcher will automatically detect it's missing and re-download it:

\`\`\`bash
# Verify all files exist and update database
pdf-fetcher --verify

# List missing files
pdf-fetcher --list-missing
\`\`\`

**Archive Support:** When moving PDFs to remote storage (SFTP, S3, etc.) to save disk space:

\`\`\`bash
# Mark a file as archived to remote location
pdf-fetcher --mark-archived 10.1007/xxx sftp://server/pdfs/file.pdf

# List all archived files
pdf-fetcher --list-archived
\`\`\`

**Custom Database Location:** Use project-specific database if needed:

\`\`\`bash
# Use custom database location
pdf-fetcher --db ./my_project.db 10.1007/xxx
\`\`\`

## Performance

- **Success Rate:** 61% on 100 diverse DOIs
- **Speed:** ~60 seconds for 100 DOIs (4 workers)
- **Unpaywall:** 49% success rate (OA discovery)
- **Publisher Strategies:** Additional 12% success

## Python API

### Basic Usage

```python
from pdf_fetcher import BasePDFFetcher

# Initialize fetcher
fetcher = BasePDFFetcher(output_dir="./pdfs")

# Download a single PDF
result = fetcher.fetch("10.1007/s10623-024-01403-z")
print(result)

# Download multiple PDFs
dois = ["10.1007/xxx", "10.1016/yyy", "10.1093/zzz"]
results = fetcher.fetch_batch(dois)

# Check stats
stats = fetcher.get_stats()
print(stats)
```

### VPN Checking (Optional)

For university network access (e.g., downloading paywalled PDFs), you can enable automatic VPN checking:

```python
from pdf_fetcher import BasePDFFetcher

# Enable VPN check - will verify connection before downloads
fetcher = BasePDFFetcher(
    output_dir="./pdfs",
    require_vpn=["130.225", "130.226"]  # Your university IP prefixes
)

# Downloads will only proceed if connected to VPN
# If all PDFs are already cached (skipped), VPN check won't run
results = fetcher.fetch_batch(dois)
```

**Installation for VPN checking:**
```bash
# Install network_utils package
cd ~/Documents/dh4pmp_tools/packages/network_utils
pip install -e .

# Or install pdf_fetcher with VPN support
pip install -e ".[vpn]"
```

The VPN check:
- Only runs when there are actual downloads to perform (not for cached PDFs)
- Verifies your public IP matches university network ranges
- Raises an error if not connected, preventing failed download attempts

## License

MIT License - see [LICENSE](LICENSE) file.
