import uuid
from datetime import datetime
from .database import get_db_connection
from utils.logger import database_logger, log_function_call, log_error


class GroupChat:
    """Group chat management"""
    
    @staticmethod
    @log_function_call(database_logger)
    def create_group(creator_id, group_name, members, session_id, mode='pakwheels'):
        """Create a new group chat"""
        try:
            group_id = f"group_{uuid.uuid4().hex[:12]}"
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Create group
            cur.execute("""
                INSERT INTO groups (id, name, creator_id, session_id, mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (group_id, group_name, creator_id, session_id, mode, datetime.now().isoformat()))
            
            # Add creator as member
            cur.execute("""
                INSERT INTO group_members (group_id, user_id, email, joined_at)
                VALUES (?, ?, ?, ?)
            """, (group_id, creator_id, None, datetime.now().isoformat()))
            
            # Add other members (by email)
            for email in members:
                try:
                    cur.execute("""
                        INSERT INTO group_members (group_id, user_id, email, joined_at)
                        VALUES (?, ?, ?, ?)
                    """, (group_id, None, email, datetime.now().isoformat()))
                except Exception as e:
                    # Skip duplicate emails
                    database_logger.warning(f"Could not add member {email} to group: {str(e)}")
            
            conn.commit()
            conn.close()
            
            database_logger.info(f"Group created: ID={group_id}, Name={group_name}, Creator={creator_id}, Members={len(members)}")
            return group_id
            
        except Exception as e:
            log_error(e, f"Failed to create group: {group_name}")
            return None
    
    @staticmethod
    @log_function_call(database_logger)
    def get_group(group_id):
        """Get group details"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, name, creator_id, session_id, mode, created_at
                FROM groups WHERE id = ?
            """, (group_id,))
            
            row = cur.fetchone()
            conn.close()
            
            if row:
                return {
                    'id': row[0],
                    'name': row[1],
                    'creator_id': row[2],
                    'session_id': row[3],
                    'mode': row[4],
                    'created_at': row[5]
                }
            return None
            
        except Exception as e:
            log_error(e, f"Failed to get group: {group_id}")
            return None
    
    @staticmethod
    @log_function_call(database_logger)
    def get_group_members(group_id):
        """Get group members"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, group_id, user_id, email, joined_at
                FROM group_members WHERE group_id = ?
                ORDER BY joined_at ASC
            """, (group_id,))
            
            rows = cur.fetchall()
            conn.close()
            
            members = []
            for row in rows:
                members.append({
                    'id': row[0],
                    'group_id': row[1],
                    'user_id': row[2],
                    'email': row[3],
                    'joined_at': row[4]
                })
            
            return members
            
        except Exception as e:
            log_error(e, f"Failed to get group members: {group_id}")
            return []
    
    @staticmethod
    @log_function_call(database_logger)
    def add_message(group_id, sender_id, sender_name, message):
        """Add message to group"""
        try:
            message_id = f"msg_{uuid.uuid4().hex[:12]}"
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO group_messages (id, group_id, sender_id, sender_name, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (message_id, group_id, sender_id, sender_name, message, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            database_logger.info(f"Message added to group: Group={group_id}, Sender={sender_id}")
            return message_id
            
        except Exception as e:
            log_error(e, f"Failed to add message to group: {group_id}")
            return None
    
    @staticmethod
    @log_function_call(database_logger)
    def get_group_messages(group_id, limit=100):
        """Get group messages"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, group_id, sender_id, sender_name, message, created_at
                FROM group_messages WHERE group_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (group_id, limit))
            
            rows = cur.fetchall()
            conn.close()
            
            messages = []
            for row in rows:
                messages.append({
                    'id': row[0],
                    'group_id': row[1],
                    'sender_id': row[2],
                    'sender_name': row[3],
                    'message': row[4],
                    'created_at': row[5]
                })
            
            # Reverse to get chronological order
            return list(reversed(messages))
            
        except Exception as e:
            log_error(e, f"Failed to get group messages: {group_id}")
            return []
    
    @staticmethod
    @log_function_call(database_logger)
    def get_user_groups(user_id, user_email=None):
        """Get all groups for a user (both created and invited)"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Query groups where user is a member (by user_id OR by email)
            if user_email:
                cur.execute("""
                    SELECT DISTINCT g.id, g.name, g.creator_id, g.session_id, g.mode, g.created_at
                    FROM groups g
                    JOIN group_members gm ON g.id = gm.group_id
                    WHERE gm.user_id = ? OR gm.email = ?
                    ORDER BY g.created_at DESC
                """, (user_id, user_email))
            else:
                cur.execute("""
                    SELECT DISTINCT g.id, g.name, g.creator_id, g.session_id, g.mode, g.created_at
                    FROM groups g
                    JOIN group_members gm ON g.id = gm.group_id
                    WHERE gm.user_id = ?
                    ORDER BY g.created_at DESC
                """, (user_id,))
            
            rows = cur.fetchall()
            conn.close()
            
            groups = []
            for row in rows:
                groups.append({
                    'id': row[0],
                    'name': row[1],
                    'creator_id': row[2],
                    'session_id': row[3],
                    'mode': row[4],
                    'created_at': row[5]
                })
            
            return groups
            
        except Exception as e:
            log_error(e, f"Failed to get user groups: {user_id}")
            return []
    
    @staticmethod
    @log_function_call(database_logger)
    def update_invited_user_id(user_id, user_email):
        """Update user_id for invited members when they log in"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Update all group_members rows where email matches but user_id is NULL
            cur.execute("""
                UPDATE group_members
                SET user_id = ?
                WHERE email = ? AND user_id IS NULL
            """, (user_id, user_email))
            
            updated_count = cur.rowcount
            conn.commit()
            conn.close()
            
            if updated_count > 0:
                database_logger.info(f"Updated {updated_count} group member(s) with user_id for email: {user_email}")
            
            return updated_count
            
        except Exception as e:
            log_error(e, f"Failed to update invited user id: {user_email}")
            return 0


