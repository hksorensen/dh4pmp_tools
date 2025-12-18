"""Test the per-PDF JSON metadata output format."""

import json
from pathlib import Path
from datetime import datetime
from web_fetcher.pdf_fetcher_v2 import (
    DownloadResult, 
    DownloadStatus,
    MetadataStore
)

# Create a test PDF directory
pdf_dir = Path("./test_pdfs")
pdf_dir.mkdir(exist_ok=True)

# Create metadata store
metadata_path = pdf_dir / "metadata.json"
store = MetadataStore(metadata_path, pdf_dir=pdf_dir)

# Test 1: Cloudflare abort
print("Test 1: Cloudflare abort")
result1 = DownloadResult(
    identifier="10.2138/am.2011.573",
    sanitized_filename="10_2138_am_2011_573.pdf",
    landing_url="https://pubs.geoscienceworld.org/msa/ammin/article/96/5-6/946/3631753",
    publisher="geoscienceworld",
    status=DownloadStatus.FAILURE,
    error_reason="Cloudflare challenge - Resource URL: https://pubs.geoscienceworld.org/msa/ammin/article/96/5-6/946/3631753, Publisher: geoscienceworld",
    first_attempted=datetime.utcnow().isoformat(),
    last_attempted=datetime.utcnow().isoformat()
)
store.update(result1)

# Test 2: Successful download
print("Test 2: Successful download")
result2 = DownloadResult(
    identifier="10.1038/nature12373",
    sanitized_filename="10_1038_nature12373.pdf",
    landing_url="https://www.nature.com/articles/nature12373",
    pdf_url="http://www.nature.com/articles/nature12373.pdf",
    publisher="nature",
    status=DownloadStatus.SUCCESS,
    pdf_path=pdf_dir / "10_1038_nature12373.pdf",
    first_attempted=datetime.utcnow().isoformat(),
    last_attempted=datetime.utcnow().isoformat(),
    last_successful=datetime.utcnow().isoformat()
)
store.update(result2)

# Test 3: Paywall
print("Test 3: Paywall")
result3 = DownloadResult(
    identifier="10.1016/j.dam.2022.11.002",
    sanitized_filename="10_1016_j_dam_2022_11_002.pdf",
    landing_url="https://www.sciencedirect.com/science/article/pii/S0166218X22002002",
    publisher="elsevier",
    status=DownloadStatus.PAYWALL,
    error_reason="Paywall detected",
    first_attempted=datetime.utcnow().isoformat(),
    last_attempted=datetime.utcnow().isoformat()
)
store.update(result3)

print("\n" + "="*80)
print("Generated JSON files:")
print("="*80)

# Show the JSON files
for json_file in sorted(pdf_dir.glob("*.json")):
    if json_file.name == "metadata.json":
        continue
    print(f"\n{json_file.name}:")
    with open(json_file, 'r') as f:
        data = json.load(f)
        print(json.dumps(data, indent=2))

print("\n" + "="*80)
print("To find Cloudflare aborts, search for:")
print("  grep -l '\"cloudflare_detected\": true' *.json")
print("  or in Python: [f for f in Path('.').glob('*.json') if json.load(open(f))['cloudflare_detected']]")
print("="*80)

