# src/main.py (FINAL VERSION with all fixes applied)
import os
import json
import time
from dotenv import load_dotenv
from typing import Dict, Any, List

# We need to use relative imports because these are local files
from .api_client import (
    # FIX 1: Import the correct function name: get_nws_forecast
    get_nws_forecast, 
    # FIX 2: Import the correct image function name: image_to_base64
    image_to_base64, 
    post_to_blogger, 
    list_accessible_blogs
)
from .content_generator import generate_blog_content
# NOTE: Assuming city_zones.py is in a config/ folder relative to the project root
from config.city_zones import NWS_ZONES, ZONE_ROTATION


# --- Configuration & State Management ---
# State file to track which zone was posted last (relative to project root)
STATE_FILE = "last_posted_zone.txt"

# File for OAuth 2.0
CLIENT_SECRETS_FILE = "client_secrets.json"

# Image and Disclaimer (assuming you have a 'placeholder.png' in the root)
IMAGE_PATH = "placeholder.png" 
DISCLAIMER_HTML = (
    "<p style=\"font-size: 0.8em; color: #888;\">"
    "Disclaimer: Forecast data is sourced from the National Weather Service (NWS) and is subject to change. "
    "This bot processes NWS data for aggregation and is not responsible for forecast accuracy."
    "</p>"
)


# --- CRITICAL FIX: Load .env and define NWS_USER_AGENT and BLOG_ID ---
# 1. Load environment variables from .env
load_dotenv() 

# 2. Define required variables from environment
NWS_USER_AGENT = os.getenv("NWS_USER_AGENT")
BLOG_ID = os.getenv("BLOG_ID")

# Safety check for required variables
if not all([NWS_USER_AGENT, BLOG_ID]):
    print("FATAL: NWS_USER_AGENT or BLOG_ID environment variable not set. Check your .env file.")
    # We must exit if critical variables are missing
    exit(1)
# --- END CRITICAL FIX ---


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
        # If last_zone is not in rotation (e.g., first run or invalid state)
        return ZONE_ROTATION[0]

def update_last_zone(zone_name: str) -> None:
    """Writes the name of the last successfully processed zone to the state file."""
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(zone_name)
        print(f"State updated: Next run will target the zone after '{zone_name}'.")
    except IOError:
        print(f"FATAL: Could not write to state file {STATE_FILE}. Rotation tracking failed.")

def create_image_tag(image_base64: str, zone_name: str) -> str:
    """
    Creates an HTML <img> tag with a Base64 encoded image for embedding.
    This avoids needing to upload the image separately.
    """
    # Create the data URI for the image
    image_uri = f"data:image/png;base64,{image_base64}"
    
    # Create the HTML img tag
    return (
        f'<p style="text-align: center;"><img '
        f'src="{image_uri}" '
        f'alt="Weather forecast visualization for the {zone_name}." '
        f'style="max-width: 100%; height: auto; border: 1px solid #ccc; border-radius: 5px;">'
        f'</p>'
    )


def main():
    """Main function to orchestrate the weather bot."""
    
    print("--- Starting Weather Blog Bot ---")
    
    # --- 1. Load Environment Variables (Done at the top) ---
    # --- 2. Test Blogger Connection with OAuth 2.0 ---
    print("\n--- Testing Blogger Connection with OAuth 2.0 ---")
    # list_accessible_blogs handles the interactive token refresh/creation
    if not list_accessible_blogs(CLIENT_SECRETS_FILE):
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
    print("Fetching NWS hourly forecasts (this may take a moment due to rate limiting)...")
    
    for city_info in zone_data['cities']:
        city = city_info['city']
        lat_lon = city_info.get('lat_lon')
        
        # We now only rely on lat_lon since api_client handles grid resolution
        if not lat_lon:
            print(f"Warning: Missing lat_lon for {city}. Skipping.")
            continue
            
        # FIX 3: Call get_nws_forecast with the correct arguments (lat_lon and user_agent)
        forecast = get_nws_forecast(
            lat_lon=lat_lon, 
            user_agent=NWS_USER_AGENT
        )
        
        if forecast:
            cities_forecasts[city] = forecast
        else:
            print(f"Warning: Failed to retrieve forecast for {city}. Skipping.")
            
        # NWS rate limit: 1 request per second is conservative, we use a 1.5s pause
        time.sleep(1.5) 

    if not cities_forecasts:
        print("FATAL: No weather data was successfully retrieved. Aborting post.")
        return

    # --- 5. Create HTML Image Tag ---
    print(f"--- Creating Placeholder Image Tag for {target_zone_name} ---")
    image_tag = ""
    try:
        # The function in api_client.py is named image_to_base64
        image_base64 = image_to_base64(IMAGE_PATH) 
        
        if image_base64 is None:
            print("FATAL: Failed to read image file. Cannot proceed.")
            # Do not return, instead set image_tag to empty and continue posting
            # to avoid losing the post content, but log the error.
            image_tag = "" 
        else:
            image_tag = create_image_tag(
                image_base64=image_base64, 
                zone_name=target_zone_name
            )
    except Exception as e:
        # Catch unexpected errors during image processing
        print(f"WARNING: Image embedding failed with error: {e}. Posting without image.")
        image_tag = "" # Ensure it's empty string for the content generator

    # --- 6. Generating Blog Content ---
    print("\n--- Generating SEO-Optimized Blog Content (1000+ Words) ---")
    
    # Pass the comprehensive data structure to the generator
    blog_content_data = generate_blog_content(
        zone_name=target_zone_name,
        city_data=zone_data,
        city_forecasts=cities_forecasts,
        image_tag=image_tag,
        disclaimer_html=DISCLAIMER_HTML,
    )

    if blog_content_data is None:
        print("FATAL: Content generation failed. Cannot proceed to posting.")
        return

    title = blog_content_data.get('title', f"Weather Update for {target_zone_name}")
    content_html = blog_content_data.get('content_html', '')

    # --- 7. Post to Blogger ---
    print(f"\n--- Posting to Blogger: '{title}' ---")

    post_success = post_to_blogger(
        blog_id=BLOG_ID,
        title=title,
        content_html=content_html,
        client_secret_path=CLIENT_SECRETS_FILE
    )

    if post_success:
        print(f"SUCCESS: Post for {target_zone_name} published.")
        update_last_zone(target_zone_name)
    else:
        print(f"FAILURE: Post for {target_zone_name} failed. State not updated.")

if __name__ == "__main__":
    main()