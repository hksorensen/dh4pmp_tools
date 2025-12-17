"""
Command-line interface for bibfetcher.
"""

import sys
import argparse
import subprocess
from pathlib import Path

from .bibfetcher import BibFetcher
from .utils import get_input_from_clipboard_or_arg, read_clipboard, write_clipboard
from .user_config import get_user_config
from .config import get_config_dir, get_cache_dir, get_citation_tools_index_path
from .index import load_citation_tools_index, get_entry_info


def cmd_fetch(args):
    """Fetch bibliographic metadata."""
    try:
        # Get input from CLI argument or clipboard
        input_str = get_input_from_clipboard_or_arg(args.identifier)
        
        if args.verbose:
            print(f"Input: {input_str}")
        
        # Create fetcher
        fetcher = BibFetcher(verbose=args.verbose)
        
        # Fetch and process
        result = fetcher.fetch(input_str)
        
        if result is None:
            print("Error: Could not fetch entry.", file=sys.stderr)
            sys.exit(1)
        
        bibkey, bibtex_str, is_duplicate = result
        
        # Handle duplicate
        if is_duplicate:
            print(f"✓ Entry already exists in citation_tools index", file=sys.stderr)
            print(f"✓ Key: {bibkey}", file=sys.stderr)
            
            # Get entry info from index if available
            index_data = load_citation_tools_index()
            if index_data:
                entry_info = get_entry_info(bibkey, index_data)
                if entry_info and 'file' in entry_info:
                    print(f"✓ Location: {entry_info['file']}", file=sys.stderr)
            
            # Copy key to clipboard
            config = get_user_config()
            if config.get('clipboard_output', True):
                try:
                    write_clipboard(bibkey)
                    print(f"✓ Copied key to clipboard: {bibkey}", file=sys.stderr)
                except Exception as e:
                    if args.verbose:
                        print(f"Warning: Failed to copy to clipboard: {e}", file=sys.stderr)
            
            sys.exit(0)  # Success - not an error!
        
        # New entry - print the BibTeX
        print(bibtex_str)
        
        if not args.quiet:
            print(f"\nGenerated key: {bibkey}", file=sys.stderr)
        
        # Interactive: Ask if user wants to append to file
        if not args.quiet and not args.no_interactive:
            try:
                response = input("\nAppend to bibliography file? [Y/n]: ").strip().lower()
                
                # Default to yes (any response except explicit 'n' or 'no')
                if response in ('n', 'no'):
                    # No append - copy full BibTeX to clipboard (current behavior)
                    if config.get('clipboard_output', True):
                        try:
                            write_clipboard(bibtex_str)
                            if args.verbose:
                                print(f"✓ Copied BibTeX to clipboard", file=sys.stderr)
                        except Exception as e:
                            print(f"Warning: Failed to copy to clipboard: {e}", file=sys.stderr)
                
                else:
                    # Yes (default) - append to file
                    # Get bibliography file from config
                    config = get_user_config()
                    bib_dirs = config.get_bibliography_directories()
                    
                    if not bib_dirs:
                        print("No bibliography directory configured.", file=sys.stderr)
                        print("Run: bibfetch config set bibliography_directories /path/to/bibfiles", file=sys.stderr)
                        sys.exit(1)
                    
                    # Use first directory
                    bib_dir = bib_dirs[0]
                    if not bib_dir.exists():
                        print(f"Bibliography directory does not exist: {bib_dir}", file=sys.stderr)
                        sys.exit(1)
                    
                    # Get bibliography filename from config (or use default)
                    bib_filename = config.get('bibliography_filename', 'references.bib')
                    bib_file = bib_dir / bib_filename
                    
                    # Append to file
                    try:
                        with open(bib_file, 'a', encoding='utf-8') as f:
                            f.write('\n')
                            f.write(bibtex_str)
                            f.write('\n')
                        
                        print(f"\n✓ Appended to: {bib_file}", file=sys.stderr)
                        
                        # Update citation_tools index if available
                        try:
                            # Try to run cite index update (citation_tools CLI)
                            result = subprocess.run(
                                ['cite', 'index', 'add-file', str(bib_file)],
                                capture_output=True,
                                text=True,
                                timeout=10
                            )
                            if result.returncode == 0:
                                print(f"✓ Updated citation_tools index", file=sys.stderr)
                                # Reload the index so future fetches see this entry
                                fetcher.index_data = load_citation_tools_index()
                            elif args.verbose:
                                print(f"Note: cite index add-file returned non-zero: {result.returncode}", file=sys.stderr)
                                if result.stderr:
                                    print(f"  stderr: {result.stderr}", file=sys.stderr)
                        except FileNotFoundError:
                            # cite command not installed or not in PATH
                            if args.verbose:
                                print(f"Note: cite command not found (index not updated)", file=sys.stderr)
                        except Exception as e:
                            if args.verbose:
                                print(f"Note: Could not update citation_tools index: {e}", file=sys.stderr)
                        
                        # Copy key only to clipboard
                        write_clipboard(bibkey)
                        print(f"✓ Copied key to clipboard: {bibkey}", file=sys.stderr)
                    
                    except IOError as e:
                        print(f"Error writing to file: {e}", file=sys.stderr)
                        sys.exit(1)
            
            except (EOFError, KeyboardInterrupt):
                # User interrupted (Ctrl+C or Ctrl+D)
                print("\nCancelled.", file=sys.stderr)
                sys.exit(1)
        
        else:
            # Non-interactive mode - copy full BibTeX (current behavior)
            config = get_user_config()
            if config.get('clipboard_output', True):
                try:
                    write_clipboard(bibtex_str)
                    if args.verbose:
                        print(f"✓ Copied to clipboard: {bibkey}", file=sys.stderr)
                except Exception as e:
                    print(f"Warning: Failed to copy to clipboard: {e}", file=sys.stderr)
    
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_config_show(args):
    """Show current configuration."""
    config = get_user_config()
    
    print("Configuration:")
    print(f"  Config directory: {get_config_dir()}")
    print(f"  Cache directory: {get_cache_dir()}")
    print()
    
    print("User Settings:")
    settings = config.show()
    print(f"  Bibliography directories:")
    for dir_path in settings.get('bibliography_directories', []):
        exists = "✓" if Path(dir_path).expanduser().exists() else "✗"
        print(f"    {exists} {dir_path}")
    
    # Show the actual target file for appending
    bib_dirs = config.get_bibliography_directories()
    if bib_dirs:
        bib_filename = settings.get('bibliography_filename', 'references.bib')
        target_file = bib_dirs[0] / bib_filename
        exists = "✓" if target_file.exists() else "✗"
        print(f"  Bibliography filename: {bib_filename}")
        print(f"  Append target: {exists} {target_file}")
    
    print(f"  Clipboard output: {settings.get('clipboard_output', True)}")
    print(f"  PDF Preview enabled: {settings.get('pdf_preview_enabled', True)}")
    print(f"  Verbose: {settings.get('verbose', False)}")
    print()
    
    # Check citation_tools index
    index_path = get_citation_tools_index_path()
    if index_path:
        print(f"citation_tools index: ✓ {index_path}")
    else:
        print("citation_tools index: ✗ Not found")


