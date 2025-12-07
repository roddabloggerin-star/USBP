# --- File: src/blogger_api_util.py (CLEANED) ---

import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request # Fixed import

# --- Configuration (Set as environment variables in GitHub Actions) ---
SCOPES = ['https://www.googleapis.com/auth/blogger']
CLIENT_SECRETS_FILE = 'client_secrets.json' 
TOKEN_FILE = 'token.json'
# BLOG_ID is loaded from os.environ in src/main.py, but kept here for fallback
BLOG_ID = '3574255880139843947' 
# --------------------------------------------------------------------

def get_creds():
    """Handles OAuth 2.0 flow to get and refresh credentials for Blogger API."""
    creds = None
    token_path = Path(TOKEN_FILE)

    # 1. Try to load existing credentials
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
    # 2. Refresh token if expired and refreshable
    if creds and creds.expired and creds.refresh_token:
        print("Refreshing expired token...")
        try:
            creds.refresh(Request())
        except Exception as e:
            print(f"Error refreshing token: {e}. Re-running full OAuth flow.")
            creds = None
            
    # 3. No valid credentials found, run the authorization flow
    if not creds or not creds.valid:
        if not Path(CLIENT_SECRETS_FILE).exists():
            print(f"CRITICAL ERROR: {CLIENT_SECRETS_FILE} not found. Please download it from GCP and place it in the project root.")
            return None
            
        print("Running authorization flow. A browser window will open...")
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)  # opens browser for user consent
    
    # 4. Save the updated or new credentials
    if creds:
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    return creds

def create_post(title, content_html, is_draft=False):
    """
    Creates a new post on the Blogger blog.
    :param title: The title of the new post.
    :param content_html: The HTML content of the new post.
    :param is_draft: If True, the post is saved as a draft.
    :return: The API response object for the created post, or None on failure.
    """
    creds = get_creds()
    if not creds:
        print("Failed to get credentials. Cannot create post.")
        return None
        
    try:
        service = build('blogger', 'v3', credentials=creds)
        
        body = {
            'title': title,
            'content': content_html
        }
        
        # Call the API to insert the post, passing isDraft as a query parameter
        post = service.posts().insert(
            blogId=BLOG_ID, 
            body=body, 
            isDraft=is_draft
        ).execute()
        
        return post
    except Exception as e:
        print(f"An error occurred while creating the post: {e}")
        return None

if __name__ == '__main__':