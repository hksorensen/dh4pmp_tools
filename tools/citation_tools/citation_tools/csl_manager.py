"""
CSL style management with bundled styles and remote downloading.

Manages citation style language (CSL) files with support for:
- Bundled styles (distributed with package)
- Cached styles (previously downloaded)
- Remote styles (downloaded on-demand from Zotero repository)
"""

from pathlib import Path
from typing import Optional, Dict, List
import urllib.request
import shutil


class CSLStyleManager:
    """Manage CSL style files with bundled defaults and remote downloading."""
    
    # Remote styles available from Zotero repository
    REMOTE_STYLES = {
        'chicago-note-bibliography': 'https://raw.githubusercontent.com/citation-style-language/styles/master/chicago-note-bibliography.csl',
        'chicago-author-date': 'https://raw.githubusercontent.com/citation-style-language/styles/master/chicago-author-date.csl',
        'apa': 'https://raw.githubusercontent.com/citation-style-language/styles/master/apa.csl',
        'authoryear': 'https://raw.githubusercontent.com/citation-style-language/styles/master/chicago-author-date.csl',  # alias
    }
    
    # Bundled styles (distributed with package)
    BUNDLED_STYLES = [
        'fund-og-forskning',
    ]
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize CSL style manager.
        
        Args:
            cache_dir: Directory to cache styles. 
                      If None, uses config.get_cache_dir()
        """
        if cache_dir is None:
            from .config import get_cache_dir
            cache_dir = get_cache_dir('citation_tools')
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Install bundled styles on initialization
        self._install_bundled_styles()
    
    def get_style_path(self, style: str) -> Path:
        """Get path to CSL style file.
        
        Resolution order:
        1. Check cache (includes bundled styles)
        2. Download from remote if available
        3. Raise error if not found
        
        Args:
            style: Style name (e.g., 'fund-og-forskning', 'chicago-author-date')
            
        Returns:
            Path to CSL file
            
        Raises:
            ValueError: If style not found
        """
        # Check cache first (includes bundled styles)
        cached_path = self.cache_dir / f'{style}.csl'
        if cached_path.exists():
            return cached_path
        
        # Download from remote if available
        if style in self.REMOTE_STYLES:
            return self._download_remote_style(style)
        
        # Not found
        available = self.list_available_styles()
        raise ValueError(
            f"Style '{style}' not found.\n"
            f"Available styles: {', '.join(available['all'])}"
        )
    
    def list_available_styles(self) -> Dict[str, List[str]]:
        """List all available styles.
        
        Returns:
            Dictionary with 'bundled', 'cached', 'remote', and 'all' style lists
        """
        cached = [f.stem for f in self.cache_dir.glob('*.csl')]
        remote = list(self.REMOTE_STYLES.keys())
        
        return {
            'bundled': self.BUNDLED_STYLES,
            'cached': sorted(cached),
            'remote': sorted(remote),
            'all': sorted(set(cached + remote))
        }
    
    def get_style_info(self, style: str) -> Optional[Dict]:
        """Get information about a style.
        
        Args:
            style: Style name
            
        Returns:
            Dictionary with style info, or None if not found
        """
        try:
            style_path = self.get_style_path(style)
            
            is_bundled = style in self.BUNDLED_STYLES
            is_remote = style in self.REMOTE_STYLES
            
            return {
                'name': style,
                'path': str(style_path),
                'bundled': is_bundled,
                'remote': is_remote,
                'exists': style_path.exists(),
            }
        except ValueError:
            return None
    
    def _install_bundled_styles(self) -> None:
        """Install bundled CSL styles from package data to cache."""
        try:
            # Try Python 3.9+ approach first
            from importlib.resources import files
            styles_dir = files('citation_tools') / 'styles'
            
            for style_name in self.BUNDLED_STYLES:
                try:
                    source = styles_dir / f'{style_name}.csl'
                    dest = self.cache_dir / f'{style_name}.csl'
                    
                    # Copy bundled style to cache if not already there
                    if not dest.exists() and source.is_file():
                        content = source.read_text()
                        dest.write_text(content)
                except Exception as e:
                    # Silently skip if bundled style not found (dev environment)
                    pass
        
        except (ImportError, AttributeError):
            # Python 3.7-3.8 fallback
            try:
                import pkg_resources
                
                for style_name in self.BUNDLED_STYLES:
                    try:
                        content = pkg_resources.resource_string(
                            'citation_tools',
                            f'styles/{style_name}.csl'
                        ).decode('utf-8')
                        
                        dest = self.cache_dir / f'{style_name}.csl'
                        if not dest.exists():
                            dest.write_text(content)
                    except Exception:
                        # Silently skip if bundled style not found
                        pass
            except ImportError:
                # No package resources available (development mode)
                # Try to find styles directory relative to this file
                styles_dir = Path(__file__).parent / 'styles'
                if styles_dir.exists():
                    for style_name in self.BUNDLED_STYLES:
                        source = styles_dir / f'{style_name}.csl'
                        dest = self.cache_dir / f'{style_name}.csl'
                        
                        if source.exists() and not dest.exists():
                            shutil.copy(source, dest)
    
    def _download_remote_style(self, style: str) -> Path:
        """Download CSL style from remote repository.
        
        Args:
            style: Style name from REMOTE_STYLES
            
        Returns:
            Path to downloaded and cached CSL file
        """
        url = self.REMOTE_STYLES[style]
        cache_file = self.cache_dir / f'{style}.csl'
        
        print(f"Downloading CSL style '{style}' from Zotero repository...")
        try:
            urllib.request.urlretrieve(url, cache_file)
            print(f"✓ Downloaded to cache")
        except Exception as e:
            raise RuntimeError(f"Failed to download CSL style '{style}': {e}")
        
        return cache_file
