# src/api_client.py (CLEANED & FIXED)
import requests
import base64
import json
from typing import Dict, Any, List
# CRITICAL FIX: service_account lives under google.oauth2
from google.oauth2 import service_account 
from google.auth.transport.requests import Request
# REMOVED: from urllib.parse import urlparse 
from time import sleep

# Max post size in bytes (5MB) - used for internal tracking
MAX_POST_SIZE_BYTES = 5 * 1024 * 1024

def get_nws_forecast(lat_lon: str, user_agent: str) -> Dict[str, Any]:
    """
    Fetches the detailed weather forecast for a given lat/lon pair from the NWS API.
    """
    # A generous timeout is used to accommodate slower NWS responses
    TIMEOUT_SECONDS = 30 
    
    try:
        # Step 1: Get the Grid Endpoint URL
        points_url = f"https://api.weather.gov/points/{lat_lon}"
        # Using 'application/json' or 'application/geo+json' is appropriate here
        headers = {'User-Agent': user_agent, 'Accept': 'application/json'}
        points_response = requests.get(points_url, headers=headers, timeout=TIMEOUT_SECONDS)
        points_response.raise_for_status() 
        
        # The 'forecastHourly' link is typically in the properties
        forecast_url = points_response.json().get('properties', {}).get('forecastHourly')
        
        if not forecast_url:
            print(f"Error: Could not find hourly forecast URL for {lat_lon}")
            return {}

        # Step 2: Get the Hourly Forecast Data
        # Re-use the same user_agent and headers
        forecast_response = requests.get(forecast_url, headers=headers, timeout=TIMEOUT_SECONDS)
        forecast_response.raise_for_status()
        
        return forecast_response.json().get('properties', {})

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error fetching NWS forecast for {lat_lon}: {e}")
        return {}
    except requests.exceptions.RequestException as e:
        print(f"Request Error fetching NWS forecast for {lat_lon}: {e}")
        return {}

def image_to_base64(image_path: str) -> str | None:
    """Reads a local image and converts it to a Base64 string."""
    try:
        with open(image_path, "rb") as image_file:
            # Encode the file content
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return encoded_string
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return None
    except IOError as e:
        print(f"Error reading image file: {e}")
        return None

# --- Blogger API Integration ---
# Required scopes for posting to a Blogger blog
BLOGGER_SCOPES = ["https://www.googleapis.com/auth/blogger"]

def get_blogger_credentials(service_account_key_path: str) -> str | None:
    """
    Authenticates using the service account and returns an access token.
    """
    try:
        # Load the credentials from the service account key file
        credentials = service_account.Credentials.from_service_account_file(
            service_account_key_path,
            scopes=BLOGGER_SCOPES
        )
        
        # Refresh the credentials to obtain a new access token
        credentials.refresh(Request())
        
        if credentials.token:
            return credentials.token
        
        print("Error: Credentials refresh failed to produce a token.")
        return None

    except Exception as e:
        print(f"Error during Blogger service account authentication: {e}")
        return None

def post_to_blogger(
    blog_id: str,
    title: str,
    content_html: str,
    service_account_key_path: str
) -> bool:
    """
    Posts content to the specified Blogger blog.
    """
    access_token = get_blogger_credentials(service_account_key_path)
    if not access_token:
        print("Failed to obtain Blogger access token.")
        return False
        
    post_url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    post_data = {
        "kind": "blogger#post",
        "blog": {"id": blog_id},
        "title": title,
        "content": content_html,
        "labels": ["Weather Forecast", "USA", "NationalWeatherService"], 
        "isDraft": False # Set to True for testing, False for live publishing
    }
    
    try:
        # Wait a moment to respect API rate limits
        sleep(1) 
        response = requests.post(post_url, headers=headers, json=post_data)
        response.raise_for_status()
        
        print("Post successful.")
        return True
    
    except requests.exceptions.RequestException as e:
        print(f"Error posting to Blogger: {e}")
        if 'response' in locals():
            try:
                error_details = response.json()
                print(f"Blogger API Error Details: {error_details.get('error', {}).get('message')}")
            except:
                print("Could not parse error response from Blogger API.")
        return False