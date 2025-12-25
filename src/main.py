#!/usr/bin/env python3
"""
USA Weather Blogger – HIGH-VOLUME EVERGREEN STRATEGY
Python 3.12 / GitHub Actions Safe

MAJOR MODIFICATIONS for Evergreen Strategy (Request #2):
1. **REMOVED Google Trends** for topic selection.
2. **NEW:** Implemented a fixed list of 400+ evergreen topics for systematic content generation.
3. **NEW:** State tracking now uses 'last_posted_index' to cycle through the 400+ topics (Strategy #9).
4. **FIX:** Implemented explicit style cycling (Guide, Emotional, Listicle) in the main loop to force title variety.
5. **FIX:** Removed unsupported argument in Blogger API for Archive Page update (already done).
6. **FIX:** Added colon stripping to filename generation to fix artifact upload error (already done).
"""

# ============================================================
# Imports & Setup
# ============================================================
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
# Removed: import pandas as pd, from pytrends.request import TrendReq
from dateutil.relativedelta import relativedelta

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.api_core import exceptions as gapi_exceptions 

# Blogger API Imports
from googleapiclient.discovery import build
from googleapiclient.http import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# ============================================================
# Logging & Environment
# ============================================================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("weatherbot")

load_dotenv()

def env(name: str, default=None, required=False):
    v = os.getenv(name, default)
    if required and not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

GEMINI_API_KEY = env("GEMINI_API_KEY", required=True)
BLOG_ID = env("BLOG_ID", required=True)

# STRATEGY #2: Post 4 times a day (Adjusted for 20 requests/day limit: 4 posts * 5 runs = 20 total)
POSTS_PER_RUN = int(env("POSTS_PER_RUN", 4)) 
PUBLISH = env("PUBLISH", "false").lower() == "true"

OUTPUT_DIR = Path("output_posts")
STATE_FILE = Path(env("STATE_FILE", "bot_state.json")) 

# Blogger Auth Files
TOKEN_FILE = Path(env("TOKEN_FILE", "token.json"))
CLIENT_SECRETS_FILE = Path(env("CLIENT_SECRETS_FILE", "client_secrets.json"))

# ============================================================
# Gemini Model, Schema, and Title Styles (FIX #4)
# ============================================================
client = genai.Client(
    api_key=GEMINI_API_KEY
)

MODEL_PREFERENCE = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]

SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "title": types.Schema(type=types.Type.STRING, description="The emotional, high-impact SEO title."),
        "meta_description": types.Schema(type=types.Type.STRING, description="A meta description optimized for high search CTR."),
        "content_html": types.Schema(type=types.Type.STRING, description="The complete blog post content in HTML format."),
        "labels": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description="5-10 SEO tags/labels for the post."),
    },
    required=["title", "meta_description", "content_html", "labels"],
)

# Define the three title styles to enforce variety (FIX #4)
TITLE_STYLES = [
    "Style 1 (Utility/Guide)",
    "Style 2 (Emotional/Shock)",
    "Style 3 (Listicle/Actionable)"
]

