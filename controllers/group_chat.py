"""
Group Chat Controller - Uses exact same chat.py functions
No duplication - just wraps group chat data and calls chat.py
"""
import json
import secrets
from flask import jsonify, request, Response, session
from flask_login import current_user, login_required
from models.group_chat import (
    create_group_chat,
    add_participant_to_group,
    remove_participant_from_group,
    get_group_chat_history,
    add_message_to_group,
    get_user_group_chats,
    delete_group_chat,
    get_group_chat_info
)
from models.datasource_permissions import DataSourcePermissions
from utils.logger import chat_logger, log_function_call, log_error, log_user_action
from controllers import chat


@log_function_call(chat_logger)
def invite_to_group_chat():
    """Invite a user to a group chat (owner only)
    Note: @login_required is applied at the route level in app.py
    """
    try:
        data = request.get_json() or {}
        group_id = (data.get("group_id") or "").strip()
        user_id = data.get("user_id")
        email = (data.get("email") or "").strip()
        
        if not group_id:
            return jsonify({"error": "group_id is required"}), 400
        
        if not user_id and not email:
            return jsonify({"error": "Either user_id or email is required"}), 400
        
        # Verify requester is owner
        group_info = get_group_chat_info(group_id, current_user.id)
        if not group_info:
            return jsonify({"error": "Group not found or unauthorized"}), 404
        
        if group_info["creator_id"] != current_user.id:
            return jsonify({"error": "Only group owner can invite participants"}), 403
        
        # Add participant by user_id or email
        if user_id:
            success = add_participant_to_group(group_id, user_id)
            invited_target = f"User {user_id}"
        else:
            # Add by email - will be linked when user logs in
            success = add_participant_to_group(group_id, email)
            invited_target = email
        
        if success:
            log_user_action("Invite to Group", current_user.id, f"Group: {group_id}, Invited: {invited_target}")
            return jsonify({"success": True, "message": f"Invitation sent to {invited_target}"}), 200
        else:
            return jsonify({"error": "Failed to invite user"}), 500
            
    except Exception as e:
        log_error(e, "Failed to invite user to group")
        return jsonify({"error": "Internal server error"}), 500


@log_function_call(chat_logger)
def remove_from_group_chat():
    """Remove a participant from group chat (owner only)
    Note: @login_required is applied at the route level in app.py
    """
    try:
        data = request.get_json() or {}
        group_id = (data.get("group_id") or "").strip()
        user_id = data.get("user_id")
        email = (data.get("email") or "").strip()
        
        if not group_id or (not user_id and not email):
            return jsonify({"error": "group_id and (user_id or email) are required"}), 400
        
        # Remove participant (can be by user_id or email)
        success = remove_participant_from_group(group_id, user_id, email, current_user.id)
        
        if success:
            log_user_action("Remove from Group", current_user.id, f"Group: {group_id}, Removed: {user_id or email}")
            return jsonify({"success": True, "message": "User removed successfully"}), 200
        else:
            return jsonify({"error": "Failed to remove user or unauthorized"}), 403
            
    except Exception as e:
        log_error(e, "Failed to remove user from group")
        return jsonify({"error": "Internal server error"}), 500


@log_function_call(chat_logger)
def start_group_chat():
    """Start a new group chat
    Note: @login_required is applied at the route level in app.py
    """
    try:
        data = request.get_json() or {}
        group_name = (data.get("group_name") or "").strip()
        members = data.get("members") or []  # Get members from request
        mode = (data.get("mode") or "pakwheels").strip().lower()
        session_id = data.get("session_id")  # Get session ID from frontend
        cloned_messages = data.get("cloned_messages")  # Optional: messages to clone
        
        if not group_name:
            return jsonify({"error": "group_name is required"}), 400
        
        # Check permission
        if not DataSourcePermissions.is_source_enabled(current_user.id, mode):
            return jsonify({"error": f"You do not have access to {mode.upper()}"}), 403
        
        # Create group with optional cloned messages and session ID
        result = create_group_chat(
            creator_id=current_user.id,
            group_name=group_name,
            members=members,  # Pass members from request
            session_id=session_id,
            mode=mode,
            original_session_id=session_id,  # Pass session ID for caching
            cloned_messages=cloned_messages  # Pass cloned messages if provided
        )
        
        if not result:
            return jsonify({"error": "Failed to create group chat"}), 500
        
        log_user_action("Start Group Chat", current_user.id, f"Group: {result['group_id']}, Mode: {mode}, Messages: {result.get('message_count', 0)}")
        return jsonify(result), 201
        
    except Exception as e:
        log_error(e, "Failed to start group chat")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@log_function_call(chat_logger)
