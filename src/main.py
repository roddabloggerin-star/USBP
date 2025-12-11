#!/usr/bin/env python3
"""
Main script that schedules and publishes weather blog posts.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv
from rich.logging import RichHandler

from src.api_client import NOAAApiClient
from src.chart_utils import build_inline_charts_html
from src.content_generator import generate_blog_content
from src.post_storage import save_post_locally_and_publish

# -----------------------------------------------------------------------------
# Load environment
# -----------------------------------------------------------------------------

load_dotenv()

# Blogger labels (used when publishing to Blogger)
BLOGGER_LABELS = ["Weather", "USA", "NWS", "Forecast"]

# Output directory for local saves
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR.joinpath("output_posts")

# NOAA/NWS API client (requires NWS_USER_AGENT in env)
API_CLIENT = NOAAApiClient()

# Logger
logger = logging.getLogger("weather_blog_publisher")
logger.setLevel(logging.INFO)
handler = RichHandler()
logger.addHandler(handler)


# -----------------------------------------------------------------------------
# Publish function
# -----------------------------------------------------------------------------

def publish_weather_post(region: str, location: str) -> bool:
    """
    Fetch weather and publish a blog post for the specified region/location.
    """

    logger.info(f"Fetching weather for: {region} ({location})")

    # 1) Fetch forecasts for the given location
    cities_forecasts: dict[str, dict[str, Any]] = API_CLIENT.fetch_weather_for_location(location)

    if not cities_forecasts:
        logger.warning(f"No forecast data for {region}. Skipping.")
        return False

    # 2) Build charts and map placeholder HTML
    placeholder_html = build_placeholder_image_tag(region)

    # Choose representative hourly forecast periods
    rep_periods = None
    for city_obj in cities_forecasts.values():
        fh = city_obj.get("forecast_hourly") or {}
        periods = fh.get("periods") if isinstance(fh, dict) else None
        if periods:
            rep_periods = periods
            break

    if rep_periods:
        image_tag = build_inline_charts_html(
            rep_periods,
            zone_name=region,
            include_map_placeholder=True,
            placeholder_html=placeholder_html,
        )
    else:
        image_tag = placeholder_html

    # 3) Create minimal city_data for Gemini prompt
    rep_city_name = next(iter(cities_forecasts.keys()), "")
    city_data = {
        "id": rep_city_name,
        "cities": [{"city": rep_city_name}]
    }

    # 4) Generate the blog content via Gemini
    result = generate_blog_content(
        region,
        city_data,
        cities_forecasts,
        image_tag,
        "",  # disclaimer; you can set a real HTML snippet if needed
    )

    if not result:
        logger.error(f"Error generating blog content for {region}. Skipping publish.")
        return False

    title = result.get("title", region)
    meta_desc = result.get("meta_description", "")
    content_html = result.get("content_html", "")

    if not content_html:
        logger.error("Empty content returned by generate_blog_content(). Skipping.")
        return False

    # 5) Save locally and optionally publish
    logger.info(f"Saving & publishing post for: {region} — Title: {title}")

    success = save_post_locally_and_publish(
        post_html=content_html,
        output_dir=OUTPUT_DIR,
        post_title=title,
    )

    if not success:
        logger.error(f"Failed to save/publish post for {region}.")
    return success


# -----------------------------------------------------------------------------
# Script entry
# -----------------------------------------------------------------------------

def run_scheduler() -> None:
    """
    You can customize this list to rotate across zones or locations.
    For now, just one national forecast.
    """
    # List of (region, location search string) pairs
    targets = [
        ("USA National Forecast", "United States"),
    ]

    for region, loc in targets:
        try:
            ok = publish_weather_post(region, loc)
            if ok:
                logger.info(f"Published: {region}")
            else:
                logger.info(f"Skipped publish for: {region}")
        except Exception as exc:
            logger.exception(f"Unexpected error while publishing {region}: {exc}")


if __name__ == "__main__":
    start_time = time.time()
    run_scheduler()
    elapsed = time.time() - start_time
    logger.info(f"Done in {elapsed:.2f} seconds")
