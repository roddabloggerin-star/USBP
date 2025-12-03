# src/main.py
import os
import json
import time
from dotenv import load_dotenv
# We need to use relative imports because these are local files
from .api_client import get_nws_forecast, image_to_base64, post_to_blogger
from .content_generator import generate_blog_content
from config.city_zones import NWS_ZONES, ZONE_ROTATION
from typing import Dict, Any, List

# --- Configuration & State Management ---
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
        # If last_zone is empty or not in the rotation, start with the first zone
        return ZONE_ROTATION[0]

def save_current_zone(zone_name: str):
    """Writes the name of the most recently posted zone to the state file."""
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(zone_name)
    except IOError as e:
        print(f"Error writing to state file {STATE_FILE}: {e}")
        
def write_service_account_key(key_json_string: str, file_path: str):
    """Writes the Service Account JSON string to a temporary file."""
    try:
        with open(file_path, 'w') as f:
            f.write(key_json_string)
        print(f"Service Account key written to temporary file: {file_path}")
    except IOError as e:
        print(f"Error writing service account key: {e}")

# --- Main Execution Logic ---
def main():
    """
    Main function to run the weather blog bot:
    1. Determine the next zone.
    2. Collect weather data for all cities in that zone.
    3. Generate the blog post content using Gemini.
    4. Post the content to Blogger.
    5. Update the rotation state.
    """
    load_dotenv()
    
    # Environment Variables
    NWS_USER_AGENT = os.getenv("NWS_USER_AGENT", "default_weather_bot_user@example.com")
    BLOG_ID = os.getenv("BLOG_ID")
    SERVICE_ACCOUNT_KEY = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")

    if not all([BLOG_ID, SERVICE_ACCOUNT_KEY]):
        print("Error: Missing required environment variables (BLOG_ID, GOOGLE_SERVICE_ACCOUNT_KEY).")
        return

    # Write the Service Account Key to a temporary file for the API client
    write_service_account_key(SERVICE_ACCOUNT_KEY, TEMP_KEY_FILE)
    
    try:
        # 1. Determine Target Zone
        target_zone_name = get_next_zone()
        target_zone_data = NWS_ZONES.get(target_zone_name)
        
        if not target_zone_data:
            print(f"Error: Zone '{target_zone_name}' not found in NWS_ZONES.")
            return

        print(f"--- Starting generation for zone: {target_zone_name} ---")

        # 2. Collect Weather Data for all cities in the target zone
        all_city_data: List[Dict[str, Any]] = []
        for city_config in target_zone_data['cities']:
            lat_lon = city_config['lat_lon']
            print(f"Fetching forecast for {city_config['city']} at {lat_lon}...")
            
            # The get_nws_forecast API call uses the grid data from the city_config
            forecast_data = get_nws_forecast(
                lat_lon=lat_lon,
                user_agent=NWS_USER_AGENT,
            )
            
            if forecast_data:
                all_city_data.append({
                    "city_config": city_config,
                    "forecast_data": forecast_data
                })
            else:
                # If a fetch fails, we continue with the cities we have
                pass 
                
            time.sleep(0.5) # Be polite to the NWS API

        # 3. Create a static map base64 image (Placeholder for simplicity)
        # In a real scenario, this would generate a relevant map image
        map_base64 = image_to_base64("https://upload.wikimedia.org/wikipedia/commons/e/e9/US_map_2.svg")
        
        if not all_city_data:
            print(f"Error: Failed to fetch any city data for zone: {target_zone_name}. Aborting.")
            return

        # 4. Generate Content (The Fix is here: removed the 'zone_id' argument)
        print("Generating blog content with Gemini...")
        blog_post = generate_blog_content(
            zone_name=target_zone_name,
            all_zone_forecast_data=all_city_data,
            image_base64=map_base64,
            # zone_id=target_zone_data['id'] # <-- REMOVED THIS EXTRA ARGUMENT
        )

        # 5. Post to Blogger
        if post_to_blogger(
            blog_id=BLOG_ID,
            title=blog_post['title'],
            content_html=blog_post['content_html'],
            service_account_key_path=TEMP_KEY_FILE # Use the temporary file path
        ):
            print("Post successful. Updating zone state.")
            # 6. Update State (Rotation)
            save_current_zone(target_zone_name)
        else:
            print("Post failed. Zone state NOT updated.")

    except Exception as e:
        print(f"An unexpected error occurred in main execution: {e}")

    finally:
        # 7. Clean up the temporary key file
        if os.path.exists(TEMP_KEY_FILE):
            os.remove(TEMP_KEY_FILE)
            print(f"Cleaned up temporary key file: {TEMP_KEY_FILE}")


if __name__ == "__main__":
    # Ensure this script is executable locally
    # Note: For running from a terminal at the project root:
    # python -m src.main
    # If running directly: python src/main.py, you might need to adjust imports.
    # The `.` imports assume modular execution context.
    
    # Simple direct execution fallback:
    try:
        main()
    except ImportError:
        # If relative imports fail in direct execution, use absolute path:
        from api_client import get_nws_forecast, image_to_base64, post_to_blogger
        from content_generator import generate_blog_content
        from config.city_zones import NWS_ZONES, ZONE_ROTATION
        
        main()