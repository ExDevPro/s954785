"""
Configuration management system for Bulk Email Sender.

This module provides centralized configuration management with support for:
- JSON-based configuration files
- Environment variable overrides
- Default value handling
- Runtime configuration updates
"""

import json
import os
import logging
from typing import Any, Dict, Optional, Union
from pathlib import Path

from core.utils.exceptions import ConfigurationError


class ConfigManager:
    """Manages application configuration with JSON files and environment variables."""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to custom configuration file
        """
        self._config: Dict[str, Any] = {}
        self._config_file: Optional[str] = config_file
        self._base_path = self._get_base_path()
        self._config_dir = os.path.join(self._base_path, 'config')
        self._default_config_file = os.path.join(self._config_dir, 'default_config.json')
        self._user_config_file = os.path.join(self._config_dir, 'settings.json')
        
        self._load_configuration()
    
    def _get_base_path(self) -> str:
        """Get the base path of the application."""
        if hasattr(os.sys, 'frozen'):
            # Running as compiled executable
            return os.path.dirname(os.sys.executable)
        else:
            # Running as script
            return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    def _load_configuration(self) -> None:
        """Load configuration from default and user files."""
        try:
            # Load default configuration
            self._load_default_config()
            
            # Load user configuration (overrides defaults)
            self._load_user_config()
            
            # Apply environment variable overrides
            self._apply_env_overrides()
            
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")
    
    def _load_default_config(self) -> None:
        """Load the default configuration file."""
        if os.path.exists(self._default_config_file):
            try:
                with open(self._default_config_file, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                raise ConfigurationError(f"Invalid default config file: {e}")
        else:
            # Create minimal default config if file doesn't exist
            self._config = self._get_minimal_config()
    
    def _load_user_config(self) -> None:
        """Load user configuration file if it exists."""
        if os.path.exists(self._user_config_file):
            try:
                with open(self._user_config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    self._merge_config(self._config, user_config)
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"Failed to load user config: {e}")
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration."""
        env_mappings = {
            'BES_DEBUG': ('app', 'debug'),
            'BES_LOG_LEVEL': ('logging', 'level'),
            'BES_MAX_THREADS': ('app', 'max_threads'),
            'BES_SMTP_TIMEOUT': ('smtp', 'timeout'),
            'BES_BATCH_SIZE': ('email', 'batch_size'),
        }
        
        for env_var, (section, key) in env_mappings.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                # Convert to appropriate type
                if key in ['debug']:
                    value = value.lower() in ('true', '1', 'yes')
                elif key in ['max_threads', 'timeout', 'batch_size']:
                    try:
                        value = int(value)
                    except ValueError:
                        logging.warning(f"Invalid value for {env_var}: {value}")
                        continue
                
                if section in self._config:
                    self._config[section][key] = value
    
    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """Recursively merge configuration dictionaries."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def _get_minimal_config(self) -> Dict[str, Any]:
        """Get minimal configuration if no config file exists."""
        return {
            'app': {
                'name': 'Bulk Email Sender',
                'version': '2.0.0',
                'debug': False,
                'max_threads': 4
            },
            'logging': {
                'level': 'INFO',
                'max_file_size_mb': 10,
                'backup_count': 5
            },
            'paths': {
                'data_dir': 'data',
                'logs_dir': 'logs'
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.
        
        Args:
            key: Configuration key in dot notation (e.g., 'app.name')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        try:
            keys = key.split('.')
            value = self._config
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value by dot-notation key.
        
        Args:
            key: Configuration key in dot notation
            value: Value to set
        """
        keys = key.split('.')
        config = self._config
        
        # Navigate to parent dictionary
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
    
    def save_user_config(self) -> None:
        """Save current configuration to user config file."""
        try:
            os.makedirs(self._config_dir, exist_ok=True)
            with open(self._user_config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2)
        except IOError as e:
            raise ConfigurationError(f"Failed to save user config: {e}")
    
    def reload(self) -> None:
        """Reload configuration from files."""
        self._load_configuration()
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section.
        
        Args:
            section: Section name
            
        Returns:
            Configuration section dictionary
        """
        return self._config.get(section, {})
    
    def get_all(self) -> Dict[str, Any]:
        """Get complete configuration dictionary."""
        return self._config.copy()
    
    def __getitem__(self, key: str) -> Any:
        """Support dictionary-style access for getting values."""
        return self.get(key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Support dictionary-style access for setting values."""
        self.set(key, value)
    
    def __contains__(self, key: str) -> bool:
        """Support 'in' operator for checking if key exists."""
        try:
            keys = key.split('.')
            value = self._config
            for k in keys:
                value = value[k]
            return True  # If we got here, the key exists
        except (KeyError, TypeError):
            return False
    
    @property
    def base_path(self) -> str:
        """Get application base path."""
        return self._base_path
    
    @property
    def config_dir(self) -> str:
        """Get configuration directory path."""
        return self._config_dir


# Global configuration instance
_config_instance: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance


def init_config(config_file: Optional[str] = None) -> ConfigManager:
    """
    Initialize global configuration instance.
    
    Args:
        config_file: Path to custom configuration file
        
    Returns:
        ConfigManager instance
    """
    global _config_instance
    _config_instance = ConfigManager(config_file)
    return _config_instance


def update_config(updates: Dict[str, Any], save: bool = True) -> None:
    """
    Update configuration with new values.
    
    Args:
        updates: Dictionary of configuration updates in dot notation
                 e.g., {'app.debug': True, 'logging.level': 'DEBUG'}
        save: Whether to save updates to user config file
    """
    config = get_config()
    
    for key, value in updates.items():
        config.set(key, value)
    
    if save:
        config.save_user_config()