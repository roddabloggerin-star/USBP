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
BLOG_BASE_URL = env("BLOG_BASE_URL", required=True)
BLOG_ID = env("BLOG_ID", required=True)
NWS_USER_AGENT = env("NWS_USER_AGENT", required=True)
PUBLISH = env("PUBLISH", "false").lower() == "true"

OUTPUT_DIR = Path("output_posts")
STATE_FILE = Path(env("STATE_FILE", "last_posted_zone.txt"))

# ============================================================
# Gemini
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
# Zones (FULL LIST – UNCHANGED)
# ============================================================
NWS_ZONES = {
    "Southern Zone": {
        "cities": [
            {"city": "Atlanta, GA", "grid_id": "FFC", "grid_x": 90, "grid_y": 78},
            {"city": "Jacksonville, FL", "grid_id": "JAX", "grid_x": 79, "grid_y": 62},
            {"city": "Miami, FL", "grid_id": "MFL", "grid_x": 73, "grid_y": 54},
            {"city": "Tampa, FL", "grid_id": "TBW", "grid_x": 67, "grid_y": 71},
            {"city": "Orlando, FL", "grid_id": "MLB", "grid_x": 58, "grid_y": 75},
            {"city": "Birmingham, AL", "grid_id": "BMX", "grid_x": 52, "grid_y": 79},
            {"city": "New Orleans, LA", "grid_id": "LIX", "grid_x": 94, "grid_y": 78},
            {"city": "Houston, TX", "grid_id": "HGX", "grid_x": 73, "grid_y": 80},
            {"city": "San Antonio, TX", "grid_id": "EWX", "grid_x": 105, "grid_y": 61},
            {"city": "Dallas, TX", "grid_id": "FWD", "grid_x": 71, "grid_y": 99},
            {"city": "Austin, TX", "grid_id": "EWX", "grid_x": 100, "grid_y": 80},
            {"city": "Oklahoma City, OK", "grid_id": "OUN", "grid_x": 80, "grid_y": 107},
            {"city": "Memphis, TN", "grid_id": "MEG", "grid_x": 78, "grid_y": 58},
            {"city": "Nashville, TN", "grid_id": "OHX", "grid_x": 50, "grid_y": 81},
            {"city": "Louisville, KY", "grid_id": "LMK", "grid_x": 55, "grid_y": 71},
        ]
    }
}

ZONE_ROTATION = list(NWS_ZONES.keys())

# ============================================================
# NWS Fetching (ASYNC + FALLBACK)
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

async def fetch_city(session: aiohttp.ClientSession, c: Dict[str, Any]) -> Dict[str, Any]:
    gid, x, y = c["grid_id"], c["grid_x"], c["grid_y"]
    base = f"https://api.weather.gov/gridpoints/{gid}/{x},{y}"

    try:
        data = await fetch_json(session, f"{base}/forecast/hourly")
        periods = data["properties"]["periods"][:12]
        source = "hourly"
    except aiohttp.ClientResponseError:
        data = await fetch_json(session, f"{base}/forecast")
        periods = data["properties"]["periods"][:12]
        source = "daily"

    return {
        "city": c["city"],
        "forecast_source": source,
        "periods": periods,
    }

async def fetch_zone(zone: str, cities: List[Dict[str, Any]]) -> Dict[str, Any]:
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*(fetch_city(session, c) for c in cities))
    return {"zone": zone, "cities": results}

# ============================================================
# Gemini Content
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
# Storage
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
# Rotation
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
# Main
# ============================================================
def main():
    zone = next_zone()
    log.info("Processing zone: %s", zone)

    nws = asyncio.run(fetch_zone(zone, NWS_ZONES[zone]["cities"]))
    post = generate_post(zone, nws)
    save_post(post, zone)
    save_state(zone)

    log.info("Completed zone: %s", zone)

if __name__ == "__main__":
    main()
