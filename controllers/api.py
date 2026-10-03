from flask import jsonify, request
from flask_login import current_user, login_required
from models.chat import (
    get_user_chat_sessions, get_user_chat_history, 
    delete_user_chat_session, clear_user_chat_history,
    save_user_chat_history
)
from models.database import get_db_connection
from utils.logger import api_logger, log_function_call, log_user_action, log_error
from datetime import datetime
from zoneinfo import ZoneInfo
import secrets

# Pakistan timezone
PAKISTAN_TZ = ZoneInfo("Asia/Karachi")
import json
import queue


@log_function_call(api_logger)
def get_selected_company():
    """Get the user's company"""
    api_logger.info(f"API: Get selected company for user {current_user.username}")
    
    from config import get_company_config
    try:
        company_config = get_company_config(current_user.company_id)
        
        response_data = {
            "success": True,
            "company": {
                "id": current_user.company_id,
                "name": company_config.full_name,
                "display_name": company_config.name  # Fix: use name instead of display_name
            }
        }
        
        api_logger.info(f"API: Company data returned for {current_user.username}: {current_user.company_id}")
        log_user_action("API: Get Company", current_user.id, f"Company: {current_user.company_id}")
        
        return jsonify(response_data)
        
    except Exception as e:
        log_error(e, f"API: Get selected company failed for user {current_user.username}")
        
        response_data = {
            "success": False,
            "error": str(e),
            "company": {
                "id": current_user.company_id,
                "name": current_user.company_id.title(),
                "display_name": current_user.company_id.title()  # This one is correct
            }
        }
        
        api_logger.error(f"API: Error getting company for {current_user.username}: {str(e)}")
        return jsonify(response_data)


@log_function_call(api_logger)
def set_selected_company():
    """This endpoint is deprecated - company is now set during user registration"""
    api_logger.warning(f"API: Deprecated set_selected_company called by user {current_user.username}")
    log_user_action("API: Set Company (Deprecated)", current_user.id, "Attempted to use deprecated endpoint")
    
    return jsonify({
        "success": False,
        "message": "Company selection is now handled during registration. Please contact support to change your company."
    })


@log_function_call(api_logger)
def get_all_companies_api():
    """Get list of all available companies"""
    api_logger.info(f"API: Get all companies requested by user {current_user.username}")
    
    from config import get_enabled_companies
    try:
        companies = get_enabled_companies()
        
        response_data = {
            "success": True,
            "companies": [
                {"id": company_id, "name": company_data}
                for company_id, company_data in companies.items()
            ]
        }
        
        api_logger.info(f"API: Returned {len(companies)} companies to user {current_user.username}")
        log_user_action("API: Get All Companies", current_user.id, f"Companies: {len(companies)}")
        
        return jsonify(response_data)
        
    except Exception as e:
        log_error(e, f"API: Get all companies failed for user {current_user.username}")
        
        fallback_companies = [
            {"id": "haval", "name": "Haval"},
            {"id": "mg", "name": "MG"},
            {"id": "kia", "name": "Kia"}
        ]
        
        api_logger.error(f"API: Using fallback companies for {current_user.username}: {str(e)}")
        
        return jsonify({
            "success": False,
            "error": str(e),
            "companies": fallback_companies
        })


@log_function_call(api_logger)
def get_chat_sessions():
    """Get user's chat sessions with proper Pakistan timezone"""
    api_logger.info(f"API: Get chat sessions for user {current_user.username}")
    
    try:
        sessions = get_user_chat_sessions(current_user.id)
        
        # Log all sessions with their modes for debugging
        api_logger.info(f"API: Raw sessions from DB: {[(s.get('session_id'), s.get('mode')) for s in sessions]}")
        
        # Ensure timestamps are properly formatted for Pakistan timezone
        for session in sessions:
            # Normalize mode to lowercase for consistency
            if 'mode' in session and session['mode']:
                session['mode'] = session['mode'].lower().strip()
            
            if 'last_updated' in session and session['last_updated']:
                try:
                    # Parse the timestamp and ensure it's in Pakistan timezone
                    if isinstance(session['last_updated'], str):
                        dt = datetime.fromisoformat(session['last_updated'].replace('Z', '+00:00'))
                    else:
                        dt = session['last_updated']
                    
                    # Convert to Pakistan timezone if needed
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=PAKISTAN_TZ)
                    else:
                        dt = dt.astimezone(PAKISTAN_TZ)
                    
                    session['last_updated'] = dt.isoformat()
                except Exception as e:
                    api_logger.warning(f"Error formatting timestamp for session {session.get('session_id')}: {e}")
        
        api_logger.info(f"API: Retrieved {len(sessions)} chat sessions for user {current_user.username}")
        api_logger.info(f"API: Sessions by mode: {[(s.get('mode'), len([x for x in sessions if x.get('mode') == s.get('mode')])) for s in sessions]}")
        log_user_action("API: Get Chat Sessions", current_user.id, f"Sessions: {len(sessions)}")
        
        return jsonify({"success": True, "sessions": sessions})
        
    except Exception as e:
        log_error(e, f"API: Get chat sessions failed for user {current_user.username}")
        api_logger.error(f"API: Error getting chat sessions for {current_user.username}: {str(e)}")
        
        return jsonify({"success": False, "error": str(e)})