def get_my_group_chats():
    """Get all group chats for current user
    Note: @login_required is applied at the route level in app.py
    """
    try:
        # Pass both user_id and email to find groups where user was invited by email
        user_email = getattr(current_user, 'email', None)
        groups = get_user_group_chats(current_user.id, user_email)
        return jsonify({"groups": groups}), 200
    except Exception as e:
        log_error(e, "Failed to get user group chats")
        return jsonify({"error": "Internal server error"}), 500


@log_function_call(chat_logger)
def get_group_chat_messages():
    """Get group chat message history
    Note: @login_required is applied at the route level in app.py
    """
    try:
        group_id = request.args.get("group_id", "").strip()
        limit = min(int(request.args.get("limit", 100)), 500)
        
        if not group_id:
            return jsonify({"error": "group_id is required"}), 400
        
        # Pass both user_id and email to find groups where user was invited by email
        user_email = getattr(current_user, 'email', None)
        messages = get_group_chat_history(group_id, current_user.id, user_email, limit)
        
        if messages is None:
            return jsonify({"error": "Group not found or unauthorized"}), 404
        
        return jsonify({"messages": messages}), 200
        
    except Exception as e:
        log_error(e, "Failed to get group messages")
        return jsonify({"error": "Internal server error"}), 500


@log_function_call(chat_logger)
def get_group_info():
    """Get detailed group chat information
    Note: @login_required is applied at the route level in app.py
    """
    try:
        group_id = request.args.get("group_id", "").strip()
        
        if not group_id:
            return jsonify({"error": "group_id is required"}), 400
        
        # Pass both user_id and email to find groups where user was invited by email
        user_email = getattr(current_user, 'email', None)
        group_info = get_group_chat_info(group_id, current_user.id, user_email)
        
        if not group_info:
            return jsonify({"error": "Group not found or unauthorized"}), 404
        
        # Add is_creator flag to indicate if current user is the group creator
        group_info['is_creator'] = (group_info.get('creator_id') == current_user.id)
        
        return jsonify(group_info), 200
        
    except Exception as e:
        log_error(e, "Failed to get group info")
        return jsonify({"error": "Internal server error"}), 500


@log_function_call(chat_logger)
def delete_group():
    """Delete a group chat (owner only)
    Note: @login_required is applied at the route level in app.py
    """
    try:
        data = request.get_json() or {}
        group_id = (data.get("group_id") or "").strip()
        
        if not group_id:
            return jsonify({"error": "group_id is required"}), 400
        
        success = delete_group_chat(group_id, current_user.id)
        
        if success:
            log_user_action("Delete Group Chat", current_user.id, f"Group: {group_id}")
            return jsonify({"success": True, "message": "Group chat deleted successfully"}), 200
        else:
            return jsonify({"error": "Failed to delete group or unauthorized"}), 403
            
    except Exception as e:
        log_error(e, "Failed to delete group")
        return jsonify({"error": "Internal server error"}), 500


@log_function_call(chat_logger)
def add_group_message():
    """Add a message to group chat (for group-only mode)
    Note: @login_required is applied at the route level in app.py
    """
    try:
        data = request.get_json() or {}
        group_id = (data.get("group_id") or "").strip()
        message = (data.get("message") or "").strip()
        response = data.get("response")
        
        if not group_id or not message:
            return jsonify({"error": "group_id and message are required"}), 400
        
        # Add message to group
        result = add_message_to_group(
            group_id=group_id,
            user_id=current_user.id,
            query=message,
            response=response
        )
        
        if result:
            log_user_action("Add Group Message", current_user.id, f"Group: {group_id}")
            return jsonify({"success": True, "message_id": result}), 200
        else:
            return jsonify({"error": "Failed to add message"}), 500
            
    except Exception as e:
        log_error(e, "Failed to add group message")
        return jsonify({"error": "Internal server error"}), 500


