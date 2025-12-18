# ==============================================================================
# main.py — SINGLE FILE, HARDENED, PRODUCTION VERSION (FULL ZONES)
# ==============================================================================

import os
import re
import json
import time
import html
import asyncio
import random
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from urllib.parse import quote

import requests
import aiohttp
from dotenv import load_dotenv

from google import genai
from google.genai import types, errors
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ------------------------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("weatherbot")

# ------------------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------------------
load_dotenv()

def _req(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

def _opt(name: str, default=None):
    return os.getenv(name, default)

@dataclass(frozen=True)
class AppConfig:
    gemini_api_key: str
    blog_id: str
    blog_base_url: str
    nws_user_agent: str
    publish: bool
    client_secrets_file: str

CONFIG = AppConfig(
    gemini_api_key=_req("GEMINI_API_KEY"),
    blog_id=_req("BLOG_ID"),
    blog_base_url=_req("BLOG_BASE_URL").rstrip("/"),
    nws_user_agent=_req("NWS_USER_AGENT"),
    publish=_opt("PUBLISH", "false").lower() == "true",
    client_secrets_file=_opt("CLIENT_SECRETS_FILE", "client_secrets.json"),
)

# ------------------------------------------------------------------------------
# CONSTANTS
# ------------------------------------------------------------------------------
STATE_FILE = "last_posted_zone.txt"
TOKEN_FILE = "token.json"
OUTPUT_DIR = Path("output_posts")
INDEX_FILE = OUTPUT_DIR / "posts_index.json"

PLACEHOLDER_IMAGE_URL = "https://www.weather.gov/wwamap/png/US.png"
IMAGE_MARKER = "[[IMAGE_TAG_HERE]]"
DISCLAIMER_MARKER = "[[DISCLAIMER_HERE]]"

DISCLAIMER_HTML = (
    "<p style='font-size:0.8em;color:#777'>"
    "Data source: National Weather Service. "
    "<a href='https://www.weather.gov/' target='_blank'>weather.gov</a>"
    "</p>"
)

# ------------------------------------------------------------------------------
# ZONES (FULL LIST)
# ------------------------------------------------------------------------------
NWS_ZONES = {
    "Eastern Zone": {
        "cities": [
            {"city": "Boston, MA", "grid_id": "BOX", "grid_x": 71, "grid_y": 90},
            {"city": "New York, NY", "grid_id": "OKX", "grid_x": 33, "grid_y": 36},
            {"city": "Philadelphia, PA", "grid_id": "PHI", "grid_x": 71, "grid_y": 48},
            {"city": "Washington, D.C.", "grid_id": "LWX", "grid_x": 88, "grid_y": 128},
            {"city": "Raleigh, NC", "grid_id": "RAH", "grid_x": 51, "grid_y": 60},
        ],
    },
    "Southern Zone": {
        "cities": [
            {"city": "Atlanta, GA", "grid_id": "FFC", "grid_x": 90, "grid_y": 78},
            {"city": "Miami, FL", "grid_id": "MFL", "grid_x": 73, "grid_y": 54},
            {"city": "Houston, TX", "grid_id": "HGX", "grid_x": 73, "grid_y": 80},
            {"city": "Dallas, TX", "grid_id": "FWD", "grid_x": 71, "grid_y": 99},
            {"city": "New Orleans, LA", "grid_id": "LIX", "grid_x": 94, "grid_y": 78},
        ],
    },
    "Central Zone": {
        "cities": [
            {"city": "Chicago, IL", "grid_id": "LOT", "grid_x": 68, "grid_y": 70},
            {"city": "Detroit, MI", "grid_id": "DTX", "grid_x": 55, "grid_y": 70},
            {"city": "Cleveland, OH", "grid_id": "CLE", "grid_x": 84, "grid_y": 50},
            {"city": "St. Louis, MO", "grid_id": "LSX", "grid_x": 76, "grid_y": 59},
            {"city": "Minneapolis, MN", "grid_id": "MPX", "grid_x": 113, "grid_y": 42},
        ],
    },
    "Western Zone": {
        "cities": [
            {"city": "Los Angeles, CA", "grid_id": "LOX", "grid_x": 155, "grid_y": 45},
            {"city": "San Francisco, CA", "grid_id": "MTR", "grid_x": 85, "grid_y": 105},
            {"city": "Seattle, WA", "grid_id": "SEW", "grid_x": 118, "grid_y": 132},
            {"city": "Phoenix, AZ", "grid_id": "PSR", "grid_x": 131, "grid_y": 127},
            {"city": "Denver, CO", "grid_id": "BOU", "grid_x": 67, "grid_y": 67},
        ],
    },
}

ZONE_ROTATION = list(NWS_ZONES.keys())

# ------------------------------------------------------------------------------
# UTILITIES
# ------------------------------------------------------------------------------
def safe_slug(text: str, max_len: int = 80) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    text = re.sub(r"\s+", "-", text)
    return text[:max_len] or "post"

def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)

