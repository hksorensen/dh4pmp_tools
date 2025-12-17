#!/usr/bin/env python3
"""
First-run setup for citation tools.

Initializes user configuration with sensible defaults for Henrik's setup.
Can be run as: python -m citation_tools.setup_config
"""

from pathlib import Path
import sys


def setup():
    """Run first-time setup."""
    print("=" * 60)
    print("Citation Tools - First Time Setup")
    print("=" * 60)
    print()
    
    # Import here so it works during installation
    try:
        from citation_tools.user_config import get_user_config
        from citation_tools.config import get_config_dir, get_cache_dir
    except ImportError:
        # During installation, try relative imports
        try:
            from .user_config import get_user_config
            from .config import get_config_dir, get_cache_dir
        except ImportError:
            print("Error: citation_tools not properly installed.")
            print("Please run: pip install -e ./tools/citation_tools")
            return
    
    config = get_user_config()
    
    # Check if already configured
    if config.config_file.exists():
        print(f"✓ Configuration already exists at: {config.config_file}")
        print()
        print("Current settings:")
        print(f"  Bibliography directories:")
        for d in config.get_bibliography_directories():
            exists = "✓" if d.exists() else "✗"
            print(f"    {exists} {d}")
        print(f"  Default style: {config.get_default_style()}")
        print(f"  Default format: {config.get_default_output_format()}")
        print()
        print("Configuration already complete. Run 'cite-setup' to reconfigure.")
        return
    
    print("Setting up configuration...")
    print()
    
    # Check default bibliography directory
    default_bibdir = Path.home() / 'Documents' / 'bibfiles'
    print(f"Checking default bibliography directory: {default_bibdir}")
    
    if default_bibdir.exists():
        bib_files = list(default_bibdir.glob('**/*.bib'))
        print(f"  ✓ Directory exists")
        print(f"  ✓ Found {len(bib_files)} .bib file(s)")
        
        # Set in config
        config.set('bibliography_directories', [str(default_bibdir)])
        print(f"  ✓ Configured as bibliography directory")
    else:
        print(f"  ✗ Directory does not exist")
        print()
        print("Please create it or specify a different directory:")
        print(f"  mkdir -p {default_bibdir}")
        print("  # or")
        print(f"  cite config add-bibdir /your/actual/path")
        print()
        
        # Keep default in config anyway
        config.set('bibliography_directories', [str(default_bibdir)])
        print(f"  ✓ Added to config (create directory before building index)")
    
    print()
    
    # Set Danish preferences
    print("Setting default citation style to 'fund-og-forskning' (Danish)...")
    config.set_default_style('fund-og-forskning')
    print("  ✓ Default style: fund-og-forskning")
    
    print()
    print("Setting default output format to 'clipboard'...")
    config.set_default_output_format('clipboard')
    print("  ✓ Default format: clipboard")
    
    print()
    print("=" * 60)
    print("✓ Setup Complete!")
    print("=" * 60)
    print()
    
    print("Configuration saved to:")
    print(f"  {config.config_file}")
    print()
    
    print("Cache directory:")
    print(f"  {get_cache_dir()}")
    print()
    
    print("Next steps:")
    if default_bibdir.exists():
        print("  1. Build index:")
        print("     cite index build --recursive")
    else:
        print(f"  1. Create bibliography directory or configure a different one:")
        print(f"     mkdir -p {default_bibdir}")
        print("     # or")
        print("     cite config add-bibdir /your/path")
        print()
        print("  2. Build index:")
        print("     cite index build --recursive")
    
    print()
    print("  3. Start using it:")
    print("     cite convert --key YourCitationKey")
    print("     # Automatically uses fund-og-forskning + clipboard!")
    print()


if __name__ == '__main__':
    setup()

