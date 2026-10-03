
"""
Email Module - OAuth & Vector Integration
Provides Gmail OAuth authentication and email vector database management
"""

from ai.email.email_indexer import EmailIndexer
from ai.email.email_vector_store import EmailVectorStore
from ai.email.gmail_langchain_service import GmailLangchainService
from ai.email.gmail_oauth_service import GmailOAuthService

__all__ = [
    'GmailOAuthService',
    'GmailLangchainService',
    'EmailVectorStore',
    'EmailIndexer'
]
