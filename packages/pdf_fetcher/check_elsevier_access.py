#!/usr/bin/env python3
"""
Check Elsevier TDM API access.

Instructions:
1. Get your API key from: https://dev.elsevier.com/
2. Optionally get InstToken from your library
3. Run: python check_elsevier_access.py YOUR_API_KEY [YOUR_INST_TOKEN]
"""

import sys
import requests

def check_elsevier_access(api_key, inst_token=None):
    """Test Elsevier API access with a sample DOI."""
    
    # Sample Elsevier DOI from your failed list
    test_doi = "10.1016/j.jalgebra.2024.07.049"
    
    print("=" * 80)
    print("ELSEVIER TDM ACCESS CHECK")
    print("=" * 80)
    print()
    print(f"Testing DOI: {test_doi}")
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    if inst_token:
        print(f"Inst Token: {inst_token[:10]}...{inst_token[-4:]}")
    print()
    
    # Headers
    headers = {
        'X-ELS-APIKey': api_key,
        'Accept': 'application/pdf'
    }
    
    if inst_token:
        headers['X-ELS-Insttoken'] = inst_token
    
    # Test 1: Get article metadata
    print("Test 1: Article Metadata Retrieval")
    print("-" * 80)
    
    meta_url = f"https://api.elsevier.com/content/article/doi/{test_doi}"
    headers_meta = headers.copy()
    headers_meta['Accept'] = 'application/json'
    
    try:
        response = requests.get(meta_url, headers=headers_meta)
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✓ Metadata access: SUCCESS")
            # Check rate limit info
            if 'X-RateLimit-Limit' in response.headers:
                print(f"  Rate limit: {response.headers.get('X-RateLimit-Limit')} requests")
                print(f"  Remaining: {response.headers.get('X-RateLimit-Remaining')}")
                print(f"  Reset: {response.headers.get('X-RateLimit-Reset')}")
        elif response.status_code == 401:
            print("✗ Authentication failed - check API key")
        elif response.status_code == 403:
            print("✗ Access forbidden - may need InstToken or lack subscription")
        elif response.status_code == 404:
            print("⚠ Article not found (DOI may be too new)")
        else:
            print(f"✗ Unexpected status: {response.text[:200]}")
            
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print()
    
    # Test 2: Try to get PDF
    print("Test 2: PDF Download")
    print("-" * 80)
    
    pdf_url = f"https://api.elsevier.com/content/article/doi/{test_doi}"
    
    try:
        response = requests.get(pdf_url, headers=headers, stream=True)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if 'pdf' in content_type:
                print("✓ PDF access: SUCCESS")
                print(f"  Content-Type: {content_type}")
                print(f"  Content-Length: {response.headers.get('Content-Length', 'unknown')} bytes")
            else:
                print(f"⚠ Response is not PDF: {content_type}")
        elif response.status_code == 401:
            print("✗ Authentication failed")
        elif response.status_code == 403:
            print("✗ Access forbidden - likely need institutional subscription")
            print("  You may have API access but not full-text rights")
        else:
            print(f"✗ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print()
    
    # Test 3: Check quota
    print("Test 3: API Quota Check")
    print("-" * 80)
    
    quota_url = "https://api.elsevier.com/content/search/scopus"
    params = {'query': 'DOI(10.1016/j.jalgebra.2024.07.049)'}
    
    try:
        response = requests.get(quota_url, headers=headers_meta, params=params)
        print(f"Status: {response.status_code}")
        
        if 'X-RateLimit-Limit' in response.headers:
            print(f"Rate Limit Info:")
            print(f"  Limit: {response.headers.get('X-RateLimit-Limit')}")
            print(f"  Remaining: {response.headers.get('X-RateLimit-Remaining')}")
            print(f"  Reset: {response.headers.get('X-RateLimit-Reset')}")
            
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print()
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. If tests pass: Implement ElsevierTDMStrategy in pdf_fetcher")
    print("2. If 403 errors: Contact your library about TDM access/InstToken")
    print("3. Check rate limits: Plan download batches accordingly")
    print("4. Read terms: https://dev.elsevier.com/policy.html")
    print()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python check_elsevier_access.py API_KEY [INST_TOKEN]")
        print()
        print("Get your API key from: https://dev.elsevier.com/")
        print("Register or login, then go to 'My API Key'")
        sys.exit(1)
    
    api_key = sys.argv[1]
    inst_token = sys.argv[2] if len(sys.argv) > 2 else None
    
    check_elsevier_access(api_key, inst_token)
