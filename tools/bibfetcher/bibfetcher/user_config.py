"""
User configuration management for bibfetcher.

Stores user preferences like bibliography directories, default output settings, etc.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import json

from .config import get_config_dir


class UserConfig:
    """Manage user configuration settings."""
    
    DEFAULT_CONFIG = {
        'bibliography_directories': [
            str(Path.home() / 'Documents' / 'bibfiles'),
        ],
        'bibliography_filename': 'references.bib',
        'clipboard_output': True,
        'pdf_preview_enabled': True,
        'verbose': False,
    }
    
    def __init__(self, config_file: Optional[Path] = None):
        """Initialize user configuration.
        
        Args:
            config_file: Path to config file. If None, uses default location.
        """
        if config_file is None:
            config_dir = get_config_dir('bibfetcher')
            config_file = config_dir / 'user_config.json'
        
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = {}
        
        # Load existing config or create with defaults
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file or create with defaults."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config from {self.config_file}: {e}")
                print("Using default configuration")
                self.config = self.DEFAULT_CONFIG.copy()
        else:
            self.config = self.DEFAULT_CONFIG.copy()
            self._save_config()
    
    def _save_config(self) -> None:
        """Save configuration to file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
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
        dirs = self.config.get('bibliography_directories', [])
        return [Path(d).expanduser() for d in dirs]
    
    def add_bibliography_directory(self, directory: Path) -> None:
        """Add a bibliography directory to configuration.
        
        Args:
            directory: Directory to add
        """
        dirs = self.config.get('bibliography_directories', [])
        dir_str = str(directory)
        
        if dir_str not in dirs:
            dirs.append(dir_str)
            self.config['bibliography_directories'] = dirs
            self._save_config()
    
    def remove_bibliography_directory(self, directory: Path) -> None:
        """Remove a bibliography directory from configuration.
        
        Args:
            directory: Directory to remove
        """
        dirs = self.config.get('bibliography_directories', [])
        dir_str = str(directory)
        
        if dir_str in dirs:
            dirs.remove(dir_str)
            self.config['bibliography_directories'] = dirs
            self._save_config()
    
    def show(self) -> Dict[str, Any]:
        """Get all configuration as dictionary.
        
        Returns:
            Dictionary of all configuration settings
        """
        return self.config.copy()
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self.config = self.DEFAULT_CONFIG.copy()
        self._save_config()


# Global config instance
_user_config: Optional[UserConfig] = None


def get_user_config() -> UserConfig:
    """Get the global user configuration instance.
    
    Returns:
        UserConfig instance
    """
    global _user_config
    if _user_config is None:
        _user_config = UserConfig()
    return _user_config
