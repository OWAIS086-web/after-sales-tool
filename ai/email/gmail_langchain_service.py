"""
Gmail Langchain Service
Integrates Gmail API with Langchain for email fetching and document processing
"""

import base64
import email
from datetime import datetime, timedelta
from email import policy
from email.parser import BytesParser
from typing import Any, Dict, List, Optional

from googleapiclient.errors import HttpError

# LangChain Document import - handle different versions
try:
    from langchain_core.documents import Document
except ImportError:
    try:
        from langchain.docstore.document import Document
    except ImportError:
        from langchain.schema import Document

from utils.logger import log_error


class GmailLangchainService:
    """
    Fetches emails from Gmail API and converts them to Langchain Documents
    """
    
    def __init__(self, gmail_service):
        """
        Initialize Gmail Langchain Service
        
        Args:
            gmail_service: Authenticated Gmail API service object
        """
        self.service = gmail_service
    
    def fetch_emails(
        self,
        max_results: int = 100,
        query: str = "",
        after_date: Optional[datetime] = None,
        before_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails from Gmail
        
        Args:
            max_results: Maximum number of emails to fetch
            query: Gmail search query (e.g., "subject:complaint")
            after_date: Fetch emails after this date
            before_date: Fetch emails before this date
            
        Returns:
            List of email dictionaries
        """
        try:
            # Build query with date filters
            search_query = query
            
            if after_date:
                after_str = after_date.strftime('%Y/%m/%d')
                search_query += f" after:{after_str}"
            
            if before_date:
                before_str = before_date.strftime('%Y/%m/%d')
                search_query += f" before:{before_str}"
            
            # Fetch message list
            results = self.service.users().messages().list(
                userId='me',
                q=search_query.strip(),
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                print("[Gmail] No messages found")
                return []
            
            # Fetch full message details
            emails = []
            for msg in messages:
                try:
                    email_data = self._get_message_details(msg['id'])
                    if email_data:
                        emails.append(email_data)
                except Exception as e:
                    log_error(f"Error fetching message {msg['id']}: {e}")
                    continue
            
            print(f"[Gmail] Fetched {len(emails)} emails")
            return emails
            
        except HttpError as error:
            log_error(f"Gmail API error: {error}")
            return []
        except Exception as e:
            log_error(f"Error fetching emails: {e}")
            return []
    
    def _get_message_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific message
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Dictionary with email details
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Extract headers
            headers = message.get('payload', {}).get('headers', [])
            subject = self._get_header(headers, 'Subject')
            sender = self._get_header(headers, 'From')
            to = self._get_header(headers, 'To')
            date = self._get_header(headers, 'Date')
            
            # Extract body
            body = self._get_message_body(message.get('payload', {}))
            
            # Parse date
            try:
                email_date = datetime.strptime(date, '%a, %d %b %Y %H:%M:%S %z') if date else None
            except:
                email_date = None
            
            return {
                'id': message_id,
                'thread_id': message.get('threadId'),
                'subject': subject,
                'sender': sender,
                'to': to,
                'date': email_date,
                'body': body,
                'snippet': message.get('snippet', ''),
                'labels': message.get('labelIds', [])
            }
            
        except Exception as e:
            log_error(f"Error getting message details: {e}")
            return None
    
    def _get_header(self, headers: List[Dict], name: str) -> str:
        """Extract header value by name"""
        for header in headers:
            if header.get('name', '').lower() == name.lower():
                return header.get('value', '')
        return ''
    
    def _get_message_body(self, payload: Dict) -> str:
        """
        Extract message body from payload
        
        Args:
            payload: Message payload from Gmail API
            
        Returns:
            Email body text
        """
        body = ''
        
        if 'body' in payload and payload['body'].get('data'):
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
        
        elif 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    if 'data' in part.get('body', {}):
                        body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                elif part.get('mimeType') == 'text/html' and not body:
                    # Use HTML as fallback
                    if 'data' in part.get('body', {}):
                        body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                elif 'parts' in part:
                    # Recursive for nested parts
                    body += self._get_message_body(part)
        
        return body.strip()
    
    def emails_to_documents(self, emails: List[Dict[str, Any]]) -> List[Document]:
        """
        Convert email dictionaries to Langchain Documents
        
        Args:
            emails: List of email dictionaries
            
        Returns:
            List of Langchain Document objects
        """
        documents = []
        
        for email_data in emails:
            # Create document content
            content = f"""Subject: {email_data.get('subject', 'No Subject')}
From: {email_data.get('sender', 'Unknown')}
To: {email_data.get('to', 'Unknown')}
Date: {email_data.get('date', 'Unknown')}

{email_data.get('body', '')}"""
            
            # Create metadata (ChromaDB only accepts str, int, float, bool - NOT None or lists)
            labels_list = email_data.get('labels', [])
            labels_str = ','.join(labels_list) if isinstance(labels_list, list) else str(labels_list) if labels_list else ''
            
            # Get date as string, default to empty string if None
            date_val = email_data.get('date')
            date_str = date_val.isoformat() if date_val else ''
            
            metadata = {
                'source': 'gmail',
                'email_id': email_data.get('id') or '',
                'thread_id': email_data.get('thread_id') or '',
                'subject': email_data.get('subject') or '',
                'sender': email_data.get('sender') or '',
                'to': email_data.get('to') or '',
                'date': date_str,
                'labels': labels_str,
                'snippet': email_data.get('snippet') or ''
            }
            
            # Create document
            doc = Document(
                page_content=content,
                metadata=metadata
            )
            
            documents.append(doc)
        
        return documents
    
    def fetch_unread_emails(self, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch unread emails
        
        Args:
            max_results: Maximum number of emails to fetch
            
        Returns:
            List of unread email dictionaries
        """
        return self.fetch_emails(max_results=max_results, query="is:unread")
    
    def fetch_emails_by_sender(self, sender_email: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch emails from specific sender
        
        Args:
            sender_email: Sender email address
            max_results: Maximum number of emails to fetch
            
        Returns:
            List of email dictionaries
        """
        return self.fetch_emails(max_results=max_results, query=f"from:{sender_email}")
    
    def fetch_emails_by_subject(self, subject_keyword: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch emails with subject containing keyword
        
        Args:
            subject_keyword: Keyword to search in subject
            max_results: Maximum number of emails to fetch
            
        Returns:
            List of email dictionaries
        """
        return self.fetch_emails(max_results=max_results, query=f"subject:{subject_keyword}")
    
    def get_total_email_count(self) -> int:
        """
        Get total number of emails in inbox
        
        Returns:
            Total email count
        """
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return profile.get('messagesTotal', 0)
        except Exception as e:
            log_error(f"Error getting email count: {e}")
            return 0
    
    def mark_as_read(self, message_id: str) -> bool:
        """
        Mark email as read
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            return True
        except Exception as e:
            log_error(f"Error marking as read: {e}")
            return False
