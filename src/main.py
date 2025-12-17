# ==============================================================================
# MERGED PYTHON PROGRAM: main.py - V2 (SEO and Async Performance Optimized)
# ==============================================================================

# ==============================================================================
# 1. CONSOLIDATED IMPORTS
# ==============================================================================
import os
import time
import json
import re
import requests
import base64
import random # <-- Used for backoff jitter
import asyncio # <-- For concurrent NWS API calls
import aiohttp # <-- For high-performance HTTP requests
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from urllib.parse import quote

# Third-party imports
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors # <-- Used to catch API errors for retrying
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ==============================================================================
# 2. CONFIGURATION AND ENVIRONMENT (from config.py)
# ==============================================================================

# Try to load .env file if it exists, but don't fail if it doesn't
load_dotenv()

# Required environment variables with error handling
def get_required_env_var(var_name):
    value = os.getenv(var_name)
    if value is None:
        raise ValueError(f"Required environment variable {var_name} is not set")
    return value

# Optional environment variables with defaults
def get_optional_env_var(var_name, default_value=None):
    return os.getenv(var_name, default_value)

# API Keys and Configuration Load
try:
    GEMINI_API_KEY = get_required_env_var("GEMINI_API_KEY")
    BLOGGER_API_KEY = get_required_env_var("BLOGGER_API_KEY")

    # Blogger Configuration
    BLOG_ID = get_required_env_var("BLOG_ID")
    BLOG_BASE_URL = get_required_env_var("BLOG_BASE_URL").rstrip('/') # Ensure no trailing slash for consistent URL building

    # OAuth Configuration
    CLIENT_SECRETS_FILE = get_optional_env_var("CLIENT_SECRETS_FILE", "client_secrets.json")

    # Publishing Configuration
    PUBLISH = get_optional_env_var("PUBLISH", "false").lower() == "true"

    # NWS Configuration
    NWS_USER_AGENT = get_required_env_var("NWS_USER_AGENT")
except ValueError as e:
    # This print ensures the user sees which variable is missing early on.
    print(f"Configuration Error: {e}")
    # We allow the program to load, but main() will check for required variables.

# Global Constants used by main.py and other modules
STATE_FILE = "last_posted_zone.txt"
TOKEN_FILE = "token.json" # Defined here for consistency

DISCLAIMER_HTML = (
    "<p style=\"font-size: 0.8em; color: #888;\">"
    "This post is created using the public data provided by the National Weather Service. "
    "Please check the <a href=\"https://www.weather.gov/\" target=\"_blank\" style=\"color: #007bff; text-decoration: none;\">Original source</a> for more information."
    "</p>"
)


# ==============================================================================
# 3. CITY ZONES DATA (from city_zones.py)
# ==============================================================================

# City → lat/lon mapping grouped into four custom zones.
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

# The rotation order for which zone to post next
ZONE_ROTATION = list(NWS_ZONES.keys())


# ==============================================================================
# 4. POST STORAGE UTILITIES (from post_storage.py)
# ==============================================================================

OUTPUT_DIR = Path("output_posts")
INDEX_FILE = OUTPUT_DIR / "posts_index.json"


@dataclass
class PostMeta:
    id: str               # unique id (date + slug)
    title: str
    meta_description: str
    zone_name: str
    tags: List[str]
    category: str
    slug: str
    filename: str
    created_at: str       # ISO-8601 UTC
    url: Optional[str]    # optional final blog URL (can be None until manually set)


# ---------- Utility functions (Primary slug function) ----------

def _safe_slug(text: str, max_len: int = 80) -> str:
    """
    Creates a URL-safe slug from a string.
    This function is used globally for post storage and SEO link generation.
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text)
    return text[:max_len] or "post"


def _load_index() -> List[PostMeta]:
    """
    Loads the list of PostMeta objects from the index file.
    """
    if not INDEX_FILE.exists():
        return []
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Re-create dataclass objects from dicts
            return [PostMeta(**item) for item in data]
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Warning: Could not load index file. Starting fresh. Error: {e}")
        return []


def _save_index(posts: List[PostMeta]):
    """
    Saves the list of PostMeta objects back to the index file.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    # Convert dataclasses to list of dicts for JSON serialization
    data = [asdict(post) for post in posts]
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"Index updated with {len(posts)} posts.")


def auto_generate_tags(title: str, content_html: str, zone_name: str) -> List[str]:
    """
    Generates a list of tags (labels for Blogger) based on the title, content,
    and zone.
    """
    tags = set()
    # 1. Static tags
    tags.add("Weather Forecast")
    tags.add("USA")
    tags.add("NationalWeatherService")

    # 2. Zone-based tags
    if zone_name:
        tags.add(zone_name)
        tags.add(zone_name.split(" ")[0] + " Weather") # e.g., "Eastern Weather"

    # 3. Simple keyword extraction from title (could be enhanced)
    for keyword in ["alert", "warning", "forecast", "danger", "weather", "update"]:
        if keyword in title.lower():
            tags.add(keyword.capitalize())

    # 4. Extract city names from content (simple heuristic)
    for city_data in NWS_ZONES.get(zone_name, {}).get("cities", []):
        # Only take the city name, ignore the state/country
        city = city_data["city"].split(",")[0].strip()
        if city in content_html:
            tags.add(city)

    return sorted(list(tags))


