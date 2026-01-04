#!/usr/bin/env python3
"""
Helper script to set up Elsevier API configuration.

Usage:
    python setup_elsevier_api.py YOUR_API_KEY [YOUR_INST_TOKEN] [YOUR_EMAIL]
"""

import sys
import yaml
from pathlib import Path


def setup_config(api_key, inst_token=None, email=None):
    """Update Elsevier config with API credentials."""
    
    config_path = Path.home() / '.config' / 'elsevier.yaml'
    
    # Load existing config
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}
    
    # Update API key
    config['api_key'] = api_key
    
    # Update inst token if provided
    if inst_token:
        config['inst_token'] = inst_token
    
    # Update email if provided
    if email:
        if 'contact' not in config:
            config['contact'] = {}
        config['contact']['email'] = email
    
    # Ensure other fields exist
    if 'rate_limit' not in config:
        config['rate_limit'] = {
            'requests_per_second': 5,
            'max_requests_per_week': 20000
        }
    
    if 'tdm' not in config:
        config['tdm'] = {
            'format': 'pdf',
            'timeout': 30,
            'max_retries': 3
        }
    
    # Save config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    # Secure permissions
    config_path.chmod(0o600)
    
    print("=" * 80)
    print("Elsevier API Configuration Updated")
    print("=" * 80)
    print(f"\nConfig file: {config_path}")
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    if inst_token:
        print(f"Inst Token: {inst_token[:10]}...{inst_token[-4:]}")
    if email:
        print(f"Email: {email}")
    print(f"\nPermissions: {oct(config_path.stat().st_mode)[-3:]} (secure)")
    print("\n✓ Configuration saved!")
    print("\nNext step: Test with:")
    print(f"  python pdf_fetcher/strategies/elsevier_tdm.py")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python setup_elsevier_api.py API_KEY [INST_TOKEN] [EMAIL]")
        print()
        print("Get your API key from: https://dev.elsevier.com/")
        sys.exit(1)
    
    api_key = sys.argv[1]
    inst_token = sys.argv[2] if len(sys.argv) > 2 else None
    email = sys.argv[3] if len(sys.argv) > 3 else None
    
    setup_config(api_key, inst_token, email)
