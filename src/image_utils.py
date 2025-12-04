# src/image_utils.py

"""
Utilities for building image tags for the blog posts.

IMPORTANT:
- We use a normal HTTP URL for the image.
- We do NOT inline base64 image data (that caused 2.2MB HTML and Blogger 400 errors).
"""

PLACEHOLDER_IMAGE_URL = "https://www.weather.gov/wwamap/png/US.png"


def build_placeholder_image_tag(zone_name: str) -> str:
    """
    Returns a lightweight <img> tag using a normal HTTP URL instead of
    a huge base64 data URI. Safe for Blogger and keeps token usage low.
    """
    # sanitize alt text
    safe_zone = zone_name.replace('"', "").replace("<", "").replace(">", "")
    alt_text = f"{safe_zone} Weather Overview"

    return (
        f'<img src="{PLACEHOLDER_IMAGE_URL}" '
        f'alt="{alt_text}" '
        'style="max-width:100%;height:auto;border-radius:8px;" '
        '<p><em>Live National Weather Service alert map (updates automatically).</em></p>'
        
    )
