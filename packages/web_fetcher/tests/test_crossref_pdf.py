"""Test if Crossref API provides direct PDF URLs for DOIs."""

import json
import requests

# Test DOIs - some publishers provide PDF links in Crossref
test_dois = [
    "10.2138/am.2011.573",  # GeoScienceWorld example
    "10.1371/journal.pone.0033693",  # PLOS ONE (often has PDF links)
    "10.1038/nature12373",  # Nature (might have PDF links)
]

def test_crossref_pdf_url(doi: str):
    """Test if Crossref provides PDF URL for a DOI."""
    print(f"Testing DOI: {doi}")
    print("="*80)
    
    # Fetch from Crossref API
    url = f"https://api.crossref.org/works/{doi}"
    print(f"Fetching: {url}")
    
    try:
        response = requests.get(url, headers={'Accept': 'application/json'})
        if response.status_code == 200:
            data = response.json()
            if 'message' in data:
                metadata = data['message']
                
                print(f"\n✓ Metadata retrieved")
                print(f"  Title: {metadata.get('title', [None])[0]}")
                print(f"  Journal: {metadata.get('container-title', [None])[0]}")
                
                # Check for links
                links = metadata.get('link', [])
                print(f"\n  Links found: {len(links)}")
                
                pdf_urls = []
                for link in links:
                    url_val = link.get('URL', '')
                    content_type = link.get('content-type', '')
                    intended_app = link.get('intended-application', '')
                    
                    print(f"    - URL: {url_val[:80]}...")
                    print(f"      Content-Type: {content_type}")
                    print(f"      Intended Application: {intended_app}")
                    
                    # Check if it's a PDF link
                    is_pdf = (
                        'pdf' in url_val.lower() or 
                        'pdf' in content_type.lower() or
                        content_type == 'application/pdf'
                    )
                    
                    if is_pdf:
                        pdf_urls.append(url_val)
                        print(f"      ✓ PDF link detected!")
                
                if pdf_urls:
                    print(f"\n✓ Found {len(pdf_urls)} PDF URL(s):")
                    for pdf_url in pdf_urls:
                        print(f"  {pdf_url}")
                    return pdf_urls[0]  # Return first PDF URL
                else:
                    print(f"\n✗ No PDF URLs found in Crossref metadata")
                    print(f"\n  Available link fields:")
                    for i, link in enumerate(links, 1):
                        print(f"    Link {i}: {json.dumps(link, indent=6)}")
                    return None
        else:
            print(f"✗ Error: HTTP {response.status_code}")
            print(f"  {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("Testing multiple DOIs to see if Crossref provides PDF URLs...\n")
    
    results = []
    for doi in test_dois:
        print(f"\n{'='*80}")
        pdf_url = test_crossref_pdf_url(doi)
        results.append((doi, pdf_url))
        print()
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    pdf_found_count = sum(1 for _, url in results if url)
    print(f"DOIs with PDF URLs in Crossref: {pdf_found_count}/{len(results)}")
    
    if pdf_found_count > 0:
        print(f"\n✓ Some publishers provide PDF URLs via Crossref!")
        print(f"  Strategy: Try Crossref first, fall back to landing page if not available")
        for doi, pdf_url in results:
            if pdf_url:
                print(f"    {doi}: {pdf_url[:80]}...")
    else:
        print(f"\n✗ Crossref does not provide PDF URLs for these DOIs")
        print(f"  Strategy: Use landing page approach (current implementation)")

