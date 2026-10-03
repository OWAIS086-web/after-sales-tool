from flask import render_template, request, jsonify, flash, url_for
from flask_login import current_user, login_required
from models.whatsapp import WhatsAppMessage
from utils.logger import whatsapp_logger, log_function_call, log_user_action, log_error
import urllib.parse
import json
import os


@log_function_call(whatsapp_logger)
def view_whatsapp():
    """WhatsApp Analytics Dashboard - Similar to Analytics Dashboard"""

    # Get user permissions and config
    from models.datasource_permissions import DataSourcePermissions
    from config.config_loader import get_config
    from scheduler.decorators import is_admin_user
    user_permissions = DataSourcePermissions.get_user_permissions(current_user.id)
    
    config = get_config()
    is_admin = is_admin_user(current_user)

    # Check if user has access to WhatsApp data (only Haval users)
    user_company = current_user.company_id or 'haval'
    whatsapp_logger.info(f"WhatsApp analytics accessed by user {current_user.username} (company: {user_company})")
    
    if user_company != 'haval':
        whatsapp_logger.warning(f"WhatsApp access denied for user {current_user.username} (company: {user_company})")
        log_user_action("WhatsApp Access Denied", current_user.id, f"Company: {user_company}")
        
        flash(f"WhatsApp data is only available for Haval users. You are registered as {user_company.title()} user.", "error")
        return render_template("access_denied.html", 
                             message="WhatsApp Access Restricted",
                             description=f"WhatsApp data is only available for Haval users. You are registered as a {user_company.title()} user.",
                             redirect_url=url_for('chatbot_advanced'),
                             redirect_text="Go to Chatbot")
    
    try:
        from models.analytics import Analytics
        
        # Get WhatsApp analytics data
        whatsapp_stats = Analytics.get_whatsapp_analytics(user_company)
        complaint_analysis = Analytics.get_complaint_analysis(user_company)
        whatsapp_complaints = complaint_analysis.get("whatsapp", [])
        
        # Calculate stats
        total_messages = whatsapp_stats.get("total_messages", 0)
        unique_customers = whatsapp_stats.get("unique_customers", 0)
        common_queries = len(whatsapp_stats.get("common_queries", []))
        complaints_count = len(whatsapp_complaints)
        
        # Get message type data
        message_types = whatsapp_stats.get("message_types", {})
        queries = message_types.get("query", 0)
        complaints = message_types.get("complaint", 0)
        support = message_types.get("support", 0)
        general = message_types.get("general", 0)
        
        whatsapp_logger.info(f"WhatsApp analytics loaded for {current_user.username}")
        log_user_action("WhatsApp Analytics", current_user.id, f"Messages: {total_messages}, Customers: {unique_customers}")
        
        return render_template(
            "whatsapp_analytics.html",
            total_messages=total_messages,
            unique_customers=unique_customers,
            common_queries=common_queries,
            complaints_count=complaints_count,
            queries=queries,
            complaints=complaints,
            support=support,
            general=general,
            user_company=user_company,
            company_name="HAVAL",
            whatsapp_complaints=whatsapp_complaints,
            selected_company=user_company,
            user_permissions=user_permissions,
            config=config,
            user=current_user,
            is_admin=is_admin
        )
        
    except Exception as e:
        log_error(e, f"Error in WhatsApp analytics for user {current_user.username}")
        whatsapp_logger.error(f"Error in view_whatsapp: {str(e)}")
        
        flash("Error loading WhatsApp analytics data", "error")
        return render_template("error.html", error="WhatsApp analytics unavailable")


