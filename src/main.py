# src/main.py (FINAL VERSION for OAuth 2.0)
import os
import json
import time
from dotenv import load_dotenv
from typing import Dict, Any, List

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
        # If the file was empty or contained an invalid zone, start at the first zone
        return ZONE_ROTATION[0]

def save_current_zone(zone_name: str) -> None:
    """Saves the name of the most recently posted zone to the state file."""
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(zone_name)
    except IOError as e:
        print(f"Error writing to state file {STATE_FILE}: {e}")


def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Environment Variables
    nws_user_agent = os.getenv("NWS_USER_AGENT")
    blog_id = os.getenv("BLOG_ID")
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    # 1. Configuration Check
    if not all([blog_id, nws_user_agent, gemini_api_key]):
        print("Error: Required environment variables (BLOG_ID, NWS_USER_AGENT, GEMINI_API_KEY) are not set in .env file.")
        return

    # NEW: Check for the required client secrets file
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"FATAL: Missing client secrets file at {CLIENT_SECRETS_FILE}.")
        print("Please ensure your 'client_secrets.json' file is in the project root.")
        return
    
    # --- TEST BLOGGER CONNECTION (using OAuth) ---
    print("\n--- Testing Blogger Connection with OAuth 2.0 ---")
    # This call handles initial authorization if token.json is missing or expired.
    # It will open a browser window for interactive authorization on the first run.
    if not list_accessible_blogs(CLIENT_SECRETS_FILE):
        print("FATAL: Blogger connection test failed. Exiting.")
        return
    print("------------------------------------------\n")
    
    # 2. Get Next Zone
    target_zone_name = get_next_zone()
    print(f"Targeting next zone: {target_zone_name}")

    # 3. Gather Data for the Zone
    zone_data = NWS_ZONES.get(target_zone_name, {})
    if not zone_data or not zone_data.get('cities'):
        print(f"FATAL: Zone data for '{target_zone_name}' is missing or empty.")
        return

    cities_forecasts = {}
    for city in zone_data['cities']:
        lat_lon = f"{city['lat_lon']}" 
        forecast = get_nws_forecast(lat_lon, nws_user_agent)
        if forecast:
            cities_forecasts[city['city']] = forecast

    if not cities_forecasts:
        print(f"Error: Failed to fetch any forecasts for {target_zone_name}. Exiting.")
        return

    # 4. Image/Disclaimer Prep (assuming 'image.png' is at the root or correctly path'd)
    base64_image = image_to_base64("image.png")
    image_tag = f'<img src="data:image/png;base64,{base64_image}" alt="Weather Map" style="width:100%; max-width:600px; display:block; margin: 0 auto;">' if base64_image else ""
    disclaimer_html = "<footer><p><strong>Disclaimer:</strong> This forecast is derived from National Weather Service (NWS) data. Weather is unpredictable; please consult official NWS sources for critical updates.</p></footer>"


    # 5. Generate Content
    print("Generating blog content...")
    blog_post = generate_blog_content(
        zone_name=target_zone_name,
        city_data=zone_data, 
        city_forecasts=cities_forecasts, 
        image_tag=image_tag, 
        disclaimer_html=disclaimer_html,
    )

    if not blog_post or not all(k in blog_post for k in ['title', 'content_html']):
        print("FATAL: Content generation failed or returned invalid data.")
        return
        
    # 6. Post to Blogger
    print(f"Attempting to post: '{blog_post['title']}' to Blogger ID: {blog_id}...")
    
    try:
        # Pass the path to client secrets
        if post_to_blogger(
            blog_id=blog_id,
            title=blog_post['title'],
            content_html=blog_post['content_html'],
            client_secret_path=CLIENT_SECRETS_FILE 
        ):
            print("Post successful. Updating zone state.")
            # 7. Update State (Rotation)
            save_current_zone(target_zone_name)
        else:
            print("Post failed. Zone state NOT updated.")

    except Exception as e:
        print(f"An unexpected error occurred in main execution: {e}")

    finally:
        # 8. No Service Account key to clean up with OAuth
        pass


if __name__ == "__main__":
    main()