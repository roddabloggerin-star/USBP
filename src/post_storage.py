# src/post_storage.py

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

OUTPUT_DIR = Path("output_posts")
INDEX_FILE = OUTPUT_DIR / "posts_index.json"

# Optional base URL for sitemap.xml (e.g. "https://usa-weather-updates.blogspot.com")
BLOG_BASE_URL = os.getenv("BLOG_BASE_URL", "").rstrip("/")


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


# ---------- Utility functions ----------

def _safe_slug(text: str, max_len: int = 80) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text)
    return text[:max_len] or "post"


def _load_index() -> List[PostMeta]:
    if not INDEX_FILE.exists():
        return []
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        posts: List[PostMeta] = [PostMeta(**p) for p in data]
        return posts
    except Exception as e:
        print(f"WARNING: Could not read {INDEX_FILE}: {e}")
        return []


def _save_index(posts: List[PostMeta]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in posts], f, ensure_ascii=False, indent=2)


# ---------- Tag generation ----------

KEYWORD_TAGS = {
    "snow": "Snow",
    "blizzard": "Blizzard",
    "cold": "Cold Wave",
    "chill": "Cold Wave",
    "freezing": "Freezing Temperatures",
    "frost": "Frost",
    "ice": "Ice",
    "storm": "Storms",
    "thunderstorm": "Thunderstorms",
    "severe": "Severe Weather",
    "tornado": "Tornado Risk",
    "flood": "Flooding",
    "rain": "Heavy Rain",
    "showers": "Rain Showers",
    "heat": "Heatwave",
    "hot": "Heatwave",
    "wildfire": "Wildfire Risk",
    "smoke": "Air Quality",
    "air quality": "Air Quality",
    "wind": "High Winds",
    "gust": "High Winds",
    "travel": "Travel Disruptions",
    "aviation": "Aviation Weather",
}


def auto_generate_tags(title: str, content_html: str, zone_name: str) -> List[str]:
    corpus = f"{title}\n{content_html}".lower()
    tags = set()

    if zone_name:
        tags.add(zone_name)
        # also add broader geo tags
        if "eastern" in zone_name.lower():
            tags.add("Eastern US")
        if "central" in zone_name.lower():
            tags.add("Central US")
        if "western" in zone_name.lower():
            tags.add("Western US")
        if "southern" in zone_name.lower():
            tags.add("Southern US")

    for kw, tag in KEYWORD_TAGS.items():
        if kw in corpus:
            tags.add(tag)

    # Always add general tags
    tags.add("USA Weather")
    tags.add("Weather Forecast")

    return sorted(tags)


# ---------- Page generators ----------

def _generate_dashboard_page(posts: List[PostMeta]) -> None:
    """
    output_posts/index.html - a simple dashboard to open
    generated posts and copy/paste into Blogger.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Newest first
    posts_sorted = sorted(posts, key=lambda p: p.created_at, reverse=True)

    rows = []
    for p in posts_sorted:
        rows.append(
            f"<tr>"
            f"<td>{p.created_at[:10]}</td>"
            f"<td>{p.zone_name}</td>"
            f"<td><a href=\"./{p.filename}\" target=\"_blank\">{p.title}</a></td>"
            f"<td>{', '.join(p.tags)}</td>"
            f"</tr>"
        )
    rows_html = "\n".join(rows) if rows else "<tr><td colspan='4'>No posts yet.</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Generated Weather Posts Dashboard</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
th {{ background-color: #f0f0f0; }}
</style>
</head>
<body>
<h1>Generated Weather Posts Dashboard</h1>
<p>Use this page to open generated posts, copy the HTML into Blogger, and publish manually.</p>
<table>
<thead>
<tr>
  <th>Date</th>
  <th>Zone</th>
  <th>Title</th>
  <th>Tags</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</body>
</html>
"""
    with open(OUTPUT_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html)


def _generate_archive_page(posts: List[PostMeta]) -> None:
    """
    output_posts/archive.html - posts grouped by year-month.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Group by YYYY-MM
    archive: Dict[str, List[PostMeta]] = {}
    for p in posts:
        ym = p.created_at[:7]  # 'YYYY-MM'
        archive.setdefault(ym, []).append(p)

    # Sort months descending
    months_sorted = sorted(archive.keys(), reverse=True)

    sections = []
    for ym in months_sorted:
        year, month = ym.split("-")
        items = sorted(archive[ym], key=lambda p: p.created_at, reverse=True)
        lis = [
            f'<li>{p.created_at[:10]} – <a href="./{p.filename}" target="_blank">{p.title}</a> ({p.zone_name})</li>'
            for p in items
        ]
        ul = "<ul>\n" + "\n".join(lis) + "\n</ul>"
        sections.append(f"<h2>{year}-{month}</h2>\n{ul}")

    body_html = "\n".join(sections) if sections else "<p>No posts yet.</p>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Weather Blog Archive</title>
</head>
<body>
<h1>Weather Blog Archive</h1>
{body_html}
</body>
</html>
"""
    with open(OUTPUT_DIR / "archive.html", "w", encoding="utf-8") as f:
        f.write(html)


