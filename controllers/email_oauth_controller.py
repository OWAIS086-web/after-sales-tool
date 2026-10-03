"""
Email OAuth Controller
Handles Gmail OAuth 2.0 authentication endpoints
"""

import os
from functools import wraps

from flask import Blueprint, jsonify, redirect, request, session, url_for
from flask_login import current_user

from ai.email.gmail_oauth_service import GmailOAuthService
from models.email_tracking import EmailTrackingDB
from utils.logger import log_error

# Create blueprint
email_oauth_bp = Blueprint('email_oauth', __name__, url_prefix='/auth/gmail')


# Initialize services (will be configured from environment)
def get_oauth_service():
    """Get Gmail OAuth service instance"""
    try:
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:10000/auth/gmail/callback')
        
        if not client_id or not client_secret:
            raise ValueError("Gmail OAuth credentials not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env")
        
        return GmailOAuthService(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri
        )
    except Exception as e:
        log_error(f"Failed to initialize OAuth service: {e}")
        raise


def get_tracking_db():
    """Get email tracking database instance"""
    return EmailTrackingDB()


def login_required(f):
    """Decorator to require user login - uses Flask-Login's current_user"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function


@email_oauth_bp.route('/status', methods=['GET'])
def oauth_status():
    """
    Check OAuth configuration status
    
    Returns:
        JSON response with OAuth status
    """
    try:
        # Check if OAuth is configured
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        
        configured = bool(client_id and client_secret)
        
        # If user is logged in, check authentication status
        authenticated = False
        user_email = None
        
        if current_user.is_authenticated and configured:
            try:
                oauth_service = get_oauth_service()
                user_id = str(current_user.id)
                authenticated = oauth_service.is_authenticated(user_id)
                
                if authenticated:
                    user_email = oauth_service.get_user_email(user_id)
                    
            except Exception as e:
                log_error(f"Error checking authentication status: {e}")
        
        return jsonify({
            "success": True,
            "configured": configured,
            "authenticated": authenticated,
            "email_address": user_email,
            "message": "OAuth status retrieved successfully"
        })
        
    except Exception as e:
        log_error(f"Error getting OAuth status: {e}")
        return jsonify({
            "success": False,
            "configured": False,
            "error": str(e),
            "message": "Failed to get OAuth status"
        }), 500


@email_oauth_bp.route('/connect', methods=['GET'])
@login_required
def connect_gmail():
    """
    Initiate Gmail OAuth flow
    
    Returns:
        Redirect to Google OAuth authorization page
    """
    try:
        user_id = str(current_user.id)
        print(f"[Email OAuth Controller] 🔐 Starting OAuth flow for user: {user_id}")
        
        # Get OAuth service
        oauth_service = get_oauth_service()
        
        # Generate authorization URL
        auth_url, state = oauth_service.get_authorization_url(user_id)
        
        # Store state in session for verification
        session['oauth_state'] = state
        
        print(f"[Email OAuth Controller] ✅ Generated OAuth URL for user: {user_id}")
        
        # Redirect to Google
        return redirect(auth_url)
        
    except ValueError as ve:
        # OAuth not configured
        print(f"[Email OAuth Controller] ⚙️ OAuth not configured: {ve}")
        return jsonify({
            "success": False,
            "error": "oauth_not_configured",
            "message": str(ve)
        }), 400
        
    except Exception as e:
        log_error(f"Error initiating OAuth: {e}")
        print(f"[Email OAuth Controller] ❌ OAuth initiation failed: {e}")
        return jsonify({
            "success": False,
            "error": "oauth_initiation_failed",
            "message": "Failed to initiate Gmail authentication"
        }), 500


@email_oauth_bp.route('/callback', methods=['GET'])
def oauth_callback():
    """
    Handle OAuth callback from Google
    
    Returns:
        Redirect to email dashboard with success/error message
    """
    try:
        print("[Email OAuth Controller] 📥 Processing OAuth callback")
        
        # Get authorization code
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        # Check for errors
        if error:
            print(f"[Email OAuth Controller] ❌ OAuth error: {error}")
            return redirect('/?email_oauth_error=' + error)
        
        if not code:
            print("[Email OAuth Controller] ❌ No authorization code received")
            return redirect('/?email_oauth_error=no_code')
        
        # Verify state (user_id)
        stored_state = session.get('oauth_state')
        user_id = session.get('user_id', state)
        
        print(f"[Email OAuth Controller] 🔍 Processing callback for user: {user_id}")
        
        # Get OAuth service
        oauth_service = get_oauth_service()
        
        # Exchange code for tokens
        success = oauth_service.handle_oauth_callback(code, user_id)
        
        if not success:
            print("[Email OAuth Controller] ❌ Token exchange failed")
            return redirect('/?email_oauth_error=token_exchange_failed')
        
        # Get user's email address
        user_email = oauth_service.get_user_email(user_id)
        
        # Store connection in database
        try:
            db = get_tracking_db()
            db.create_oauth_connection(user_id, user_email)
        except Exception as db_error:
            log_error(f"Database error during OAuth callback: {db_error}")
            print(f"[Email OAuth Controller] ⚠️ Database error (continuing): {db_error}")
        
        print(f"[Email OAuth Controller] ✅ Successfully connected Gmail for user: {user_id} ({user_email})")
        
        # Redirect to main chat page with email mode active
        return redirect('/?email_oauth_success=true&email=' + (user_email or '') + '&mode=email')
        
    except Exception as e:
        log_error(f"Error handling OAuth callback: {e}")
        print(f"[Email OAuth Controller] ❌ Callback error: {e}")
        return redirect('/?email_oauth_error=callback_failed')


@email_oauth_bp.route('/disconnect', methods=['POST'])
@login_required
def disconnect_gmail():
    """
    Disconnect Gmail and revoke OAuth access
    
    Returns:
        JSON response with success status
    """
    try:
        user_id = str(current_user.id)
        print(f"[Email OAuth Controller] 🔌 Disconnecting Gmail for user: {user_id}")
        
        # Get OAuth service
        oauth_service = get_oauth_service()
        
        # Revoke access
        success = oauth_service.revoke_access(user_id)
        
        if success:
            # Remove from database
            try:
                db = get_tracking_db()
                db.remove_oauth_connection(user_id)
            except Exception as db_error:
                log_error(f"Database error during disconnect: {db_error}")
                print(f"[Email OAuth Controller] ⚠️ Database error (continuing): {db_error}")
            
            print(f"[Email OAuth Controller] ✅ Disconnected Gmail for user: {user_id}")
            
            return jsonify({
                "success": True,
                "message": "Gmail disconnected successfully"
            })
        else:
            print(f"[Email OAuth Controller] ❌ Failed to disconnect Gmail for user: {user_id}")
            return jsonify({
                "success": False,
                "error": "Failed to revoke OAuth access"
            }), 500
            
    except Exception as e:
        log_error(f"Error disconnecting Gmail: {e}")
        print(f"[Email OAuth Controller] ❌ Disconnect error: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to disconnect Gmail"
        }), 500


@email_oauth_bp.route('/status', methods=['GET'])
@login_required
def get_connection_status():
    """
    Get Gmail connection status
    
    Returns:
        JSON response with connection details
    """
    try:
        user_id = str(current_user.id)
        
        # Get OAuth service
        oauth_service = get_oauth_service()
        
        # Check authentication
        is_authenticated = oauth_service.is_authenticated(user_id)
        
        if not is_authenticated:
            return jsonify({
                "connected": False,
                "user_id": user_id
            })
        
        # Get connection details from database
        db = get_tracking_db()
        connection = db.get_oauth_connection(user_id)
        
        # Get user email
        user_email = oauth_service.get_user_email(user_id)
        
        return jsonify({
            "connected": True,
            "user_id": user_id,
            "email_address": user_email,
            "connected_at": connection.get('connected_at') if connection else None,
            "last_sync_at": connection.get('last_sync_at') if connection else None,
            "total_emails_indexed": connection.get('total_emails_indexed', 0) if connection else 0
        })
        
    except Exception as e:
        log_error(f"Error getting connection status: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@email_oauth_bp.route('/test', methods=['GET'])
@login_required
def test_connection():
    """
    Test Gmail API connection
    
    Returns:
        JSON response with test results
    """
    try:
        user_id = str(current_user.id)
        
        # Get OAuth service
        oauth_service = get_oauth_service()
        
        # Get Gmail service
        gmail_service = oauth_service.get_gmail_service(user_id)
        
        if not gmail_service:
            return jsonify({
                "success": False,
                "error": "Not authenticated or token expired"
            }), 401
        
        # Test API call - get profile
        profile = gmail_service.users().getProfile(userId='me').execute()
        
        return jsonify({
            "success": True,
            "message": "Gmail API connection successful",
            "email": profile.get('emailAddress'),
            "total_messages": profile.get('messagesTotal'),
            "total_threads": profile.get('threadsTotal')
        })
        
    except Exception as e:
        log_error(f"Error testing connection: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Gmail API connection test failed"
        }), 500