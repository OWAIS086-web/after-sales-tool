"""
Data Source Permissions
Manages user access to individual data sources via user table columns
"""
from models.database import get_db_connection
from utils.logger import server_logger


class DataSourcePermissions:
    """Manage data source permissions for users"""
    
    # All available data sources
    ALL_SOURCES = [
        'pakwheels',
        'reddit',
        'whatsapp',
        'cross_platform',
        'dealership',
        'finance',
        'facebook',
        'supplychain',
        'insights'
    ]
    
    # Column name mapping
    COLUMN_PREFIX = 'perm_'
    
    @staticmethod
    def get_column_name(source):
        """Get database column name for a source"""
        return f"{DataSourcePermissions.COLUMN_PREFIX}{source}"
    
    @staticmethod
    def get_user_permissions(user_id):
        """Get all permissions for a user as dict {source: bool}"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Get user record
            columns = ', '.join([DataSourcePermissions.get_column_name(s) for s in DataSourcePermissions.ALL_SOURCES])
            cur.execute(f"SELECT {columns} FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            conn.close()
            
            if not row:
                server_logger.warning(f"User {user_id} not found")
                return {}
            
            # Build permissions dict
            permissions = {}
            for i, source in enumerate(DataSourcePermissions.ALL_SOURCES):
                permissions[source] = bool(row[i])
            
            return permissions
        
        except Exception as e:
            server_logger.error(f"Error getting permissions for user {user_id}: {e}")
            conn.close()
            return {}
    
    @staticmethod
    def is_source_enabled(user_id, source):
        """Check if user has access to a data source"""
        if source not in DataSourcePermissions.ALL_SOURCES:
            server_logger.warning(f"Unknown data source: {source}")
            return False
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            column = DataSourcePermissions.get_column_name(source)
            cur.execute(f"SELECT {column} FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            conn.close()
            
            if not row:
                server_logger.warning(f"User {user_id} not found")
                return False
            
            return bool(row[0])
        
        except Exception as e:
            server_logger.error(f"Error checking permission for user {user_id}, source {source}: {e}")
            conn.close()
            return False
    
    @staticmethod
    def set_source_permission(user_id, source, enabled):
        """Set permission for a user/source"""
        if source not in DataSourcePermissions.ALL_SOURCES:
            server_logger.error(f"Unknown data source: {source}")
            return False
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            column = DataSourcePermissions.get_column_name(source)
            cur.execute(f"UPDATE users SET {column} = ? WHERE id = ?", (enabled, user_id))
            conn.commit()
            conn.close()
            
            server_logger.info(f"Set permission for user {user_id}, source {source}: {enabled}")
            return True
        
        except Exception as e:
            server_logger.error(f"Error setting permission for user {user_id}, source {source}: {e}")
            conn.rollback()
            conn.close()
            return False
    
    @staticmethod
    def get_enabled_sources(user_id):
        """Get list of enabled data sources for user"""
        permissions = DataSourcePermissions.get_user_permissions(user_id)
        return [source for source, enabled in permissions.items() if enabled]
    
    @staticmethod
    def get_disabled_sources(user_id):
        """Get list of disabled data sources for user"""
        permissions = DataSourcePermissions.get_user_permissions(user_id)
        return [source for source, enabled in permissions.items() if not enabled]
    
    @staticmethod
    def enable_all_sources(user_id):
        """Enable all data sources for a user"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Build SET clause for all sources
            set_clause = ', '.join([f"{DataSourcePermissions.get_column_name(s)} = 1" for s in DataSourcePermissions.ALL_SOURCES])
            cur.execute(f"UPDATE users SET {set_clause} WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            
            server_logger.info(f"Enabled all data sources for user {user_id}")
            return True
        
        except Exception as e:
            server_logger.error(f"Error enabling all sources for user {user_id}: {e}")
            conn.rollback()
            conn.close()
            return False
    
    @staticmethod
    def disable_all_sources(user_id):
        """Disable all data sources for a user"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Build SET clause for all sources
            set_clause = ', '.join([f"{DataSourcePermissions.get_column_name(s)} = 0" for s in DataSourcePermissions.ALL_SOURCES])
            cur.execute(f"UPDATE users SET {set_clause} WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            
            server_logger.info(f"Disabled all data sources for user {user_id}")
            return True
        
        except Exception as e:
            server_logger.error(f"Error disabling all sources for user {user_id}: {e}")
            conn.rollback()
            conn.close()
            return False
    
    @staticmethod
    def get_all_sources():
        """Get list of all available data sources"""
        return DataSourcePermissions.ALL_SOURCES