@log_function_call(api_logger)
def get_session_history(session_id):
    """Get chat history for a specific session, filtered by mode"""
    api_logger.info(f"API: Get session history for user {current_user.username}, session {session_id}")
    
    try:
        # Get mode from query parameter (required for mode-specific filtering)
        requested_mode = request.args.get('mode', None)
        
        if not requested_mode:
            api_logger.warning(f"API: No mode specified for session {session_id}, using default 'pakwheels'")
            requested_mode = 'pakwheels'
        
        # Normalize mode to lowercase
        requested_mode = requested_mode.lower().strip()
        
        # Get history filtered by BOTH session_id AND mode
        from models.database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verify this session exists for this user and mode
        cur.execute("""
            SELECT COUNT(*) as count FROM chat_history 
            WHERE user_id = ? AND session_id = ? AND LOWER(TRIM(mode)) = ?
        """, (current_user.id, session_id, requested_mode))
        
        result = cur.fetchone()
        message_count = result[0] if result else 0
        
        conn.close()
        
        api_logger.info(f"API: Found {message_count} messages for session {session_id}, mode {requested_mode}")
        
        if message_count == 0:
            api_logger.warning(f"API: No messages found for session {session_id} in mode {requested_mode}")
            return jsonify({
                "success": True,
                "history": [],
                "messages": [],
                "mode": requested_mode,
                "session_id": session_id
            })
        
        # Get history filtered by mode
        history = get_user_chat_history(current_user.id, requested_mode, session_id)
        
        api_logger.info(f"API: Retrieved {len(history)} messages for session {session_id}, user {current_user.username}, mode {requested_mode}")
        log_user_action("API: Get Session History", current_user.id, f"Session: {session_id}, Mode: {requested_mode}, Messages: {len(history)}")
        
        # Add mode to response for frontend
        return jsonify({
            "success": True, 
            "history": history,
            "messages": history,  # Also include as 'messages' for compatibility
            "mode": requested_mode,
            "session_id": session_id
        })
        
    except Exception as e:
        log_error(e, f"API: Get session history failed for user {current_user.username}, session {session_id}")
        api_logger.error(f"API: Error getting session history for {current_user.username}: {str(e)}")
        
        return jsonify({"success": False, "error": str(e)})


@log_function_call(api_logger)
def delete_chat_session(session_id):
    """Delete a chat session"""
    api_logger.info(f"API: Delete chat session {session_id} for user {current_user.username}")
    
    try:
        success = delete_user_chat_session(current_user.id, session_id)
        
        if success:
            api_logger.info(f"API: Successfully deleted session {session_id} for user {current_user.username}")
            log_user_action("API: Delete Chat Session", current_user.id, f"Session: {session_id}")
            
            return jsonify({"success": True, "message": "Session deleted successfully"})
        else:
            api_logger.warning(f"API: Session {session_id} not found for user {current_user.username}")
            return jsonify({"success": False, "error": "Session not found"})
            
    except Exception as e:
        log_error(e, f"API: Delete chat session failed for user {current_user.username}, session {session_id}")
        api_logger.error(f"API: Error deleting session for {current_user.username}: {str(e)}")
        
        return jsonify({"success": False, "error": str(e)})


