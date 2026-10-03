from functools import wraps
from flask import request, jsonify, current_app
from flask_login import current_user
from utils.logger import warning_logger, log_user_action
import time
from collections import defaultdict, deque


class RateLimitingMiddleware:
    """Rate limiting middleware to prevent abuse"""
    
    # In-memory storage for rate limiting (in production, use Redis)
    _request_counts = defaultdict(lambda: deque())
    _blocked_ips = {}
    
    @staticmethod
    def rate_limit(max_requests=60, window_seconds=60, per_user=False):
        """
        Rate limiting decorator
        
        Args:
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            per_user: If True, limit per user; if False, limit per IP
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Determine the key for rate limiting
                if per_user and current_user.is_authenticated:
                    key = f"user_{current_user.id}"
                    identifier = f"User {current_user.username}"
                else:
                    key = f"ip_{request.remote_addr}"
                    identifier = f"IP {request.remote_addr}"
                
                current_time = time.time()
                
                # Check if IP is temporarily blocked
                if key in RateLimitingMiddleware._blocked_ips:
                    block_until = RateLimitingMiddleware._blocked_ips[key]
                    if current_time < block_until:
                        remaining = int(block_until - current_time)
                        warning_logger.warning(
                            f"Rate limit blocked request from {identifier} - "
                            f"Blocked for {remaining} more seconds"
                        )
                        return jsonify({
                            "error": "Rate limit exceeded. Please try again later.",
                            "retry_after": remaining
                        }), 429
                    else:
                        # Remove expired block
                        del RateLimitingMiddleware._blocked_ips[key]
                
                # Get request history for this key
                requests = RateLimitingMiddleware._request_counts[key]
                
                # Remove old requests outside the window
                while requests and requests[0] < current_time - window_seconds:
                    requests.popleft()
                
                # Check if limit exceeded
                if len(requests) >= max_requests:
                    # Block for additional time (progressive blocking)
                    block_duration = min(300, 60 * (len(requests) - max_requests + 1))  # Max 5 minutes
                    RateLimitingMiddleware._blocked_ips[key] = current_time + block_duration
                    
                    warning_logger.warning(
                        f"Rate limit exceeded by {identifier} - "
                        f"Blocked for {block_duration} seconds"
                    )
                    
                    if current_user.is_authenticated:
                        log_user_action(
                            "Rate Limit Exceeded", 
                            current_user.id, 
                            f"Endpoint: {request.endpoint}"
                        )
                    
                    return jsonify({
                        "error": "Rate limit exceeded. Please try again later.",
                        "retry_after": block_duration
                    }), 429
                
                # Add current request
                requests.append(current_time)
                
                # Execute the function
                return f(*args, **kwargs)
                
            return decorated_function
        return decorator
    
    @staticmethod
    def strict_rate_limit(max_requests=10, window_seconds=60):
        """Strict rate limiting for sensitive endpoints"""
        return RateLimitingMiddleware.rate_limit(max_requests, window_seconds, per_user=True)
    
    @staticmethod
    def api_rate_limit(max_requests=100, window_seconds=60):
        """Standard API rate limiting"""
        return RateLimitingMiddleware.rate_limit(max_requests, window_seconds, per_user=True)
    
    @staticmethod
    def auth_rate_limit(max_requests=5, window_seconds=300):
        """Rate limiting for authentication endpoints"""
        return RateLimitingMiddleware.rate_limit(max_requests, window_seconds, per_user=False)
    
    @staticmethod
    def cleanup_old_entries():
        """Clean up old rate limiting entries (call periodically)"""
        current_time = time.time()
        
        # Clean up request counts
        for key in list(RateLimitingMiddleware._request_counts.keys()):
            requests = RateLimitingMiddleware._request_counts[key]
            while requests and requests[0] < current_time - 3600:  # Remove entries older than 1 hour
                requests.popleft()
            
            if not requests:
                del RateLimitingMiddleware._request_counts[key]
        
        # Clean up expired blocks
        for key in list(RateLimitingMiddleware._blocked_ips.keys()):
            if RateLimitingMiddleware._blocked_ips[key] < current_time:
                del RateLimitingMiddleware._blocked_ips[key]


# Convenience decorators
strict_rate_limit = RateLimitingMiddleware.strict_rate_limit()
api_rate_limit = RateLimitingMiddleware.api_rate_limit()
auth_rate_limit = RateLimitingMiddleware.auth_rate_limit()