# ============================================================
# Evergreen Topic List (Strategy #9)
# ============================================================
# The full list of 400+ evergreen topics provided by the user, formatted for Python.
# Note: State-specific templates have been generalized (e.g., "[State]" -> "the USA") 
# to keep the list fixed and rotationally viable.
EVERGREEN_TOPICS = [
    # Group 1: The 4 Master Templates
    "The Complete Newcomer’s Guide to USA Weather: What to Expect Year-Round",
    "Severe Weather in the USA: The Most Common Risks and How to Prepare",
    "The Best Time to Visit the USA for Perfect Weather (A Month-by-Month Guide)",
    "Gardening in the USA: Understanding Hardiness Zones and Frost Dates",
    # Group 2: The "What Is...?" Dictionary (100 Posts) - Full List
    "What is a Derecho?", "What is a Supercell Thunderstorm?", "What is a Squall Line?", 
    "Microburst vs. Macroburst: What’s the Difference?", "Funnel Cloud vs. Tornado: How to Tell Them Apart", 
    "What is a Waterspout?", "Flash Flood vs. River Flood", "What is Storm Surge?", 
    "How does a Tsunami form?", "Hail: How does ice form in summer?", 
    "Cloud-to-Ground Lightning explained", "What causes Thunder?", "What is a Gust Front?", 
    "Wall Cloud identification guide", "Shelf Cloud identification guide", 
    "Mammatus Clouds: Are they dangerous?", "What is a Hook Echo on radar?", "What is a Bow Echo?", 
    "What is a Debris Ball on radar?", "The Enhanced Fujita (EF) Scale explained", 
    "The Saffir-Simpson Hurricane Scale explained", "What is a Tropical Depression?", 
    "What is a Tropical Storm?", "The Eye Wall: The most dangerous part of a hurricane", 
    "What is Landfall?", "What is the Polar Vortex?", "What is a Bomb Cyclone?", 
    "What is a Nor'easter?", "Lake Effect Snow explained", "What defines a Blizzard?", 
    "What is an Ice Storm?", "Freezing Rain vs. Sleet: The difference", "What is Graupel?", 
    "Black Ice: Why you can't see it", "What is a Frost Quake (Cryoseism)?", 
    "What is a Snow Squall?", "Thundersnow: Lightning in winter", "How is Wind Chill calculated?", 
    "What are Whiteout Conditions?", "Hoar Frost vs. Rime Ice", "What is an Alberta Clipper?", 
    "Hard Freeze vs. Light Freeze", "Winter Weather Advisory meaning", 
    "Winter Storm Warning meaning", "What is an Ice Jam?", "Why is Slush dangerous for driving?", 
    "What is Snowpack?", "How do Snow Drifts form?", "Sublimation: When snow vanishes without melting", 
    "What is a Wintry Mix?", "What is a Heat Dome?", "Heat Index vs. Real Temperature", 
    "What is Wet Bulb Temperature?", "The UV Index explained", "What is the Dew Point?", 
    "Relative Humidity explained", "What is an Ozone Action Day?", "What is a Temperature Inversion?", 
    "El Niño explained simply", "La Niña explained simply", "What is the Jet Stream?", 
    "High Pressure vs. Low Pressure Systems", "What is a Cold Front?", "What is a Warm Front?", 
    "What is a Stationary Front?", "What is an Occluded Front?", 
    "Barometric Pressure: How it predicts weather", "What are Trade Winds?", 
    "Santa Ana Winds explained", "Chinook Winds (Snow Eaters)", "The North American Monsoon", 
    "What is a Haboob?", "Fire Weather explained", "What is a Red Flag Warning?", 
    "Urban Heat Island Effect", "Cumulonimbus Clouds (The King of Clouds)", 
    "Cirrus Clouds (Mares' Tails)", "Stratus Clouds (The blanket)", 
    "Lenticular Clouds (UFO clouds)", "Kelvin-Helmholtz Clouds (Wave clouds)", 
    "Contrails vs. Chemtrails: The Science", "Fog vs. Mist: The difference", 
    "What is Radiation Fog?", "What is Advection Fog?", "How do Double Rainbows form?", 
    "What is a Sun Halo?", "What are Sun Dogs?", "The Aurora Borealis (Northern Lights)", 
    "What are Light Pillars?", "The Green Flash at sunset", "What is a Mirage?", 
    "Airglow: Why the night sky isn't black", "Noctilucent Clouds (Night shining)", 
    "Crepuscular Rays (God rays)", "Virga: Rain that never hits the ground", 
    "Petrichor: Why rain smells good", "What is a Blue Moon?", "What is a Harvest Moon?", 
    "Supermoon and its effect on tides", "What are King Tides?",
    # Group 3: Home & Lifestyle Solutions (100 Posts) - Full List
    "How to Identify Hail Damage on Shingles", "Wind Damage: When to Call a Roofer", 
    "Preventing Ice Dams in Gutters", "Best Siding Options for Humid Climates", 
    "Best Siding Options for Cold Climates", "How to Clean Gutters Before Storm Season", 
    "Storm Shutters: Are They Necessary?", "Protecting Windows from Hurricane Debris", 
    "Drafty Windows: DIY Weatherstripping Guide", "Garage Door Reinforcement for High Winds", 
    "How Solar Panels Handle Snow Loads", "How Solar Panels Handle Hail", 
    "Lightning Rods: Do You Need One?", "Painting Your House: Best Weather Conditions", 
    "Protecting Outdoor Faucets from Freezing", "Sump Pump Maintenance Before Heavy Rain", 
    "French Drains for Yard Flooding", "Sandbagging 101: How to Stack Properly", 
    "Removing Snow from Roofs (Safety Guide)", "Detecting Water Leaks After a Storm", 
    "Smart Thermostats: Best Settings for Summer", "Smart Thermostats: Best Settings for Winter", 
    "Humidity Control: Using Dehumidifiers", "Dry Air: Benefits of Humidifiers", 
    "How Barometric Pressure Affects Indoor Air Quality", "Best Insulation Types for Your Climate", 
    "Ceiling Fan Direction: Summer vs. Winter", "Protecting Electronics from Lightning Surges", 
    "Carbon Monoxide Safety during Winter", "Wood Stove Safety Tips", "Space Heater Safety", 
    "Preventing Frozen Pipes in Basements", "What to Do if Pipes Burst", 
    "Mold Prevention in Humid Climates", "Energy Efficient Curtains: Do They Work?", 
    "Air Conditioning Maintenance Before Summer", "Furnace Tune-Up Before Winter", 
    "Power Outage Survival Kit for Indoors", "Food Safety During Power Outages", 
    "Emergency Water Storage Tips", "How to Drive in Hydroplaning Conditions", 
    "Driving in Thick Fog", "Winter Tires vs. All-Season Tires", 
    "Putting Chains on Tires: A How-To", "De-icing Your Windshield Quickly", 
    "Preventing Car Door Locks from Freezing", "How to Jump Start a Car in Cold Weather", 
    "What to Keep in a Winter Car Kit", "Hot Cars: The Dangers of Heatstroke", 
    "Checking Tire Pressure in Changing Temps", "Protecting Car Paint from Sun Damage", 
    "Repairing Hail Dents on Cars", "Driving in High Winds (Trucks/RVs)", 
    "Sun Glare Driving Safety", "Dust Storm Driving Safety (Pull Aside, Stay Alive)", 
    "Tornado on the Road: What to Do", "Flooded Roads: Turn Around Don't Drown", 
    "Salt Damage on Cars: How to Wash it Off", "Wiper Blade Maintenance for Rainy Seasons", 
    "Convertible Care in Sun and Rain", "Storing Patio Furniture for Winter", 
    "Protecting Grills from Rust and Rain", "Pool Maintenance During Heavy Rain", 
    "Winterizing Your Swimming Pool", "Best Deck Stains for Wet Climates", 
    "Securing Trampolines for High Winds", "Tree Trimming to Prevent Storm Damage", 
    "Landscaping for Drainage", "Xeriscaping (Drought-tolerant landscaping)", 
    "Rain Barrels: Harvesting Water", "Watering Lawns: Morning vs. Evening", 
    "Protecting Potted Plants from Frost", "Greenhouse Temperature Management", 
    "Composting in Winter", "Mosquito Control in Wet Seasons", "Fire Pits and Wind Safety", 
    "Outdoor Rugs that Survive Rain", "Best Material for Outdoor Cushions", 
    "Building a Windbreak with Trees", "Snow Blowing Etiquette and Tips", 
    "Dog Walking in Heat: The Pavement Test", "Dog Walking in Extreme Cold", 
    "Thunderstorm Anxiety in Dogs", "Outdoor Cats and Winter Shelters", 
    "Hydration for Pets in Summer", "Protecting Paws from Salt and Ice", 
    "Flea and Tick Season and Weather", "Livestock Safety in Hurricanes", 
    "Chicken Coop Winterizing", "Horse Care in Extreme Heat", "Heartworm Prevention and Mosquitos", 
    "Bird Feeding in Winter", "Heating Bird Baths", "Koi Pond Winter Care", 
    "Reptile Tank Humidity Control", "Evacuating with Pets", "Pet Emergency Kits", 
    "Beehive Winterizing", "Wild Animals Seeking Warmth in Cars", "Toxic Plants that Bloom in Rain",
    # Group 4: Health & Human Impact (50 Posts) - Full List
    "How Arthritis and Barometric Pressure Affect Your Joints", "How Migraines and Weather Changes Affect Your Headaches", 
    "How Sinus Pressure and Storm Systems Affect Your Sinuses", "Seasonal Affective Disorder (SAD)", 
    "Vitamin D Deficiency in Winter", "Sunburn in Cloudy Weather", "Snow Blindness (Photokeratitis)", 
    "Dry Skin in Winter", "Eczema Flare-ups and Weather", "Asthma and Cold Air", 
    "Asthma and Thunderstorms", "Allergies: Pollen Counts and Wind", "Mold Allergies and Rain", 
    "Heat Exhaustion Symptoms", "Heat Stroke Symptoms", "Dehydration Signs", 
    "Hypothermia Signs", "Frostbite Signs", "Raynaud’s Disease and Cold", 
    "Hair Frizz and Humidity", "Static Electricity and Dry Air", "Sleep Quality and Room Temperature", 
    "Sleep and Rain Sounds (White Noise)", "Exercise in Humidity", "Exercise in Cold Weather", 
    "Heart Attacks and Shoveling Snow", "Altitude Sickness and Weather", 
    "Motion Sickness (Seasickness) and Waves", "Lyme Disease (Ticks) and Mild Winters", 
    "West Nile Virus (Mosquitos) and Wet Springs", "The Science of 'Feeling' a Storm Coming", 
    "Weather Phobias (Lilapsophobia)", "Managing Anxiety During Storms", "Kids and Weather Fears", 
    "Best Clothing Fabrics for Heat", "Best Clothing Fabrics for Cold (Layering)", 
    "Best Sunglasses for UV Protection", "Sunscreen Types (Chemical vs. Physical)", 
    "Chapped Lips Prevention", "Nosebleeds and Dry Air", "Contact Lenses in Dry/Windy Weather", 
    "Hydration: Electrolytes vs. Water", "Calories Burned in Cold vs. Heat", 
    "Weather's Effect on Mood", "Productivity and Weather", "Crime Rates and Heat Waves", 
    "Slip and Fall Prevention on Ice", "Carbon Monoxide Poisoning Symptoms", 
    "Eye Safety in Dust Storms", "Ear Infections and Swimmer's Ear",
    # Group 5: "Best Of" Rankings (50 Posts) - Full List
    "Top 10 Sunniest Cities in the USA", "Top 10 Cloudiest Cities in the USA", 
    "Top 10 Rainiest Cities in the USA", "Top 10 Snowiest Cities in the USA", 
    "Top 10 Windiest Cities in the USA", "Top 10 Most Humid Cities in the USA", 
    "Top 10 Driest Cities in the USA", "Cities with the Best Air Quality", 
    "Cities with the Worst Air Quality", "Safest States from Natural Disasters", 
    "Most Prone States for Tornadoes", "Most Prone States for Hurricanes", 
    "Coldest Cities in the USA", "Hottest Cities in the USA", 
    "Cities with the Most Pleasant Year-Round Weather", "Best Cities for Winter Sports", 
    "Best Cities for Summer Vacations", "Best Stargazing Locations (Dark Sky Parks)", 
    "Worst Traffic Cities during Rain", "Best States for Solar Energy Potential", 
    "Most Expensive States for Flood Insurance", "Best Places to Retire for Weather", 
    "Best Places to Move for Allergy Sufferers", "Most Extreme Weather Records in US History", 
    "Oldest Weather Stations in the USA", "Top 10 States with the Most Thunderstorms", 
    "Top 10 States with the Least Natural Disasters", "Best US Cities for Asthmatics (Air Quality)", 
    "Worst US Cities for Migraine Sufferers", "Top 10 Foggiest Places in America", 
    "Most Expensive Weather Disasters in US History", "Top 10 Cities for Renewable Energy (Wind/Sun)", 
    "Snowiest Colleges in the USA", "Sunniest Colleges in the USA", 
    "Best Beaches for Warm Water Swimming", "Coldest Swimming Holes in the USA", 
    "States with the Most Tornadoes per Square Mile", "Cities with the Most Reliable Weather Forecasts", 
    "Top 10 Places to See a Rainbow", "Best Places to Experience a 'White Christmas'", 
    "Hottest Places to Spend Christmas", "Cities with the Mildest Summers", 
    "Cities with the Mildest Winters", "Best Places to Watch Storms (safely)", 
    "Top 10 Windy Cities (It's not just Chicago)", "Rainiest Month in Every State (Listicle)", 
    "Hottest Month in Every State (Listicle)", "Coldest Month in Every State (Listicle)", 
    "Most Common Natural Disaster by State", "The 'Tornado Alley' vs. 'Dixie Alley' Ranking",
    # Group 6: Agriculture, Gardening & Farming (50 Posts) - Full List
    "Understanding USDA Hardiness Zones", "First Frost vs. Last Frost: Why it Matters", 
    "What are 'Growing Degree Days' (GDD)?", "'Chill Hours' Explained: Fruit Trees", 
    "How to Protect Tomato Plants from Freeze", "Drought-Resistant Lawns: Best Grass Types", 
    "Rain Gardens: Managing Stormwater Naturally", "Composting in Winter: Does it Work?", 
    "Best Vegetables for a Rainy Spring", "Best Vegetables for a Hot Summer", 
    "Watering Your Garden: Morning vs. Night", "Windbreak Planting for Crop Protection", 
    "Hail Netting: Is it Worth It?", "Soil Erosion from Heavy Rain", 
    "Mulching to Keep Soil Moist", "Greenhouse Ventilation Tips", 
    "Hydroponics and Temperature Control", "Livestock Safety During Thunderstorms", 
    "Heat Stress in Cattle: Warning Signs", "Chicken Coops: Winter Ventilation", 
    "Protecting Beehives from Wind", "Harvesting Rainwater (State Laws)", 
    "El Niño's Impact on US Agriculture", "La Niña's Impact on US Agriculture", 
    "Frost Cloth vs. Plastic", "Cold Frames: Gardening in Snow", "Xeriscaping Principles", 
    "Native Plants and Local Weather", "Microclimates in Your Backyard", 
    "Pruning Trees to Avoid Ice Damage", "Root Rot and Moisture Issues", 
    "Fungal Diseases from Humidity", "Pest Explosions after Mild Winters", 
    "Mosquito Control for Farm Ponds", "Tractor Safety on Muddy Slopes", 
    "Barn Ventilation for Summer", "Silage Safety and Moisture", 
    "Hay Fires: Spontaneous Combustion", "Flood Recovery for Farmland", 
    "Saltwater Intrusion in Coastal Gardens", "Snow Load Capacities for Barns", 
    "Aquaponics Temperature Requirements", "Best Cover Crops for Winter", 
    "Predicting Weather for Harvest", "Farmers' Almanac vs. NWS Accuracy", 
    "Urban Gardening Heat Islands", "Container Gardening Watering Needs", 
    "Vertical Farming Climate Control", "Orchard Heating Systems", 
    "Sustainable Farming and Climate Change",
    # Group 7: Travel & Outdoor Recreation (50 Posts) - Full List
    "Best Time to Visit Disney World (Weather)", "Best Time to Visit National Parks (Weather)", 
    "Hurricane Season Cruising Guide", "Turbulence Explained: Is it Dangerous?", 
    "Why Flights Get Cancelled: Wind vs. Visibility", "De-icing Planes: Why You Wait", 
    "Camping in the Rain: Gear List", "RV Camping in High Winds", "Beach Safety: Rip Currents", 
    "Jellyfish and Warm Water", "Lightning Safety on the Beach", "Hiking: Afternoon Storm Dangers", 
    "Altitude Sickness Tips", "Desert Hiking: Flash Flood Risks", "Skiing: What is Champagne Powder?", 
    "Spring Break Weather: FL vs. Mexico", "Fall Foliage Prediction Science", 
    "Driving an EV in Cold Weather", "Driving an EV in Extreme Heat", "Towing a Boat in Wind", 
    "Kayaking: Water vs. Air Temp", "Cold Water Shock (Hypothermia in Summer)", 
    "Best US Cities for 'Snowbirds'", "Glamping: Heating and Cooling", "Best Road Trip Weather Apps", 
    "Visiting Death Valley (Safety)", "Visiting Alaska (Summer Clothing)", 
    "Tornado Safety for Campers", "Activities for Rainy Vacation Days", "Golfing in the Wind", 
    "Fishing and Barometric Pressure", "Hunting and Wind Direction", "Surfing: Swell and Wind", 
    "Sailing: Reading Clouds", "Bonfire Safety and Wind", "Theme Park Rain Policies", 
    "Packing for Multi-Climate Trips", "Travel Insurance and Weather", 
    "Outdoor Wedding Weather Plan B", "Golden Hour Photography and Weather", 
    "Astrophotography: Finding Clear Skies", "Birdwatching and Migration Winds", 
    "Hawaii: Rainy Side vs. Dry Side", "San Francisco: Why is it Cold in Summer?", 
    "Seattle: Is it Always Rainy?", "Route 66 Weather Hazards", "Blue Ridge Parkway Fog", 
    "Going-to-the-Sun Road Snow Plowing", "Niagara Falls: Winter vs. Summer", 
    "Safety in Remote Cabins"
]

