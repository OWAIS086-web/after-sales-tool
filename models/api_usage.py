"""
API Usage Tracking Model
Tracks LLM and embedding token usage for billing and analytics
"""

import sqlite3
from datetime import datetime
from models.database import get_db_connection
from utils.logger import ai_logger


class APIUsage:
    """Model for tracking API usage (tokens, costs)"""
    
    @staticmethod
    def log_usage(user_id, api_type, model_name, operation, 
                  input_tokens=0, output_tokens=0, cost=0.0, company_id='haval'):
        """
        Log API usage to database
        
        Args:
            user_id: User ID (can be None for system operations)
            api_type: Type of API ('llm_grok', 'llm_gemini', 'embedding')
            model_name: Model name (e.g., 'grok-3-fast', 'gemini-2.5-flash')
            operation: Operation description (e.g., 'Chat query', 'Embedding vectors')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost: Estimated cost in USD
            company_id: Company identifier
        """
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            total_tokens = input_tokens + output_tokens
            
            cur.execute("""
                INSERT INTO api_usage 
                (user_id, company_id, api_type, model_name, operation, 
                 input_tokens, output_tokens, total_tokens, cost, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                company_id,
                api_type,
                model_name,
                operation,
                input_tokens,
                output_tokens,
                total_tokens,
                cost,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            ai_logger.info(f"API usage logged: {api_type} - {model_name} - {total_tokens} tokens")
            
        except Exception as e:
            ai_logger.error(f"Failed to log API usage: {str(e)}")
    
    @staticmethod
    def get_usage_stats(user_id=None, company_id='haval', api_type=None, days=30):
        """
        Get API usage statistics
        
        Args:
            user_id: Filter by user (None for all users)
            company_id: Filter by company
            api_type: Filter by API type
            days: Number of days to look back
        
        Returns:
            Dictionary with usage statistics
        """
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            query = """
                SELECT 
                    api_type,
                    model_name,
                    COUNT(*) as request_count,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost,
                    AVG(total_tokens) as avg_tokens_per_request
                FROM api_usage
                WHERE company_id = ?
                AND datetime(timestamp) >= datetime('now', '-' || ? || ' days')
            """
            
            params = [company_id, days]
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            if api_type:
                query += " AND api_type = ?"
                params.append(api_type)
            
            query += " GROUP BY api_type, model_name ORDER BY total_tokens DESC"
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            conn.close()
            
            stats = []
            for row in rows:
                stats.append({
                    'api_type': row[0],
                    'model_name': row[1],
                    'request_count': row[2],
                    'total_input_tokens': row[3] or 0,
                    'total_output_tokens': row[4] or 0,
                    'total_tokens': row[5] or 0,
                    'total_cost': row[6] or 0.0,
                    'avg_tokens_per_request': row[7] or 0
                })
            
            return stats
            
        except Exception as e:
            ai_logger.error(f"Failed to get usage stats: {str(e)}")
            return []
    
    @staticmethod
    def get_daily_usage(company_id='haval', days=30):
        """
        Get daily API usage breakdown
        
        Args:
            company_id: Filter by company
            days: Number of days to look back
        
        Returns:
            List of daily usage records
        """
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT 
                    DATE(timestamp) as date,
                    api_type,
                    COUNT(*) as request_count,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost
                FROM api_usage
                WHERE company_id = ?
                AND datetime(timestamp) >= datetime('now', '-' || ? || ' days')
                GROUP BY DATE(timestamp), api_type
                ORDER BY date DESC, api_type
            """, (company_id, days))
            
            rows = cur.fetchall()
            conn.close()
            
            daily_usage = []
            for row in rows:
                daily_usage.append({
                    'date': row[0],
                    'api_type': row[1],
                    'request_count': row[2],
                    'total_tokens': row[3] or 0,
                    'total_cost': row[4] or 0.0
                })
            
            return daily_usage
            
        except Exception as e:
            ai_logger.error(f"Failed to get daily usage: {str(e)}")
            return []
    
    @staticmethod
    def get_user_usage(user_id, company_id='haval', days=30):
        """
        Get usage for a specific user
        
        Args:
            user_id: User ID
            company_id: Company ID
            days: Number of days to look back
        
        Returns:
            Dictionary with user's usage statistics
        """
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT 
                    COUNT(*) as request_count,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost
                FROM api_usage
                WHERE user_id = ?
                AND company_id = ?
                AND datetime(timestamp) >= datetime('now', '-' || ? || ' days')
            """, (user_id, company_id, days))
            
            row = cur.fetchone()
            conn.close()
            
            if row:
                return {
                    'request_count': row[0] or 0,
                    'total_input_tokens': row[1] or 0,
                    'total_output_tokens': row[2] or 0,
                    'total_tokens': row[3] or 0,
                    'total_cost': row[4] or 0.0
                }
            
            return {
                'request_count': 0,
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_tokens': 0,
                'total_cost': 0.0
            }
            
        except Exception as e:
            ai_logger.error(f"Failed to get user usage: {str(e)}")
            return {}

    
    @staticmethod
    def get_detailed_usage(company_id='haval', api_type=None, days=30):
        """
        Get detailed usage data for each individual request
        
        Args:
            company_id: Filter by company
            api_type: Filter by API type
            days: Number of days to look back
        
        Returns:
            List of detailed usage records
        """
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            query = """
                SELECT 
                    id,
                    user_id,
                    company_id,
                    api_type,
                    model_name,
                    operation,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    cost,
                    timestamp
                FROM api_usage
                WHERE company_id = ?
                AND datetime(timestamp) >= datetime('now', '-' || ? || ' days')
            """
            
            params = [company_id, days]
            
            if api_type:
                query += " AND api_type = ?"
                params.append(api_type)
            
            query += " ORDER BY timestamp DESC"
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            conn.close()
            
            # Get user mapping for display
            from models import User
            user_map = {}
            
            detailed_usage = []
            for row in rows:
                user_id = row[1]
                
                # Get username if available
                if user_id and user_id not in user_map:
                    try:
                        user = User.get(user_id)
                        user_map[user_id] = user.username if user else 'Unknown'
                    except:
                        user_map[user_id] = 'Unknown'
                
                username = user_map.get(user_id, 'System') if user_id else 'System'
                
                detailed_usage.append({
                    'id': row[0],
                    'user_id': user_id,
                    'user': username,
                    'company_id': row[2],
                    'api_type': row[3],
                    'model_name': row[4],
                    'operation': row[5],
                    'input_tokens': row[6] or 0,
                    'output_tokens': row[7] or 0,
                    'total_tokens': row[8] or 0,
                    'cost': row[9] or 0.0,
                    'timestamp': row[10]
                })
            
            return detailed_usage
            
        except Exception as e:
            ai_logger.error(f"Failed to get detailed usage: {str(e)}")
            return []
