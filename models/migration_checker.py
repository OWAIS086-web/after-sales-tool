"""
Database Migration Checker
Verifies all required tables and columns exist before application starts
"""
import sqlite3
from models.database import get_db_connection
from utils.logger import server_logger, log_error


class MigrationChecker:
    """Check and verify database schema integrity"""
    
    REQUIRED_TABLES = {
        'users': ['id', 'username', 'email', 'password_hash', 'company_id'],
        'chat_history': ['id', 'user_id', 'session_id', 'mode', 'query', 'response'],
        'groups': ['id', 'name', 'creator_id', 'session_id', 'mode'],
        'group_members': ['id', 'group_id', 'user_id', 'email'],
        'group_messages': ['id', 'group_id', 'sender_id', 'message'],
        'user_data_source_permissions': ['id', 'user_id', 'data_source', 'enabled'],
        'whatsapp_messages': ['id', 'customer_name', 'message'],
        'posts': ['id', 'user_id', 'category'],
        'search_results': ['id', 'user_id', 'search_query'],
        'issues': ['id', 'platform_reference'],
        'facebook_issues': ['id', 'platform_reference'],
        'system_settings': ['key', 'value'],
    }
    
    REQUIRED_COLUMNS = {
        'chat_history': ['structured_data'],
        'users': ['company_id', 'is_verified', 'otp_code', 'otp_expiry', 'reset_otp', 'reset_otp_expiry', 'is_deleted', 'deleted_at', 'deleted_by'],
        'whatsapp_messages': ['company_id', 'sender'],
        'posts': ['company_id'],
        'search_results': ['company_id'],
    }
    
    REQUIRED_INDEXES = [
        ('idx_user_permissions_user_source', 'user_data_source_permissions'),
        ('idx_email_blacklist_email', 'email_blacklist'),
        ('idx_users_is_deleted', 'users'),
        ('idx_groups_creator', 'groups'),
        ('idx_group_members_group', 'group_members'),
        ('idx_group_messages_group', 'group_messages'),
    ]
    
    @staticmethod
    def check_all():
        """Run all migration checks"""
        server_logger.info("🔍 Starting database migration checks...")
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Check tables
            missing_tables = MigrationChecker._check_tables(cur)
            
            # Check columns
            missing_columns = MigrationChecker._check_columns(cur)
            
            # Check indexes
            missing_indexes = MigrationChecker._check_indexes(cur)
            
            conn.close()
            
            # Report results
            if missing_tables or missing_columns or missing_indexes:
                server_logger.warning("⚠️  Database schema issues detected:")
                if missing_tables:
                    server_logger.warning(f"   Missing tables: {missing_tables}")
                if missing_columns:
                    server_logger.warning(f"   Missing columns: {missing_columns}")
                if missing_indexes:
                    server_logger.warning(f"   Missing indexes: {missing_indexes}")
                return False
            else:
                server_logger.info("✅ All database tables and columns verified successfully")
                return True
                
        except Exception as e:
            log_error(e, "Database migration check failed")
            return False
    
    @staticmethod
    def _check_tables(cur):
        """Check if all required tables exist"""
        missing = []
        
        for table_name, required_cols in MigrationChecker.REQUIRED_TABLES.items():
            try:
                cur.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
                server_logger.debug(f"✓ Table '{table_name}' exists")
            except sqlite3.OperationalError:
                missing.append(table_name)
                server_logger.warning(f"✗ Table '{table_name}' missing")
        
        return missing
    
    @staticmethod
    def _check_columns(cur):
        """Check if all required columns exist in tables"""
        missing = []
        
        for table_name, required_cols in MigrationChecker.REQUIRED_COLUMNS.items():
            try:
                cur.execute(f"PRAGMA table_info({table_name})")
                existing_cols = {row[1] for row in cur.fetchall()}
                
                for col in required_cols:
                    if col not in existing_cols:
                        missing.append(f"{table_name}.{col}")
                        server_logger.warning(f"✗ Column '{table_name}.{col}' missing")
                    else:
                        server_logger.debug(f"✓ Column '{table_name}.{col}' exists")
                        
            except sqlite3.OperationalError as e:
                server_logger.warning(f"✗ Cannot check columns for table '{table_name}': {e}")
        
        return missing
    
    @staticmethod
    def _check_indexes(cur):
        """Check if all required indexes exist"""
        missing = []
        
        try:
            cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
            existing_indexes = {row[0] for row in cur.fetchall()}
            
            for index_name, table_name in MigrationChecker.REQUIRED_INDEXES:
                if index_name not in existing_indexes:
                    missing.append(index_name)
                    server_logger.debug(f"⚠️  Index '{index_name}' on table '{table_name}' missing (non-critical)")
                else:
                    server_logger.debug(f"✓ Index '{index_name}' exists")
                    
        except sqlite3.OperationalError as e:
            server_logger.warning(f"Cannot check indexes: {e}")
        
        return missing
    
    @staticmethod
    def verify_group_chat_tables():
        """Specifically verify group chat tables exist"""
        server_logger.info("🔍 Verifying group chat tables...")

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            group_tables = [
                'groups',
                'group_members',
                'group_messages'
            ]

            all_exist = True
            for table in group_tables:
                try:
                    cur.execute(f"SELECT 1 FROM {table} LIMIT 1")
                    server_logger.info(f"✓ Group chat table '{table}' verified")
                except sqlite3.OperationalError:
                    server_logger.error(f"✗ Group chat table '{table}' NOT FOUND")
                    all_exist = False

            conn.close()
            return all_exist

        except Exception as e:
            log_error(e, "Failed to verify group chat tables")
            return False
    
    @staticmethod
    def verify_chat_history_columns():
        """Verify chat_history table has all required columns"""
        server_logger.info("🔍 Verifying chat_history columns...")
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("PRAGMA table_info(chat_history)")
            columns = {row[1] for row in cur.fetchall()}
            
            required = ['id', 'user_id', 'session_id', 'mode', 'query', 'response', 'structured_data', 'timestamp']
            missing = [col for col in required if col not in columns]
            
            if missing:
                server_logger.error(f"✗ chat_history missing columns: {missing}")
                conn.close()
                return False
            
            server_logger.info("✓ chat_history table has all required columns")
            conn.close()
            return True
            
        except Exception as e:
            log_error(e, "Failed to verify chat_history columns")
            return False
    
    @staticmethod
    def verify_users_table():
        """Verify users table has all required columns"""
        server_logger.info("🔍 Verifying users table...")
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("PRAGMA table_info(users)")
            columns = {row[1] for row in cur.fetchall()}
            
            required = ['id', 'username', 'email', 'password_hash', 'company_id', 'created_at']
            missing = [col for col in required if col not in columns]
            
            if missing:
                server_logger.error(f"✗ users table missing columns: {missing}")
                conn.close()
                return False
            
            server_logger.info("✓ users table has all required columns")
            conn.close()
            return True
            
        except Exception as e:
            log_error(e, "Failed to verify users table")
            return False
    
    @staticmethod
    def verify_permissions_table():
        """Verify user_data_source_permissions table exists"""
        server_logger.info("🔍 Verifying permissions table...")
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT 1 FROM user_data_source_permissions LIMIT 1")
            server_logger.info("✓ user_data_source_permissions table verified")
            conn.close()
            return True
            
        except sqlite3.OperationalError:
            server_logger.error("✗ user_data_source_permissions table NOT FOUND")
            conn.close()
            return False
        except Exception as e:
            log_error(e, "Failed to verify permissions table")
            return False
    
    @staticmethod
    def get_migration_status():
        """Get detailed migration status"""
        status = {
            'tables_ok': True,
            'columns_ok': True,
            'indexes_ok': True,
            'group_chat_ok': True,
            'chat_history_ok': True,
            'users_ok': True,
            'permissions_ok': True,
            'issues': []
        }
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Check tables
            missing_tables = MigrationChecker._check_tables(cur)
            if missing_tables:
                status['tables_ok'] = False
                status['issues'].append(f"Missing tables: {missing_tables}")
            
            # Check columns
            missing_columns = MigrationChecker._check_columns(cur)
            if missing_columns:
                status['columns_ok'] = False
                status['issues'].append(f"Missing columns: {missing_columns}")
            
            # Check indexes
            missing_indexes = MigrationChecker._check_indexes(cur)
            if missing_indexes:
                status['indexes_ok'] = False
                status['issues'].append(f"Missing indexes: {missing_indexes}")
            
            conn.close()
            
            # Check specific components
            status['group_chat_ok'] = MigrationChecker.verify_group_chat_tables()
            status['chat_history_ok'] = MigrationChecker.verify_chat_history_columns()
            status['users_ok'] = MigrationChecker.verify_users_table()
            status['permissions_ok'] = MigrationChecker.verify_permissions_table()
            
        except Exception as e:
            log_error(e, "Failed to get migration status")
            status['issues'].append(str(e))
        
        return status
