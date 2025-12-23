#!/usr/bin/env python3
"""
USA Weather Blogger – Single-File Edition
Python 3.12 / GitHub Actions Safe
"""

# ============================================================
# Imports
# ============================================================
import os
import json
import asyncio
import aiohttp
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

# --- UPDATED IMPORTS FOR BLOGGER AUTH ---
from googleapiclient.discovery import build
from googleapiclient.http import HttpError 
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
# pickle is no longer needed
# import pickle 
# ----------------------------------------

# ============================================================
# Logging
# ============================================================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("weatherbot")

# ============================================================
# Environment
# ============================================================
load_dotenv()

def env(name: str, default=None, required=False):
    v = os.getenv(name, default)
    if required and not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

GEMINI_API_KEY = env("GEMINI_API_KEY", required=True)
# BLOGGER_API_KEY is no longer used for write access
BLOG_BASE_URL = env("BLOG_BASE_URL", required=True)
BLOG_ID = env("BLOG_ID", required=True)
NWS_USER_AGENT = env("NWS_USER_AGENT", required=True)
PUBLISH = env("PUBLISH", "false").lower() == "true"

OUTPUT_DIR = Path("output_posts")
STATE_FILE = Path(env("STATE_FILE", "last_posted_zone.txt"))

# --- NEW BLOGGER AUTH FILE PATHS ---
TOKEN_FILE = Path(env("TOKEN_FILE", "token.json"))
CLIENT_SECRETS_FILE = Path(env("CLIENT_SECRETS_FILE", "client_secrets.json"))
# -----------------------------------

# ============================================================
# Gemini (UNCHANGED)
# ============================================================
client = genai.Client(api_key=GEMINI_API_KEY)

MODEL = "gemini-2.5-flash"

SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "title": types.Schema(type=types.Type.STRING),
        "meta_description": types.Schema(type=types.Type.STRING),
        "content_html": types.Schema(type=types.Type.STRING),
    },
    required=["title", "meta_description", "content_html"],
)

