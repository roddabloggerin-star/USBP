# src/api_client.py
import requests
import base64
import json
from typing import Dict, Any, List
from google.auth import service_account
from google.auth.transport.requests import Request

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
        points_response = requests.get(points_url, headers=headers)
        points_response.raise_for_status() 
        forecast_url = points_response.json().get('properties', {}).get('forecastHourly')
        
        if not forecast_url:
            print(f"Error: Could not find hourly forecast URL for {lat_lon}")
            return {}

        # Step 2: Get the Hourly Forecast Data
        forecast_response = requests.get(forecast_url, headers=headers)
        forecast_response.raise_for_status()
        
        return forecast_response.json().get('properties', {})
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching NWS data for {lat_lon}: {e}")
        return {}


def image_to_base64(image_url: str, user_agent: str) -> str:
    """
    Downloads an image from a URL and converts it to a Base64 string (data URI),
    checking for size constraints.
    """
    try:
        # Set a hard limit on individual images to ensure overall post size is manageable
        MAX_IMAGE_SIZE_KB = 500 
        MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_KB * 1024
        
        headers = {'User-Agent': user_agent}
        image_response = requests.get(image_url, headers=headers, stream=True, timeout=10)
        image_response.raise_for_status()
        
        image_content = image_response.content
        
        if len(image_content) > MAX_IMAGE_SIZE_BYTES: 
            print(f"Warning: Image at {image_url} is too large ({len(image_content)/1024:.2f}KB > {MAX_IMAGE_SIZE_KB}KB). Skipping.")
            return ""

        content_type = image_response.headers.get('Content-Type', 'image/png')
        encoded_image = base64.b64encode(image_content).decode('utf-8')
        
        return f"data:{content_type};base64,{encoded_image}"

    except requests.exceptions.RequestException as e:
        print(f"Error downloading or converting image from {image_url}: {e}")
        return ""


def get_blogger_credentials(keyfile_path: str) -> str:
    """
    Generates a valid OAuth 2.0 access token using a Google Service Account key file.
    """
    SCOPES = ['https://www.googleapis.com/auth/blogger']
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            keyfile_path,
            scopes=SCOPES
        )
        credentials.refresh(Request())
        return credentials.token
    
    except Exception as e:
        print(f"Error generating Blogger credentials. Ensure keyfile path is correct and JSON is valid: {e}")
        return ""


def post_to_blogger(blog_id: str, title: str, content_html: str, service_account_key_path: str) -> bool:
    """
    Publishes a new post to Blogger using the V3 API with Service Account authentication.
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
        response = requests.post(post_url, headers=headers, json=post_data)
        response.raise_for_status()
        
        # Check if the response contains the meta description (which it should if the model outputs it)
        # response_data = response.json()
        # print(f"Post URL: {response_data.get('url')}") 
        return True
    
    except requests.exceptions.RequestException as e:
        print(f"Error posting to Blogger: {e}")
        if 'response' in locals():
            try:
                error_details = response.json()
                print(f"Blogger API Error: {error_details.get('error', {}).get('message', 'No message')}")
            except json.JSONDecodeError:
                 print(f"Response Content: {response.text}")
        return False