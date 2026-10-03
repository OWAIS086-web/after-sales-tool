"""
Email Management Controller
Handles email indexing, counting, and management operations
"""

import os
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, jsonify, request, session
from flask_login import current_user

from ai.email.email_fetcher import CleanEmailFetcher
from ai.email.email_indexer import EmailIndexer
from ai.email.email_rag_handler import EmailRAGHandler
from ai.email.email_vector_store import EmailVectorStore
from ai.email.gmail_oauth_service import GmailOAuthService
from models.email_tracking import EmailTrackingDB
from utils.logger import log_error

# Import shared LLM config - same as other functionality
try:
    from config.llm_config import LLM_COMPONENTS, get_llm_for_component
    HAS_LLM_CONFIG = True
except ImportError:
    HAS_LLM_CONFIG = False

# Create blueprint
email_management_bp = Blueprint('email_management', __name__, url_prefix='/email')


# Initialize services
def get_oauth_service():
    """Get Gmail OAuth service instance"""
    print("[DEBUG] get_oauth_service() called")
    try:
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:10000/auth/gmail/callback')
        
        print(f"[DEBUG]   client_id present: {bool(client_id)}")
        print(f"[DEBUG]   client_secret present: {bool(client_secret)}")
        print(f"[DEBUG]   redirect_uri: {redirect_uri}")
        
        if not client_id or not client_secret:
            raise ValueError("Gmail OAuth credentials not configured")
        
        print("[DEBUG]   Creating GmailOAuthService instance...")
        service = GmailOAuthService(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri
        )
        print("[DEBUG]   GmailOAuthService created successfully")
        return service
    except Exception as e:
        print(f"[DEBUG]   ERROR in get_oauth_service: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        log_error(f"Failed to initialize OAuth service: {e}")
        raise


def get_email_fetcher():
    """Get clean email fetcher instance"""
    oauth_service = get_oauth_service()
    return CleanEmailFetcher(oauth_service)


def get_rag_handler():
    """Get email RAG handler instance - uses same API keys as other functionality"""
    try:
        vector_store = get_vector_store()
        
        # Use SHARED LLM config - same API keys as other features
        # Priority: XAI_API_KEY (Grok) > OPENAI_API_KEY > GOOGLE_API_KEY
        api_key = os.getenv('XAI_API_KEY')
        llm_provider = 'grok'
        
        if not api_key:
            api_key = os.getenv('OPENAI_API_KEY')
            llm_provider = 'openai'
            
        if not api_key:
            api_key = os.getenv('GOOGLE_API_KEY')
            llm_provider = 'gemini'
            
        if not api_key:
            raise ValueError("No LLM API key configured. Set XAI_API_KEY or OPENAI_API_KEY in .env")
        
        print(f"[Email RAG] Using {llm_provider} provider for email queries")
        
        return EmailRAGHandler(
            vector_store=vector_store,
            llm_provider=llm_provider,
            api_key=api_key
        )
    except Exception as e:
        log_error(f"Failed to initialize RAG handler: {e}")
        raise


def get_vector_store():
    """Get email vector store instance"""
    return EmailVectorStore()


def get_indexer():
    """Get email indexer instance"""
    oauth_service = get_oauth_service()
    vector_store = get_vector_store()
    return EmailIndexer(oauth_service, vector_store)


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


@email_management_bp.route('/config-status', methods=['GET'])
def get_config_status():
    """
    Get email system configuration status
    Shows whether OAuth and LLM API keys are configured
    
    Returns:
        JSON response with configuration status
    """
    print("\n" + "="*60)
    print("[DEBUG] /email/config-status endpoint called")
    print("="*60)
    
    try:
        # Check OAuth configuration
        print("[DEBUG] Step 1: Checking OAuth configuration...")
        google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        
        print(f"[DEBUG]   GOOGLE_CLIENT_ID present: {bool(google_client_id)}")
        print(f"[DEBUG]   GOOGLE_CLIENT_SECRET present: {bool(google_client_secret)}")
        
        oauth_configured = bool(google_client_id and google_client_secret)
        print(f"[DEBUG]   OAuth configured: {oauth_configured}")
        
        # Check LLM API keys (same as other functionality)
        print("[DEBUG] Step 2: Checking LLM API keys...")
        xai_api_key = os.getenv('XAI_API_KEY')
        openai_api_key = os.getenv('OPENAI_API_KEY')
        google_api_key = os.getenv('GOOGLE_API_KEY')
        
        print(f"[DEBUG]   XAI_API_KEY present: {bool(xai_api_key)}")
        print(f"[DEBUG]   OPENAI_API_KEY present: {bool(openai_api_key)}")
        print(f"[DEBUG]   GOOGLE_API_KEY present: {bool(google_api_key)}")
        
        llm_configured = bool(xai_api_key or openai_api_key or google_api_key)
        print(f"[DEBUG]   LLM configured: {llm_configured}")
        
        # Determine which LLM provider will be used
        llm_provider = None
        if xai_api_key:
            llm_provider = 'grok'
        elif openai_api_key:
            llm_provider = 'openai'
        elif google_api_key:
            llm_provider = 'gemini'
        print(f"[DEBUG]   LLM provider: {llm_provider}")
        
        # Check if user is Gmail authenticated
        print("[DEBUG] Step 3: Checking Gmail authentication...")
        gmail_authenticated = False
        user_email = None
        
        # Use Flask-Login's current_user instead of session['user_id']
        user_logged_in = current_user.is_authenticated
        print(f"[DEBUG]   current_user.is_authenticated: {user_logged_in}")
        if user_logged_in:
            print(f"[DEBUG]   current_user.id: {current_user.id}")
        
        if user_logged_in and oauth_configured:
            try:
                print("[DEBUG]   Getting OAuth service...")
                oauth_service = get_oauth_service()
                print("[DEBUG]   OAuth service obtained successfully")
                
                user_id = str(current_user.id)
                print(f"[DEBUG]   Checking if user {user_id} is authenticated...")
                
                gmail_authenticated = oauth_service.is_authenticated(user_id)
                print(f"[DEBUG]   Gmail authenticated: {gmail_authenticated}")
                
                if gmail_authenticated:
                    print("[DEBUG]   Getting user email...")
                    user_email = oauth_service.get_user_email(user_id)
                    print(f"[DEBUG]   User email: {user_email}")
                    
            except Exception as e:
                print(f"[DEBUG]   ERROR checking Gmail auth: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                log_error(f"Error checking Gmail auth: {e}")
        else:
            print("[DEBUG]   Skipping Gmail auth check (user not logged in or OAuth not configured)")
        
        # Build response
        print("[DEBUG] Step 4: Building response...")
        response_data = {
            "success": True,
            "user_logged_in": user_logged_in,
            "oauth_configured": oauth_configured,
            "llm_configured": llm_configured,
            "llm_provider": llm_provider,
            "gmail_authenticated": gmail_authenticated,
            "user_email": user_email,
            "ready_to_use": oauth_configured and llm_configured and user_logged_in,
            "message": get_config_message(oauth_configured, llm_configured, gmail_authenticated, user_logged_in)
        }
        
        print(f"[DEBUG] Response data: {response_data}")
        print("="*60 + "\n")
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"[DEBUG] FATAL ERROR in /email/config-status: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        log_error(f"Error getting config status: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def get_config_message(oauth_configured: bool, llm_configured: bool, gmail_authenticated: bool, user_logged_in: bool = True) -> str:
    """Generate helpful configuration message"""
    if not user_logged_in:
        return "🔒 Please log in to the app first to use Gmail features."
    if not oauth_configured:
        return "⚙️ Gmail OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"
    if not llm_configured:
        return "⚙️ LLM not configured. Your XAI_API_KEY or OPENAI_API_KEY will be used automatically."
    if not gmail_authenticated:
        return "🔐 Please connect your Gmail account to start using Email Intelligence."
    return "✅ All configured! Ready to analyze your emails."


@email_management_bp.route('/count', methods=['GET'])
@login_required
def get_email_count():
    """
    Get total and indexed email counts
    
    Returns:
        JSON response with email counts
    """
    try:
        user_id = str(current_user.id)
        
        # Get indexer
        indexer = get_indexer()
        
        # Get counts
        result = indexer.get_unindexed_count(user_id)
        
        if not result.get('success'):
            return jsonify({
                "success": False,
                "error": result.get('error', 'Failed to get email counts'),
                "authenticated": False
            }), 401
        
        return jsonify({
            "success": True,
            "total_emails": result.get('total_emails', 0),
            "indexed_emails": result.get('indexed_emails', 0),
            "unindexed_emails": result.get('unindexed_emails', 0),
            "user_id": user_id
        })
        
    except Exception as e:
        log_error(f"Error getting email count: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@email_management_bp.route('/sync', methods=['POST'])
@login_required
def sync_emails():
    """
    Sync emails from Gmail using clean email fetcher
    
    Returns:
        JSON response with sync results
    """
    try:
        user_id = str(current_user.id)
        print(f"[Email Management] 🔄 Starting email sync for user: {user_id}")
        
        # Get request parameters
        data = request.get_json() or {}
        limit = data.get('limit', 100)
        days_back = data.get('days_back', 30)
        
        # Get email fetcher
        fetcher = get_email_fetcher()
        
        # Check if OAuth is set up
        oauth_service = get_oauth_service()
        if not oauth_service.is_authenticated(user_id):
            return jsonify({
                "success": False,
                "error": "gmail_not_connected",
                "message": "Gmail not connected. Please authenticate first."
            }), 401
        
        # Fetch emails
        emails = fetcher.fetch_emails(
            user_id=user_id,
            limit=limit,
            days_back=days_back
        )
        
        # Get tracking db
        db = get_tracking_db()
        
        # Store emails in tracking database
        stored_count = 0
        for email_data in emails:
            try:
                # Store email if not already exists
                if not db.email_exists(user_id, email_data['id']):
                    db.store_email(user_id, email_data)
                    stored_count += 1
            except Exception as e:
                log_error(f"Error storing email {email_data['id']}: {e}")
                continue
        
        # Update last sync time
        db.update_last_sync(user_id)
        
        print(f"[Email Management] ✅ Sync completed: {len(emails)} fetched, {stored_count} stored")
        
        return jsonify({
            "success": True,
            "message": f"Successfully synced {len(emails)} emails",
            "fetched": len(emails),
            "stored": stored_count,
            "sync_time": datetime.now().isoformat()
        })
        
    except ValueError as ve:
        # OAuth not configured
        return jsonify({
            "success": False,
            "error": "oauth_not_configured", 
            "message": str(ve)
        }), 400
        
    except Exception as e:
        log_error(f"Error syncing emails: {e}")
        print(f"[Email Management] ❌ Sync error: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to sync emails"
        }), 500


@email_management_bp.route('/index', methods=['POST'])
@login_required
def index_emails():
    """
    Fetch and index emails from Gmail in one operation
    This is the main endpoint for syncing emails to the vector database
    
    Request body (optional):
        - max_emails: Maximum emails to fetch/index (default: 100)
        - days_back: Fetch emails from last N days (default: 30)
    
    Returns:
        JSON response with indexing results
    """
    print("\n" + "="*60)
    print("[DEBUG] /email/index endpoint called")
    print("="*60)
    
    try:
        user_id = str(current_user.id)
        print(f"[DEBUG] User ID: {user_id}")
        
        data = request.get_json() or {}
        max_emails = data.get('max_emails', 100)
        days_back = data.get('days_back', 30)
        print(f"[DEBUG] Parameters: max_emails={max_emails}, days_back={days_back}")
        
        # Check OAuth
        print("[DEBUG] Step 1: Checking OAuth authentication...")
        oauth_service = get_oauth_service()
        if not oauth_service.is_authenticated(user_id):
            print("[DEBUG] ERROR: User not authenticated with Gmail")
            return jsonify({
                "success": False,
                "error": "gmail_not_connected",
                "message": "Gmail not connected. Please authenticate first."
            }), 401
        print("[DEBUG] OAuth check passed")
        
        # Get indexer
        print("[DEBUG] Step 2: Getting email indexer...")
        try:
            indexer = get_indexer()
            print("[DEBUG] Indexer obtained successfully")
        except Exception as e:
            print(f"[DEBUG] ERROR getting indexer: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Index emails directly from Gmail
        print("[DEBUG] Step 3: Starting email indexing...")
        try:
            result = indexer.index_user_emails(
                user_id=user_id,
                max_emails=max_emails
            )
            print(f"[DEBUG] Indexing result: {result}")
        except Exception as e:
            print(f"[DEBUG] ERROR during indexing: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Update last sync time if successful
        if result.get('success'):
            try:
                db = get_tracking_db()
                db.update_last_sync(user_id)
                print("[DEBUG] Updated last sync time")
            except Exception as e:
                print(f"[DEBUG] Warning: Failed to update last sync time: {e}")
        
        print(f"[DEBUG] Returning result: {result}")
        print("="*60 + "\n")
        
        return jsonify(result)
        
    except ValueError as ve:
        print(f"[DEBUG] ValueError: {ve}")
        return jsonify({
            "success": False,
            "error": "configuration_error",
            "message": str(ve)
        }), 400
        
    except Exception as e:
        print(f"[DEBUG] FATAL ERROR in /email/index: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        log_error(f"Error indexing emails: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to index emails"
        }), 500


@email_management_bp.route('/index-new', methods=['POST'])
@login_required
def index_new_emails():
    """
    Index emails not yet in vector database
    
    Request body (optional):
        - max_emails: Maximum emails to index (default: 100)
        - query: Gmail search query (optional)
        - days: Index emails from last N days (optional)
    
    Returns:
        JSON response with indexing results
    """
    try:
        user_id = str(current_user.id)
        data = request.get_json() or {}
        
        # Get parameters
        max_emails = data.get('max_emails', 100)
        query = data.get('query', '')
        days = data.get('days')
        
        # Get indexer
        indexer = get_indexer()
        
        # Get tracking DB
        db = get_tracking_db()
        
        # Create indexing session
        session_id = db.create_indexing_session(user_id)
        
        # Index emails
        if days:
            result = indexer.index_recent_emails(user_id, days=days, max_emails=max_emails)
        elif query:
            result = indexer.index_by_query(user_id, query, max_emails=max_emails)
        else:
            result = indexer.index_user_emails(user_id, max_emails=max_emails)
        
        # Update session
        if session_id:
            status = 'completed' if result.get('success') else 'failed'
            db.update_indexing_session(
                session_id=session_id,
                status=status,
                emails_fetched=result.get('total_fetched', 0),
                emails_indexed=result.get('indexed', 0),
                error_message=result.get('error')
            )
        
        # Update last sync time
        if result.get('success'):
            db.update_last_sync(user_id)
        
        return jsonify(result)
        
    except Exception as e:
        log_error(f"Error indexing emails: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to index emails"
        }), 500


@email_management_bp.route('/index-batch', methods=['POST'])
@login_required
def index_emails_batch():
    """
    Index emails in batches for large mailboxes
    
    Request body:
        - batch_size: Number of emails per batch (default: 50)
        - total_limit: Total maximum emails to index (default: 1000)
    
    Returns:
        JSON response with batch indexing results
    """
    try:
        user_id = str(current_user.id)
        data = request.get_json() or {}
        
        # Get parameters
        batch_size = data.get('batch_size', 50)
        total_limit = data.get('total_limit', 1000)
        
        # Get indexer
        indexer = get_indexer()
        
        # Get tracking DB
        db = get_tracking_db()
        
        # Create indexing session
        session_id = db.create_indexing_session(user_id)
        
        # Index in batches
        result = indexer.batch_index_emails(
            user_id=user_id,
            batch_size=batch_size,
            total_limit=total_limit
        )
        
        # Update session
        if session_id:
            status = 'completed' if result.get('success') else 'failed'
            db.update_indexing_session(
                session_id=session_id,
                status=status,
                emails_fetched=result.get('total_indexed', 0),
                emails_indexed=result.get('total_indexed', 0),
                error_message=result.get('error')
            )
        
        # Update last sync time
        if result.get('success'):
            db.update_last_sync(user_id)
        
        return jsonify(result)
        
    except Exception as e:
        log_error(f"Error in batch indexing: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to batch index emails"
        }), 500


@email_management_bp.route('/status', methods=['GET'])
@login_required
def get_indexing_status():
    """
    Get comprehensive indexing status
    
    Returns:
        JSON response with status information
    """
    try:
        user_id = str(current_user.id)
        
        # Get indexer
        indexer = get_indexer()
        
        # Get status
        status = indexer.get_indexing_status(user_id)
        
        return jsonify(status)
        
    except Exception as e:
        log_error(f"Error getting status: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@email_management_bp.route('/clear-index', methods=['DELETE'])
@login_required
def clear_email_index():
    """
    Clear all indexed emails from vector store
    
    Returns:
        JSON response with success status
    """
    try:
        user_id = str(current_user.id)
        
        # Get vector store
        vector_store = get_vector_store()
        
        # Clear vector store
        success = vector_store.clear()
        
        if success:
            # Clear database records
            db = get_tracking_db()
            db.delete_indexed_emails(user_id)
            
            return jsonify({
                "success": True,
                "message": "Email index cleared successfully"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to clear email index"
            }), 500
            
    except Exception as e:
        log_error(f"Error clearing index: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to clear email index"
        }), 500


@email_management_bp.route('/stats', methods=['GET'])
@login_required
def get_vector_stats():
    """
    Get vector store statistics
    
    Returns:
        JSON response with vector store stats
    """
    try:
        # Get vector store
        vector_store = get_vector_store()
        
        # Get stats
        stats = vector_store.get_stats()
        
        return jsonify({
            "success": True,
            "stats": stats
        })
        
    except Exception as e:
        log_error(f"Error getting stats: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@email_management_bp.route('/search', methods=['POST'])
@login_required
def search_emails():
    """
    Search indexed emails by query
    
    Request body:
        - query: Search query (required)
        - n_results: Number of results (default: 5)
        - filter: Optional metadata filters
    
    Returns:
        JSON response with search results
    """
    try:
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "error": "Query is required"
            }), 400
        
        query = data.get('query')
        n_results = data.get('n_results', 5)
        filter_metadata = data.get('filter')
        
        # Get vector store
        vector_store = get_vector_store()
        
        # Search
        results = vector_store.search(
            query=query,
            n_results=n_results,
            filter_metadata=filter_metadata
        )
        
        return jsonify({
            "success": True,
            "query": query,
            "results_count": len(results),
            "results": results
        })
        
    except Exception as e:
        log_error(f"Error searching emails: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@email_management_bp.route('/query', methods=['POST'])
@login_required
def query_emails_rag():
    """
    Query emails using RAG (Retrieval-Augmented Generation)
    
    Request body:
        - question: User question (required)
        - n_results: Number of emails to retrieve (default: 5)
        - filter: Optional metadata filters
    
    Returns:
        JSON response with AI-generated answer and sources
    """
    try:
        user_id = str(current_user.id)
        data = request.get_json()
        
        print(f"[Email Management] 🤖 Processing RAG query for user: {user_id}")
        
        if not data or 'question' not in data:
            return jsonify({
                "success": False,
                "error": "question_required",
                "message": "Question is required"
            }), 400
        
        question = data.get('question')
        n_results = data.get('n_results', 5)
        filter_metadata = data.get('filter')
        
        print(f"[Email Management] 📝 Question: {question}")
        
        # Get RAG handler
        try:
            rag_handler = get_rag_handler()
        except ValueError as ve:
            return jsonify({
                "success": False,
                "error": "llm_not_configured",
                "message": str(ve)
            }), 500
        
        # Query using RAG
        result = rag_handler.query(
            query=question,
            n_results=n_results,
            filter_metadata=filter_metadata
        )
        
        print(f"[Email Management] ✅ RAG query completed")
        
        return jsonify({
            "success": True,
            "question": question,
            "answer": result.get('answer', 'No answer generated'),
            "sources": result.get('sources', []),
            "retrieved_count": result.get('retrieved_count', 0),
            "query_time": datetime.now().isoformat()
        })
        
    except Exception as e:
        log_error(f"Error in RAG query: {e}")
        print(f"[Email Management] ❌ RAG query error: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to process email query"
        }), 500


@email_management_bp.route('/indexed-list', methods=['GET'])
@login_required
def get_indexed_list():
    """
    Get list of indexed emails with pagination
    
    Query parameters:
        - limit: Maximum results (default: 50)
        - offset: Pagination offset (default: 0)
    
    Returns:
        JSON response with indexed emails list
    """
    try:
        user_id = str(current_user.id)
        
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Get tracking DB
        db = get_tracking_db()
        
        # Get indexed emails
        emails = db.get_indexed_emails(user_id, limit=limit, offset=offset)
        total_count = db.get_indexed_email_count(user_id)
        
        return jsonify({
            "success": True,
            "emails": emails,
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        })
        
    except Exception as e:
        log_error(f"Error getting indexed list: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
