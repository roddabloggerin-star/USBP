# src/api_client.py (FINAL VERSION for OAuth 2.0 and Blogger posting via requests)

import requests
import base64
import json
import os
from typing import Dict, Any
from google.auth.transport.requests import Request
from time import sleep
from typing import Optional, List

# --- NEW OAUTH IMPORTS ---
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
# --- END NEW OAUTH IMPORTS ---

# at top of src/api_client.py, after other imports
BLOGGER_API_KEY = os.getenv("BLOGGER_API_KEY")
if not BLOGGER_API_KEY:
    print("FATAL: BLOGGER_API_KEY environment variable not set. Check your .env file.")
    raise SystemExit(1)
# ========== BLOGGER API CONFIGURATION ==========

# Base URL for the Blogger API  

BLOGGER_API_BASE_URL = "https://www.googleapis.com/blogger/v3"

# Blogger API Scopes (full read/write access is required for publishing)
BLOGGER_SCOPES = ["https://www.googleapis.com/auth/blogger"]

# File where the authorized access/refresh token is stored (project root)
TOKEN_FILE = "token.json"


# ========== OAUTH 2.0 CREDENTIALS ==========

def get_oauth_credentials(client_secret_path: str) -> str | None:
    """
    Handles the OAuth 2.0 flow: loads existing token, refreshes it, or starts a new
    interactive user authorization. Returns the raw access token string.
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
            print("Refreshing expired OAuth token...")
            creds.refresh(Request())
        else:
            # 3. Start the interactive authorization flow (only runs locally the first time)
            print("\n--- Starting OAuth 2.0 Authorization Flow ---")
            print("Please follow the link in your browser to grant permission.")

            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_path,
                BLOGGER_SCOPES,
            )
            creds = flow.run_local_server(port=0)

            print("Authorization successful.")

        # 4. Save the new or refreshed credentials
        with open(TOKEN_FILE, "w") as token:
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

    list_url = "https://www.googleapis.com/blogger/v3/users/self/blogs"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(list_url, headers=headers)
        response.raise_for_status()

        data = response.json()
        blogs = data.get("items", [])

        print(f"Successfully connected! Retrieved {len(blogs)} blog(s).")
        if blogs:
            print("Visible blogs:")
            for blog in blogs:
                print(f"  - ID: {blog.get('id')} | Name: {blog.get('name')}")
            return True
        else:
            print("Service is authorized but sees no blogs.")
            return True  # Still authorized, just no content

    except requests.exceptions.RequestException as e:
        print(f"Error listing accessible blogs: {e}")
        if "response" in locals() and response.status_code == 403:
            print("Error: 403 Forbidden. Check Blogger API is enabled for your project and scopes were granted.")
        return False


# ========== NWS + IMAGE HELPERS ==========

def get_nws_forecast(lat_lon: str, user_agent: str) -> Dict[str, Any]:
    """
    Fetches the detailed weather forecast for a given lat/lon pair from the NWS API.

    We resolve the hourly forecast URL from /points and return the 'properties'
    object which contains the 'periods' array.
    """
    try:
        # Step 1: Get the grid endpoint URL
        points_url = f"https://api.weather.gov/points/{lat_lon}"
        headers = {"User-Agent": user_agent, "Accept": "application/json"}
        points_response = requests.get(points_url, headers=headers, timeout=15)
        points_response.raise_for_status()

        forecast_url = points_response.json().get("properties", {}).get("forecastHourly")
        if not forecast_url:
            print(f"Error: Could not find hourly forecast URL for {lat_lon}")
            return {}

        # Step 2: Fetch hourly forecast
        forecast_response = requests.get(forecast_url, headers=headers, timeout=15)
        forecast_response.raise_for_status()

        return forecast_response.json().get("properties", {})

    except requests.exceptions.RequestException as e:
        print(f"Error fetching NWS data for {lat_lon}: {e}")
        return {}


def image_to_base64(image_path: str) -> str | None:
    """
    Converts a local image file to a Base64 string for embedding in a blog post.
    Only used if you ever go back to inline base64 images.
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except IOError as e:
        print(f"Error reading image file {image_path}: {e}")
        return None


# ========== BLOGGER POSTING ==========

def post_to_blogger(
    blog_id: str,
    title: str,
    content_html: str,
    client_secret_path: str,
    labels: Optional[List[str]] = None,
) -> bool:
    """
    Posts content to the specified Blogger blog using OAuth 2.0 credentials.
    Uses the REST API directly via requests.
    """
    access_token = get_oauth_credentials(client_secret_path)
    if not access_token:
        print("Failed to obtain Blogger access token.")
        return False

    base_url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    if labels is None or not labels:
        labels = ["Weather Forecast", "USA", "NationalWeatherService"]

    post_data = {
        "kind": "blogger#post",
        "blog": {"id": blog_id},
        "title": title,
        "content": content_html,
        "labels": labels,
    }

    try:
        sleep(1)  # avoid hammering the API
        response = requests.post(base_url, headers=headers, json=post_data)
        response.raise_for_status()
        print("Post successful.")
        return True

    except requests.exceptions.RequestException as e:
        print(f"Error posting to Blogger: {e}")
        try:
            error_details = response.json()
            print("Full Blogger API error:", json.dumps(error_details, indent=2))
        except Exception:
            pass
        return False

# -------------------------------------------------------------------
# NOAAApiClient: wrapper around NWS and simple geocoding to support main.py
# -------------------------------------------------------------------

class NOAAApiClient:
    """
    NOAAApiClient compatible with main.py:
     - fetch_weather_for_location(location_str)
     - returns a dict of city names with
       forecast_hourly, current_conditions (empty), alerts (empty)
    """

    def __init__(self, user_agent: str | None = None):
        """
        user_agent for NWS requests must be set (required by weather.gov)
        If not provided, uses environment variable NWS_USER_AGENT
        """
        self.user_agent = user_agent or os.getenv("NWS_USER_AGENT")
        if not self.user_agent:
            raise ValueError(
                "Must set NWS_USER_AGENT environment variable for NWS API"
            )

    def _geocode_location(self, location: str) -> tuple[float, float] | None:
        """
        Simple geocoding via OpenStreetMap Nominatim free API.
        Returns (lat, lon) or None on failure.
        Note: Nominatim free API usage must not be abused (rate limits apply).
        """
        geocode_url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": location,
            "format": "json",
            "limit": 1
        }
        try:
            resp = requests.get(geocode_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return None
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            return lat, lon
        except Exception as e:
            print(f"Geocoding failed for '{location}': {e}")
            return None

    def fetch_weather_for_location(self, location: str) -> dict[str, dict]:"""
    Given a location search string (e.g. "New York, NY"),
    this method returns a dict with a single key
    referring to the location and the NWS forecast data.

    For broad national requests like "United States" or "USA",
    use a fixed lat/lon to avoid geocoding errors.
    """
    # Recognize common broad national terms
    fallback_national = [
        "united states",
        "usa",
        "us national",
        "national forecast",
        "united states national forecast",
    ]

    loc_lower = location.strip().lower()
    if loc_lower in fallback_national:
        # Geographic center of the contiguous United States
        lat, lon = (39.8283, -98.5795)
    else:
        geocoded = self._geocode_location(location)
        if not geocoded:
            print(f"Could not geocode location: {location}")
            return {}
        lat, lon = geocoded

    latlon_str = f"{lat},{lon}"

    # Fetch NWS hourly forecast
    hourly_props = get_nws_forecast(latlon_str, self.user_agent)

    result = {
        location: {
            "forecast_hourly": hourly_props or {},
            "current_conditions": {},
            "alerts": []
        }
    }
    return result