# ============================================================
# Zones (UNCHANGED)
# ==========================================================================================
NWS_ZONES = {
    "Eastern Zone": {
        "id": "eastern",
        "cities": [
            {"city": "Boston, MA", "lat_lon": "42.3601,-71.0589", "grid_id": "BOX", "grid_x": 71, "grid_y": 90},
            {"city": "Worcester, MA", "lat_lon": "42.2626,-71.8023", "grid_id": "BOX", "grid_x": 47, "grid_y": 81},
            {"city": "Springfield, MA", "lat_lon": "42.1015,-72.5898", "grid_id": "BOX", "grid_x": 22, "grid_y": 69},
            {"city": "Providence, RI", "lat_lon": "41.8240,-71.4128", "grid_id": "BOX", "grid_x": 64, "grid_y": 64},
            {"city": "Hartford, CT", "lat_lon": "41.7658,-72.6734", "grid_id": "BOX", "grid_x": 22, "grid_y": 54},
            {"city": "New Haven, CT", "lat_lon": "41.3083,-72.9224", "grid_id": "BOX", "grid_x": 9, "grid_y": 38},
            {"city": "New York, NY", "lat_lon": "40.7128,-74.0060", "grid_id": "OKX", "grid_x": 33, "grid_y": 36},
            {"city": "Philadelphia, PA", "lat_lon": "39.9526,-75.1652", "grid_id": "PHI", "grid_x": 71, "grid_y": 48},
            {"city": "Pittsburgh, PA", "lat_lon": "40.4406,-79.9959", "grid_id": "PBZ", "grid_x": 61, "grid_y": 58},
            {"city": "Baltimore, MD", "lat_lon": "39.2904,-76.6122", "grid_id": "LWX", "grid_x": 62, "grid_y": 142},
            {"city": "Washington, D.C.", "lat_lon": "38.9072,-77.0369", "grid_id": "LWX", "grid_x": 88, "grid_y": 128},
            {"city": "Richmond, VA", "lat_lon": "37.5407,-77.4360", "grid_id": "AKQ", "grid_x": 39, "grid_y": 79},
            {"city": "Raleigh, NC", "lat_lon": "35.7796,-78.6382", "grid_id": "RAH", "grid_x": 51, "grid_y": 60},
            {"city": "Charlotte, NC", "lat_lon": "35.2271,-80.8431", "grid_id": "GSP", "grid_x": 76, "grid_y": 63},
            {"city": "Charleston, SC", "lat_lon": "32.7765,-79.9311", "grid_id": "CHS", "grid_x": 89, "grid_y": 47},
        ]
    },
    "Southern Zone": {
        "id": "southern",
        "cities": [
            {"city": "Atlanta, GA", "lat_lon": "33.7490,-84.3880", "grid_id": "FFC", "grid_x": 90, "grid_y": 78},
            {"city": "Jacksonville, FL", "lat_lon": "30.3322,-81.6557", "grid_id": "JAX", "grid_x": 79, "grid_y": 62},
            {"city": "Miami, FL", "lat_lon": "25.7617,-80.1918", "grid_id": "MFL", "grid_x": 73, "grid_y": 54},
            {"city": "Tampa, FL", "lat_lon": "27.9475,-82.4582", "grid_id": "TBW", "grid_x": 67, "grid_y": 71},
            {"city": "Orlando, FL", "lat_lon": "28.5383,-81.3792", "grid_id": "MLB", "grid_x": 58, "grid_y": 75},
            {"city": "Birmingham, AL", "lat_lon": "33.5207,-86.8024", "grid_id": "BMX", "grid_x": 52, "grid_y": 79},
            {"city": "New Orleans, LA", "lat_lon": "29.9511,-90.0715", "grid_id": "LIX", "grid_x": 94, "grid_y": 78},
            {"city": "Houston, TX", "lat_lon": "29.7604,-95.3698", "grid_id": "HGX", "grid_x": 73, "grid_y": 80},
            {"city": "San Antonio, TX", "lat_lon": "29.4241,-98.4936", "grid_id": "EWX", "grid_x": 105, "grid_y": 61},
            {"city": "Dallas, TX", "lat_lon": "32.7767,-96.7970", "grid_id": "FWD", "grid_x": 71, "grid_y": 99},
            {"city": "Austin, TX", "lat_lon": "30.2672,-97.7431", "grid_id": "EWX", "grid_x": 100, "grid_y": 80},
            {"city": "Oklahoma City, OK", "lat_lon": "35.4676,-97.5164", "grid_id": "OUN", "grid_x": 80, "grid_y": 107},
            {"city": "Memphis, TN", "lat_lon": "35.1495,-90.0490", "grid_id": "MEG", "grid_x": 78, "grid_y": 58},
            {"city": "Nashville, TN", "lat_lon": "36.1627,-86.7816", "grid_id": "OHX", "grid_x": 50, "grid_y": 81},
            {"city": "Louisville, KY", "lat_lon": "38.2527,-85.7585", "grid_id": "LMK", "grid_x": 55, "grid_y": 71},
        ]
    },
    "Central Zone": {
        "id": "central",
        "cities": [
            {"city": "Chicago, IL", "lat_lon": "41.8781,-87.6298", "grid_id": "LOT", "grid_x": 68, "grid_y": 70},
            {"city": "Indianapolis, IN", "lat_lon": "39.7684,-86.1580", "grid_id": "IND", "grid_x": 60, "grid_y": 70},
            {"city": "Detroit, MI", "lat_lon": "42.3314,-83.0458", "grid_id": "DTX", "grid_x": 55, "grid_y": 70},
            {"city": "Cleveland, OH", "lat_lon": "41.4993,-81.6944", "grid_id": "CLE", "grid_x": 84, "grid_y": 50},
            {"city": "Cincinnati, OH", "lat_lon": "39.1031,-84.5120", "grid_id": "ILN", "grid_x": 58, "grid_y": 70},
            {"city": "St. Louis, MO", "lat_lon": "38.6270,-90.1994", "grid_id": "LSX", "grid_x": 76, "grid_y": 59},
            {"city": "Kansas City, MO", "lat_lon": "39.0997,-94.5786", "grid_id": "EAX", "grid_x": 39, "grid_y": 48},
            {"city": "Omaha, NE", "lat_lon": "41.2565,-95.9345", "grid_id": "OAX", "grid_x": 105, "grid_y": 66},
            {"city": "Minneapolis, MN", "lat_lon": "44.9778,-93.2650", "grid_id": "MPX", "grid_x": 113, "grid_y": 42},
            {"city": "Milwaukee, WI", "lat_lon": "43.0389,-87.9065", "grid_id": "MKX", "grid_x": 100, "grid_y": 50},
            {"city": "Madison, WI", "lat_lon": "43.0731,-89.4012", "grid_id": "MKX", "grid_x": 66, "grid_y": 46},
            {"city": "Des Moines, IA", "lat_lon": "41.5910,-93.6037", "grid_id": "DMX", "grid_x": 92, "grid_y": 61},
            {"city": "Denver, CO", "lat_lon": "39.7392,-104.9903", "grid_id": "BOU", "grid_x": 67, "grid_y": 67},
            {"city": "Cheyenne, WY", "lat_lon": "41.1400,-104.8202", "grid_id": "CYS", "grid_x": 23, "grid_y": 27},
            {"city": "Fargo, ND", "lat_lon": "46.8772,-96.7898", "grid_id": "FGF", "grid_x": 80, "grid_y": 40},
        ]
    },
    "Western Zone": {
        "id": "western",
        "cities": [
            {"city": "Los Angeles, CA", "lat_lon": "34.0522,-118.2437", "grid_id": "LOX", "grid_x": 155, "grid_y": 45},
            {"city": "San Diego, CA", "lat_lon": "32.7157,-117.1611", "grid_id": "SGX", "grid_x": 57, "grid_y": 14},
            {"city": "San Jose, CA", "lat_lon": "37.3382,-121.8863", "grid_id": "MTR", "grid_x": 99, "grid_y": 82},
            {"city": "San Francisco, CA", "lat_lon": "37.7749,-122.4194", "grid_id": "MTR", "grid_x": 85, "grid_y": 105},
            {"city": "Sacramento, CA", "lat_lon": "38.5816,-121.4944", "grid_id": "STO", "grid_x": 41, "grid_y": 68},
            {"city": "Fresno, CA", "lat_lon": "36.7378,-119.7871", "grid_id": "HNX", "grid_x": 52, "grid_y": 100},
            {"city": "Portland, OR", "lat_lon": "45.5051,-122.6750", "grid_id": "PQR", "grid_x": 128, "grid_y": 133},
            {"city": "Seattle, WA", "lat_lon": "47.6062,-122.3321", "grid_id": "SEW", "grid_x": 118, "grid_y": 132},
            {"city": "Boise, ID", "lat_lon": "43.6150,-116.2024", "grid_id": "BOI", "grid_x": 120, "grid_y": 152},
            {"city": "Phoenix, AZ", "lat_lon": "33.4484,-112.0740", "grid_id": "PSR", "grid_x": 131, "grid_y": 127},
            {"city": "Las Vegas, NV", "lat_lon": "36.1699,-115.1398", "grid_id": "VEF", "grid_x": 86, "grid_y": 80},
            {"city": "Salt Lake City, UT", "lat_lon": "40.7608,-111.8910", "grid_id": "SLC", "grid_x": 100, "grid_y": 120},
            {"city": "Albuquerque, NM", "lat_lon": "35.0844,-106.6504", "grid_id": "ABQ", "grid_x": 132, "grid_y": 161},
            {"city": "El Paso, TX", "lat_lon": "31.7619,-106.4850", "grid_id": "EPZ", "grid_x": 57, "grid_y": 91},
            {"city": "Helena, MT", "lat_lon": "46.5920,-112.0270", "grid_id": "TFX", "grid_x": 39, "grid_y": 57},
        ]
    }
}

