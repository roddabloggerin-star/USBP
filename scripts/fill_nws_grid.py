# scripts/fill_nws_grid.py (Cleaned up and Finalized)
import requests
import json
import os
import time
from dotenv import load_dotenv

# --- Configuration ---
CONFIG_PATH = 'config/city_zones.py' 

# Load the environment variables to get the User-Agent
load_dotenv()
NWS_USER_AGENT = os.getenv("NWS_USER_AGENT", "default_weather_bot_user@example.com")

def get_grid_data(lat_lon: str, user_agent: str) -> dict | None:
    """
    Fetches the NWS grid ID, X, and Y from the /points endpoint.
    Includes detailed error logging for debugging API issues.
    """
    points_url = f"https://api.weather.gov/points/{lat_lon}"
    # --- CHANGED: Using application/geo+json instead of application/ld+json ---
    headers = {'User-Agent': user_agent, 'Accept': 'application/geo+json'} 
    TIMEOUT_SECONDS = 15 

    try:
        response = requests.get(points_url, headers=headers, timeout=TIMEOUT_SECONDS)
        
        # 1. Check for non-200 HTTP Status Codes
        response.raise_for_status() # Raises HTTPError for 4xx or 5xx responses
        
        # 2. Parse JSON response
        try:
            data = response.json()
        except json.JSONDecodeError:
            print(f" (JSON Decode Error: Non-JSON Response received.)", end="")
            return None
            
        properties = data.get('properties', {})
        
        grid_id = properties.get('gridId')
        grid_x = properties.get('gridX')
        grid_y = properties.get('gridY')
        
        # 3. Check for Data Fields
        if grid_id and grid_x is not None and grid_y is not None:
            return {
                "grid_id": grid_id,
                "grid_x": grid_x,
                "grid_y": grid_y
            }
        
        # If we reach here, the status was 200, but data was missing.
        print(f" (Data Missing: Status 200, but grid fields empty in JSON.)", end="")
        return None

    except requests.exceptions.HTTPError as e:
        # Log the specific HTTP status code error
        print(f" (HTTP Error: {e.response.status_code} {e.response.reason})", end="")
        return None
        
    except requests.exceptions.RequestException as e:
        # Log all other request-level errors (timeouts, connection issues)
        print(f" (Request Error: {type(e).__name__})", end="")
        return None


def run_grid_fill():
    """
    Loads city data, fetches grid points for all cities, and rewrites the config file.
    """
    if not NWS_USER_AGENT or NWS_USER_AGENT == "default_weather_bot_user@example.com":
        print("CRITICAL ERROR: NWS_USER_AGENT not found. Please set it in your .env file.")
        return

    print("--- Starting NWS Grid Point Lookup Utility ---")
    
    local_vars = {}
    try:
        # Ensure we read the file using UTF-8 to handle special characters (like '→')
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            exec(f.read(), globals(), local_vars)
        NWS_ZONES = local_vars.get('NWS_ZONES', {})
        ZONE_ROTATION = local_vars.get('ZONE_ROTATION', [])
    except Exception as e:
        print(f"ERROR: Could not load {CONFIG_PATH}. Ensure it's valid Python syntax: {e}")
        return

    total_cities = sum(len(zone['cities']) for zone in NWS_ZONES.values())
    processed_count = 0
    
    for zone_name, zone_data in NWS_ZONES.items():
        print(f"\nProcessing {zone_name} ({len(zone_data['cities'])} cities)...")
        
        for city_config in zone_data['cities']:
            processed_count += 1
            city = city_config['city']
            lat_lon = city_config['lat_lon']
            
            # Skip if already populated (check for Python 'None')
            if city_config.get('grid_id') is not None and city_config.get('grid_x') is not None:
                print(f"  [{processed_count}/{total_cities}] {city}: Already populated. Skipping.")
                continue

            print(f"  [{processed_count}/{total_cities}] Looking up grid for {city} ({lat_lon})...", end="")
            
            grid_info = get_grid_data(lat_lon, NWS_USER_AGENT)
            
            if grid_info:
                city_config.update(grid_info)
                print(f" SUCCESS. ID: {grid_info['grid_id']}/{grid_info['grid_x']},{grid_info['grid_y']}")
            else:
                print(" FAILED (API Error/Data Missing).")
            
            # Rate limit
            time.sleep(1.1) 

    print("\n--- Grid Lookup Complete. Rewriting config file... ---")
    
    # --- Rewriting logic using standard Python dict representation ---
    new_content = ""
    # Retain the Python comments and docstring
    new_content += '# config/city_zones.py\n\n'
    new_content += '"""\n'
    new_content += 'City → lat/lon mapping grouped into four custom zones.\n\n'
    new_content += 'grid_id/grid_x/grid_y populated by scripts/fill_nws_grid.py\n'
    new_content += '"""\n\n'
    new_content += 'NWS_ZONES = {\n'
    
    for zone_name, zone_data in NWS_ZONES.items():
        new_content += f'    "{zone_name}": {{\n'
        new_content += f'        "id": "{zone_data["id"]}",\n'
        new_content += f'        "cities": [\n'
        for city in zone_data['cities']:
            # Use repr() to get the correct Python string representation of the dictionary
            # This handles strings, integers, and 'None' correctly.
            city_str = repr(city).replace("'", '"') # Using double quotes for consistency
            new_content += f'            {city_str},\n'
        new_content += f'        ],\n'
        new_content += f'    }},\n\n'
    
    new_content += '}\n\n'
    new_content += f'ZONE_ROTATION = {ZONE_ROTATION}\n'

    # Write the new content to the file, explicitly using UTF-8 encoding
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"SUCCESS: Updated configuration saved to {CONFIG_PATH}")
    except IOError as e:
        print(f"CRITICAL ERROR: Failed to write to {CONFIG_PATH}: {e}")
        
    print("-------------------------------------------------------")


if __name__ == "__main__":
    run_grid_fill()