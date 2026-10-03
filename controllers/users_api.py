"""
Users API Controller
Provides endpoints for user-related operations
"""
from flask import jsonify, request
from flask_login import login_required, current_user
from models.database import get_db_connection
from utils.logger import chat_logger, log_function_call, log_error


@login_required
@log_function_call(chat_logger)
def get_users_list():
    """
    Get list of all users (for group chat invitations).
    
    Query params:
        - search: Optional search query (username or email)
        - limit: Max users to return (default: 50)
        - exclude_current: Exclude current user (default: true)
    
    Response:
        - users: List of user objects with id, username, email
    """
    try:
        search_query = request.args.get('search', '').strip().lower()
        limit = min(int(request.args.get('limit', 50)), 200)
        exclude_current = request.args.get('exclude_current', 'true').lower() == 'true'
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build query
        if search_query:
            cur.execute("""
                SELECT id, username, email, company_id
                FROM users
                WHERE (username LIKE ? OR email LIKE ?)
                AND is_active = TRUE
                AND is_deleted = FALSE
                ORDER BY username ASC
                LIMIT ?
            """, (f'%{search_query}%', f'%{search_query}%', limit))
        else:
            cur.execute("""
                SELECT id, username, email, company_id
                FROM users
                WHERE is_active = TRUE
                AND is_deleted = FALSE
                ORDER BY username ASC
                LIMIT ?
            """, (limit,))
        
        rows = cur.fetchall()
        conn.close()
        
        users = []
        for row in rows:
            user_id = row[0]
            
            # Exclude current user if requested
            if exclude_current and user_id == current_user.id:
                continue
            
            users.append({
                "id": user_id,
                "username": row[1],
                "email": row[2],
                "company_id": row[3]
            })
        
        chat_logger.info(f"Retrieved {len(users)} users for group chat invitation")
        return jsonify({"success": True, "users": users}), 200
        
    except Exception as e:
        log_error(e, "Failed to get users list")
        return jsonify({"error": "Failed to get users list"}), 500


@login_required
@log_function_call(chat_logger)
def get_user_by_id():
    """
    Get user details by ID.
    
    Query params:
        - user_id: User ID to retrieve
    
    Response:
        - user: User object with id, username, email, company_id
    """
    try:
        user_id = request.args.get('user_id', type=int)
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, username, email, company_id
            FROM users
            WHERE id = ? AND is_active = TRUE AND is_deleted = FALSE
        """, (user_id,))
        
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return jsonify({"error": "User not found"}), 404
        
        user = {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "company_id": row[3]
        }
        
        return jsonify(user), 200
        
    except Exception as e:
        log_error(e, "Failed to get user by ID")
        return jsonify({"error": "Failed to get user"}), 500


@login_required
@log_function_call(chat_logger)
def search_users():
    """
    Search for users by username or email.
    
    Query params:
        - q: Search query (username or email)
        - limit: Max results (default: 20)
    
    Response:
        - results: List of matching users
    """
    try:
        query = request.args.get('q', '').strip().lower()
        limit = min(int(request.args.get('limit', 20)), 100)
        
        if len(query) < 2:
            return jsonify({"results": []}), 200
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, username, email, company_id
            FROM users
            WHERE (username LIKE ? OR email LIKE ?)
            AND is_active = TRUE
            AND is_deleted = FALSE
            AND id != ?
            ORDER BY username ASC
            LIMIT ?
        """, (f'%{query}%', f'%{query}%', current_user.id, limit))
        
        rows = cur.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "company_id": row[3]
            })
        
        chat_logger.info(f"User search: query='{query}', results={len(results)}")
        return jsonify({"results": results}), 200
        
    except Exception as e:
        log_error(e, "Failed to search users")
        return jsonify({"error": "Failed to search users"}), 500
