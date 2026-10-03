"""
Gmail OAuth Service
Handles Google OAuth 2.0 authentication flow and token management
"""

import json
import os
import pickle
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build

from utils.logger import log_error

# Allow HTTP for localhost development (required for OAuth with localhost)
# Allow scope changes (Google may reorder or add scopes like 'openid')
# REMOVE THESE IN PRODUCTION - use HTTPS only and strict scope validation
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'


class GmailOAuthService:
    """
    Manages Gmail OAuth 2.0 authentication and token lifecycle
    Clean implementation without encryption complexity
    """
    
    # OAuth Scopes - Gmail read and send access
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile'
    ]
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = None):
        """
        Initialize Gmail OAuth Service
        
        Args:
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret
            redirect_uri: OAuth callback redirect URI
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri or 'http://localhost:10000/auth/gmail/callback'
        
        # Token storage directory
        self.token_dir = Path("data/oauth_tokens")
        self.token_dir.mkdir(parents=True, exist_ok=True)
        
    def get_client_config(self) -> Dict[str, Any]:
        """Get OAuth client configuration"""
        return {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }
    
    def get_authorization_url(self, user_id: str) -> tuple[str, str]:
        """
        Generate OAuth authorization URL
        
        Args:
            user_id: User identifier for state management
            
        Returns:
            Tuple of (authorization_url, state)
        """
        try:
            flow = Flow.from_client_config(
                self.get_client_config(),
                scopes=self.SCOPES,
                redirect_uri=self.redirect_uri
            )
            
            # Generate authorization URL with state parameter
            auth_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent',
                state=user_id  # Use user_id as state for verification
            )
            
            print(f"[Gmail OAuth] Generated auth URL for user: {user_id}")
            return auth_url, state
            
        except Exception as e:
            log_error(f"Error generating authorization URL: {e}")
            raise
    
    def handle_oauth_callback(self, authorization_code: str, user_id: str) -> bool:
        """
        Handle OAuth callback and exchange code for tokens
        
        Args:
            authorization_code: Authorization code from OAuth callback
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"[Gmail OAuth] 🔄 Starting token exchange for user: {user_id}")
            print(f"[Gmail OAuth]   redirect_uri: {self.redirect_uri}")
            
            flow = Flow.from_client_config(
                self.get_client_config(),
                scopes=self.SCOPES,
                redirect_uri=self.redirect_uri
            )
            
            # Exchange authorization code for credentials
            # Suppress scope order change warnings (Google may reorder scopes or add 'openid')
            print(f"[Gmail OAuth] 📡 Fetching token from Google...")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                flow.fetch_token(code=authorization_code)
            
            credentials = flow.credentials
            
            if not credentials:
                raise ValueError("Failed to obtain credentials from token exchange")
            
            print(f"[Gmail OAuth] 💾 Saving credentials...")
            # Save tokens (without encryption for simplicity)
            self.save_credentials(user_id, credentials)
            
            print(f"[Gmail OAuth] ✅ Successfully authenticated user: {user_id}")
            return True
            
        except Exception as e:
            log_error(f"Error handling OAuth callback: {e}")
            print(f"[Gmail OAuth] ❌ Failed to authenticate user: {user_id}")
            print(f"[Gmail OAuth] ❌ Error type: {type(e).__name__}")
            print(f"[Gmail OAuth] ❌ Error details: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_credentials(self, user_id: str, credentials: Credentials) -> None:
        """
        Save credentials to disk (simplified without encryption)
        
        Args:
            user_id: User identifier
            credentials: Google OAuth credentials
        """
        try:
            print(f"[Gmail OAuth] 💾 save_credentials() called for user: {user_id}")
            token_file = self.token_dir / f"gmail_token_{user_id}.json"
            print(f"[Gmail OAuth]   Token file path: {token_file}")
            
            # Ensure token directory exists
            self.token_dir.mkdir(parents=True, exist_ok=True)
            print(f"[Gmail OAuth]   Token directory created/verified")
            
            # Serialize credentials (no encryption for simplicity)
            print(f"[Gmail OAuth]   Serializing credentials...")
            print(f"[Gmail OAuth]   - token present: {bool(credentials.token)}")
            print(f"[Gmail OAuth]   - refresh_token present: {bool(credentials.refresh_token)}")
            print(f"[Gmail OAuth]   - scopes: {credentials.scopes}")
            
            cred_data = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes,
                'expiry': credentials.expiry.isoformat() if credentials.expiry else None
            }
            
            print(f"[Gmail OAuth]   Credentials serialized successfully")
            # Save to file
            with open(token_file, 'w') as f:
                json.dump(cred_data, f, indent=2)
            
            print(f"[Gmail OAuth] ✅ Saved credentials for user: {user_id} to {token_file}")
            
        except Exception as e:
            log_error(f"Error saving credentials: {e}")
            print(f"[Gmail OAuth] ❌ Failed to save credentials: {e}")
            raise
    
    def load_credentials(self, user_id: str) -> Optional[Credentials]:
        """
        Load credentials from disk (simplified without decryption)
        
        Args:
            user_id: User identifier
            
        Returns:
            Credentials object or None if not found
        """
        try:
            token_file = self.token_dir / f"gmail_token_{user_id}.json"
            
            if not token_file.exists():
                print(f"[Gmail OAuth] No token file found for user: {user_id}")
                return None
            
            # Load and deserialize
            with open(token_file, 'r') as f:
                cred_data = json.load(f)
            
            # Reconstruct credentials
            credentials = Credentials(
                token=cred_data.get('token'),
                refresh_token=cred_data.get('refresh_token'),
                token_uri=cred_data.get('token_uri'),
                client_id=cred_data.get('client_id'),
                client_secret=cred_data.get('client_secret'),
                scopes=cred_data.get('scopes')
            )
            
            # Set expiry
            if cred_data.get('expiry'):
                credentials.expiry = datetime.fromisoformat(cred_data['expiry'])
            
            print(f"[Gmail OAuth] ✅ Loaded credentials for user: {user_id}")
            
            # Refresh if expired
            if credentials.expired and credentials.refresh_token:
                print(f"[Gmail OAuth] Refreshing expired token for user: {user_id}")
                try:
                    credentials.refresh(Request())
                    self.save_credentials(user_id, credentials)
                    print(f"[Gmail OAuth] ✅ Token refreshed for user: {user_id}")
                except Exception as refresh_error:
                    log_error(f"Failed to refresh token: {refresh_error}")
                    print(f"[Gmail OAuth] ❌ Token refresh failed: {refresh_error}")
                    return None
            
            return credentials
            
        except Exception as e:
            log_error(f"Error loading credentials: {e}")
            print(f"[Gmail OAuth] ❌ Failed to load credentials for {user_id}: {e}")
            return None
    
    def get_gmail_service(self, user_id: str):
        """
        Get authenticated Gmail API service
        
        Args:
            user_id: User identifier
            
        Returns:
            Gmail API service object or None
        """
        try:
            credentials = self.load_credentials(user_id)
            
            if not credentials:
                print(f"[Gmail OAuth] No valid credentials for user: {user_id}")
                return None
            
            service = build('gmail', 'v1', credentials=credentials)
            print(f"[Gmail OAuth] ✅ Created Gmail service for user: {user_id}")
            return service
            
        except Exception as e:
            log_error(f"Error creating Gmail service: {e}")
            print(f"[Gmail OAuth] ❌ Failed to create Gmail service: {e}")
            return None
    
    def revoke_access(self, user_id: str) -> bool:
        """
        Revoke OAuth access and delete stored tokens
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            token_file = self.token_dir / f"gmail_token_{user_id}.json"
            
            # Delete token file
            if token_file.exists():
                token_file.unlink()
                print(f"[Gmail OAuth] ✅ Revoked access for user: {user_id}")
                return True
            else:
                print(f"[Gmail OAuth] No token file to revoke for user: {user_id}")
                return True  # Consider this success
            
        except Exception as e:
            log_error(f"Error revoking access: {e}")
            print(f"[Gmail OAuth] ❌ Failed to revoke access: {e}")
            return False
    
    def is_authenticated(self, user_id: str) -> bool:
        """
        Check if user is authenticated
        
        Args:
            user_id: User identifier
            
        Returns:
            True if authenticated, False otherwise
        """
        print(f"[Gmail OAuth] is_authenticated() called for user_id: {user_id}")
        try:
            print(f"[Gmail OAuth]   Loading credentials...")
            credentials = self.load_credentials(user_id)
            print(f"[Gmail OAuth]   Credentials loaded: {credentials is not None}")
            
            if credentials is None:
                print(f"[Gmail OAuth]   No credentials found, returning False")
                return False
                
            print(f"[Gmail OAuth]   Credentials expired: {credentials.expired}")
            print(f"[Gmail OAuth]   Has refresh_token: {bool(credentials.refresh_token)}")
            
            is_auth = credentials is not None and (not credentials.expired or credentials.refresh_token)
            print(f"[Gmail OAuth]   Authentication status for {user_id}: {is_auth}")
            return is_auth
        except Exception as e:
            print(f"[Gmail OAuth]   ERROR in is_authenticated: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            log_error(f"Error checking authentication: {e}")
            return False
    
    def get_user_email(self, user_id: str) -> Optional[str]:
        """
        Get authenticated user's email address
        
        Args:
            user_id: User identifier
            
        Returns:
            Email address or None
        """
        try:
            service = self.get_gmail_service(user_id)
            
            if not service:
                print(f"[Gmail OAuth] No Gmail service available for user: {user_id}")
                return None
            
            profile = service.users().getProfile(userId='me').execute()
            email = profile.get('emailAddress')
            print(f"[Gmail OAuth] ✅ Retrieved email for user {user_id}: {email}")
            return email
            
        except Exception as e:
            log_error(f"Error getting user email: {e}")
            print(f"[Gmail OAuth] ❌ Failed to get email for user {user_id}: {e}")
            return None
    
    def get_simple_flow_for_desktop_auth(self) -> InstalledAppFlow:
        """
        Get a simple OAuth flow for desktop authentication (like reference code)
        
        Returns:
            InstalledAppFlow instance for desktop app authentication
        """
        try:
            flow = InstalledAppFlow.from_client_config(
                self.get_client_config()["web"], 
                self.SCOPES
            )
            return flow
        except Exception as e:
            log_error(f"Error creating desktop OAuth flow: {e}")
            raise
            
        except Exception as e:
            log_error(f"Error getting user email: {e}")
            return None
