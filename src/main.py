# src/main.py (CLEANED with pathlib)
import os
import json
import time
# Use pathlib for robust path handling
from pathlib import Path 
from dotenv import load_dotenv
# We need to use relative imports because these are local files
from .api_client import get_nws_forecast, image_to_base64, post_to_blogger
from .content_generator import generate_blog_content
from config.city_zones import NWS_ZONES, ZONE_ROTATION
from typing import Dict, Any, List

# --- Configuration & State Management ---
# State file to track which zone was posted last
STATE_FILE = Path("last_posted_zone.txt") 
# Temporary file for Service Account Key 
TEMP_KEY_FILE = Path("service_account_key.json") 

def get_next_zone() -> str:
    """Reads the last zone posted and determines the next zone for rotation."""
    last_zone = ""
    # Use Path.exists() for checking file presence
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                last_zone = f.read().strip()
        except IOError:
            print("Warning: Could not read state file. Starting rotation from beginning.")
            last_zone = ""
            
    # If the last_zone is not in rotation or is empty, start from the first one
    if last_zone not in ZONE_ROTATION:
        next_zone = ZONE_ROTATION[0]
    else:
        try:
            # Find the index of the last posted zone
            current_index = ZONE_ROTATION.index(last_zone)
            # Move to the next index, wrapping around using modulo
            next_index = (current_index + 1) % len(ZONE_ROTATION)
            next_zone = ZONE_ROTATION[next_index]
        except ValueError:
            # Should not happen if last_zone is in ZONE_ROTATION, but as a fallback:
            next_zone = ZONE_ROTATION[0] 
            
    return next_zone

def save_current_zone(zone_name: str) -> None:
    """Saves the name of the last successfully processed zone."""
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(zone_name)
    except IOError as e:
        print(f"Error saving state file: {e}")

def main():
    """
    Main function to orchestrate the weather content generation and posting.
    """
    # 1. Setup Environment and Variables
    load_dotenv()
    
    # Use os.environ.get for robustness in GitHub Actions environment
    nws_user_agent = os.environ.get("NWS_USER_AGENT")
    blog_id = os.environ.get("BLOG_ID")
    service_account_key_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
    
    if not all([nws_user_agent, blog_id, service_account_key_json]):
        print("Error: Missing required environment variables (NWS_USER_AGENT, BLOG_ID, GOOGLE_SERVICE_ACCOUNT_KEY).")
        return

    try:
        # 2. Prepare the Service Account Key File
        # Write the JSON string from the environment variable to a temporary file
        with open(TEMP_KEY_FILE, 'w') as f:
            f.write(service_account_key_json)
        
        print(f"Service Account key written to temporary file: {TEMP_KEY_FILE}")

        # 3. Determine the next zone in rotation
        target_zone_name = get_next_zone()
        print(f"--- Starting generation for zone: {target_zone_name} ---")
        
        target_zone_data = NWS_ZONES.get(target_zone_name)
        if not target_zone_data:
            print(f"Error: Zone '{target_zone_name}' not found in NWS_ZONES configuration.")
            return

        zone_id = target_zone_data.get("id", "unknown")
        cities_in_zone = target_zone_data.get("cities", [])
        
        city_forecasts = {}
        # 4. Fetch Weather Data for all cities in the zone
        for city_data in cities_in_zone:
            city_name = city_data['city']
            lat_lon = f"{city_data['lat_lon']}"
            
            print(f"Fetching forecast for {city_name} at {lat_lon}...")
            forecast = get_nws_forecast(lat_lon, nws_user_agent)
            
            if forecast:
                city_forecasts[city_name] = forecast
            
            # 5. Respect API rate limits (NWS is generally 20-30/min, so 2 seconds is safe)
            time.sleep(2) 

        if not city_forecasts:
            print(f"No successful forecasts retrieved for zone '{target_zone_name}'. Exiting.")
            return

        # 6. Generate Blog Content using Gemini
        print("Generating blog content with Gemini...")
        blog_post = generate_blog_content(
            zone_name=target_zone_name,
            zone_id=zone_id,
            city_data=cities_in_zone,
            city_forecasts=city_forecasts,
            nws_user_agent=nws_user_agent
        )
        
        if not blog_post or 'title' not in blog_post:
            print("Content generation failed or returned invalid data. Exiting.")
            return

        # 7. Post to Blogger
        print(f"Attempting to post to Blogger: '{blog_post['title']}'")
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
        if TEMP_KEY_FILE.exists():
            os.remove(TEMP_KEY_FILE)
            print(f"Cleaned up temporary key file: {TEMP_KEY_FILE}")


if __name__ == "__main__":
    main()