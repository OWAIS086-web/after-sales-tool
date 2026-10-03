"""
API Usage Analytics Controller
Provides endpoints for viewing API usage statistics
"""

from flask import jsonify, request
from flask_login import login_required, current_user
from models.api_usage import APIUsage
from utils.logger import ai_logger


@login_required
def get_usage_stats():
    """Get API usage statistics for current user"""
    try:
        days = request.args.get('days', 30, type=int)
        api_type = request.args.get('api_type', None)
        exclude_chatbot = request.args.get('exclude_chatbot', 'false').lower() == 'true'
        exclude_embedding = request.args.get('exclude_embedding', 'false').lower() == 'true'
        
        stats = APIUsage.get_usage_stats(
            user_id=current_user.id,
            company_id=current_user.company_id,
            api_type=api_type,
            days=days
        )
        
        # Filter out chatbot if requested
        if exclude_chatbot and 'by_api_type' in stats:
            stats['by_api_type'] = {k: v for k, v in stats['by_api_type'].items() if k != 'chatbot'}
        
        # Filter out embedding if requested
        if exclude_embedding and 'by_api_type' in stats:
            stats['by_api_type'] = {k: v for k, v in stats['by_api_type'].items() if k != 'embedding'}
        
        return jsonify({
            'success': True,
            'data': stats,
            'period_days': days,
            'filters': {
                'exclude_chatbot': exclude_chatbot,
                'exclude_embedding': exclude_embedding
            }
        })
        
    except Exception as e:
        ai_logger.error(f"Failed to get usage stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve usage statistics'
        }), 500


@login_required
def get_daily_usage():
    """Get daily API usage breakdown"""
    try:
        days = request.args.get('days', 30, type=int)
        exclude_chatbot = request.args.get('exclude_chatbot', 'false').lower() == 'true'
        exclude_embedding = request.args.get('exclude_embedding', 'false').lower() == 'true'
        
        daily_usage = APIUsage.get_daily_usage(
            company_id=current_user.company_id,
            days=days
        )
        
        # Filter out chatbot if requested
        if exclude_chatbot:
            daily_usage = [{k: v for k, v in day.items() if k != 'chatbot'} for day in daily_usage]
        
        # Filter out embedding if requested
        if exclude_embedding:
            daily_usage = [{k: v for k, v in day.items() if k != 'embedding'} for day in daily_usage]
        
        return jsonify({
            'success': True,
            'data': daily_usage,
            'period_days': days,
            'filters': {
                'exclude_chatbot': exclude_chatbot,
                'exclude_embedding': exclude_embedding
            }
        })
        
    except Exception as e:
        ai_logger.error(f"Failed to get daily usage: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve daily usage'
        }), 500


@login_required
def get_user_usage():
    """Get usage statistics for current user"""
    try:
        days = request.args.get('days', 30, type=int)
        exclude_chatbot = request.args.get('exclude_chatbot', 'false').lower() == 'true'
        exclude_embedding = request.args.get('exclude_embedding', 'false').lower() == 'true'
        
        usage = APIUsage.get_user_usage(
            user_id=current_user.id,
            company_id=current_user.company_id,
            days=days
        )
        
        # Filter out chatbot if requested
        if exclude_chatbot and 'by_api_type' in usage:
            usage['by_api_type'] = {k: v for k, v in usage['by_api_type'].items() if k != 'chatbot'}
        
        # Filter out embedding if requested
        if exclude_embedding and 'by_api_type' in usage:
            usage['by_api_type'] = {k: v for k, v in usage['by_api_type'].items() if k != 'embedding'}
        
        return jsonify({
            'success': True,
            'data': usage,
            'period_days': days,
            'filters': {
                'exclude_chatbot': exclude_chatbot,
                'exclude_embedding': exclude_embedding
            }
        })
        
    except Exception as e:
        ai_logger.error(f"Failed to get user usage: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve user usage'
        }), 500


