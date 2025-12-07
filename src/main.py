# src/main.py

import os
import time
from typing import Dict, Any

from dotenv import load_dotenv

from src.image_utils import build_placeholder_image_tag
from src.seo_utils import inject_seo_and_links
from src.post_storage import save_post_and_update_indexes
from src.api_client import (
    get_nws_forecast,
    post_to_blogger,
    list_accessible_blogs,
)
from config.city_zones import NWS_ZONES, ZONE_ROTATION

STATE_FILE = "last_posted_zone.txt"
CLIENT_SECRETS_FILE = "client_secrets.json"

DISCLAIMER_HTML = (
    "<p style=\"font-size: 0.8em; color: #888;\">"
    "This post is created using the public data provided by the National Weather Service. "
    "Please check the **<a href=\"https://www.weather.gov/\" target=\"_blank\" style=\"color: #007bff; text-decoration: none;\">Original source</a>** for more information."
    "</p>"
)

# --- Load environment variables first ---
load_dotenv()

# --- MASTER SWITCH: PUBLISH vs OFFLINE MODE ---
# PUBLISH=true  -> call Blogger API + save locally
# PUBLISH=false -> only save locally (no Blogger calls)
PUBLISH = os.getenv("PUBLISH", "false").lower() == "true"

NWS_USER_AGENT = os.getenv("NWS_USER_AGENT")
BLOG_ID = os.getenv("BLOG_ID")

if not NWS_USER_AGENT:
    print("FATAL: NWS_USER_AGENT environment variable not set. Check your .env or GitHub secrets.")
    raise SystemExit(1)

if PUBLISH and not BLOG_ID:
    print("FATAL: PUBLISH=True but BLOG_ID is not set in environment.")
    raise SystemExit(1)


# --- Rotation helpers ---

def get_next_zone() -> str:
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
        # First run or corrupted state
        return ZONE_ROTATION[0]


def update_last_zone(zone_name: str) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            f.write(zone_name)
        print(f"State updated: Next run will target the zone after '{zone_name}'.")
    except OSError:
        print(f"FATAL: Could not write to state file {STATE_FILE}. Rotation tracking failed.")


# --- Main orchestration ---

def main() -> None:
    print("--- Starting Weather Blog Bot ---")

    # 1) Blogger connection only if we are actually publishing
    if PUBLISH:
        print("\n--- Testing Blogger Connection with OAuth 2.0 ---")
        if not list_accessible_blogs(CLIENT_SECRETS_FILE):
            print("FATAL: Failed to connect to Blogger API or retrieve blogs.")
            return
    else:
        print("\nPUBLISH flag is False. Running in OFFLINE GENERATION MODE (no Blogger API calls).")

    # 2) Determine which zone to post for
    target_zone_name = get_next_zone()
    if target_zone_name not in NWS_ZONES:
        print(f"FATAL: Target zone '{target_zone_name}' not found in NWS_ZONES configuration.")
        return

    print(f"\nTargeting next zone: {target_zone_name}")
    zone_data = NWS_ZONES[target_zone_name]

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
            cities_forecasts[city_name] = {
                "alerts": [],
                "current_conditions": {},
                "forecast_hourly": forecast_props,
            }
        else:
            print(f"Warning: Failed to retrieve forecast for {city_name}. Skipping.")

        time.sleep(1.5)  # respect NWS rate limits

    if not cities_forecasts:
        print("FATAL: No weather data was successfully retrieved. Aborting post.")
        return

    # 4) Build image tag
    print(f"--- Creating Placeholder Image Tag for {target_zone_name} ---")
    image_tag = build_placeholder_image_tag(target_zone_name)

    # 5) Generate blog content with Gemini
    from src.content_generator import generate_blog_content  # local import to avoid circulars

    print("\n--- Generating SEO-Optimized Blog Content (1000+ Words) ---")
    blog_payload = generate_blog_content(
        zone_name=target_zone_name,
        city_data=zone_data,
        city_forecasts=cities_forecasts,
        image_tag=image_tag,
        disclaimer_html=DISCLAIMER_HTML,
    )

    if not blog_payload:
        print("FATAL: Content generation failed. Cannot proceed.")
        return

    title = blog_payload["title"]
    meta_description = blog_payload.get("meta_description", "")
    content_html = blog_payload["content_html"]

    # 6) Inject SEO schema + internal links
    content_html = inject_seo_and_links(
        content_html=content_html,
        title=title,
        zone_name=target_zone_name,
    )

    # 7) Save locally and update indexes (dashboard, archive, categories, sitemap)
    post_meta = save_post_and_update_indexes(
        title=title,
        meta_description=meta_description,
        content_html=content_html,
        zone_name=target_zone_name,
    )

    # 8) If publishing is enabled, also send to Blogger
    if PUBLISH:
        print(f"\n--- Posting to Blogger: '{title}' ---")
        success = post_to_blogger(
            blog_id=BLOG_ID,
            title=title,
            content_html=content_html,
            client_secret_path=CLIENT_SECRETS_FILE,
            labels=post_meta.tags,  # auto-generated tags used as Blogger labels
        )

        if success:
            print(f"SUCCESS: Post for {target_zone_name} published.")
            update_last_zone(target_zone_name)
        else:
            print(f"FAILURE: Post for {target_zone_name} failed. State not updated.")
    else:
        print("\nPUBLISH=False → Skipping Blogger API. Post saved locally only.")
        update_last_zone(target_zone_name)


if __name__ == "__main__":
    main()
