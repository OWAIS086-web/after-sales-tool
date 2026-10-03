from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .database import get_db_connection
from utils.logger import auth_logger, database_logger, log_function_call, log_user_action, log_error


class User(UserMixin):
    def __init__(self, id, username, email, created_at=None, company_id=None):
        self.id = id
        self.username = username
        self.email = email
        self.created_at = created_at
        self.company_id = company_id or 'haval'  # Default to haval for backward compatibility
        auth_logger.debug(f"User object created: ID={id}, Username={username}, Company={self.company_id}")
    
    @staticmethod
    @log_function_call(auth_logger)
    def get(user_id):
        """Get user by ID"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, username, email, created_at, company_id FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            conn.close()
            
            if row:
                user = User(row[0], row[1], row[2], row[3], row[4])
                auth_logger.info(f"User retrieved successfully: ID={user_id}, Username={user.username}")
                return user
            else:
                auth_logger.warning(f"User not found: ID={user_id}")
                return None
                
        except Exception as e:
            log_error(e, f"Failed to get user by ID: {user_id}")
            return None
    
    @staticmethod
    @log_function_call(auth_logger)
    def get_by_username(username):
        """Get user by username"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, username, email, created_at, company_id FROM users WHERE username = ?", (username,))
            row = cur.fetchone()
            conn.close()
            
            if row:
                user = User(row[0], row[1], row[2], row[3], row[4])
                auth_logger.info(f"User retrieved by username: {username}, ID={user.id}")
                return user
            else:
                auth_logger.warning(f"User not found by username: {username}")
                return None
                
        except Exception as e:
            log_error(e, f"Failed to get user by username: {username}")
            return None
    
    @staticmethod
    @log_function_call(auth_logger, log_args=False)  # Don't log password
    def create(username, email, password, company_id='haval', is_verified=False):
        """Create a new user"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Check if user already exists
            cur.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
            if cur.fetchone():
                conn.close()
                auth_logger.warning(f"User creation failed - already exists: username={username}, email={email}")
                return None
            
            # Create user
            password_hash = generate_password_hash(password)
            cur.execute("""
                INSERT INTO users (username, email, password_hash, created_at, company_id, is_verified)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, email, password_hash, datetime.now().isoformat(), company_id, is_verified))
            
            user_id = cur.lastrowid
            conn.commit()
            conn.close()
            
            user = User(user_id, username, email, company_id=company_id)
            auth_logger.info(f"User created successfully: ID={user_id}, Username={username}, Company={company_id}, Verified={is_verified}")
            log_user_action("User Registration", user_id, f"Username: {username}, Company: {company_id}")
            database_logger.info(f"New user inserted: ID={user_id}, Table=users")
            
            return user
            
        except Exception as e:
            log_error(e, f"Failed to create user: username={username}, email={email}")
            return None
    
    @staticmethod
    @log_function_call(auth_logger, log_args=False)  # Don't log password
    def verify_password(username, password):
        """Verify user password"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
            row = cur.fetchone()
            conn.close()
            
            if row and check_password_hash(row[0], password):
                auth_logger.info(f"Password verification successful for user: {username}")
                log_user_action("Password Verification Success", None, f"Username: {username}")
                return True
            else:
                auth_logger.warning(f"Password verification failed for user: {username}")
                log_user_action("Password Verification Failed", None, f"Username: {username}")
                return False
                
        except Exception as e:
            log_error(e, f"Password verification error for user: {username}")
            return False