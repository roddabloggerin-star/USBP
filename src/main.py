#!/usr/bin/env python3
"""
USA Weather Blogger – Programmatic SEO Engine (1-Request Limit)
Python 3.12 / GitHub Actions Safe
============================================================
Features Included:
- **Model:** Uses 'gemini-3-flash' for superior structured output.
- **API Efficiency:** Implements the Mega-Prompt Strategy (1 Gemini request per run).
- **Scaling:** City-Level Rotation (5 cities per run) via 'state.txt' file. <-- ADJUSTED
- **Evergreen Content:** Blogger 'Search and Update' logic for all posts/pages.
- **Topical Authority:** Programmatically generated City Hub Pages for internal linking.
============================================================
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
import pickle
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

# --- API Keys and Config ---
GEMINI_API_KEY = env("GEMINI_API_KEY", required=True)
BLOG_ID = env("BLOG_ID", required=True)
CREDENTIALS_FILE = env("CREDENTIALS_FILE", "client_secret.json", required=True)
TOKEN_FILE = Path(env("TOKEN_FILE", "token.pickle"))
PUBLISH = env("PUBLISH", "False").lower() in ('true', '1', 't')
STATE_FILE = Path(env("STATE_FILE", "state.txt")) # Path to store the index of the last processed city

# --- Programmatic SEO Config ---
CITIES_PER_RUN = 5 # REDUCED to 5 to avoid Blogger API invisible rate limits.
SCOPES = ['https://www.googleapis.com/auth/blogger']
NWS_BASE_URL = "https://api.weather.gov/alerts/active?point={lat},{lon}"


# NWS Zones and a selection of cities (used for rotation)
NWS_ZONES = {
    "NWS_EAST_COAST_NORTHEAST": {
        "cities": [
            {"city": "New York, NY", "lat": 40.7128, "lon": -74.0060, "nws_url": "https://www.weather.gov/okx/"},
            {"city": "Boston, MA", "lat": 42.3601, "lon": -71.0589, "nws_url": "https://www.weather.gov/box/"},
            {"city": "Philadelphia, PA", "lat": 39.9526, "lon": -75.1652, "nws_url": "https://www.weather.gov/phi/"},
            {"city": "Baltimore, MD", "lat": 39.2904, "lon": -76.6122, "nws_url": "https://www.weather.gov/lwx/"},
            {"city": "Providence, RI", "lat": 41.8240, "lon": -71.4128, "nws_url": "https://www.weather.gov/box/"},
            {"city": "Buffalo, NY", "lat": 42.8864, "lon": -78.8784, "nws_url": "https://www.weather.gov/buf/"},
            {"city": "Portland, ME", "lat": 43.6591, "lon": -70.2568, "nws_url": "https://www.weather.gov/gyx/"},
            {"city": "Newark, NJ", "lat": 40.7357, "lon": -74.1724, "nws_url": "https://www.weather.gov/okx/"},
            {"city": "Hartford, CT", "lat": 41.7658, "lon": -72.6734, "nws_url": "https://www.weather.gov/okx/"},
            {"city": "Pittsburgh, PA", "lat": 40.4406, "lon": -79.9959, "nws_url": "https://www.weather.gov/pbz/"},
            {"city": "Richmond, VA", "lat": 37.5407, "lon": -77.4360, "nws_url": "https://www.weather.gov/akq/"},
            {"city": "Charleston, SC", "lat": 32.7765, "lon": -79.9311, "nws_url": "https://www.weather.gov/chs/"},
            {"city": "Savannah, GA", "lat": 32.0835, "lon": -81.0998, "nws_url": "https://www.weather.gov/chs/"},
            {"city": "Raleigh, NC", "lat": 35.7796, "lon": -78.6382, "nws_url": "https://www.weather.gov/rah/"},
            {"city": "Wilmington, DE", "lat": 39.7391, "lon": -75.5398, "nws_url": "https://www.weather.gov/phi/"},
        ]
    },
    "NWS_WEST_COAST_PACIFIC": {
        "cities": [
            {"city": "Los Angeles, CA", "lat": 34.0522, "lon": -118.2437, "nws_url": "https://www.weather.gov/los/"},
            {"city": "San Francisco, CA", "lat": 37.7749, "lon": -122.4194, "nws_url": "https://www.weather.gov/mtr/"},
            {"city": "Seattle, WA", "lat": 47.6062, "lon": -122.3321, "nws_url": "https://www.weather.gov/sew/"},
            {"city": "San Diego, CA", "lat": 32.7157, "lon": -117.1611, "nws_url": "https://www.weather.gov/sgx/"},
            {"city": "Portland, OR", "lat": 45.5051, "lon": -122.6750, "nws_url": "https://www.weather.gov/pqr/"},
            {"city": "Las Vegas, NV", "lat": 36.1716, "lon": -115.1391, "nws_url": "https://www.weather.gov/vef/"},
            {"city": "Sacramento, CA", "lat": 38.5816, "lon": -121.4944, "nws_url": "https://www.weather.gov/sto/"},
            {"city": "Fresno, CA", "lat": 36.7468, "lon": -119.7726, "nws_url": "https://www.weather.gov/hnx/"},
            {"city": "Anchorage, AK", "lat": 61.2181, "lon": -149.9003, "nws_url": "https://www.weather.gov/arh/"},
            {"city": "Honolulu, HI", "lat": 21.3069, "lon": -157.8583, "nws_url": "https://www.weather.gov/hfo/"},
            {"city": "Reno, NV", "lat": 39.5296, "lon": -119.8138, "nws_url": "https://www.weather.gov/rev/"},
            {"city": "Boise, ID", "lat": 43.6150, "lon": -116.2024, "nws_url": "https://www.weather.gov/boi/"},
            {"city": "Spokane, WA", "lat": 47.6588, "lon": -117.4260, "nws_url": "https://www.weather.gov/otx/"},
            {"city": "Eugene, OR", "lat": 44.0521, "lon": -123.0868, "nws_url": "https://www.weather.gov/pqr/"},
            {"city": "San Jose, CA", "lat": 37.3382, "lon": -121.8863, "nws_url": "https://www.weather.gov/mtr/"},
        ]
    },
    "NWS_MIDWEST_GREAT_LAKES": {
        "cities": [
            {"city": "Chicago, IL", "lat": 41.8781, "lon": -87.6298, "nws_url": "https://www.weather.gov/lot/"},
            {"city": "Detroit, MI", "lat": 42.3314, "lon": -83.0458, "nws_url": "https://www.weather.gov/dtx/"},
            {"city": "Indianapolis, IN", "lat": 39.7684, "lon": -86.1580, "nws_url": "https://www.weather.gov/ind/"},
            {"city": "Columbus, OH", "lat": 39.9612, "lon": -82.9988, "nws_url": "https://www.weather.gov/iln/"},
            {"city": "Milwaukee, WI", "lat": 43.0389, "lon": -87.9065, "nws_url": "https://www.weather.gov/mkx/"},
            {"city": "Cleveland, OH", "lat": 41.4993, "lon": -81.6944, "nws_url": "https://www.weather.gov/cle/"},
            {"city": "Minneapolis, MN", "lat": 44.9778, "lon": -93.2650, "nws_url": "https://www.weather.gov/mpx/"},
            {"city": "St. Louis, MO", "lat": 38.6270, "lon": -90.1994, "nws_url": "https://www.weather.gov/lsx/"},
            {"city": "Cincinnati, OH", "lat": 39.1031, "lon": -84.5120, "nws_url": "https://www.weather.gov/iln/"},
            {"city": "Kansas City, MO", "lat": 39.0997, "lon": -94.5786, "nws_url": "https://www.weather.gov/eax/"},
            {"city": "Omaha, NE", "lat": 41.2565, "lon": -95.9345, "nws_url": "https://www.weather.gov/oax/"},
            {"city": "Wichita, KS", "lat": 37.6877, "lon": -97.3300, "nws_url": "https://www.weather.gov/ict/"},
            {"city": "Grand Rapids, MI", "lat": 42.9634, "lon": -85.6681, "nws_url": "https://www.weather.gov/grr/"},
            {"city": "Madison, WI", "lat": 43.0731, "lon": -89.4012, "nws_url": "https://www.weather.gov/mkx/"},
            {"city": "Des Moines, IA", "lat": 41.5868, "lon": -93.6250, "nws_url": "https://www.weather.gov/dmx/"},
        ]
    },
    "NWS_SOUTH_TEXAS_MOUNTAIN": {
        "cities": [
            {"city": "Dallas, TX", "lat": 32.7767, "lon": -96.7970, "nws_url": "https://www.weather.gov/fwd/"},
            {"city": "Houston, TX", "lat": 29.7604, "lon": -95.3698, "nws_url": "https://www.weather.gov/hgx/"},
            {"city": "Phoenix, AZ", "lat": 33.4484, "lon": -112.0740, "nws_url": "https://www.weather.gov/psr/"},
            {"city": "Miami, FL", "lat": 25.7617, "lon": -80.1918, "nws_url": "https://www.weather.gov/mfl/"},
            {"city": "Atlanta, GA", "lat": 33.7490, "lon": -84.3880, "nws_url": "https://www.weather.gov/ffc/"},
            {"city": "Denver, CO", "lat": 39.7392, "lon": -104.9903, "nws_url": "https://www.weather.gov/bou/"},
            {"city": "Austin, TX", "lat": 30.2672, "lon": -97.7431, "nws_url": "https://www.weather.gov/ewx/"},
            {"city": "Orlando, FL", "lat": 28.5383, "lon": -81.3792, "nws_url": "https://www.weather.gov/mlb/"},
            {"city": "Salt Lake City, UT", "lat": 40.7608, "lon": -111.8910, "nws_url": "https://www.weather.gov/slc/"},
            {"city": "San Antonio, TX", "lat": 29.4241, "lon": -98.4936, "nws_url": "https://www.weather.gov/ewx/"},
            {"city": "Nashville, TN", "lat": 36.1627, "lon": -86.7816, "nws_url": "https://www.weather.gov/ohx/"},
            {"city": "Albuquerque, NM", "lat": 35.0844, "lon": -106.6504, "nws_url": "https://www.weather.gov/abq/"},
            {"city": "Tucson, AZ", "lat": 32.2217, "lon": -110.9265, "nws_url": "https://www.weather.gov/twc/"},
            {"city": "Jacksonville, FL", "lat": 30.3322, "lon": -81.6557, "nws_url": "https://www.weather.gov/jax/"},
            {"city": "Oklahoma City, OK", "lat": 35.4676, "lon": -97.5164, "nws_url": "https://www.weather.gov/oun/"},
        ]
    }
}


# ============================================================
# Gemini (MODEL AND SCHEMA)
# ============================================================
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-3-flash" # Use the new Gemini 3 Flash model

# The individual post structure (now an object within the array)
PROGRAMMATIC_POST_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "city": types.Schema(type=types.Type.STRING, description="The City Name used to generate this specific post (e.g., 'New York, NY')."),
        "title": types.Schema(type=types.Type.STRING, description="The SEO-optimized, query-based post title."),
        "meta_description": types.Schema(type=types.Type.STRING, description="A unique meta description for the post."),
        "content_html": types.Schema(type=types.Type.STRING, description="The full post content in HTML format, including H2 tags and a link to the NWS source."),
        "slug": types.Schema(type=types.Type.STRING, description="The programmatic evergreen URL slug."), 
    },
    required=["city", "title", "meta_description", "content_html", "slug"],
)

# The Mega-Post Schema (the single response from Gemini)
MEGA_POST_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "posts": types.Schema(
            type=types.Type.ARRAY,
            items=PROGRAMMATIC_POST_SCHEMA,
            description=f"An array containing {CITIES_PER_RUN} distinct, fully-formed programmatic posts."
        )
    },
    required=["posts"],
)


# ============================================================
# Programmatic Configuration 
# ============================================================
# This is the single, high-value forecast post type generated daily per city.
ACTIVE_POST_TYPE = {
    "type": "7_day_outlook",
    "title_template": "{city} 7-Day Weather Outlook and Extended Forecast Analysis",
    "slug_template": "{city_slug}-7-day-outlook",
    "data_key": "daily_periods",
    "prompt_intent": "a comprehensive 7-day weather outlook, detailing high/low temperatures, general conditions, and long-range trends. The final HTML post must be between 500-700 words and include a visible link to the NWS source.",
}

# Hub Page Definition
HUB_PAGE_TYPE = {
    "type": "city_hub",
    "title_template": "{city} Weather Forecast Center & Local Outlooks",
    "slug_template": "weather/{city_slug}",
}

# Define ALL programmatic post types (for the Hub Page to link to)
ALL_PROGRAMMATIC_TYPES = [
    ACTIVE_POST_TYPE, # 7_day_outlook (the one we generate daily)
    {
        "type": "24_hour_hourly",
        "title_template": "{city} Weather Forecast: Next 24 Hours Hourly Breakdown",
        "slug_template": "{city_slug}-weather-next-24-hours",
    },
    {
        "type": "snow_rain_chances",
        "title_template": "{city} Precipitation Chances: Today's Rain and Snow Forecast",
        "slug_template": "{city_slug}-rain-snow-chances-today",
    }
]

# Combine all cities into a single list for easy indexing and rotation
ALL_CITIES_LIST = [city_data for zone in NWS_ZONES.values() for city_data in zone["cities"]]
TOTAL_CITIES = len(ALL_CITIES_LIST) # Should be 60

# ============================================================
# Helper Functions
# ============================================================

def create_slug(text: str) -> str:
    """Creates a basic SEO-friendly slug from text."""
    # Note: Blogger handles non-ASCII characters, but this ensures a clean, predictable URL part
    return text.lower().replace(",", "").replace(" ", "-").replace(".", "").replace("'", "")

def save_post(post: Dict[str, str], filename_prefix: str):
    """Saves the generated content to a local JSON file for backup."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    slug = create_slug(filename_prefix)
    filename = Path(f"posts/{today}_{slug}.json")
    filename.parent.mkdir(exist_ok=True)
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(post, f, ensure_ascii=False, indent=2)
        log.info("Post content saved to %s", filename)
    except Exception as e:
        log.error("Failed to save post for %s: %s", filename_prefix, e)