@log_function_call(whatsapp_logger)
def view_whatsapp_by_customer(customer_name):
    """Show all WhatsApp messages for a specific customer - Only for Haval users"""

    # Get user permissions and config
    from models.datasource_permissions import DataSourcePermissions
    from config.config_loader import get_config
    from scheduler.decorators import is_admin_user
    user_permissions = DataSourcePermissions.get_user_permissions(current_user.id)
    config = get_config()
    is_admin = is_admin_user(current_user)

    # Check if user has access to WhatsApp data (only Haval users)
    user_company = current_user.company_id or 'haval'
    
    # Decode the customer name from URL
    decoded_customer = urllib.parse.unquote(customer_name)
    
    whatsapp_logger.info(f"WhatsApp customer view accessed by user {current_user.username} for customer: {decoded_customer}")
    
    if user_company != 'haval':
        whatsapp_logger.warning(f"WhatsApp customer access denied for user {current_user.username} (company: {user_company})")
        log_user_action("WhatsApp Customer Access Denied", current_user.id, f"Company: {user_company}, Customer: {decoded_customer}")
        
        flash(f"WhatsApp data is only available for Haval users. You are registered as {user_company.title()} user.", "error")
        return render_template("access_denied.html", 
                             message="WhatsApp Access Restricted",
                             description=f"WhatsApp data is only available for Haval users. You are registered as a {user_company.title()} user.",
                             redirect_url=url_for('chatbot_advanced'),
                             redirect_text="Go to Chatbot")
    
    try:
        # Get all messages for this customer
        whatsapp_logger.info(f"Fetching messages for customer {decoded_customer} by user {current_user.username}")
        messages = WhatsAppMessage.get_messages_by_customer(decoded_customer, user_company)
        
        # Convert to dict format for template and filter duplicates
        messages_list = []
        seen_messages = set()
        
        for msg in messages:
            message_text = msg.message.lower().strip() if msg.message else ""
            
            # Skip if duplicate (exact match)
            if message_text in seen_messages:
                continue
            
            # Check for near-duplicates (85% similarity)
            is_duplicate = False
            for seen_msg in seen_messages:
                if len(message_text) > 20 and len(seen_msg) > 20:
                    # Simple similarity check
                    common_chars = sum(1 for a, b in zip(message_text, seen_msg) if a == b)
                    similarity = common_chars / max(len(message_text), len(seen_msg))
                    if similarity > 0.85:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                seen_messages.add(message_text)
                messages_list.append({
                    'id': msg.id,
                    'customer_name': msg.customer_name,
                    'country_code': msg.country_code,
                    'contact_number': msg.contact_number,
                    'message_type': msg.message_type,
                    'message': msg.message,
                    'timestamp': msg.timestamp,
                    'imported_at': msg.imported_at,
                    'phone_number': f"+{msg.country_code}{msg.contact_number}" if msg.country_code and msg.contact_number else "N/A"
                })
        
        whatsapp_logger.info(f"Customer messages loaded for {current_user.username}: {len(messages_list)} unique messages for {decoded_customer} (filtered duplicates)")
        log_user_action("WhatsApp Customer View", current_user.id, 
                       f"Customer: {decoded_customer}, Messages: {len(messages_list)}")
        
    except Exception as e:
        log_error(e, f"Error getting customer messages for user {current_user.username}, customer {decoded_customer}")
        whatsapp_logger.error(f"Error getting customer messages for {current_user.username}: {str(e)}")
        messages_list = []
    
    return render_template("view_whatsapp_detail_pro.html",
                         customer_name=decoded_customer,
                         messages=messages_list,
                         total_messages=len(messages_list),
                         selected_company=user_company,
                         user_permissions=user_permissions,
                         config=config,
                         user=current_user,
                         is_admin=is_admin)


@log_function_call(whatsapp_logger)
def debug_whatsapp():
    """Debug route to check WhatsApp messages in database"""
    from models.database import get_db_connection
    
    whatsapp_logger.info(f"WhatsApp debug accessed by user {current_user.username}")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='whatsapp_messages'")
        table_exists = cur.fetchone()
        
        if not table_exists:
            conn.close()
            whatsapp_logger.warning(f"WhatsApp debug: table does not exist for user {current_user.username}")
            return jsonify({"error": "whatsapp_messages table does not exist"})
        
        # Get table schema
        cur.execute("PRAGMA table_info(whatsapp_messages)")
        schema = cur.fetchall()
        
        # Get sample data
        cur.execute("SELECT * FROM whatsapp_messages LIMIT 5")
        sample_data = cur.fetchall()
        
        # Get count
        cur.execute("SELECT COUNT(*) FROM whatsapp_messages")
        total_count = cur.fetchone()[0]
        
        conn.close()
        
        debug_result = {
            "table_exists": True,
            "schema": [{"column": row[1], "type": row[2]} for row in schema],
            "total_count": total_count,
            "sample_data": [dict(row) for row in sample_data]
        }
        
        whatsapp_logger.info(f"WhatsApp debug completed for {current_user.username}: {total_count} total messages")
        log_user_action("WhatsApp Debug", current_user.id, f"Total messages: {total_count}")
        
        return jsonify(debug_result)
        
    except Exception as e:
        log_error(e, f"WhatsApp debug error for user {current_user.username}")
        whatsapp_logger.error(f"WhatsApp debug error for {current_user.username}: {str(e)}")
        return jsonify({"error": str(e)})