ZONE_ROTATION = list(NWS_ZONES.keys())

# ============================================================
# NWS Fetching (ASYNC + FALLBACK - UNCHANGED)
# ============================================================
HEADERS = {
    "User-Agent": NWS_USER_AGENT,
    "Accept": "application/geo+json",
}

async def fetch_json(session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
    async with session.get(url, headers=HEADERS) as r:
        if r.status == 404:
            raise aiohttp.ClientResponseError(
                r.request_info, r.history, status=404
            )
        r.raise_for_status()
        return await r.json()

async def fetch_city(session: aiohttp.ClientSession, c: Dict[str, Any]) -> Dict[str, Any] | None:
    gid, x, y = c["grid_id"], c["grid_x"], c["grid_y"]
    base = f"https://api.weather.gov/gridpoints/{gid}/{x},{y}"

    try:
        data = await fetch_json(session, f"{base}/forecast/hourly")
        periods = data["properties"]["periods"][:12]
        source = "hourly"

    except aiohttp.ClientResponseError as e:
        if e.status != 404:
            raise

        try:
            data = await fetch_json(session, f"{base}/forecast")
            periods = data["properties"]["periods"][:12]
            source = "daily"

        except aiohttp.ClientResponseError as e2:
            if e2.status != 404:
                raise

            log.warning(
                "Skipping city %s — no forecast endpoints available (%s %s,%s)",
                c["city"], gid, x, y
            )
            return None

    return {
        "city": c["city"],
        "forecast_source": source,
        "periods": periods,
    }


async def fetch_zone(zone: str, cities: List[Dict[str, Any]]) -> Dict[str, Any]:
    async with aiohttp.ClientSession() as session:
        raw = await asyncio.gather(*(fetch_city(session, c) for c in cities))
    results = [r for r in raw if r is not None]

    return {"zone": zone, "cities": results}

# ============================================================
# Gemini Content (UNCHANGED)
# ============================================================
def generate_post(zone: str, nws_data: Dict[str, Any]) -> Dict[str, str]:
    prompt = f"""
Generate an SEO-optimized US weather blog post.

ZONE: {zone}

DATA:
{json.dumps(nws_data, indent=2)}

Rules:
- Use <h2> per city
- Mention alerts if present
- Friendly, professional tone
"""

    r = client.models.generate_content(
        model=MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_schema=SCHEMA,
            response_mime_type="application/json",
            temperature=0.5,
        ),
    )

    return json.loads(r.text)