# ============================================================
# State Management (Rotation)
# ============================================================

def get_city_batch() -> tuple[List[Dict[str, Any]], int]:
    """Determines which 5 cities to process in the current run and returns the current index."""
    try:
        if STATE_FILE.exists():
            start_index = int(STATE_FILE.read_text().strip())
        else:
            start_index = 0
    except Exception:
        start_index = 0
        log.warning("Could not read state file, starting from index 0.")

    # Calculate the batch slice
    end_index = start_index + CITIES_PER_RUN
    
    if end_index <= TOTAL_CITIES:
        # Simple slice
        city_batch = ALL_CITIES_LIST[start_index:end_index]
    else:
        # Wrap around 
        city_batch = ALL_CITIES_LIST[start_index:] + ALL_CITIES_LIST[:end_index % TOTAL_CITIES]
        
    log.info("Processing cities starting from index %d. Batch size: %d", start_index, len(city_batch))
    return city_batch, start_index


def save_next_city_index(current_start_index: int):
    """Saves the starting index for the next run."""
    next_start_index = (current_start_index + CITIES_PER_RUN) % TOTAL_CITIES
    STATE_FILE.write_text(str(next_start_index))
    log.info("Saved next run start index: %d", next_start_index)

# ============================================================
# NWS API Calls
# ============================================================

