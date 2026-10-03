"""
Admin Users Controller
Manages user permissions and deletion for admin users
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from scheduler.decorators import admin_required
from models.database import get_db_connection
from config.config_loader import get_config
from utils.logger import LoggerManager

logger = LoggerManager.get_logger('admin_users')

bp = Blueprint('admin_users', __name__, url_prefix='/admin')

@bp.route('/users')
@login_required
@admin_required
def list_users():
    """Get list of all users for admin table"""
    from scheduler.decorators import is_admin_user
    from models.datasource_permissions import DataSourcePermissions

    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get ALL users
    cur.execute('''
        SELECT id, username, email, created_at, last_login, is_deleted, company_id,
               perm_pakwheels, perm_reddit, perm_whatsapp, perm_cross_platform,
               perm_dealership, perm_finance, perm_facebook, perm_supplychain, perm_insights,
               perm_lucid, perm_reddit_lucid
        FROM users
        WHERE company_id = ?
        ORDER BY created_at DESC
    ''', (current_user.company_id or 'haval',))
    users = cur.fetchall()
    conn.close()

    # Process all users
    result = []
    for user in users:
        # Check if user is admin
        class UserObj:
            def __init__(self, email, username=''):
                self.email = email
                self.username = username
                self.is_authenticated = True

        is_admin = is_admin_user(UserObj(user['email'], user['username']))
        
        # Get permissions for all users
        permissions = {
            'pakwheels': bool(user['perm_pakwheels']),
            'reddit': bool(user['perm_reddit']),
            'whatsapp': bool(user['perm_whatsapp']),
            'cross_platform': bool(user['perm_cross_platform']),
            'dealership': bool(user['perm_dealership']),
            'finance': bool(user['perm_finance']),
            'facebook': bool(user['perm_facebook']),
            'supplychain': bool(user['perm_supplychain']),
            'insights': bool(user['perm_insights']),
            'lucid': bool(user['perm_lucid']) if 'perm_lucid' in user.keys() else True,
            'reddit_lucid': bool(user['perm_reddit_lucid']) if 'perm_reddit_lucid' in user.keys() else True,
        }
        
        result.append({
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'created_at': user['created_at'],
            'last_login': user['last_login'],
            'is_admin': is_admin,
            'is_deleted': bool(user['is_deleted']),
            'company_id': user['company_id'],
            'permissions': permissions
        })

    logger.info(f"Admin {current_user.username} loaded {len(result)} users")
    return jsonify({'success': True, 'users': result})

@bp.route('/users/data-sources')
@login_required
@admin_required
def get_data_sources():
    """Get configured data sources from config - filtered by company"""
    config = get_config()
    data_sources = config.get('data_sources', {})
    
    # Get current user's company
    user_company = current_user.company_id or 'haval'

    # Convert to list with sorted order
    sources_list = []
    for source_id, source_config in data_sources.items():
        # Filter data sources based on company
        if user_company == 'lucid':
            # Lucid users only see: dealership (DMS), lucid, reddit_lucid, and insights
            if source_id not in ['dealership', 'lucid', 'reddit_lucid', 'insights']:
                continue
        
        sources_list.append({
            'id': source_id,
            'display_name': source_config.get('display_name', source_id),
            'description': source_config.get('description', ''),
            'is_demo': source_config.get('is_demo', False)
        })

    return jsonify({'success': True, 'data_sources': sources_list})

@bp.route('/users/<int:user_id>/permissions', methods=['POST'])
@login_required
@admin_required
def update_permission(user_id):
    """Update permission for user/source"""
    data = request.get_json() or {}
    data_source = data.get('data_source')
    enabled = data.get('enabled', True)

    if not data_source:
        return jsonify({'success': False, 'error': 'data_source required'}), 400

    # Check if user is admin
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT email, username FROM users WHERE id = ?', (user_id,))
    user = cur.fetchone()
    conn.close()

    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    from scheduler.decorators import is_admin_user
    class UserObj:
        def __init__(self, email, username=''):
            self.email = email
            self.username = username
            self.is_authenticated = True

    # Extract values from Row object
    user_email = user['email']
    user_username = user['username'] or ''

    if is_admin_user(UserObj(user_email, user_username)):
        return jsonify({'success': False, 'error': 'Cannot modify admin permissions'}), 403

    # Update permission using new system
    from models.datasource_permissions import DataSourcePermissions
    DataSourcePermissions.set_source_permission(user_id, data_source, enabled)
    logger.info(f"Admin {current_user.username} set {data_source}={enabled} for user_id={user_id}")

    return jsonify({'success': True})

@bp.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """Hard delete user and all associated data"""
    # Prevent self-deletion
    if user_id == current_user.id:
        return jsonify({'success': False, 'error': 'Cannot delete your own account'}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    # Get user info before deletion
    cur.execute('SELECT email, username FROM users WHERE id = ?', (user_id,))
    user = cur.fetchone()

    if not user:
        conn.close()
        return jsonify({'success': False, 'error': 'User not found'}), 404

    try:
        # Delete user permissions
        cur.execute('DELETE FROM user_data_source_permissions WHERE user_id = ?', (user_id,))
        
        # Delete user sessions
        cur.execute('DELETE FROM user_sessions WHERE user_id = ?', (user_id,))
        
        # Delete chat history
        cur.execute('DELETE FROM chat_history WHERE user_id = ?', (user_id,))
        
        # Delete group memberships
        cur.execute('DELETE FROM group_members WHERE user_id = ?', (user_id,))
        
        # Delete groups created by user
        cur.execute('DELETE FROM groups WHERE creator_id = ?', (user_id,))
        
        # Delete API usage records
        cur.execute('DELETE FROM api_usage WHERE user_id = ?', (user_id,))
        
        # Delete posts
        cur.execute('DELETE FROM posts WHERE user_id = ?', (user_id,))
        
        # Delete search results
        cur.execute('DELETE FROM search_results WHERE user_id = ?', (user_id,))
        
        # Finally, delete the user
        cur.execute('DELETE FROM users WHERE id = ?', (user_id,))
        
        conn.commit()
        conn.close()

        logger.warning(f"Admin {current_user.username} permanently deleted user {user['username']} ({user['email']}) and all associated data.")

        return jsonify({'success': True, 'message': f"User {user['username']} and all associated data permanently deleted. Email is now available for new registration."})
    
    except Exception as e:
        conn.rollback()
        conn.close()
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        return jsonify({'success': False, 'error': f'Failed to delete user: {str(e)}'}), 500


@bp.route('/users/<email>/blacklist', methods=['DELETE'])
@login_required
@admin_required
def remove_from_blacklist(email):
    """Remove email from blacklist to allow re-registration"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if email is in blacklist
        cur.execute('SELECT id FROM email_blacklist WHERE email = ?', (email,))
        if not cur.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Email not found in blacklist'}), 404
        
        # Remove from blacklist
        cur.execute('DELETE FROM email_blacklist WHERE email = ?', (email,))
        conn.commit()
        conn.close()
        
        logger.info(f"Admin {current_user.username} removed {email} from blacklist")
        return jsonify({'success': True, 'message': f"Email {email} removed from blacklist and is now available for registration"})
    
    except Exception as e:
        logger.error(f"Error removing email from blacklist: {str(e)}")
        return jsonify({'success': False, 'error': f'Failed to remove email: {str(e)}'}), 500
