# src/image_utils.py

"""
Utilities for building image tags for the blog posts.

We now use a normal HTTP URL instead of inlining base64 image data.
This keeps HTML small and avoids Blogger 400 errors.
"""

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
