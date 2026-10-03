"""
Email Indexer
Orchestrates email fetching, processing, and indexing into vector store
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ai.email.email_vector_store import EmailVectorStore
from ai.email.gmail_langchain_service import GmailLangchainService
from ai.email.gmail_oauth_service import GmailOAuthService
from utils.logger import log_error


class EmailIndexer:
    """
    Manages the complete email indexing pipeline:
    1. Fetch emails from Gmail
    2. Convert to Langchain documents
    3. Index into vector store
    """
    
    def __init__(
        self,
        oauth_service: GmailOAuthService,
        vector_store: EmailVectorStore
    ):
        """
        Initialize Email Indexer
        
        Args:
            oauth_service: Gmail OAuth service instance
            vector_store: Email vector store instance
        """
        self.oauth_service = oauth_service
        self.vector_store = vector_store
    
    def index_user_emails(
        self,
        user_id: str,
        max_emails: int = 100,
        query: str = "",
        after_date: Optional[datetime] = None,
        index_only_new: bool = True
    ) -> Dict[str, Any]:
        """
        Index emails for a specific user
        
        Args:
            user_id: User identifier
            max_emails: Maximum number of emails to fetch
            query: Gmail search query
            after_date: Fetch emails after this date
            index_only_new: Only index emails not already in vector store
            
        Returns:
            Dictionary with indexing results
        """
        print(f"[Email Indexer] index_user_emails called for user: {user_id}")
        print(f"[Email Indexer]   max_emails={max_emails}, query={query}, index_only_new={index_only_new}")
        
        try:
            # Get Gmail service
            print("[Email Indexer] Getting Gmail service...")
            gmail_service = self.oauth_service.get_gmail_service(user_id)
            
            if not gmail_service:
                print("[Email Indexer] ERROR: No Gmail service returned")
                return {
                    'success': False,
                    'error': 'User not authenticated or token expired',
                    'user_id': user_id
                }
            print("[Email Indexer] Gmail service obtained successfully")
            
            # Initialize Gmail Langchain service
            print("[Email Indexer] Initializing GmailLangchainService...")
            gmail_langchain = GmailLangchainService(gmail_service)
            
            # Fetch emails
            print(f"[Email Indexer] Fetching emails for user: {user_id}")
            try:
                emails = gmail_langchain.fetch_emails(
                    max_results=max_emails,
                    query=query,
                    after_date=after_date
                )
                print(f"[Email Indexer] Fetched {len(emails) if emails else 0} emails")
            except Exception as fetch_error:
                print(f"[Email Indexer] ERROR fetching emails: {type(fetch_error).__name__}: {fetch_error}")
                import traceback
                traceback.print_exc()
                raise
            
            if not emails:
                print("[Email Indexer] No emails found")
                return {
                    'success': True,
                    'user_id': user_id,
                    'total_fetched': 0,
                    'indexed': 0,
                    'skipped': 0,
                    'message': 'No emails found matching criteria'
                }
            
            # Convert to documents
            print(f"[Email Indexer] Converting {len(emails)} emails to documents")
            try:
                documents = gmail_langchain.emails_to_documents(emails)
                print(f"[Email Indexer] Created {len(documents)} documents")
            except Exception as convert_error:
                print(f"[Email Indexer] ERROR converting to documents: {type(convert_error).__name__}: {convert_error}")
                import traceback
                traceback.print_exc()
                raise
            
            # Index documents
            print(f"[Email Indexer] Indexing {len(documents)} documents...")
            try:
                result = self.vector_store.add_documents(
                    documents,
                    skip_duplicates=index_only_new
                )
                print(f"[Email Indexer] Indexing result: {result}")
            except Exception as index_error:
                print(f"[Email Indexer] ERROR indexing documents: {type(index_error).__name__}: {index_error}")
                import traceback
                traceback.print_exc()
                raise
            
            result['user_id'] = user_id
            result['total_fetched'] = len(emails)
            
            print(f"[Email Indexer] Successfully indexed emails. Result: {result}")
            return result
            
        except Exception as e:
            error_msg = f"Error indexing emails: {e}"
            print(f"[Email Indexer] FATAL ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            log_error(error_msg)
            return {
                'success': False,
                'error': str(e),
                'user_id': user_id,
                'message': error_msg
            }
    
    def get_unindexed_count(self, user_id: str) -> Dict[str, Any]:
        """
        Get count of emails not yet indexed
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with email counts
        """
        try:
            # Get Gmail service
            gmail_service = self.oauth_service.get_gmail_service(user_id)
            
            if not gmail_service:
                return {
                    'success': False,
                    'error': 'User not authenticated'
                }
            
            # Get total email count
            gmail_langchain = GmailLangchainService(gmail_service)
            total_count = gmail_langchain.get_total_email_count()
            
            # Get indexed count
            stats = self.vector_store.get_stats()
            indexed_count = stats.get('unique_emails', 0)
            
            return {
                'success': True,
                'total_emails': total_count,
                'indexed_emails': indexed_count,
                'unindexed_emails': max(0, total_count - indexed_count),
                'user_id': user_id
            }
            
        except Exception as e:
            log_error(f"Error getting unindexed count: {e}")
            return {
                'success': False,
                'error': str(e),
                'user_id': user_id
            }
    
    def index_recent_emails(
        self,
        user_id: str,
        days: int = 30,
        max_emails: int = 500
    ) -> Dict[str, Any]:
        """
        Index recent emails from last N days
        
        Args:
            user_id: User identifier
            days: Number of days to look back
            max_emails: Maximum emails to index
            
        Returns:
            Dictionary with indexing results
        """
        after_date = datetime.now() - timedelta(days=days)
        
        return self.index_user_emails(
            user_id=user_id,
            max_emails=max_emails,
            after_date=after_date,
            index_only_new=True
        )
    
    def index_by_query(
        self,
        user_id: str,
        search_query: str,
        max_emails: int = 100
    ) -> Dict[str, Any]:
        """
        Index emails matching a specific query
        
        Args:
            user_id: User identifier
            search_query: Gmail search query (e.g., "subject:complaint")
            max_emails: Maximum emails to index
            
        Returns:
            Dictionary with indexing results
        """
        return self.index_user_emails(
            user_id=user_id,
            max_emails=max_emails,
            query=search_query,
            index_only_new=True
        )
    
    def batch_index_emails(
        self,
        user_id: str,
        batch_size: int = 50,
        total_limit: int = 1000,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Index emails in batches for large mailboxes
        
        Args:
            user_id: User identifier
            batch_size: Number of emails per batch
            total_limit: Total maximum emails to index
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Dictionary with overall indexing results
        """
        try:
            total_indexed = 0
            total_skipped = 0
            batches_processed = 0
            
            # Get Gmail service
            gmail_service = self.oauth_service.get_gmail_service(user_id)
            
            if not gmail_service:
                return {
                    'success': False,
                    'error': 'User not authenticated'
                }
            
            gmail_langchain = GmailLangchainService(gmail_service)
            
            while total_indexed < total_limit:
                # Calculate remaining
                remaining = min(batch_size, total_limit - total_indexed)
                
                # Fetch batch
                print(f"[Email Indexer] Processing batch {batches_processed + 1}")
                emails = gmail_langchain.fetch_emails(max_results=remaining)
                
                if not emails:
                    break
                
                # Convert and index
                documents = gmail_langchain.emails_to_documents(emails)
                result = self.vector_store.add_documents(documents, skip_duplicates=True)
                
                # Update totals
                total_indexed += result.get('indexed', 0)
                total_skipped += result.get('skipped', 0)
                batches_processed += 1
                
                # Progress callback
                if progress_callback:
                    progress_callback({
                        'batch': batches_processed,
                        'indexed': total_indexed,
                        'skipped': total_skipped
                    })
                
                # Break if no more new emails
                if result.get('indexed', 0) == 0:
                    break
            
            return {
                'success': True,
                'user_id': user_id,
                'total_indexed': total_indexed,
                'total_skipped': total_skipped,
                'batches_processed': batches_processed,
                'message': f'Successfully indexed {total_indexed} emails in {batches_processed} batches'
            }
            
        except Exception as e:
            log_error(f"Error in batch indexing: {e}")
            return {
                'success': False,
                'error': str(e),
                'user_id': user_id
            }
    
    def get_indexing_status(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive indexing status
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with status information
        """
        try:
            # Check authentication
            is_authenticated = self.oauth_service.is_authenticated(user_id)
            
            if not is_authenticated:
                return {
                    'authenticated': False,
                    'user_id': user_id,
                    'message': 'User not authenticated with Gmail'
                }
            
            # Get email counts
            counts = self.get_unindexed_count(user_id)
            
            # Get vector store stats
            stats = self.vector_store.get_stats()
            
            # Get user email
            user_email = self.oauth_service.get_user_email(user_id)
            
            return {
                'authenticated': True,
                'user_id': user_id,
                'user_email': user_email,
                'total_emails': counts.get('total_emails', 0),
                'indexed_emails': counts.get('indexed_emails', 0),
                'unindexed_emails': counts.get('unindexed_emails', 0),
                'vector_store_stats': stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            log_error(f"Error getting indexing status: {e}")
            return {
                'authenticated': False,
                'user_id': user_id,
                'error': str(e)
            }