@log_function_call(api_logger)
def clear_chat_history():
    """Clear user's chat history"""
    api_logger.info(f"API: Clear chat history for user {current_user.username}")
    
    try:
        mode = request.json.get('mode') if request.json else None
        
        # Normalize mode to lowercase if provided
        if mode:
            mode = mode.lower().strip()
        
        success = clear_user_chat_history(current_user.id, mode)
        
        if success:
            message = f"Chat history cleared for {mode} mode" if mode else "All chat history cleared"
            
            api_logger.info(f"API: {message} for user {current_user.username}")
            log_user_action("API: Clear Chat History", current_user.id, f"Mode: {mode or 'all'}")
            
            return jsonify({"success": True, "message": message})
        else:
            api_logger.info(f"API: No chat history to clear for user {current_user.username}")
            return jsonify({"success": False, "error": "No chat history found to clear"})
            
    except Exception as e:
        log_error(e, f"API: Clear chat history failed for user {current_user.username}")
        api_logger.error(f"API: Error clearing chat history for {current_user.username}: {str(e)}")
        
        return jsonify({"success": False, "error": str(e)})


@log_function_call(api_logger)
def api_pipeline_status():
    """Get current pipeline status for status indicator"""
    # Handle both authenticated and anonymous users
    username = current_user.username if current_user.is_authenticated else "anonymous"
    user_id = current_user.id if current_user.is_authenticated else None
    
    api_logger.info(f"API: Pipeline status requested by user {username}")
    
    try:
        from ai.haval_pipeline import get_pipeline_status
        status = get_pipeline_status()
        
        api_logger.info(f"API: Pipeline status returned: {status.get('status', 'unknown')} for user {username}")
        
        # Only log user action if user is authenticated
        if current_user.is_authenticated:
            log_user_action("API: Pipeline Status", user_id, f"Status: {status.get('status', 'unknown')}")
        
        return jsonify(status)
        
    except Exception as e:
        username = current_user.username if current_user.is_authenticated else "anonymous"
        log_error(e, f"API: Pipeline status failed for user {username}")
        api_logger.error(f"API: Error getting pipeline status for {username}: {str(e)}")
        
        return jsonify({"status": "error", "message": str(e)})


@log_function_call(api_logger)
def get_wati_progress():
    """Get current WATI fetching progress"""
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required"}), 401
    
    # Check if user has access to WATI data (only Haval users)
    user_company = current_user.company_id or 'haval'
    if user_company != 'haval':
        return jsonify({"error": "WATI access restricted to Haval users"}), 403
    
    try:
        # This is a simple implementation - in a real scenario, you'd track progress in a database or cache
        # For now, we'll return a simulated progress or check if WATI process is running
        
        # Check if there are recent WATI logs to determine if process is running
        import os
        from datetime import datetime, timedelta
        
        log_file = "logs/fetching.log"
        if os.path.exists(log_file):
            # Check if there are recent WATI-related log entries
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                # Look for recent processing messages
                recent_cutoff = datetime.now() - timedelta(minutes=5)
                processing_lines = []
                
                for line in reversed(lines[-100:]):  # Check last 100 lines
                    if 'Processing' in line and ('/' in line):
                        try:
                            # Extract timestamp from log line
                            timestamp_str = line.split(' - ')[0]
                            log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                            
                            if log_time > recent_cutoff:
                                processing_lines.append(line)
                        except:
                            continue
                
                if processing_lines:
                    # Parse the most recent processing line
                    latest_line = processing_lines[0]
                    
                    # Extract progress info: "Processing 51/400: Naeem (46761545684)"
                    if 'Processing' in latest_line:
                        try:
                            parts = latest_line.split('Processing ')[1].split(':')
                            progress_part = parts[0].strip()  # "51/400"
                            contact_part = parts[1].strip() if len(parts) > 1 else ""
                            
                            if '/' in progress_part:
                                current, total = progress_part.split('/')
                                current = int(current.strip())
                                total = int(total.strip())
                                
                                # Extract contact name and phone
                                contact_name = "Unknown"
                                contact_phone = ""
                                
                                if contact_part:
                                    # Parse "Naeem (46761545684)"
                                    if '(' in contact_part and ')' in contact_part:
                                        contact_name = contact_part.split('(')[0].strip()
                                        contact_phone = contact_part.split('(')[1].split(')')[0].strip()
                                    else:
                                        contact_name = contact_part
                                
                                return jsonify({
                                    "status": "processing",
                                    "progress": {
                                        "current": current,
                                        "total": total,
                                        "contact_name": contact_name,
                                        "contact_phone": contact_phone
                                    }
                                })
                        except Exception as e:
                            api_logger.warning(f"Error parsing WATI progress: {e}")
                
            except Exception as e:
                api_logger.warning(f"Error reading WATI progress from logs: {e}")
        
        # Default response - no active processing
        return jsonify({
            "status": "idle",
            "message": "No active WATI processing detected"
        })
        
    except Exception as e:
        log_error(e, f"API: WATI progress check failed for user {current_user.username}")
        api_logger.error(f"API: Error getting WATI progress for {current_user.username}: {str(e)}")
        
        return jsonify({"status": "error", "message": str(e)})