async def fetch_json(session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, Any]]:
    """Generic async JSON fetcher with error handling."""
    try:
        async with session.get(url, headers={'Accept': 'application/geo+json'}) as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientError as e:
        log.error("HTTP Error fetching %s: %s", url, e)
    except Exception as e:
        log.error("Unexpected error fetching %s: %s", url, e)
    return None

async def fetch_city(session: aiohttp.ClientSession, city_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fetches full forecast data for a single city."""
    city_name = city_info["city"]
    lat, lon = city_info["lat"], city_info["lon"]
    
    # 1. Get the forecast grid points
    points_url = f"https://api.weather.gov/points/{lat},{lon}"
    points_data = await fetch_json(session, points_url)
    
    if not points_data or 'properties' not in points_data:
        log.warning("Could not get grid points for %s.", city_name)
        return None

    properties = points_data['properties']
    city_data = {
        "city": city_name,
        "nws_url": city_info["nws_url"],
        "slug": create_slug(city_name),
    }

    # 2. Fetch required forecast data (Hourly and Daily are needed for the Hub Page's links/data proxy)
    
    # Hourly forecast
    hourly_forecast_url = properties.get('forecastHourly')
    if hourly_forecast_url:
        hourly_data = await fetch_json(session, hourly_forecast_url)
        if hourly_data and 'periods' in hourly_data['properties']:
            city_data["hourly_periods"] = hourly_data['properties']['periods'][:24]
    
    # Daily forecast (used for the ACTIVE_POST_TYPE)
    daily_forecast_url = properties.get('forecast')
    if daily_forecast_url:
        daily_data = await fetch_json(session, daily_forecast_url)
        if daily_data and 'periods' in daily_data['properties']:
            city_data["daily_periods"] = daily_data['properties']['periods']
            
    # Alerts/Chances proxy
    alerts_url = properties.get('alerts')
    if alerts_url:
        alerts_data = await fetch_json(session, alerts_url)
        if alerts_data and alerts_data.get('features'):
            city_data["alerts"] = alerts_data['features']
        else:
            city_data["alerts"] = []

    # Only return if essential data for the Mega-Prompt is available
    if ACTIVE_POST_TYPE["data_key"] in city_data: 
        log.info("Successfully fetched data for %s.", city_name)
        return city_data
    
    return None

async def fetch_city_batch(cities_to_fetch: List[Dict[str, Any]]):
    """
    Runs the asynchronous fetch_city function for a batch of cities.
    """
    async with aiohttp.ClientSession(trust_env=True) as session:
        # The gather function runs all fetch_city calls concurrently
        raw = await asyncio.gather(*(fetch_city(session, c) for c in cities_to_fetch))
    # Filter out any cities that failed to fetch data
    return [r for r in raw if r is not None]


# ============================================================
# Gemini Content (Mega-Prompt Strategy - 1 Request)
# ============================================================

def generate_mega_post(city_data_list: List[Dict[str, Any]], post_type: Dict[str, str]) -> List[Dict[str, str]] | None:
    """
    Generates an array of programmatic posts using a single Gemini API call.
    """
    
    cities_for_prompt = []
    
    # 1. Prepare data structure for the prompt
    for city_data in city_data_list:
        city_name = city_data["city"]
        city_slug = city_data["slug"]
        
        # Prepare final SEO fields
        title = post_type["title_template"].format(city=city_name)
        slug = post_type["slug_template"].format(city_slug=city_slug)
        
        # Ensure data is present
        data_key = post_type["data_key"]
        if not city_data.get(data_key):
            continue
            
        cities_for_prompt.append({
            "city_name": city_name,
            "title": title,
            "slug": slug,
            "nws_url": city_data["nws_url"],
            "forecast_data": city_data[data_key]
        })
    
    if not cities_for_prompt:
        log.warning("No cities had sufficient data to include in the Mega-Prompt.")
        return None
        
    
    # 2. Construct the single, detailed Mega-Prompt
    prompt = f"""
***TASK: Generate {len(cities_for_prompt)} Programmatic SEO Posts in a Single JSON Response***

**CONTEXT:** You must generate a highly specific, focused weather forecast blog post for each city provided below. All posts must follow the same structure and adhere to the strict SEO requirements.

**POST INTENT (FOR ALL POSTS):** {post_type["prompt_intent"]}

**STRICT GENERATION RULES (MUST BE FOLLOWED FOR EVERY POST):**
1.  **Word Count:** The final HTML content for EACH post MUST be between **500 and 700 words**.
2.  **Linking:** You MUST include a hyperlink to the city's specific `nws_url` provided. Place this link prominently in the first paragraph using standard HTML anchor tags (`<a href="[NWS URL]">Official NWS Source for [City Name]</a>`). Use the exact URL and City Name provided in the JSON data for that specific post.
3.  **Title/Slug:** You MUST use the exact `title` and `slug` provided for each city in the final JSON output.
4.  **HTML Structure:** Use clean HTML: `<h2>` for subheadings, and `<p>` for paragraphs. Do not use markdown formatting.
5.  **Data Analysis:** Directly analyze and reference the `forecast_data` provided for each city to generate the content.

**CITIES AND DATA TO PROCESS:**
{json.dumps(cities_for_prompt, indent=2)}

**OUTPUT FORMAT:**
- Your entire response MUST be a single JSON object matching the `MEGA_POST_SCHEMA`.
- The 'posts' array MUST contain {len(cities_for_prompt)} objects, one for each city processed.
"""

    log.info("Making single Gemini request to generate %d posts using %s...", len(cities_for_prompt), MODEL)
    
    # 3. Call the API
    try:
        r = client.models.generate_content(
            model=MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_schema=MEGA_POST_SCHEMA,
                response_mime_type="application/json",
                temperature=0.7, 
            ),
        )
        
        # 4. Parse the array of posts
        mega_output = json.loads(r.text)
        
        if 'posts' not in mega_output or not isinstance(mega_output['posts'], list):
            log.error("Gemini output was not in the expected format. Raw output: %s", r.text[:200])
            return None
            
        log.info("Successfully generated %d posts from 1 request.", len(mega_output['posts']))
        return mega_output['posts']
        
    except Exception as e:
        log.error("Gemini content generation failed for Mega-Prompt: %s", e)
        return None

# ============================================================
# Hub Page Generation (Internal Linking Architecture)
# ============================================================

def generate_city_hub_html(city_name: str, city_slug: str) -> Dict[str, str]:
    """
    Programmatically generates the HTML content for a City Hub Page (Zero API Call).
    This creates the essential internal linking structure.
    """
    
    # 1. Start HTML content
    title = HUB_PAGE_TYPE["title_template"].format(city=city_name)
    content_html = f"<h1>{title}</h1>"
    content_html += f"<p>Welcome to your comprehensive weather resource for {city_name}. Use the links below for the latest, most detailed forecast analysis, updated daily:</p>"
    
    # 2. Add internal links to all programmatic posts for this city
    content_html += "<h2>Detailed Forecasts and Outlooks</h2><ul>"
    
    for pt in ALL_PROGRAMMATIC_TYPES:
        # Build the exact slug/path that the forecast post will use
        forecast_slug = pt["slug_template"].format(city_slug=city_slug)
        forecast_title = pt["title_template"].format(city=city_name)
        
        # Link using the relative path, assuming your Blogger permalink structure is configured
        content_html += f"<li><a href='/{forecast_slug}'>{forecast_title}</a></li>"

    content_html += "</ul>"
    
    # 3. Add Evergreen/Local Authority Content (Static text)
    content_html += "<h2>Local Weather Authority</h2>"
    content_html += f"<p>Our forecast analysis for the {city_name} metropolitan area is derived from official National Weather Service (NWS) data, providing accurate and localized information. By updating these pages daily, we ensure you always have the most relevant long-range trends, hourly details, and severe weather watches for {city_name}.</p>"
    
    # 4. Return the full structure
    return {
        "title": title,
        "meta_description": f"The definitive weather forecast hub for {city_name}. Get 7-day, hourly, and precipitation analysis updated daily.",
        "content_html": content_html,
        "slug": HUB_PAGE_TYPE["slug_template"].format(city_slug=city_slug),
        "city": city_name, 
    }


# ============================================================
# Blogger API (Search and Update Logic)
# ============================================================

def get_authenticated_service():
    """Authenticates with Google using OAuth 2.0 flow."""
    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return build('blogger', 'v3', credentials=creds)


def find_existing_post(service, blog_id: str, title: str) -> Optional[Dict[str, Any]]:
    """
    Searches the Blogger posts for a post with a matching title.
    """
    try:
        log.info("Searching for existing post with title: '%s'", title)
        page_token = None
        
        while True:
            request = service.posts().list(
                blogId=blog_id, 
                fetchBodies=False, 
                pageToken=page_token
            )
            response = request.execute()
            
            for post in response.get('items', []):
                # Match on the exact title for programmatic posts
                if post.get('title') == title:
                    log.info("Found existing post (ID: %s, URL: %s).", post['id'], post['url'])
                    return post
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break

        return None
        
    except HttpError as e:
        log.error("Failed to search posts (HTTP Error: %s).", e.resp.status)
        return None
    except Exception as e:
        log.error("An unexpected error occurred during post search: %s", e)
        return None


def publish_post(post: Dict[str, str], blog_id: str):
    """
    Implements the Evergreen URL logic: Search, then Update or Insert.
    This handles both forecast posts and hub pages.
    """
    service = get_authenticated_service()
    post_url = None
    
    body = {
        'kind': 'blogger#post',
        'blog': {'id': blog_id},
        'title': post['title'],
        'content': post['content_html'],
        # slug_hint might be ignored by Blogger but included for completeness
        'url_slug_hint': post['slug'] 
    }

    # Step 1: Search for the existing post
    existing_post = find_existing_post(service, blog_id, post['title'])

    try:
        if existing_post:
            # Step 2: Update the existing post (Evergreen URL)
            post_id = existing_post['id']
            log.info("Updating existing post ID %s to refresh content.", post_id)
            
            request = service.posts().update(
                blogId=blog_id, 
                postId=post_id, 
                body=body,
            )
            result = request.execute()
            post_url = result.get('url')
            log.info("Successfully updated post. Evergreen URL: %s", post_url)

        else:
            # Step 3: Insert a new post
            log.info("No existing post found. Inserting a new programmatic post.")
            
            request = service.posts().insert(
                blogId=blog_id, 
                body=body, 
                isDraft=False
            )
            result = request.execute()
            post_url = result.get('url')
            log.info("Successfully published new post: %s", post_url)
            
    except HttpError as e:
        log.error("Failed to update/insert post (HTTP Error: %s).", e.resp.status)
    except Exception as e:
        log.error("An unexpected error occurred during publishing: %s", e)
        
    return post_url


def publish_hub_page(hub_page_data: Dict[str, str], blog_id: str):
    """
    Wrapper for publishing the Hub Page, ensuring its URL is evergreen.
    """
    log.info("Attempting to publish/update City Hub Page for: %s", hub_page_data['city'])
    return publish_post(hub_page_data, blog_id)


# ============================================================
# Main Execution
# ============================================================
def main():
    log.info("Starting Programmatic SEO Weather Engine (1-Request Limit Mode).")
    
    # Step 1: Get the current starting index and the batch of cities to process
    city_batch_info, current_start_index = get_city_batch()
    
    # Step 2: Fetch data for *only* the cities in the current batch
    all_city_data = asyncio.run(fetch_city_batch(city_batch_info))
    
    if not all_city_data:
        log.warning("No data fetched for the current city batch. Skipping content generation.")
        save_next_city_index(current_start_index)
        return

    # Step 3: Single Gemini API Call (1 Request made here)
    posts_to_publish = generate_mega_post(all_city_data, ACTIVE_POST_TYPE)
    
    if not posts_to_publish:
        log.warning("No content generated from the single Mega-Prompt. Exiting.")
        save_next_city_index(current_start_index)
        return

    log.info("Generated %d total posts from 1 API request. Proceeding to publish...", len(posts_to_publish))
    
    # Step 4: Publish all generated posts and Hub Pages for the current batch
    for city_data in all_city_data:
        city_name = city_data['city']
        city_slug = create_slug(city_name)
        
        # A. Publish/Update the Programmatic Forecast Post 
        forecast_post = next((p for p in posts_to_publish if p['city'] == city_name), None)
        
        if forecast_post:
            save_post(forecast_post, city_name + "-forecast") 
            if PUBLISH:
                publish_post(forecast_post, BLOG_ID)
        
        # B. Generate and Publish/Update the City Hub Page
        hub_page_data = generate_city_hub_html(city_name, city_slug)
        save_post(hub_page_data, city_name + "-hub")
        
        if PUBLISH:
            publish_hub_page(hub_page_data, BLOG_ID)
        else:
            log.info("PUBLISH is set to false. Skipping Blogger API posts for %s.", city_name)


    # Step 5: Update the rotation state for the next run
    save_next_city_index(current_start_index)
    
    log.info("Completed all processing. Programmatic Engine finished.")

if __name__ == "__main__":
    main()