# ============================================================
# State Management (Updated for Evergreen Index)
# ============================================================
def get_state() -> Dict[str, Any]:
    """Retrieves state, including view history and the last posted index."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            log.warning("State file corrupted, resetting.")
    # Initialize with the new last_posted_index
    return {"daily_views": 0, "last_view_check": str(datetime.now() - relativedelta(days=1)), "last_posted_index": -1, "post_history": {}}

def save_state(state: Dict[str, Any]):
    """Saves the bot's state."""
    STATE_FILE.write_text(json.dumps(state, indent=2))

# ============================================================
# Evergreen Topic Selection (NEW STRATEGY #9)
# ============================================================
def get_next_evergreen_topic(state: Dict[str, Any]) -> List[str]:
    """
    Cycles through the EVERGREEN_TOPICS list to select the next POSTS_PER_RUN topics.
    Updates the 'last_posted_index' in the state.
    """
    total_topics = len(EVERGREEN_TOPICS)
    
    # 1. Get the starting index
    start_index = state.get('last_posted_index', -1) + 1
    
    # 2. Check for wrap-around and reset
    if start_index >= total_topics:
        start_index = 0
        log.info("Completed one full cycle of %d evergreen posts. Restarting list.", total_topics)
    
    # 3. Determine the end index for the current run
    topics_to_post = []
    new_last_index = start_index - 1
    
    for i in range(POSTS_PER_RUN):
        # Calculate the current index, handling wrap-around
        current_index = (start_index + i) % total_topics
        topics_to_post.append(EVERGREEN_TOPICS[current_index])
        new_last_index = current_index
        
    # 4. Update the state
    state['last_posted_index'] = new_last_index
    log.info("Selected %d posts starting from initial index %d. New index: %d", POSTS_PER_RUN, start_index, new_last_index)
    
    return topics_to_post


