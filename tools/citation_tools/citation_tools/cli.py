#!/usr/bin/env python3
"""
Command-line interface for citation tools.

Provides commands for:
- Converting BibTeX to formatted citations
- Managing BibTeX file index
- Managing CSL styles
- Configuration
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from .citation_converter import bibtex_to_citation, bibtex_to_citation_from_key
from .bibtex_index import BibTeXIndex
from .csl_manager import CSLStyleManager
from .config import get_default_index_path, get_cache_dir, get_config_dir
from .user_config import get_user_config


def cmd_convert(args):
    """Handle convert subcommand."""
    user_config = get_user_config()
    
    # Use config defaults if not specified
    style = args.style or user_config.get_default_style()
    output_format = args.format or user_config.get_default_output_format()
    
    # Determine input source
    if args.key:
        # Convert from citation key - need index
        index_path = Path(args.index) if args.index else get_default_index_path()
        
        # Auto-build index if it doesn't exist
        if not index_path.exists():
            print("Index not found. Building index from configured directories...")
            bib_dirs = user_config.get_bibliography_directories()
            
            if not bib_dirs:
                print("Error: No bibliography directories configured.")
                print("Run: cite config add-bibdir <directory>")
                sys.exit(1)
            
            # Use auto_rebuild=True so it actually builds when we add directories
            bib_index = BibTeXIndex(index_file=index_path, auto_rebuild=True)
            for bib_dir in bib_dirs:
                if bib_dir.exists():
                    bib_index.add_bib_directory(bib_dir, recursive=True)
            print()
        else:
            # Check if index needs updating (if auto_rebuild enabled in config)
            bib_index = BibTeXIndex(index_file=index_path, auto_rebuild=user_config.get('index_auto_rebuild', True))
        
        try:
            result = bibtex_to_citation_from_key(
                args.key,
                bib_index,
                style=style,
                output_format=output_format
            )
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    elif args.file:
        # Read from file
        bibtex_file = Path(args.file)
        if not bibtex_file.exists():
            print(f"Error: File not found: {bibtex_file}")
            sys.exit(1)
        
        bibtex_string = bibtex_file.read_text()
        result = bibtex_to_citation(bibtex_string, style=style, output_format=output_format)
    
    elif args.bibtex:
        # Read from --bibtex flag
        result = bibtex_to_citation(args.bibtex, style=style, output_format=output_format)
    
    else:
        # No input provided
        print("Error: Must provide a citation key, --bibtex string, or --file")
        print("Usage: cite convert <key>")
        print("   or: cite convert --bibtex '@article{...}'")
        print("   or: cite convert --file mybib.bib")
        sys.exit(1)
    
    # Handle output
    if output_format == 'clipboard':
        # Already handled by conversion function
        pass
    elif output_format == 'docx':
        if args.output:
            # Move to specified location
            import shutil
            shutil.move(result, args.output)
            print(f"Created: {args.output}")
        else:
            print(f"Created: {result}")
    else:
        if args.output:
            Path(args.output).write_text(result)
            print(f"Saved to: {args.output}")
        else:
            print(result)


def cmd_index_build(args):
    """Build BibTeX index from directory."""
    index_path = Path(args.index) if args.index else get_default_index_path()
    
    bib_index = BibTeXIndex(index_file=index_path, auto_rebuild=False)
    
    # If no directory specified, use config directories
    if args.directory:
        directories = [Path(args.directory)]
    else:
        user_config = get_user_config()
        directories = user_config.get_bibliography_directories()
        
        if not directories:
            print("Error: No bibliography directories configured.")
            print("Either specify --directory or add directories with:")
            print("  cite config add-bibdir <directory>")
            sys.exit(1)
        
        print(f"Building index from configured directories:")
        for d in directories:
            exists_marker = "✓" if d.exists() else "✗"
            print(f"  {exists_marker} {d}")
            
            # Check for .bib files
            if d.exists():
                bib_files = list(d.glob('**/*.bib' if args.recursive else '*.bib'))
                if not bib_files:
                    print(f"    ⚠ Warning: No .bib files found in {d}")
                else:
                    print(f"    Found {len(bib_files)} .bib file(s)")
            else:
                print(f"    ⚠ Warning: Directory does not exist!")
    
    for directory in directories:
        if directory.exists():
            bib_index.add_bib_directory(directory, recursive=args.recursive)
        else:
            print(f"\nSkipping non-existent directory: {directory}")


def cmd_index_add_file(args):
    """Add single BibTeX file to index."""
    index_path = Path(args.index) if args.index else get_default_index_path()
    
    bib_index = BibTeXIndex(index_file=index_path, auto_rebuild=False)
    bib_index.add_bib_file(Path(args.file))


def cmd_index_add_dir(args):
    """Add directory of BibTeX files to index."""
    index_path = Path(args.index) if args.index else get_default_index_path()
    
    bib_index = BibTeXIndex(index_file=index_path, auto_rebuild=False)
    bib_index.add_bib_directory(Path(args.directory), recursive=args.recursive)


def cmd_index_rebuild(args):
    """Rebuild entire index."""
    index_path = Path(args.index) if args.index else get_default_index_path()
    
    # Allow rebuild even if index doesn't exist (create from scratch)
    bib_index = BibTeXIndex(index_file=index_path, auto_rebuild=False)
    
    # Get directories from config if index doesn't have any files yet
    if not bib_index.bib_files:
        user_config = get_user_config()
        bib_dirs = user_config.get_bibliography_directories()
        
        if not bib_dirs:
            print("Error: No bibliography directories configured.")
            print("Run: cite config add-bibdir <directory>")
            sys.exit(1)
        
        print("Loading bibliography files from configured directories...")
        for bib_dir in bib_dirs:
            if bib_dir.exists():
                bib_index.add_bib_directory(bib_dir, recursive=True)
        print()
    
    bib_index.rebuild_index()


def cmd_index_reset(args):
    """Delete the index completely."""
    index_path = Path(args.index) if args.index else get_default_index_path()
    
    if not index_path.exists():
        print(f"Index does not exist: {index_path}")
        return
    
    if not args.confirm:
        print(f"This will delete the index at: {index_path}")
        print("Run with --confirm to proceed.")
        sys.exit(1)
    
    try:
        index_path.unlink()
        print(f"✓ Index deleted: {index_path}")
        print("\nThe index will be rebuilt automatically on next use, or run:")
        print("  cite index build --recursive")
    except Exception as e:
        print(f"Error deleting index: {e}")
        sys.exit(1)


def cmd_index_list(args):
    """List all citation keys in index."""
    index_path = Path(args.index) if args.index else get_default_index_path()
    
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}")
        sys.exit(1)
    
    bib_index = BibTeXIndex(index_file=index_path, auto_rebuild=False)
    keys = bib_index.list_keys()
    
    for key in keys:
        print(key)
    
    print(f"\nTotal: {len(keys)} entries")


def cmd_index_search(args):
    """Search for citation keys."""
    index_path = Path(args.index) if args.index else get_default_index_path()
    
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}")
        sys.exit(1)
    
    bib_index = BibTeXIndex(index_file=index_path, auto_rebuild=False)
    matches = bib_index.search_keys(args.pattern)
    
    for key in matches:
        print(key)
    
    print(f"\nFound: {len(matches)} matches")


def cmd_index_show(args):
    """Show BibTeX entry for key."""
    index_path = Path(args.index) if args.index else get_default_index_path()
    
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}")
        sys.exit(1)
    
    bib_index = BibTeXIndex(index_file=index_path, auto_rebuild=False)
    entry = bib_index.get_entry(args.key)
    
    if entry:
        print(entry)
    else:
        print(f"Error: Key '{args.key}' not found in index")
        sys.exit(1)


def cmd_index_lookup_doi(args):
    """Lookup citation key by DOI."""
    index_path = Path(args.index) if args.index else get_default_index_path()
    
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}")
        sys.exit(1)
    
    bib_index = BibTeXIndex(index_file=index_path, auto_rebuild=False)
    key = bib_index.get_by_doi(args.doi)
    
    if key:
        print(f"DOI {args.doi} → {key}")
        if args.show:
            print()
            entry = bib_index.get_entry(key)
            print(entry)
    else:
        print(f"Error: No entry found with DOI: {args.doi}")
        sys.exit(1)


def cmd_index_lookup_arxiv(args):
    """Lookup citation key by arXiv ID."""
    index_path = Path(args.index) if args.index else get_default_index_path()
    
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}")
        sys.exit(1)
    
    bib_index = BibTeXIndex(index_file=index_path, auto_rebuild=False)
    key = bib_index.get_by_arxiv(args.arxiv_id)
    
    if key:
        print(f"arXiv {args.arxiv_id} → {key}")
        if args.show:
            print()
            entry = bib_index.get_entry(key)
            print(entry)
    else:
        print(f"Error: No entry found with arXiv ID: {args.arxiv_id}")
        sys.exit(1)


def cmd_index_search_year(args):
    """Search for entries by year."""
    index_path = Path(args.index) if args.index else get_default_index_path()
    
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}")
        sys.exit(1)
    
    bib_index = BibTeXIndex(index_file=index_path, auto_rebuild=False)
    keys = bib_index.search_by_year(args.year)
    
    for key in keys:
        print(key)
    
    print(f"\nFound: {len(keys)} entries from {args.year}")


def cmd_index_info(args):
    """Show index statistics."""
    index_path = Path(args.index) if args.index else get_default_index_path()
    
    if not index_path.exists():
        print(f"Index file not found: {index_path}")
        print("Run 'cite index build' to create an index.")
        sys.exit(1)
    
    bib_index = BibTeXIndex(index_file=index_path, auto_rebuild=False)
    stats = bib_index.get_statistics()
    
    print("Index Statistics:")
    print(f"  Total entries: {stats['total_keys']}")
    print(f"  Total files: {stats['total_files']}")
    print(f"  Index file: {stats['index_file']}")


def cmd_styles_list(args):
    """List available styles."""
    style_manager = CSLStyleManager()
    styles = style_manager.list_available_styles()
    
    if styles['bundled']:
        print("Bundled styles:")
        for style in styles['bundled']:
            print(f"  {style}")
    
    if styles['cached']:
        print("\nCached styles:")
        for style in styles['cached']:
            if style not in styles['bundled']:
                print(f"  {style}")
    
    if styles['remote']:
        print("\nRemote styles (will be downloaded on first use):")
        for style in styles['remote']:
            if style not in styles['cached']:
                print(f"  {style}")


def cmd_styles_show(args):
    """Show style information."""
    style_manager = CSLStyleManager()
    info = style_manager.get_style_info(args.style)
    
    if info:
        print(f"Style: {info['name']}")
        print(f"Path: {info['path']}")
        print(f"Bundled: {'Yes' if info['bundled'] else 'No'}")
        print(f"Remote: {'Yes' if info['remote'] else 'No'}")
        print(f"Exists: {'Yes' if info['exists'] else 'No'}")
    else:
        print(f"Error: Style '{args.style}' not found")
        sys.exit(1)


def cmd_styles_download(args):
    """Pre-download remote style."""
    style_manager = CSLStyleManager()
    
    try:
        style_path = style_manager.get_style_path(args.style)
        print(f"Style available at: {style_path}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_styles_path(args):
    """Print path to style file."""
    style_manager = CSLStyleManager()
    
    try:
        style_path = style_manager.get_style_path(args.style)
        print(style_path)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_config_show(args):
    """Show current configuration."""
    user_config = get_user_config()
    
    print("System Paths:")
    print(f"  Cache directory: {get_cache_dir()}")
    print(f"  Config directory: {get_config_dir()}")
    print(f"  Default index: {get_default_index_path()}")
    print()
    
    print("User Configuration:")
    config = user_config.show()
    
    print(f"  Bibliography directories:")
    for dir in config.get('bibliography_directories', []):
        exists = "✓" if Path(dir).expanduser().exists() else "✗"
        print(f"    {exists} {dir}")
    
    print(f"  Default style: {config.get('default_style', 'not set')}")
    print(f"  Default output format: {config.get('default_output_format', 'not set')}")
    print(f"  Auto-rebuild index: {config.get('index_auto_rebuild', 'not set')}")
    
    excluded = config.get('excluded_files', [])
    if excluded:
        print(f"  Excluded file patterns:")
        for pattern in excluded:
            print(f"    - {pattern}")
    else:
        print(f"  Excluded file patterns: (none)")



def cmd_config_set_style(args):
    """Set default citation style."""
    user_config = get_user_config()
    user_config.set_default_style(args.style)
    print(f"Default style set to: {args.style}")


def cmd_config_set_format(args):
    """Set default output format."""
    user_config = get_user_config()
    user_config.set_default_output_format(args.format)
    print(f"Default output format set to: {args.format}")


def cmd_config_add_bibdir(args):
    """Add bibliography directory to config."""
    user_config = get_user_config()
    bibdir = Path(args.directory).expanduser()
    
    if not bibdir.exists():
        print(f"Warning: Directory does not exist: {bibdir}")
        if not args.force:
            print("Use --force to add anyway")
            sys.exit(1)
    
    user_config.add_bibliography_directory(bibdir)
    print(f"Added bibliography directory: {bibdir}")


def cmd_config_remove_bibdir(args):
    """Remove bibliography directory from config."""
    user_config = get_user_config()
    user_config.remove_bibliography_directory(Path(args.directory))
    print(f"Removed bibliography directory: {args.directory}")


def cmd_config_exclude_file(args):
    """Exclude a file pattern from indexing."""
    user_config = get_user_config()
    user_config.add_excluded_file(args.pattern)
    print(f"Added exclusion pattern: {args.pattern}")
    print("\nNote: You may need to rebuild the index for this to take effect:")
    print("  cite index rebuild")


def cmd_config_include_file(args):
    """Remove a file pattern from exclusion list."""
    user_config = get_user_config()
    excluded = user_config.get_excluded_files()
    
    if args.pattern not in excluded:
        print(f"Pattern '{args.pattern}' is not in exclusion list")
        sys.exit(1)
    
    user_config.remove_excluded_file(args.pattern)
    print(f"Removed exclusion pattern: {args.pattern}")
    print("\nNote: You may need to rebuild the index to include these files:")
    print("  cite index rebuild")


def cmd_config_reset(args):
    """Reset configuration to defaults."""
    if not args.confirm:
        print("This will reset all configuration to defaults.")
        print("Run with --confirm to proceed.")
        sys.exit(1)
    
    user_config = get_user_config()
    user_config.reset_to_defaults()
    print("Configuration reset to defaults")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Citation tools for BibTeX to formatted citations',
        prog='cite'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Convert command
    parser_convert = subparsers.add_parser('convert', help='Convert BibTeX to citation')
    
    # Positional argument: citation key (most common use case)
    parser_convert.add_argument('key', nargs='?', help='Citation key to convert')
    
    # Alternative inputs (mutually exclusive with key)
    parser_convert.add_argument('--bibtex', help='BibTeX entry string')
    parser_convert.add_argument('--file', help='Read BibTeX from file')
    
    parser_convert.add_argument('--style',
                               help='Citation style (default: from config or chicago-author-date)')
    parser_convert.add_argument('--format',
                               choices=['plain', 'markdown', 'html', 'rtf', 'docx', 'clipboard'],
                               help='Output format (default: from config or plain)')
    parser_convert.add_argument('--output', help='Output file path (for docx/html/rtf)')
    parser_convert.add_argument('--index', help='Custom index file path')
    parser_convert.set_defaults(func=cmd_convert)
    
    # Index command
    parser_index = subparsers.add_parser('index', help='Manage BibTeX index')
    index_subparsers = parser_index.add_subparsers(dest='index_command', help='Index commands')
    
    # Index build
    parser_index_build = index_subparsers.add_parser('build', help='Build index from directory')
    parser_index_build.add_argument('--directory', help='Directory containing .bib files (uses config if not specified)')
    parser_index_build.add_argument('--recursive', action='store_true', help='Search subdirectories')
    parser_index_build.add_argument('--index', help='Custom index file path')
    parser_index_build.set_defaults(func=cmd_index_build)
    
    # Index add-file
    parser_index_add_file = index_subparsers.add_parser('add-file', help='Add single .bib file')
    parser_index_add_file.add_argument('file', help='BibTeX file to add')
    parser_index_add_file.add_argument('--index', help='Custom index file path')
    parser_index_add_file.set_defaults(func=cmd_index_add_file)
    
    # Index add-dir
    parser_index_add_dir = index_subparsers.add_parser('add-dir', help='Add directory of .bib files')
    parser_index_add_dir.add_argument('directory', help='Directory to add')
    parser_index_add_dir.add_argument('--recursive', action='store_true', help='Search subdirectories')
    parser_index_add_dir.add_argument('--index', help='Custom index file path')
    parser_index_add_dir.set_defaults(func=cmd_index_add_dir)
    
    # Index rebuild
    parser_index_rebuild = index_subparsers.add_parser('rebuild', help='Rebuild entire index')
    parser_index_rebuild.add_argument('--index', help='Custom index file path')
    parser_index_rebuild.set_defaults(func=cmd_index_rebuild)
    
    # Index reset
    parser_index_reset = index_subparsers.add_parser('reset', help='Delete the index completely')
    parser_index_reset.add_argument('--confirm', action='store_true', help='Confirm deletion')
    parser_index_reset.add_argument('--index', help='Custom index file path')
    parser_index_reset.set_defaults(func=cmd_index_reset)
    
    # Index list
    parser_index_list = index_subparsers.add_parser('list', help='List all citation keys')
    parser_index_list.add_argument('--index', help='Custom index file path')
    parser_index_list.set_defaults(func=cmd_index_list)
    
    # Index search
    parser_index_search = index_subparsers.add_parser('search', help='Search for citation keys')
    parser_index_search.add_argument('pattern', help='Search pattern')
    parser_index_search.add_argument('--index', help='Custom index file path')
    parser_index_search.set_defaults(func=cmd_index_search)
    
    # Index show
    parser_index_show = index_subparsers.add_parser('show', help='Show BibTeX entry')
    parser_index_show.add_argument('key', help='Citation key')
    parser_index_show.add_argument('--index', help='Custom index file path')
    parser_index_show.set_defaults(func=cmd_index_show)
    
    # Index lookup-doi
    parser_index_doi = index_subparsers.add_parser('lookup-doi', help='Lookup citation key by DOI')
    parser_index_doi.add_argument('doi', help='DOI to lookup')
    parser_index_doi.add_argument('--show', action='store_true', help='Show full BibTeX entry')
    parser_index_doi.add_argument('--index', help='Custom index file path')
    parser_index_doi.set_defaults(func=cmd_index_lookup_doi)
    
    # Index lookup-arxiv
    parser_index_arxiv = index_subparsers.add_parser('lookup-arxiv', help='Lookup citation key by arXiv ID')
    parser_index_arxiv.add_argument('arxiv_id', help='arXiv ID to lookup (e.g., 1405.0312)')
    parser_index_arxiv.add_argument('--show', action='store_true', help='Show full BibTeX entry')
    parser_index_arxiv.add_argument('--index', help='Custom index file path')
    parser_index_arxiv.set_defaults(func=cmd_index_lookup_arxiv)
    
    # Index search-year
    parser_index_year = index_subparsers.add_parser('search-year', help='Search entries by year')
    parser_index_year.add_argument('year', help='Year to search for')
    parser_index_year.add_argument('--index', help='Custom index file path')
    parser_index_year.set_defaults(func=cmd_index_search_year)
    
    # Index info
    parser_index_info = index_subparsers.add_parser('info', help='Show index statistics')
    parser_index_info.add_argument('--index', help='Custom index file path')
    parser_index_info.set_defaults(func=cmd_index_info)
    
    # Styles command
    parser_styles = subparsers.add_parser('styles', help='Manage CSL styles')
    styles_subparsers = parser_styles.add_subparsers(dest='styles_command', help='Style commands')
    
    # Styles list
    parser_styles_list = styles_subparsers.add_parser('list', help='List available styles')
    parser_styles_list.set_defaults(func=cmd_styles_list)
    
    # Styles show
    parser_styles_show = styles_subparsers.add_parser('show', help='Show style information')
    parser_styles_show.add_argument('style', help='Style name')
    parser_styles_show.set_defaults(func=cmd_styles_show)
    
    # Styles download
    parser_styles_download = styles_subparsers.add_parser('download', help='Download remote style')
    parser_styles_download.add_argument('style', help='Style name')
    parser_styles_download.set_defaults(func=cmd_styles_download)
    
    # Styles path
    parser_styles_path = styles_subparsers.add_parser('path', help='Show path to style file')
    parser_styles_path.add_argument('style', help='Style name')
    parser_styles_path.set_defaults(func=cmd_styles_path)
    
    # Config command
    parser_config = subparsers.add_parser('config', help='Manage configuration')
    config_subparsers = parser_config.add_subparsers(dest='config_command', help='Config commands')
    
    # Config show
    parser_config_show = config_subparsers.add_parser('show', help='Show configuration')
    parser_config_show.set_defaults(func=cmd_config_show)
    
    # Config set-style
    parser_config_set_style = config_subparsers.add_parser('set-style', help='Set default citation style')
    parser_config_set_style.add_argument('style', help='Style name')
    parser_config_set_style.set_defaults(func=cmd_config_set_style)
    
    # Config set-format
    parser_config_set_format = config_subparsers.add_parser('set-format', help='Set default output format')
    parser_config_set_format.add_argument('format',
                                         choices=['plain', 'markdown', 'html', 'rtf', 'docx', 'clipboard'],
                                         help='Output format')
    parser_config_set_format.set_defaults(func=cmd_config_set_format)
    
    # Config add-bibdir
    parser_config_add_bibdir = config_subparsers.add_parser('add-bibdir', help='Add bibliography directory')
    parser_config_add_bibdir.add_argument('directory', help='Directory path')
    parser_config_add_bibdir.add_argument('--force', action='store_true',
                                         help='Add even if directory does not exist')
    parser_config_add_bibdir.set_defaults(func=cmd_config_add_bibdir)
    
    # Config remove-bibdir
    parser_config_remove_bibdir = config_subparsers.add_parser('remove-bibdir', help='Remove bibliography directory')
    parser_config_remove_bibdir.add_argument('directory', help='Directory path')
    parser_config_remove_bibdir.set_defaults(func=cmd_config_remove_bibdir)
    
    # Config exclude-file
    parser_config_exclude = config_subparsers.add_parser('exclude-file', help='Exclude a file or pattern from indexing')
    parser_config_exclude.add_argument('pattern', help='Filename or glob pattern (e.g., temp.bib, *.backup.bib)')
    parser_config_exclude.set_defaults(func=cmd_config_exclude_file)
    
    # Config include-file
    parser_config_include = config_subparsers.add_parser('include-file', help='Remove a file pattern from exclusion list')
    parser_config_include.add_argument('pattern', help='Pattern to remove from exclusions')
    parser_config_include.set_defaults(func=cmd_config_include_file)
    
    # Config reset
    parser_config_reset = config_subparsers.add_parser('reset', help='Reset to default configuration')
    parser_config_reset.add_argument('--confirm', action='store_true', help='Confirm reset')
    parser_config_reset.set_defaults(func=cmd_config_reset)
    
    # Parse and execute
    args = parser.parse_args()
    
    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == '__main__':
    main()
