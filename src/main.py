# src/main.py

import os
import time
from dotenv import load_dotenv

from typing import Dict, Any

from src.image_utils import build_placeholder_image_tag
from src.seo_utils import inject_seo_and_links

from .api_client import (
    get_nws_forecast,
    post_to_blogger,
    list_accessible_blogs,
)
from .content_generator import generate_blog_content
from config.city_zones import NWS_ZONES, ZONE_ROTATION


# --- Configuration & State Management ---

STATE_FILE = "last_posted_zone.txt"
CLIENT_SECRETS_FILE = "client_secrets.json"

DISCLAIMER_HTML = (
    "<p style=\"font-size: 0.8em; color: #888;\">"
    "Disclaimer: Forecast data is sourced from the National Weather Service (NWS) and is subject to change. "
    "This bot processes NWS data for aggregation and is not responsible for forecast accuracy."
    "</p>"
)

# --- Environment / critical settings ---

load_dotenv()

NWS_USER_AGENT = os.getenv("NWS_USER_AGENT")
BLOG_ID = os.getenv("BLOG_ID")

if not NWS_USER_AGENT or not BLOG_ID:
    print("FATAL: NWS_USER_AGENT or BLOG_ID environment variable not set. Check your .env file.")
    raise SystemExit(1)


# --- Rotation helpers ---

def get_next_zone() -> str:
    """
    Reads the last zone posted from STATE_FILE and returns the next zone
    from ZONE_ROTATION. On first run or invalid state, returns the first zone.
    """
    last_zone = ""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                last_zone = f.read().strip()
        except OSError:
            print("Warning: Could not read state file. Starting rotation from beginning.")
            last_zone = ""

    try:
        current_index = ZONE_ROTATION.index(last_zone)
        next_index = (current_index + 1) % len(ZONE_ROTATION)
        return ZONE_ROTATION[next_index]
    except ValueError:
        # last_zone not in rotation (first run or corrupted state)
        return ZONE_ROTATION[0]


def update_last_zone(zone_name: str) -> None:
    """Writes the name of the last successfully processed zone to STATE_FILE."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            f.write(zone_name)
        print(f"State updated: Next run will target the zone after '{zone_name}'.")
    except OSError:
        print(f"FATAL: Could not write to state file {STATE_FILE}. Rotation tracking failed.")


# --- Main orchestration ---

def main() -> None:
    print("--- Starting Weather Blog Bot ---")

    # 1) Test Blogger OAuth connection (also refreshes/creates token)
    print("\n--- Testing Blogger Connection with OAuth 2.0 ---")
    if not list_accessible_blogs(CLIENT_SECRETS_FILE):
        print("FATAL: Failed to connect to Blogger API or retrieve blogs.")
        return

    # 2) Determine which zone to post for
    target_zone_name = get_next_zone()
    if target_zone_name not in NWS_ZONES:
        print(f"FATAL: Target zone '{target_zone_name}' not found in NWS_ZONES configuration.")
        return

    print(f"\nTargeting next zone: {target_zone_name}")
    zone_data = NWS_ZONES[target_zone_name]  # contains 'id' and 'cities'

    # 3) Fetch NWS hourly forecasts for each city in this zone
    print("Fetching NWS hourly forecasts (this may take a moment due to rate limiting)...")
    cities_forecasts: Dict[str, Dict[str, Any]] = {}

    for city_info in zone_data["cities"]:
        city_name = city_info["city"]
        lat_lon = city_info.get("lat_lon")

        if not lat_lon:
            print(f"Warning: Missing lat_lon for {city_name}. Skipping.")
            continue

        forecast_props = get_nws_forecast(lat_lon=lat_lon, user_agent=NWS_USER_AGENT)
        if forecast_props:
            # Shape the data to match what content_generator expects:
            #   alerts: list (not yet implemented, so empty)
            #   current_conditions: dict (not yet implemented, so empty)
            #   forecast_hourly: dict with 'periods'
            cities_forecasts[city_name] = {
                "alerts": [],
                "current_conditions": {},
                "forecast_hourly": forecast_props,
            }
        else:
            print(f"Warning: Failed to retrieve forecast for {city_name}. Skipping.")

        # Respect NWS rate limits
        time.sleep(1.5)

    if not cities_forecasts:
        print("FATAL: No weather data was successfully retrieved. Aborting post.")
        return

    # 4) Build image tag (lightweight URL-based image, no base64)
    print(f"--- Creating Placeholder Image Tag for {target_zone_name} ---")
    image_tag = build_placeholder_image_tag(target_zone_name)

    # 5) Generate blog content with Gemini
    print("\n--- Generating SEO-Optimized Blog Content (1000+ Words) ---")
    blog_payload = generate_blog_content(
        zone_name=target_zone_name,
        city_data=zone_data,
        city_forecasts=cities_forecasts,
        image_tag=image_tag,
        disclaimer_html=DISCLAIMER_HTML,
    )

    if not blog_payload:
        print("FATAL: Content generation failed. Cannot proceed to posting.")
        return

    title = blog_payload["title"]
    content_html = blog_payload["content_html"]

    # 6) Inject SEO schema + internal links
    content_html = inject_seo_and_links(
        content_html=content_html,
        title=title,
        zone_name=target_zone_name,
    )

    # 7) Post to Blogger
    print(f"\n--- Posting to Blogger: '{title}' ---")
    post_success = post_to_blogger(
        blog_id=BLOG_ID,
        title=title,
        content_html=content_html,
        client_secret_path=CLIENT_SECRETS_FILE,
    )

    if post_success:
        print(f"SUCCESS: Post for {target_zone_name} published.")
        update_last_zone(target_zone_name)
    else:
        print(f"FAILURE: Post for {target_zone_name} failed. State not updated.")


if __name__ == "__main__":
    main()