def cmd_config_set(args):
    """Set configuration value."""
    config = get_user_config()
    
    # Convert string boolean values
    value = args.value
    if value.lower() in ('true', 'yes', '1'):
        value = True
    elif value.lower() in ('false', 'no', '0'):
        value = False
    
    config.set(args.key, value)
    print(f"Set {args.key} = {value}")


def cmd_config_reset(args):
    """Reset configuration to defaults."""
    if not args.confirm:
        print("This will reset all configuration to defaults.")
        print("Run with --confirm to proceed.")
        sys.exit(1)
    
    config = get_user_config()
    config.reset_to_defaults()
    print("Configuration reset to defaults")


def main():
    """Main CLI entry point."""
    from . import __version__
    
    # Check if first argument is a known subcommand
    if len(sys.argv) > 1 and sys.argv[1] in ['config', 'fetch']:
        # Subcommand mode
        parser = argparse.ArgumentParser(
            prog='bibfetch',
            description='Fetch bibliographic metadata from DOI, ISBN, arXiv ID, or PDF files'
        )
        parser.add_argument(
            '--version',
            action='version',
            version=f'bibfetch {__version__}'
        )
        
        subparsers = parser.add_subparsers(dest='command', help='Commands')
        
        # Fetch command
        fetch_parser = subparsers.add_parser(
            'fetch',
            help='Fetch bibliographic metadata',
            epilog='Examples:\n'
                   '  bibfetch fetch 10.1234/example\n'
                   '  bibfetch fetch 2404.12345 -v\n'
                   '  bibfetch fetch  # use clipboard\n',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        fetch_parser.add_argument(
            'identifier',
            nargs='?',
            help='DOI, ISBN, arXiv ID, or PDF file path (uses clipboard if not provided)'
        )
        fetch_parser.add_argument(
            '-v', '--verbose',
            action='store_true',
            help='Verbose output'
        )
        fetch_parser.add_argument(
            '-q', '--quiet',
            action='store_true',
            help='Suppress informational messages'
        )
        fetch_parser.add_argument(
            '-n', '--no-interactive',
            action='store_true',
            help='Non-interactive mode (no prompts, copy full BibTeX to clipboard)'
        )
        fetch_parser.set_defaults(func=cmd_fetch)
        
        # Config command
        config_parser = subparsers.add_parser('config', help='Manage configuration')
        config_subparsers = config_parser.add_subparsers(dest='config_command')
        
        # Config show
        config_show = config_subparsers.add_parser('show', help='Show configuration')
        config_show.set_defaults(func=cmd_config_show)
        
        # Config set
        config_set = config_subparsers.add_parser('set', help='Set configuration value')
        config_set.add_argument('key', help='Configuration key')
        config_set.add_argument('value', help='Configuration value')
        config_set.set_defaults(func=cmd_config_set)
        
        # Config reset
        config_reset = config_subparsers.add_parser('reset', help='Reset configuration')
        config_reset.add_argument('--confirm', action='store_true', help='Confirm reset')
        config_reset.set_defaults(func=cmd_config_reset)
        
        args = parser.parse_args()
        
        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()
    
    else:
        # Direct mode (default) - treat as fetch
        parser = argparse.ArgumentParser(
            prog='bibfetch',
            description='Fetch bibliographic metadata from DOI, ISBN, arXiv ID, or PDF files',
            epilog='Examples:\n'
                   '  bibfetch 10.1234/example      # Fetch from DOI\n'
                   '  bibfetch 2404.12345           # Fetch from arXiv ID\n'
                   '  bibfetch paper.pdf            # Extract DOI from PDF\n'
                   '  bibfetch                      # Use clipboard content\n'
                   '\n'
                   'Explicit subcommands:\n'
                   '  bibfetch fetch <id>           # Same as above\n'
                   '  bibfetch config show          # Show settings\n'
                   '  bibfetch config set key value # Set a value\n',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        
        parser.add_argument(
            '--version',
            action='version',
            version=f'bibfetch {__version__}'
        )
        
        parser.add_argument(
            'identifier',
            nargs='?',
            help='DOI, ISBN, arXiv ID, or PDF file path (uses clipboard if not provided)'
        )
        parser.add_argument(
            '-v', '--verbose',
            action='store_true',
            help='Verbose output'
        )
        parser.add_argument(
            '-q', '--quiet',
            action='store_true',
            help='Suppress informational messages'
        )
        parser.add_argument(
            '-n', '--no-interactive',
            action='store_true',
            help='Non-interactive mode (no prompts, copy full BibTeX to clipboard)'
        )
        
        args = parser.parse_args()
        args.func = cmd_fetch
        args.func(args)


if __name__ == '__main__':
    main()
