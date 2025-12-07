# src/seo_utils.py

from datetime import datetime, timezone
import json
import os
import re
from typing import List
from urllib.parse import quote

# Optional base URL for canonical + internal links
# Example (in .env):
#   BLOG_BASE_URL=https://unitedstatesweatherupdates.blogspot.com
BLOG_BASE_URL = os.getenv("BLOG_BASE_URL", "").rstrip("/")


def _safe_slug(text: str, max_len: int = 80) -> str:
    """
    Slugify helper used to approximate a canonical URL
    based on the post title. This will NOT always match
    Blogger exactly, but it's good enough for JSON-LD.
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text)
    return text[:max_len] or "post"


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


def _build_internal_links_html(current_zone: str) -> str:
    """
    Builds an 'Explore Other US Regions' block with REAL URLs
    instead of href="#", using BLOG_BASE_URL + /search/label/<Zone>.
    If BLOG_BASE_URL is not set, falls back to '#'.
    """

    zones: List[str] = [
        "Eastern Zone",
        "Western Zone",
        "Central Zone",
        "Southern Zone",
    ]

    other_zones = [z for z in zones if z != current_zone]
    if not other_zones:
        return ""

    items: List[str] = []
    for z in other_zones:
        if BLOG_BASE_URL:
            # Blogger label pages follow /search/label/<label>
            label_part = quote(z, safe="")
            href = f"{BLOG_BASE_URL}/search/label/{label_part}"
        else:
            href = "#"

        items.append(f'  <li><a href="{href}">{z} Weather Forecast</a></li>')

    return (
        "<h2>Explore Other US Regions</h2>\n"
        "<ul>\n"
        + "\n".join(items)
        + "\n</ul>\n"
    )


def inject_seo_and_links(
    content_html: str,
    title: str,
    zone_name: str,
    meta_description: str = "",
) -> str:
    """
    Injects:
      - Article/BlogPosting schema (JSON-LD) with:
          * url (best-effort canonical)
          * mainEntityOfPage pointing to this article
          * inLanguage = en-US
          * geo fields (contentLocation, spatialCoverage)
          * richer, zone-aware keywords
      - Internal 'Explore Other US Regions' links.

    The resulting HTML is:
      <script type="application/ld+json"> ... </script>
      <existing content_html ...>
      <Explore Other US Regions ...>
    """
    now = datetime.now(timezone.utc).isoformat()
    region_name = _zone_to_region_name(zone_name)

    # Approximate canonical URL from title + BLOG_BASE_URL
    slug = _safe_slug(title)
    if BLOG_BASE_URL:
        canonical_url = f"{BLOG_BASE_URL}/{slug}.html"
    else:
        # Fallback placeholder (still better than homepage-only)
        canonical_url = f"https://example.com/{slug}.html"

    # Description fallback if meta_description is empty
    if not meta_description:
        meta_description = (
            f"Detailed weather forecast for the {region_name}, including "
            f"conditions, travel advice, and alerts for key cities."
        )

    # Base NWS national map as representative image
    image_url = "https://www.weather.gov/wwamap/png/US.png"

    # Build stronger keyword set
    keywords: List[str] = [
        "USA weather",
        f"{region_name} weather",
        f"{zone_name} forecast",
        "weather alerts",
        "storm updates",
        "travel weather",
        "today's forecast",
    ]

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

    links_block = _build_internal_links_html(zone_name)

    # Prepend schema, append internal links
    enhanced_html = schema_block + content_html
    if links_block:
        enhanced_html = enhanced_html + "\n" + links_block

    return enhanced_html
