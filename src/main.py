# src/main.py (CLEANED & FIXED)
import os
import json
# REMOVED: import time 
from dotenv import load_dotenv
from typing import Dict, Any, List
# We need to use relative imports because these are local files
from .api_client import get_nws_forecast, image_to_base64, post_to_blogger
from .content_generator import generate_blog_content
from config.city_zones import NWS_ZONES, ZONE_ROTATION


# --- Configuration & State Management ---\
# State file to track which zone was posted last (relative to project root)
STATE_FILE = "last_posted_zone.txt"
# Temporary file for Service Account Key (relative to project root)
TEMP_KEY_FILE = "service_account_key.json" 

def get_next_zone() -> str:
    """Reads the last zone posted and determines the next zone for rotation."""
    last_zone = ""
    # Check if the state file exists and read it
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                last_zone = f.read().strip()
        except IOError:
            print("Warning: Could not read state file. Starting rotation from beginning.")
            last_zone = ""
            
    try:
        # Find the index of the last posted zone
        current_index = ZONE_ROTATION.index(last_zone)
        # Move to the next index, wrapping around using modulo
        next_index = (current_index + 1) % len(ZONE_ROTATION)
        return ZONE_ROTATION[next_index]
        
    except ValueError:
        # If last_zone is empty or not found in the list, start from the first one
        return ZONE_ROTATION[0]

def save_current_zone(zone_name: str) -> None:
    """Saves the name of the most recently posted zone to the state file."""
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(zone_name)
        print(f"State saved: Next rotation will start after {zone_name}")
    except IOError as e:
        print(f"Error saving state file: {e}")

# --- Environment Setup ---
def setup_env() -> tuple[str, str, str, str]: 
    """Loads environment variables and returns necessary values."""
    load_dotenv()
    # Note: These values can be sourced from a local .env file or GitHub Secrets
    nws_user_agent = os.getenv("NWS_USER_AGENT")
    blog_id = os.getenv("BLOG_ID")
    sa_key_content = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY") 

    if not all([nws_user_agent, blog_id, sa_key_content, gemini_api_key]):
        print("Error: Missing one or more required environment variables.")
        # Return empty strings to signal failure
        return "", "", "", ""

    return nws_user_agent, blog_id, sa_key_content, gemini_api_key

# --- Main Logic ---
def main():
    # 1. Setup Environment
    # BUG FIX: Ensure all four return values are correctly unpacked
    nws_user_agent, blog_id, sa_key_content, gemini_api_key = setup_env() 

    if not all([nws_user_agent, blog_id, sa_key_content, gemini_api_key]):
        print("Fatal: Environment setup failed. Exiting.")
        return

    # 2. Create temporary service account key file
    # This is required because the google-auth library only accepts a file path.
    try:
        with open(TEMP_KEY_FILE, 'w') as f:
            f.write(sa_key_content)
        print(f"Temporary Service Account key written to {TEMP_KEY_FILE}")
    except IOError as e:
        print(f"Error writing temporary key file: {e}. Exiting.")
        return
    
    try:
        # 3. Determine Next Zone
        target_zone_name = get_next_zone()
        target_zone_data = NWS_ZONES.get(target_zone_name)
        
        if not target_zone_data:
            print(f"Error: Target zone '{target_zone_name}' not found in NWS_ZONES config. Exiting.")
            return

        print(f"Targeting Zone: {target_zone_name}")

        # 4. Fetch Forecasts for all cities in the target zone
        city_forecasts = {}
        # We only take the first city's coordinates for now, but loop through all.
        for city_info in target_zone_data['cities']:
            city_name = city_info['city']
            lat_lon = city_info['lat_lon']
            
            # The grid_id/x/y are populated by fill_nws_grid.py, which is run before this script.
            # We don't need them here, but ensure they exist for the data structure's integrity.
            
            print(f"Fetching forecast for {city_name}...")
            forecast = get_nws_forecast(lat_lon, nws_user_agent)
            if forecast:
                city_forecasts[city_name] = forecast

        if not city_forecasts:
            print(f"Fatal: Could not retrieve any forecasts for {target_zone_name}. Exiting.")
            return

        # 5. Prepare Disclaimer and Image Tag
        # This is a sample image tag. You should replace the src URL with your actual hosted image URL.
        # Blogger allows embedding images directly, but you may need to upload them first.
        SAMPLE_IMAGE_URL = "YOUR_HOSTED_WEATHER_IMAGE_URL.jpg"
        image_tag = f'<div style="text-align: center;"><img src="{SAMPLE_IMAGE_URL}" alt="{target_zone_name} Weather Forecast" style="max-width: 100%; height: auto; margin: 15px 0;"></div>'

        # Legal Disclaimer is mandatory for NWS data usage
        DISCLAIMER_HTML = (
            '<hr>'
            '<p style="font-size: small; color: #888;">'
            '<strong>Legal Disclaimer:</strong> This forecast is based on public data '
            'from the National Weather Service (NWS) and is intended for informational '
            'purposes only. Always consult official NWS sources for critical weather '
            'information and safety updates. The accuracy of the NWS data is not guaranteed '
            'by this service. Data is subject to change.'
            '</p>'
        )

        # 6. Generate Blog Content using Gemini
        print("Generating blog content using Gemini...")
        blog_post = generate_blog_content(
            zone_name=target_zone_name,
            city_data=target_zone_data,
            city_forecasts=city_forecasts,
            image_tag=image_tag,
            disclaimer_html=DISCLAIMER_HTML,
        )

        if not blog_post:
            print("Fatal: Blog content generation failed. Exiting.")
            return
            
        print(f"Content generated: Title='{blog_post.get('title')}'")

        # 7. Post to Blogger
        # BUG FIX: Use the local variable blog_id
        if post_to_blogger(
            blog_id=blog_id, 
            title=blog_post['title'],
            content_html=blog_post['content_html'],
            service_account_key_path=TEMP_KEY_FILE # Use the temporary file path
        ):
            print("Post successful. Updating zone state.")
            # 8. Update State (Rotation)
            save_current_zone(target_zone_name)
        else:
            print("Post failed. Zone state NOT updated.")

    except Exception as e:
        print(f"An unexpected error occurred in main execution: {e}")

    finally:
        # 9. Clean up the temporary key file
        if os.path.exists(TEMP_KEY_FILE):
            os.remove(TEMP_KEY_FILE)
            print(f"Cleaned up temporary key file: {TEMP_KEY_FILE}")


if __name__ == "__main__":
    # Ensure this script is executable locally
    # When running from the project root: `python -m src.main`
    # If running directly: `python src/main.py`, you might need to adjust imports.
    main()