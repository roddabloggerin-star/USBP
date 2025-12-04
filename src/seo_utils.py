# src/seo_utils.py

from datetime import datetime, timezone
import json
from typing import List


def _build_internal_links_html(current_zone: str) -> str:
    """
    Builds an 'Explore Other US Regions' block.
    Adjust the zone names/URLs if your structure is different.
    """
    # Known zones – adjust to match your NWS_ZONES keys if needed
    zones: List[str] = [
        "Eastern Zone",
        "Western Zone",
        "Central Zone",
        "Southern Zone",
    ]

    other_zones = [z for z in zones if z != current_zone]
    if not other_zones:
        return ""

    # You can later replace href="#" with real URLs for each zone landing page.
    items = "\n".join(
        f'  <li><a href="#">{z} Weather Forecast</a></li>'
        for z in other_zones
    )

    return (
        "<h2>Explore Other US Regions</h2>\n"
        "<ul>\n"
        f"{items}\n"
        "</ul>\n"
    )


def inject_seo_and_links(content_html: str, title: str, zone_name: str) -> str:
    """
    Injects:
      - Article schema (JSON-LD)
      - Internal links block at the bottom
    into the given HTML content.
    """
    now = datetime.now(timezone.utc).isoformat()

    schema_obj = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
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
            "@id": "https://unitedstatesweatherupdates.blogspot.com/",
        },
        "articleSection": zone_name,
        "keywords": [
            "USA weather",
            f"{zone_name} forecast",
            "weather alerts",
            "storm updates",
            "climate news",
            "today weather",
        ],
    }

    schema_json = json.dumps(schema_obj, ensure_ascii=False)
    schema_block = f'<script type="application/ld+json">\n{schema_json}\n</script>\n'

    links_block = _build_internal_links_html(zone_name)

    # Prepend schema, append internal links
    enhanced_html = schema_block + content_html
    if links_block:
        enhanced_html = enhanced_html + "\n" + links_block

    return enhanced_html