@log_function_call(api_logger)
def new_chat_session():
    """Start a new chat session"""
    api_logger.info(f"API: New chat session requested by user {current_user.username}")
    
    try:
        session_id = secrets.token_urlsafe(16)
        
        api_logger.info(f"API: New chat session created: {session_id} for user {current_user.username}")
        log_user_action("API: New Chat Session", current_user.id, f"Session: {session_id}")
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "message": "New chat session created"
        })
        
    except Exception as e:
        log_error(e, f"API: New chat session failed for user {current_user.username}")
        api_logger.error(f"API: Error creating new session for {current_user.username}: {str(e)}")
        
        return jsonify({"success": False, "error": str(e)})


@log_function_call(api_logger)
def get_logs():
    """Get recent logs for the process logs section"""
    api_logger.info(f"API: Get logs requested by user {current_user.username}")
    
    # Import here to avoid circular imports
    import app
    
    logs = []
    temp_queue = queue.Queue()
    
    # Get all logs from queue
    while not app.log_queue.empty():
        try:
            log_entry = app.log_queue.get_nowait()
            logs.append(log_entry)
            temp_queue.put(log_entry)  # Keep for other requests
        except queue.Empty:
            break
    
    # Put logs back in queue
    while not temp_queue.empty():
        try:
            app.log_queue.put_nowait(temp_queue.get_nowait())
        except queue.Full:
            break
    
    api_logger.info(f"API: Returned {len(logs)} log entries to user {current_user.username}")
    log_user_action("API: Get Logs", current_user.id, f"Logs: {len(logs)}")
    
    return jsonify(logs)


@log_function_call(api_logger)
def stream_logs():
    """Server-Sent Events stream for real-time logs"""
    from flask import Response
    # Import here to avoid circular imports
    import app
    
    # Capture user info at the start since current_user might become None during streaming
    username = current_user.username if current_user.is_authenticated else "anonymous"
    user_id = current_user.id if current_user.is_authenticated else None
    
    api_logger.info(f"API: Log stream started for user {username}")
    if user_id:
        log_user_action("API: Start Log Stream", user_id, "Real-time log streaming")
    
    def generate():
        # Create a queue for this subscriber
        subscriber_queue = queue.Queue(maxsize=100)
        app.log_subscribers.append(subscriber_queue)
        
        try:
            # Send existing logs first
            existing_logs = []
            temp_queue = queue.Queue()
            
            while not app.log_queue.empty():
                try:
                    log_entry = app.log_queue.get_nowait()
                    existing_logs.append(log_entry)
                    temp_queue.put(log_entry)
                except queue.Empty:
                    break
            
            # Put logs back
            while not temp_queue.empty():
                try:
                    app.log_queue.put_nowait(temp_queue.get_nowait())
                except queue.Full:
                    break
            
            # Send existing logs
            for log_entry in existing_logs[-20:]:  # Send last 20 logs
                yield f"data: {json.dumps(log_entry)}\n\n"
            
            # Stream new logs
            while True:
                try:
                    log_entry = subscriber_queue.get(timeout=30)  # 30 second timeout
                    yield f"data: {json.dumps(log_entry)}\n\n"
                except queue.Empty:
                    # Send heartbeat
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                    
        except GeneratorExit:
            # Client disconnected
            if subscriber_queue in app.log_subscribers:
                app.log_subscribers.remove(subscriber_queue)
            api_logger.info(f"API: Log stream ended for user {username} (client disconnected)")
        except Exception as e:
            # Remove subscriber on error
            if subscriber_queue in app.log_subscribers:
                app.log_subscribers.remove(subscriber_queue)
            api_logger.error(f"API: Log stream error for user {username}: {str(e)}")
    
    return Response(generate(), mimetype='text/event-stream')



