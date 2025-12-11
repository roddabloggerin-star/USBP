#!/usr/bin/env python3
"""
Main script that schedules and publishes weather blog posts.
This version has been updated to include charts via chart_utils.
"""

from __future__ import annotations
import logging
from pathlib import Path
import time

from dotenv import load_dotenv
from rich.logging import RichHandler

from src.api_client import NOAAApiClient
from src.image_utils import build_placeholder_image_tag
from src.chart_utils import build_inline_charts_html
from src.content_generator import generate_blog_content
from src.post_storage import save_post_locally_and_publish

# Load .env variables
load_dotenv()

# Configure rich logging
logger = logging.getLogger("weather_blog_publisher")
logger.setLevel(logging.INFO)
handler = RichHandler()
logger.addHandler(handler)

# ===========================================================================
# ENVIRONMENT
# ===========================================================================

# Blogger settings -> from .env
BLOGGER_LABELS = ["Weather", "USA", "NWS", "Forecast"]

# Output directory
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR.joinpath("output_posts")

# ===========================================================================
# NOAA/NWS API
# ===========================================================================

API_CLIENT = NOAAApiClient()

# ===========================================================================
# MAIN LOGIC
# ===========================================================================


def publish_weather_post(region: str, location: str) -> bool:
    """
    Publish a post for given region and location name
    Returns True if successfully published/created locally else False.
    """

    # 1. Fetch forecast + current conditions + alerts
    logger.info(f"Fetching weather for: {region} ({location})")
    cities_forecasts = API_CLIENT.fetch_weather_for_location(location)

    # If no data, skip
    if not cities_forecasts:
        logger.warning(f"No forecast data for {region}. Skipping.")
        return False

    # 2. Build the chart / image HTML
    # -------------------------------------------------
    # a) Always include the US map placeholder
    placeholder_html = build_placeholder_image_tag(region)

    # b) Try to find hourly periods from any city in this zone
    rep_periods = None
    for city_name, city_obj in cities_forecasts.items():
        fh = city_obj.get("forecast_hourly") or {}
        periods = fh.get("periods")
        if periods:
            rep_periods = periods
            break

    # c) Construct image_tag
    if rep_periods:
        # Generate up to 4 charts + US map
        image_tag = build_inline_charts_html(
            rep_periods,
            zone_name=region,
            include_map_placeholder=True,
            placeholder_html=placeholder_html,
        )
    else:
        # If no hourly, just embed the map
        image_tag = placeholder_html

    # 3. Prepare blog content HTML from template
    logger.info(f"Generating content for {region}.")
    html_body = generate_blog_content(
        region_name=region,
        forecasts_by_city=cities_forecasts,
        image_tag=image_tag,
        labels=BLOGGER_LABELS,
    )

    # 4. Save locally and (if configured) publish
    logger.info(f"Saving & posting {region} blog entry.")
    success = save_post_locally_and_publish(
        post_html=html_body,
        output_dir=OUTPUT_DIR,
        post_title=region,
    )

    return success


def run_scheduler() -> None:
    """
    You can customize to run periodically, for now runs once
    """
    TARGET_LOCATIONS = [
        ("USA National Forecast", "United States"),
    ]
    for region, loc in TARGET_LOCATIONS:
        try:
            ok = publish_weather_post(region, loc)
            if ok:
                logger.info(f"Published: {region}")
            else:
                logger.error(f"Failed publish: {region}")
        except Exception as exc:
            logger.exception(f"Error publishing {region}: {exc}")


if __name__ == "__main__":
    start = time.time()
    run_scheduler()
    logger.info(f"Done in {time.time() - start:.2f}s")
