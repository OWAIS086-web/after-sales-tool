"""
User Data Source Permissions Model
Manages user-level access control for data sources
"""
from models.database import get_db_connection
from config.config_loader import get_config
from utils.logger import server_logger
from datetime import datetime
from typing import Dict, List, Optional

class UserPermissions:
    """Handle user data source permission operations"""

    @staticmethod
    def initialize_user_permissions(user_id: int, company_id: str = 'haval'):
        """
        Initialize permissions for new user based on config defaults

        Args:
            user_id: User ID to initialize permissions for
            company_id: Company ID (defaults to 'haval')
        """
        config = get_config()
        data_sources = config.get('data_sources', {})

        conn = get_db_connection()
        cur = conn.cursor()

        for source_id, source_config in data_sources.items():
            enabled = source_config.get('enabled_by_default', True)
            try:
                cur.execute('''
                    INSERT OR IGNORE INTO user_data_source_permissions
                    (user_id, data_source, enabled)
                    VALUES (?, ?, ?)
                ''', (user_id, source_id, enabled))
            except Exception as e:
                server_logger.error(f"Failed to init permission {source_id} for user {user_id}: {e}")

        conn.commit()
        conn.close()
        server_logger.info(f"Initialized permissions for user {user_id}: {list(data_sources.keys())}")

    @staticmethod
    def get_user_permissions(user_id: int) -> Dict[str, bool]:
        """
        Get all permissions for a user as dict {source_id: enabled}

        Args:
            user_id: User ID

        Returns:
            Dictionary mapping data source IDs to enabled status
        """
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT data_source, enabled
            FROM user_data_source_permissions
            WHERE user_id = ?
        ''', (user_id,))
        rows = cur.fetchall()
        conn.close()

        return {row['data_source']: bool(row['enabled']) for row in rows}

    @staticmethod
    def is_source_enabled(user_id: int, data_source: str) -> bool:
        """
        Check if specific data source is enabled for user

        Args:
            user_id: User ID
            data_source: Data source ID

        Returns:
            True if enabled, False if disabled
        """
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT enabled
            FROM user_data_source_permissions
            WHERE user_id = ? AND data_source = ?
        ''', (user_id, data_source))
        row = cur.fetchone()
        conn.close()

        # Default to True if no permission record (backward compatibility)
        return bool(row['enabled']) if row else True

    @staticmethod
    def set_user_permission(user_id: int, data_source: str, enabled: bool):
        """
        Set permission for user/source

        Args:
            user_id: User ID
            data_source: Data source ID
            enabled: Enable or disable
        """
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO user_data_source_permissions (user_id, data_source, enabled, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, data_source)
            DO UPDATE SET enabled = ?, updated_at = CURRENT_TIMESTAMP
        ''', (user_id, data_source, enabled, enabled))
        conn.commit()
        conn.close()
        server_logger.info(f"Set permission: user={user_id}, source={data_source}, enabled={enabled}")

    @staticmethod
    def get_enabled_sources(user_id: int) -> List[str]:
        """
        Get list of enabled data sources for user

        Args:
            user_id: User ID

        Returns:
            List of enabled data source IDs
        """
        permissions = UserPermissions.get_user_permissions(user_id)
        return [source for source, enabled in permissions.items() if enabled]

    @staticmethod
    def ensure_all_sources_initialized(user_id: int, company_id: str = 'haval'):
        """
        Ensure user has permission records for ALL configured data sources.
        This is for backward compatibility with existing users who may not have
        all sources initialized.

        Args:
            user_id: User ID
            company_id: Company ID (defaults to 'haval')
        """
        config = get_config()
        data_sources = config.get('data_sources', {})
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get existing permissions for this user
        cur.execute('''
            SELECT data_source FROM user_data_source_permissions
            WHERE user_id = ?
        ''', (user_id,))
        existing_sources = {row['data_source'] for row in cur.fetchall()}
        
        # Add missing sources with defaults
        for source_id, source_config in data_sources.items():
            if source_id not in existing_sources:
                enabled = source_config.get('enabled_by_default', True)
                try:
                    cur.execute('''
                        INSERT INTO user_data_source_permissions
                        (user_id, data_source, enabled)
                        VALUES (?, ?, ?)
                    ''', (user_id, source_id, enabled))
                    server_logger.info(f"Added missing permission for user {user_id}: {source_id}={enabled}")
                except Exception as e:
                    server_logger.error(f"Failed to add missing permission {source_id} for user {user_id}: {e}")
        
        conn.commit()
        conn.close()
