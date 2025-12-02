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
    except ValueError:
        # If file is empty or contains an invalid zone, start with the first one
        next_index = 0
        
    return ZONE_ROTATION[next_index]

def save_current_zone(zone_name: str):
    """Saves the name of the zone that was just posted."""
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(zone_name)
    except IOError as e:
        print(f"ERROR: Could not write to state file {STATE_FILE}: {e}")

# --- Main Execution Function ---
def main():
    # 1. Load Environment Variables (for local testing)
    # The load_dotenv() call must be outside of the __name__ == "__main__": block
    # for it to work correctly in some execution contexts.
    load_dotenv()
    
    # 2. Get Secrets
    nws_user_agent = os.getenv("NWS_USER_AGENT")
    blog_id = os.getenv("BLOG_ID")
    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY") 

    if not nws_user_agent or not service_account_json or not blog_id:
        print("CRITICAL ERROR: Missing required environment variables (NWS_USER_AGENT, GOOGLE_SERVICE_ACCOUNT_KEY, BLOG_ID). Exiting.")
        print("Required for local testing: .env file. Required for GitHub: Repository Secrets.")
        return

    # 3. Create a temporary key file from the secret string
    try:
        # The service account JSON must be valid
        key_data = json.loads(service_account_json)
        with open(TEMP_KEY_FILE, 'w') as f:
            json.dump(key_data, f, indent=2)
        print(f"Created temporary key file: {TEMP_KEY_FILE}")

        # 4. Determine the Current Zone for Posting
        target_zone_name = get_next_zone()
        print(f"--- Starting run for: {target_zone_name} ---")
        
        target_zone_config = NWS_ZONES.get(target_zone_name)
        if not target_zone_config or not target_zone_config['cities']:
            print(f"Error: Configuration for zone '{target_zone_name}' not found or is empty.")
            return

        # 5. Collect Data for All Cities in the Zone
        all_zone_forecast_data: List[Dict[str, Any]] = []
        primary_image_base64 = ""
        
        # NOTE: Using the first valid icon found as the primary image
        for city_config in target_zone_config['cities']:
            # Introduce a small delay to respect NWS API rate limits (1 request/sec is recommended)
            time.sleep(1) 
            
            city_name = city_config.get('city', 'Unknown City')
            print(f"Fetching forecast for {city_name}...")
            
            # Get the full hourly forecast
            forecast_properties = get_nws_forecast(city_config['lat_lon'], nws_user_agent)
            
            if forecast_properties:
                all_zone_forecast_data.append({
                    'city_config': city_config,
                    'forecast_data': forecast_properties
                })
                
                # Fetch image only if we haven't found one yet
                if not primary_image_base64 and forecast_properties.get('periods'):
                     first_icon_url = forecast_properties['periods'][0].get('icon')
                     if first_icon_url:
                         print(f"Found primary image icon at: {first_icon_url}")
                         primary_image_base64 = image_to_base64(first_icon_url, nws_user_agent)

        if not all_zone_forecast_data:
            print("No valid forecast data was collected. Cannot generate post. Exiting.")
            return

        # 6. Generate Blog Content (Title, Meta, HTML)
        print("Generating SEO-optimized blog content with Gemini...")
        blog_post = generate_blog_content(
            zone_name=target_zone_name,
            all_zone_forecast_data=all_zone_forecast_data,
            image_base64=primary_image_base64 # Pass the Base64 image string
        )
        
        # 7. Safety Check: Content size constraint (5MB limit)
        content_size_bytes = len(blog_post.get('content_html', '').encode('utf-8'))
        MAX_SAFE_SIZE = 4.8 * 1024 * 1024 # Slightly less than 5MB for safety
        
        if content_size_bytes > MAX_SAFE_SIZE:
            print(f"Warning: Generated content size ({content_size_bytes / 1024**2:.2f}MB) exceeds safe limit. Skipping post.")
            return
            
        # 8. Post to Blogger
        print(f"Content generated: {len(blog_post['title'])} chars title, {content_size_bytes / 1024:.2f}KB body.")
        print("Attempting to post to Blogger with Service Account...")
        
        if post_to_blogger(
            blog_id=blog_id,
            title=blog_post['title'],
            content_html=blog_post['content_html'],
            service_account_key_path=TEMP_KEY_FILE # Use the temporary file path
        ):
            print("Post successful. Updating zone state.")
            # 9. Update State (Rotation)
            save_current_zone(target_zone_name)
        else:
            print("Post failed. Zone state NOT updated.")

    except Exception as e:
        print(f"An unexpected error occurred in main execution: {e}")

    finally:
        # 10. Clean up the temporary key file
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
        print("Attempting execution with direct imports (likely local test).")
        main()