# ============================================================
# Gemini Content Generation (With Title Style)
# ============================================================
def generate_post(topic: str, required_style: str) -> Dict[str, Any]:
    """Generates an evergreen, SEO-heavy blog post based on a fixed topic."""
    
    current_date = datetime.now().strftime("%B %d, %Y")

    prompt = f"""
***TASK: High-Traffic, Evergreen, 2000+ Word USA Weather Blog Post***

**GOAL:** Generate a detailed, evergreen blog post of at least **2000 words** focused on the topic: **"{topic}"**. The post must be written to appeal directly to a **United States audience** seeking utility, safety, and deep context.

**FOCUS:**
- **Topic:** "{topic}" (Make sure the topic is the central theme)
- **Target:** US Audience
- **Date Context:** {current_date} (Use this for initial framing, but the core content must remain relevant for years).

**STRUCTURE & REQUIREMENTS (CRITICAL for SEO and 1000+ Daily Views):**

1.  **Content Length:** MUST exceed 2000 words. Achieve this by providing deep analysis, historical context, and comprehensive safety guides.
2.  **Title & Meta (FORCED VARIETY):** The `title` MUST be highly emotional, curiosity-driven, or a comprehensive guide for maximum CTR. **You MUST strictly follow the required title style for this post:** **{required_style}**
    * **Style 1 (Utility/Guide):** Use phrases like "The Ultimate Guide," "Complete Blueprint," or "Master Checklist."
    * **Style 2 (Emotional/Shock):** Use phrases like "The Shocking Truth About...," "Hidden Dangers of...," or "Why You Must Prepare for..."
    * **Style 3 (Listicle/Actionable):** Use numbered lists like "5 Ways to Prepare for...," "3 Essential Steps to...," or "7 Things to Know About..."
3.  **Source Linking:** Include **more than 10** distinct, high-authority external hyperlinks (`<a href="...">...</a>`) spread throughout the content. These links must point to **plausible, high-authority sources** in the US (NOAA, FEMA, CDC, specific state/local government sites, academic journals). **Invent these link URLs and link text to be highly relevant to the content you generate.** Example: `<a href="https://www.fema.gov/disaster-safety/tornadoes">FEMA Tornado Safety Checklist</a>`.
4.  **Evergreen Sections:** The content must be framed as a long-term resource. Include sections like:
    * **Historical Impact:** How has this type of weather event impacted the US in the last 10-20 years?
    * **Preparation Utility:** Highly actionable, state-by-state safety and preparation checklists.
    * **Future Trends:** Expert outlooks on how climate change affects this specific topic.
5.  **Labels (Tags):** MUST include a `labels` array with 5-10 relevant SEO keywords/categories.

**OUTPUT FORMAT:**
- Use standard, clean HTML markup (`<h1>`, `<h2>`, `<p>`, `<a>`, `<ul>`/`<ol>`).
- Your entire response MUST be a single JSON object matching the SCHEMA.
- The `content_html` field must contain ALL content.
"""
    
    for model_name in MODEL_PREFERENCE:
        log.info("Generating post content for topic: %s using model: %s (Style: %s)", topic, model_name, required_style)
        
        try:
            r = client.models.generate_content(
                model=model_name,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_schema=SCHEMA,
                    response_mime_type="application/json",
                    temperature=0.9,
                ),
            )
            log.info("Successfully generated content using %s.", model_name)
            return json.loads(r.text)

        except (Exception, gapi_exceptions.ResourceExhausted) as e:
            if model_name != MODEL_PREFERENCE[-1]:
                log.warning("Model %s failed: %s. Attempting fallback to next model...", model_name, e)
            else:
                log.error("All models failed for topic %s: %s", topic, e)
                raise 
                 
    raise RuntimeError("Critical: Model generation failed after all fallback attempts.")