@login_required
def get_company_usage():
    """Get usage statistics for entire company (admin only)"""
    try:
        # Check if user is admin
        from scheduler.decorators import is_admin_user
        if not is_admin_user(current_user):
            return jsonify({
                'success': False,
                'error': 'Admin access required'
            }), 403
        
        days = request.args.get('days', 30, type=int)
        api_type = request.args.get('api_type', None)
        exclude_chatbot = request.args.get('exclude_chatbot', 'false').lower() == 'true'
        exclude_embedding = request.args.get('exclude_embedding', 'false').lower() == 'true'
        
        stats = APIUsage.get_usage_stats(
            user_id=None,
            company_id=current_user.company_id,
            api_type=api_type,
            days=days
        )
        
        # Filter out chatbot if requested
        if exclude_chatbot and 'by_api_type' in stats:
            stats['by_api_type'] = {k: v for k, v in stats['by_api_type'].items() if k != 'chatbot'}
        
        # Filter out embedding if requested
        if exclude_embedding and 'by_api_type' in stats:
            stats['by_api_type'] = {k: v for k, v in stats['by_api_type'].items() if k != 'embedding'}
        
        return jsonify({
            'success': True,
            'data': stats,
            'period_days': days,
            'company_id': current_user.company_id,
            'filters': {
                'exclude_chatbot': exclude_chatbot,
                'exclude_embedding': exclude_embedding
            }
        })
        
    except Exception as e:
        ai_logger.error(f"Failed to get company usage: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve company usage'
        }), 500


@login_required
def get_detailed_usage():
    """Get detailed usage data for each request (admin only)"""
    try:
        # Check if user is admin
        from scheduler.decorators import is_admin_user
        if not is_admin_user(current_user):
            return jsonify({
                'success': False,
                'error': 'Admin access required'
            }), 403
        
        days = request.args.get('days', 30, type=int)
        api_type = request.args.get('api_type', None)
        operation = request.args.get('operation', None)
        
        # Get detailed usage data
        detailed_data = APIUsage.get_detailed_usage(
            company_id=current_user.company_id,
            api_type=api_type,
            days=days
        )
        
        # Filter by operation if specified
        if operation:
            detailed_data = [item for item in detailed_data if item.get('operation') == operation]
        
        # Recalculate costs using Grok rate for each item
        for item in detailed_data:
            item['cost'] = (item.get('output_tokens', 0) / 1_000_000) * 1.50
        
        # Calculate summary stats
        stats = {
            'request_count': len(detailed_data),
            'total_tokens': sum(item.get('total_tokens', 0) for item in detailed_data),
            'total_cost': sum(item.get('cost', 0) for item in detailed_data),
            'active_users': len(set(item.get('user') for item in detailed_data if item.get('user')))
        }
        
        return jsonify({
            'success': True,
            'data': detailed_data,
            'stats': stats,
            'period_days': days,
            'filters': {
                'operation': operation
            }
        })
        
    except Exception as e:
        ai_logger.error(f"Failed to get detailed usage: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve detailed usage'
        }), 500


@login_required
def migrate_rag_tokens():
    """Migrate RAG token usage from logs to database (admin only)"""
    try:
        # Check if user is admin
        from scheduler.decorators import is_admin_user
        if not is_admin_user(current_user):
            return jsonify({
                'success': False,
                'error': 'Admin access required'
            }), 403
        
        # Get absolute path to log file
        import os
        log_file_path = os.path.join(os.getcwd(), 'logs', 'ai.log')
        
        # Check if log file exists
        if not os.path.exists(log_file_path):
            ai_logger.warning(f"Log file not found at: {log_file_path}")
            return jsonify({
                'success': False,
                'error': f'Log file not found at {log_file_path}. Make sure logs/ai.log exists.'
            }), 400
        
        # Run migration using local RAGTokenMigrator class
        result = RAGTokenMigrator.run_migration(
            log_file_path=log_file_path,
            company_id=current_user.company_id
        )
        
        return jsonify(result)
        
    except Exception as e:
        ai_logger.error(f"Failed to migrate RAG tokens: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Migration failed: {str(e)}'
        }), 500


# RAG Token Migrator Class (moved from scripts/migrate_rag_tokens.py to avoid path issues)
import re
from datetime import datetime