# ------------------------------------------------------------------------------
# IMAGE
# ------------------------------------------------------------------------------
def build_image(zone: str) -> str:
    return (
        f"<img src='{PLACEHOLDER_IMAGE_URL}' "
        f"alt='{html.escape(zone)} Weather Map' "
        "style='max-width:100%;border-radius:8px'>"
    )

# ------------------------------------------------------------------------------
# GEMINI
# ------------------------------------------------------------------------------
MODEL = "gemini-2.5-flash"

BLOG_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "title": types.Schema(type=types.Type.STRING),
        "meta_description": types.Schema(type=types.Type.STRING),
        "content_html": types.Schema(type=types.Type.STRING),
    },
    required=["title", "meta_description", "content_html"],
)

def generate_content(zone: str, nws: dict, image: str) -> Optional[dict]:
    client = genai.Client(api_key=CONFIG.gemini_api_key)
    prompt = json.dumps(nws, indent=2)

    for attempt in range(5):
        try:
            r = client.models.generate_content(
                model=MODEL,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    system_instruction=(
                        f"Generate a weather blog post. "
                        f"Include {IMAGE_MARKER} and {DISCLAIMER_MARKER}."
                    ),
                    response_schema=BLOG_SCHEMA,
                    response_mime_type="application/json",
                ),
            )
            data = json.loads(r.text)
            data["content_html"] = (
                data["content_html"]
                .replace(IMAGE_MARKER, image)
                .replace(DISCLAIMER_MARKER, DISCLAIMER_HTML)
            )
            return data
        except errors.APIError:
            time.sleep(2 ** attempt)
    return None

# ------------------------------------------------------------------------------
# NWS ASYNC
# ------------------------------------------------------------------------------
SEM = asyncio.Semaphore(5)

async def fetch_json(session, url):
    async with SEM:
        async with session.get(url, headers={"User-Agent": CONFIG.nws_user_agent}) as r:
            r.raise_for_status()
            return await r.json()

async def fetch_city(session, c):
    gid, x, y = c["grid_id"], c["grid_x"], c["grid_y"]
    alerts = await fetch_json(session, f"https://api.weather.gov/alerts/active?point={gid},{x},{y}")
    hourly = await fetch_json(session, f"https://api.weather.gov/gridpoints/{gid}/{x},{y}/forecast/hourly")
    return {"city": c["city"], "alerts": alerts.get("features", []), "hourly": hourly.get("properties", {}).get("periods", [])}

async def fetch_zone(zone: str, cities: list) -> dict:
    async with aiohttp.ClientSession() as s:
        data = await asyncio.gather(*(fetch_city(s, c) for c in cities))
    return {"zone": zone, "cities": data}

# ------------------------------------------------------------------------------
# STATE
# ------------------------------------------------------------------------------
def get_last_zone():
    return Path(STATE_FILE).read_text().strip() if Path(STATE_FILE).exists() else None

def save_last_zone(z):
    Path(STATE_FILE).write_text(z)

def get_next_zone():
    last = get_last_zone()
    if last not in ZONE_ROTATION:
        return ZONE_ROTATION[0]
    return ZONE_ROTATION[(ZONE_ROTATION.index(last) + 1) % len(ZONE_ROTATION)]

# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------
def main():
    zone = get_next_zone()
    log.info("Processing zone: %s", zone)

    nws = run_async(fetch_zone(zone, NWS_ZONES[zone]["cities"]))
    image = build_image(zone)

    payload = generate_content(zone, nws, image)
    if not payload:
        raise RuntimeError("Gemini generation failed")

    slug = safe_slug(payload["title"])
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / f"{slug}.html").write_text(payload["content_html"], encoding="utf-8")

    save_last_zone(zone)
    log.info("Completed zone: %s", zone)

if __name__ == "__main__":
    main()
# ==============================================================================
# End of main.py
# ==============================================================================

