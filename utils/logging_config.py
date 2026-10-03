"""
Logging Configuration Utility
Provides centralized logging configuration management for the application
"""

import os
import json
import logging
import logging.config
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

class LoggingConfigManager:
    """Manages logging configuration for the entire application"""
    
    DEFAULT_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "simple": {
                "format": "%(levelname)s - %(message)s"
            },
            "json": {
                "format": '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "module": "%(module)s", "function": "%(funcName)s", "line": %(lineno)d, "message": "%(message)s"}',
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "standard",
                "stream": "ext://sys.stdout"
            },
            "file_handler": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": "logs/app.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "error_file_handler": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": "logs/error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "server_handler": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "standard",
                "filename": "logs/server.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "ai_handler": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": "logs/ai.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "whatsapp_handler": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "standard",
                "filename": "logs/whatsapp.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "chat_handler": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "standard",
                "filename": "logs/chat.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "dealership_handler": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "standard",
                "filename": "logs/dealership.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "fetching_handler": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "standard",
                "filename": "logs/fetching.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            }
        },
        "loggers": {
            "": {  # Root logger
                "handlers": ["console", "file_handler"],
                "level": "INFO",
                "propagate": False
            },
            "server": {
                "handlers": ["console", "server_handler", "error_file_handler"],
                "level": "INFO",
                "propagate": False
            },
            "ai": {
                "handlers": ["console", "ai_handler", "error_file_handler"],
                "level": "DEBUG",
                "propagate": False
            },
            "whatsapp": {
                "handlers": ["console", "whatsapp_handler", "error_file_handler"],
                "level": "INFO",
                "propagate": False
            },
            "chat": {
                "handlers": ["console", "chat_handler", "error_file_handler"],
                "level": "INFO",
                "propagate": False
            },
            "dealership": {
                "handlers": ["console", "dealership_handler", "error_file_handler"],
                "level": "INFO",
                "propagate": False
            },
            "fetching": {
                "handlers": ["console", "fetching_handler", "error_file_handler"],
                "level": "INFO",
                "propagate": False
            }
        }
    }
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize logging config manager"""
        self.config_file = config_file or "config/logging.json"
        self._cached_config = None
        self._config_mtime = None
        self.logs_dir = Path("logs")
        self.ensure_logs_directory()
    
    def ensure_logs_directory(self):
        """Ensure logs directory exists"""
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create .gitkeep to ensure directory is tracked
        gitkeep_file = self.logs_dir / ".gitkeep"
        if not gitkeep_file.exists():
            gitkeep_file.touch()
    
    def load_config(self) -> Dict[str, Any]:
        """Load logging configuration from file or return default (with caching)"""
        config_path = Path(self.config_file)
        
        if config_path.exists():
            try:
                # Check if config file has been modified
                current_mtime = config_path.stat().st_mtime
                
                # Return cached config if file hasn't changed
                if (self._cached_config is not None and 
                    self._config_mtime is not None and 
                    current_mtime == self._config_mtime):
                    return self._cached_config
                
                # Load and cache new config
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                self._cached_config = config
                self._config_mtime = current_mtime
                
                # Only print on first load or when file changes
                if self._config_mtime != current_mtime:
                    print(f"✅ Loaded logging config from {config_path}")
                
                return config
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠️ Error loading logging config from {config_path}: {e}")
                print("📝 Using default configuration")
                return self.DEFAULT_CONFIG
        else:
            if self._cached_config is None:
                print(f"📝 No logging config found at {config_path}, using defaults")
            return self.DEFAULT_CONFIG
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save logging configuration to file"""
        try:
            config_path = Path(self.config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Saved logging config to {config_path}")
            return True
            
        except IOError as e:
            print(f"❌ Error saving logging config: {e}")
            return False
    
    def apply_config(self, config: Optional[Dict[str, Any]] = None):
        """Apply logging configuration"""
        if config is None:
            config = self.load_config()
        
        try:
            # Ensure all log file directories exist
            self._ensure_handler_directories(config)
            
            # Apply the configuration
            logging.config.dictConfig(config)
            
            # Test that logging is working
            logger = logging.getLogger("logging_config")
            logger.info("🚀 Logging configuration applied successfully")
            
            return True
            
        except Exception as e:
            print(f"❌ Error applying logging config: {e}")
            # Fallback to basic configuration
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            return False
    
    def _ensure_handler_directories(self, config: Dict[str, Any]):
        """Ensure all handler log file directories exist"""
        handlers = config.get('handlers', {})
        
        for handler_name, handler_config in handlers.items():
            if 'filename' in handler_config:
                log_file_path = Path(handler_config['filename'])
                log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    def set_log_level(self, logger_name: str, level: str):
        """Set log level for a specific logger"""
        try:
            logger = logging.getLogger(logger_name)
            numeric_level = getattr(logging, level.upper())
            logger.setLevel(numeric_level)
            
            print(f"✅ Set {logger_name} log level to {level.upper()}")
            return True
            
        except AttributeError:
            print(f"❌ Invalid log level: {level}")
            return False
        except Exception as e:
            print(f"❌ Error setting log level: {e}")
            return False
    
    def get_log_levels(self) -> Dict[str, str]:
        """Get current log levels for all loggers"""
        levels = {}
        
        # Get all configured loggers
        config = self.load_config()
        loggers = config.get('loggers', {})
        
        for logger_name in loggers.keys():
            logger = logging.getLogger(logger_name)
            level_name = logging.getLevelName(logger.level)
            levels[logger_name or 'root'] = level_name
        
        return levels
    
    def list_log_files(self) -> Dict[str, Dict[str, Any]]:
        """List all log files with their information"""
        log_files = {}
        
        for log_file in self.logs_dir.glob("*.log"):
            try:
                stat = log_file.stat()
                log_files[log_file.name] = {
                    'path': str(log_file),
                    'size': stat.st_size,
                    'size_mb': round(stat.st_size / (1024 * 1024), 2),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'exists': True
                }
            except OSError:
                log_files[log_file.name] = {
                    'path': str(log_file),
                    'exists': False
                }
        
        return log_files
    
    def rotate_logs(self):
        """Manually rotate all log files"""
        rotated_count = 0
        
        # Get all rotating file handlers
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                try:
                    handler.doRollover()
                    rotated_count += 1
                    print(f"✅ Rotated log file: {handler.baseFilename}")
                except Exception as e:
                    print(f"❌ Error rotating {handler.baseFilename}: {e}")
        
        print(f"🔄 Rotated {rotated_count} log files")
        return rotated_count
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up log files older than specified days"""
        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        cleaned_count = 0
        
        for log_file in self.logs_dir.glob("*.log*"):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    cleaned_count += 1
                    print(f"🗑️ Deleted old log file: {log_file.name}")
            except OSError as e:
                print(f"❌ Error deleting {log_file.name}: {e}")
        
        print(f"🧹 Cleaned up {cleaned_count} old log files")
        return cleaned_count
    
    def create_custom_logger(self, name: str, level: str = "INFO", 
                           log_file: Optional[str] = None) -> logging.Logger:
        """Create a custom logger with specified configuration"""
        logger = logging.getLogger(name)
        
        # Set level
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        logger.setLevel(numeric_level)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # Add file handler if specified
        if log_file:
            log_path = self.logs_dir / log_file
            file_handler = logging.handlers.RotatingFileHandler(
                log_path, maxBytes=10485760, backupCount=5
            )
            file_handler.setLevel(numeric_level)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        logger.propagate = False
        return logger

def setup_logging(config_file: Optional[str] = None) -> LoggingConfigManager:
    """Setup logging configuration for the application"""
    manager = LoggingConfigManager(config_file)
    manager.apply_config()
    return manager

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)

# CLI interface for logging management
def main():
    """Command line interface for logging configuration"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Logging Configuration Manager")
    parser.add_argument("--config", help="Path to logging config file")
    parser.add_argument("--level", help="Set log level for logger")
    parser.add_argument("--logger", help="Logger name (use with --level)")
    parser.add_argument("--rotate", action="store_true", help="Rotate all log files")
    parser.add_argument("--cleanup", type=int, metavar="DAYS", 
                       help="Clean up log files older than DAYS")
    parser.add_argument("--list", action="store_true", help="List all log files")
    parser.add_argument("--levels", action="store_true", help="Show current log levels")
    parser.add_argument("--save-default", action="store_true", 
                       help="Save default configuration to file")
    
    args = parser.parse_args()
    
    manager = LoggingConfigManager(args.config)
    
    if args.save_default:
        manager.save_config(manager.DEFAULT_CONFIG)
        print("✅ Default configuration saved")
        return
    
    if args.level and args.logger:
        manager.set_log_level(args.logger, args.level)
        return
    
    if args.rotate:
        manager.rotate_logs()
        return
    
    if args.cleanup:
        manager.cleanup_old_logs(args.cleanup)
        return
    
    if args.list:
        log_files = manager.list_log_files()
        print("\n📁 Log Files:")
        print("-" * 60)
        for name, info in log_files.items():
            if info['exists']:
                print(f"{name:<20} {info['size_mb']:>8.2f} MB  {info['modified']}")
            else:
                print(f"{name:<20} {'NOT FOUND':>20}")
        return
    
    if args.levels:
        levels = manager.get_log_levels()
        print("\n📊 Current Log Levels:")
        print("-" * 30)
        for logger_name, level in levels.items():
            print(f"{logger_name:<15} {level}")
        return
    
    # Default action: setup logging
    manager.apply_config()
    print("🚀 Logging configuration applied")

if __name__ == "__main__":
    main()