@log_function_call(whatsapp_logger)
def fetch_wati_data():
    """Fetch latest contacts and messages from WATI API - Only for Haval users"""
    
    # Check if user has access to WhatsApp data (only Haval users)
    user_company = current_user.company_id or 'haval'
    
    whatsapp_logger.info(f"WATI data fetch requested by user {current_user.username} (company: {user_company})")
    
    if user_company != 'haval':
        whatsapp_logger.warning(f"WATI access denied for user {current_user.username} (company: {user_company})")
        log_user_action("WATI Access Denied", current_user.id, f"Company: {user_company}")
        
        flash(f"WATI data access is only available for Haval users. You are registered as {user_company.title()} user.", "error")
        return render_template("access_denied.html", 
                             message="WATI Access Restricted",
                             description=f"WATI data access is only available for Haval users. You are registered as a {user_company.title()} user.",
                             redirect_url=url_for('chatbot_advanced'),
                             redirect_text="Go to Chatbot")
    
    try:
        # Get time period from form
        time_period = request.form.get('period', '24h')
        
        whatsapp_logger.info(f"WATI fetch started by {current_user.username}: period={time_period}")
        
        # Import WATI functionality
        from controllers.wati_integration import fetch_and_import_wati_data
        
        # Fetch data from WATI API
        whatsapp_logger.info(f"Calling WATI integration for user {current_user.username}")
        result = fetch_and_import_wati_data(user_company, time_period)
        
        if result['success']:
            messages_imported = result.get('messages_imported', 0)
            messages_skipped = result.get('messages_skipped', 0)
            contacts_fetched = result.get('contacts_fetched', 0)
            
            whatsapp_logger.info(f"WATI fetch successful for {current_user.username}: {messages_imported} imported, {messages_skipped} skipped, {contacts_fetched} contacts")
            log_user_action("WATI Fetch Success", current_user.id, 
                           f"Period: {time_period}, Imported: {messages_imported}, Skipped: {messages_skipped}, Contacts: {contacts_fetched}")
            
            flash(f"Successfully imported {messages_imported} new messages from WATI API.", "success")
            if messages_skipped > 0:
                flash(f"Skipped {messages_skipped} duplicate messages.", "info")
        else:
            error_msg = result.get('error', 'Unknown error')
            whatsapp_logger.error(f"WATI fetch failed for {current_user.username}: {error_msg}")
            log_user_action("WATI Fetch Failed", current_user.id, f"Period: {time_period}, Error: {error_msg}")
            
            flash(f"Error importing WATI data: {error_msg}", "error")
        
        return jsonify(result)
        
    except ImportError:
        error_msg = "WATI integration module not found"
        whatsapp_logger.error(f"WATI import error for {current_user.username}: {error_msg}")
        log_user_action("WATI Import Error", current_user.id, error_msg)
        
        flash("WATI integration is not available. Please check your configuration.", "error")
        return jsonify({
            "success": False,
            "error": error_msg
        })
    except Exception as e:
        error_msg = str(e)
        log_error(e, f"WATI fetch error for user {current_user.username}")
        whatsapp_logger.error(f"WATI fetch error for {current_user.username}: {error_msg}")
        log_user_action("WATI Fetch Error", current_user.id, f"Error: {error_msg}")
        
        flash(f"Error fetching WATI data: {error_msg}", "error")
        return jsonify({
            "success": False,
            "error": error_msg
        })



