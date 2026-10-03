import os

# Suppress TensorFlow/oneDNN logs BEFORE any imports
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=info, 2=warning, 3=error
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Suppress oneDNN messages

import json
import logging
import queue
import secrets
import signal
import sys
import threading
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request
from flask_login import LoginManager, current_user, login_required

# Load environment variables
load_dotenv()

# Import configuration system
from config.config_loader import get_config

# Initialize configuration
config = get_config()

# Import logging system with config
from utils.logger import (init_logging, log_error, log_function_call,
                          server_logger)

# Initialize logging with configuration
init_logging(config.get_logging_config())

# Initialize Error Notification System (right after config and logging)
try:
    from utils.error_notifier import (get_notification_queue,
                                      shutdown_notification_system)

    # Start the error notification worker
    notification_queue = get_notification_queue()
    server_logger.info("✅ Error notification system initialized - critical errors will be emailed to admins")
    
    # Register shutdown handler
    def shutdown_error_notifier():
        """Shutdown error notifier on app termination"""
        try:
            shutdown_notification_system()
            server_logger.info("Error notification system shutdown complete")
        except Exception as e:
            server_logger.error(f"Error shutting down notification system: {e}")
    
    # Register with atexit for graceful shutdown
    import atexit
    atexit.register(shutdown_error_notifier)
    
except Exception as e:
    server_logger.error(f"Failed to initialize error notification system: {e}")
    server_logger.warning("Application will continue without error email notifications")

# Suppress verbose infrastructure logs (keep only RAG/LLM logs)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('openai._base_client').setLevel(logging.WARNING)
logging.getLogger('server').setLevel(logging.WARNING)
logging.getLogger('api').setLevel(logging.WARNING)
logging.getLogger('auth').setLevel(logging.WARNING)
logging.getLogger('chat').setLevel(logging.WARNING)
logging.getLogger('database').setLevel(logging.WARNING)
logging.getLogger('user').setLevel(logging.WARNING)
logging.getLogger('models.chat').setLevel(logging.WARNING)
logging.getLogger('controllers.chat').setLevel(logging.WARNING)
logging.getLogger('controllers.api').setLevel(logging.WARNING)
logging.getLogger('controllers.ai_analysis').setLevel(logging.WARNING)

# Suppress verbose third-party library logs
logging.getLogger('tensorflow').setLevel(logging.ERROR)
logging.getLogger('chromadb').setLevel(logging.WARNING)
logging.getLogger('chromadb.telemetry').setLevel(logging.ERROR)
logging.getLogger('chromadb.telemetry.product.posthog').setLevel(logging.ERROR)
logging.getLogger('sentence_transformers').setLevel(logging.WARNING)
logging.getLogger('sentence_transformers.SentenceTransformer').setLevel(logging.WARNING)
logging.getLogger('datasets').setLevel(logging.WARNING)
logging.getLogger('transformers').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Import controllers
from controllers import (analytics, api, auth, chat, facebook, main, settings,
                         whatsapp)
from controllers.scheduler_controller import bp as scheduler_bp
# Import models and initialize database
from models import User, init_db


def graceful_shutdown(signum, frame):
    """Handle SIGTERM for Docker graceful shutdown"""
    server_logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    if scheduler_manager:
        try:
            scheduler_manager.shutdown()
            server_logger.info("Scheduler shutdown complete")
        except Exception as e:
            server_logger.error(f"Error shutting down scheduler: {e}")
    sys.exit(0)

# Register signal handlers (only in main thread)
if threading.current_thread() == threading.main_thread():
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)

# Configuration from config file
DATA_DIR = config.get('database.db_file', 'data').split('/')[0]  # Extract directory
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize Flask app with configuration
app = Flask(__name__)
flask_config = config.get_flask_config()
app.config.update(flask_config)

# Initialize Socket.IO for real-time group chat
from flask_socketio import SocketIO

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

server_logger.info("Flask application starting...")
server_logger.info(f"Data directory: {DATA_DIR}")
server_logger.info(f"Secret key configured: {'Yes' if config.get('server.secret_key') else 'No (using generated)'}")
server_logger.info(f"Debug mode: {config.get('server.debug', False)}")
server_logger.info(f"Host: {config.get('server.host', '127.0.0.1')}")
server_logger.info(f"Port: {config.get('server.port', 10000)}")
server_logger.info("Socket.IO initialized for real-time group chat")

# Register scheduler blueprint
app.register_blueprint(scheduler_bp)

# Register admin users blueprint
from controllers.admin_users_controller import bp as admin_users_bp

app.register_blueprint(admin_users_bp)
server_logger.info("Admin users blueprint registered")

# Register email OAuth and management blueprints
try:
    print("[DEBUG] Registering email blueprints...")
    from controllers.email_management_controller import email_management_bp
    from controllers.email_oauth_controller import email_oauth_bp
    
    print(f"[DEBUG] email_oauth_bp url_prefix: {email_oauth_bp.url_prefix}")
    print(f"[DEBUG] email_management_bp url_prefix: {email_management_bp.url_prefix}")
    
    app.register_blueprint(email_oauth_bp)
    app.register_blueprint(email_management_bp)
    
    # List all email routes for debugging
    print("[DEBUG] Registered email routes:")
    for rule in app.url_map.iter_rules():
        if 'email' in rule.rule or 'gmail' in rule.rule:
            print(f"[DEBUG]   {rule.rule} -> {rule.endpoint}")
    
    server_logger.info("Email OAuth and management blueprints registered")
