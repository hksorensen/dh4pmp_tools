"""
User configuration management for citation tools.

Handles user-specific settings like default bibliography directories,
preferred citation styles, and other preferences.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import json
import os

from .config import get_config_dir


class UserConfig:
    """Manage user configuration settings."""
    
    DEFAULT_CONFIG = {
        'bibliography_directories': [
            str(Path.home() / 'Documents' / 'bibfiles'),
        ],
        'excluded_files': [],  # List of filenames or glob patterns to exclude
        'default_style': 'chicago-author-date',
        'default_output_format': 'plain',
        'index_auto_rebuild': True,
    }
    
    def __init__(self, config_file: Optional[Path] = None):
        """Initialize user configuration.
        
        Args:
            config_file: Path to config file. If None, uses default location.
        """
        if config_file is None:
            config_dir = get_config_dir('citation_tools')
            config_file = config_dir / 'user_config.json'
        
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = {}
        
        # Load existing config or create with defaults
        self._load_config()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value.
        
        Args:
            key: Configuration key
            value: Value to set
        """
        self.config[key] = value
        self._save_config()
    
    def get_bibliography_directories(self) -> List[Path]:
        """Get list of bibliography directories.
        
        Returns:
            List of Path objects for bibliography directories
        """
        dirs = self.get('bibliography_directories', self.DEFAULT_CONFIG['bibliography_directories'])
        return [Path(d).expanduser() for d in dirs]
    
    def add_bibliography_directory(self, directory: Path) -> None:
        """Add a bibliography directory to the configuration.
        
        Args:
            directory: Path to bibliography directory
        """
        dirs = self.get('bibliography_directories', [])
        dir_str = str(Path(directory).expanduser())
        
        if dir_str not in dirs:
            dirs.append(dir_str)
            self.set('bibliography_directories', dirs)
    
    def remove_bibliography_directory(self, directory: Path) -> None:
        """Remove a bibliography directory from the configuration.
        
        Args:
            directory: Path to bibliography directory
        """
        dirs = self.get('bibliography_directories', [])
        dir_str = str(Path(directory).expanduser())
        
        if dir_str in dirs:
            dirs.remove(dir_str)
            self.set('bibliography_directories', dirs)
    
    def get_default_style(self) -> str:
        """Get default citation style.
        
        Returns:
            Default style name
        """
        return self.get('default_style', self.DEFAULT_CONFIG['default_style'])
    
    def set_default_style(self, style: str) -> None:
        """Set default citation style.
        
        Args:
            style: Style name
        """
        self.set('default_style', style)
    
    def get_default_output_format(self) -> str:
        """Get default output format.
        
        Returns:
            Default output format
        """
        return self.get('default_output_format', self.DEFAULT_CONFIG['default_output_format'])
    
    def set_default_output_format(self, format: str) -> None:
        """Set default output format.
        
        Args:
            format: Output format
        """
        self.set('default_output_format', format)
    
    def get_excluded_files(self) -> List[str]:
        """Get list of excluded file patterns.
        
        Returns:
            List of filenames or glob patterns to exclude
        """
        return self.get('excluded_files', [])
    
    def add_excluded_file(self, pattern: str) -> None:
        """Add a file pattern to exclusion list.
        
        Args:
            pattern: Filename or glob pattern (e.g., 'temp.bib', '*.backup.bib', 'old_*')
        """
        excluded = self.get_excluded_files()
        if pattern not in excluded:
            excluded.append(pattern)
            self.set('excluded_files', excluded)
    
    def remove_excluded_file(self, pattern: str) -> None:
        """Remove a file pattern from exclusion list.
        
        Args:
            pattern: Pattern to remove
        """
        excluded = self.get_excluded_files()
        if pattern in excluded:
            excluded.remove(pattern)
            self.set('excluded_files', excluded)
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self.config = self.DEFAULT_CONFIG.copy()
        self._save_config()
    
    def show(self) -> Dict[str, Any]:
        """Get all configuration settings.
        
        Returns:
            Dictionary of all settings
        """
        return self.config.copy()
    
    def _load_config(self) -> None:
        """Load configuration from file or create with defaults."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                
                # Merge with defaults for any missing keys
                for key, value in self.DEFAULT_CONFIG.items():
                    if key not in self.config:
                        self.config[key] = value
            except Exception as e:
                print(f"Warning: Could not load config from {self.config_file}: {e}")
                self.config = self.DEFAULT_CONFIG.copy()
        else:
            # Create new config with defaults
            self.config = self.DEFAULT_CONFIG.copy()
            self._save_config()
    
    def _save_config(self) -> None:
        """Save configuration to file."""
        # Ensure parent directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)


def get_user_config() -> UserConfig:
    """Get the global user configuration instance.
    
    Returns:
        UserConfig instance
    """
    return UserConfig()
