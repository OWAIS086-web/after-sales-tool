from .database import get_db_connection
from utils.logger import database_logger, chat_logger, log_function_call, log_database_activity, log_error
from datetime import datetime
from zoneinfo import ZoneInfo
import json

# Pakistan timezone
PAKISTAN_TZ = ZoneInfo("Asia/Karachi")


@log_function_call(chat_logger)
def get_user_chat_history(user_id, mode, session_id=None, limit=None):
    """Get user-specific chat history for a mode with structured data
    
    Args:
        user_id: User ID
        mode: Chat mode (pakwheels, dealership, etc.)
        session_id: Optional session ID to get specific session history
        limit: Max messages to retrieve (None = all messages, useful for loading complete history)
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Normalize mode to lowercase
        mode = (mode or '').lower().strip()
        
        # Check if structured_data column exists
        cur.execute("PRAGMA table_info(chat_history)")
        columns = [row[1] for row in cur.fetchall()]
        has_structured_data = 'structured_data' in columns
        
        # Build LIMIT clause - if limit is None, get all records
        limit_clause = "" if limit is None else f"LIMIT {limit}"
        
        if has_structured_data:
            # Query with structured_data column
            if session_id:
                # When loading a specific session, get ONLY messages from the specified mode
                # This ensures mode-specific history
                cur.execute(f"""
                    SELECT query, response, structured_data, timestamp FROM chat_history 
                    WHERE user_id = ? AND session_id = ? AND LOWER(TRIM(mode)) = ?
                    ORDER BY timestamp ASC {limit_clause}
                """, (user_id, session_id, mode))
                chat_logger.info(f"Retrieved chat history for user {user_id}, session {session_id}, mode {mode}, limit={limit}")
            else:
                cur.execute(f"""
                    SELECT query, response, structured_data, timestamp FROM chat_history 
                    WHERE user_id = ? AND LOWER(TRIM(mode)) = ?
                    ORDER BY timestamp DESC {limit_clause}
                """, (user_id, mode))
                chat_logger.info(f"Retrieved chat history for user {user_id}, mode {mode}, limit={limit}")
        else:
            # Fallback for databases without structured_data column
            chat_logger.warning("structured_data column not found, using fallback query")
            if session_id:
                # When loading a specific session, get ONLY messages from the specified mode
                cur.execute(f"""
                    SELECT query, response, timestamp FROM chat_history 
                    WHERE user_id = ? AND session_id = ? AND LOWER(TRIM(mode)) = ?
                    ORDER BY timestamp ASC {limit_clause}
                """, (user_id, session_id, mode))
            else:
                cur.execute(f"""
                    SELECT query, response, timestamp FROM chat_history 
                    WHERE user_id = ? AND LOWER(TRIM(mode)) = ?
                    ORDER BY timestamp DESC {limit_clause}
                """, (user_id, mode))
        
        rows = cur.fetchall()
        history = []
        
        chat_logger.info(f"Database returned {len(rows)} rows for user {user_id}, session {session_id}")
        
        for row in rows:
            # Convert timestamp to ISO format string if it's a datetime object
            timestamp = row[3] if len(row) > 3 else None
            if timestamp and isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()
            
            # Add user message
            history.append({"role": "user", "content": row[0], "timestamp": timestamp})
            
            # Add assistant message with structured data if available
            assistant_msg = {"role": "assistant", "content": row[1], "timestamp": timestamp}
            
            # Parse structured data if available (only if column exists)
            if has_structured_data and len(row) > 2 and row[2]:
                try:
                    structured_data = json.loads(row[2])
                    assistant_msg["structured"] = structured_data
                    # chat_logger.debug(f"Loaded structured data for message: {len(structured_data.get('references', []))} refs, {len(structured_data.get('charts', []))} charts")
                except json.JSONDecodeError as e:
                    chat_logger.warning(f"Failed to parse structured data: {e}")
                except Exception as e:
                    chat_logger.warning(f"Error processing structured data: {e}")
            
            history.append(assistant_msg)
        
        conn.close()
        log_database_activity("SELECT", "chat_history", len(rows), user_id)
        
        chat_logger.info(f"Returning {len(history)} messages for user {user_id}, session {session_id}")
        return history
        
    except Exception as e:
        log_error(e, f"Failed to get chat history for user {user_id}")
        return []


@log_function_call(chat_logger, log_args=False)  # Don't log full query/response content
def save_user_chat_history(user_id, session_id, mode, query, response, structured_data=None):
    """Save user chat interaction to database with Pakistan timezone and structured data"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get current time in Pakistan timezone
        pakistan_time = datetime.now(PAKISTAN_TZ)
        
        # Check if structured_data column exists
        cur.execute("PRAGMA table_info(chat_history)")
        columns = [row[1] for row in cur.fetchall()]
        has_structured_data = 'structured_data' in columns
        
        if has_structured_data:
            # Serialize structured data to JSON if provided
            structured_json = None
            if structured_data:
                try:
                    structured_json = json.dumps(structured_data)
                    # chat_logger.debug(f"Serialized structured data: {len(structured_data.get('references', []))} refs, {len(structured_data.get('charts', []))} charts")
                except Exception as e:
                    chat_logger.warning(f"Failed to serialize structured data: {e}")
            
            cur.execute("""
                INSERT INTO chat_history (user_id, session_id, mode, query, response, structured_data, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, session_id, mode, query, response, structured_json, pakistan_time))
        else:
            # Fallback for databases without structured_data column
            chat_logger.warning("structured_data column not found, saving without structured data")
            cur.execute("""
                INSERT INTO chat_history (user_id, session_id, mode, query, response, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, session_id, mode, query, response, pakistan_time))
        
        conn.commit()
        conn.close()
        
        chat_logger.info(f"Saved chat interaction for user {user_id}, session {session_id}, mode {mode} at {pakistan_time}")
        log_database_activity("INSERT", "chat_history", 1, user_id)
        
    except Exception as e:
        log_error(e, f"Failed to save chat history for user {user_id}")


