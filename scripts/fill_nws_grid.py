# scripts/fill_nws_grid.py (IMPROVED: Robust Config Rewriting)
import requests
import json
import os
import time
from dotenv import load_dotenv

# --- Configuration ---
CONFIG_PATH = 'config/city_zones.py' 

# Load the environment variables to get the User-Agent
# This assumes the script is run from the project root.
load_dotenv()
NWS_USER_AGENT = os.getenv("NWS_USER_AGENT", "default_weather_bot_user@example.com")

def get_grid_data(lat_lon: str, user_agent: str) -> dict | None:
    """
    Fetches the NWS grid ID, X, and Y from the /points endpoint.
    Includes detailed error logging for debugging API issues.
    """
    points_url = f"https://api.weather.gov/points/{lat_lon}"
    # Use application/geo+json for NWS API
    headers = {'User-Agent': user_agent, 'Accept': 'application/geo+json'} 
    TIMEOUT_SECONDS = 15 

    try:
        response = requests.get(points_url, headers=headers, timeout=TIMEOUT_SECONDS)
        
        # 1. Check for non-200 HTTP Status Codes
        response.raise_for_status() # Raises HTTPError for 4xx or 5xx responses
        
        # 2. Parse JSON response
        data = response.json()
        
        # 3. Extract Grid Information
        properties = data.get('properties', {})
        grid_id = properties.get('cwa')
        grid_x = properties.get('gridX')
        grid_y = properties.get('gridY')
        
        if grid_id and grid_x is not None and grid_y is not None:
            return {
                "grid_id": grid_id,
                "grid_x": int(grid_x),
                "grid_y": int(grid_y)
            }
        else:
            print(f"Warning: Grid data incomplete for {lat_lon}. Properties: {properties}")
            return None

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error for {lat_lon}: {response.status_code}. Response: {response.text[:100]}...")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request Error for {lat_lon}: {e}")
        return None
    except json.JSONDecodeError:
        print(f"JSON Decode Error for {lat_lon}. Response: {response.text[:100]}...")
        return None

def rewrite_config(NWS_ZONES: dict, ZONE_ROTATION: list) -> None:
    """Rewrites config/city_zones.py with the updated grid data."""
    print(f"Rewriting {CONFIG_PATH} with {len(NWS_ZONES)} zones and updated grid data...")
    
    # Use repr() and manual string assembly for a cleaner, more reliable output
    nws_zones_content = json.dumps(NWS_ZONES, indent=4)
    zone_rotation_content = repr(ZONE_ROTATION)
    
    # Manually construct the Python file content
    new_content = (
        '# config/city_zones.py\n\n'
        '"""\n'
        'City → lat/lon mapping grouped into four custom zones.\n\n'
        'grid_id/grid_x/grid_y populated by scripts/fill_nws_grid.py\n'
        '"""\n\n'
        # NWS_ZONES is complex, using JSON string then conversion for better readability in the file
        'NWS_ZONES = \\\n'
        f'{nws_zones_content}\n\n'
        f'ZONE_ROTATION = {zone_rotation_content}\n'
    )

    # Write the new content to the file, explicitly using UTF-8 encoding
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Successfully rewrote {CONFIG_PATH}")
    except IOError as e:
        print(f"Error writing to config file {CONFIG_PATH}: {e}")

def main():
    """
    Main function to load the existing config, update grid data, and rewrite the file.
    """
    # NOTE: To avoid circular imports, we must execute the config file directly
    # and use the globals() to get the current state of NWS_ZONES and ZONE_ROTATION.
    # We will assume a placeholder 'city_zones.py' exists for the first run.
    
    # 1. Load Initial Configuration (Requires config/city_zones.py to exist)
    try:
        # Temporarily add the config directory to the path to import the module
        import sys
        sys.path.append(os.path.dirname(os.path.abspath(CONFIG_PATH)))
        # Execute the file to get the current constants
        import city_zones
        
        # Make a deep copy of the mutable data structures
        NWS_ZONES_UPDATED = json.loads(json.dumps(city_zones.NWS_ZONES))
        ZONE_ROTATION_LIST = list(city_zones.ZONE_ROTATION)
        
        # Remove the imported module and path for cleanup
        sys.path.pop()
        del sys.modules['city_zones']
        
        if not NWS_ZONES_UPDATED:
            print("Error: Could not load initial NWS_ZONES data. Check config/city_zones.py")
            return
            
    except Exception as e:
        print(f"Failed to load or parse initial config file: {e}")
        print("Please ensure config/city_zones.py exists and is valid Python code.")
        return

    print(f"Loaded {len(NWS_ZONES_UPDATED)} zones for update.")
    
    # 2. Iterate and Update
    update_count = 0
    
    for zone_name, zone_data in NWS_ZONES_UPDATED.items():
        print(f"\nProcessing Zone: {zone_name}...")
        
        for city in zone_data['cities']:
            # Skip if grid data is already present
            if 'grid_id' in city and 'grid_x' in city and 'grid_y' in city:
                # print(f"Grid data already exists for {city['city']}. Skipping.")
                continue
                
            lat_lon = city.get('lat_lon')
            if not lat_lon:
                print(f"Error: Missing lat_lon for {city.get('city', 'Unknown City')}. Skipping.")
                continue
                
            # Fetch the grid data
            grid_info = get_grid_data(lat_lon, NWS_USER_AGENT)
            
            if grid_info:
                # Update the city dictionary in the NWS_ZONES_UPDATED structure
                city.update(grid_info)
                print(f"  - Updated {city['city']} with grid: {grid_info['grid_id']} {grid_info['grid_x']},{grid_info['grid_y']}")
                update_count += 1
            else:
                print(f"  - Failed to get grid data for {city['city']}")
            
            # Rate limit NWS API calls (1 call per second recommended)
            time.sleep(1.5) 

    if update_count > 0:
        print(f"\n--- Update Complete. {update_count} cities were updated. ---")
        # 3. Rewrite the Configuration File
        rewrite_config(NWS_ZONES_UPDATED, ZONE_ROTATION_LIST)
    else:
        print("\n--- Update Complete. No new grid data was required. ---")

if __name__ == "__main__":
    main()