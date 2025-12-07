# blogger_post.py
import json
import base64
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request  # <-- FIX 1: Import Request

# --- Configuration ---
SCOPES = ['https://www.googleapis.com/auth/blogger']
# Use the b64 file from your repo, which will be decoded in the get_creds function
CLIENT_SECRETS_B64 = 'client_secrets.b64'
TOKEN_FILE = 'token.json'
BLOG_ID = '3574255880139843947' # replace with your blog id (or move to a config file)
# --- Configuration ---

def get_creds():
    """Handles OAuth 2.0 flow to get and refresh credentials for Blogger API."""
    creds = None
    token_path = Path(TOKEN_FILE)

    # 1. Try to load existing credentials
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
    # 2. Check if credentials are valid or need refreshing
    if creds and creds.expired and creds.refresh_token:
        # Refresh the token
        creds.refresh(Request())
    elif creds and creds.valid:
        # Credentials are valid, nothing to do
        pass
    else:
        # 3. No valid credentials found, run the authorization flow
        # FIX 2: Handle the Base64-encoded client secrets file (if used)
        if Path(CLIENT_SECRETS_B64).exists():
            print(f"Decoding {CLIENT_SECRETS_B64} for authentication...")
            with open(CLIENT_SECRETS_B64, 'rb') as f:
                decoded_secrets = base64.b64decode(f.read())
            
            # Use a temporary file path for the flow to read the JSON
            temp_json_path = "temp_client_secrets.json"
            with open(temp_json_path, 'wb') as f:
                f.write(decoded_secrets)
            
            flow = InstalledAppFlow.from_client_secrets_file(temp_json_path, SCOPES)
            Path(temp_json_path).unlink() # Clean up the temporary file
        else:
            # Fallback for a standard client_secret.json
            print("Running authorization flow with standard client_secret.json...")
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)


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
    :return: The API response object for the created post.
    """
    creds = get_creds()
    # Note: build is an expensive operation; consider initializing 'service' once if
    # this function is called repeatedly.
    service = build('blogger', 'v3', credentials=creds)
    
    # The request body containing the post details
    body = {
        'title': title,
        'content': content_html
    }
    
    # Call the API to insert the post, passing isDraft as a query parameter
    # FIX 3: Confirming correct parameter name (isDraft)
    post = service.posts().insert(
        blogId=BLOG_ID, 
        body=body, 
        isDraft=is_draft
    ).execute()
    
    return post

if __name__ == '__main__':
    print("--- Running Blogger Post Test ---")
    
    # Example: Create a draft post
    post = create_post(
        title="Test from script (Draft)", 
        content_html="<p>This is a test post created using the revised Python script.</p>", 
        is_draft=false
    )
    
    print(f"Successfully created post (Draft): {post.get('id')}")
    print(f"View on Blogger: {post.get('url')}")