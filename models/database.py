import os
import sqlite3
import threading

# Thread-local storage for database connections
local_storage = threading.local()

# Database configuration
DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "posts.db")

def get_db_connection():
    """Get fresh database connection"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize main application database with all necessary tables"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        company_id TEXT DEFAULT 'haval',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE,
        is_verified BOOLEAN DEFAULT FALSE,
        otp_code TEXT,
        otp_expiry TIMESTAMP,
        reset_otp TEXT,
        reset_otp_expiry TIMESTAMP
    )
    """)
    
    # Add company_id column to existing users table if it doesn't exist
    try:
        cur.execute("ALTER TABLE users ADD COLUMN company_id TEXT DEFAULT 'haval'")
        print("[DB] Added company_id column to users table")
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    # Add is_verified column if it doesn't exist (keep this - used for user verification)
    try:
        cur.execute("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE")
        print("[DB] Added is_verified column to users table")
    except sqlite3.OperationalError:
        pass
    
    # Add data source permission columns
    data_sources = [
        'pakwheels', 'reddit', 'whatsapp', 'cross_platform', 
        'dealership', 'finance', 'facebook', 'supplychain', 'insights', 'lucid', 'reddit_lucid'
    ]
    
    for source in data_sources:
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN perm_{source} BOOLEAN DEFAULT TRUE")
            print(f"[DB] Added perm_{source} column to users table")
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    # Sessions table for better session management
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        session_token TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
    
    # Posts table (user-specific data)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        category TEXT,
        topic_title TEXT,
        topic_url TEXT,
        post_number INTEGER,
        author TEXT,
        created_at TEXT,
        cooked_text TEXT,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
    
    # Search results table (user-specific data)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS search_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        search_query TEXT,
        topic_title TEXT,
        topic_url TEXT,
        post_number INTEGER,
        author TEXT,
        created_at TEXT,
        post_text TEXT,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
    
    # WhatsApp messages table (shared data - no user_id needed)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS whatsapp_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT,
        country_code INTEGER,
        contact_number INTEGER,
        message_type TEXT,
        message TEXT,
        timestamp TEXT,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        sender TEXT DEFAULT 'customer',
        company_id TEXT DEFAULT 'haval'
    )
    """)
    
    # Migration: Add company_id column to whatsapp_messages if it doesn't exist
    try:
        cur.execute("ALTER TABLE whatsapp_messages ADD COLUMN company_id TEXT DEFAULT 'haval'")
        print("✅ Added company_id column to whatsapp_messages table")
    except sqlite3.OperationalError:
        # Column already exists
        pass

    # Migration: Add sender column if it doesn't exist
    try:
        cur.execute("ALTER TABLE whatsapp_messages ADD COLUMN sender TEXT DEFAULT 'customer'")
        print("✅ Added sender column to whatsapp_messages table")
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    # Chat history table (user-specific)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        session_id TEXT,
        mode TEXT DEFAULT 'pakwheels',
        query TEXT,
        response TEXT,
        structured_data TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
    
    # Migration: Add structured_data column if it doesn't exist
    try:
        cur.execute("SELECT structured_data FROM chat_history LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding structured_data column to chat_history table...")
        cur.execute("ALTER TABLE chat_history ADD COLUMN structured_data TEXT")
        print("✅ Added structured_data column to chat_history table")
    
    # Issues tables (shared data - no user_id needed)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS issues (
        id INTEGER PRIMARY KEY,
        platform_reference TEXT,
        issue_type TEXT,
        exact_issue_description TEXT,
        severity_estimate TEXT,
        first_seen_public_example TEXT,
        recommended_action TEXT,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS facebook_issues (
        id INTEGER PRIMARY KEY,
        platform_reference TEXT,
        issue_type TEXT,
        exact_issue_description TEXT,
        severity_estimate TEXT,
        first_seen_public_example TEXT,
        user_name TEXT,
        reference_link TEXT,
        recommended_action TEXT,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # System settings table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Migration: Add post_number column if it doesn't exist
    try:
        cur.execute("SELECT post_number FROM posts LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding missing post_number column to posts table...")
        cur.execute("ALTER TABLE posts ADD COLUMN post_number INTEGER")
        print("✅ Added post_number column")

    # Migration: Add company_id column if it doesn't exist
    try:
        cur.execute("SELECT company_id FROM posts LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding missing company_id column to posts table...")
        cur.execute("ALTER TABLE posts ADD COLUMN company_id TEXT DEFAULT 'haval'")
        print("✅ Added company_id column to posts table")

    # Migration: Add company_id column to search_results if it doesn't exist
    try:
        cur.execute("SELECT company_id FROM search_results LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding missing company_id column to search_results table...")
        cur.execute("ALTER TABLE search_results ADD COLUMN company_id TEXT DEFAULT 'haval'")
        print("✅ Added company_id column to search_results table")

    try:
        cur.execute("SELECT complaint_category FROM posts LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding complaint_category column to posts table...")
        cur.execute("ALTER TABLE posts ADD COLUMN complaint_category TEXT DEFAULT 'none'")
        print("✅ Added complaint_category column to posts table")

    try:
        cur.execute("SELECT car_name FROM posts LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding car_name column to posts table...")
        cur.execute("ALTER TABLE posts ADD COLUMN car_name TEXT DEFAULT 'none'")
        print("✅ Added car_name column to posts table")

    try:
        cur.execute("SELECT complaint_category FROM whatsapp_messages LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding complaint_category column to whatsapp_messages table...")
        cur.execute("ALTER TABLE whatsapp_messages ADD COLUMN complaint_category TEXT DEFAULT 'none'")
        print("✅ Added complaint_category column to whatsapp_messages table")

    try:
        cur.execute("SELECT car_name FROM whatsapp_messages LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding car_name column to whatsapp_messages table...")
        cur.execute("ALTER TABLE whatsapp_messages ADD COLUMN car_name TEXT DEFAULT 'none'")
        print("✅ Added car_name column to whatsapp_messages table")

    # Migration: Add severity column to posts table
    try:
        cur.execute("SELECT severity FROM posts LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding severity column to posts table...")
        cur.execute("ALTER TABLE posts ADD COLUMN severity TEXT DEFAULT 'low'")
        print("✅ Added severity column to posts table")

    # Migration: Add severity column to whatsapp_messages table
    try:
        cur.execute("SELECT severity FROM whatsapp_messages LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding severity column to whatsapp_messages table...")
        cur.execute("ALTER TABLE whatsapp_messages ADD COLUMN severity TEXT DEFAULT 'low'")
        print("✅ Added severity column to whatsapp_messages table")

    # =========================================================================
    # USER PERMISSIONS & ADMIN CONTROL TABLES
    # =========================================================================

    # User data source permissions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_data_source_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        data_source TEXT NOT NULL,
        enabled BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        UNIQUE(user_id, data_source)
    )
    """)

    # Email blacklist for deleted users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS email_blacklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        reason TEXT DEFAULT 'user_deleted',
        deleted_by INTEGER,
        deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (deleted_by) REFERENCES users (id)
    )
    """)

    # Add soft delete columns to users table
    try:
        cur.execute('ALTER TABLE users ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE')
        print("✅ Added is_deleted column to users table")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cur.execute('ALTER TABLE users ADD COLUMN deleted_at TIMESTAMP')
        print("✅ Added deleted_at column to users table")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute('ALTER TABLE users ADD COLUMN deleted_by INTEGER')
        print("✅ Added deleted_by column to users table")
    except sqlite3.OperationalError:
        pass

    # =========================================================================
    # GROUP CHAT TABLES
    # =========================================================================

    # Groups table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        creator_id INTEGER NOT NULL,
        session_id TEXT,
        mode TEXT DEFAULT 'pakwheels',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (creator_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # Group members table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS group_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id TEXT NOT NULL,
        user_id INTEGER,
        email TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL,
        UNIQUE(group_id, email)
    )
    """)

    # Group messages table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS group_messages (
        id TEXT PRIMARY KEY,
        group_id TEXT NOT NULL,
        sender_id INTEGER,
        sender_name TEXT,
        message TEXT NOT NULL,
        structured_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE CASCADE,
        FOREIGN KEY (sender_id) REFERENCES users (id) ON DELETE SET NULL
    )
    """)

    # Migration: Add structured_data column to group_messages if it doesn't exist
    try:
        cur.execute("SELECT structured_data FROM group_messages LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding structured_data column to group_messages table...")
        cur.execute("ALTER TABLE group_messages ADD COLUMN structured_data TEXT")
        print("✅ Added structured_data column to group_messages table")

    # Create indexes for performance
    cur.execute('CREATE INDEX IF NOT EXISTS idx_user_permissions_user_source ON user_data_source_permissions(user_id, data_source)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_email_blacklist_email ON email_blacklist(email)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_users_is_deleted ON users(is_deleted)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_groups_creator ON groups(creator_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_group_messages_group ON group_messages(group_id)')

    # =========================================================================
    # API USAGE TRACKING TABLE
    # =========================================================================

    # API usage table for tracking LLM and embedding token usage
    cur.execute("""
    CREATE TABLE IF NOT EXISTS api_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        company_id TEXT DEFAULT 'haval',
        api_type TEXT NOT NULL,
        model_name TEXT,
        operation TEXT,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        cost REAL DEFAULT 0.0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
    )
    """)

    # Create indexes for api_usage table
    cur.execute('CREATE INDEX IF NOT EXISTS idx_api_usage_user ON api_usage(user_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_api_usage_company ON api_usage(company_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_api_usage_type ON api_usage(api_type)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(timestamp)')

    conn.commit()
    conn.close()

def get_user_data_dir(user_id):
    """Get user-specific data directory"""
    user_data_dir = os.path.join(DATA_DIR, f"user_{user_id}")
    os.makedirs(user_data_dir, exist_ok=True)
    return user_data_dir