# ---------- Main function ----------

def save_post_and_update_indexes(
    title: str,
    meta_description: str,
    content_html: str,
    zone_name: str,
) -> PostMeta:
    """
    1. Saves the final HTML to a file in OUTPUT_DIR.
    2. Updates the central posts index (posts_index.json).
    3. Generates and updates sitemap.xml.
    4. Generates and updates an index HTML for local viewing.
    """
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Timestamp & slug
    now = datetime.now(timezone.utc)
    iso_now = now.isoformat()
    date_str = now.strftime("%Y-%m-%d")
    slug = _safe_slug(title) # Uses the safe slug function defined above
    post_id = f"{date_str}-{slug}"
    filename = f"{post_id}.html"

    # Tags & category
    tags = auto_generate_tags(title, content_html, zone_name)
    category = zone_name or "USA Weather"

    # Wrap into full HTML document (primarily for local viewing)
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<meta name="description" content="{meta_description}" />
<link rel="canonical" href="{BLOG_BASE_URL}/{date_str}/{slug}.html" />
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 20px auto; padding: 0 15px; background-color: #f8f9fa; }}
h1, h2, h3 {{ color: #343a40; }}
.disclaimer {{ font-size: 0.8em; color: #888; border-top: 1px solid #eee; padding-top: 10px; margin-top: 20px; }}
.internal-links {{ margin-top: 40px; border-top: 1px solid #ccc; padding-top: 20px; }}
.internal-links h2 {{ font-size: 1.2em; color: #007bff; }}
</style>
</head>
<body>
{content_html}
<p class="disclaimer">Note: This is a local copy. The canonical URL is <a href="{BLOG_BASE_URL}/{date_str}/{slug}.html">{BLOG_BASE_URL}/{date_str}/{slug}.html</a></p>
</body>
</html>
"""

    # Write HTML file
    with open(OUTPUT_DIR / filename, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"Post saved locally to: {OUTPUT_DIR / filename}")

    # Load existing index & upsert
    posts = _load_index()
    meta = PostMeta(
        id=post_id,
        title=title,
        meta_description=meta_description,
        zone_name=zone_name,
        tags=tags,
        category=category,
        slug=slug,
        filename=filename,
        created_at=iso_now,
        # Create a proxy URL for the local index / sitemap generation
        # This approximates the Blogger URL format, though it's technically wrong for date path.
        # It's primarily used for canonical link and sitemap submission.
        url=f"{BLOG_BASE_URL}/{now.strftime('%Y/%m')}/{slug}.html",
    )

    # upsert by id
    existing_idx = next((i for i, p in enumerate(posts) if p.id == post_id), -1)
    if existing_idx != -1:
        posts[existing_idx] = meta
    else:
        # Insert new post at the start (most recent first)
        posts.insert(0, meta)

    _save_index(posts)

    # Update sitemap, index, and tag pages
    _update_sitemap(posts)
    _update_local_index_html(posts)
    _update_tag_pages(posts)

    return meta


def _update_sitemap(posts: List[PostMeta]):
    """
    Generates a basic sitemap.xml from the posts index and tag pages.
    -- IMPROVEMENT: Added tag pages to sitemap for better crawl coverage. --
    """
    sitemap_path = OUTPUT_DIR / "sitemap.xml"
    if not BLOG_BASE_URL:
        print("Warning: BLOG_BASE_URL not set. Skipping sitemap generation.")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    url_entries = []
    # 1. Post Entries
    for post in posts:
        # Use a simplified URL structure for the sitemap
        url_entries.append(f"""
    <url>
        <loc>{post.url}</loc>
        <lastmod>{post.created_at.split('+')[0]}+00:00</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>""")

    # 2. Tag/Category Pages (Important for internal link equity)
    all_tags = set(tag for post in posts for tag in post.tags)
    for tag in all_tags:
        # Blogger search URL for a tag: https://BLOG_BASE_URL/search/label/TAG_NAME
        tag_url = f"{BLOG_BASE_URL}/search/label/{quote(tag)}"
        url_entries.append(f"""
    <url>
        <loc>{tag_url}</loc>
        <lastmod>{now}</lastmod>
        <changefreq>daily</changefreq>
        <priority>0.7</priority>
    </url>""")

    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>{BLOG_BASE_URL}/</loc>
        <lastmod>{now}</lastmod>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
    </url>
    {
        "".join(url_entries)
    }
</urlset>
"""
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write(sitemap_content.strip())
    print(f"Sitemap updated: {sitemap_path}")


def _update_local_index_html(posts: List[PostMeta]):
    """Generates a simple index.html for viewing locally saved posts."""
    index_path = OUTPUT_DIR / "index.html"

    list_items = []
    for post in posts:
        tags_str = ", ".join(post.tags)
        list_items.append(f"""
        <li>
            <a href="{post.filename}" target="_blank">{post.title}</a>
            <br><small>Zone: {post.zone_name} | Tags: {tags_str} | Date: {post.created_at[:10]}</small>
        </li>""")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Local Posts Index</title>
    <style>
        body {{ font-family: sans-serif; max-width: 800px; margin: 20px auto; }}
        li {{ margin-bottom: 15px; }}
    </style>
</head>
<body>
    <h1>Local Posts Index ({len(posts)} Total)</h1>
    <p>Click on a link to view the locally generated HTML file.</p>
    <ul>
        {"".join(list_items)}
    </ul>
</body>
</html>
"""
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html_content.strip())
    print(f"Local index updated: {index_path}")

def _update_tag_pages(posts: List[PostMeta]):
    """Generates a simple index for each unique tag (label)."""
    tags_dir = OUTPUT_DIR / "tags"
    tags_dir.mkdir(exist_ok=True)

    tag_to_posts: Dict[str, List[PostMeta]] = {}
    for post in posts:
        for tag in post.tags:
            tag = tag.strip() # Clean tag
            if tag not in tag_to_posts:
                tag_to_posts[tag] = []
            tag_to_posts[tag].append(post)

    for tag, tagged_posts in tag_to_posts.items():
        # Sanitize tag for filename
        tag_slug = _safe_slug(tag)
        tag_path = tags_dir / f"{tag_slug}.html"

        list_items = []
        for post in tagged_posts:
            list_items.append(f"""
            <li>
                <a href="../{post.filename}">{post.title}</a>
                <br><small>Zone: {post.zone_name} | Date: {post.created_at[:10]}</small>
            </li>""")

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Posts Tagged: {tag}</title>
    <style>
        body {{ font-family: sans-serif; max-width: 800px; margin: 20px auto; }}
        li {{ margin-bottom: 15px; }}
    </style>
</head>
<body>
    <h1>Posts Tagged: {tag} ({len(tagged_posts)} Total)</h1>
    <p><a href="../index.html">← Back to Main Index</a></p>
    <ul>
        {"".join(list_items)}
    </ul>
</body>
</html>
"""
        with open(tag_path, "w", encoding="utf-8") as f:
            f.write(html_content.strip())
        # print(f"Tag page updated: {tag_path}") # Suppress for cleaner output

# ==============================================================================
# 5. IMAGE UTILITIES (from image_utils.py)
# ==============================================================================

# Live national weather map from NWS (auto-updating)
PLACEHOLDER_IMAGE_URL = "https://www.weather.gov/wwamap/png/US.png"


def build_placeholder_image_tag(zone_name: str) -> str:
    """
    Returns a lightweight <img> tag using the live NWS USA map URL,
    followed by a disclaimer about the live nature of the image.
    """
    safe_zone = zone_name.replace('"', "").replace("<", "").replace(">", "")
    alt_text = f"{safe_zone} Weather Alerts Map"

    # We use a multi-line f-string for clarity, combining the image and the warning text
    return (
        # Start the image tag
        f'<img src="{PLACEHOLDER_IMAGE_URL}" '
        f'alt="{alt_text}" '
        'style="max-width:100%;height:auto;border-radius:8px;display:block;margin-bottom: 5px;" />'

        # Add the warning text right after the image
        '<p style="font-size: 0.7em; color: #666; text-align: center; margin-top: 5px;">'
        'The image is a live image for the National Weather Service server. It gets updated on Real time.'
        '</p>'
    )

# ==============================================================================
# 6. SEO UTILITIES (from seo_utils.py)
# ==============================================================================
# Note: This section relies on the _safe_slug and auto_generate_tags from Section 4.

def _zone_to_region_name(zone_name: str) -> str:
    """
    Map your logical zone name to a clearer US region label.
    This is used for articleSection / geo fields / keywords.
    """
    zl = (zone_name or "").lower()
    if "southern" in zl:
        return "Southern United States"
    if "eastern" in zl:
        return "Eastern United States"
    if "western" in zl:
        return "Western United States"
    if "central" in zl:
        return "Central United States"
    # fallback
    return "United States"


def _build_internal_links_html(current_zone_name: str) -> str:
    """
    Generates a block of internal links to other zone pages.
    """
    if not BLOG_BASE_URL:
        return ""

    links = []
    # Use the ZONE_ROTATION list for a fixed order
    for zone in ZONE_ROTATION:
        if zone == current_zone_name:
            continue
        # Assuming a structure like: https://BLOG_BASE_URL/search/label/ZoneName
        safe_tag = quote(zone.replace(" ", "%20"))
        link_url = f"{BLOG_BASE_URL}/search/label/{safe_tag}"
        link_html = f'<a href="{link_url}" style="text-decoration:none; color:#007bff; font-weight:bold;">{zone}</a>'
        links.append(link_html)

    if not links:
        return ""

    # Generate the final HTML block
    links_html = " | ".join(links)
    return f"""
<div class="internal-links" style="margin-top: 40px; padding: 20px; border: 1px solid #eee; border-radius: 8px; background-color: #f9f9f9;">
    <h2 style="font-size: 1.2em; color: #333; margin-top: 0; border-bottom: 1px solid #eee; padding-bottom: 10px;">Check Other Zone Forecasts:</h2>
    <p style="text-align: center; line-height: 1.8;">{links_html}</p>
</div>
"""


def inject_seo_and_links(
    content_html: str,
    title: str,
    zone_name: str,
    meta_description: str,
) -> str:
    """
    Injects JSON-LD Schema and internal links into the content HTML.
    """
    # 1. Generate Schema.org JSON-LD
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    slug = _safe_slug(title) # Correctly calls _safe_slug from Section 4
    # The canonical URL approximation:
    date_str = datetime.now(timezone.utc).strftime("%Y/%m")
    canonical_url = f"{BLOG_BASE_URL}/{date_str}/{slug}.html" if BLOG_BASE_URL else f"/post/{slug}"

    # Use a generic image for the schema
    image_url = PLACEHOLDER_IMAGE_URL # Uses constant from image_utils section

    region_name = _zone_to_region_name(zone_name)
    keywords = ",".join(auto_generate_tags(title, content_html, zone_name))

    schema_obj = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "url": canonical_url,
        "image": image_url,
        "description": meta_description,
        "inLanguage": "en-US",
        "datePublished": now,
        "dateModified": now,
        "author": {
            "@type": "Organization",
            "name": "USA Weather Updates",
        },
        "publisher": {
            "@type": "Organization",
            "name": "USA Weather Updates",
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": canonical_url,
        },
        "articleSection": f"{region_name} Weather",
        "keywords": keywords,
        "contentLocation": {
            "@type": "Place",
            "name": region_name,
            "address": {
                "@type": "PostalAddress",
                "addressCountry": "US",
            },
        },
        "spatialCoverage": {
            "@type": "Place",
            "name": region_name,
            "address": {
                "@type": "PostalAddress",
                "addressCountry": "US",
            },
        },
    }

    schema_json = json.dumps(schema_obj, ensure_ascii=False)
    schema_block = f'<script type="application/ld+json">\n{schema_json}\n</script>\n'

    # 2. Generate Internal Links
    links_block = _build_internal_links_html(zone_name)

    # 3. Prepend schema, append internal links
    enhanced_html = schema_block + content_html
    if links_block:
        enhanced_html += links_block

    return enhanced_html


# ==============================================================================
# 7. CONTENT GENERATOR (from content_generator.py)
# ==============================================================================

# Define the Gemini model we are using
MODEL_NAME = "gemini-2.5-flash"

# Timeout constant
API_TIMEOUT_SECONDS = 120

# Initialize the Gemini client here.
try:
    # Uses GEMINI_API_KEY from the config section (Section 2)
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Warning: Could not initialize Gemini client: {e}")
    client = None

# --- Constants for token control / compaction ---
MAX_CITIES_PER_ZONE = 15           # Hard cap on how many cities per zone we send to Gemini
MAX_ALERTS_PER_CITY = 2            # Max alerts to include per city
KEY_HOURLY_INDICES = [0, 12]       # Representative hourly points (~now and ~12h later)

# Markers used inside model output instead of full HTML
IMAGE_MARKER = "[[IMAGE_TAG_HERE]]"
DISCLAIMER_MARKER = "[[DISCLAIMER_HERE]]"

# --- JSON Schemas ---

# Final blog post schema
BLOG_POST_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "title": types.Schema(
            type=types.Type.STRING,
            description="A strong, SEO-optimized blog post title (max 70 characters)."
        ),
        "meta_description": types.Schema(
            type=types.Type.STRING,
            description="A concise summary of the content for search engines (max 160 characters)."
        ),
        "content_html": types.Schema(
            type=types.Type.STRING,
            description=(
                f"The complete HTML content of the blog post, including headers, paragraphs, and lists. "
                f"The content MUST include the image marker ('{IMAGE_MARKER}') near the top and "
                f"the disclaimer marker ('{DISCLAIMER_MARKER}') near the bottom. "
                f"Do not include <html>, <body>, <head>, or any <script> tags."
            )
        )
    },
    required=["title", "meta_description", "content_html"]
)

# --- Rate Limit / Retry Config (UPDATED FOR RESILIENCE) ---
MAX_RETRIES = 5 # Increased retries for better resilience
RETRY_DELAY_SECONDS = 5 # Starting delay for exponential backoff


# --- NEW RETRY UTILITY FOR GEMINI API ---
def call_gemini_api_with_retry(
    client: genai.Client,
    model: str,
    system_instruction: str,
    user_prompt: str,
    response_mime_type: str,
    response_schema: types.Schema,
    temperature: float
) -> Optional[str]:
    """
    Calls the Gemini API with a retry mechanism for transient errors (like 503 UNAVAILABLE or 429).
    Uses exponential backoff with jitter.
    """
    for attempt in range(MAX_RETRIES):
        try:
            print(f"  > Attempting content generation (Attempt {attempt + 1}/{MAX_RETRIES})...")

            # The actual Gemini API call
            response = client.models.generate_content(
                model=model,
                contents=[user_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type=response_mime_type,
                    response_schema=response_schema,
                    temperature=temperature,
                )
            )

            # Check if the response is valid (no failure reason)
            if response.candidates and response.candidates[0].finish_reason.name not in ('STOP', 'MAX_TOKENS'):
                 # Raise an error to trigger a retry for safety reasons if content was not fully generated
                raise Exception(f"Model finished with failure reason: {response.candidates[0].finish_reason.name}. Trying again.")

            return response.text.strip()

        # Catch API-specific errors, which include 503 (server error) and 429 (rate limit)
        except errors.APIError as e:
            error_code = getattr(e, 'code', 'Unknown')
            # Check for retry conditions: not the final attempt AND a retryable server error/rate limit
            is_retryable_error = (error_code == 503 or error_code == 429 or "UNAVAILABLE" in str(e))

            if attempt < MAX_RETRIES - 1 and is_retryable_error:
                # Calculate exponential backoff with jitter (a small random component)
                delay = RETRY_DELAY_SECONDS * (2 ** attempt) + random.uniform(0, 1)
                print(f"  > Transient API Error ({error_code}): {e.__class__.__name__}. Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
            else:
                # Re-raise the error if it's the last attempt or a non-retryable/unexpected error
                # We raise here, and the calling function (generate_content) will catch it and log the final failure.
                raise

        except Exception as e:
            # Catch other potential errors like network issues or the finish_reason error raised above
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_SECONDS * (2 ** attempt) + random.uniform(0, 1)
                print(f"  > General Error: {e.__class__.__name__}. Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
            else:
                # Re-raise for the calling function to handle the final failure
                raise

    # Fallback return (should only be reached if an exception was caught and handled in a way that prevents re-raising)
    return None


def generate_content(
    zone_name: str,
    nws_data: Dict[str, Any],
    image_tag: str,
    disclaimer_html: str,
) -> Optional[Dict[str, Any]]:
    """
    Generates the final blog post content, title, and meta description
    from the NWS data using the Gemini API, leveraging the retry utility.
    """
    if not client:
        print("FATAL: Gemini client not initialized due to missing API key.")
        return None

    # 1. Prune the NWS data to fit within the model's context window
    pruned_data = nws_data.copy()
    pruned_data["zone_name"] = zone_name
    pruned_data["cities"] = []

    # Iterate through cities and prune alerts/hourly data
    for city_data in nws_data.get("cities", []):
        pruned_city = city_data.copy()

        # Prune hourly data to only key indices
        if "hourly_forecast" in pruned_city and pruned_city["hourly_forecast"]:
            pruned_city["hourly_forecast"] = [
                pruned_city["hourly_forecast"][i]
                for i in KEY_HOURLY_INDICES
                if i < len(pruned_city["hourly_forecast"])
            ]

        # Prune alerts
        if "alerts" in pruned_city and pruned_city["alerts"]:
            pruned_city["alerts"] = pruned_city["alerts"][:MAX_ALERTS_PER_CITY]

        pruned_data["cities"].append(pruned_city)

        # Stop after MAX_CITIES_PER_ZONE
        if len(pruned_data["cities"]) >= MAX_CITIES_PER_ZONE:
            break

    # 2. Build the System Instruction / Prompt
    data_json = json.dumps(pruned_data, indent=2, ensure_ascii=False)

    system_instruction = (
        "You are an expert, data-driven, SEO-focused weather blogger. "
        "Your task is to analyze the provided JSON data from the National Weather Service (NWS) "
        "and generate a high-quality blog post about the current weather for the specified zone. "
        "You MUST return the output as a single JSON object matching the provided schema. "
        "The generated HTML must be well-structured, easy-to-read, and detailed. "
        
        # --- SEO IMPROVEMENT: Emphasize semantic structure and city names ---
        "**CRITICAL:** The first paragraph must be a unique, compelling summary that incorporates "
        "the main zone and key city names. Use semantic headers: one main `<h1>` (the title, implicitly the blog title itself), "
        "followed by detailed sections using `<h2>` and `<h3>` tags throughout the post. "
        "For example, use `<h2>Current Severe Weather Alerts` and `<h3>Forecast for [City Name]`. "
        "Ensure content is factually accurate based ONLY on the provided JSON data. "
        # -------------------------------------------------------------------
        
        f"You MUST include the placeholder image marker ('{IMAGE_MARKER}') near the top and "
        f"the disclaimer marker ('{DISCLAIMER_MARKER}') near the bottom of the 'content_html' field. "
        "Ensure the 'title' is under 70 characters and the 'meta_description' is under 160 characters. "
        "Prioritize severe weather alerts if present."
    )

    user_prompt = f"Generate a blog post based on the following NWS data for the '{zone_name}':\n\n{data_json}"

    # 3. Call the Gemini API with Retries (using the new utility)
    try:
        response_text = call_gemini_api_with_retry(
            client=client,
            model=MODEL_NAME,
            system_instruction=system_instruction,
            user_prompt=user_prompt,
            response_mime_type="application/json",
            response_schema=BLOG_POST_SCHEMA,
            temperature=0.6,
        )
    except Exception as e:
        # This catches the final re-raised exception from call_gemini_api_with_retry
        print(f"Unexpected error during content generation: {e.__class__.__name__}. Details: {e}")
        return None

    if not response_text:
        print("FAILURE: Content generation failed. No response text received after retries.")
        return None

    # 4. Process the successful response text
    try:
        result = json.loads(response_text)

        # Inject the real image tag and disclaimer HTML where the markers are
        content = result.get("content_html", "")
        if content:
            content = content.replace(IMAGE_MARKER, image_tag)
            content = content.replace(DISCLAIMER_MARKER, disclaimer_html)
            result["content_html"] = content

        return result

    except json.JSONDecodeError as e:
        print("FATAL: The model returned invalid JSON in the content generation step.")
        # print(f"Raw response text: {response_text[:200]}") # Uncomment for debugging
        print(f"Details: {e}")
        return None

    except Exception as e:
        print(f"Unexpected error during content processing/injection: {e}")
        return None


# ==============================================================================
# 8. API CLIENT (from api_client.py)
#    -- PERFORMANCE IMPROVEMENT: Refactored NWS fetching to use aiohttp/asyncio --
# ==============================================================================

# Note: BLOGGER_API_KEY, NWS_USER_AGENT, CLIENT_SECRETS_FILE, TOKEN_FILE are now global

# Blogger API Config
BLOGGER_API_BASE_URL = "https://www.googleapis.com/blogger/v3"
BLOGGER_SCOPES = ["https://www.googleapis.com/auth/blogger"]


# ========== OAUTH 2.0 CREDENTIALS (Synchronous) ==========

def get_oauth_credentials(client_secret_path: str) -> Optional[str]:
    """
    Handles the OAuth 2.0 flow: loads existing token, refreshes it, or starts a new
    interactive user authorization. Returns the raw access token string.
    (This remains synchronous as it is only called once per run)
    """
    creds = None
    token_path = Path(TOKEN_FILE) # Uses TOKEN_FILE from global constants

    # 1. Try to load existing credentials
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, BLOGGER_SCOPES)
        except Exception as e:
            print(f"Error loading token file: {e}. Starting new flow.")
            creds = None

    # 2. Refresh token if expired and refreshable
    if creds and creds.expired and creds.refresh_token:
        print("Refreshing expired Blogger token...")
        try:
            creds.refresh(Request())
        except Exception as e:
            print(f"Error refreshing token: {e}. Re-running full OAuth flow.")
            creds = None

    # 3. Perform a new flow if no valid credentials exist
    if not creds or not creds.valid:
        if not Path(client_secret_path).exists():
            print(f"FATAL: Client secrets file not found at '{client_secret_path}'. Cannot proceed with OAuth.")
            return None

        print("Starting new interactive OAuth 2.0 flow...")
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_path, BLOGGER_SCOPES
            )
            # Use 'localhost' flow for desktop apps
            creds = flow.run_local_server(port=0)

            # Save the new credentials
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            print(f"New token saved to {TOKEN_FILE}.")
        except Exception as e:
            print(f"Error during OAuth flow: {e}")
            return None

    if creds and creds.valid:
        return creds.token
    else:
        print("Failed to obtain valid Blogger credentials.")
        return None


# ========== ASYNCHRONOUS NWS API FETCHING (Performance Improvement) ==========

async def _get_api_response_async(session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, Any]]:
    """Async helper to fetch JSON data from an API concurrently."""
    headers = {
        "Accept": "application/geo+json",
        "User-Agent": NWS_USER_AGENT,
    }
    try:
        # Use aiohttp for concurrent requests
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            response.raise_for_status() # Raise exception for bad status codes
            return await response.json()
    except aiohttp.ClientResponseError as e:
        print(f"Error fetching data from NWS API ({url}): Status {e.status}")
        return None
    except aiohttp.ClientError as e:
        print(f"Error fetching data from NWS API ({url}): {e}")
        return None
    except Exception as e:
        print(f"Unexpected error during async fetch from {url}: {e}")
        return None


async def _fetch_alerts_async(session: aiohttp.ClientSession, grid_id: str, grid_x: int, grid_y: int) -> List[Dict[str, Any]]:
    """Async fetch current alerts for a grid point."""
    alerts_url = f"https://api.weather.gov/alerts/active?point={grid_id},{grid_x},{grid_y}"
    alerts_json = await _get_api_response_async(session, alerts_url)

    if not alerts_json:
        return []

    alerts = []
    for feature in alerts_json.get("features", []):
        properties = feature.get("properties", {})
        if properties.get("status") == "actual":
            alerts.append({
                "event": properties.get("event"),
                "severity": properties.get("severity"),
                "headline": properties.get("headline"),
                "area_description": properties.get("areaDesc"),
                "effective": properties.get("effective"),
                "expires": properties.get("expires"),
                "description": properties.get("description", "").strip(),
                "instruction": properties.get("instruction", "").strip(),
            })
    return alerts

async def _fetch_hourly_forecast_async(session: aiohttp.ClientSession, grid_id: str, grid_x: int, grid_y: int) -> List[Dict[str, Any]]:
    """Async fetch 48-hour hourly forecast for a grid point."""
    forecast_url = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}/forecast/hourly"
    forecast_json = await _get_api_response_async(session, forecast_url)

    if not forecast_json or "properties" not in forecast_json:
        return []

    periods = forecast_json["properties"].get("periods", [])
    hourly_data = []
    for period in periods:
        hourly_data.append({
            "time": period.get("startTime"),
            "temperature": period.get("temperature"),
            "windSpeed": period.get("windSpeed"),
            "windDirection": period.get("windDirection"),
            "shortForecast": period.get("shortForecast"),
            "dewpoint": period.get("dewpoint", {}).get("value"),
            "relativeHumidity": period.get("relativeHumidity", {}).get("value"),
        })

    return hourly_data

async def _fetch_7_day_forecast_async(session: aiohttp.ClientSession, grid_id: str, grid_x: int, grid_y: int) -> List[Dict[str, Any]]:
    """Async fetch 7-day text forecast for a grid point."""
    forecast_url = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}/forecast"
    forecast_json = await _get_api_response_async(session, forecast_url)

    if not forecast_json or "properties" not in forecast_json:
        return []

    periods = forecast_json["properties"].get("periods", [])
    daily_data = []
    for period in periods:
        daily_data.append({
            "name": period.get("name"),
            "isDaytime": period.get("isDaytime"),
            "temperature": period.get("temperature"),
            "shortForecast": period.get("shortForecast"),
            "detailedForecast": period.get("detailedForecast"),
        })

    return daily_data

async def _process_city_forecast_async(session: aiohttp.ClientSession, city_config: Dict[str, Any]) -> Dict[str, Any]:
    """Runs all fetches for a single city concurrently."""
    city_name = city_config["city"]
    grid_id = city_config["grid_id"]
    grid_x = city_config["grid_x"]
    grid_y = city_config["grid_y"]

    print(f"  > Starting concurrent fetch for {city_name}...")

    # Create a list of all fetching coroutines for the city
    tasks = [
        _fetch_alerts_async(session, grid_id, grid_x, grid_y),
        _fetch_hourly_forecast_async(session, grid_id, grid_x, grid_y),
        _fetch_7_day_forecast_async(session, grid_id, grid_x, grid_y),
    ]

    # Run all tasks concurrently and wait for them to complete
    alerts, hourly_forecast, daily_forecast = await asyncio.gather(*tasks)

    city_data = {
        "city": city_name,
        "alerts": alerts,
        "hourly_forecast": hourly_forecast,
        "daily_forecast": daily_forecast,
        "has_alerts": bool(alerts),
    }
    return city_data

async def get_nws_forecast_async(zone_name: str, city_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Manages the concurrent fetching of NWS data for all cities in a zone.
    """
    print(f"--- Starting Concurrent NWS Fetch for {zone_name} ({len(city_list)} cities) ---")
    
    # Use a single ClientSession for all concurrent requests
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=20)) as session:
        tasks = []
        for city_config in city_list:
            tasks.append(_process_city_forecast_async(session, city_config))
        
        # Run all city processing tasks concurrently
        city_results = await asyncio.gather(*tasks)

    zone_data = {"cities": city_results}
    zone_data["has_alerts"] = any(city["has_alerts"] for city in zone_data["cities"])
    print(f"--- Concurrent NWS data fetching complete for {zone_name}. Alerts: {zone_data['has_alerts']} ---")
    return zone_data

# ========== BLOGGER POSTING (Synchronous) ==========

def post_to_blogger(
    blog_id: str,
    title: str,
    content_html: str,
    client_secret_path: str,
    labels: Optional[List[str]] = None,
) -> bool:
    """
    Posts content to the specified Blogger blog using OAuth 2.0 credentials.
    Uses the REST API directly via requests (synchronous).
    """
    access_token = get_oauth_credentials(client_secret_path)
    if not access_token:
        print("Failed to obtain Blogger access token.")
        return False

    base_url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    if labels is None or not labels:
        labels = ["Weather Forecast", "USA", "NationalWeatherService"]

    post_data = {
        "kind": "blogger#post",
        "blog": {"id": blog_id},
        "title": title,
        "content": content_html,
        "labels": labels,
    }

    try:
        time.sleep(1)  # avoid hammering the API
        response = requests.post(base_url, headers=headers, json=post_data)
        response.raise_for_status()
        print("Post successful.")
        return True

    except requests.exceptions.RequestException as e:
        print(f"Error posting to Blogger: {e}")
        try:
            error_details = response.json()
            print(f"API Error Details: {json.dumps(error_details, indent=2)}")
        except Exception:
            pass
        return False


# ==============================================================================
# 9. ALTERNATIVE BLOGGER UTILITIES (from blogger_api_util.py / blogger_post.py)
#    - Included for completeness but NOT used by the main execution loop
# ==============================================================================

def get_creds_alt():
    """Alternative: Handles OAuth 2.0 flow to get and refresh credentials for Blogger API (using googleapiclient dependencies)."""
    # Note: Uses global constants: TOKEN_FILE, CLIENT_SECRETS_FILE, BLOGGER_SCOPES
    creds = None
    token_path = Path(TOKEN_FILE)
    _ALT_SCOPES = BLOGGER_SCOPES # Use the same scopes list

    # 1. Try to load existing credentials
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, _ALT_SCOPES)

    # 2. Refresh token if expired and refreshable
    if creds and creds.expired and creds.refresh_token:
        print("Refreshing expired token...")
        try:
            creds.refresh(Request())
            # Save the refreshed token
            with open(TOKEN_FILE, 'w') as f:
                f.write(creds.to_json())
        except Exception as e:
            print(f"Error refreshing token: {e}. Re-running full OAuth flow.")
            creds = None

    # 3. Perform new flow
    if not creds or not creds.valid:
        print("Starting new interactive OAuth 2.0 flow...")
        if not Path(CLIENT_SECRETS_FILE).exists():
            print(f"FATAL: Client secrets file not found at '{CLIENT_SECRETS_FILE}'. Cannot proceed with OAuth.")
            return None

        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, _ALT_SCOPES)
        creds = flow.run_local_server(port=0)  # opens browser for user consent

        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
        print(f"New token saved to {TOKEN_FILE}.")

    return creds

def create_post_alt(title, content_html, is_draft=False):
    """Alternative: Creates a post using the googleapiclient library (NOT USED by main loop)."""
    # Note: Uses global constant: BLOG_ID
    creds = get_creds_alt()
    if not creds:
        print("Could not get credentials. Aborting post creation.")
        return None

    service = build('blogger', 'v3', credentials=creds)
    body = {
        'title': title,
        'content': content_html,
    }

    try:
        # Call the API to insert the post, passing isDraft as a query parameter
        post = service.posts().insert(
            blogId=BLOG_ID,
            body=body,
            isDraft=is_draft
        ).execute()
        return post
    except Exception as e:
        print(f"An error occurred while creating the post: {e}")
        return None

# ==============================================================================
# 10. MAIN EXECUTION LOGIC (from main.py)
# ==============================================================================

def get_last_zone() -> Optional[str]:
    """Reads the name of the last zone that was successfully posted."""
    try:
        with open(STATE_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def update_last_zone(zone_name: str):
    """Writes the name of the most recently posted zone."""
    try:
        with open(STATE_FILE, "w") as f:
            f.write(zone_name)
    except Exception as e:
        print(f"Warning: Could not save state to {STATE_FILE}: {e}")

def get_next_zone() -> str:
    """
    Determines the next zone to process based on a rotation list.
    """
    last_zone = get_last_zone()
    rotation_list = ZONE_ROTATION
    num_zones = len(rotation_list)

    if not last_zone or last_zone not in rotation_list:
        # Start at the first zone in the rotation
        print(f"Starting rotation: Last zone '{last_zone}' not found or invalid. Using first zone.")
        return rotation_list[0]

    try:
        # Find the index of the last posted zone
        last_index = rotation_list.index(last_zone)
        # Calculate the index of the next zone in the circular list
        next_index = (last_index + 1) % num_zones
        return rotation_list[next_index]
    except ValueError:
        # Fallback
        print("Error in rotation logic. Falling back to first zone.")
        return rotation_list[0]


def main():
    """
    Main execution loop.
    """
    # Check essential configurations before proceeding
    if not NWS_USER_AGENT or not BLOG_ID or not BLOG_BASE_URL or not GEMINI_API_KEY:
        print("\nFATAL: One or more essential environment variables (GEMINI_API_KEY, NWS_USER_AGENT, BLOG_ID, BLOG_BASE_URL) are missing or invalid.")
        print("Please check your .env file or environment settings.")
        return

    # 1) Determine the next zone to process
    target_zone_name = get_next_zone()
    target_zone_data = NWS_ZONES.get(target_zone_name)

    if not target_zone_data:
        print(f"FATAL: Zone data not found for '{target_zone_name}'. Check NWS_ZONES definition.")
        return

    print(f"\n==================================================")
    print(f"   STARTING POST GENERATION FOR: {target_zone_name}")
    print(f"   Publish Mode: {'ON' if PUBLISH else 'OFF (Local Save Only)'}")
    print(f"==================================================")

    city_list = target_zone_data["cities"]

    # 2) Fetch NWS forecast data CONCURRENTLY
    # NOTE: We use asyncio.run to execute the async function from the sync main()
    nws_data = asyncio.run(get_nws_forecast_async(target_zone_name, city_list))

    # Simple check for empty data
    if not nws_data.get("cities") or all(not c.get('hourly_forecast') for c in nws_data['cities']):
        print(f"FAILURE: Could not retrieve any meaningful forecast data for {target_zone_name}.")
        return

    # 3) Build placeholder image tag and disclaimer HTML
    image_tag = build_placeholder_image_tag(target_zone_name)
    # DISCLAIMER_HTML is a global constant

    # 4) Generate content with the Gemini model
    print("\n--- Generating content with Gemini API... ---")
    blog_payload = generate_content(
        zone_name=target_zone_name,
        nws_data=nws_data,
        image_tag=image_tag,
        disclaimer_html=DISCLAIMER_HTML,
    )

    if not blog_payload:
        print(f"FAILURE: Content generation failed for {target_zone_name}.")
        return

    title = blog_payload["title"]
    meta_description = blog_payload.get("meta_description", "")
    content_html = blog_payload["content_html"]

    # 5) Inject SEO schema + internal links
    print("\n--- Injecting SEO and Internal Links ---")
    content_html = inject_seo_and_links(
        content_html=content_html,
        title=title,
        zone_name=target_zone_name,
        meta_description=meta_description,
    )

    # 6) Save locally and update indexes (dashboard, archive, categories, sitemap)
    print("\n--- Saving post locally and updating indexes ---")
    post_meta = save_post_and_update_indexes(
        title=title,
        meta_description=meta_description,
        content_html=content_html,
        zone_name=target_zone_name,
    )

    # 7) If publishing is enabled, also send to Blogger
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
        print(f"\nSUCCESS: Post for {target_zone_name} saved locally. Skipping Blogger post (PUBLISH=false).")
        update_last_zone(target_zone_name)


if __name__ == "__main__":
    main()