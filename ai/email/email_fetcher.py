"""
Clean Gmail Email Fetcher Service
Handles fetching emails via Gmail API with OAuth2 authentication
Based on reference implementation with improved error handling
"""

import base64
import email
from datetime import datetime, timedelta
from email.header import decode_header
from typing import Dict, List, Optional

from ai.email.gmail_oauth_service import GmailOAuthService
from utils.logger import log_error


class CleanEmailFetcher:
    """
    Clean Gmail email fetcher with OAuth2 support
    Fetches emails using Gmail API instead of IMAP for better reliability
    """
    
    def __init__(self, oauth_service: GmailOAuthService):
        """
        Initialize email fetcher
        
        Args:
            oauth_service: Gmail OAuth service instance
        """
        self.oauth_service = oauth_service
    
    def fetch_emails(
        self, 
        user_id: str, 
        folder: str = "INBOX", 
        limit: int = 100,
        days_back: int = 30
    ) -> List[Dict]:
        """
        Fetch emails from Gmail using API
        
        Args:
            user_id: User identifier
            folder: Gmail label/folder (default: INBOX)
            limit: Maximum number of emails to fetch
            days_back: Number of days back to search
            
        Returns:
            List of email dictionaries
        """
        emails = []
        
        try:
            print(f"[Email Fetcher] 📧 Starting to fetch emails for user: {user_id}")
            
            # Get Gmail service
            service = self.oauth_service.get_gmail_service(user_id)
            if not service:
                print(f"[Email Fetcher] ❌ No Gmail service available for user: {user_id}")
                return []
            
            # Calculate date filter
            after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
            query = f'in:{folder.lower()} after:{after_date}'
            
            print(f"[Email Fetcher] 🔍 Searching with query: {query}")
            
            # Search for messages
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=limit
            ).execute()
            
            messages = results.get('messages', [])
            print(f"[Email Fetcher] 📊 Found {len(messages)} emails")
            
            # Fetch email details
            for i, message in enumerate(messages):
                try:
                    print(f"[Email Fetcher] 📄 Processing email {i+1}/{len(messages)}")
                    
                    email_data = self._get_email_data(service, message['id'])
                    if email_data:
                        emails.append(email_data)
                        
                except Exception as e:
                    log_error(f"Error processing message {message['id']}: {e}")
                    print(f"[Email Fetcher] ⚠️ Skipped email {message['id']}: {e}")
                    continue
            
            print(f"[Email Fetcher] ✅ Successfully fetched {len(emails)} emails")
            return emails
            
        except Exception as e:
            log_error(f"Error fetching emails: {e}")
            print(f"[Email Fetcher] ❌ Error fetching emails: {e}")
            return []
    
    def _get_email_data(self, service, message_id: str) -> Optional[Dict]:
        """
        Get detailed email data for a message
        
        Args:
            service: Gmail API service
            message_id: Email message ID
            
        Returns:
            Email data dictionary or None
        """
        try:
            # Get full message
            message = service.users().messages().get(
                userId='me', 
                id=message_id, 
                format='full'
            ).execute()
            
            # Extract headers
            headers = {}
            for header in message['payload'].get('headers', []):
                headers[header['name']] = header['value']
            
            # Extract basic info
            subject = self._decode_header(headers.get('Subject', 'No Subject'))
            from_addr = self._decode_header(headers.get('From', 'Unknown'))
            to_addr = self._decode_header(headers.get('To', ''))
            date_str = headers.get('Date', '')
            
            # Parse date
            email_date = self._parse_email_date(date_str)
            
            # Extract body
            body = self._extract_email_body(message['payload'])
            
            # Build email data
            email_data = {
                'id': message_id,
                'subject': subject,
                'from_address': from_addr,
                'to_address': to_addr,
                'date': email_date,
                'body': body,
                'thread_id': message.get('threadId', ''),
                'labels': message.get('labelIds', []),
                'snippet': message.get('snippet', ''),
                'size': message.get('sizeEstimate', 0)
            }
            
            return email_data
            
        except Exception as e:
            log_error(f"Error getting email data for {message_id}: {e}")
            return None
    
    def _decode_header(self, header_value: str) -> str:
        """
        Decode email header value
        
        Args:
            header_value: Raw header value
            
        Returns:
            Decoded header value
        """
        if not header_value:
            return ""
        
        try:
            decoded_parts = []
            for part, encoding in decode_header(header_value):
                if isinstance(part, bytes):
                    decoded_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
                else:
                    decoded_parts.append(str(part))
            return ''.join(decoded_parts)
        except Exception as e:
            log_error(f"Error decoding header: {e}")
            return str(header_value)
    
    def _parse_email_date(self, date_str: str) -> datetime:
        """
        Parse email date string
        
        Args:
            date_str: Email date string
            
        Returns:
            Parsed datetime object
        """
        try:
            # Try parsing with email.utils
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except Exception:
            # Fallback to current time
            return datetime.now()
    
    def _extract_email_body(self, payload: Dict) -> str:
        """
        Extract email body from Gmail payload
        
        Args:
            payload: Gmail message payload
            
        Returns:
            Email body text
        """
        body = ""
        
        try:
            if 'parts' in payload:
                # Multipart message
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        if 'data' in part['body']:
                            body = base64.urlsafe_b64decode(
                                part['body']['data']
                            ).decode('utf-8', errors='ignore')
                            break
                    elif part['mimeType'] == 'text/html' and not body:
                        if 'data' in part['body']:
                            body = base64.urlsafe_b64decode(
                                part['body']['data']
                            ).decode('utf-8', errors='ignore')
                            # Remove HTML tags
                            import re
                            body = re.sub(r'<[^>]+>', '', body)
            else:
                # Single part message
                if payload['mimeType'] == 'text/plain' and 'data' in payload['body']:
                    body = base64.urlsafe_b64decode(
                        payload['body']['data']
                    ).decode('utf-8', errors='ignore')
            
            # Clean up body
            body = body.strip()
            # Remove extra whitespace
            import re
            body = re.sub(r'\s+', ' ', body)
            
            return body
            
        except Exception as e:
            log_error(f"Error extracting email body: {e}")
            return ""
    
    def get_email_count(self, user_id: str, folder: str = "INBOX") -> int:
        """
        Get count of emails in folder
        
        Args:
            user_id: User identifier
            folder: Gmail label/folder
            
        Returns:
            Number of emails
        """
        try:
            service = self.oauth_service.get_gmail_service(user_id)
            if not service:
                return 0
            
            results = service.users().messages().list(
                userId='me',
                q=f'in:{folder.lower()}',
                maxResults=1
            ).execute()
            
            return results.get('resultSizeEstimate', 0)
            
        except Exception as e:
            log_error(f"Error getting email count: {e}")
            return 0
    
    def sync_recent_emails(
        self, 
        user_id: str, 
        hours_back: int = 24,
        max_emails: int = 50
    ) -> Dict:
        """
        Sync recent emails (useful for background sync)
        
        Args:
            user_id: User identifier
            hours_back: Hours to look back
            max_emails: Maximum emails to fetch
            
        Returns:
            Sync results dictionary
        """
        try:
            print(f"[Email Fetcher] 🔄 Starting recent email sync for user: {user_id}")
            
            # Fetch recent emails
            emails = self.fetch_emails(
                user_id=user_id,
                limit=max_emails,
                days_back=max(1, hours_back // 24)  # Convert hours to days
            )
            
            result = {
                'success': True,
                'fetched': len(emails),
                'emails': emails,
                'sync_time': datetime.now().isoformat()
            }
            
            print(f"[Email Fetcher] ✅ Sync completed: {len(emails)} emails")
            return result
            
        except Exception as e:
            log_error(f"Error in recent email sync: {e}")
            return {
                'success': False,
                'error': str(e),
                'fetched': 0,
                'emails': []
            }