# ============================================================
# Blogger API Handlers
# ============================================================
BLOGGER_SCOPE = ["https://www.googleapis.com/auth/blogger"]
ARCHIVE_PAGE_TITLE = "Blog Index/Archive"

def get_authenticated_service():
    """ Handles OAuth 2.0 flow and returns an authenticated Blogger service."""
    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, BLOGGER_SCOPE)
        except Exception:
            pass 

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            log.warning("Starting interactive OAuth 2.0 flow. Run this script locally ONCE to generate token.json.")
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, BLOGGER_SCOPE
            )
            creds = flow.run_local_server(port=0) 

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('blogger', 'v3', credentials=creds)

def get_existing_post_id(service, blog_id: str, title: str) -> Optional[str]:
    """ Searches for an existing post by title (approximation)."""
    try:
        results = service.posts().list(blogId=blog_id, maxResults=50).execute()
        for post in results.get('items', []):
            if post['title'].lower().strip() == title.lower().strip():
                log.info("Found existing post with matching title: %s", post['id'])
                return post['id']
        return None
    except HttpError as e:
        log.error("Failed to list posts from Blogger API: %s", e)
        return None

def get_blog_page_views(service, blog_id: str, state: Dict[str, Any]):
    """ Retrieves total page views for the blog (Strategy #7 Insight)."""
    log.info("Fetching last 7 days of page views...")
    try:
        result = service.pageViews().get(blogId=blog_id, range='7DAYS').execute()
        # Safely extract the count and convert to int
        views_data = result.get('counts', [{'count': '0'}])[0]
        views = int(views_data.get('count', '0'))
        
        state['daily_views'] = views
        state['last_view_check'] = str(datetime.now(timezone.utc))

        log.info(f"Blog Page View Count (Last 7 Days): {views}. Target: 7000+")
    except HttpError as e:
        log.error("HTTP Error fetching page views: %s", e)
    except Exception as e:
        log.error("General Error fetching page views: %s", e)