# ============================================================
# Storage (UNCHANGED)
# ============================================================
def save_post(post: Dict[str, str], zone: str):
    OUTPUT_DIR.mkdir(exist_ok=True)
    slug = zone.lower().replace(" ", "-")
    fname = OUTPUT_DIR / f"{slug}.html"

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{post['title']}</title>
<meta name="description" content="{post['meta_description']}">
</head>
<body>
{post['content_html']}
</body>
</html>
"""

    fname.write_text(html, encoding="utf-8")
    log.info("Saved %s", fname)

# ============================================================
# Blogger Authentication & Publishing (MODIFIED)
# ============================================================
BLOGGER_SCOPE = ["https://www.googleapis.com/auth/blogger"]


def get_authenticated_service():
    """
    Handles the OAuth 2.0 flow. 
    Prioritizes reading credentials from a standard JSON token file,
    falling back to interactive flow if run locally and needed.
    """
    creds = None
    
    # 1. Try to load credentials from a standard JSON token file 
    if TOKEN_FILE.exists():
        log.info("Attempting to load credentials from standard JSON file: %s", TOKEN_FILE)
        try:
            # Credentials.from_authorized_user_file reads plain JSON, NOT pickled object
            creds = Credentials.from_authorized_user_file(
                TOKEN_FILE, BLOGGER_SCOPE
            )
        except Exception as e:
            # If the file exists but is corrupt or in the wrong format, log and proceed
            log.warning("Could not load credentials from JSON file: %s. Proceeding to interactive flow (or refresh).", e)

    # 2. If no valid credentials, or they are expired, refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh token automatically if possible
            log.info("Refreshing Blogger access token...")
            creds.refresh(Request())
        else:
            # Interactive authentication (MUST be run locally once)
            log.warning("Starting interactive OAuth 2.0 flow. Run this script locally ONCE.")
            
            # This line will fail in a headless environment
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, BLOGGER_SCOPE
            )
            # Port 0 means the system picks a free port for the local server
            creds = flow.run_local_server(port=0)

        # 3. Save the new/refreshed credentials as standard JSON for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            log.info("Credentials saved as standard JSON to %s", TOKEN_FILE)

    # 4. Build the authorized service.
    return build('blogger', 'v3', credentials=creds)


def publish_post(post: Dict[str, str], blog_id: str):
    log.info("Attempting to publish post to Blogger...")
    
    try:
        # Get the service object, authorized via OAuth 2.0
        service = get_authenticated_service()
        
        # Construct the post body
        body = {
            'kind': 'blogger#post',
            'blog': {'id': blog_id},
            'title': post['title'],
            'content': post['content_html'],
        }
        
        # Insert/Publish the post (isDraft=False makes it live immediately)
        request = service.posts().insert(blogId=blog_id, body=body, isDraft=False)
        result = request.execute()
        
        log.info("Successfully published post: %s", result.get('url'))
        return result.get('url')

    except HttpError as e:
        log.error("Failed to publish post to Blogger (HTTP Error: %s).", e.resp.status)
        log.error("Response: %s", e.content.decode())
        log.error("Check: Is your 'token.json' file valid, and is the linked Google Account an author/admin on Blog ID: %s?", blog_id)
        if e.resp.status in [401, 403]:
             log.error("HINT: If running on GitHub Actions, ensure 'token.json' is correctly created from your GitHub Secret.")
    except Exception as e:
        log.error("An unexpected error occurred during publishing: %s", e)

# ============================================================
# Rotation (UNCHANGED)
# ============================================================
def next_zone() -> str:
    if not STATE_FILE.exists():
        return ZONE_ROTATION[0]

    last = STATE_FILE.read_text().strip()

    if not last or last not in ZONE_ROTATION:
        log.warning(
            "Invalid or empty zone state (%r), resetting rotation", last
        )
        return ZONE_ROTATION[0]

    i = ZONE_ROTATION.index(last)
    return ZONE_ROTATION[(i + 1) % len(ZONE_ROTATION)]


def save_state(zone: str):
    STATE_FILE.write_text(zone)

# ============================================================
# Main (UPDATED CALL)
# ============================================================
def main():
    zone = next_zone()
    log.info("Processing zone: %s", zone)

    nws = asyncio.run(fetch_zone(zone, NWS_ZONES[zone]["cities"]))
    post = generate_post(zone, nws)
    save_post(post, zone)
    save_state(zone)
    
    # --- UPDATED PUBLISHING LOGIC ---
    if PUBLISH:
        # The API key argument is removed
        publish_post(post, BLOG_ID)
    else:
        log.info("PUBLISH is set to false. Skipping Blogger API post.")
    # --- END UPDATED LOGIC ---

    log.info("Completed zone: %s", zone)

if __name__ == "__main__":
    main()