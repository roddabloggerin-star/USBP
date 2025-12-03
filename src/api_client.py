# src/api_client.py (FINAL VERSION for OAuth 2.0 and API Key Fix)
import requests
import base64
import json
import os
from typing import Dict, Any, List
from google.auth.transport.requests import Request
from urllib.parse import urlparse
from time import sleep

# --- NEW OAUTH IMPORTS ---
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
# --- END NEW OAUTH IMPORTS ---

# Max post size in bytes (5MB)
MAX_POST_SIZE_BYTES = 5 * 1024 * 1024

# Blogger API Scopes (Full read/write access is required for publishing)
BLOGGER_SCOPES = ['https://www.googleapis.com/auth/blogger']
# File where the authorized access/refresh token is stored (in the project root)
TOKEN_FILE = 'token.json' 

# --- OAuth 2.0 Credential Functions ---

def get_oauth_credentials(client_secret_path: str) -> str | None:
    """
    Handles the OAuth 2.0 flow: loads existing token, refreshes it, or starts a new interactive user authorization.
    Returns the raw access token string.
    """
    creds = None
    
    # 1. Try to load the token from token.json
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, BLOGGER_SCOPES)
        except Exception as e:
             print(f"Error loading credentials from {TOKEN_FILE}: {e}. Will attempt re-authorization.")
    
    # 2. Check if credentials are valid/refreshable
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh the token non-interactively if possible
            print("Refreshing expired OAuth token...")
            creds.refresh(Request())
        else:
            # 3. Start the interactive authorization flow (ONLY RUNS LOCALLY THE FIRST TIME)
            print(f"\n--- Starting OAuth 2.0 Authorization Flow ---")
            print(f"Please follow the link in your browser to grant permission.")
            
            # This line will launch the local web server and open the browser
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_path, BLOGGER_SCOPES)
            
            # port=0 allows the OS to pick a free port for the local web server
            creds = flow.run_local_server(port=0) 
            
            print("Authorization successful.")
            
        # 4. Save the new or refreshed credentials
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        print(f"Credentials saved/updated in {TOKEN_FILE}.")

    if creds and creds.token:
        return creds.token
    
    return None

def list_accessible_blogs(client_secret_path: str) -> bool:
    """
    Tests the connection by listing accessible blogs using OAuth credentials.
    This also forces the initial authorization/token refresh.
    """
    access_token = get_oauth_credentials(client_secret_path)
    if not access_token:
        print("Fatal: Failed to obtain Blogger access token.")
        return False
        
    list_url = 'https://www.googleapis.com/blogger/v3/users/self/blogs'
    # NOTE: No API key needed here because the OAuth Bearer token is used for user authentication
    headers = {"Authorization": f"Bearer {access_token}"} 
    
    try:
        response = requests.get(list_url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        blogs = data.get('items', [])
        
        print(f"Successfully connected! Retrieved {len(blogs)} blog(s).")
        if blogs:
            print("Visible blogs:")
            for blog in blogs:
                print(f"  - ID: {blog.get('id')} | Name: {blog.get('name')}")
            return True
        else:
            print("Service is authorized but sees no blogs.")
            return True # Still authorized, just no content
            
    except requests.exceptions.RequestException as e:
        print(f"Error listing accessible blogs: {e}")
        if 'response' in locals() and response.status_code == 403:
             print("Error: 403 Forbidden. Check Blogger API is enabled for your project and scopes were granted.")
        return False
        
# --- NWS and Image Functions ---

def get_nws_forecast(lat_lon: str, user_agent: str) -> Dict[str, Any]:
    """
    Fetches the detailed weather forecast for a given lat/lon pair from the NWS API.
    
    This replaces the previous call structure that required grid_id/x/y by resolving 
    the forecast URL directly from the /points endpoint using only lat/lon.
    """
    try:
        # Step 1: Get the Grid Endpoint URL
        points_url = f"https://api.weather.gov/points/{lat_lon}"
        headers = {'User-Agent': user_agent, 'Accept': 'application/json'}
        points_response = requests.get(points_url, headers=headers, timeout=15)
        points_response.raise_for_status() 
        
        # The forecastHourly URL is within properties
        forecast_url = points_response.json().get('properties', {}).get('forecastHourly')
        
        if not forecast_url:
            print(f"Error: Could not find hourly forecast URL for {lat_lon}")
            return {}

        # Step 2: Get the Hourly Forecast Data
        forecast_response = requests.get(forecast_url, headers=headers, timeout=15)
        forecast_response.raise_for_status()
        
        # We only return the 'properties' part which contains the forecast periods
        return forecast_response.json().get('properties', {})

    except requests.exceptions.RequestException as e:
        print(f"Error fetching NWS data for {lat_lon}: {e}")
        return {}

def image_to_base64(image_path: str) -> str | None:
    """
    Converts a local image file to a Base64 string for embedding in a blog post.
    NOTE: The function name here is image_to_base64.
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except IOError as e:
        print(f"Error reading image file {image_path}: {e}")
        return None

# --- MODIFIED: post_to_blogger function (API Key Fix) ---

def post_to_blogger(
    blog_id: str,
    title: str,
    content_html: str,
    client_secret_path: str
) -> bool:
    """
    Posts content to the specified Blogger blog using OAuth 2.0 credentials.
    No API key required when using a user access token.
    """
    access_token = get_oauth_credentials(client_secret_path)
    if not access_token:
        print("Failed to obtain Blogger access token.")
        return False

    # Pure OAuth endpoint: no ?key=... needed
    post_url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    post_data = {
        "kind": "blogger#post",
        "blog": {"id": blog_id},
        "title": title,
        "content": content_html,
        "labels": ["Weather Forecast", "USA", "NationalWeatherService"],
    }

    try:
        sleep(1)  # avoid hammering the API
        response = requests.post(post_url, headers=headers, json=post_data)
        response.raise_for_status()
        print("Post successful.")
        return True

    except requests.exceptions.RequestException as e:
        print(f"Error posting to Blogger: {e}")
        if 'response' in locals():
            try:
                error_details = response.json()
                # Log full error for debugging, not just message
                print("Full Blogger API error:", json.dumps(error_details, indent=2))
            except Exception:
                pass
        return False
