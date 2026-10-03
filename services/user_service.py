from models.user import User
from models.database import get_db_connection
from utils.logger import auth_logger, log_user_action, log_database_activity
from middleware.error_handling import handle_database_errors
from datetime import datetime, timedelta
import hashlib


class UserService:
    """Service layer for user-related operations"""
    
    @staticmethod
    @handle_database_errors
    def create_user(username, email, password, company_id='haval'):
        """Create a new user with validation"""
        
        # Validate input
        if not username or len(username) < 3:
            raise ValueError("Username must be at least 3 characters long")
        
        if not email or '@' not in email:
            raise ValueError("Valid email address is required")
        
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters long")
        
        # Check for existing user
        existing_user = User.get_by_username(username)
        if existing_user:
            raise ValueError("Username already exists")
        
        # Create user
        user = User.create(username, email, password, company_id)
        if not user:
            raise ValueError("Failed to create user - email may already exist")
        
        # Log activity
        log_user_action("User Created", user.id, f"Company: {company_id}")
        log_database_activity("INSERT", "users", 1, user.id)
        auth_logger.info(f"New user created: {username} (ID: {user.id})")
        
        return user
    
    @staticmethod
    @handle_database_errors
    def authenticate_user(username, password):
        """Authenticate user credentials"""
        
        if not username or not password:
            raise ValueError("Username and password are required")
        
        # Get user
        user = User.get_by_username(username)
        if not user:
            auth_logger.warning(f"Login attempt with non-existent username: {username}")
            raise ValueError("Invalid username or password")
        
        # Verify password
        if not User.verify_password(username, password):
            auth_logger.warning(f"Failed login attempt for user: {username}")
            log_user_action("Login Failed", user.id, "Invalid password")
            raise ValueError("Invalid username or password")
        
        # Update last login
        UserService.update_last_login(user.id)
        
        # Log successful login
        auth_logger.info(f"Successful login: {username} (ID: {user.id})")
        log_user_action("Login Success", user.id)
        
        return user
    
    @staticmethod
    @handle_database_errors
    def update_last_login(user_id):
        """Update user's last login timestamp"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now().isoformat(), user_id)
        )
        
        conn.commit()
        conn.close()
        
        log_database_activity("UPDATE", "users", 1, user_id)
    
    @staticmethod
    @handle_database_errors
    def get_user_profile(user_id):
        """Get comprehensive user profile"""
        user = User.get(user_id)
        if not user:
            raise ValueError("User not found")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get user statistics
        cur.execute("SELECT COUNT(*) FROM posts WHERE user_id = ?", (user_id,))
        post_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM chat_history WHERE user_id = ?", (user_id,))
        chat_count = cur.fetchone()[0]
        
        cur.execute("SELECT last_login FROM users WHERE id = ?", (user_id,))
        last_login = cur.fetchone()[0]
        
        conn.close()
        
        profile = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'company_id': user.company_id,
            'created_at': user.created_at,
            'last_login': last_login,
            'statistics': {
                'posts_scraped': post_count,
                'chat_queries': chat_count
            }
        }
        
        return profile
    
    @staticmethod
    @handle_database_errors
    def update_user_profile(user_id, **kwargs):
        """Update user profile information"""
        user = User.get(user_id)
        if not user:
            raise ValueError("User not found")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build update query
        allowed_fields = ['email']  # Only allow certain fields to be updated
        updates = []
        values = []
        
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                updates.append(f"{field} = ?")
                values.append(value)
        
        if not updates:
            raise ValueError("No valid fields to update")
        
        values.append(user_id)
        
        cur.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
            values
        )
        
        conn.commit()
        conn.close()
        
        log_user_action("Profile Updated", user_id, f"Fields: {list(kwargs.keys())}")
        log_database_activity("UPDATE", "users", 1, user_id)
        
        return User.get(user_id)
    
    @staticmethod
    @handle_database_errors
    def change_password(user_id, current_password, new_password):
        """Change user password"""
        user = User.get(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Verify current password
        if not User.verify_password(user.username, current_password):
            raise ValueError("Current password is incorrect")
        
        # Validate new password
        if len(new_password) < 6:
            raise ValueError("New password must be at least 6 characters long")
        
        # Update password
        from werkzeug.security import generate_password_hash
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        password_hash = generate_password_hash(new_password)
        cur.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id)
        )
        
        conn.commit()
        conn.close()
        
        log_user_action("Password Changed", user_id)
        log_database_activity("UPDATE", "users", 1, user_id)
        auth_logger.info(f"Password changed for user: {user.username}")
    
    @staticmethod
    @handle_database_errors
    def get_user_activity_summary(user_id, days=30):
        """Get user activity summary for the last N days"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get chat activity
        cur.execute("""
            SELECT DATE(timestamp) as date, COUNT(*) as count
            FROM chat_history 
            WHERE user_id = ? AND timestamp >= ?
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """, (user_id, start_date.isoformat()))
        
        chat_activity = {row[0]: row[1] for row in cur.fetchall()}
        
        # Get scraping activity
        cur.execute("""
            SELECT DATE(scraped_at) as date, COUNT(*) as count
            FROM posts 
            WHERE user_id = ? AND scraped_at >= ?
            GROUP BY DATE(scraped_at)
            ORDER BY date DESC
        """, (user_id, start_date.isoformat()))
        
        scraping_activity = {row[0]: row[1] for row in cur.fetchall()}
        
        conn.close()
        
        return {
            'period_days': days,
            'chat_activity': chat_activity,
            'scraping_activity': scraping_activity,
            'total_chats': sum(chat_activity.values()),
            'total_posts': sum(scraping_activity.values())
        }