except Exception as e:
    print(f"[DEBUG] ERROR registering email blueprints: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    server_logger.warning(f"Email management features not available: {e}")

# Register logs blueprint
from controllers.logs_controller import bp as logs_bp

app.register_blueprint(logs_bp)
server_logger.info("Logs blueprint registered")

# Initialize automated scheduler (if enabled in config)
scheduler_manager = None
if config.get('scheduling.enabled', False):
    try:
        from scheduler.manager import scheduler_manager as sm
        sm.init_app(app)
        scheduler_manager = sm
        server_logger.info("Automated scheduler initialized")
    except Exception as e:
        server_logger.error(f"Failed to initialize scheduler: {e}")
        # Continue without scheduler - app still works
else:
    server_logger.info("Automated scheduler disabled in configuration")
# Real-time log capture system
log_queue = queue.Queue(maxsize=1000)
log_subscribers = []

class LogCapture(logging.Handler):
    """Custom logging handler to capture logs for real-time display"""

    def emit(self, record):
        try:
            # Use datetime already imported at module level (don't import inside emit - causes deadlocks in Docker)
            # Format the log message
            log_entry = {
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'level': record.levelname.lower(),
                'message': self.format(record)
            }
            
            # Add to queue (remove oldest if full)
            try:
                log_queue.put_nowait(log_entry)
            except queue.Full:
                try:
                    log_queue.get_nowait()
                    log_queue.put_nowait(log_entry)
                except queue.Empty:
                    pass
            
            # Notify all subscribers
            for subscriber in log_subscribers[:]:
                try:
                    subscriber.put_nowait(log_entry)
                except queue.Full:
                    log_subscribers.remove(subscriber)
                except:
                    if subscriber in log_subscribers:
                        log_subscribers.remove(subscriber)
                        
        except Exception as e:
            pass  # Avoid logging errors in the logger


class StdoutCapture:
    """Capture stdout/stderr for tqdm progress bars and other console output"""
    
    def __init__(self, original_stream, stream_name):
        self.original_stream = original_stream
        self.stream_name = stream_name
        self.buffer = ""
        self.enabled = True
    
    def write(self, text):
        # Always write to original stream first
        try:
            self.original_stream.write(text)
            self.original_stream.flush()
        except:
            pass  # Don't let capture errors break the original stream

        # Handle bytes input (Flask/click may pass bytes)
        if isinstance(text, bytes):
            try:
                text = text.decode('utf-8', errors='ignore')
            except:
                return

        # Only capture if enabled and not in Flask's internal operations
        if not self.enabled or not text or not text.strip():
            return
        
        # Skip Flask internal messages that might interfere with server
        if any(skip_pattern in text for skip_pattern in [
            'werkzeug', 'serving.py', 'socketserver.py', 'selectors.py',
            'Thread-', 'serve_forever', 'socket', 'OSError'
        ]):
            return
        
        try:
            self.buffer += text
            
            # Check for complete lines or progress updates
            if '\n' in text or '\r' in text or any(keyword in text for keyword in [
                'Enriching blocks', 'Pipeline completed', 'Block separation', 
                'MixBlock', 'HavalPipeline', 'Starting pipeline', 'Scraping', 'Fetching',
                'WATI', 'WhatsApp', 'contacts', 'messages', 'import completed'
            ]):
                lines = self.buffer.replace('\r', '\n').split('\n')
                
                for line in lines[:-1]:  # Process all complete lines
                    line = line.strip()
                    if line and any(keyword in line for keyword in [
                        'Enriching blocks', 'Pipeline completed', 'Block separation',
                        'MixBlock', 'HavalPipeline', 'Starting pipeline', 'Scraping',
                        'Fetching', '🤖', '📡', '✅', '[07:', 'posts to database',
                        'WATI', 'WhatsApp', 'contacts', 'messages', 'import completed',
                        'Starting WATI', 'Processing contact', 'messages imported'
                    ]):
                        # Create log entry for progress updates
                        log_entry = {
                            'timestamp': datetime.now().strftime('%H:%M:%S'),
                            'level': 'info',
                            'message': line
                        }
                        
                        # Add to queue safely
                        try:
                            log_queue.put_nowait(log_entry)
                        except queue.Full:
                            try:
                                log_queue.get_nowait()
                                log_queue.put_nowait(log_entry)
                            except:
                                pass
                        except:
                            pass  # Don't let logging errors break the capture
                        
                        # Notify subscribers safely
                        for subscriber in log_subscribers[:]:
                            try:
                                subscriber.put_nowait(log_entry)
                            except:
                                try:
                                    if subscriber in log_subscribers:
                                        log_subscribers.remove(subscriber)
                                except:
                                    pass
                
                # Keep the last incomplete line
                self.buffer = lines[-1] if lines else ""
        except:
            pass  # Don't let capture errors break anything
    
    def flush(self):
        try:
            self.original_stream.flush()
        except:
            pass
    
    def disable(self):
        """Disable capture temporarily"""
        self.enabled = False
    
    def enable(self):
        """Re-enable capture"""
        self.enabled = True
    
    def __getattr__(self, name):
        return getattr(self.original_stream, name)


# Set up log capture
log_capture = LogCapture()
log_capture.setLevel(logging.INFO)
formatter = logging.Formatter('%(message)s')
log_capture.setFormatter(formatter)

# Add to app logger
app.logger.addHandler(log_capture)
app.logger.setLevel(logging.INFO)

# Add log capture handler to all our custom loggers
from utils.logger import (ai_logger, analytics_logger, api_logger, auth_logger,
                          chat_logger, database_logger, error_logger,
                          fetching_logger, scraping_logger, server_logger,
                          user_logger, warning_logger, whatsapp_logger)

# Add the log capture handler to all loggers so they appear in the web stream
for logger in [user_logger, server_logger, error_logger, scraping_logger,
               fetching_logger, warning_logger, ai_logger, database_logger,
               auth_logger, api_logger, analytics_logger, whatsapp_logger, chat_logger]:
    logger.addHandler(log_capture)

server_logger.info("Log capture system initialized")

# Set up stdout/stderr capture for tqdm progress bars (with safety checks)
try:
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Only enable stdout capture if not in production or if explicitly enabled
    enable_stdout_capture = config.get('development.hot_reload', True)

    if enable_stdout_capture:
        sys.stdout = StdoutCapture(original_stdout, 'stdout')
        sys.stderr = StdoutCapture(original_stderr, 'stderr')
        server_logger.info("Stdout/stderr capture initialized for progress monitoring")
    else:
        server_logger.info("Stdout/stderr capture disabled (production mode)")

except Exception as e:
    server_logger.warning(f"Failed to initialize stdout capture: {e}")
    # Continue without stdout capture if it fails
# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
@log_function_call(server_logger)
def load_user(user_id):
    return User.get(int(user_id))

server_logger.info("Flask-Login initialized")

# Session management - ensure sessions are permanent and track activity
@app.before_request
def before_request():
    """Handle session management before each request"""
    import time

    from flask import session

    # Skip session handling for static files
    if request.endpoint and request.endpoint == 'static':
        return None

    # Make session permanent to use PERMANENT_SESSION_LIFETIME
    session.permanent = True

    # Update last activity timestamp for session validation
    if current_user.is_authenticated:
        session['last_activity'] = time.time()

# Initialize database
try:
    init_db()
    server_logger.info("Database initialized successfully")
except Exception as e:
    log_error(e, "Database initialization failed")
    raise

# Run database migration checks
try:
    from models.migration_checker import MigrationChecker
    
    server_logger.info("=" * 70)
    server_logger.info("DATABASE MIGRATION CHECK")
    server_logger.info("=" * 70)
    
    # Get detailed migration status
    migration_status = MigrationChecker.get_migration_status()
    
    # Log status
    server_logger.info(f"✓ Tables: {'OK' if migration_status['tables_ok'] else 'ISSUES'}")
    server_logger.info(f"✓ Columns: {'OK' if migration_status['columns_ok'] else 'ISSUES'}")
    server_logger.info(f"✓ Indexes: {'OK' if migration_status['indexes_ok'] else 'ISSUES'}")
    server_logger.info(f"✓ Group Chat: {'OK' if migration_status['group_chat_ok'] else 'ISSUES'}")
    server_logger.info(f"✓ Chat History: {'OK' if migration_status['chat_history_ok'] else 'ISSUES'}")
    server_logger.info(f"✓ Users: {'OK' if migration_status['users_ok'] else 'ISSUES'}")
    server_logger.info(f"✓ Permissions: {'OK' if migration_status['permissions_ok'] else 'ISSUES'}")
    
    # Report any issues
    if migration_status['issues']:
        server_logger.warning("⚠️  Migration issues detected:")
        for issue in migration_status['issues']:
            server_logger.warning(f"   - {issue}")
    
    # Check if all critical components are OK
    all_ok = all([
        migration_status['tables_ok'],
        migration_status['columns_ok'],
        migration_status['group_chat_ok'],
        migration_status['chat_history_ok'],
        migration_status['users_ok'],
        migration_status['permissions_ok']
    ])
    
    if all_ok:
        server_logger.info("=" * 70)
        server_logger.info("✅ ALL DATABASE MIGRATIONS VERIFIED - APPLICATION READY")
        server_logger.info("=" * 70)
    else:
        server_logger.error("=" * 70)
        server_logger.error("❌ DATABASE MIGRATION ISSUES DETECTED - PLEASE FIX BEFORE CONTINUING")
        server_logger.error("=" * 70)
        # Don't raise - allow app to start but log the issues
        
except Exception as e:
    log_error(e, "Database migration check failed")
    server_logger.error("⚠️  Could not perform migration checks - proceeding with caution")

# Initialize AI pipeline on startup (skip if DISABLE_AI_INIT is set to 'true' for local testing)
disable_ai_init = os.getenv('DISABLE_AI_INIT', 'false').lower() == 'true'
if not disable_ai_init:
    try:
        server_logger.info("Initializing AI pipeline...")
        from ai.haval_pipeline import get_pipeline_status, get_rag_engine

        # Check if pipeline is ready
        status = get_pipeline_status()
        server_logger.info(f"Pipeline status: {status.get('status', 'unknown')}")

        # Try to initialize RAG engine
        rag_engine = get_rag_engine()
        if rag_engine:
            server_logger.info("RAG engine initialized successfully")
        else:
            server_logger.warning("RAG engine not available - may need data processing")

    except Exception as e:
        log_error(e, "AI pipeline initialization failed")
        server_logger.warning("AI features may not be available until data is processed")
        # Notify about startup error
        try:
            from utils.error_notifier import notify_startup_error
            notify_startup_error(f"AI Pipeline Error: {str(e)}")
        except:
            pass
else:
    server_logger.warning("AI pipeline initialization skipped (DISABLE_AI_INIT=true)")
# Lazy initialization functions for AI components
openai_client = None
llm_client = None

@log_function_call(server_logger)
def get_openai_client():
    """Lazy initialization of OpenAI client for Insights mode"""
    global openai_client
    if openai_client is not None:
        return openai_client

    try:
        from config import get_llm_for_component
        openai_client = get_llm_for_component("insights")
        server_logger.info("OpenAI client initialized for Insights mode")
        return openai_client
    except Exception as e:
        openai_client = False
        log_error(e, "Failed to initialize Insights LLM")
        return None

@log_function_call(server_logger)
def get_llm_client():
    """Lazy initialization of LLM client"""
    global llm_client
    if llm_client is not None:
        return llm_client

    try:
        from config import get_llm_for_component
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        llm_client = get_llm_for_component("answer_generation", fallback_api_key=gemini_api_key)
        server_logger.info("LLM client initialized from centralized config")
        return llm_client
    except Exception as e:
        llm_client = False
        log_error(e, "Failed to initialize LLM client")
        return None

# ----------------------
# ROUTES - Using MVC Controllers
# ----------------------

# Authentication Routes
@app.route("/login", methods=["GET", "POST"])
@log_function_call(server_logger)
def login():
    return auth.login()

@app.route("/register", methods=["GET", "POST"])
@log_function_call(server_logger)
def register():
    return auth.register()

@app.route("/logout")
@login_required
@log_function_call(server_logger)
def logout():
    return auth.logout()

@app.route("/verify-otp", methods=["GET", "POST"])
@log_function_call(server_logger)
def verify_otp():
    return auth.verify_otp()

@app.route("/resend-otp", methods=["POST"])
@log_function_call(server_logger)
def resend_otp():
    return auth.resend_otp()

@app.route("/forgot-password", methods=["GET", "POST"])
@log_function_call(server_logger)
def forgot_password():
    return auth.forgot_password()

@app.route("/reset-password", methods=["GET", "POST"])
@log_function_call(server_logger)
def reset_password():
    return auth.reset_password()

@app.route("/resend-reset-otp", methods=["POST"])
@log_function_call(server_logger)
def resend_reset_otp():
    return auth.resend_reset_otp()

# Main Routes
@app.route("/")
@log_function_call(server_logger)
def index():
    """Landing page for non-authenticated users"""
    return render_template('landing.html')

@app.route("/help")
@log_function_call(server_logger)
def help_page():
    """Help center page"""
    return render_template('help.html')

@app.route("/download_file")
@log_function_call(server_logger)
def download_file():
    return main.download_file()

@app.route("/scrape_single_topic", methods=["POST"])
@login_required
@log_function_call(server_logger)
def scrape_single_topic():
    return main.scrape_single_topic()

@app.route("/scrape_manual_url", methods=["POST"])
@login_required
@log_function_call(server_logger)
def scrape_manual_url():
    return main.scrape_manual_url()

@app.route("/scrape_reddit", methods=["POST"])
@login_required
@log_function_call(server_logger)
def scrape_reddit():
    return main.scrape_reddit()

@app.route("/scrape_lucid", methods=["POST"])
@login_required
@log_function_call(server_logger)
def scrape_lucid():
    return main.scrape_lucid()

@app.route("/scrape_lucid_thread", methods=["POST"])
@login_required
@log_function_call(server_logger)
def scrape_lucid_thread():
    return main.scrape_lucid_thread()

@app.route("/scrape_reddit_lucid", methods=["POST"])
@login_required
@log_function_call(server_logger)
def scrape_reddit_lucid():
    return main.scrape_reddit_lucid()

@app.route("/scrape_reddit_lucid_manual", methods=["POST"])
@login_required
@log_function_call(server_logger)
def scrape_reddit_lucid_manual():
    return main.scrape_reddit_lucid_manual()

@app.route("/pipeline_status")
@log_function_call(server_logger)
def pipeline_status():
    return main.pipeline_status()

# Chat Routes
@app.route("/chatbot")
@login_required
@log_function_call(server_logger)
def chatbot():
    return chat.chatbot()

@app.route("/chatbot_advanced")
@login_required
@log_function_call(server_logger)
def chatbot_advanced():
    return chat.chatbot_advanced()

@app.route("/api/user/permissions", methods=["GET"])
@login_required
def get_user_permissions():
    """Get current user's data source permissions"""
    try:
        from models.datasource_permissions import DataSourcePermissions
        permissions = DataSourcePermissions.get_user_permissions(current_user.id)
        return jsonify({
            'success': True,
            'permissions': permissions,
            'user_id': current_user.id,
            'username': current_user.username
        })
    except Exception as e:
        server_logger.error(f"Error getting permissions for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    """Check if user is authenticated"""
    try:
        is_authenticated = current_user.is_authenticated
        username = current_user.username if is_authenticated else None
        user_id = current_user.id if is_authenticated else None
        
        # Add debug logging
        from utils.logger import server_logger
        server_logger.info(f"Auth status check: authenticated={is_authenticated}, username={username}, user_id={user_id}")
        
        return jsonify({
            "authenticated": is_authenticated,
            "username": username,
            "user_id": user_id
        })
    except Exception as e:
        from utils.logger import log_error, server_logger
        log_error(e, "Error in auth status check")
        return jsonify({
            "authenticated": False,
            "username": None,
            "error": str(e)
        })

@app.route("/api/auth/active-sessions", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_active_sessions():
    """Get active user sessions with login/logout times"""
    try:
        from models.database import get_db_connection
        from datetime import datetime, timedelta
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get all users with their last login time
        cur.execute("""
            SELECT id, username, email, last_login, created_at, company_id
            FROM users
            WHERE is_active = 1 AND is_deleted = 0
            ORDER BY last_login DESC
        """)
        
        users = cur.fetchall()
        conn.close()
        
        active_sessions = []
        currently_online = 0
        
        for user in users:
            user_id, username, email, last_login, created_at, company_id = user
            
            if last_login:
                login_time = datetime.fromisoformat(last_login)
                # Consider user online if logged in within last 30 minutes
                time_since_login = (datetime.now() - login_time).total_seconds()
                is_online = time_since_login < 1800  # 30 minutes
                
                if is_online:
                    currently_online += 1
                
                # Calculate session duration if still online
                if is_online:
                    hours = int(time_since_login // 3600)
                    minutes = int((time_since_login % 3600) // 60)
                    session_duration = f"{hours}h {minutes}m"
                else:
                    session_duration = "Offline"
                
                active_sessions.append({
                    'user_id': user_id,
                    'username': username,
                    'email': email,
                    'last_login': last_login,
                    'created_at': created_at,
                    'company_id': company_id,
                    'is_online': is_online,
                    'session_duration': session_duration,
                    'time_since_login_seconds': int(time_since_login)
                })
        
        return jsonify({
            'success': True,
            'currently_online': currently_online,
            'total_active_users': len(active_sessions),
            'sessions': active_sessions
        })
    except Exception as e:
        log_error(e, "Error fetching active sessions")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route("/api/debug/session", methods=["GET"])
def debug_session():
    """Debug session information"""
    try:
        from flask import session
        return jsonify({
            "session_keys": list(session.keys()),
            "has_user_id": '_user_id' in session,
            "current_user_authenticated": current_user.is_authenticated,
            "current_user_id": getattr(current_user, 'id', None),
            "current_user_username": getattr(current_user, 'username', None)
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/debug/chat-history", methods=["GET"])
@login_required
def debug_chat_history():
    """Debug chat history data"""
    try:
        from flask import request

        from models.chat import get_user_chat_history

        # Get parameters
        mode = request.args.get('mode', 'insights')
        limit = int(request.args.get('limit', 10))
        
        # Get current session ID
        from flask import session
        session_id = session.get('chat_session_id', 'no-session')
        
        # Get chat history
        history = get_user_chat_history(current_user.id, mode, session_id, limit=limit)
        
        # Also get raw database data
        from models import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, user_id, session_id, mode, query, response, 
                   timestamp
            FROM chat_history 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (current_user.id, limit))
        
        raw_data = []
        for row in cur.fetchall():
            raw_data.append({
                'id': row[0],
                'user_id': row[1],
                'session_id': row[2],
                'mode': row[3],
                'user_message': row[4][:100] + '...' if len(row[4]) > 100 else row[4],
                'bot_response': row[5][:100] + '...' if len(row[5]) > 100 else row[5],
                'timestamp': row[6]
            })
        
        conn.close()
        
        return jsonify({
            "current_user_id": current_user.id,
            "current_session_id": session_id,
            "mode": mode,
            "processed_history_count": len(history),
            "processed_history": history[:5],  # First 5 for brevity
            "raw_database_count": len(raw_data),
            "raw_database_data": raw_data[:5],  # First 5 for brevity
            "all_sessions": list(set([row['session_id'] for row in raw_data]))
        })
        
    except Exception as e:
        log_error(e, "Error in debug chat history")
        return jsonify({"error": str(e)})

@app.route("/api/debug/test-chat-save", methods=["POST"])
@login_required
def debug_test_chat_save():
    """Test saving a chat message"""
    try:
        import secrets

        from flask import session

        from models.chat import save_user_chat_history

        # Get or create session ID
        session_id = session.get('chat_session_id')  # Debug endpoint doesn't use payload session_id
        if not session_id:
            session_id = secrets.token_hex(16)
            session['chat_session_id'] = session_id
        
        # Test data
        test_query = "Test message from debug endpoint"
        test_response = "Test response from debug endpoint"
        test_mode = "insights"
        
        # Save the test chat
        save_user_chat_history(current_user.id, session_id, test_mode, test_query, test_response)
        
        return jsonify({
            "success": True,
            "message": "Test chat saved successfully",
            "user_id": current_user.id,
            "session_id": session_id,
            "mode": test_mode
        })
        
    except Exception as e:
        log_error(e, "Error in test chat save")
        return jsonify({"error": str(e), "success": False})

@app.route("/api/debug/test-followups", methods=["POST"])
@login_required
def debug_test_followups():
    """Test follow-up generation functionality"""
    try:
        data = request.get_json()
        test_query = data.get('query', 'What are the problems with Haval H6?')
        test_answer = data.get('answer', 'There are several issues reported with Haval H6 including engine problems, electrical issues, and transmission concerns.')
        
        # Import the structured data extraction function
        from controllers.ai_analysis import extract_structured_data

        # Test structured data extraction (no follow-ups generated)
        structured = extract_structured_data(test_answer, [], 'pakwheels')
        
        return jsonify({
            "success": True,
            "test_query": test_query,
            "test_answer": test_answer,
            "structured_data": structured,
            "recommendations_removed": True,
            "followups_removed": True
        })
        
    except Exception as e:
        server_logger.error(f"Error in debug_test_followups: {e}")
        return jsonify({"error": str(e), "success": False})

@app.route("/api/system/migration-status", methods=["GET"])
def migration_status_endpoint():
    """Get database migration status"""
    try:
        from models.migration_checker import MigrationChecker
        status = MigrationChecker.get_migration_status()
        return jsonify(status), 200
    except Exception as e:
        log_error(e, "Failed to get migration status")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route("/api/system/health", methods=["GET"])
def system_health():
    """Get system health status including database"""
    try:
        from models.migration_checker import MigrationChecker
        
        migration_status = MigrationChecker.get_migration_status()
        
        health = {
            "status": "healthy" if all([
                migration_status['tables_ok'],
                migration_status['columns_ok'],
                migration_status['group_chat_ok'],
                migration_status['chat_history_ok'],
                migration_status['users_ok'],
                migration_status['permissions_ok']
            ]) else "degraded",
            "database": migration_status,
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(health), 200
    except Exception as e:
        log_error(e, "Failed to get system health")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/chatbot_query", methods=["POST"])
@login_required
@log_function_call(server_logger)
def chatbot_query():
    """Process chatbot queries - debug version"""
    try:
        # Add debug logging
        server_logger.info(f"Chatbot query endpoint hit by user: {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        server_logger.info(f"User authenticated: {current_user.is_authenticated}")
        
        return chat.chatbot_query()
    except Exception as e:
        log_error(e, "Error in chatbot_query endpoint")
        return jsonify({"answer": f"Error: {str(e)}"})

@app.route("/chatbot_query_stream", methods=["POST"])
@login_required
@log_function_call(server_logger)
def chatbot_query_stream():
    return chat.chatbot_query_stream()

# Group Chat Routes
@app.route("/api/group-chat/start", methods=["POST"])
@login_required
@log_function_call(server_logger)
def start_group_chat():
    """Start a new group chat by cloning current conversation"""
    from controllers.group_chat import start_group_chat as start_gc
    return start_gc()

@app.route("/api/group-chat/invite", methods=["POST"])
@login_required
@log_function_call(server_logger)
def invite_to_group_chat():
    """Invite a user to a group chat"""
    from controllers.group_chat import invite_to_group_chat as invite_gc
    return invite_gc()

@app.route("/api/group-chat/remove", methods=["POST"])
@login_required
@log_function_call(server_logger)
def remove_from_group_chat():
    """Remove a participant from group chat"""
    from controllers.group_chat import remove_from_group_chat as remove_gc
    return remove_gc()

@app.route("/api/group-chat/messages", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_group_chat_messages():
    """Get group chat message history"""
    from controllers.group_chat import get_group_chat_messages as get_msgs
    return get_msgs()

@app.route("/api/group-chat/query", methods=["POST"])
@login_required
@log_function_call(server_logger)
def group_chat_query_stream():
    """Stream a query to group chat"""
    from controllers.group_chat import group_chat_query_stream as query_stream
    return query_stream()

@app.route("/api/group-chat/list", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_my_group_chats():
    """Get all group chats for current user"""
    from controllers.group_chat import get_my_group_chats as get_groups
    return get_groups()

@app.route("/api/group-chat/delete", methods=["POST"])
@login_required
@log_function_call(server_logger)
def delete_group():
    """Delete a group chat"""
    from controllers.group_chat import delete_group as delete_gc
    return delete_gc()

@app.route("/api/group-chat/clear", methods=["POST"])
@login_required
@log_function_call(server_logger)
def clear_group_conversation():
    """Clear all messages in a group chat"""
    from controllers.group_chat import clear_group_conversation as clear_gc
    return clear_gc()

@app.route("/api/group-chat/add-message", methods=["POST"])
@login_required
@log_function_call(server_logger)
def add_group_message():
    """Add a message to group chat (for group-only mode)"""
    from controllers.group_chat import add_group_message as add_msg
    return add_msg()

@app.route("/api/group-chat/info", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_group_info():
    """Get detailed group chat information"""
    from controllers.group_chat import get_group_info as get_info
    return get_info()

@app.route("/create_group_chat", methods=["POST"])
@login_required
@log_function_call(server_logger)
def create_group_chat():
    """Create a new group chat (legacy endpoint for frontend compatibility)"""
    from controllers.group_chat import start_group_chat as start_gc
    return start_gc()

@app.route("/api/group-chat/message/send", methods=["POST"])
@login_required
@log_function_call(server_logger)
def send_group_message():
    """Send a message to group chat"""
    from controllers.group_chat import group_chat_query_stream
    return group_chat_query_stream()

@app.route("/api/group-chat/user-groups", methods=["GET"])
@login_required
@log_function_call(server_logger)
def user_groups():
    """Get all groups for current user"""
    from controllers.group_chat import get_my_group_chats
    return get_my_group_chats()

@app.route("/api/group-chat/invite-user", methods=["POST"])
@login_required
@log_function_call(server_logger)
def invite_user_to_group():
    """Invite a user to a group chat"""
    from controllers.group_chat import invite_to_group_chat
    return invite_to_group_chat()

@app.route("/api/group-chat/update-mode", methods=["POST"])
@login_required
@log_function_call(server_logger)
def update_group_mode_route():
    """Update group mode (creator only)"""
    from controllers.group_chat import update_group_mode
    return update_group_mode()

# Users API Routes
@app.route("/api/users/list", methods=["GET"])
@login_required
@log_function_call(server_logger)
def users_list():
    """Get list of all users"""
    from controllers.users_api import get_users_list
    return get_users_list()

@app.route("/api/users/search", methods=["GET"])
@login_required
@log_function_call(server_logger)
def users_search():
    """Search for users"""
    from controllers.users_api import search_users
    return search_users()

@app.route("/api/users/<int:user_id>", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_user(user_id):
    """Get user by ID"""
    from controllers.users_api import get_user_by_id
    return get_user_by_id()

@app.route("/api/users/invite-list", methods=["GET"])
@login_required
@log_function_call(server_logger)
def users_invite_list():
    """Get list of users for group chat invitations"""
    from controllers.users_api import get_users_list
    return get_users_list()

@app.route("/chatbot_query_fast", methods=["POST"])
@login_required
@log_function_call(server_logger)
def chatbot_query_fast():
    return chat.chatbot_query_fast()

# API Routes
@app.route("/api/test/facebook-beta", methods=["POST"])
@log_function_call(server_logger)
def test_facebook_beta():
    """Test endpoint for Facebook Beta mode without authentication"""
    try:
        from flask import request

        from services.ai_service import AIService
        
        data = request.get_json() or {}
        query = data.get("query", "recent issues")
        
        # Test Facebook Beta mode directly
        answer = AIService.process_chat_query(query, "facebook_beta", "haval")
        
        return jsonify({
            "answer": answer,
            "status": "success"
        })
        
    except Exception as e:
        from utils.logger import log_error
        log_error(e, "Test Facebook Beta endpoint error")
        return jsonify({
            "answer": f"Error: {str(e)}",
            "status": "error"
        })

@app.route("/api/company", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_selected_company():
    return api.get_selected_company()

@app.route("/api/company", methods=["POST"])
@login_required
@log_function_call(server_logger)
def set_selected_company():
    return api.set_selected_company()

@app.route("/api/companies", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_all_companies_api():
    return api.get_all_companies_api()

@app.route("/api/chat/sessions", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_chat_sessions():
    return api.get_chat_sessions()

@app.route("/api/chat/history/<session_id>", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_session_history(session_id):
    return api.get_session_history(session_id)

@app.route("/api/chat/session/<session_id>", methods=["DELETE"])
@login_required
@log_function_call(server_logger)
def delete_chat_session(session_id):
    return api.delete_chat_session(session_id)

@app.route("/api/chat/clear", methods=["POST"])
@login_required
@log_function_call(server_logger)
def clear_chat_history():
    return api.clear_chat_history()

@app.route("/api/pipeline-status", methods=["GET"])
@log_function_call(server_logger)
def api_pipeline_status():
    return api.api_pipeline_status()

@app.route("/api/pipeline/reset", methods=["POST"])
@login_required
@log_function_call(server_logger)
def api_pipeline_reset():
    """Force reset pipeline status to ready - use when pipeline is stuck.
    Admin-only endpoint accessible at http://ai.sazgarautos.com:10001/api/pipeline/reset
    """
    from scheduler.decorators import is_admin_user
    if not is_admin_user(current_user):
        return jsonify({"success": False, "error": "Admin access required"}), 403
    try:
        from ai.haval_pipeline import reset_pipeline_status
        result = reset_pipeline_status()
        return jsonify({"success": True, "message": "Pipeline status reset to ready", "status": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/wati/progress", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_wati_progress():
    return api.get_wati_progress()

@app.route("/api/chat/new-session", methods=["POST"])
@login_required
@log_function_call(server_logger)
def new_chat_session():
    return api.new_chat_session()

@app.route("/api/current-model", methods=["GET"])
@login_required
@log_function_call(server_logger)
def api_current_model():
    """Get current AI model configuration"""
    try:
        from config.llm_config import get_llm_config

        # Get the main answer generation model config
        config = get_llm_config("answer_generation")
        
        return jsonify({
            "success": True,
            "provider": config.provider,
            "model_name": config.model_name,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens
        })
        
    except Exception as e:
        server_logger.error(f"Error getting current model: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "provider": "grok",  # Default fallback
            "model_name": "grok-3-fast"
        })

# Dealership Management Routes
@app.route("/dealership")
@login_required
@log_function_call(server_logger)
def dealership_dashboard():
    import controllers.dealership as dealership
    return dealership.dealership_dashboard()

@app.route("/dealership/warranty-claims")
@login_required
@log_function_call(server_logger)
def warranty_claims():
    import controllers.dealership as dealership
    return dealership.warranty_claims()

@app.route("/dealership/campaign-reports")
@login_required
@log_function_call(server_logger)
def campaign_reports():
    import controllers.dealership as dealership
    return dealership.campaign_reports()

@app.route("/dealership/ffs-inspections")
@login_required
@log_function_call(server_logger)
def ffs_inspections():
    import controllers.dealership as dealership
    return dealership.ffs_inspections()

@app.route("/dealership/sfs-inspections")
@login_required
@log_function_call(server_logger)
def sfs_inspections():
    import controllers.dealership as dealership
    return dealership.sfs_inspections()

@app.route("/dealership/pdi-inspections")
@login_required
@log_function_call(server_logger)
def pdi_inspections():
    import controllers.dealership as dealership
    return dealership.pdi_inspections()

@app.route("/dealership/repair-orders")
@login_required
@log_function_call(server_logger)
def repair_orders():
    import controllers.dealership as dealership
    return dealership.repair_orders()

@app.route("/dealership/vin-history")
@login_required
@log_function_call(server_logger)
def vin_history():
    import controllers.dealership as dealership
    return dealership.vin_history()

# API Usage Tracking Routes
@app.route("/api/usage/stats", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_usage_stats():
    from controllers.api_usage import get_usage_stats as get_stats
    return get_stats()

@app.route("/api/usage/daily", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_daily_usage():
    from controllers.api_usage import get_daily_usage as get_daily
    return get_daily()

@app.route("/api/usage/user", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_user_usage():
    from controllers.api_usage import get_user_usage as get_user
    return get_user()

@app.route("/api/usage/company", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_company_usage():
    from controllers.api_usage import get_company_usage as get_company
    return get_company()

@app.route("/api/usage/detailed", methods=["GET"])
@login_required
@log_function_call(server_logger)
def get_detailed_usage():
    from controllers.api_usage import get_detailed_usage as get_detailed
    return get_detailed()

@app.route("/api/usage/migrate-rag-tokens", methods=["POST"])
@login_required
@log_function_call(server_logger)
def migrate_rag_tokens():
    from controllers.api_usage import migrate_rag_tokens as migrate_rag
    return migrate_rag()

@app.route("/usage", methods=["GET"])
@login_required
@log_function_call(server_logger)
def usage_dashboard():
    """Admin-only API usage dashboard"""
    from scheduler.decorators import is_admin_user
    
    if not is_admin_user(current_user):
        return jsonify({
            'success': False,
            'error': 'Admin access required'
        }), 403
    
    # Get user permissions and company info
    user_permissions = {}
    selected_company = current_user.company_id or 'haval'
    
    # Check if user has specific permissions
    if hasattr(current_user, 'permissions'):
        user_permissions = current_user.permissions
    
    return render_template('usage_dashboard.html',
        is_admin=is_admin_user(current_user),
        user_permissions=user_permissions,
        selected_company=selected_company
    )

# Dealership API Routes
@app.route("/api/dealership/tyre-complaints")
@login_required
@log_function_call(server_logger)
def api_tyre_complaints():
    import controllers.dealership as dealership
    return dealership.api_tyre_complaints()

@app.route("/api/dealership/stats")
@login_required
@log_function_call(server_logger)
def api_dealership_stats():
    import controllers.dealership as dealership
    return dealership.api_dealership_stats()

@app.route("/api/dealership/export")
@login_required
@log_function_call(server_logger)
def export_dealership_data():
    import controllers.dealership as dealership
    return dealership.export_data()

@app.route("/api/ai-analysis", methods=["POST"])
@login_required
@log_function_call(server_logger)
def ai_analysis_query():
    """Direct AI analysis endpoint for intelligent query processing"""
    try:
        data = request.get_json(force=True) or {}
        query = (data.get("query") or "").strip()
        
        if not query:
            return jsonify({"answer": "Please provide a query for analysis."})
        
        from controllers.ai_analysis import ai_analyze_query
        from models import get_db_connection
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Use AI analysis for intelligent responses
        answer = ai_analyze_query(query, cur)
        conn.close()
        
        return jsonify({
            "answer": answer,
            "structured": {"references": [], "charts": [], "tables": [], "recommendations": []}
        })
        
    except Exception as e:
        log_error(e, f"AI Analysis error for user {current_user.username}")
        return jsonify({
            "answer": "Sorry, the AI analysis encountered an error. Please try again."
        })

@app.route("/api/logs")
@login_required
@log_function_call(server_logger)
def get_logs():
    return api.get_logs()

@app.route("/api/logs/stream")
@login_required
@log_function_call(server_logger)
def stream_logs():
    return api.stream_logs()

# Analytics Routes
@app.route("/analysis")
@login_required
@log_function_call(server_logger)
def analysis():
    return analytics.analysis_new()

@app.route("/lucid-analytics")
@login_required
@log_function_call(server_logger)
def lucid_analytics_route():
    return analytics.lucid_analytics()

@app.route("/generate_report", methods=['GET', 'POST'])
@login_required
@log_function_call(server_logger)
def generate_report():
    return analytics.generate_report()

@app.route("/generate_report_charts", methods=['POST'])
@login_required
@log_function_call(server_logger)
def generate_report_charts():
    return analytics.generate_report_charts()

@app.route("/api/analytics/source", methods=['GET'])
@login_required
@log_function_call(server_logger)
def get_analytics_by_source():
    return analytics.get_analytics_by_source()

@app.route("/api/analytics/complaints", methods=['GET'])
@login_required
@log_function_call(server_logger)
def get_recent_complaints():
    return analytics.get_recent_complaints()

@app.route("/api/analytics/queries", methods=['GET'])
@login_required
@log_function_call(server_logger)
def get_recent_queries():
    return analytics.get_recent_queries()

@app.route("/api/analytics/report", methods=['GET'])
@login_required
@log_function_call(server_logger)
def api_generate_report():
    return analytics.api_generate_report()

@app.route("/db_summary")
@login_required
@log_function_call(server_logger)
def db_summary():
    return analytics.db_summary()

@app.route("/api/conversation/pakwheels/<author>", methods=['GET'])
@login_required
@log_function_call(server_logger)
def get_pakwheels_conversation(author):
    return analytics.get_pakwheels_conversation(author)

@app.route("/api/conversation/whatsapp/<customer_name>", methods=['GET'])
@login_required
@log_function_call(server_logger)
def get_whatsapp_conversation(customer_name):
    return analytics.get_whatsapp_conversation(customer_name)

# WhatsApp Routes
@app.route("/view_whatsapp")
@login_required
@log_function_call(server_logger)
def view_whatsapp():
    return whatsapp.view_whatsapp()

@app.route("/api/whatsapp/stats")
@login_required
@log_function_call(server_logger)
def get_whatsapp_stats_api():
    return whatsapp.get_whatsapp_stats_api()

@app.route("/api/whatsapp/conversations")
@login_required
@log_function_call(server_logger)
def get_whatsapp_conversations_api():
    return whatsapp.get_whatsapp_conversations_api()

@app.route("/debug_whatsapp")
@login_required
@log_function_call(server_logger)
def debug_whatsapp():
    return whatsapp.debug_whatsapp()

@app.route("/view_whatsapp/<path:customer_name>")
@login_required
@log_function_call(server_logger)
def view_whatsapp_by_customer(customer_name):
    return whatsapp.view_whatsapp_by_customer(customer_name)

@app.route("/view_pakwheels_conversation/<path:author>")
@login_required
@log_function_call(server_logger)
def view_pakwheels_conversation(author):
    return analytics.view_pakwheels_conversation(author)

@app.route("/api/conversation/reddit/<author>", methods=['GET'])
@login_required
@log_function_call(server_logger)
def get_reddit_conversation(author):
    return analytics.get_reddit_conversation(author)

@app.route("/view_reddit_conversation/<path:author>")
@login_required
@log_function_call(server_logger)
def view_reddit_conversation(author):
    return analytics.view_reddit_conversation(author)

@app.route("/view_all_complaints")
@login_required
@log_function_call(server_logger)
def view_all_complaints():
    return analytics.view_all_complaints()

@app.route("/view_whatsapp_by_customer/<path:customer_name>")
@login_required
@log_function_call(server_logger)
def view_whatsapp_conversation_detail(customer_name):
    return whatsapp.view_whatsapp_by_customer(customer_name)

@app.route("/view_whatsapp_conversations")
@login_required
@log_function_call(server_logger)
def view_whatsapp_conversations():
    return whatsapp.view_whatsapp_conversations()

@app.route("/view_whatsapp_conversation/<path:customer_name>/<conversation_date>")
@login_required
@log_function_call(server_logger)
def view_whatsapp_conversation(customer_name, conversation_date):
    return whatsapp.view_whatsapp_conversation(customer_name, conversation_date)

@app.route("/view_whatsapp_chat")
@login_required
@log_function_call(server_logger)
def view_whatsapp_chat():
    return whatsapp.view_whatsapp_chat()

@app.route("/fetch_wati_data", methods=["POST"])
@login_required
@log_function_call(server_logger)
def fetch_wati_data():
    return whatsapp.fetch_wati_data()

# Facebook Routes
@app.route("/view_facebook")
@login_required
@log_function_call(server_logger)
def view_facebook():
    return facebook.view_facebook()

@app.route("/api/facebook/posts")
@login_required
@log_function_call(server_logger)
def api_facebook_posts():
    return facebook.api_facebook_posts()

@app.route("/api/facebook/stats")
@login_required
@log_function_call(server_logger)
def api_facebook_stats():
    return facebook.api_facebook_stats()

@app.route("/api/facebook/insights")
@login_required
@log_function_call(server_logger)
def api_facebook_issue_insights():
    return facebook.api_facebook_issue_insights()

@app.route("/api/facebook/process", methods=["POST"])
@login_required
@log_function_call(server_logger)
def api_process_facebook_data():
    return facebook.api_process_facebook_data()

# Email Dashboard Route
@app.route("/email/dashboard")
@login_required
@log_function_call(server_logger)
def email_dashboard():
    """Render email intelligence dashboard"""
    from flask import render_template
    return render_template('email_dashboard.html', user=current_user)

# Settings Routes
@app.route("/settings")
@login_required
@log_function_call(server_logger)
def settings_page():
    return settings.settings_page()

@app.route("/update_settings", methods=["POST"])
@login_required
@log_function_call(server_logger)
def update_settings():
    return settings.update_settings()

@app.route("/api/settings")
@login_required
@log_function_call(server_logger)
def get_settings_api():
    return settings.get_settings_api()

@app.route("/reset_settings", methods=["POST"])
@login_required
@log_function_call(server_logger)
def reset_settings():
    return settings.reset_settings()

@app.route("/export_settings")
@login_required
@log_function_call(server_logger)
def export_settings():
    return settings.export_settings()

@app.route("/import_settings", methods=["POST"])
@login_required
@log_function_call(server_logger)
def import_settings():
    return settings.import_settings()

@app.route("/restart_server", methods=["POST"])
@login_required
@log_function_call(server_logger)
def restart_server():
    return settings.restart_server()

# Logging Management API Routes
@app.route("/api/logging_status")
@login_required
@log_function_call(server_logger)
def get_logging_status():
    return settings.get_logging_status()

@app.route("/api/rotate_logs", methods=["POST"])
@login_required
@log_function_call(server_logger)
def rotate_logs():
    return settings.rotate_logs()

@app.route("/api/cleanup_logs", methods=["POST"])
@login_required
@log_function_call(server_logger)
def cleanup_logs():
    return settings.cleanup_logs()

@app.route("/api/set_logger_level", methods=["POST"])
@login_required
@log_function_call(server_logger)
def set_logger_level():
    return settings.set_logger_level()

@app.route("/api/download_log")
@login_required
@log_function_call(server_logger)
def download_log_file():
    return settings.download_log_file()

# ============================================
# QUICK QUESTIONS API ENDPOINTS
# ============================================

QUICK_QUESTIONS_FILE = os.path.join(DATA_DIR, 'quick_questions.txt')

def load_quick_questions():
    """Load quick questions from both default config and user additions"""
    try:
        import json
        import os

        # Load default questions from config
        default_questions = {}
        config_file = "config/quick_Q_A.json"
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                default_questions = json.load(f)
        
        # Load user-added questions
        user_questions = {}
        if os.path.exists(QUICK_QUESTIONS_FILE):
            with open(QUICK_QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content and not content.startswith('#'):
                    try:
                        user_questions = json.loads(content)
                    except json.JSONDecodeError:
                        # Try line-by-line format (legacy)
                        f.seek(0)
                        legacy_questions = []
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                try:
                                    question = json.loads(line)
                                    legacy_questions.append(question)
                                except json.JSONDecodeError:
                                    continue
                        # Convert legacy format to new format
                        user_questions = {}
                        for q in legacy_questions:
                            mode = q.get('mode', 'pakwheels')
                            if mode not in user_questions:
                                user_questions[mode] = []
                            user_questions[mode].append(q)
        
        # Combine default and user questions for each mode
        all_questions = []
        for mode in ['pakwheels', 'whatsapp', 'dealership', 'facebook', 'finance', 'supplychain', 'reddit', 'lucid', 'reddit_lucid', 'cross_platform', 'insights']:
            # Get default questions for this mode
            mode_defaults = default_questions.get(mode, [])
            
            # Get user questions for this mode
            mode_user_questions = user_questions.get(mode, [])
            
            # Add default questions
            for i, default_q in enumerate(mode_defaults):
                all_questions.append({
                    'id': f"{mode}_default_{i}",
                    'question': default_q,
                    'mode': mode,
                    'user_id': 'system',
                    'is_default': True,
                    'timestamp': '2024-01-01T00:00:00Z'
                })
            
            # Add user questions
            for i, user_q in enumerate(mode_user_questions):
                if isinstance(user_q, dict):
                    all_questions.append({
                        'id': user_q.get('id', f"{mode}_user_{i}"),
                        'question': user_q.get('question', user_q.get('text', '')),
                        'mode': mode,
                        'user_id': user_q.get('user_id', 'unknown'),
                        'is_default': False,
                        'timestamp': user_q.get('timestamp', '2024-01-01T00:00:00Z')
                    })
                elif isinstance(user_q, str):
                    all_questions.append({
                        'id': f"{mode}_user_{i}",
                        'question': user_q,
                        'mode': mode,
                        'user_id': 'unknown',
                        'is_default': False,
                        'timestamp': '2024-01-01T00:00:00Z'
                    })
        
        return all_questions
        
    except Exception as e:
        server_logger.error(f"Error loading quick questions: {e}")
        return []

def save_quick_questions(questions):
    """Save user-added quick questions (excluding defaults)"""
    try:
        import json
        import os

        # Filter out default questions and organize by mode
        user_questions_by_mode = {}
        
        for question in questions:
            if not question.get('is_default', False):
                mode = question.get('mode', 'pakwheels')
                if mode not in user_questions_by_mode:
                    user_questions_by_mode[mode] = []
                
                user_questions_by_mode[mode].append({
                    'id': question.get('id'),
                    'question': question.get('question'),
                    'user_id': question.get('user_id'),
                    'timestamp': question.get('timestamp')
                })
        
        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # Save user questions in new JSON format
        with open(QUICK_QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_questions_by_mode, f, indent=2, ensure_ascii=False)
        
        return True
        
    except Exception as e:
        server_logger.error(f"Error saving quick questions: {e}")
        return False

@app.route("/api/quick-questions/add", methods=["POST"])
@login_required
@log_function_call(server_logger)
def add_quick_question():
    """Add a new quick question"""
    try:
        data = request.get_json()
        question_text = data.get('question', '').strip()
        mode = data.get('mode', 'pakwheels')
        
        if not question_text:
            return jsonify({"success": False, "error": "Question text is required"})
        
        # Load existing questions
        questions = load_quick_questions()
        
        # Filter user questions for this mode to get next ID
        user_questions_for_mode = [
            q for q in questions 
            if not q.get('is_default', False) and q.get('mode') == mode
        ]
        
        # Generate new ID (string format to match the enhanced system)
        next_user_id = len(user_questions_for_mode)
        new_id = f"{mode}_user_{next_user_id}"
        
        # Ensure unique ID
        existing_ids = [q.get('id') for q in questions if q.get('id')]
        while new_id in existing_ids:
            next_user_id += 1
            new_id = f"{mode}_user_{next_user_id}"
        
        # Add new question (using the enhanced system format)
        new_question = {
            'id': new_id,
            'question': question_text,  # Use 'question' not 'text'
            'mode': mode,
            'user_id': str(current_user.id),  # Convert to string
            'is_default': False,
            'timestamp': datetime.now().isoformat()  # Use 'timestamp' not 'created_at'
        }
        
        questions.append(new_question)
        
        # Save to file
        if save_quick_questions(questions):
            server_logger.info(f"Quick question added by {current_user.username}: {question_text}")
            return jsonify({"success": True, "question": new_question})
        else:
            return jsonify({"success": False, "error": "Failed to save question"})
            
    except Exception as e:
        log_error(e, "Error adding quick question")
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/quick-questions/list", methods=["GET"])
@login_required
@log_function_call(server_logger)
def list_quick_questions():
    """List quick questions for current user and mode"""
    try:
        mode = request.args.get('mode', 'pakwheels')
        limit = int(request.args.get('limit', 100))  # Support up to 100 questions
        
        # Load all questions
        all_questions = load_quick_questions()
        
        # Debug logging
        server_logger.info(f"[QuickQ] Total questions loaded: {len(all_questions)}")
        server_logger.info(f"[QuickQ] Requested mode: {mode}")
        
        # Filter by mode (include both default and user questions)
        mode_questions = [
            q for q in all_questions 
            if q.get('mode') == mode
        ]
        
        server_logger.info(f"[QuickQ] Questions for mode '{mode}': {len(mode_questions)}")
        if mode_questions:
            server_logger.info(f"[QuickQ] First question: {mode_questions[0].get('question', 'N/A')[:100]}")
        
        # Sort questions: defaults first, then user questions by timestamp
        mode_questions.sort(key=lambda x: (
            not x.get('is_default', False),  # Defaults first (False sorts before True)
            x.get('timestamp', '2024-01-01T00:00:00Z')
        ))
        
        # Limit to requested number of questions
        limited_questions = mode_questions[:limit]
        
        # Add display information
        for q in limited_questions:
            q['can_edit'] = not q.get('is_default', False) and str(q.get('user_id')) == str(current_user.id)
            q['can_delete'] = not q.get('is_default', False) and str(q.get('user_id')) == str(current_user.id)
        
        return jsonify({
            "success": True, 
            "questions": limited_questions,
            "total_count": len(mode_questions),
            "default_count": len([q for q in mode_questions if q.get('is_default', False)]),
            "user_count": len([q for q in mode_questions if not q.get('is_default', False)]),
            "mode": mode
        })
        
    except Exception as e:
        log_error(e, "Error listing quick questions")
        return jsonify({"success": False, "error": str(e), "questions": []})

@app.route("/api/quick-questions/edit", methods=["POST"])
@login_required
@log_function_call(server_logger)
def edit_quick_question():
    """Edit an existing quick question"""
    try:
        data = request.get_json()
        question_id = data.get('id')
        new_text = data.get('question', '').strip()
        
        if not question_id or not new_text:
            return jsonify({"success": False, "error": "Question ID and text are required"})
        
        # Load existing questions
        questions = load_quick_questions()
        
        # Find and update the question
        updated = False
        for q in questions:
            if (q.get('id') == question_id and 
                str(q.get('user_id')) == str(current_user.id) and 
                not q.get('is_default', False)):
                q['question'] = new_text  # Use 'question' not 'text'
                q['timestamp'] = datetime.now().isoformat()  # Update timestamp
                updated = True
                break
        
        if not updated:
            return jsonify({"success": False, "error": "Question not found or access denied"})
        
        # Save to file
        if save_quick_questions(questions):
            server_logger.info(f"Quick question {question_id} updated by {current_user.username}")
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to save changes"})
            
    except Exception as e:
        log_error(e, "Error editing quick question")
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/quick-questions/delete", methods=["POST"])
@login_required
@log_function_call(server_logger)
def delete_quick_question():
    """Delete a quick question"""
    try:
        data = request.get_json()
        question_id = data.get('id')
        
        if not question_id:
            return jsonify({"success": False, "error": "Question ID is required"})
        
        # Load existing questions
        questions = load_quick_questions()
        
        # Filter out the question to delete (only if it belongs to current user and is not default)
        original_count = len(questions)
        questions = [
            q for q in questions 
            if not (q.get('id') == question_id and 
                   str(q.get('user_id')) == str(current_user.id) and 
                   not q.get('is_default', False))
        ]
        
        if len(questions) == original_count:
            return jsonify({"success": False, "error": "Question not found or access denied"})
        
        # Save to file
        if save_quick_questions(questions):
            server_logger.info(f"Quick question {question_id} deleted by {current_user.username}")
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to save changes"})
            
    except Exception as e:
        log_error(e, "Error deleting quick question")
        return jsonify({"success": False, "error": str(e)})

@app.route("/scrape_manual_reddit_url", methods=["POST"])
@login_required
@log_function_call(server_logger)
def scrape_manual_reddit_url():
    """Scrape a specific Reddit URL manually with complete pipeline processing"""
    import re
    import time

    try:
        manual_url = request.form.get('manual_url', '').strip()
        max_posts = int(request.form.get('max_posts', 100))
        fetch_mode = request.form.get('fetch_mode', 'latest')

        if not manual_url:
            return jsonify({
                "success": False,
                "error": "URL is required",
                "validation_error": True
            })

        # Validate Reddit URL format
        subreddit_pattern = r'^r/[a-zA-Z0-9_]+$'
        subreddit_url_pattern = r'^https?://(www\.)?reddit\.com/r/[a-zA-Z0-9_]+/?$'
        post_url_pattern = r'^https?://(www\.)?reddit\.com/r/[a-zA-Z0-9_]+/comments/[a-zA-Z0-9_]+'

        if not (re.match(subreddit_pattern, manual_url) or
                re.match(subreddit_url_pattern, manual_url) or
                re.match(post_url_pattern, manual_url)):
            return jsonify({
                "success": False,
                "error": "Invalid Reddit URL format. Use: r/subreddit or https://reddit.com/r/subreddit/...",
                "validation_error": True
            })

        # Convert r/subreddit format to full URL if needed
        if manual_url.startswith('r/'):
            manual_url = f"https://www.reddit.com/{manual_url}/"

        # Normalize URL to have trailing slash
        if not manual_url.endswith('/') and '/comments/' not in manual_url:
            manual_url = manual_url + '/'

        # Get user's company and config
        user_company = current_user.company_id or 'haval'

        from config import get_company_config
        from controllers.scraping import (export_reddit_posts_to_files,
                                          save_reddit_posts_to_db,
                                          search_reddit_posts)
        from utils.scraped_urls_tracker import (load_scraped_reddit_urls,
                                                mark_reddit_url_as_scraped)

        try:
            company_config = get_company_config(user_company)
            company_name = company_config.full_name
            min_year = company_config.min_year if hasattr(company_config, 'min_year') else None
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"Error getting company configuration: {str(e)}"
            }), 500

        # Check if URL was previously scraped (informational only - we still allow re-scraping)
        was_previously_scraped = manual_url in load_scraped_reddit_urls(user_company)

        # Extract subreddit name from URL
        subreddit_match = re.search(r'reddit\.com/r/([a-zA-Z0-9_]+)', manual_url)
        subreddit = subreddit_match.group(1) if subreddit_match else None

        if not subreddit:
            return jsonify({
                "success": False,
                "error": "Could not extract subreddit from URL"
            }), 400

        rescrape_msg = " (re-scraping for new posts)" if was_previously_scraped else ""
        server_logger.info(f"[Manual Reddit] Starting scrape for {company_name}: r/{subreddit}{rescrape_msg}")

        start_time = time.time()

        # Search Reddit posts with min_year filter
        posts = search_reddit_posts(
            query=f"{company_name}",
            subreddit=subreddit,
            sort="new",
            time_filter="all",
            max_posts=max_posts,
            delay=0.5,
            include_comments=True,
            min_year=min_year  # Apply year filter
        )

        if not posts:
            server_logger.warning(f"[Manual Reddit] No posts found: r/{subreddit}")
            return jsonify({
                "success": False,
                "error": f"No posts found in r/{subreddit}. Try a different subreddit."
            }), 404

        # Save posts to database (post-level dedup happens here)
        saved_count, skipped_count = save_reddit_posts_to_db(
            query=f"manual_{subreddit}",
            posts=posts,
            user_id=current_user.id,
            company_id=user_company
        )

        # Export to files
        json_path, csv_path = export_reddit_posts_to_files(
            query=f"manual_{subreddit}",
            posts=posts,
            company_id=user_company
        )

        elapsed_time = time.time() - start_time
        total_comments = sum(post.get('total_comments_scraped', 0) for post in posts)

        server_logger.info(f"[Manual Reddit] Scraped {len(posts)} posts ({saved_count} new, {skipped_count} duplicates) in {elapsed_time:.1f}s")

        # Start complete pipeline
        if len(posts) > 0:
            try:
                from ai.haval_pipeline import start_haval_pipeline

                server_logger.info(f"[Manual Reddit] Starting complete pipeline for r/{subreddit}")

                start_haval_pipeline(
                    json_path=json_path,
                    topic_url=f"reddit_manual_{subreddit}",
                    sources="Reddit",
                    company_id=user_company
                )

                server_logger.info(f"[Manual Reddit] Pipeline completed successfully")

                # Mark URL as scraped ONLY after complete pipeline succeeds
                mark_reddit_url_as_scraped(user_company, manual_url)
                server_logger.info(f"[Manual Reddit] Marked URL as scraped: {manual_url}")

                return jsonify({
                    "success": True,
                    "message": f"Successfully scraped r/{subreddit}: {len(posts)} posts ({saved_count} new, {skipped_count} duplicates)",
                    "posts_scraped": len(posts),
                    "posts_saved": saved_count,
                    "posts_skipped": skipped_count,
                    "comments_scraped": total_comments,
                    "was_rescrape": was_previously_scraped,
                    "elapsed_time": round(elapsed_time, 1),
                    "url": manual_url
                })

            except Exception as e:
                server_logger.error(f"[Manual Reddit] Pipeline failed for r/{subreddit}: {e}")
                return jsonify({
                    "success": False,
                    "error": f"Scraping succeeded but pipeline failed: {str(e)}",
                    "partial_success": True,
                    "posts_scraped": len(posts)
                }), 500

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": f"Invalid input: {str(e)}",
            "validation_error": True
        })
    except Exception as e:
        log_error(e, "Error in manual Reddit URL scraping")
        return jsonify({
            "success": False,
            "error": str(e)
        })

# Error handlers
@app.errorhandler(404)
@log_function_call(server_logger)
def not_found_error(error):
    server_logger.warning(f"404 error: {error}")
    return render_template('error.html',
        error_code='404',
        error_message='Page Not Found',
        error_description='The page you are looking for does not exist. It may have been moved or deleted.'
    ), 404

@app.errorhandler(500)
@log_function_call(server_logger)
def internal_error(error):
    log_error(error, "Internal server error")
    return render_template('error.html',
        error_code='500',
        error_message='Internal Server Error',
        error_description='Something went wrong on our end. Our team has been notified and is working to fix it.'
    ), 500

# ----------------------
# Pipeline Pre-Warming
# ----------------------

def prewarm_pipelines():
    """
    Pre-initialize DMS and RAG pipelines at app startup.
    This prevents the ~35s delay on first user query.
    """
    from ai.pipeline_manager import PipelineManager
    from config.companies import COMPANIES, get_company_config

    server_logger.info("[Pre-Warm] Starting pipeline pre-initialization...")
    start_time = datetime.now()

    # Pre-download ChromaDB embedding model (ONNX all-MiniLM-L6-v2)
    # This model is downloaded on first ChromaDB query, so we trigger it at startup
    try:
        server_logger.info("[Pre-Warm] Downloading ChromaDB embedding model...")
        from ai.rag_engine.semantic_cache import SemanticCache
        temp_cache = SemanticCache(
            persist_directory="./data/semantic_cache_prewarm",
            collection_name="prewarm_temp"
        )
        # Trigger embedding model download by doing a dummy query
        temp_cache.collection.query(query_texts=["test"], n_results=1)
        server_logger.info("[Pre-Warm] ✓ ChromaDB embedding model ready")
    except Exception as e:
        server_logger.warning(f"[Pre-Warm] ⚠ Failed to pre-download embedding model: {e}")

    # Initialize Haval pipeline (loads all vector stores including Lucid)
    try:
        server_logger.info("[Pre-Warm] Initializing Haval pipeline and vector stores...")
        from ai.haval_pipeline import get_pipeline_status
        status = get_pipeline_status()
        server_logger.info("[Pre-Warm] ✓ Haval pipeline initialized")
    except Exception as e:
        server_logger.warning(f"[Pre-Warm] ⚠ Failed to initialize Haval pipeline: {e}")

    pipeline_manager = PipelineManager()

    # Pre-warm DMS pipelines for companies with DMS enabled (skip dummy DMS)
    for company_id, company_config in COMPANIES.items():
        if company_config.has_dms:
            # Skip dummy DMS - doesn't need prewarming
            dms_type = getattr(company_config, 'dms_type', 'production')
            if dms_type == 'dummy':
                server_logger.info(f"[Pre-Warm] Skipping dummy DMS for {company_id}")
                continue

            try:
                dms_data_source = getattr(company_config, 'dms_data_source', 'mssql')
                server_logger.info(f"[Pre-Warm] Initializing DMS pipeline for {company_id} ({dms_data_source})...")

                pipeline_manager.get_dms_pipeline(
                    company_id=company_id,
                    db_path=company_config.dms_db_path,
                    dealer_id=company_config.dms_dealer_id,
                    db_config=company_config.dms_db_config if dms_data_source == "mssql" else None,
                    dms_data_source=dms_data_source,
                    enable_tier0=True,
                    enable_tier1=True,
                    enable_tier2=True,
                    enable_tier3=True,
                    enable_semantic_cache=True,
                    enable_follow_ups=True,
                    verbose=False
                )
                server_logger.info(f"[Pre-Warm] ✓ DMS pipeline ready for {company_id}")
            except Exception as e:
                server_logger.warning(f"[Pre-Warm] ⚠ Failed to pre-warm DMS for {company_id}: {e}")

    elapsed = (datetime.now() - start_time).total_seconds()
    server_logger.info(f"[Pre-Warm] ✓ All pipelines initialized ({elapsed:.1f}s)")


# ----------------------
# Application Entry Point
# ----------------------

if __name__ == "__main__":
    import logging

    # Get server configuration
    server_config = config.get_server_config()

    # Suppress SSL handshake errors and reduce noise
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    # Display startup information
    server_logger.info("="*70)
    server_logger.info(f"{config.get('app.name', 'Haval Marketing Tool')} - Version {config.get('app.version', '2.0')}")
    server_logger.info("="*70)
    server_logger.info("Server starting...")
    server_logger.info(f"Open your browser to: http://{server_config['host']}:{server_config['port']}/")
    server_logger.info(f"Debug mode: {server_config['debug']}")
    server_logger.info(f"Auto-reload: {server_config.get('use_reloader', False)}")
    server_logger.info(f"Threading: {server_config.get('threaded', True)}")
    server_logger.info("="*70)

    # Pre-warm pipelines before accepting requests (only in non-debug mode or first run)
    # Skip prewarming if DISABLE_PREWARM is set to 'true' (useful for local testing without MSSQL)
    disable_prewarm = os.getenv('DISABLE_PREWARM', 'false').lower() == 'true'
    if not disable_prewarm and (not server_config.get('use_reloader', False) or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'):
        try:
            prewarm_pipelines()
        except Exception as e:
            server_logger.error(f"[Pre-Warm] Critical error during prewarming: {e}")
            server_logger.warning("[Pre-Warm] Continuing without prewarming - pipelines will initialize on first use")

    try:
        # Start Flask application with configuration
        app.run(**server_config)
    except KeyboardInterrupt:
        server_logger.info("Server shutdown requested")

        # Shutdown scheduler gracefully
        if scheduler_manager:
            try:
                scheduler_manager.shutdown()
                server_logger.info("Scheduler shutdown complete")
            except Exception as e:
                server_logger.error(f"Error shutting down scheduler: {e}")

        # Restore original stdout/stderr
        try:
            if hasattr(sys.stdout, 'original_stream'):
                sys.stdout = sys.stdout.original_stream
            if hasattr(sys.stderr, 'original_stream'):
                sys.stderr = sys.stderr.original_stream
        except:
            pass
    except Exception as e:
        log_error(e, "Failed to start Flask application")
        # Restore original stdout/stderr on error
        try:
            if 'original_stdout' in locals():
                sys.stdout = original_stdout
            if 'original_stderr' in locals():
                sys.stderr = original_stderr
        except:
            pass
        raise