class RAGTokenMigrator:
    """Migrate RAG token usage from logs to database"""
    
    # Pattern to match RAG token logs
    # Example: "AI: Chat Query - whatsapp Model: rag_engine Tokens: 318 Duration: 22.49s"
    RAG_TOKEN_PATTERN = r'Model:\s*rag_engine\s+Tokens:\s*(\d+)\s+Duration:'
    
    # Pattern to extract timestamp from log line
    # Example: "2026-02-06 10:30:45 - ai - INFO"
    TIMESTAMP_PATTERN = r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})'
    
    @staticmethod
    def get_migration_status():
        """Check if migration has already been done"""
        try:
            from models.database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Check if we have a migration marker
            cur.execute("""
                SELECT COUNT(*) FROM api_usage 
                WHERE operation = 'RAG_MIGRATION' 
                AND api_type = 'rag_engine'
            """)
            
            count = cur.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except Exception as e:
            ai_logger.error(f"Failed to check migration status: {str(e)}")
            return False
    
    @staticmethod
    def remove_duplicate_entries():
        """Remove duplicate RAG entries to prevent duplicates on re-run"""
        try:
            from models.database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Remove all RAG entries except the migration marker
            cur.execute("""
                DELETE FROM api_usage 
                WHERE api_type = 'rag_engine' 
                AND operation != 'RAG_MIGRATION'
            """)
            
            deleted_count = cur.rowcount
            conn.commit()
            conn.close()
            
            ai_logger.info(f"Removed {deleted_count} duplicate RAG entries")
            return deleted_count
            
        except Exception as e:
            ai_logger.error(f"Failed to remove duplicates: {str(e)}")
            return 0
    
    @staticmethod
    def mark_migration_complete():
        """Mark migration as complete"""
        try:
            APIUsage.log_usage(
                user_id=None,
                api_type='rag_engine',
                model_name='rag_engine',
                operation='RAG_MIGRATION',
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                company_id='haval'
            )
            ai_logger.info("Migration marked as complete")
        except Exception as e:
            ai_logger.error(f"Failed to mark migration complete: {str(e)}")
    
    @staticmethod
    def parse_log_file(log_file_path):
        """
        Parse ai.log file and extract RAG token usage
        
        Args:
            log_file_path: Path to ai.log file
        
        Returns:
            List of tuples: (timestamp, total_tokens, operation)
        """
        import os
        entries = []
        
        try:
            if not os.path.exists(log_file_path):
                ai_logger.error(f"Log file not found: {log_file_path}")
                raise FileNotFoundError(f"Log file not found at {log_file_path}")
            
            if not os.path.isfile(log_file_path):
                ai_logger.error(f"Path is not a file: {log_file_path}")
                raise ValueError(f"Path is not a file: {log_file_path}")
            
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            ai_logger.info(f"Parsing {len(lines)} lines from {log_file_path}")
            
            for line in lines:
                # Check if line contains RAG token information
                if 'rag_engine' in line and 'Tokens:' in line:
                    try:
                        # Extract timestamp
                        timestamp_match = re.search(RAGTokenMigrator.TIMESTAMP_PATTERN, line)
                        if not timestamp_match:
                            continue
                        
                        timestamp_str = timestamp_match.group(1)
                        
                        # Extract tokens (total tokens only)
                        token_match = re.search(RAGTokenMigrator.RAG_TOKEN_PATTERN, line)
                        if not token_match:
                            continue
                        
                        total_tokens = int(token_match.group(1))
                        
                        # Extract operation (Chat Query, etc.)
                        operation = 'RAG query processing'
                        if 'Chat Query' in line:
                            operation = 'Chat Query - RAG'
                        
                        entries.append({
                            'timestamp': timestamp_str,
                            'input_tokens': 0,  # Not available in logs
                            'output_tokens': total_tokens,  # Use total as output
                            'total_tokens': total_tokens,
                            'operation': operation
                        })
                        
                    except Exception as e:
                        # ai_logger.debug(f"Failed to parse line: {line[:100]} - {str(e)}")
                        continue
            
            ai_logger.info(f"Extracted {len(entries)} RAG token entries from logs")
            return entries
            
        except Exception as e:
            ai_logger.error(f"Error parsing log file: {str(e)}")
            return entries
    
    @staticmethod
    def migrate_to_database(entries, company_id='haval'):
        """
        Save extracted entries to database
        
        Args:
            entries: List of token entries
            company_id: Company identifier
        
        Returns:
            Number of entries saved
        """
        from models.database import get_db_connection
        saved_count = 0
        
        try:
            for entry in entries:
                try:
                    # Estimate cost for RAG (treat as embedding-like operation)
                    from utils.token_counter import TokenCounter
                    cost = TokenCounter.estimate_cost(
                        entry['input_tokens'],
                        entry['output_tokens'],
                        'embedding'  # Use embedding pricing as baseline
                    )
                    
                    # Save to database
                    conn = get_db_connection()
                    cur = conn.cursor()
                    
                    cur.execute("""
                        INSERT INTO api_usage 
                        (user_id, company_id, api_type, model_name, operation, 
                         input_tokens, output_tokens, total_tokens, cost, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        None,  # user_id
                        company_id,
                        'rag_engine',
                        'rag_engine',
                        entry['operation'],
                        entry['input_tokens'],
                        entry['output_tokens'],
                        entry['total_tokens'],
                        cost,
                        entry['timestamp']
                    ))
                    
                    conn.commit()
                    conn.close()
                    
                    saved_count += 1
                    
                except Exception as e:
                    ai_logger.error(f"Failed to save entry: {str(e)}")
                    continue
            
            ai_logger.info(f"Successfully saved {saved_count} RAG token entries to database")
            return saved_count
            
        except Exception as e:
            ai_logger.error(f"Error migrating to database: {str(e)}")
            return saved_count
    
    @staticmethod
    def run_migration(log_file_path='logs/ai.log', company_id='haval'):
        """
        Run the complete migration process
        
        Args:
            log_file_path: Path to ai.log file
            company_id: Company identifier
        
        Returns:
            Dictionary with migration results
        """
        ai_logger.info("=" * 70)
        ai_logger.info("RAG TOKEN MIGRATION PROCESS STARTED")
        ai_logger.info("=" * 70)
        
        # Remove any existing duplicate entries first (including old marker)
        ai_logger.info("Step 0: Removing any existing duplicate entries")
        deleted = RAGTokenMigrator.remove_duplicate_entries()
        
        # Also remove the migration marker to allow re-running
        try:
            from models.database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                DELETE FROM api_usage 
                WHERE operation = 'RAG_MIGRATION' 
                AND api_type = 'rag_engine'
            """)
            conn.commit()
            conn.close()
            ai_logger.info("Removed migration marker to allow re-running")
        except Exception as e:
            ai_logger.error(f"Failed to remove migration marker: {str(e)}")
        
        # Parse log file
        ai_logger.info(f"Step 1: Parsing log file: {log_file_path}")
        entries = RAGTokenMigrator.parse_log_file(log_file_path)
        
        if not entries:
            ai_logger.warning("No RAG token entries found in logs")
            return {
                'success': False,
                'status': 'no_entries_found',
                'entries_found': 0,
                'entries_migrated': 0,
                'message': 'No RAG token entries found in the log file'
            }
        
        # Migrate to database
        ai_logger.info(f"Step 2: Migrating {len(entries)} entries to database")
        saved_count = RAGTokenMigrator.migrate_to_database(entries, company_id)
        
        # Mark migration as complete
        ai_logger.info("Step 3: Marking migration as complete")
        RAGTokenMigrator.mark_migration_complete()
        
        ai_logger.info("=" * 70)
        ai_logger.info(f"MIGRATION COMPLETE - {saved_count} entries saved")
        ai_logger.info("=" * 70)
        
        return {
            'success': True,
            'status': 'completed',
            'entries_found': len(entries),
            'entries_migrated': saved_count,
            'message': f'Successfully migrated {saved_count} RAG token entries to database'
        }