def _generate_category_pages(posts: List[PostMeta]) -> None:
    """
    output_posts/category-<slug>.html for each zone/category.
    Right now category = zone_name.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    by_category: Dict[str, List[PostMeta]] = {}
    for p in posts:
        by_category.setdefault(p.category, []).append(p)

    for category, plist in by_category.items():
        cat_slug = _safe_slug(category)
        plist_sorted = sorted(plist, key=lambda p: p.created_at, reverse=True)
        lis = [
            f'<li>{p.created_at[:10]} – <a href="./{p.filename}" target="_blank">{p.title}</a></li>'
            for p in plist_sorted
        ]
        ul = "<ul>\n" + "\n".join(lis) + "\n</ul>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{category} Weather Posts</title>
</head>
<body>
<h1>{category} Weather Posts</h1>
{ul}
</body>
</html>
"""
        with open(OUTPUT_DIR / f"category-{cat_slug}.html", "w", encoding="utf-8") as f:
            f.write(html)


def _generate_sitemap(posts: List[PostMeta]) -> None:
    """
    output_posts/sitemap.xml - basic XML sitemap.

    If BLOG_BASE_URL is configured, we build real URLs like:
      BLOG_BASE_URL/<slug>.html
    Otherwise, we skip URL entries (or you can fill them later).
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    if not BLOG_BASE_URL:
        print("NOTE: BLOG_BASE_URL is not set; sitemap.xml will use placeholder URLs.")
    url_entries = []

    for p in posts:
        if p.url:
            loc = p.url
        elif BLOG_BASE_URL:
            # best-effort guess; adjust to match your Blogger permalinks strategy
            loc = f"{BLOG_BASE_URL}/{p.slug}.html"
        else:
            # fallback placeholder
            loc = f"https://example.com/{p.slug}.html"

        lastmod = p.created_at.split("T")[0]
        url_entries.append(
            f"<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>"
        )

    urls_xml = "\n".join(url_entries)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls_xml}
</urlset>
"""
    with open(OUTPUT_DIR / "sitemap.xml", "w", encoding="utf-8") as f:
        f.write(xml)


def regenerate_all_indexes_and_sitemap() -> None:
    """
    Rebuild dashboard, archive, category pages, and sitemap
    from posts_index.json. Safe to call every time.
    """
    posts = _load_index()
    _generate_dashboard_page(posts)
    _generate_archive_page(posts)
    _generate_category_pages(posts)
    _generate_sitemap(posts)


# ---------- Public main entry: save post + update everything ----------

def save_post_and_update_indexes(
    title: str,
    meta_description: str,
    content_html: str,
    zone_name: str,
) -> PostMeta:
    """
    Saves a full HTML file for the post, updates posts_index.json,
    and regenerates:
      - index.html (dashboard)
      - archive.html
      - category-*.html
      - sitemap.xml

    Returns the PostMeta for this post (including tags and filename).
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Timestamp & slug
    now = datetime.now(timezone.utc)
    iso_now = now.isoformat()
    date_str = now.strftime("%Y-%m-%d")
    slug = _safe_slug(title)
    post_id = f"{date_str}-{slug}"
    filename = f"{post_id}.html"

    # Tags & category
    tags = auto_generate_tags(title, content_html, zone_name)
    category = zone_name or "USA Weather"

    # Wrap into full HTML document
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<meta name="description" content="{meta_description}" />
</head>
<body>
{content_html}
</body>
</html>
"""

    # Write HTML file
    with open(OUTPUT_DIR / filename, "w", encoding="utf-8") as f:
        f.write(full_html)

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
        url=None,  # you can fill this manually later if you want exact Blogger URL
    )

    # upsert by id
    existing_idx = next((i for i, p in enumerate(posts) if p.id == post_id), None)
    if existing_idx is not None:
        posts[existing_idx] = meta
    else:
        posts.append(meta)

    _save_index(posts)
    regenerate_all_indexes_and_sitemap()

    print(f"\n✅ BLOG POST SAVED LOCALLY: {OUTPUT_DIR / filename}")
    return meta
