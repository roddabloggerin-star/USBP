# src/main.py (FINAL VERSION with Retry Mechanism)
import os
import json
import time # <-- NEW: Added for time.sleep()
from dotenv import load_dotenv
from typing import Dict, Any, List

# NEW: Import the specific exception from the Google SDK
from google.genai.errors import ResourceExhaustedError # <-- NEW

# We need to use relative imports because these are local files
from .api_client import get_nws_forecast, image_to_base64, post_to_blogger, list_accessible_blogs
from .content_generator import generate_blog_content
from config.city_zones import NWS_ZONES, ZONE_ROTATION

# --- Configuration & State Management ---
# State file to track which zone was posted last (relative to project root)
STATE_FILE = "last_posted_zone.txt"

# NEW: File for OAuth 2.0
CLIENT_SECRETS_FILE = "client_secrets.json"


def get_next_zone() -> str:
    """Reads the last zone posted and determines the next zone for rotation."""
    last_zone = ""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                last_zone = f.read().strip()
        except IOError:
            print("Warning: Could not read state file. Starting rotation from beginning.")
            last_zone = ""
            
    try:
        current_index = ZONE_ROTATION.index(last_zone)
        next_index = (current_index + 1) % len(ZONE_ROTATION)
        return ZONE_ROTATION[next_index]
    except ValueError:
        # If last_zone is not in ZONE_ROTATION or is empty/invalid, start at the beginning
        return ZONE_ROTATION[0]

def save_current_zone(zone_name: str):
    """Saves the name of the successfully posted zone to the state file."""
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(zone_name)
        print(f"State updated: '{zone_name}' saved to {STATE_FILE}.")
    except IOError as e:
        print(f"FATAL: Could not save state file {STATE_FILE}. Error: {e}")


def main():
    # Load environment variables (used for local testing, but still good practice)
    # In GitHub Actions, secrets are passed via the 'env' block.
    load_dotenv()

    # --- 1. Get Environment Variables ---
    nws_user_agent = os.getenv("NWS_USER_AGENT")
    blog_id = os.getenv("BLOG_ID")
    
    if not nws_user_agent or not blog_id:
        print("FATAL: Required environment variables (NWS_USER_AGENT, BLOG_ID) not set.")
        return

    # --- 2. Test Blogger Connection (Optional but Recommended) ---
    print("\n--- Testing Blogger Connection with OAuth 2.0 ---")
    blogs = list_accessible_blogs(CLIENT_SECRETS_FILE)
    if blogs is None:
        print("FATAL: Failed to connect to Blogger API or retrieve blogs.")
        return

    # --- 3. Determine Target Zone ---
    target_zone_name = get_next_zone()
    if target_zone_name not in NWS_ZONES:
        print(f"FATAL: Target zone '{target_zone_name}' not found in NWS_ZONES configuration.")
        return

    print(f"\nTargeting next zone: {target_zone_name}")
    zone_data = NWS_ZONES[target_zone_name]
    
    # --- 4. Fetch Weather Data ---
    cities_forecasts = {}
    print("Fetching NWS forecasts...")
    
    for city_info in zone_data['cities']:
        city = city_info['city']
        grid_id = city_info.get('grid_id')
        grid_x = city_info.get('grid_x')
        grid_y = city_info.get('grid_y')
        
        if not all([grid_id, grid_x, grid_y]):
            print(f"Warning: Missing NWS grid data for {city}. Skipping.")
            continue
            
        forecast = get_nws_forecast(
            grid_id=grid_id, 
            grid_x=grid_x, 
            grid_y=grid_y, 
            user_agent=nws_user_agent
        )
        
        if forecast:
            cities_forecasts[city] = forecast
        
        # Respect NWS rate limits
        time.sleep(1) 

    if not cities_forecasts:
        print("FATAL: Could not retrieve any forecasts. Exiting.")
        return
    
    