# Standalone functions for group chat operations (used by controller)

@log_function_call(database_logger)
def create_group_chat(creator_id, group_name, members=None, session_id=None, mode='pakwheels', original_session_id=None, cloned_messages=None):
    """Create a new group chat with members"""
    try:
        # Handle members parameter - can be None or empty list
        if members is None:
            members = []
        
        group_id = f"group_{uuid.uuid4().hex[:12]}"
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create group
        cur.execute("""
            INSERT INTO groups (id, name, creator_id, session_id, mode, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (group_id, group_name, creator_id, original_session_id or session_id, mode, datetime.now().isoformat()))
        
        # Add creator as member
        cur.execute("""
            INSERT INTO group_members (group_id, user_id, email, joined_at)
            VALUES (?, ?, ?, ?)
        """, (group_id, creator_id, None, datetime.now().isoformat()))
        
        # Add other members (by email or user_id)
        for member in members:
            try:
                # Check if member is an email or user_id
                if isinstance(member, str) and '@' in member:
                    # It's an email
                    cur.execute("""
                        INSERT INTO group_members (group_id, user_id, email, joined_at)
                        VALUES (?, ?, ?, ?)
                    """, (group_id, None, member, datetime.now().isoformat()))
                else:
                    # It's a user_id
                    cur.execute("""
                        INSERT INTO group_members (group_id, user_id, email, joined_at)
                        VALUES (?, ?, ?, ?)
                    """, (group_id, member, None, datetime.now().isoformat()))
            except Exception as e:
                # Skip duplicate members
                database_logger.warning(f"Could not add member {member} to group: {str(e)}")
        
        conn.commit()
        conn.close()
        
        database_logger.info(f"Group created: ID={group_id}, Name={group_name}, Creator={creator_id}, Members={len(members)}")
        return {
            'success': True,
            'group_id': group_id,
            'group_name': group_name,
            'message_count': 0
        }
        
    except Exception as e:
        log_error(e, f"Failed to create group: {group_name}")
        return None


@log_function_call(database_logger)
def add_participant_to_group(group_id, participant):
    """Add a participant to a group
    
    Args:
        group_id: Group ID
        participant: Either user_id (int) or email (str)
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Determine if participant is user_id or email
        if isinstance(participant, int) or (isinstance(participant, str) and participant.isdigit()):
            # It's a user_id
            user_id = int(participant)
            email = None
            
            # Check if user already in group
            cur.execute("""
                SELECT id FROM group_members
                WHERE group_id = ? AND user_id = ?
            """, (group_id, user_id))
            
            if cur.fetchone():
                conn.close()
                return True  # Already a member
            
            # Add user to group
            cur.execute("""
                INSERT INTO group_members (group_id, user_id, email, joined_at)
                VALUES (?, ?, ?, ?)
            """, (group_id, user_id, None, datetime.now().isoformat()))
        else:
            # It's an email
            email = participant
            
            # Check if email already in group
            cur.execute("""
                SELECT id FROM group_members
                WHERE group_id = ? AND email = ?
            """, (group_id, email))
            
            if cur.fetchone():
                conn.close()
                return True  # Already invited
            
            # Add email to group (user_id will be set when they log in)
            cur.execute("""
                INSERT INTO group_members (group_id, user_id, email, joined_at)
                VALUES (?, ?, ?, ?)
            """, (group_id, None, email, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        database_logger.info(f"Participant added to group: Group={group_id}, Participant={participant}")
        return True
        
    except Exception as e:
        log_error(e, f"Failed to add participant to group: {group_id}")
        return False


@log_function_call(database_logger)
def remove_participant_from_group(group_id, user_id=None, email=None, requester_id=None):
    """Remove a participant from a group (requester must be owner)
    Can remove by user_id or by email
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if requester is group owner
        cur.execute("""
            SELECT creator_id FROM groups WHERE id = ?
        """, (group_id,))
        
        row = cur.fetchone()
        if not row or row[0] != requester_id:
            conn.close()
            return False  # Not authorized
        
        # Remove user from group (by user_id or email)
        if user_id:
            cur.execute("""
                DELETE FROM group_members
                WHERE group_id = ? AND user_id = ?
            """, (group_id, user_id))
        elif email:
            cur.execute("""
                DELETE FROM group_members
                WHERE group_id = ? AND email = ?
            """, (group_id, email))
        else:
            conn.close()
            return False
        
        conn.commit()
        conn.close()
        
        database_logger.info(f"Participant removed from group {group_id}: user_id={user_id}, email={email}")
        return True
        
    except Exception as e:
        log_error(e, f"Failed to remove participant from group: {group_id}")
        return False


@log_function_call(database_logger)
def get_group_chat_history(group_id, user_id, user_email=None, limit=100):
    """Get group chat message history"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if user is member of group (by user_id OR by email)
        if user_email:
            cur.execute("""
                SELECT id FROM group_members
                WHERE group_id = ? AND (user_id = ? OR email = ?)
            """, (group_id, user_id, user_email))
        else:
            cur.execute("""
                SELECT id FROM group_members
                WHERE group_id = ? AND user_id = ?
            """, (group_id, user_id))
        
        if not cur.fetchone():
            conn.close()
            return None  # User not authorized
        
        # Get messages with structured_data column
        cur.execute("""
            SELECT id, group_id, sender_id, sender_name, message, structured_data, created_at
            FROM group_messages
            WHERE group_id = ?
            ORDER BY created_at ASC
            LIMIT ?
        """, (group_id, limit))
        
        rows = cur.fetchall()
        messages = []
        for row in rows:
            messages.append({
                'id': row[0],
                'group_id': row[1],
                'sender_id': row[2],
                'sender_name': row[3],
                'message': row[4],
                'structured_data': row[5],
                'created_at': row[6]
            })
        
        conn.close()
        
        # Return in chronological order (oldest first)
        return messages
        
    except Exception as e:
        log_error(e, f"Failed to get group chat history: {group_id}")
        return None


@log_function_call(database_logger)
def add_message_to_group(group_id, user_id, query, response=None, structured_data=None):
    """Add a message to group chat
    
    Args:
        group_id: Group ID
        user_id: User ID of sender
        query: User's message/query
        response: AI response (optional, will be combined with query if provided)
        structured_data: Structured data from AI response (optional)
    """
    try:
        import json
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get sender name
        cur.execute("""
            SELECT username FROM users WHERE id = ?
        """, (user_id,))
        
        row = cur.fetchone()
        sender_name = row[0] if row else f"User {user_id}"
        
        # Combine query and response for the message
        if response:
            full_message = f"**User:** {query}\n\n**AI Response:** {response}"
        else:
            full_message = query
        
        # Convert structured_data to JSON string if it's a dict
        structured_data_json = None
        if structured_data:
            if isinstance(structured_data, dict):
                structured_data_json = json.dumps(structured_data)
            else:
                structured_data_json = structured_data
        
        # Add message with structured_data column
        cur.execute("""
            INSERT INTO group_messages (id, group_id, sender_id, sender_name, message, structured_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (message_id, group_id, user_id, sender_name, full_message, structured_data_json, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        database_logger.info(f"Message added to group: Group={group_id}, Sender={user_id}")
        return message_id
        
    except Exception as e:
        log_error(e, f"Failed to add message to group: {group_id}")
        return None


@log_function_call(database_logger)
def get_user_group_chats(user_id, user_email=None):
    """Get all group chats for a user (both created and invited by email)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get groups where user is a member (by user_id OR by email)
        if user_email:
            cur.execute("""
                SELECT DISTINCT g.id, g.name, g.creator_id, g.session_id, g.mode, g.created_at
                FROM groups g
                JOIN group_members gm ON g.id = gm.group_id
                WHERE gm.user_id = ? OR gm.email = ?
                ORDER BY g.created_at DESC
            """, (user_id, user_email))
        else:
            cur.execute("""
                SELECT DISTINCT g.id, g.name, g.creator_id, g.session_id, g.mode, g.created_at
                FROM groups g
                JOIN group_members gm ON g.id = gm.group_id
                WHERE gm.user_id = ?
                ORDER BY g.created_at DESC
            """, (user_id,))
        
        rows = cur.fetchall()
        conn.close()
        
        groups = []
        for row in rows:
            groups.append({
                'id': row[0],
                'name': row[1],
                'creator_id': row[2],
                'session_id': row[3],
                'mode': row[4],
                'created_at': row[5]
            })
        
        database_logger.info(f"Retrieved {len(groups)} groups for user {user_id} (email: {user_email})")
        return groups
        
    except Exception as e:
        log_error(e, f"Failed to get user group chats: {user_id}")
        return []


@log_function_call(database_logger)
def delete_group_chat(group_id, requester_id):
    """Delete a group chat (owner only)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if requester is group owner
        cur.execute("""
            SELECT creator_id FROM groups WHERE id = ?
        """, (group_id,))
        
        row = cur.fetchone()
        if not row or row[0] != requester_id:
            conn.close()
            return False  # Not authorized
        
        # Delete group messages
        cur.execute("""
            DELETE FROM group_messages WHERE group_id = ?
        """, (group_id,))
        
        # Delete group members
        cur.execute("""
            DELETE FROM group_members WHERE group_id = ?
        """, (group_id,))
        
        # Delete group
        cur.execute("""
            DELETE FROM groups WHERE id = ?
        """, (group_id,))
        
        conn.commit()
        conn.close()
        
        database_logger.info(f"Group deleted: {group_id}")
        return True
        
    except Exception as e:
        log_error(e, f"Failed to delete group: {group_id}")
        return False


@log_function_call(database_logger)
def get_group_chat_info(group_id, user_id, user_email=None):
    """Get detailed group chat information"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if user is member of group (by user_id OR by email)
        if user_email:
            cur.execute("""
                SELECT id FROM group_members
                WHERE group_id = ? AND (user_id = ? OR email = ?)
            """, (group_id, user_id, user_email))
        else:
            cur.execute("""
                SELECT id FROM group_members
                WHERE group_id = ? AND user_id = ?
            """, (group_id, user_id))
        
        if not cur.fetchone():
            conn.close()
            return None  # User not authorized
        
        # Get group info
        cur.execute("""
            SELECT id, name, creator_id, session_id, mode, created_at
            FROM groups WHERE id = ?
        """, (group_id,))
        
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        
        # Get members
        cur.execute("""
            SELECT user_id, email FROM group_members WHERE group_id = ?
        """, (group_id,))
        
        members = []
        for member_row in cur.fetchall():
            if member_row[0]:
                # Get username for user_id
                cur.execute("""
                    SELECT username FROM users WHERE id = ?
                """, (member_row[0],))
                user_row = cur.fetchone()
                members.append({
                    'user_id': member_row[0],
                    'username': user_row[0] if user_row else f"User {member_row[0]}",
                    'email': member_row[1]
                })
            else:
                members.append({
                    'user_id': None,
                    'username': member_row[1],
                    'email': member_row[1]
                })
        
        conn.close()
        
        return {
            'id': row[0],
            'name': row[1],
            'creator_id': row[2],
            'session_id': row[3],
            'mode': row[4],
            'created_at': row[5],
            'members': members,
            'member_count': len(members)
        }
        
    except Exception as e:
        log_error(e, f"Failed to get group info: {group_id}")
        return None


@log_function_call(database_logger)
def clear_group_messages(group_id):
    """Clear all messages in a group chat"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Delete all messages for the group
        cur.execute("""
            DELETE FROM group_messages WHERE group_id = ?
        """, (group_id,))
        
        conn.commit()
        conn.close()
        
        database_logger.info(f"Group messages cleared: {group_id}")
        return True
        
    except Exception as e:
        log_error(e, f"Failed to clear group messages: {group_id}")
        return False


@log_function_call(database_logger)
def update_group_mode(group_id, mode, requester_id):
    """Update group mode (creator only)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if requester is group creator
        cur.execute("""
            SELECT creator_id FROM groups WHERE id = ?
        """, (group_id,))
        
        row = cur.fetchone()
        if not row or row[0] != requester_id:
            conn.close()
            return False  # Not authorized
        
        # Update group mode
        cur.execute("""
            UPDATE groups SET mode = ? WHERE id = ?
        """, (mode, group_id))
        
        conn.commit()
        conn.close()
        
        database_logger.info(f"Group mode updated: {group_id} -> {mode}")
        return True
        
    except Exception as e:
        log_error(e, f"Failed to update group mode: {group_id}")
        return False




@log_function_call(database_logger)
def get_group_settings(group_id):
    """Get group mode setting"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT mode FROM groups WHERE id = ?
        """, (group_id,))
        
        row = cur.fetchone()
        conn.close()
        
        if row:
            return {
                'mode': row[0]
            }
        return None
        
    except Exception as e:
        log_error(e, f"Failed to get group settings: {group_id}")
        return None