def publish_or_update_post(post: Dict[str, Any], blog_id: str):
    """ Checks for existing post, updates it if found, or inserts a new one."""
    log.info("Attempting to publish/update post...")
    
    try:
        service = get_authenticated_service()
        existing_post_id = get_existing_post_id(service, blog_id, post['title'])
        
        body = {
            'kind': 'blogger#post',
            'blog': {'id': blog_id},
            'title': post['title'],
            'content': post['content_html'],
            'labels': post.get('labels', [])
        }
        
        if existing_post_id:
            log.info("Updating existing post ID %s to refresh content...", existing_post_id)
            body['published'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            request = service.posts().patch(
                blogId=blog_id, 
                postId=existing_post_id, 
                body=body,
                fetchBody=False 
            )
            result = request.execute()
            log.info("Successfully UPDATED post: %s", result.get('url'))
        
        else:
            log.info("No existing post found. Inserting new post...")
            request = service.posts().insert(blogId=blog_id, body=body, isDraft=False)
            result = request.execute()
            log.info("Successfully INSERTED new post: %s", result.get('url'))
            
        
        # Inject Canonical Link (SEO Enhancement)
        final_post_url = result.get('url')
        if final_post_url:
            canonical_tag = f'<link rel="canonical" href="{final_post_url}">'
            log.info("Injecting canonical link: %s", canonical_tag)
            
            updated_content_html = canonical_tag + post['content_html']
            
            canonical_body = {
                'content': updated_content_html,
                'published': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
            
            canonical_request = service.posts().patch(
                blogId=blog_id,
                postId=result.get('id'),
                body=canonical_body,
                fetchBody=False
            )
            canonical_request.execute()
            log.info("Canonical link successfully patched into post content.")

        return final_post_url

    except HttpError as e:
        log.error("Failed to interact with Blogger API (HTTP Error: %s).", e.resp.status)
    except Exception as e:
        log.error("An unexpected error occurred during publishing: %s", e)

def update_archive_page(service, blog_id: str):
    """ Fetches all posts, generates a sorted list of links, and updates/creates the Archive Page. """
    log.info("--- Starting Archive Page Update ---")
    
    try:
        all_posts = []
        page_token = None
        while True:
            request = service.posts().list(
                blogId=blog_id, 
                maxResults=50, 
                orderBy='PUBLISHED', 
                status='LIVE',       
                pageToken=page_token
            )
            result = request.execute()
            all_posts.extend(result.get('items', []))
            page_token = result.get('nextPageToken')
            if not page_token:
                break
        
        log.info("Fetched %d total published posts for the archive.", len(all_posts))

        all_posts.sort(key=lambda p: p['published'], reverse=True) 

        archive_html = f'<h1>{ARCHIVE_PAGE_TITLE}</h1>'
        archive_html += '<p>This index provides direct links to every comprehensive weather resource on our blog.</p>'
        archive_html += '<ul>\n'
        
        for post in all_posts:
            pub_date = datetime.fromisoformat(post['published'].replace('Z', '+00:00')).strftime('%Y-%m-%d')
            archive_html += f'    <li><a href="{post["url"]}">{post["title"]}</a> - ({pub_date})</li>\n'
            
        archive_html += '</ul>'

        archive_page_id = None
        page_token = None
        while True:
            request = service.pages().list(blogId=blog_id, pageToken=page_token)
            result = request.execute()
            
            for page in result.get('items', []):
                if page['title'].strip() == ARCHIVE_PAGE_TITLE:
                    archive_page_id = page['id']
                    break
            
            page_token = result.get('nextPageToken')
            if not page_token or archive_page_id:
                break

        body = {
            'kind': 'blogger#page',
            'blog': {'id': blog_id},
            'title': ARCHIVE_PAGE_TITLE,
            'content': archive_html,
        }

        if archive_page_id:
            log.info("Found existing Archive Page (ID: %s). Updating content...", archive_page_id)
            service.pages().patch(
                blogId=blog_id,
                pageId=archive_page_id,
                body=body
            ).execute()
            log.info("Successfully updated Archive Page.")
        else:
            log.info("Archive Page not found. Creating a new one...")
            service.pages().insert(blogId=blog_id, body=body, isDraft=False).execute()
            log.info("Successfully created new Archive Page.")

    except HttpError as e:
        log.error("Failed to manage Archive Page via Blogger API (HTTP Error: %s).", e.resp.status)
    except Exception as e:
        log.error("An unexpected error occurred during Archive Page update: %s", e)
        
    log.info("--- Archive Page Update Complete ---")


# ============================================================
# Main Execution
# ============================================================
def main():
    state = get_state()
    log.info("Starting run. Target posts this run: %d. Strategy: Fixed Evergreen Rotation.", POSTS_PER_RUN)
    
    service = None
    if PUBLISH:
        try:
            service = get_authenticated_service()
            get_blog_page_views(service, BLOG_ID, state)
        except Exception as e:
            log.error("Failed to initialize Blogger service: %s. Cannot publish.", e)
            return

    # 1. Get the next set of evergreen topics
    topics_to_post = get_next_evergreen_topic(state)
    
    # 2. Cycle through the topics and generate posts
    for i, topic in enumerate(topics_to_post):
        # Determine the title style based on the current post's index (i) within the run
        # This forces the rotation: Post 1 = Guide, Post 2 = Shock, Post 3 = Listicle, Post 4 = Guide
        title_style = TITLE_STYLES[i % len(TITLE_STYLES)] 
        log.info("--- Post %d/%d: Processing topic: %s (Style: %s) ---", i + 1, POSTS_PER_RUN, topic, title_style)

        try:
            # Pass the required style to the generation function
            post = generate_post(topic, title_style)
            
            # 3. Save a local backup
            # Explicitly remove colon and other invalid characters from filename
            post_title_safe = (
                post['title'].lower()
                .replace(' ', '-')
                .replace('/', '-')
                .replace('\\', '-')
                .replace(':', '') 
                .strip()
            )
            post_title_safe = post_title_safe[:50] # Truncate

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            fname = OUTPUT_DIR / f"{timestamp}-{post_title_safe}.html"
            OUTPUT_DIR.mkdir(exist_ok=True)
            Path(fname).write_text(post['content_html'], encoding="utf-8")
            log.info("Saved local backup to %s", fname)

            # 4. Publish or Update
            if PUBLISH:
                publish_or_update_post(post, BLOG_ID)
            else:
                log.info("PUBLISH is set to false. Skipping Blogger API interaction.")

        except Exception as e:
            log.error("CRITICAL ERROR during post generation/publishing for topic %s: %s. Continuing to next post.", topic, e)
            continue
            
    log.info("Completed run of %d posts.", POSTS_PER_RUN)
    
    # 5. UPDATE ARCHIVE PAGE
    if PUBLISH and service:
        update_archive_page(service, BLOG_ID)
        
    # 6. Save final state (including the new last_posted_index)
    save_state(state)
    log.info("Final state saved successfully.")

if __name__ == "__main__":
    main()