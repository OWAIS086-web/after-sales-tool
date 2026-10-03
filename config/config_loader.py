"""
Configuration loader for the Flask application.
Loads settings from config.yml and provides easy access to configuration values.
"""

import yaml
import os
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from utils.logger import server_logger


class ConfigLoader:
    """Configuration loader and manager"""
    
    def __init__(self, config_file: str = "config/config.yml"):
        self.config_file = config_file
        self.config = {}
        self._load_config()
        self._validate_config()
        self._setup_defaults()
    
    def _load_config(self):
        """Load configuration from YAML file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f) or {}
                server_logger.info(f"Configuration loaded from {self.config_file}")
            else:
                server_logger.warning(f"Configuration file {self.config_file} not found, using defaults")
                self.config = {}
        except Exception as e:
            server_logger.error(f"Error loading configuration: {e}")
            self.config = {}
    
    def _validate_config(self):
        """Validate configuration values"""
        # Ensure required sections exist
        required_sections = ['server', 'database', 'logging', 'ai']
        for section in required_sections:
            if section not in self.config:
                self.config[section] = {}
        
        # Validate port number
        port = self.get('server.port', 10000)
        if not isinstance(port, int) or port < 1 or port > 65535:
            server_logger.warning(f"Invalid port {port}, using default 10000")
            self.config['server']['port'] = 10000
        
        # Validate host
        host = self.get('server.host', '127.0.0.1')
        if not isinstance(host, str) or not host.strip():
            server_logger.warning(f"Invalid host {host}, using default 127.0.0.1")
            self.config['server']['host'] = '127.0.0.1'
    
    def _setup_defaults(self):
        """Setup default values and auto-generated settings"""
        # Generate secret key if not provided
        if not self.get('server.secret_key'):
            # Try to get from environment first (for production)
            secret_key = os.getenv('SECRET_KEY')
            if not secret_key:
                # Generate random key as fallback
                secret_key = secrets.token_hex(32)
                server_logger.info("Generated new secret key")
            else:
                server_logger.info("Using SECRET_KEY from environment variable")
            self.set('server.secret_key', secret_key)
        
        # Set build date if not set
        if not self.get('app.build_date'):
            self.set('app.build_date', datetime.now().isoformat())
        
        # Ensure directories exist
        directories = [
            self.get('logging.log_dir', 'logs'),
            self.get('uploads.upload_dir', 'uploads'),
            self.get('backup.backup_dir', 'backups'),
            os.path.dirname(self.get('database.db_file', 'data/haval_marketing.db'))
        ]
        
        for directory in directories:
            if directory and not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                    server_logger.info(f"Created directory: {directory}")
                except Exception as e:
                    server_logger.error(f"Failed to create directory {directory}: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        Example: get('server.port') returns config['server']['port']
        """
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value using dot notation.
        Example: set('server.port', 8000) sets config['server']['port'] = 8000
        """
        keys = key.split('.')
        config = self.config
        
        # Navigate to the parent dictionary
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
    
    def save(self) -> bool:
        """Save current configuration to file"""
        try:
            # Ensure config directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2, sort_keys=False)
            
            server_logger.info(f"Configuration saved to {self.config_file}")
            return True
        except Exception as e:
            server_logger.error(f"Error saving configuration: {e}")
            return False
    
    def reload(self) -> None:
        """Reload configuration from file"""
        self._load_config()
        self._validate_config()
        self._setup_defaults()
        server_logger.info("Configuration reloaded")
    
    def get_flask_config(self) -> Dict[str, Any]:
        """Get Flask-specific configuration"""
        session_timeout_seconds = self.get('server.session_timeout', 3600)
        return {
            'SECRET_KEY': self.get('server.secret_key'),
            'DEBUG': self.get('server.debug', False),
            'TESTING': False,
            'PERMANENT_SESSION_LIFETIME': timedelta(seconds=session_timeout_seconds),
            'SESSION_PERMANENT': self.get('server.permanent_session', False),
            'MAX_CONTENT_LENGTH': self.get('uploads.max_file_size', 52428800),
            'UPLOAD_FOLDER': self.get('uploads.upload_dir', 'uploads'),
        }
    
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return not self.get('server.debug', False)
    
    def get_server_config(self) -> Dict[str, Any]:
        """Get server startup configuration"""
        if self.is_production():
            # Use production settings
            return {
                'host': self.get('server.host', '0.0.0.0'),
                'port': self.get('server.port', 10000),
                'debug': False,
                'use_reloader': False,
                'threaded': self.get('server.threaded', True),
            }
        else:
            # Use development settings
            return {
                'host': self.get('server.host', '127.0.0.1'),
                'port': self.get('server.port', 10000),
                'debug': self.get('server.debug', True),
                'use_reloader': self.get('server.auto_reload', True),
                'threaded': self.get('server.threaded', True),
            }
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return {
            'level': self.get('logging.level', 'INFO'),
            'log_dir': self.get('logging.log_dir', 'logs'),
            'max_log_size': self.get('logging.max_log_size', 10485760),
            'backup_count': self.get('logging.backup_count', 5),
            'console_logging': self.get('logging.console_logging', True),
            'format': self.get('logging.format', '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s')
        }
    
    def get_feature_flags(self) -> Dict[str, bool]:
        """Get feature flags"""
        return self.get('features', {})
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled"""
        return self.get(f'features.{feature}', False)
    
    def get_company_features(self, company_id: str) -> list:
        """Get enabled features for a specific company"""
        return self.get(f'companies.company_features.{company_id}', [])
    
    def is_maintenance_mode(self) -> bool:
        """Check if maintenance mode is enabled"""
        return self.get('maintenance.maintenance_mode', False)
    
    def get_maintenance_message(self) -> str:
        """Get maintenance mode message"""
        return self.get('maintenance.maintenance_message', 'System is under maintenance. Please try again later.')
    
    def export_config(self) -> Dict[str, Any]:
        """Export configuration for settings page (excluding sensitive data)"""
        config_copy = self.config.copy()
        
        # Remove sensitive information
        if 'server' in config_copy and 'secret_key' in config_copy['server']:
            config_copy['server']['secret_key'] = '***HIDDEN***'
        
        return config_copy
    
    def update_from_dict(self, updates: Dict[str, Any]) -> bool:
        """Update configuration from dictionary (for settings page)"""
        try:
            for key, value in updates.items():
                if key != 'server.secret_key':  # Don't allow secret key updates from web
                    self.set(key, value)
            
            self._validate_config()
            return self.save()
        except Exception as e:
            server_logger.error(f"Error updating configuration: {e}")
            return False


# Global configuration instance
config = ConfigLoader()


def get_config() -> ConfigLoader:
    """Get the global configuration instance"""
    return config


def reload_config():
    """Reload the global configuration"""
    global config
    config.reload()