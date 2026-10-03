from functools import wraps
from flask import jsonify, request, current_app
from flask_login import current_user
from utils.logger import error_logger, log_error, log_user_action
from utils.error_notifier import notify_error
import traceback
import sys


class ErrorHandlingMiddleware:
    """Comprehensive error handling middleware"""
    
    @staticmethod
    def handle_exceptions(return_json=True):
        """Decorator to handle exceptions gracefully"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                try:
                    return f(*args, **kwargs)
                    
                except ValueError as e:
                    # Handle validation errors
                    error_msg = f"Validation Error: {str(e)}"
                    ErrorHandlingMiddleware._log_error(error_msg, "ValueError", f.__name__)
                    
                    if return_json:
                        return jsonify({
                            "success": False,
                            "error": "Invalid input data",
                            "message": str(e)
                        }), 400
                    else:
                        raise
                
                except PermissionError as e:
                    # Handle permission errors
                    error_msg = f"Permission Error: {str(e)}"
                    ErrorHandlingMiddleware._log_error(error_msg, "PermissionError", f.__name__)
                    
                    if return_json:
                        return jsonify({
                            "success": False,
                            "error": "Permission denied",
                            "message": "You don't have permission to perform this action"
                        }), 403
                    else:
                        raise
                
                except FileNotFoundError as e:
                    # Handle file not found errors
                    error_msg = f"File Not Found: {str(e)}"
                    ErrorHandlingMiddleware._log_error(error_msg, "FileNotFoundError", f.__name__)
                    
                    if return_json:
                        return jsonify({
                            "success": False,
                            "error": "Resource not found",
                            "message": "The requested resource could not be found"
                        }), 404
                    else:
                        raise
                
                except ConnectionError as e:
                    # Handle connection errors (database, external APIs)
                    error_msg = f"Connection Error: {str(e)}"
                    ErrorHandlingMiddleware._log_error(error_msg, "ConnectionError", f.__name__)
                    
                    if return_json:
                        return jsonify({
                            "success": False,
                            "error": "Service unavailable",
                            "message": "Unable to connect to required services"
                        }), 503
                    else:
                        raise
                
                except TimeoutError as e:
                    # Handle timeout errors
                    error_msg = f"Timeout Error: {str(e)}"
                    ErrorHandlingMiddleware._log_error(error_msg, "TimeoutError", f.__name__)
                    
                    if return_json:
                        return jsonify({
                            "success": False,
                            "error": "Request timeout",
                            "message": "The request took too long to complete"
                        }), 408
                    else:
                        raise
                
                except Exception as e:
                    # Handle all other exceptions
                    error_msg = f"Unexpected Error: {str(e)}"
                    ErrorHandlingMiddleware._log_error(error_msg, type(e).__name__, f.__name__)
                    
                    if return_json:
                        # Don't expose internal error details in production
                        if current_app.debug:
                            return jsonify({
                                "success": False,
                                "error": "Internal server error",
                                "message": str(e),
                                "traceback": traceback.format_exc()
                            }), 500
                        else:
                            return jsonify({
                                "success": False,
                                "error": "Internal server error",
                                "message": "An unexpected error occurred"
                            }), 500
                    else:
                        raise
                        
            return decorated_function
        return decorator
    
    @staticmethod
    def _log_error(error_msg, error_type, function_name):
        """Log error with context"""
        user_info = f"User {current_user.id}" if current_user.is_authenticated else "Anonymous"
        
        context = {
            "function": function_name,
            "endpoint": request.endpoint if request else "Unknown",
            "method": request.method if request else "Unknown",
            "user": user_info,
            "ip": request.remote_addr if request else "Unknown"
        }
        
        error_logger.error(f"{error_type} in {function_name}: {error_msg}")
        error_logger.error(f"Context: {context}")
        error_logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        # Log user action if authenticated
        if current_user.is_authenticated:
            log_user_action(
                f"Error in {function_name}",
                current_user.id,
                f"{error_type}: {error_msg[:100]}"
            )
    
    @staticmethod
    def handle_database_errors(f):
        """Specific handler for database-related errors"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                if "database" in str(e).lower() or "sqlite" in str(e).lower():
                    error_logger.error(f"Database Error in {f.__name__}: {str(e)}")
                    return jsonify({
                        "success": False,
                        "error": "Database error",
                        "message": "Unable to access database"
                    }), 500
                else:
                    raise
        return decorated_function
    
    @staticmethod
    def handle_ai_errors(f):
        """Specific handler for AI-related errors"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ['model', 'ai', 'llm', 'embedding', 'vector']):
                    error_logger.error(f"AI Error in {f.__name__}: {str(e)}")
                    return jsonify({
                        "success": False,
                        "error": "AI service error",
                        "message": "AI services are temporarily unavailable"
                    }), 503
                else:
                    raise
        return decorated_function


# Convenience decorators
handle_exceptions = ErrorHandlingMiddleware.handle_exceptions()
handle_api_exceptions = ErrorHandlingMiddleware.handle_exceptions(return_json=True)
handle_view_exceptions = ErrorHandlingMiddleware.handle_exceptions(return_json=False)
handle_database_errors = ErrorHandlingMiddleware.handle_database_errors
handle_ai_errors = ErrorHandlingMiddleware.handle_ai_errors