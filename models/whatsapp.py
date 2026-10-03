from .database import get_db_connection
from datetime import datetime
import sqlite3


class WhatsAppMessage:
    def __init__(self, id=None, customer_name=None, country_code=None, 
                 contact_number=None, message_type=None, message=None, 
                 timestamp=None, imported_at=None, sender=None, company_id=None,
                 complaint_category='none'):
        self.id = id
        self.customer_name = customer_name
        self.country_code = country_code
        self.contact_number = contact_number
        self.message_type = message_type
        self.message = message
        self.timestamp = timestamp
        self.imported_at = imported_at
        self.sender = sender
        self.company_id = company_id
        self.complaint_category = complaint_category

    @staticmethod
    def create_table():
        """Create WhatsApp messages table if it doesn't exist"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS whatsapp_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT,
                country_code INTEGER,
                contact_number TEXT,
                message_type TEXT,
                message TEXT,
                timestamp TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sender TEXT DEFAULT 'customer',
                company_id TEXT DEFAULT 'haval'
            )
        """)
        
        # Add company_id column if it doesn't exist (migration)
        try:
            cur.execute("ALTER TABLE whatsapp_messages ADD COLUMN company_id TEXT DEFAULT 'haval'")
        except sqlite3.OperationalError:
            # Column already exists
            pass
        
        # Add sender column if it doesn't exist (migration)
        try:
            cur.execute("ALTER TABLE whatsapp_messages ADD COLUMN sender TEXT DEFAULT 'customer'")
        except sqlite3.OperationalError:
            # Column already exists
            pass
        
        conn.commit()
        conn.close()

    @staticmethod
    def get_messages(company_id=None, message_type=None, customer_name=None, 
                    date_filter=None, limit=1000):
        """Get WhatsApp messages with filters"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        where_clauses = []
        params = []
        
        if company_id:
            where_clauses.append("company_id = ?")
            params.append(company_id)
        
        if message_type and message_type != 'all':
            where_clauses.append("message_type = ?")
            params.append(message_type)
        
        if customer_name:
            where_clauses.append("customer_name LIKE ?")
            params.append(f"%{customer_name}%")
        
        if date_filter and date_filter != 'all':
            if date_filter == 'today':
                where_clauses.append("DATE(timestamp) = DATE('now')")
            elif date_filter == 'week':
                where_clauses.append("DATE(timestamp) >= DATE('now', '-7 days')")
            elif date_filter == 'month':
                where_clauses.append("DATE(timestamp) >= DATE('now', '-30 days')")
        
        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        cur.execute(f"""
            SELECT id, customer_name, country_code, contact_number, message_type, 
                   message, timestamp, imported_at, sender, company_id
            FROM whatsapp_messages
            {where_sql}
            ORDER BY timestamp DESC
            LIMIT ?
        """, params + [limit])
        
        rows = cur.fetchall()
        conn.close()
        
        messages = []
        for row in rows:
            message = WhatsAppMessage(
                id=row[0], customer_name=row[1], country_code=row[2],
                contact_number=row[3], message_type=row[4], message=row[5],
                timestamp=row[6], imported_at=row[7],
                sender=row[8],
                company_id=row[9] if len(row) > 9 else 'haval'
            )
            messages.append(message)
        
        return messages

    @staticmethod
    def get_messages_by_customer(customer_name, company_id=None):
        """Get all messages for a specific customer"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        if company_id:
            cur.execute("""
                SELECT id, customer_name, country_code, contact_number, message_type, 
                       message, timestamp, imported_at, sender, company_id
                FROM whatsapp_messages 
                WHERE customer_name = ? AND company_id = ?
                ORDER BY timestamp ASC
            """, (customer_name, company_id))
        else:
            cur.execute("""
                SELECT id, customer_name, country_code, contact_number, message_type, 
                       message, timestamp, imported_at, sender, company_id
                FROM whatsapp_messages 
                WHERE customer_name = ?
                ORDER BY timestamp ASC
            """, (customer_name,))
        
        rows = cur.fetchall()
        conn.close()
        
        messages = []
        for row in rows:
            message = WhatsAppMessage(
                id=row[0], customer_name=row[1], country_code=row[2],
                contact_number=row[3], message_type=row[4], message=row[5],
                timestamp=row[6], imported_at=row[7],
                sender=row[8],
                company_id=row[9] if len(row) > 9 else 'haval'
            )
            messages.append(message)
        
        return messages

    @staticmethod
    def get_statistics(company_id=None, date_filter=None):
        """Get WhatsApp message statistics"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        where_clauses = []
        params = []
        
        if company_id:
            where_clauses.append("company_id = ?")
            params.append(company_id)
        
        if date_filter and date_filter != 'all':
            if date_filter == 'today':
                where_clauses.append("DATE(timestamp) = DATE('now')")
            elif date_filter == 'week':
                where_clauses.append("DATE(timestamp) >= DATE('now', '-7 days')")
            elif date_filter == 'month':
                where_clauses.append("DATE(timestamp) >= DATE('now', '-30 days')")
        
        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Total messages
        cur.execute(f"SELECT COUNT(*) FROM whatsapp_messages{where_sql}", params)
        total_messages = cur.fetchone()[0]
        
        # Messages by type
        cur.execute(f"""
            SELECT message_type, COUNT(*) 
            FROM whatsapp_messages{where_sql} 
            GROUP BY message_type
        """, params)
        message_types = {row[0]: row[1] for row in cur.fetchall()}
        
        # Total complaints and queries
        total_complaints = message_types.get('complaint', 0)
        total_queries = message_types.get('query', 0)
        
        # Unique customers
        cur.execute(f"SELECT COUNT(DISTINCT customer_name) FROM whatsapp_messages{where_sql}", params)
        unique_customers = cur.fetchone()[0]
        
        # Daily activity (last 7 days)
        activity_where = where_clauses + ["timestamp >= datetime('now', '-7 days')"] if where_clauses else ["timestamp >= datetime('now', '-7 days')"]
        cur.execute(f"""
            SELECT DATE(timestamp) as date, COUNT(*) as count
            FROM whatsapp_messages 
            WHERE {' AND '.join(activity_where)}
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """, params)
        daily_activity = {row[0]: row[1] for row in cur.fetchall()}
        
        conn.close()
        
        return {
            "total_messages": total_messages,
            "message_types": message_types,
            "total_complaints": total_complaints,
            "total_queries": total_queries,
            "unique_customers": unique_customers,
            "daily_activity": daily_activity
        }

    @staticmethod
    def get_unique_customers(company_id=None):
        """Get list of unique customers"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        if company_id:
            cur.execute("""
                SELECT DISTINCT customer_name 
                FROM whatsapp_messages 
                WHERE company_id = ?
                ORDER BY customer_name
            """, (company_id,))
        else:
            cur.execute("""
                SELECT DISTINCT customer_name 
                FROM whatsapp_messages 
                ORDER BY customer_name
            """)
        
        customers = [row[0] for row in cur.fetchall()]
        conn.close()
        
        return customers

    @staticmethod
    def classify_message(text):
        """Classify WhatsApp message as 'complaint', 'query', or 'chat'"""
        text_lower = text.lower()
        
        # Complaint indicators - Comprehensive list synchronized with posts
        complaint_words = [
            'problem', 'issue', 'complaint', 'not working', 'broken', 
            'defect', 'fault', 'disappointed', 'bad', 'poor', 'worst',
            'terrible', 'awful', 'hate', 'disappointing'
        ]
        if any(word in text_lower for word in complaint_words):
            return 'complaint'
        
        # Query indicators
        query_words = ['how', 'what', 'when', 'where', 'why', 'can you', 'please', '?']
        if any(word in text_lower for word in query_words) or '?' in text:
            return 'query'
        
        # Default to chat
        return 'chat'

    @staticmethod
    def classify_sender(text, customer_name=None):
        """Heuristic to determine sender: 'customer' or 'company'"""
        t = (text or "").lower()
        if customer_name:
            # check for greeting like "Hi <CustomerName>" or "Hello <CustomerName>"
            try:
                if f"hi {customer_name.lower()}" in t or f"hello {customer_name.lower()}" in t:
                    return 'company'
            except:
                pass
        bot_indicators = ['welcome to', 'automated customer service', 'sazgar automated', 'what would you like', 'select ', 'please wait', 'www.', 'http', 'visit', 'brochure', 'welcome', 'please visit', 'please wait while', 'welcome to saz']
        if any(k in t for k in bot_indicators):
            return 'company'
        # Long menu-like messages likely from the bot/company
        if len(t) > 50 and ('\n' in t or 'what would you like' in t):
            return 'company'
        return 'customer'

    @staticmethod
    def import_messages(messages_data, company_id='haval'):
        """Import messages from JSON data"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        imported_count = 0
        skipped_count = 0
        
        for msg in messages_data:
            # Check if message already exists
            cur.execute("""
                SELECT COUNT(*) FROM whatsapp_messages 
                WHERE customer_name = ? AND message = ? AND timestamp = ?
            """, (msg.get('customer_name'), msg.get('message'), msg.get('timestamp')))
            
            if cur.fetchone()[0] > 0:
                skipped_count += 1
                continue
            
            # Classify message type and sender
            message_type = WhatsAppMessage.classify_message(msg.get('message', ''))
            sender = WhatsAppMessage.classify_sender(msg.get('message', ''), msg.get('customer_name'))
            
            # Complaint classification: Reverted to none for WhatsApp (Heuristic only)
            complaint_category = 'none'

            cur.execute("""
                INSERT INTO whatsapp_messages 
                (customer_name, country_code, contact_number, message_type, message, timestamp, sender, company_id, complaint_category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                msg.get('customer_name'),
                msg.get('country_code'),
                msg.get('contact_number'),
                message_type,
                msg.get('message'),
                msg.get('timestamp'),
                sender,
                company_id,
                complaint_category
            ))
            imported_count += 1
        
        conn.commit()
        conn.close()
        
        return imported_count, skipped_count

    @staticmethod
    def create(customer_name, country_code, contact_number, message_type, message, timestamp, sender='customer', company_id='haval'):
        """Create a new WhatsApp message"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Complaint classification: Reverted to none for WhatsApp (Heuristic only)
            complaint_category = 'none'

            cur.execute("""
                INSERT INTO whatsapp_messages 
                (customer_name, country_code, contact_number, message_type, message, timestamp, sender, company_id, complaint_category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (customer_name, country_code, contact_number, message_type, message, timestamp, sender, company_id, complaint_category))
            
            message_id = cur.lastrowid
            conn.commit()
            conn.close()
            
            return WhatsAppMessage(
                id=message_id,
                customer_name=customer_name,
                country_code=country_code,
                contact_number=contact_number,
                message_type=message_type,
                message=message,
                timestamp=timestamp,
                sender=sender,
                company_id=company_id
            )
        except Exception as e:
            conn.close()
            raise e

    @staticmethod
    def get_conversations(company_id=None, limit=100):
        """Get conversations grouped by customer and date"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        where_clause = "WHERE company_id = ?" if company_id else ""
        params = [company_id] if company_id else []
        
        # Get unique conversations (customer + date)
        cur.execute(f"""
            SELECT 
                customer_name,
                DATE(timestamp) as conversation_date,
                COUNT(*) as message_count,
                MAX(timestamp) as last_message_time,
                GROUP_CONCAT(DISTINCT message_type) as message_types
            FROM whatsapp_messages
            {where_clause}
            GROUP BY customer_name, DATE(timestamp)
            ORDER BY MAX(timestamp) DESC
            LIMIT ?
        """, params + [limit])
        
        conversations = []
        for row in cur.fetchall():
            conversations.append({
                'customer_name': row[0],
                'conversation_date': row[1],
                'message_count': row[2],
                'last_message_time': row[3],
                'message_types': row[4].split(',') if row[4] else []
            })
        
        conn.close()
        return conversations

    @staticmethod
    def get_conversation_messages(customer_name, conversation_date, company_id=None):
        """Get all messages for a specific conversation (customer + date)"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        if company_id:
            cur.execute("""
                SELECT id, customer_name, country_code, contact_number, message_type, 
                       message, timestamp, imported_at, sender, company_id
                FROM whatsapp_messages 
                WHERE customer_name = ? AND DATE(timestamp) = ? AND company_id = ?
                ORDER BY timestamp ASC
            """, (customer_name, conversation_date, company_id))
        else:
            cur.execute("""
                SELECT id, customer_name, country_code, contact_number, message_type, 
                       message, timestamp, imported_at, sender, company_id
                FROM whatsapp_messages 
                WHERE customer_name = ? AND DATE(timestamp) = ?
                ORDER BY timestamp ASC
            """, (customer_name, conversation_date))
        
        rows = cur.fetchall()
        conn.close()
        
        messages = []
        for row in rows:
            message = WhatsAppMessage(
                id=row[0], customer_name=row[1], country_code=row[2],
                contact_number=row[3], message_type=row[4], message=row[5],
                timestamp=row[6], imported_at=row[7],
                sender=row[8],
                company_id=row[9] if len(row) > 9 else 'haval'
            )
            messages.append(message)
        
        return messages

    @staticmethod
    def get_by_content_and_timestamp(message_content, timestamp):
        """Check if a message with the same content and timestamp already exists"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, customer_name, country_code, contact_number, message_type, 
                   message, timestamp, imported_at, sender, company_id
            FROM whatsapp_messages 
            WHERE message = ? AND timestamp = ?
            LIMIT 1
        """, (message_content, timestamp))
        
        row = cur.fetchone()
        conn.close()
        
        if row:
            return WhatsAppMessage(
                id=row[0], customer_name=row[1], country_code=row[2],
                contact_number=row[3], message_type=row[4], message=row[5],
                timestamp=row[6], imported_at=row[7],
                sender=row[8],
                company_id=row[9] if len(row) > 9 else 'haval'
            )
        return None