# ============================================================================
# GROUP CHAT ENDPOINTS
# ============================================================================

@log_function_call(api_logger)
def create_group_chat():
    """Create a new group chat"""
    api_logger.info(f"API: Create group chat requested by user {current_user.username}")
    
    try:
        from models.group_chat import GroupChat
        
        data = request.get_json()
        group_name = data.get('group_name', '').strip()
        members = data.get('members', [])
        session_id = data.get('session_id')
        mode = data.get('mode', 'pakwheels').lower()
        
        if not group_name:
            return jsonify({"success": False, "error": "Group name is required"})
        
        if not members:
            return jsonify({"success": False, "error": "At least one member is required"})
        
        # Create group
        group_id = GroupChat.create_group(
            creator_id=current_user.id,
            group_name=group_name,
            members=members,
            session_id=session_id,
            mode=mode
        )
        
        if not group_id:
            return jsonify({"success": False, "error": "Failed to create group"})
        
        api_logger.info(f"API: Group created: {group_id} by user {current_user.username}")
        log_user_action("API: Create Group Chat", current_user.id, f"Group: {group_name}, Members: {len(members)}")
        
        return jsonify({
            "success": True,
            "group_id": group_id,
            "message": f"Group '{group_name}' created successfully"
        })
        
    except Exception as e:
        log_error(e, f"API: Create group chat failed for user {current_user.username}")
        api_logger.error(f"API: Error creating group chat for {current_user.username}: {str(e)}")
        
        return jsonify({"success": False, "error": str(e)})


@log_function_call(api_logger)
def get_group_chat(group_id):
    """Get group chat details"""
    api_logger.info(f"API: Get group chat {group_id} requested by user {current_user.username}")
    
    try:
        from models.group_chat import GroupChat
        
        group = GroupChat.get_group(group_id)
        if not group:
            return jsonify({"success": False, "error": "Group not found"})
        
        members = GroupChat.get_group_members(group_id)
        
        api_logger.info(f"API: Group chat retrieved: {group_id} for user {current_user.username}")
        
        return jsonify({
            "success": True,
            "group": group,
            "members": members
        })
        
    except Exception as e:
        log_error(e, f"API: Get group chat failed for user {current_user.username}")
        api_logger.error(f"API: Error getting group chat for {current_user.username}: {str(e)}")
        
        return jsonify({"success": False, "error": str(e)})


@log_function_call(api_logger)
def get_group_messages(group_id):
    """Get group messages"""
    api_logger.info(f"API: Get group messages for {group_id} requested by user {current_user.username}")
    
    try:
        from models.group_chat import GroupChat
        
        limit = request.args.get('limit', 100, type=int)
        messages = GroupChat.get_group_messages(group_id, limit=limit)
        
        api_logger.info(f"API: Retrieved {len(messages)} messages from group {group_id} for user {current_user.username}")
        
        return jsonify({
            "success": True,
            "messages": messages
        })
        
    except Exception as e:
        log_error(e, f"API: Get group messages failed for user {current_user.username}")
        api_logger.error(f"API: Error getting group messages for {current_user.username}: {str(e)}")
        
        return jsonify({"success": False, "error": str(e)})


@log_function_call(api_logger)
def send_group_message():
    """Send message to group"""
    api_logger.info(f"API: Send group message requested by user {current_user.username}")
    
    try:
        from models.group_chat import GroupChat
        
        data = request.get_json()
        group_id = data.get('group_id')
        message = data.get('message', '').strip()
        
        if not group_id or not message:
            return jsonify({"success": False, "error": "Group ID and message are required"})
        
        # Add message to group
        message_id = GroupChat.add_message(
            group_id=group_id,
            sender_id=current_user.id,
            sender_name=current_user.username,
            message=message
        )
        
        if not message_id:
            return jsonify({"success": False, "error": "Failed to send message"})
        
        api_logger.info(f"API: Message sent to group {group_id} by user {current_user.username}")
        log_user_action("API: Send Group Message", current_user.id, f"Group: {group_id}")
        
        return jsonify({
            "success": True,
            "message_id": message_id,
            "message": "Message sent successfully"
        })
        
    except Exception as e:
        log_error(e, f"API: Send group message failed for user {current_user.username}")
        api_logger.error(f"API: Error sending group message for {current_user.username}: {str(e)}")
        
        return jsonify({"success": False, "error": str(e)})