@log_function_call(whatsapp_logger)
def get_whatsapp_stats_api():
    """API endpoint to get WhatsApp statistics - Only for Haval users"""
    
    # Check if user has access to WhatsApp data (only Haval users)
    user_company = current_user.company_id or 'haval'
    
    if user_company != 'haval':
        whatsapp_logger.warning(f"WhatsApp stats API access denied for user {current_user.username} (company: {user_company})")
        return jsonify({
            "success": False,
            "error": "Access denied"
        }), 403
    
    try:
        # Get filter parameters
        date_filter = request.args.get('date', 'all')
        
        # Get statistics
        whatsapp_logger.info(f"Fetching WhatsApp stats API for user {current_user.username}")
        stats = WhatsAppMessage.get_statistics(
            company_id=user_company,
            date_filter=date_filter
        )
        
        whatsapp_logger.info(f"WhatsApp stats API returned for {current_user.username}: total_messages={stats.get('total_messages')}, total_complaints={stats.get('total_complaints')}, total_queries={stats.get('total_queries')}")
        
        return jsonify(stats)
        
    except Exception as e:
        log_error(e, f"Error getting WhatsApp stats API for user {current_user.username}")
        whatsapp_logger.error(f"WhatsApp stats API error for {current_user.username}: {str(e)}")
        
        return jsonify({
            "success": False,
            "error": str(e),
            "total_messages": 0,
            "total_complaints": 0,
            "total_queries": 0,
            "unique_customers": 0,
            "message_types": {},
            "daily_activity": {}
        }), 500


@log_function_call(whatsapp_logger)
def view_whatsapp_conversations():
    """Show all WhatsApp conversations grouped by customer and date - Only for Haval users"""

    # Get user permissions and config
    from models.datasource_permissions import DataSourcePermissions
    from config.config_loader import get_config
    from scheduler.decorators import is_admin_user
    user_permissions = DataSourcePermissions.get_user_permissions(current_user.id)
    config = get_config()
    is_admin = is_admin_user(current_user)

    # Check if user has access to WhatsApp data (only Haval users)
    user_company = current_user.company_id or 'haval'
    whatsapp_logger.info(f"WhatsApp conversations view accessed by user {current_user.username}")
    
    if user_company != 'haval':
        whatsapp_logger.warning(f"WhatsApp conversations access denied for user {current_user.username} (company: {user_company})")
        log_user_action("WhatsApp Conversations Access Denied", current_user.id, f"Company: {user_company}")
        
        flash(f"WhatsApp data is only available for Haval users. You are registered as {user_company.title()} user.", "error")
        return render_template("access_denied.html", 
                             message="WhatsApp Access Restricted",
                             description=f"WhatsApp data is only available for Haval users. You are registered as a {user_company.title()} user.",
                             redirect_url=url_for('chatbot_advanced'),
                             redirect_text="Go to Chatbot")
    
    try:
        # Get all conversations
        whatsapp_logger.info(f"Fetching conversations for user {current_user.username}")
        conversations = WhatsAppMessage.get_conversations(user_company, limit=500)
        
        whatsapp_logger.info(f"Conversations loaded for {current_user.username}: {len(conversations)} conversations")
        log_user_action("WhatsApp Conversations View", current_user.id, f"Conversations: {len(conversations)}")
        
        return render_template("view_whatsapp_conversations.html",
                             conversations=conversations,
                             total_conversations=len(conversations),
                             selected_company=user_company,
                             user_permissions=user_permissions,
                             config=config,
                             user=current_user,
                             is_admin=is_admin)
        
    except Exception as e:
        log_error(e, f"Error getting conversations for user {current_user.username}")
        whatsapp_logger.error(f"Error getting conversations for {current_user.username}: {str(e)}")
        
        flash("Error loading WhatsApp conversations", "error")
        return render_template("error.html", error="WhatsApp conversations unavailable")


