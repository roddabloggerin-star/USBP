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
    # ... (Existing get_creds logic remains unchanged, it is robust)
    # ...
    # This function is correct.

def create_post(title, content_html, is_draft=False):
    """
    Creates a new post on the Blogger blog.
    
    :param title: The title of the new post.
    :param content_html: The HTML content of the new post.
    :param is_draft: If True, the post is saved as a draft (Default is False in function definition).
    :return: The API response object for the created post, or None on failure.
    """
    # Fetch BLOG_ID from environment variable first, use hardcoded as fallback
    current_blog_id = os.environ.get('BLOG_ID', BLOG_ID)
    
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
        
        # isDraft must be set based on the function argument
        post = service.posts().insert(
            blogId=current_blog_id, 
            body=body, 
            isDraft=is_draft
        ).execute()
        
        return post
    except Exception as e:
        print(f"An error occurred while creating the post: {e}")
        return None

# --- REMOVED THE if __name__ == '__main__': TEST BLOCK ---
# This file is now a pure utility module.