@log_function_call(api_logger)
def get_user_groups():
    """Get all groups for current user"""
    api_logger.info(f"API: Get user groups requested by user {current_user.username}")
    
    try:
        from models.group_chat import GroupChat
        
        # Update user_id for any invited groups when they log in
        GroupChat.update_invited_user_id(current_user.id, current_user.email)
        
        # Get all groups (both created and invited)
        groups = GroupChat.get_user_groups(current_user.id, current_user.email)
        
        api_logger.info(f"API: Retrieved {len(groups)} groups for user {current_user.username}")
        log_user_action("API: Get User Groups", current_user.id, f"Groups: {len(groups)}")
        
        return jsonify({
            "success": True,
            "groups": groups
        })
        
    except Exception as e:
        log_error(e, f"API: Get user groups failed for user {current_user.username}")
        api_logger.error(f"API: Error getting user groups for {current_user.username}: {str(e)}")
        
        return jsonify({"success": False, "error": str(e)})



@log_function_call(api_logger)
def get_all_users_for_invite():
    """Get all users for group chat invitation"""
    api_logger.info(f"API: Get all users for invite requested by user {current_user.username}")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get all active users except current user
        cur.execute("""
            SELECT id, username, email, company_id
            FROM users
            WHERE is_deleted = FALSE AND id != ?
            ORDER BY username ASC
        """, (current_user.id,))
        
        rows = cur.fetchall()
        conn.close()
        
        users = []
        for row in rows:
            users.append({
                'id': row[0],
                'username': row[1],
                'email': row[2],
                'company_id': row[3]
            })
        
        api_logger.info(f"API: Retrieved {len(users)} users for invite for user {current_user.username}")
        
        return jsonify({
            "success": True,
            "users": users
        })
        
    except Exception as e:
        log_error(e, f"API: Get all users for invite failed for user {current_user.username}")
        api_logger.error(f"API: Error getting users for invite for {current_user.username}: {str(e)}")
        
        return jsonify({"success": False, "error": str(e), "users": []})


@log_function_call(api_logger)
def invite_user_to_group():
    """Invite a user to an existing group"""
    api_logger.info(f"API: Invite user to group requested by user {current_user.username}")
    
    try:
        from models.group_chat import GroupChat
        
        data = request.get_json()
        group_id = data.get('group_id')
        email = data.get('email')
        
        if not group_id or not email:
            return jsonify({"success": False, "error": "Missing group_id or email"})
        
        # Verify user is member of the group
        group = GroupChat.get_group(group_id)
        if not group:
            return jsonify({"success": False, "error": "Group not found"})
        
        # Check if user is creator or member
        members = GroupChat.get_group_members(group_id)
        is_member = any(m['user_id'] == current_user.id for m in members)
        
        if not is_member and group['creator_id'] != current_user.id:
            return jsonify({"success": False, "error": "You don't have permission to invite users to this group"})
        
        # Check if user is already invited
        already_invited = any(m['email'] == email for m in members)
        if already_invited:
            return jsonify({"success": False, "error": "User is already invited to this group"})
        
        # Add user to group
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO group_members (group_id, user_id, email, joined_at)
                VALUES (?, ?, ?, ?)
            """, (group_id, None, email, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            api_logger.info(f"API: User {email} invited to group {group_id} by {current_user.username}")
            log_user_action("API: Invite User to Group", current_user.id, f"Group: {group_id}, Email: {email}")
            
            return jsonify({
                "success": True,
                "message": f"Invitation sent to {email}"
            })
        except Exception as e:
            conn.close()
            if "UNIQUE constraint failed" in str(e):
                return jsonify({"success": False, "error": "User is already invited to this group"})
            raise
        
    except Exception as e:
        log_error(e, f"API: Invite user to group failed for user {current_user.username}")
        api_logger.error(f"API: Error inviting user to group for {current_user.username}: {str(e)}")
        
        return jsonify({"success": False, "error": str(e)})