@log_function_call(whatsapp_logger)
def view_whatsapp_conversation(customer_name, conversation_date):
    """Show all messages for a specific conversation (customer + date) - Only for Haval users"""

    # Get user permissions and config
    from models.datasource_permissions import DataSourcePermissions
    from config.config_loader import get_config
    from scheduler.decorators import is_admin_user
    user_permissions = DataSourcePermissions.get_user_permissions(current_user.id)
    config = get_config()
    is_admin = is_admin_user(current_user)

    # Check if user has access to WhatsApp data (only Haval users)
    user_company = current_user.company_id or 'haval'

    # Decode the customer name from URL
    decoded_customer = urllib.parse.unquote(customer_name)
    
    whatsapp_logger.info(f"WhatsApp conversation view accessed by user {current_user.username} for customer: {decoded_customer}, date: {conversation_date}")
    
    if user_company != 'haval':
        whatsapp_logger.warning(f"WhatsApp conversation access denied for user {current_user.username} (company: {user_company})")
        log_user_action("WhatsApp Conversation Access Denied", current_user.id, f"Company: {user_company}, Customer: {decoded_customer}, Date: {conversation_date}")
        
        flash(f"WhatsApp data is only available for Haval users. You are registered as {user_company.title()} user.", "error")
        return render_template("access_denied.html", 
                             message="WhatsApp Access Restricted",
                             description=f"WhatsApp data is only available for Haval users. You are registered as a {user_company.title()} user.",
                             redirect_url=url_for('chatbot_advanced'),
                             redirect_text="Go to Chatbot")
    
    try:
        # Get all messages for this conversation
        whatsapp_logger.info(f"Fetching conversation messages for customer {decoded_customer}, date {conversation_date} by user {current_user.username}")
        messages = WhatsAppMessage.get_conversation_messages(decoded_customer, conversation_date, user_company)
        
        # Convert to dict format for template
        messages_list = []
        for msg in messages:
            messages_list.append({
                'id': msg.id,
                'customer_name': msg.customer_name,
                'country_code': msg.country_code,
                'contact_number': msg.contact_number,
                'message_type': msg.message_type,
                'message': msg.message,
                'timestamp': msg.timestamp,
                'imported_at': msg.imported_at,
                'sender': msg.sender,
                'phone_number': f"+{msg.country_code}{msg.contact_number}" if msg.country_code and msg.contact_number else "N/A"
            })
        
        whatsapp_logger.info(f"Conversation messages loaded for {current_user.username}: {len(messages_list)} messages for {decoded_customer} on {conversation_date}")
        log_user_action("WhatsApp Conversation View", current_user.id, 
                       f"Customer: {decoded_customer}, Date: {conversation_date}, Messages: {len(messages_list)}")
        
    except Exception as e:
        log_error(e, f"Error getting conversation messages for user {current_user.username}, customer {decoded_customer}, date {conversation_date}")
        whatsapp_logger.error(f"Error getting conversation messages for {current_user.username}: {str(e)}")
        messages_list = []
    
    return render_template("view_whatsapp_conversation_detail.html",
                         customer_name=decoded_customer,
                         conversation_date=conversation_date,
                         messages=messages_list,
                         total_messages=len(messages_list),
                         selected_company=user_company,
                         user_permissions=user_permissions,
                         config=config,
                         user=current_user,
                         is_admin=is_admin)



@log_function_call(whatsapp_logger)
def get_whatsapp_conversations_api():
    """API endpoint to get all WhatsApp conversations - Only for Haval users"""
    
    # Check if user has access to WhatsApp data (only Haval users)
    user_company = current_user.company_id or 'haval'
    
    if user_company != 'haval':
        whatsapp_logger.warning(f"WhatsApp conversations API access denied for user {current_user.username} (company: {user_company})")
        return jsonify({
            "success": False,
            "error": "Access denied"
        }), 403
    
    try:
        # Get all conversations
        whatsapp_logger.info(f"Fetching conversations API for user {current_user.username}")
        conversations = WhatsAppMessage.get_conversations(user_company, limit=500)
        
        # Format for API response
        formatted_conversations = []
        for conv in conversations:
            formatted_conversations.append({
                'customer_name': conv['customer_name'],
                'conversation_date': conv['conversation_date'],
                'message_count': conv['message_count'],
                'last_message_time': conv['last_message_time'],
                'message_types': conv['message_types']
            })
        
        whatsapp_logger.info(f"Conversations API returned for {current_user.username}: {len(formatted_conversations)} conversations")
        
        return jsonify({
            "success": True,
            "conversations": formatted_conversations,
            "total": len(formatted_conversations)
        })
        
    except Exception as e:
        log_error(e, f"Error getting conversations API for user {current_user.username}")
        whatsapp_logger.error(f"Conversations API error for {current_user.username}: {str(e)}")
        
        return jsonify({
            "success": False,
            "error": str(e),
            "conversations": []
        }), 500


