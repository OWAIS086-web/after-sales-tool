"""
Permission Mode System
Defines user roles and permission levels for role-based access control
"""
from enum import Enum
from utils.logger import server_logger


class PermissionMode(Enum):
    """User permission modes/roles"""
    
    # Basic user - can only access assigned data sources
    USER = 'user'
    
    # Analyst - can access multiple data sources and view analytics
    ANALYST = 'analyst'
    
    # Manager - can manage users and view reports
    MANAGER = 'manager'
    
    # Admin - full system access
    ADMIN = 'admin'
    
    # Super Admin - can manage admins and system settings
    SUPER_ADMIN = 'super_admin'


class PermissionModeManager:
    """Manage user permission modes and access control"""
    
    # Permission hierarchy (higher number = more permissions)
    HIERARCHY = {
        PermissionMode.USER.value: 1,
        PermissionMode.ANALYST.value: 2,
        PermissionMode.MANAGER.value: 3,
        PermissionMode.ADMIN.value: 4,
        PermissionMode.SUPER_ADMIN.value: 5,
    }
    
    # Capabilities per mode
    CAPABILITIES = {
        PermissionMode.USER.value: {
            'view_data': True,
            'view_analytics': False,
            'manage_permissions': False,
            'manage_users': False,
            'manage_system': False,
            'view_reports': False,
            'export_data': False,
        },
        PermissionMode.ANALYST.value: {
            'view_data': True,
            'view_analytics': True,
            'manage_permissions': False,
            'manage_users': False,
            'manage_system': False,
            'view_reports': True,
            'export_data': True,
        },
        PermissionMode.MANAGER.value: {
            'view_data': True,
            'view_analytics': True,
            'manage_permissions': True,
            'manage_users': True,
            'manage_system': False,
            'view_reports': True,
            'export_data': True,
        },
        PermissionMode.ADMIN.value: {
            'view_data': True,
            'view_analytics': True,
            'manage_permissions': True,
            'manage_users': True,
            'manage_system': True,
            'view_reports': True,
            'export_data': True,
        },
        PermissionMode.SUPER_ADMIN.value: {
            'view_data': True,
            'view_analytics': True,
            'manage_permissions': True,
            'manage_users': True,
            'manage_system': True,
            'view_reports': True,
            'export_data': True,
        },
    }
    
    # Data sources accessible per mode
    DATA_SOURCE_ACCESS = {
        PermissionMode.USER.value: ['pakwheels', 'reddit', 'whatsapp', 'lucid', 'cross_platform'],
        PermissionMode.ANALYST.value: ['pakwheels', 'reddit', 'whatsapp', 'lucid', 'cross_platform', 'dealership'],
        PermissionMode.MANAGER.value: ['pakwheels', 'reddit', 'whatsapp', 'lucid', 'cross_platform', 'dealership', 'finance'],
        PermissionMode.ADMIN.value: ['pakwheels', 'reddit', 'whatsapp', 'lucid', 'cross_platform', 'dealership', 'finance', 'facebook', 'supplychain'],
        PermissionMode.SUPER_ADMIN.value: ['pakwheels', 'reddit', 'whatsapp', 'lucid', 'cross_platform', 'dealership', 'finance', 'facebook', 'supplychain', 'insights'],
    }
    
    @staticmethod
    def is_valid_mode(mode):
        """Check if mode is valid"""
        return mode in [m.value for m in PermissionMode]
    
    @staticmethod
    def get_hierarchy_level(mode):
        """Get hierarchy level for a mode"""
        return PermissionModeManager.HIERARCHY.get(mode, 0)
    
    @staticmethod
    def has_capability(mode, capability):
        """Check if mode has a specific capability"""
        capabilities = PermissionModeManager.CAPABILITIES.get(mode, {})
        return capabilities.get(capability, False)
    
    @staticmethod
    def can_access_source(mode, source):
        """Check if mode can access a data source"""
        sources = PermissionModeManager.DATA_SOURCE_ACCESS.get(mode, [])
        return source in sources
    
    @staticmethod
    def get_accessible_sources(mode):
        """Get list of accessible sources for a mode"""
        return PermissionModeManager.DATA_SOURCE_ACCESS.get(mode, [])
    
    @staticmethod
    def get_capabilities(mode):
        """Get all capabilities for a mode"""
        return PermissionModeManager.CAPABILITIES.get(mode, {})
    
    @staticmethod
    def is_higher_or_equal(mode1, mode2):
        """Check if mode1 has equal or higher permissions than mode2"""
        level1 = PermissionModeManager.get_hierarchy_level(mode1)
        level2 = PermissionModeManager.get_hierarchy_level(mode2)
        return level1 >= level2
    
    @staticmethod
    def is_higher(mode1, mode2):
        """Check if mode1 has higher permissions than mode2"""
        level1 = PermissionModeManager.get_hierarchy_level(mode1)
        level2 = PermissionModeManager.get_hierarchy_level(mode2)
        return level1 > level2
    
    @staticmethod
    def get_all_modes():
        """Get all available modes"""
        return [m.value for m in PermissionMode]
    
    @staticmethod
    def get_mode_description(mode):
        """Get human-readable description of a mode"""
        descriptions = {
            PermissionMode.USER.value: 'Regular User - Access to assigned data sources',
            PermissionMode.ANALYST.value: 'Analyst - Can view analytics and export data',
            PermissionMode.MANAGER.value: 'Manager - Can manage users and permissions',
            PermissionMode.ADMIN.value: 'Administrator - Full system access',
            PermissionMode.SUPER_ADMIN.value: 'Super Admin - Can manage admins and system',
        }
        return descriptions.get(mode, 'Unknown')
    
    @staticmethod
    def log_mode_change(user_id, old_mode, new_mode, changed_by):
        """Log permission mode change"""
        server_logger.warning(
            f"Permission mode changed for user {user_id}: "
            f"{old_mode} → {new_mode} (by {changed_by})"
        )


# Decorators for permission checking

def require_permission_mode(required_mode):
    """Decorator to require minimum permission mode"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            from flask_login import current_user
            from flask import jsonify
            
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required'}), 401
            
            user_mode = getattr(current_user, 'permission_mode', 'user')
            
            if not PermissionModeManager.is_higher_or_equal(user_mode, required_mode):
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator


def require_capability(capability):
    """Decorator to require specific capability"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            from flask_login import current_user
            from flask import jsonify
            
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required'}), 401
            
            user_mode = getattr(current_user, 'permission_mode', 'user')
            
            if not PermissionModeManager.has_capability(user_mode, capability):
                return jsonify({'error': 'Insufficient permissions for this operation'}), 403
            
            return f(*args, **kwargs)
        
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator
