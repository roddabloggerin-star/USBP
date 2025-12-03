# src/api_client.py (CLEANED & FIXED)
import requests
import base64
import json
from typing import Dict, Any, List
# CRITICAL FIX: service_account lives under google.oauth2
from google.oauth2 import service_account 
from google.auth.transport.requests import Request
from urllib.parse import urlparse
from time import sleep

# Max post size in bytes (5MB) - used for internal tracking
MAX_POST_SIZE_BYTES = 5 * 1024 * 1024

def get_nws_forecast(lat_lon: str, user_agent: str) -> Dict[str, Any]:
    """
    Fetches the detailed weather forecast for a given lat/lon pair from the NWS API.
    """
    try:
        # Step 1: Get the Grid Endpoint URL
        points_url = f"https://api.weather.gov/points/{lat_lon}"
        headers = {'User-Agent': user_agent, 'Accept': 'application/json'}
        points_response = requests.get(points_url, headers=headers, timeout=15)
        points_response.raise_for_status() 
        forecast_url = points_response.json().get('properties', {}).get('forecastHourly')
        
        if not forecast_url:
            print(f"Error: Could not find hourly forecast URL for {lat_lon}")
            return {}

        # Step 2: Get the Hourly Forecast Data
        forecast_response = requests.get(forecast_url, headers=headers, timeout=15)
        forecast_response.raise_for_status()
        
        return forecast_response.json().get('properties', {})
        
    except requests.exceptions.HTTPError as e:
        print(f"NWS API HTTP Error: {e.response.status_code} for {lat_lon}. Details: {e.response.text}")
        return {}
    except requests.exceptions.RequestException as e:
        print(f"NWS API Request Error for {lat_lon}: {e}")
        return {}


def image_to_base64(image_url: str, user_agent: str) -> str | None:
    """
    Downloads an image from a URL, encodes it as base64, and returns the string.
    """
    if not urlparse(image_url).scheme in ('http', 'https'):
        print(f"Invalid URL scheme: {image_url}")
        return None
        
    try:
        headers = {'User-Agent': user_agent}
        # Use a timeout for the image download
        response = requests.get(image_url, headers=headers, stream=True, timeout=30) 
        response.raise_for_status()
        
        # Read the image data and encode it
        image_data = response.content
        return base64.b64encode(image_data).decode('utf-8')

    except requests.exceptions.RequestException as e:
        print(f"Error fetching image from {image_url}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during image processing: {e}")
        return None


def get_blogger_credentials(service_account_key_path: str) -> str | None:
    """
    Authenticates with Google Blogger using a Service Account Key file.
    Returns the access token if successful.
    """
    try:
        # Define the scope required for Blogger API (Read/Write)
        SCOPES = ["https://www.googleapis.com/auth/blogger"]
        
        # Load the credentials from the key file
        credentials = service_account.Credentials.from_service_account_file(
            service_account_key_path,
            scopes=SCOPES
        )
        
        # Refresh the credentials to get an access token
        credentials.refresh(Request())
        
        return credentials.token

    except Exception as e:
        print(f"Authentication Error: {e}")
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
                print(f"Blogger Error Details: {error_details}")
            except json.JSONDecodeError:
                print(f"Blogger Error Response Text: {response.text}")
        return False