@log_function_call(chat_logger)
def get_user_chat_sessions(user_id, limit=None):
    """Get user's chat sessions
    
    Args:
        user_id: User ID
        limit: Max sessions to retrieve (None = all sessions, default shows all)
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build LIMIT clause - if limit is None, get all sessions
        limit_clause = "" if limit is None else f"LIMIT {limit}"
        
        # Group by session_id and mode to show separate sessions for each mode
        # This way each mode has its own conversation thread
        # Normalize mode to lowercase for consistency
        cur.execute(f"""
            SELECT session_id, 
                   LOWER(TRIM(mode)) as mode,
                   MIN(timestamp) as first_message,
                   MAX(timestamp) as last_updated,
                   COUNT(*) as message_count,
                   MIN(query) as first_query
            FROM chat_history 
            WHERE user_id = ?
            GROUP BY session_id, LOWER(TRIM(mode))
            ORDER BY last_updated DESC
            {limit_clause}
        """, (user_id,))
        
        sessions = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        chat_logger.info(f"Retrieved {len(sessions)} chat sessions for user {user_id}")
        # chat_in data(f"Sessions by mode: {[(s['mode'], s['session_id']) for s in sessions]}")
        log_database_activity("SELECT", "chat_history", len(sessions), user_id)
        return sessions
        
    except Exception as e:
        log_error(e, f"Failed to get chat sessions for user {user_id}")
        return []


@log_function_call(chat_logger)
def delete_user_chat_session(user_id, session_id):
    """Delete a specific chat session for a user"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM chat_history 
            WHERE user_id = ? AND session_id = ?
        """, (user_id, session_id))
        
        conn.commit()
        result = cur.rowcount > 0
        conn.close()
        
        if result:
            chat_logger.info(f"Deleted chat session {session_id} for user {user_id}")
            log_database_activity("DELETE", "chat_history", cur.rowcount, user_id)
        else:
            chat_logger.warning(f"No chat session found to delete: {session_id} for user {user_id}")
            
        return result
        
    except Exception as e:
        log_error(e, f"Failed to delete chat session {session_id} for user {user_id}")
        return False


@log_function_call(chat_logger)
def clear_user_chat_history(user_id, mode=None):
    """Clear all chat history for a user (optionally for a specific mode)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        if mode:
            # Normalize mode to lowercase for consistency
            mode = (mode or '').lower().strip()
            
            cur.execute("""
                DELETE FROM chat_history 
                WHERE user_id = ? AND LOWER(TRIM(mode)) = ?
            """, (user_id, mode))
            chat_logger.info(f"Cleared chat history for user {user_id}, mode {mode}")
        else:
            cur.execute("""
                DELETE FROM chat_history 
                WHERE user_id = ?
            """, (user_id,))
            chat_logger.info(f"Cleared all chat history for user {user_id}")
        
        conn.commit()
        result = cur.rowcount > 0
        conn.close()
        
        log_database_activity("DELETE", "chat_history", cur.rowcount, user_id)
        return result
        
    except Exception as e:
        log_error(e, f"Failed to clear chat history for user {user_id}")
        return False