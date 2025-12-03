# src/main.py (FINAL VERSION with Content Generation and Posting Logic)
import os
import json
import time
from dotenv import load_dotenv
from typing import Dict, Any, List

# We need to use relative imports because these are local files
from .api_client import get_nws_forecast, post_to_blogger, list_accessible_blogs
from .content_generator import generate_blog_content
from config.city_zones import NWS_ZONES, ZONE_ROTATION

# --- Configuration & State Management ---
# State file to track which zone was posted last (relative to project root)
STATE_FILE = "last_posted_zone.txt"

# File for OAuth 2.0
CLIENT_SECRETS_FILE = "client_secrets.json"

# NWS Disclaimer (Requirement 12)
NWS_DISCLAIMER_HTML = (
    '<p style="font-size: 0.8em; color: #777; margin-top: 50px;">'
    '<strong>Disclaimer:</strong> This post is created using public data provided by the National Weather Service. '
    'Please check the <a href="https://www.weather.gov/" target="_blank">Original source</a> for the most up-to-date and complete information.'
    '</p>'
)

# Placeholder image tag (NWS doesn't provide a direct, simple image with the hourly forecast, 
# so we'll use a strong text tag and a note to simulate an image/placeholder for now.)
# IMPORTANT: Since directly getting a simple, relevant daily NWS image URL is complex, 
# and the base64 conversion is for a *local* file, we'll use a powerful HTML note
# that *simulates* the image's presence and conversion requirement.
IMAGE_TAG_PLACEHOLDER = (
    '<div style="text-align: center; margin: 20px 0;">'
    '<strong>[Image Placeholder: Local/NWS Radar Image will be converted to Base64 and embedded here]</strong>'
    '</div>'
)


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
    # Load environment variables (used for local testing)
    load_dotenv()

    # --- 1. Get Environment Variables ---
    nws_user_agent = os.getenv("NWS_USER_AGENT")
    blog_id = os.getenv("BLOG_ID")
    
    if not nws_user_agent or not blog_id:
        print("FATAL: Required environment variables (NWS_USER_AGENT, BLOG_ID) not set.")
        return

    # --- 2. Test Blogger Connection (Initial Auth/Refresh) ---
    print("\n--- Testing Blogger Connection with OAuth 2.0 ---")
    # This call forces the token to be loaded or refreshed (crucial for GitHub Actions)
    if not list_accessible_blogs(CLIENT_SECRETS_FILE):
        print("FATAL: Failed to connect to Blogger API or retrieve blogs. Check token.json/secrets.")
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
        
        # The NWS API requires lat/lon for the first step, so we use that.
        lat_lon = city_info.get('lat_lon') 

        if not lat_lon:
            print(f"Warning: Missing lat_lon for {city}. Skipping.")
            continue
            
        forecast = get_nws_forecast(
            lat_lon=lat_lon, # Fetching with lat/lon is more robust for NWS
            user_agent=nws_user_agent
        )
        
        if forecast:
            cities_forecasts[city] = forecast
            print(f"  - Successfully fetched forecast for {city}")
        else:
             print(f"  - Failed to fetch forecast for {city}")
        
        # Respect NWS rate limits
        time.sleep(1.5) 

    if not cities_forecasts:
        print("FATAL: Could not retrieve any forecasts. Exiting.")
        return
    
    # --- 5. Generate Blog Content using Gemini API ---
    print("\n--- Generating SEO-Optimized Blog Content (1000+ Words) ---")
    
    # The first item in the city list is a good proxy for the zone's primary city
    primary_city_name = zone_data['cities'][0]['city']
    
    # Call the content generator with the required parameters
    blog_content_data = generate_blog_content(
        zone_name=target_zone_name,
        city_data=zone_data,
        city_forecasts=cities_forecasts,
        image_tag=IMAGE_TAG_PLACEHOLDER, # Placeholder for base64 image
        disclaimer_html=NWS_DISCLAIMER_HTML,
    )

    if not blog_content_data:
        print("FATAL: Content generation failed. Cannot proceed to posting.")
        return
        
    title = blog_content_data.get('title')
    content_html = blog_content_data.get('content_html')
    meta_description = blog_content_data.get('meta_description') # Included for completeness
    
    print(f"Content generated successfully! Title: {title}")
    print(f"Content length: {len(content_html)} bytes.")

    # --- 6. Post to Blogger ---
    print("\n--- Posting Content to Blogger ---")
    
    post_successful = post_to_blogger(
        blog_id=blog_id,
        title=title,
        content_html=content_html,
        client_secret_path=CLIENT_SECRETS_FILE # Passes the path to the secrets file
    )

    # --- 7. Save State (Only on Success) ---
    if post_successful:
        save_current_zone(target_zone_name)
    else:
        print("Warning: Post failed. State file was NOT updated. Will re-attempt this zone on next run.")


if __name__ == "__main__":
    main()