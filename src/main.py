# src/main.py (CLEANED)

import os
import json
import time
# Use pathlib for robust path handling
from pathlib import Path 
from dotenv import load_dotenv
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
            
    # ... (rest of get_next_zone function logic is correct)
    
def save_current_zone(zone_name: str) -> None:
    """Saves the name of the last successfully processed zone."""
    # Use Path object
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(zone_name)
    except IOError as e:
        print(f"Error saving state file: {e}")

# ... (inside main function)

        # 10. Clean up the temporary key file
        # Use Path.exists()
        if TEMP_KEY_FILE.exists():
            os.remove(TEMP_KEY_FILE)
            print(f"Cleaned up temporary key file: {TEMP_KEY_FILE}")

# ... (the rest of the script is correct)