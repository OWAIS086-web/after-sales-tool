import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
import functools
import traceback

class LoggerManager:
    """Centralized logger management with configuration support"""
    
    _loggers = {}
    _config = None
    
    @classmethod
    def set_config(cls, config):
        """Set logging configuration"""
        cls._config = config
    
    @classmethod
    def get_config(cls):
        """Get current logging configuration or defaults"""
        if cls._config:
            return cls._config
        
        # Default configuration
        return {
            'level': 'INFO',
            'log_dir': 'logs',
            'max_log_size': 10485760,  # 10MB
            'backup_count': 5,
            'console_logging': True,
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        }
    
    @classmethod
    def get_logger(cls, name, log_file=None, level=None, console_logging=None):
        """Get or create a logger with specified configuration
        
        Args:
            name: Logger name
            log_file: Optional log file path
            level: Optional log level
            console_logging: Optional override for console logging (True/False/None for default)
        """
        
        if name in cls._loggers:
            return cls._loggers[name]
        
        config = cls.get_config()
        
        # Use config level if not specified
        if level is None:
            level_str = config.get('level', 'INFO')
            level = getattr(logging, level_str.upper(), logging.INFO)
        
        logger = logging.getLogger(name)
        
        config = cls.get_config()
        log_dir = config.get('log_dir', 'logs')
        
        # Create logs directory
        os.makedirs(log_dir, exist_ok=True)
        
        # Remove existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Set logger level explicitly (don't inherit from root)
        logger.setLevel(level)
        
        # Determine if console logging should be enabled
        # Priority: explicit parameter > logger-specific config > global config
        enable_console = console_logging
        if enable_console is None:
            # Check for logger-specific console logging config
            logger_console_config = config.get('logger_console_logging', {})
            if name in logger_console_config:
                enable_console = logger_console_config[name]
            else:
                enable_console = config.get('console_logging', True)
        
        # Console handler (if enabled)
        if enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_formatter = logging.Formatter(
                config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
                '%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        
        # File handler
        if log_file is None:
            log_file = os.path.join(log_dir, f'{name}.log')
        
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=config.get('max_log_size', 10485760),  # 10MB default
            backupCount=config.get('backup_count', 5),
            encoding='utf-8'  # Add UTF-8 encoding to handle emoji characters
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            '%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
        
        # Store logger and return
        cls._loggers[name] = logger
        return logger


def init_logging(config=None):
    """Initialize logging system with configuration"""
    try:
        # Try to use the new logging configuration system
        from utils.logging_config import setup_logging
        
        # Setup logging with the new system
        manager = setup_logging()
        
        # Set config if provided
        if config:
            LoggerManager.set_config(config)
        
        # Create logs directory
        log_dir = LoggerManager.get_config().get('log_dir', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Get server logger for initialization message
        server_logger = LoggerManager.get_logger('server')
        server_logger.info("="*50)
        server_logger.info("LOGGING SYSTEM INITIALIZED (Enhanced)")
        server_logger.info(f"Log directory: {log_dir}")
        server_logger.info(f"Available loggers: {list(LOG_FILES.keys())}")
        server_logger.info("Configuration: Enhanced logging config applied")
        server_logger.info("="*50)
        
        return manager
        
    except ImportError:
        # Fallback to original system if new config is not available
        if config:
            LoggerManager.set_config(config)
        
        # Create logs directory
        log_dir = LoggerManager.get_config().get('log_dir', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Get server logger for initialization message
        server_logger = LoggerManager.get_logger('server')
        server_logger.info("="*50)
        server_logger.info("LOGGING SYSTEM INITIALIZED (Basic)")
        server_logger.info(f"Log directory: {log_dir}")
        server_logger.info(f"Available loggers: {list(LOG_FILES.keys())}")
        server_logger.info("="*50)
        
        return None


# Define log files
LOG_FILES = {
    'user': 'user.log',
    'server': 'server.log',
    'error': 'error.log',
    'scraping': 'scraping.log',
    'fetching': 'fetching.log',
    'warning': 'warning.log',
    'ai': 'ai.log',
    'database': 'database.log',
    'auth': 'auth.log',
    'api': 'api.log',
    'analytics': 'analytics.log',
    'whatsapp': 'whatsapp.log',
    'chat': 'chat.log',
    'dealership': 'dealership.log',
    'scheduler': 'scheduler.log'
}

# Create specific loggers (will be initialized with config when init_logging is called)
user_logger = LoggerManager.get_logger('user', level=logging.INFO)
server_logger = LoggerManager.get_logger('server', level=logging.INFO)
error_logger = LoggerManager.get_logger('error', level=logging.ERROR)
scraping_logger = LoggerManager.get_logger('scraping', level=logging.INFO)
fetching_logger = LoggerManager.get_logger('fetching', level=logging.INFO)
warning_logger = LoggerManager.get_logger('warning', level=logging.WARNING)
ai_logger = LoggerManager.get_logger('ai', level=logging.INFO)
database_logger = LoggerManager.get_logger('database', level=logging.INFO)
auth_logger = LoggerManager.get_logger('auth', level=logging.INFO)
api_logger = LoggerManager.get_logger('api', level=logging.INFO)
analytics_logger = LoggerManager.get_logger('analytics', level=logging.INFO)
whatsapp_logger = LoggerManager.get_logger('whatsapp', level=logging.INFO)
chat_logger = LoggerManager.get_logger('chat', level=logging.INFO)
dealership_logger = LoggerManager.get_logger('dealership', level=logging.INFO)

def log_function_call(logger=None, log_args=True, log_result=False):
    """Decorator to log function calls"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Use provided logger or default to server logger
            log = logger or server_logger
            
            # Log function entry
            func_name = f"{func.__module__}.{func.__name__}"
            
            if log_args and (args or kwargs):
                # Sanitize sensitive data
                safe_args = []
                for arg in args:
                    if isinstance(arg, str) and ('password' in str(arg).lower() or len(str(arg)) > 100):
                        safe_args.append('[SANITIZED]')
                    else:
                        safe_args.append(str(arg)[:100])
                
                safe_kwargs = {}
                for k, v in kwargs.items():
                    if 'password' in k.lower() or 'token' in k.lower():
                        safe_kwargs[k] = '[SANITIZED]'
                    else:
                        safe_kwargs[k] = str(v)[:100] if isinstance(v, str) else v
                
                log.info(f"CALL {func_name} - Args: {safe_args}, Kwargs: {safe_kwargs}")
            else:
                log.info(f"CALL {func_name}")
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Log successful completion
                if log_result and result is not None:
                    result_str = str(result)[:200] if isinstance(result, (str, dict, list)) else type(result).__name__
                    log.info(f"SUCCESS {func_name} - Result: {result_str}")
                else:
                    log.info(f"SUCCESS {func_name}")
                
                return result
                
            except Exception as e:
                # Log error
                error_msg = f"ERROR {func_name} - {type(e).__name__}: {str(e)}"
                log.error(error_msg)
                error_logger.error(f"{error_msg}\nTraceback:\n{traceback.format_exc()}")
                raise
                
        return wrapper
    return decorator

def log_user_action(action, user_id=None, details=None):
    """Log user actions"""
    user_info = f"User {user_id}" if user_id else "Anonymous"
    details_str = f" - {details}" if details else ""
    user_logger.info(f"{user_info}: {action}{details_str}")

def log_error(error, context=None, user_id=None):
    """Log errors with context"""
    context_str = f" Context: {context}" if context else ""
    user_str = f" User: {user_id}" if user_id else ""
    error_logger.error(f"ERROR: {str(error)}{context_str}{user_str}\nTraceback:\n{traceback.format_exc()}")

def log_warning(message, context=None):
    """Log warnings"""
    context_str = f" Context: {context}" if context else ""
    warning_logger.warning(f"WARNING: {message}{context_str}")

def log_scraping_activity(action, url=None, count=None, duration=None):
    """Log scraping activities"""
    url_str = f" URL: {url}" if url else ""
    count_str = f" Count: {count}" if count else ""
    duration_str = f" Duration: {duration}s" if duration else ""
    scraping_logger.info(f"SCRAPING: {action}{url_str}{count_str}{duration_str}")

def log_fetching_activity(action, source=None, count=None, status=None):
    """Log data fetching activities"""
    source_str = f" Source: {source}" if source else ""
    count_str = f" Count: {count}" if count else ""
    status_str = f" Status: {status}" if status else ""
    fetching_logger.info(f"FETCHING: {action}{source_str}{count_str}{status_str}")

def log_ai_activity(action, model=None, tokens=None, duration=None):
    """Log AI activities to both logger and database"""
    from flask_login import current_user
    from models.api_usage import APIUsage
    
    model_str = f" Model: {model}" if model else ""
    tokens_str = f" Tokens: {tokens}" if tokens else ""
    duration_str = f" Duration: {duration}s" if duration else ""
    ai_logger.info(f"AI: {action}{model_str}{tokens_str}{duration_str}")
    
    # Also log to database if user is logged in
    try:
        if current_user and current_user.is_authenticated:
            user_id = current_user.id
            company_id = current_user.company_id or 'haval'
            
            # Determine API type based on action
            api_type = 'rag_engine'
            if 'DMS' in action or 'dealership' in action.lower():
                api_type = 'dms_pipeline'
            elif 'Finance' in action:
                api_type = 'finance_ai'
            elif 'Supply Chain' in action:
                api_type = 'supply_chain_ai'
            elif 'Insights' in action:
                api_type = 'llm_insights'
            elif 'Facebook' in action:
                api_type = 'facebook_ai'
            
            # Log to database
            APIUsage.log_usage(
                user_id=user_id,
                api_type=api_type,
                model_name=model or 'Unknown',
                operation=action,
                input_tokens=0,
                output_tokens=tokens or 0,
                cost=0.0,
                company_id=company_id
            )
    except Exception as e:
        ai_logger.error(f"Failed to log AI activity to database: {str(e)}")

def log_database_activity(action, table=None, count=None, user_id=None):
    """Log database activities"""
    table_str = f" Table: {table}" if table else ""
    count_str = f" Count: {count}" if count else ""
    user_str = f" User: {user_id}" if user_id else ""
    database_logger.info(f"DB: {action}{table_str}{count_str}{user_str}")

# Note: init_logging() is now called from app.py with configuration