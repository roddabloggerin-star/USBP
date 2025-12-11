# blogger_post.py
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/blogger']
CLIENT_SECRETS_FILE = 'client_secret.json'   # downloaded from GCP
TOKEN_FILE = 'token.json'
BLOG_ID = '3574255880139843947'  # replace with your blog id

def get_creds():
    token_path = Path(TOKEN_FILE)
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, 'w') as f:
                f.write(creds.to_json())
            return creds
    # run local server flow to get new credentials
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)  # opens browser for user consent
    with open(TOKEN_FILE, 'w') as f:
        f.write(creds.to_json())
    return creds

def create_post(title, content_html, is_draft=False):
    creds = get_creds()
    service = build('blogger', 'v3', credentials=creds)
    body = {
        'title': title,
        'content': content_html
    }
    post = service.posts().insert(blogId=BLOG_ID, body=body, isDraft=is_draft).execute()
    return post

if __name__ == '__main__':
    # simple test
    post = create_post("Test from script", "<p>This is a test post.</p>", is_draft=True)
    print("Created post id:", post.get('id'))
