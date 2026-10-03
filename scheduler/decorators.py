"""
Scheduler Decorators

Admin access control via configuration file.
Simply add admin email to config.yml - no database changes needed.
EMAIL is the source of truth for authentication.
Supports multiple admins.
"""

from functools import wraps
from flask import redirect, url_for, flash, jsonify, request
from flask_login import current_user
from config.config_loader import get_config
from utils.logger import LoggerManager

logger = LoggerManager.get_logger('scheduler')


def is_admin_user(user):
    """
    Check if user is an admin based on config.yml settings.

    EMAIL is the SOURCE OF TRUTH for admin access:
    - If user's email matches any admin email in config, access is GRANTED
    - Username match is logged but not required
    - Supports multiple admins in config.yml

    Config example:
    scheduling:
      admin_users:
        - username: "ubi"
          email: "obaid.nasir@visionrdai.com"
        - username: "admin2"
          email: "admin2@example.com"

    Args:
        user: Flask-Login user object

    Returns:
        bool: True if user's email matches any admin email in config
    """
    if not user or not user.is_authenticated:
        return False

    try:
        config = get_config()
        admin_users = config.get('scheduling.admin_users', [])

        if not admin_users:
            logger.warning("No admin users configured in scheduling config")
            return False

        # Get user's email and username
        user_username = user.username.lower().strip() if user.username else ''
        user_email = (user.email.lower().strip() if user.email else '') if hasattr(user, 'email') else ''

        if not user_email:
            logger.warning(f"Admin access denied: user {user.username} has no email")
            return False

        # Check against admin_users list - EMAIL is the source of truth
        for admin in admin_users:
            if isinstance(admin, dict):
                config_username = admin.get('username', '').lower().strip()
                config_email = admin.get('email', '').lower().strip()

                # EMAIL MATCH = ACCESS GRANTED (source of truth)
                if config_email and user_email == config_email:
                    # Check if username also matches (for logging purposes)
                    if config_username and user_username == config_username:
                        logger.info(f"Admin access granted (email + username match): username={user.username}, email={user.email}")
                    else:
                        logger.info(f"Admin access granted (email match): email={user.email} (username mismatch: user={user.username}, config={config_username})")
                    return True

        logger.warning(f"Admin access denied: username={user.username}, email={user_email} (not in admin list)")
        return False

    except Exception as e:
        logger.error(f"Error checking admin status: {e}", exc_info=True)
        return False


def admin_required(f):
    """
    Decorator to require admin access for scheduler routes.

    EMAIL is the source of truth for admin authentication.
    Supports multiple admins defined in config.yml.

    Usage:
        @app.route('/admin/scheduler')
        @login_required
        @admin_required
        def scheduler_dashboard():
            ...

    Admin users are defined in config.yml (email is source of truth):
        scheduling:
          admin_users:
            - username: "admin1"
              email: "admin1@example.com"
            - username: "admin2"
              email: "admin2@example.com"
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))

        if not is_admin_user(current_user):
            logger.warning(f"Non-admin user '{current_user.username}' attempted to access scheduler admin")
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Admin access required'}), 403
            flash("You don't have permission to access the scheduler admin panel.", "error")
            return redirect(url_for('chatbot_advanced'))

        return f(*args, **kwargs)

    return decorated_function


def get_admin_users_display():
    """
    Get list of configured admin users for display.

    Returns:
        list: List of admin user info (username only, for privacy)
    """
    try:
        config = get_config()
        admin_users = config.get('scheduling.admin_users', [])

        display_list = []
        for admin in admin_users:
            if isinstance(admin, dict):
                username = admin.get('username', 'Unknown')
                display_list.append(username)
            elif isinstance(admin, str):
                display_list.append(admin)

        return display_list

    except Exception as e:
        logger.error(f"Error getting admin users display: {e}")
        return []
