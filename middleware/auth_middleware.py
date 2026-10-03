from functools import wraps
from flask import request, jsonify, session, current_app
from flask_login import current_user
from utils.logger import auth_logger, log_user_action
import time


class AuthMiddleware:
    """Authentication and authorization middleware"""
    
    @staticmethod
    def require_company_access(allowed_companies=None):
        """Decorator to restrict access based on user's company"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not current_user.is_authenticated:
                    auth_logger.warning(f"Unauthenticated access attempt to {request.endpoint}")
                    return jsonify({"error": "Authentication required"}), 401
                
                user_company = current_user.company_id or 'haval'
                
                if allowed_companies and user_company not in allowed_companies:
                    auth_logger.warning(
                        f"Company access denied - User: {current_user.username}, "
                        f"Company: {user_company}, Required: {allowed_companies}"
                    )
                    log_user_action(
                        "Company Access Denied", 
                        current_user.id, 
                        f"Required: {allowed_companies}, Has: {user_company}"
                    )
                    return jsonify({
                        "error": f"Access restricted to {', '.join(allowed_companies)} users only"
                    }), 403
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    @staticmethod
    def log_api_access(f):
        """Decorator to log API access"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            
            # Log request
            user_info = f"User {current_user.id}" if current_user.is_authenticated else "Anonymous"
            auth_logger.info(
                f"API Access - {request.method} {request.endpoint} - {user_info} - "
                f"IP: {request.remote_addr}"
            )
            
            try:
                result = f(*args, **kwargs)
                
                # Log successful completion
                duration = time.time() - start_time
                auth_logger.info(
                    f"API Success - {request.endpoint} - {user_info} - "
                    f"Duration: {duration:.2f}s"
                )
                
                return result
                
            except Exception as e:
                # Log error
                duration = time.time() - start_time
                auth_logger.error(
                    f"API Error - {request.endpoint} - {user_info} - "
                    f"Error: {str(e)} - Duration: {duration:.2f}s"
                )
                raise
                
        return decorated_function
    
    @staticmethod
    def validate_session(f):
        """Decorator to validate user session"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.is_authenticated:
                # Check session validity
                last_activity = session.get('last_activity')
                if last_activity:
                    inactive_time = time.time() - last_activity
                    max_inactive = current_app.config.get('PERMANENT_SESSION_LIFETIME', 86400).total_seconds()
                    
                    if inactive_time > max_inactive:
                        auth_logger.warning(f"Session expired for user {current_user.username}")
                        log_user_action("Session Expired", current_user.id)
                        return jsonify({"error": "Session expired"}), 401
                
                # Update last activity
                session['last_activity'] = time.time()
            
            return f(*args, **kwargs)
        return decorated_function


# Convenience decorators
require_haval_access = AuthMiddleware.require_company_access(['haval'])
require_mg_access = AuthMiddleware.require_company_access(['mg'])
require_kia_access = AuthMiddleware.require_company_access(['kia'])
log_api_access = AuthMiddleware.log_api_access
validate_session = AuthMiddleware.validate_session