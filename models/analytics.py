from datetime import datetime, timedelta
from typing import Dict, List, Optional

from models.database import get_db_connection


class Analytics:
    """Analytics model for handling various analytics operations"""
    
    @staticmethod
    def get_company_analytics(user_id: int, company_id: str, date_from: str = None, 
                          date_to: str = None) -> Dict:
        """Get comprehensive analytics for a company (company-wide data)"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build date filter
        date_filter = ""
        date_params = []
        if date_from:
            date_filter += " AND created_at >= ?"
            date_params.append(date_from)
        if date_to:
            date_filter += " AND created_at <= ?"
            date_params.append(date_to + " 23:59:59")
        
        analytics = {}
        
        # Basic post statistics - Company-wide for dashboard
        cur.execute(f"SELECT COUNT(*) FROM posts WHERE company_id = ?{date_filter}", 
                   [company_id] + date_params)
        analytics['total_posts'] = cur.fetchone()[0]
        
        cur.execute(f"SELECT COUNT(*) FROM search_results WHERE company_id = ?{date_filter}", 
                   [company_id] + date_params)
        analytics['search_posts'] = cur.fetchone()[0]
        
        cur.execute(f"SELECT COUNT(DISTINCT topic_title) FROM posts WHERE company_id = ?{date_filter}", 
                   [company_id] + date_params)
        analytics['unique_topics'] = cur.fetchone()[0]
        
        cur.execute(f"SELECT COUNT(DISTINCT author) FROM posts WHERE company_id = ?{date_filter}", 
                   [company_id] + date_params)
        analytics['unique_authors'] = cur.fetchone()[0]
        
        # Chat analytics
        chat_date_filter = ""
        chat_date_params = []
        if date_from:
            chat_date_filter += " AND timestamp >= ?"
            chat_date_params.append(date_from)
        if date_to:
            chat_date_filter += " AND timestamp <= ?"
            chat_date_params.append(date_to + " 23:59:59")
        
        cur.execute(f"""
            SELECT mode, COUNT(*) as count 
            FROM chat_history ch
            JOIN users u ON ch.user_id = u.id
            WHERE u.company_id = ?{chat_date_filter}
            GROUP BY mode 
            ORDER BY count DESC
        """, [company_id] + chat_date_params)
        analytics['chatbot_usage'] = {row[0]: row[1] for row in cur.fetchall()}
        
        # Popular queries
        cur.execute(f"""
            SELECT query, COUNT(*) as count 
            FROM chat_history ch
            JOIN users u ON ch.user_id = u.id
            WHERE u.company_id = ? AND LENGTH(query) > 10{chat_date_filter}
            GROUP BY LOWER(query) 
            ORDER BY count DESC 
            LIMIT 10
        """, [company_id] + chat_date_params)
        analytics['popular_queries'] = [{"query": row[0], "count": row[1]} for row in cur.fetchall()]
        
        conn.close()
        return analytics
    
    @staticmethod
    def get_sentiment_analysis(company_id: str, date_from: str = None, 
                              date_to: str = None) -> Dict:
        """Analyze sentiment in posts and WhatsApp messages. Filters to exclude bot messages."""
        from models.message_filter import MessageFilter
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build date filter
        date_filter = ""
        date_params = []
        if date_from:
            date_filter += " AND created_at >= ?"
            date_params.append(date_from)
        if date_to:
            date_filter += " AND created_at <= ?"
            date_params.append(date_to + " 23:59:59")
        
        positive_keywords = ['good', 'great', 'excellent', 'amazing', 'love', 'best', 'perfect', 'recommend', 'happy', 'satisfied']
        negative_keywords = ['bad', 'poor', 'worst', 'hate', 'terrible', 'awful', 'disappointed', 'problem', 'issue', 'complaint']
        
        # Analyze posts sentiment - filter out bot messages
        cur.execute(f"SELECT cooked_text FROM posts WHERE company_id = ?{date_filter}", 
                   [company_id] + date_params)
        posts_text = []
        for row in cur.fetchall():
            text = row[0]
            # Skip bot messages
            if not MessageFilter.is_bot_message(text):
                posts_text.append(text.lower())
        
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for text in posts_text:
            pos_score = sum(1 for word in positive_keywords if word in text)
            neg_score = sum(1 for word in negative_keywords if word in text)
            
            if pos_score > neg_score:
                positive_count += 1
            elif neg_score > pos_score:
                negative_count += 1
            else:
                neutral_count += 1
        
        return {
            'positive': positive_count,
            'negative': negative_count,
            'neutral': neutral_count,
            'total_analyzed': len(posts_text)
        }
    
    @staticmethod
    def get_complaint_analysis(company_id: str, date_from: str = None, 
                              date_to: str = None) -> Dict:
        """Analyze complaints from posts and WhatsApp. Filters to keep only meaningful complaints."""
        from models.message_filter import MessageFilter
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build date filter (inclusive of created_at OR scraped_at)
        date_filter = ""
        date_params = []
        if date_from:
            # Check both creation date and ingestion date to catch newly scraped older posts
            date_filter += " AND (created_at >= ? OR date(scraped_at) >= ?)"
            date_params.extend([date_from, date_from])
        if date_to:
            date_filter += " AND created_at <= ?"
            date_params.append(date_to + " 23:59:59")
        
        complaints = {}
        
        # PakWheels complaints - Strictly show ONLY car complaints
        cur.execute(f"""
            SELECT cooked_text, author, created_at, topic_url, post_number, complaint_category, scraped_at FROM posts 
            WHERE company_id = ?{date_filter} AND complaint_category = 'car_complaint'
            ORDER BY created_at DESC
        """, [company_id] + date_params)
        
        # Filter to keep only meaningful complaints (not bot messages) + include additional fields
        pakwheels_complaints = []
        for row in cur.fetchall():
            complaint_text = row[0]
            # Skip if it's a bot message
            if MessageFilter.is_bot_message(complaint_text):
                continue
            # Keep if it's meaningful
            if MessageFilter.is_meaningful_message(complaint_text):
                pakwheels_complaints.append({
                    "text": complaint_text, 
                    "author": row[1], 
                    "date": row[2], 
                    "url": row[3], 
                    "post_number": row[4],
                    "category": row[5] if len(row) > 5 else 'none',
                    "scraped_at": row[6] if len(row) > 6 else None
                })
        
        complaints['pakwheels'] = pakwheels_complaints
        
        # WhatsApp complaints - Get ONLY car complaints (LLM classified)
        whatsapp_date_filter = date_filter.replace('created_at', 'timestamp') if date_filter else ""
        try:
            # Check if whatsapp_messages table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='whatsapp_messages'")
            table_exists = cur.fetchone() is not None
            
            if table_exists:
                try:
                    # Get car complaints only - matches PakWheels pattern
                    cur.execute(f"""
                        SELECT customer_name, message, timestamp, contact_number, country_code, complaint_category
                        FROM whatsapp_messages 
                        WHERE company_id = ? AND complaint_category = 'car_complaint'{whatsapp_date_filter}
                        ORDER BY timestamp DESC
                    """, [company_id] + date_params)
                    
                    # Filter to keep only meaningful complaints (not bot messages) + include additional fields
                    whatsapp_complaints = []
                    for row in cur.fetchall():
                        complaint_msg = row[1]
                        # Skip if it's a bot message
                        if MessageFilter.is_bot_message(complaint_msg):
                            continue
                        # Keep if it's meaningful
                        if MessageFilter.is_meaningful_message(complaint_msg):
                            whatsapp_complaints.append({
                                "customer": row[0], 
                                "message": complaint_msg, 
                                "date": row[2],
                                "contact_number": row[3] if row[3] else "N/A",
                                "country_code": row[4] if row[4] else "92",
                                "category": row[5] if len(row) > 5 else 'none'
                            })
                    
                    complaints['whatsapp'] = whatsapp_complaints
                except Exception as e:
                    # If query fails, try without contact info (backward compatibility)
                    print(f"Error fetching WhatsApp complaints with contact info: {e}")
                    cur.execute(f"""
                        SELECT customer_name, message, timestamp
                        FROM whatsapp_messages 
                        WHERE company_id = ? AND complaint_category = 'car_complaint'{whatsapp_date_filter}
                        ORDER BY timestamp DESC
                    """, [company_id] + date_params)
                    
                    # Filter to keep only meaningful complaints
                    whatsapp_complaints = []
                    for row in cur.fetchall():
                        complaint_msg = row[1]
                        # Skip if it's a bot message
                        if MessageFilter.is_bot_message(complaint_msg):
                            continue
                        # Keep if it's meaningful
                        if MessageFilter.is_meaningful_message(complaint_msg):
                            whatsapp_complaints.append({
                                "customer": row[0], 
                                "message": complaint_msg, 
                                "date": row[2],
                                "contact_number": "N/A",
                                "country_code": "92"
                            })
                    
                    complaints['whatsapp'] = whatsapp_complaints
            else:
                complaints['whatsapp'] = []
        except Exception as e:
            print(f"Error fetching WhatsApp complaints: {e}")
            complaints['whatsapp'] = []
        
        conn.close()
        return complaints

    @staticmethod
    def get_reddit_complaint_analysis(company_id: str, date_from: str = None, 
                                     date_to: str = None) -> Dict:
        """Analyze complaints from Reddit posts"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build date filter (inclusive of created_at OR scraped_at)
        date_filter = ""
        date_params = []
        if date_from:
            # Check both creation date and ingestion date to catch newly scraped older posts
            date_filter += " AND (created_at >= ? OR date(scraped_at) >= ?)"
            date_params.extend([date_from, date_from])
        if date_to:
            date_filter += " AND created_at <= ?"
            date_params.append(date_to + " 23:59:59")
        
        complaints = {}
        
        # Reddit complaints - Strictly show ONLY car complaints
        cur.execute(f"""
            SELECT cooked_text, author, created_at, topic_url, post_number, complaint_category, scraped_at FROM posts 
            WHERE company_id = ? AND category LIKE '%Reddit%'{date_filter} AND complaint_category = 'car_complaint'
            ORDER BY created_at DESC
        """, [company_id] + date_params)
        
        complaints['reddit'] = [
            {
                "text": row[0], 
                "author": row[1], 
                "date": row[2], 
                "url": row[3], 
                "post_number": row[4],
                "category": row[5] if len(row) > 5 else 'none',
                "scraped_at": row[6] if len(row) > 6 else None
            } 
            for row in cur.fetchall()
        ]
        
        conn.close()
        return complaints
    
    @staticmethod
    def get_whatsapp_analytics(company_id: str, date_from: str = None, 
                              date_to: str = None) -> Dict:
        """Get WhatsApp specific analytics"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build date filter for WhatsApp
        date_filter = ""
        date_params = []
        if date_from:
            date_filter += " AND timestamp >= ?"
            date_params.append(date_from)
        if date_to:
            date_filter += " AND timestamp <= ?"
            date_params.append(date_to + " 23:59:59")
        
        analytics = {}
        
        try:
            # Check if whatsapp_messages table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='whatsapp_messages'")
            table_exists = cur.fetchone() is not None
            
            if not table_exists:
                # Create table if it doesn't exist
                from models.whatsapp import WhatsAppMessage
                WhatsAppMessage.create_table()
                
                # Try to import data from JSON file if available
                try:
                    import json
                    import os
                    json_file_path = 'data/whatsapp_kia_wati.json'
                    if os.path.exists(json_file_path):
                        with open(json_file_path, 'r', encoding='utf-8') as f:
                            whatsapp_data = json.load(f)
                        
                        # Process and import the data
                        processed_messages = []
                        for item in whatsapp_data:
                            if item.get('eventType') == 'message' and item.get('text'):
                                # Extract customer info
                                contact_number = item.get('contactNumber', 'Unknown')
                                customer_name = item.get('operatorName', f'Customer_{contact_number}')
                                if item.get('owner') is False:  # Customer message
                                    customer_name = f'Customer_{contact_number}'
                                
                                # Classify message
                                message_text = item.get('text', '')
                                message_type = WhatsAppMessage.classify_message(message_text)
                                sender = 'company' if item.get('owner') is True else 'customer'
                                
                                # Convert timestamp
                                timestamp_unix = item.get('timestamp')
                                if timestamp_unix:
                                    from datetime import datetime
                                    timestamp = datetime.fromtimestamp(int(timestamp_unix)).strftime('%Y-%m-%d %H:%M:%S')
                                else:
                                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                
                                processed_messages.append({
                                    'customer_name': customer_name,
                                    'country_code': 92,  # Pakistan
                                    'contact_number': contact_number,
                                    'message': message_text,
                                    'timestamp': timestamp,
                                    'message_type': message_type,
                                    'sender': sender
                                })
                        
                        # Import the processed messages
                        if processed_messages:
                            WhatsAppMessage.import_messages(processed_messages, company_id)
                            print(f"Imported {len(processed_messages)} WhatsApp messages")
                
                except Exception as e:
                    print(f"Error importing WhatsApp data: {e}")
            
            # Now get the analytics
            # Message type distribution
            cur.execute(f"""
                SELECT message_type, COUNT(*) as count 
                FROM whatsapp_messages 
                WHERE company_id = ?{date_filter}
                GROUP BY message_type 
                ORDER BY count DESC
            """, [company_id] + date_params)
            message_types_result = cur.fetchall()
            analytics['message_types'] = {row[0]: row[1] for row in message_types_result}
            
            # Total messages
            cur.execute(f"SELECT COUNT(*) FROM whatsapp_messages WHERE company_id = ?{date_filter}", 
                       [company_id] + date_params)
            analytics['total_messages'] = cur.fetchone()[0]
            
            # Common queries
            cur.execute(f"""
                SELECT message, COUNT(*) as count 
                FROM whatsapp_messages 
                WHERE company_id = ? AND message_type = 'query' AND sender = 'customer' AND LENGTH(message) > 10{date_filter}
                GROUP BY LOWER(message) 
                ORDER BY count DESC 
                LIMIT 10
            """, [company_id] + date_params)
            analytics['common_queries'] = [{"query": row[0], "count": row[1]} for row in cur.fetchall()]
            
            # Daily activity
            activity_filter = date_filter if date_filter else " AND timestamp >= datetime('now', '-7 days')"
            cur.execute(f"""
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM whatsapp_messages 
                WHERE company_id = ?{activity_filter}
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """, [company_id] + (date_params if date_filter else []))
            analytics['daily_activity'] = {row[0]: row[1] for row in cur.fetchall()}
            
            # Unique customers
            cur.execute(f"""
                SELECT COUNT(DISTINCT customer_name) 
                FROM whatsapp_messages 
                WHERE company_id = ?{date_filter}
            """, [company_id] + date_params)
            analytics['unique_customers'] = cur.fetchone()[0]
            
        except Exception as e:
            # WhatsApp table might not exist or have issues
            analytics = {
                'message_types': {},
                'total_messages': 0,
                'daily_activity': {},
                'common_queries': []
            }
        
        conn.close()
        return analytics
    
    @staticmethod
    def get_reddit_analytics(company_id: str, date_from: str = None, 
                          date_to: str = None) -> Dict:
        """Get Reddit-specific analytics"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build date filter
        date_filter = ""
        date_params = []
        if date_from:
            date_filter += " AND created_at >= ?"
            date_params.append(date_from)
        if date_to:
            date_filter += " AND created_at <= ?"
            date_params.append(date_to + " 23:59:59")
        
        analytics = {}
        
        # Reddit posts statistics - filter by category containing 'Reddit'
        cur.execute(f"SELECT COUNT(*) FROM posts WHERE company_id = ? AND category LIKE '%Reddit%'{date_filter}", 
                   [company_id] + date_params)
        analytics['total_posts'] = cur.fetchone()[0]
        
        cur.execute(f"SELECT COUNT(DISTINCT author) FROM posts WHERE company_id = ? AND category LIKE '%Reddit%'{date_filter}", 
                   [company_id] + date_params)
        analytics['unique_authors'] = cur.fetchone()[0]
        
        cur.execute(f"SELECT COUNT(DISTINCT topic_title) FROM posts WHERE company_id = ? AND category LIKE '%Reddit%'{date_filter}", 
                   [company_id] + date_params)
        analytics['unique_topics'] = cur.fetchone()[0]
        
        conn.close()
        return analytics
    
    @staticmethod
    def get_reddit_sentiment_analysis(company_id: str, date_from: str = None, 
                                     date_to: str = None) -> Dict:
        """Analyze sentiment in Reddit posts. Filters to exclude bot messages."""
        from models.message_filter import MessageFilter
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build date filter
        date_filter = ""
        date_params = []
        if date_from:
            date_filter += " AND created_at >= ?"
            date_params.append(date_from)
        if date_to:
            date_filter += " AND created_at <= ?"
            date_params.append(date_to + " 23:59:59")
        
        positive_keywords = ['good', 'great', 'excellent', 'amazing', 'love', 'best', 'perfect', 'recommend', 'happy', 'satisfied']
        negative_keywords = ['bad', 'poor', 'worst', 'hate', 'terrible', 'awful', 'disappointed', 'problem', 'issue', 'complaint']
        
        # Analyze Reddit posts sentiment - filter out bot messages
        cur.execute(f"SELECT cooked_text FROM posts WHERE company_id = ? AND category LIKE '%Reddit%'{date_filter}", 
                   [company_id] + date_params)
        posts_text = []
        for row in cur.fetchall():
            text = row[0]
            # Skip bot messages
            if not MessageFilter.is_bot_message(text):
                posts_text.append(text.lower())
        
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for text in posts_text:
            pos_score = sum(1 for word in positive_keywords if word in text)
            neg_score = sum(1 for word in negative_keywords if word in text)
            
            if pos_score > neg_score:
                positive_count += 1
            elif neg_score > pos_score:
                negative_count += 1
            else:
                neutral_count += 1
        
        conn.close()
        return {
            'positive': positive_count,
            'negative': negative_count,
            'neutral': neutral_count,
            'total_analyzed': len(posts_text)
        }
    
    @staticmethod
    def generate_report(company_id: str) -> Dict:
        """Generate comprehensive analytics report"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "report_type": "comprehensive_analytics",
            "company_id": company_id,
            "summary": {}
        }
        
        if company_id:
            # Company-specific report
            cur.execute("SELECT COUNT(*) FROM posts WHERE company_id = ?", (company_id,))
            report["summary"]["total_posts"] = cur.fetchone()[0]
            
            try:
                cur.execute("SELECT COUNT(*) FROM whatsapp_messages WHERE company_id = ?", (company_id,))
                report["summary"]["total_whatsapp_messages"] = cur.fetchone()[0]
            except:
                report["summary"]["total_whatsapp_messages"] = 0
            
            cur.execute("SELECT COUNT(*) FROM chat_history WHERE user_id IN (SELECT id FROM users WHERE company_id = ?)", (company_id,))
            report["summary"]["total_chatbot_queries"] = cur.fetchone()[0]
            
        else:
            # Global report
            cur.execute("SELECT COUNT(*) FROM posts")
            report["summary"]["total_posts"] = cur.fetchone()[0]
            
            try:
                cur.execute("SELECT COUNT(*) FROM whatsapp_messages")
                report["summary"]["total_whatsapp_messages"] = cur.fetchone()[0]
            except:
                report["summary"]["total_whatsapp_messages"] = 0
            
            cur.execute("SELECT COUNT(*) FROM chat_history")
            report["summary"]["total_chatbot_queries"] = cur.fetchone()[0]
        
        # Complaint analysis
        if company_id:
            cur.execute("""
                SELECT COUNT(*) FROM posts 
                WHERE company_id = ? AND (
                    LOWER(cooked_text) LIKE '%problem%' OR 
                    LOWER(cooked_text) LIKE '%issue%' OR 
                    LOWER(cooked_text) LIKE '%complaint%'
                )
            """, (company_id,))
            report["summary"]["pakwheels_complaints"] = cur.fetchone()[0]
            
            try:
                cur.execute("SELECT COUNT(*) FROM whatsapp_messages WHERE company_id = ? AND message_type = 'complaint'", (company_id,))
                report["summary"]["whatsapp_complaints"] = cur.fetchone()[0]
            except:
                report["summary"]["whatsapp_complaints"] = 0
        else:
            cur.execute("""
                SELECT COUNT(*) FROM posts 
                WHERE (
                    LOWER(cooked_text) LIKE '%problem%' OR 
                    LOWER(cooked_text) LIKE '%issue%' OR 
                    LOWER(cooked_text) LIKE '%complaint%'
                )
            """)
            report["summary"]["pakwheels_complaints"] = cur.fetchone()[0]
            
            try:
                cur.execute("SELECT COUNT(*) FROM whatsapp_messages WHERE message_type = 'complaint'")
                report["summary"]["whatsapp_complaints"] = cur.fetchone()[0]
            except:
                report["summary"]["whatsapp_complaints"] = 0
        
        # Most active periods
        cur.execute("""
            SELECT DATE(timestamp) as date, COUNT(*) as count
            FROM chat_history 
            GROUP BY DATE(timestamp)
            ORDER BY count DESC
            LIMIT 5
        """)
        report["most_active_days"] = [{"date": row[0], "queries": row[1]} for row in cur.fetchall()]
        
        # Additional insights
        if company_id:
            cur.execute("SELECT COUNT(DISTINCT author) FROM posts WHERE company_id = ?", (company_id,))
            report["summary"]["unique_authors"] = cur.fetchone()[0]
            
            try:
                cur.execute("SELECT COUNT(DISTINCT customer_name) FROM whatsapp_messages WHERE company_id = ?", (company_id,))
                report["summary"]["unique_whatsapp_customers"] = cur.fetchone()[0]
            except:
                report["summary"]["unique_whatsapp_customers"] = 0
        else:
            cur.execute("SELECT COUNT(DISTINCT author) FROM posts")
            report["summary"]["unique_authors"] = cur.fetchone()[0]
            
            try:
                cur.execute("SELECT COUNT(DISTINCT customer_name) FROM whatsapp_messages")
                report["summary"]["unique_whatsapp_customers"] = cur.fetchone()[0]
            except:
                report["summary"]["unique_whatsapp_customers"] = 0
        
        conn.close()
        return report
    
    @staticmethod
    def get_daily_stats(company_id: str = None, days: int = 30) -> List[Dict]:
        """Get daily statistics for the last N days"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Generate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        stats = []
        
        for i in range(days):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            
            day_stats = {
                'date': date_str,
                'posts': 0,
                'whatsapp_messages': 0,
                'chat_queries': 0
            }
            
            # Posts count
            if company_id:
                cur.execute("SELECT COUNT(*) FROM posts WHERE company_id = ? AND DATE(created_at) = ?", 
                           (company_id, date_str))
            else:
                cur.execute("SELECT COUNT(*) FROM posts WHERE DATE(created_at) = ?", (date_str,))
            day_stats['posts'] = cur.fetchone()[0]
            
            # WhatsApp messages count
            try:
                if company_id:
                    cur.execute("SELECT COUNT(*) FROM whatsapp_messages WHERE company_id = ? AND DATE(timestamp) = ?", 
                               (company_id, date_str))
                else:
                    cur.execute("SELECT COUNT(*) FROM whatsapp_messages WHERE DATE(timestamp) = ?", (date_str,))
                day_stats['whatsapp_messages'] = cur.fetchone()[0]
            except:
                day_stats['whatsapp_messages'] = 0
            
            # Chat queries count
            if company_id:
                cur.execute("""
                    SELECT COUNT(*) FROM chat_history 
                    WHERE user_id IN (SELECT id FROM users WHERE company_id = ?) 
                    AND DATE(timestamp) = ?
                """, (company_id, date_str))
            else:
                cur.execute("SELECT COUNT(*) FROM chat_history WHERE DATE(timestamp) = ?", (date_str,))
            day_stats['chat_queries'] = cur.fetchone()[0]
            
            stats.append(day_stats)
        
        conn.close()
        return stats
    
    @staticmethod
    def get_most_asked_queries(company_id: str, limit: int = 10) -> List[Dict]:
        """Get the most frequently discussed topics from posts (PakWheels, Reddit, etc.)
        Filters to show actual topics/questions, not platform names. Removes bot messages."""
        from models.message_filter import MessageFilter
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            queries = []
            
            # Keywords to filter out (platform names, generic terms)
            exclude_keywords = [
                'pakwheels', 'reddit', 'facebook', 'whatsapp', 'instagram', 'twitter',
                'discussion', 'thread', 'post', 'comment', 'reply', 'message',
                'haval', 'kia', 'toyota', 'honda', 'suzuki', 'mg', 'hyundai', 'changan',
                'h6', 'sportage', 'picanto', 'corolla', 'civic', 'city', 'accord'
            ]
            
            # Get most common topics from posts (PakWheels, Reddit, etc.) - only from posts
            if company_id:
                cur.execute("""
                    SELECT topic_title, COUNT(*) as count 
                    FROM posts 
                    WHERE company_id = ? AND LENGTH(TRIM(topic_title)) > 10
                    GROUP BY LOWER(TRIM(topic_title))
                    ORDER BY count DESC 
                    LIMIT ?
                """, (company_id, limit * 3))  # Get more to filter
            else:
                cur.execute("""
                    SELECT topic_title, COUNT(*) as count 
                    FROM posts 
                    WHERE LENGTH(TRIM(topic_title)) > 10
                    GROUP BY LOWER(TRIM(topic_title))
                    ORDER BY count DESC 
                    LIMIT ?
                """, (limit * 3,))
            
            # Filter out platform names and generic terms, and bot messages
            for row in cur.fetchall():
                topic = row[0]
                topic_lower = topic.lower()
                
                # Skip if contains platform/car names
                if any(keyword in topic_lower for keyword in exclude_keywords):
                    continue
                
                # Skip if it's a bot message
                if MessageFilter.is_bot_message(topic):
                    continue
                
                # Keep if it's meaningful
                if MessageFilter.is_meaningful_message(topic):
                    queries.append({"query": topic, "count": row[1]})
                
                if len(queries) >= limit:
                    break
            
            conn.close()
            return queries[:limit]
            
        except Exception as e:
            print(f"Error getting most asked queries from posts: {e}")
            conn.close()
            return []
    
    @staticmethod
    def get_query_topics_distribution(company_id: str) -> Dict:
        """Get distribution of query topics by mode"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            if company_id:
                cur.execute("""
                    SELECT mode, COUNT(*) as count 
                    FROM chat_history ch
                    JOIN users u ON ch.user_id = u.id
                    WHERE u.company_id = ?
                    GROUP BY mode 
                    ORDER BY count DESC
                """, (company_id,))
            else:
                cur.execute("""
                    SELECT mode, COUNT(*) as count 
                    FROM chat_history 
                    GROUP BY mode 
                    ORDER BY count DESC
                """)
            
            distribution = {row[0]: row[1] for row in cur.fetchall()}
            conn.close()
            return distribution
        except Exception as e:
            conn.close()
            return {}