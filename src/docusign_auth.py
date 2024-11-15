import os
import json
from pathlib import Path
from datetime import datetime, timedelta
import requests # type: ignore
from docusign_esign import ApiClient # type: ignore

class DocuSignAuth:
    def __init__(self):
        """Initialize DocuSign authentication handler"""
        self.client_id = os.getenv('DOCUSIGN_CLIENT_ID')
        self.client_secret = os.getenv('DOCUSIGN_CLIENT_SECRET')
        self.redirect_uri = os.getenv('DOCUSIGN_REDIRECT_URI')
        self.auth_server = os.getenv('DOCUSIGN_AUTH_SERVER')
        self.token_path = os.getenv('TOKEN_PATH')
        self.api_client = ApiClient()
        
        # Create token directory if it doesn't exist
        token_dir = os.path.dirname(self.token_path)
        if token_dir:
            Path(token_dir).mkdir(parents=True, exist_ok=True)

    def get_consent_url(self):
        """Generate the consent URL for DocuSign OAuth"""
        return (
            f"https://{self.auth_server}/oauth/auth"
            f"?response_type=code"
            f"&scope=signature%20impersonation"
            f"&client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
        )

    def get_token_from_code(self, code):
        """Exchange authorization code for access token"""
        url = f"https://{self.auth_server}/oauth/token"
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri
        }
        response = requests.post(url, data=data)
        if response.status_code == 200:
            token_data = response.json()
            self._save_token(token_data)
            return token_data
        else:
            raise Exception(f"Failed to get token: {response.text}")

    def refresh_token(self, refresh_token):
        """Refresh the access token using refresh token"""
        url = f"https://{self.auth_server}/oauth/token"
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        response = requests.post(url, data=data)
        if response.status_code == 200:
            token_data = response.json()
            self._save_token(token_data)
            return token_data
        else:
            raise Exception(f"Failed to refresh token: {response.text}")

    def _save_token(self, token_data):
        """Save token data to file"""
        token_data['timestamp'] = datetime.now().isoformat()
        with open(self.token_path, 'w') as f:
            json.dump(token_data, f)

    def load_token(self):
        """Load token data from file"""
        try:
            with open(self.token_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def is_token_valid(self, token_data):
        """Check if the current token is valid"""
        if not token_data:
            return False
        
        timestamp = datetime.fromisoformat(token_data['timestamp'])
        expires_in = token_data['expires_in']
        expiration_time = timestamp + timedelta(seconds=expires_in)
        
        # Consider token invalid if it expires in less than 5 minutes
        return datetime.now() < (expiration_time - timedelta(minutes=5))

    def delete_token(self):
        """Delete the stored token file"""
        try:
            if os.path.exists(self.token_path):
                os.remove(self.token_path)
                return True
        except Exception:
            pass
        return False