@log_function_call(chat_logger)
def clear_group_conversation():
    """Clear all messages in a group chat (owner only)
    Note: @login_required is applied at the route level in app.py
    """
    try:
        data = request.get_json() or {}
        group_id = (data.get("group_id") or "").strip()
        
        if not group_id:
            return jsonify({"error": "group_id is required"}), 400
        
        # Verify requester is owner
        group_info = get_group_chat_info(group_id, current_user.id)
        if not group_info:
            return jsonify({"error": "Group not found or unauthorized"}), 404
        
        if group_info["creator_id"] != current_user.id:
            return jsonify({"error": "Only group owner can clear conversation"}), 403
        
        # Clear messages
        from models.group_chat import clear_group_messages
        success = clear_group_messages(group_id)
        
        if success:
            log_user_action("Clear Group Conversation", current_user.id, f"Group: {group_id}")
            return jsonify({"success": True, "message": "Conversation cleared successfully"}), 200
        else:
            return jsonify({"error": "Failed to clear conversation"}), 500
            
    except Exception as e:
        log_error(e, "Failed to clear group conversation")
        return jsonify({"error": "Internal server error"}), 500


@log_function_call(chat_logger)
def group_chat_query_stream():
    """
    Send a message to group chat with AI processing.
    Uses the same AI pipeline as regular chats but with isolated context.
    Note: @login_required is applied at the route level in app.py
    """
    # CRITICAL: Capture ALL data BEFORE creating generator
    # This preserves the request context and avoids thread issues
    try:
        if not current_user or not current_user.is_authenticated:
            def error_gen():
                yield f"data: {json.dumps({'content': 'User not authenticated', 'done': True, 'error': 'auth_error'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')
        
        data = request.get_json(force=True) or {}
        group_id = (data.get("group_id") or "").strip()
        query = (data.get("query") or "").strip()
        frontend_mode = (data.get("mode") or "").strip().lower()  # Get mode from frontend
        thinking_mode = bool(data.get("thinking", False))  # Get thinking mode from frontend
        user_id = current_user.id
        user_email = getattr(current_user, 'email', None)
        company_id = getattr(current_user, 'company_id', None)
        
        # CRITICAL: Fetch all data NOW in main thread before generator
        if not group_id or not query:
            def error_gen():
                yield f"data: {json.dumps({'content': 'group_id and query are required', 'done': True, 'error': 'invalid_request'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')
        
        # Get group info in main thread
        group_info = get_group_chat_info(group_id, user_id, user_email)
        if not group_info:
            def error_gen():
                yield f"data: {json.dumps({'content': 'Group not found or unauthorized', 'done': True, 'error': 'unauthorized'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')
        
        # Get group history in main thread
        group_history = get_group_chat_history(group_id, user_id, user_email, limit=50)
        if group_history is None:
            def error_gen():
                yield f"data: {json.dumps({'content': 'Failed to retrieve group context', 'done': True, 'error': 'context_error'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')
        
        # Build context messages in main thread
        context_messages = []
        if group_history:
            for msg in group_history:
                if msg.get('query'):
                    context_messages.append({
                        'role': 'user',
                        'content': msg['query']
                    })
                if msg.get('response'):
                    context_messages.append({
                        'role': 'assistant',
                        'content': msg['response']
                    })
        
        # Use group's mode setting (set by creator, applies to all members)
        # Ignore frontend values - use group settings instead
        mode = group_info.get('mode', 'pakwheels')
        # Use frontend thinking_mode for individual user preference
        thinking_mode = bool(data.get("thinking", False))
        chat_logger.info(f"Using group mode: {mode}, user thinking_mode: {thinking_mode}, thinking_type: {type(thinking_mode)}")
        
    except Exception as e:
        log_error(e, "Failed to get request data")
        def error_gen():
            yield f"data: {json.dumps({'content': 'Failed to read request', 'done': True, 'error': 'request_error'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')
    
    # Now create the generator with captured data (no database access in generator)
    def response_generator():
        try:
            # Process query through AI based on mode
            answer = None
            
            # Use AIService only for group chats (avoids SQLite thread issues with DMS)
            # DMS pipeline creates SQLite connections that can't be used across threads
            # AIService handles mode mapping internally (dealership → pakwheels, etc.)
            try:
                from services.ai_service import AIService
                # Process query through AIService with thinking_mode
                answer = AIService.process_chat_query(query, mode, company_id, thinking_mode=thinking_mode)
                chat_logger.info(f"Query processed via AIService: group={group_id}, mode={mode}, thinking={thinking_mode}")
            except Exception as ai_error:
                chat_logger.error(f"AIService error: {ai_error}", exc_info=True)
                # For group chats, we don't use DMS pipeline due to SQLite thread issues
                # Just provide a fallback response
                answer = None
            
            # Final fallback if AIService fails
            if not answer:
                answer = f"I received your message: '{query}'. Please try again or contact support."
            
            # Extract structured data (references, charts) BEFORE streaming
            try:
                from controllers.ai_analysis import extract_structured_data
                import re
                structured_data = extract_structured_data(answer, None, mode)
                
                # Clean answer for display (remove ALL reference sections)
                clean_answer = answer
                # Remove all variations of reference sections
                clean_answer = re.sub(r'###\s*📋\s*References[\s\S]*?(?=\n###|\n\n###|$)', '', clean_answer)
                clean_answer = re.sub(r'##\s*📋\s*References[\s\S]*?(?=\n##|\n\n##|$)', '', clean_answer)
                clean_answer = re.sub(r'#\s*📋\s*References[\s\S]*?(?=\n#|\n\n#|$)', '', clean_answer)
                clean_answer = re.sub(r'🔗\s*Reddit References[\s\S]*?(?=\n\n|$)', '', clean_answer)
                clean_answer = re.sub(r'🔗\s*PakWheels References[\s\S]*?(?=\n\n|$)', '', clean_answer)
                clean_answer = re.sub(r'🔗\s*WhatsApp References[\s\S]*?(?=\n\n|$)', '', clean_answer)
                clean_answer = re.sub(r'🔗\s*Facebook References[\s\S]*?(?=\n\n|$)', '', clean_answer)
                clean_answer = re.sub(r'---\s*\n###\s*📋\s*References[\s\S]*?---', '', clean_answer)
                clean_answer = re.sub(r'\n\s*\n\s*\n+', '\n\n', clean_answer).strip()
            except Exception as extract_error:
                chat_logger.error(f"Error extracting structured data: {extract_error}")
                structured_data = {}
                clean_answer = answer
            
            # Stream cleaned answer in chunks (without references section)
            words = clean_answer.split()
            chunk_size = 10
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i+chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "
                yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
            
            # Save message to group chat with AI response
            # NOTE: Create fresh connection in this thread for saving
            try:
                add_message_to_group(
                    group_id=group_id,
                    user_id=user_id,
                    query=query,
                    response=answer,
                    structured_data=structured_data
                )
                chat_logger.info(f"Group message saved: group={group_id}, user={user_id}")
            except Exception as save_error:
                chat_logger.error(f"Error saving group message: {save_error}", exc_info=True)
            
            # Send completion signal with structured data
            yield f"data: {json.dumps({'content': '', 'done': True, 'success': True, 'structured': structured_data})}\n\n"
                
        except Exception as e:
            log_error(e, "Failed to send group message")
            yield f"data: {json.dumps({'content': 'Internal server error', 'done': True, 'error': 'server_error'})}\n\n"
    
    return Response(response_generator(), mimetype='text/event-stream')


@log_function_call(chat_logger)
def update_group_mode():
    """Update group mode (creator only)
    Note: @login_required is applied at the route level in app.py
    """
    try:
        data = request.get_json() or {}
        group_id = (data.get("group_id") or "").strip()
        mode = (data.get("mode") or "").strip().lower()
        
        if not group_id or not mode:
            return jsonify({"error": "group_id and mode are required"}), 400
        
        # Update group mode
        from models.group_chat import update_group_mode
        success = update_group_mode(group_id, mode, current_user.id)
        
        if success:
            log_user_action("Update Group Mode", current_user.id, f"Group: {group_id}, Mode: {mode}")
            return jsonify({"success": True, "message": f"Group mode updated to {mode}"}), 200
        else:
            return jsonify({"error": "Failed to update group mode or unauthorized"}), 403
            
    except Exception as e:
        log_error(e, "Failed to update group mode")
        return jsonify({"error": "Internal server error"}), 500