@log_function_call(whatsapp_logger)
def view_whatsapp_chat():
    """Show WhatsApp chat interface with conversation list and message thread - Only for Haval users"""

    # Get user permissions and config
    from models.datasource_permissions import DataSourcePermissions
    from config.config_loader import get_config
    from scheduler.decorators import is_admin_user
    import sqlite3
    
    user_permissions = DataSourcePermissions.get_user_permissions(current_user.id)
    config = get_config()
    is_admin = is_admin_user(current_user)

    # Check if user has access to WhatsApp data (only Haval users)
    user_company = current_user.company_id or 'haval'
    
    whatsapp_logger.info(f"WhatsApp chat view accessed by user {current_user.username} (company: {user_company})")
    
    # Allow access for haval users
    if user_company not in ['haval', None, '']:
        whatsapp_logger.warning(f"WhatsApp chat access denied for user {current_user.username} (company: {user_company})")
        log_user_action("WhatsApp Chat Access Denied", current_user.id, f"Company: {user_company}")
        
        flash(f"WhatsApp data is only available for Haval users. You are registered as {user_company.title()} user.", "error")
        return render_template("access_denied.html", 
                             message="WhatsApp Access Restricted",
                             description=f"WhatsApp data is only available for Haval users. You are registered as a {user_company.title()} user.",
                             redirect_url=url_for('chatbot_advanced'),
                             redirect_text="Go to Chatbot")
    
    # Get customer name and phone from query params
    customer_name = request.args.get('customer_name', '')
    phone_number = request.args.get('phone_number', '')
    
    messages_list = []
    conversations = []
    
    try:
        # Connect to posts.db directly (where WhatsApp messages are stored)
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'posts.db')
        
        if not os.path.exists(db_path):
            whatsapp_logger.error(f"Database file not found: {db_path}")
            print(f"ERROR: Database file not found: {db_path}")
        else:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            
            # Get all conversations from database
            cur.execute("""
                SELECT DISTINCT 
                    customer_name,
                    country_code,
                    contact_number,
                    MAX(timestamp) as last_message_time
                FROM whatsapp_messages
                GROUP BY customer_name
                ORDER BY last_message_time DESC
                LIMIT 500
            """)
            
            conv_rows = cur.fetchall()
            print(f"DEBUG: Found {len(conv_rows)} conversations")
            whatsapp_logger.info(f"Found {len(conv_rows)} conversations from database")
            
            # Get last message for each customer
            for row in conv_rows:
                conv_customer_name = row[0]
                country_code = row[1]
                contact_number = row[2]
                last_msg_time = row[3]
                
                conv_phone = f"+{country_code}{contact_number}" if country_code and contact_number else ""
                
                # Get last message text
                cur.execute("""
                    SELECT message FROM whatsapp_messages
                    WHERE customer_name = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (conv_customer_name,))
                
                last_msg_row = cur.fetchone()
                last_message = last_msg_row[0] if last_msg_row and last_msg_row[0] else ""
                
                conversations.append({
                    'customer_name': conv_customer_name,
                    'phone_number': conv_phone,
                    'last_message': last_message[:50] if last_message else '',
                    'last_message_time': last_msg_time if last_msg_time else ''
                })
            
            print(f"DEBUG: Built {len(conversations)} conversations")
            whatsapp_logger.info(f"Built {len(conversations)} conversations for sidebar")
            
            # If customer selected, get their messages
            if customer_name:
                decoded_customer = urllib.parse.unquote(customer_name)
                whatsapp_logger.info(f"Fetching messages for customer {decoded_customer} from database")
                
                # Get all messages for this customer
                cur.execute("""
                    SELECT id, customer_name, country_code, contact_number, message_type, message, timestamp, sender
                    FROM whatsapp_messages
                    WHERE customer_name = ?
                    ORDER BY timestamp ASC
                """, (decoded_customer,))
                
                msg_rows = cur.fetchall()
                whatsapp_logger.info(f"Found {len(msg_rows)} messages for customer {decoded_customer}")
                
                # Convert to dict format and determine sender type
                for msg_row in msg_rows:
                    msg_id = msg_row[0]
                    cust_name = msg_row[1]
                    country_code = msg_row[2]
                    contact_number = msg_row[3]
                    msg_type = msg_row[4]
                    msg_text = msg_row[5]
                    timestamp = msg_row[6]
                    sender = msg_row[7]
                    
                    sender_type = 'user'  # Default to user
                    if sender:
                        sender_lower = sender.lower().strip()
                        if sender_lower in ['bot', 'ai', 'system', 'assistant']:
                            sender_type = 'bot'
                        elif sender_lower in ['company', 'support', 'haval', 'sazgar', 'saz']:
                            sender_type = 'company'
                    
                    # Also check message content for company/bot indicators
                    if sender_type == 'user' and msg_text:
                        msg_lower = msg_text.lower()
                        # Keywords that indicate company/bot messages
                        company_keywords = [
                            'welcome to saz',
                            'sazgar automated',
                            'customer service',
                            'what would you like to do',
                            'products & prices',
                            'register a complaint',
                            'track your vehicle',
                            'find a dealership',
                            'book a vehicle',
                            'book a test drive',
                            'feedback',
                            'aftersales',
                            'maintenance',
                            'select 1',
                            'select 2',
                            'return to main menu',
                            'please share your pbo',
                            'booking form',
                            'customer service agent',
                            'expected delivery time',
                            'booked vehicle',
                            'hi ',  # Messages starting with "Hi [name]" are usually bot greetings
                            'hello ',
                            'dear ',
                            'thank you',
                            'regards',
                            'best regards',
                            'sincerely',
                            'we apologize',
                            'sir we',
                            'sir, kindly',
                            'noted, sir',
                            'sir or madam',
                            'ike is',
                            'please note',
                            'for further details',
                            'contact us',
                            'our team',
                            'we are happy'
                        ]
                        
                        for keyword in company_keywords:
                            if keyword in msg_lower:
                                sender_type = 'company'
                                break
                    
                    phone = f"+{country_code}{contact_number}" if country_code and contact_number else "N/A"
                    
                    messages_list.append({
                        'id': msg_id,
                        'customer_name': cust_name,
                        'phone_number': phone,
                        'message_type': 'message',  # Always set to 'message' to show 💬 Message
                        'message': msg_text,
                        'timestamp': timestamp,
                        'sender_type': sender_type
                    })
                
                whatsapp_logger.info(f"Chat messages loaded: {len(messages_list)} messages for {decoded_customer}")
                log_user_action("WhatsApp Chat View", current_user.id, 
                               f"Customer: {decoded_customer}, Messages: {len(messages_list)}")
            
            conn.close()
        
    except Exception as e:
        print(f"ERROR in view_whatsapp_chat: {str(e)}")
        import traceback
        traceback.print_exc()
        log_error(e, f"Error in WhatsApp chat view for user {current_user.username}")
        whatsapp_logger.error(f"Error in view_whatsapp_chat: {str(e)}", exc_info=True)
    
    print(f"DEBUG: Rendering template with {len(conversations)} conversations and {len(messages_list)} messages")
    
    return render_template("whatsapp_analytics.html",
                         customer_name=customer_name,
                         phone_number=phone_number,
                         messages=messages_list,
                         conversations=conversations,
                         selected_company=user_company,
                         user_permissions=user_permissions,
                         config=config,
                         user=current_user,
                         is_admin=is_admin)
