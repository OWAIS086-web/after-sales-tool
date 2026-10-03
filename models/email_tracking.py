"""
Email Tracking Database Models
Stores email indexing metadata and OAuth token information
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.logger import log_error


class EmailTrackingDB:
    """
    Database for tracking indexed emails and OAuth tokens
    """
    
    def __init__(self, db_path: str = "data/email_tracking.db"):
        """
        Initialize Email Tracking Database
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database tables
        self._init_db()
    
    def _init_db(self):
        """Create database tables if they don't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create indexed_emails table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS indexed_emails (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        email_id TEXT NOT NULL,
                        gmail_message_id TEXT NOT NULL,
                        subject TEXT,
                        sender TEXT,
                        date TEXT,
                        indexed_at TEXT NOT NULL,
                        UNIQUE(user_id, gmail_message_id)
                    )
                """)
                
                # Create oauth_connections table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS oauth_connections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT UNIQUE NOT NULL,
                        email_address TEXT,
                        connected_at TEXT NOT NULL,
                        last_sync_at TEXT,
                        is_active INTEGER DEFAULT 1,
                        total_emails_indexed INTEGER DEFAULT 0
                    )
                """)
                
                # Create indexing_sessions table for tracking batch operations
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS indexing_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        completed_at TEXT,
                        status TEXT DEFAULT 'in_progress',
                        emails_fetched INTEGER DEFAULT 0,
                        emails_indexed INTEGER DEFAULT 0,
                        error_message TEXT
                    )
                """)
                
                # Create indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_indexed_emails_user 
                    ON indexed_emails(user_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_indexed_emails_gmail_id 
                    ON indexed_emails(gmail_message_id)
                """)
                
                conn.commit()
                print("[Email Tracking DB] Database initialized successfully")
                
        except Exception as e:
            log_error(f"Error initializing database: {e}")
            raise
    
    # OAuth Connection Methods
    
    def create_oauth_connection(
        self,
        user_id: str,
        email_address: Optional[str] = None
    ) -> bool:
        """
        Create OAuth connection record
        
        Args:
            user_id: User identifier
            email_address: User's email address
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO oauth_connections 
                    (user_id, email_address, connected_at)
                    VALUES (?, ?, ?)
                """, (user_id, email_address, datetime.now().isoformat()))
                
                conn.commit()
                return True
                
        except Exception as e:
            log_error(f"Error creating OAuth connection: {e}")
            return False
    
    def update_last_sync(self, user_id: str) -> bool:
        """
        Update last sync timestamp
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE oauth_connections 
                    SET last_sync_at = ?
                    WHERE user_id = ?
                """, (datetime.now().isoformat(), user_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            log_error(f"Error updating last sync: {e}")
            return False
    
    def remove_oauth_connection(self, user_id: str) -> bool:
        """
        Remove OAuth connection (soft delete)
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE oauth_connections 
                    SET is_active = 0
                    WHERE user_id = ?
                """, (user_id,))
                
                conn.commit()
                return True
                
        except Exception as e:
            log_error(f"Error removing OAuth connection: {e}")
            return False
    
    def get_oauth_connection(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get OAuth connection details
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with connection details or None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM oauth_connections 
                    WHERE user_id = ? AND is_active = 1
                """, (user_id,))
                
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                
                return None
                
        except Exception as e:
            log_error(f"Error getting OAuth connection: {e}")
            return None
    
    # Indexed Emails Methods
    
    def add_indexed_email(
        self,
        user_id: str,
        email_id: str,
        gmail_message_id: str,
        subject: Optional[str] = None,
        sender: Optional[str] = None,
        date: Optional[str] = None
    ) -> bool:
        """
        Record indexed email
        
        Args:
            user_id: User identifier
            email_id: Internal email ID
            gmail_message_id: Gmail message ID
            subject: Email subject
            sender: Email sender
            date: Email date
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR IGNORE INTO indexed_emails 
                    (user_id, email_id, gmail_message_id, subject, sender, date, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    email_id,
                    gmail_message_id,
                    subject,
                    sender,
                    date,
                    datetime.now().isoformat()
                ))
                
                # Update total count
                cursor.execute("""
                    UPDATE oauth_connections 
                    SET total_emails_indexed = (
                        SELECT COUNT(*) FROM indexed_emails WHERE user_id = ?
                    )
                    WHERE user_id = ?
                """, (user_id, user_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            log_error(f"Error adding indexed email: {e}")
            return False
    
    def is_email_indexed(self, user_id: str, gmail_message_id: str) -> bool:
        """
        Check if email is already indexed
        
        Args:
            user_id: User identifier
            gmail_message_id: Gmail message ID
            
        Returns:
            True if indexed, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT COUNT(*) FROM indexed_emails 
                    WHERE user_id = ? AND gmail_message_id = ?
                """, (user_id, gmail_message_id))
                
                count = cursor.fetchone()[0]
                return count > 0
                
        except Exception as e:
            log_error(f"Error checking indexed email: {e}")
            return False
    
    def get_indexed_email_count(self, user_id: str) -> int:
        """
        Get count of indexed emails for user
        
        Args:
            user_id: User identifier
            
        Returns:
            Count of indexed emails
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT COUNT(*) FROM indexed_emails 
                    WHERE user_id = ?
                """, (user_id,))
                
                count = cursor.fetchone()[0]
                return count
                
        except Exception as e:
            log_error(f"Error getting indexed email count: {e}")
            return 0
    
    def get_indexed_emails(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get list of indexed emails
        
        Args:
            user_id: User identifier
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of indexed email dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM indexed_emails 
                    WHERE user_id = ?
                    ORDER BY indexed_at DESC
                    LIMIT ? OFFSET ?
                """, (user_id, limit, offset))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            log_error(f"Error getting indexed emails: {e}")
            return []
    
    def delete_indexed_emails(self, user_id: str) -> bool:
        """
        Delete all indexed emails for user
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM indexed_emails WHERE user_id = ?
                """, (user_id,))
                
                # Reset count
                cursor.execute("""
                    UPDATE oauth_connections 
                    SET total_emails_indexed = 0
                    WHERE user_id = ?
                """, (user_id,))
                
                conn.commit()
                return True
                
        except Exception as e:
            log_error(f"Error deleting indexed emails: {e}")
            return False
    
    # Indexing Sessions Methods
    
    def create_indexing_session(self, user_id: str) -> Optional[int]:
        """
        Create new indexing session
        
        Args:
            user_id: User identifier
            
        Returns:
            Session ID or None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO indexing_sessions (user_id, started_at)
                    VALUES (?, ?)
                """, (user_id, datetime.now().isoformat()))
                
                conn.commit()
                return cursor.lastrowid
                
        except Exception as e:
            log_error(f"Error creating indexing session: {e}")
            return None
    
    def update_indexing_session(
        self,
        session_id: int,
        status: str,
        emails_fetched: int = 0,
        emails_indexed: int = 0,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update indexing session
        
        Args:
            session_id: Session ID
            status: Session status (in_progress, completed, failed)
            emails_fetched: Number of emails fetched
            emails_indexed: Number of emails indexed
            error_message: Error message if failed
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE indexing_sessions 
                    SET status = ?,
                        emails_fetched = ?,
                        emails_indexed = ?,
                        error_message = ?,
                        completed_at = ?
                    WHERE id = ?
                """, (
                    status,
                    emails_fetched,
                    emails_indexed,
                    error_message,
                    datetime.now().isoformat(),
                    session_id
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            log_error(f"Error updating indexing session: {e}")
            return False
