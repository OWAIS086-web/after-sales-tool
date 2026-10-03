from functools import wraps
from flask import request, g
from flask_login import current_user
from utils.logger import server_logger, api_logger, log_user_action
import time
import uuid


class LoggingMiddleware:
    """Comprehensive logging middleware"""
    
    @staticmethod
    def log_request_response(logger=None):
        """Decorator to log request and response details"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Generate request ID
                request_id = str(uuid.uuid4())[:8]
                g.request_id = request_id
                
                # Use provided logger or default
                log = logger or server_logger
                
                start_time = time.time()
                
                # Log request details
                user_info = f"User:{current_user.id}" if current_user.is_authenticated else "Anonymous"
                log.info(
                    f"[{request_id}] REQUEST {request.method} {request.path} - "
                    f"{user_info} - IP:{request.remote_addr}"
                )
                
                # Log request data (sanitized)
                if request.is_json and request.json:
                    sanitized_data = LoggingMiddleware._sanitize_data(request.json)
                    log.debug(f"[{request_id}] Request Data: {sanitized_data}")
                
                try:
                    # Execute function
                    result = f(*args, **kwargs)
                    
                    # Log response
                    duration = time.time() - start_time
                    status_code = getattr(result, 'status_code', 200) if hasattr(result, 'status_code') else 200
                    
                    log.info(
                        f"[{request_id}] RESPONSE {status_code} - "
                        f"Duration:{duration:.3f}s"
                    )
                    
                    # Log user action
                    if current_user.is_authenticated:
                        log_user_action(
                            f"{request.method} {request.endpoint}",
                            current_user.id,
                            f"Duration: {duration:.3f}s"
                        )
                    
                    return result
                    
                except Exception as e:
                    # Log error
                    duration = time.time() - start_time
                    log.error(
                        f"[{request_id}] ERROR {type(e).__name__}: {str(e)} - "
                        f"Duration:{duration:.3f}s"
                    )
                    raise
                    
            return decorated_function
        return decorator
    
    @staticmethod
    def _sanitize_data(data):
        """Sanitize sensitive data from logs"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in ['password', 'token', 'secret', 'key']):
                    sanitized[key] = '[REDACTED]'
                elif isinstance(value, (dict, list)):
                    sanitized[key] = LoggingMiddleware._sanitize_data(value)
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [LoggingMiddleware._sanitize_data(item) for item in data]
        else:
            return data
    
    @staticmethod
    def log_performance(threshold_seconds=1.0):
        """Decorator to log slow operations"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                start_time = time.time()
                
                try:
                    result = f(*args, **kwargs)
                    
                    duration = time.time() - start_time
                    if duration > threshold_seconds:
                        server_logger.warning(
                            f"SLOW OPERATION: {f.__name__} took {duration:.3f}s "
                            f"(threshold: {threshold_seconds}s)"
                        )
                    
                    return result
                    
                except Exception as e:
                    duration = time.time() - start_time
                    server_logger.error(
                        f"FAILED OPERATION: {f.__name__} failed after {duration:.3f}s - "
                        f"Error: {str(e)}"
                    )
                    raise
                    
            return decorated_function
        return decorator


# Convenience decorators
log_request = LoggingMiddleware.log_request_response()
log_api_request = LoggingMiddleware.log_request_response(api_logger)
log_slow_operations = LoggingMiddleware.log_performance()