# src/post_storage.py

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

load_dotenv()

# ---------- Existing Constants ----------

OUTPUT_DIR = Path("output_posts")
INDEX_FILE = OUTPUT_DIR / "posts_index.json"

# Optional base URL for sitemap.xml (e.g. "https://usa-weather-updates.blogspot.com")
BLOG_BASE_URL = os.getenv("BLOG_BASE_URL", "").rstrip("/")

# Blogger publishing environment (used below)
BLOG_ID = os.getenv("BLOG_ID")
CLIENT_SECRETS_FILE = os.getenv("CLIENT_SECRETS_FILE")


# ==================== Dataclass ====================

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
    url: Optional[str]    # optional final blog URL (can be None)


# ==================== Existing Utilities ====================

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


# ==================== Tag Generation ====================

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

    tags.add("USA Weather")
    tags.add("Weather Forecast")

    return sorted(tags)


# ==================== Page Generation Helpers ====================

def _generate_dashboard_page(posts: List[PostMeta]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
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
    rows_html = "\n".join(rows) or "<tr><td colspan='4'>No posts yet.</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Generated Weather Posts Dashboard</title></head>
<body>
<h1>Generated Weather Posts Dashboard</h1>
<table><thead><tr><th>Date</th><th>Zone</th><th>Title</th><th>Tags</th></tr></thead><tbody>
{rows_html}
</tbody></table>
</body>
</html>
"""
    with open(OUTPUT_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html)


def _generate_archive_page(posts: List[PostMeta]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    archive: Dict[str, List[PostMeta]] = {}
    for p in posts:
        ym = p.created_at[:7]
        archive.setdefault(ym, []).append(p)

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
    html = f"<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\"><title>Weather Blog Archive</title></head><body><h1>Weather Blog Archive</h1>{body_html}</body></html>"

    with open(OUTPUT_DIR / "archive.html", "w", encoding="utf-8") as f:
        f.write(html)


def _generate_category_pages(posts: List[PostMeta]) -> None:
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
        html = f"<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\"><title>{category} Weather Posts</title></head><body><h1>{category} Weather Posts</h1><ul>{''.join(lis)}</ul></body></html>"
        with open(OUTPUT_DIR / f"category-{cat_slug}.html", "w", encoding="utf-8") as f:
            f.write(html)


def _generate_sitemap(posts: List[PostMeta]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    if not BLOG_BASE_URL:
        print("NOTE: BLOG_BASE_URL is not set; sitemap.xml will use placeholder URLs.")
    url_entries = []
    for p in posts:
        if p.url:
            loc = p.url
        elif BLOG_BASE_URL:
            loc = f"{BLOG_BASE_URL}/{p.slug}.html"
        else:
            loc = f"https://example.com/{p.slug}.html"
        lastmod = p.created_at.split("T")[0]
        url_entries.append(f"<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    xml = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n{''.join(url_entries)}\n</urlset>"
    with open(OUTPUT_DIR / "sitemap.xml", "w", encoding="utf-8") as f:
        f.write(xml)


def regenerate_all_indexes_and_sitemap() -> None:
    posts = _load_index()
    _generate_dashboard_page(posts)
    _generate_archive_page(posts)
    _generate_category_pages(posts)
    _generate_sitemap(posts)


# ==================== Save + Index Functionality ====================

def save_post_and_update_indexes(
    title: str,
    meta_description: str,
    content_html: str,
    zone_name: str,
) -> PostMeta:
    OUTPUT_DIR.mkdir(exist_ok=True)

    now = datetime.now(timezone.utc)
    iso_now = now.isoformat()
    date_str = now.strftime("%Y-%m-%d")
    slug = _safe_slug(title)
    post_id = f"{date_str}-{slug}"
    filename = f"{post_id}.html"

    tags = auto_generate_tags(title, content_html, zone_name)
    category = zone_name or "USA Weather"

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{title}</title><meta name="description" content="{meta_description}" /></head>
<body>{content_html}</body></html>
"""

    with open(OUTPUT_DIR / filename, "w", encoding="utf-8") as f:
        f.write(full_html)

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
        url=None,
    )

    existing_idx = next((i for i, p in enumerate(posts) if p.id == post_id), None)
    if existing_idx is not None:
        posts[existing_idx] = meta
    else:
        posts.append(meta)

    _save_index(posts)
    regenerate_all_indexes_and_sitemap()

    print(f"\n✅ BLOG POST SAVED LOCALLY: {OUTPUT_DIR / filename}")
    return meta


# ==================== New Publishing Helpers ====================

def ensure_output_dir(dir_path: Path) -> None:
    """
    Ensure output directory exists (helper for publishing).
    """
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating directory {dir_path}: {e}")


def save_post_locally(post_html: str, post_title: str, output_dir: Path) -> Path:
    """
    Save post HTML content under a safe filename.
    """
    safe_name = post_title.strip().replace(" ", "_").replace("/", "_")
    filename = f"{safe_name}.html"
    file_path = output_dir.joinpath(filename)

    ensure_output_dir(output_dir)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(post_html)
        print(f"Post saved locally at: {file_path}")
    except Exception as e:
        print(f"Error saving post locally: {e}")

    return file_path


def publish_to_blogger(
    post_html: str,
    post_title: str,
    blog_id: str,
    labels: list[str],
    client_secrets_file: str,
) -> bool:
    """
    Publish a post to Blogger using the existing post_to_blogger in api_client.
    """
    try:
        from src.api_client import post_to_blogger
    except ImportError as exc:
        print(f"Could not import post_to_blogger: {exc}")
        return False

    try:
        success = post_to_blogger(
            blog_id=blog_id,
            title=post_title,
            content_html=post_html,
            client_secret_path=client_secrets_file,
            labels=labels,
        )
        return bool(success)
    except Exception as e:
        print(f"Error sending to Blogger API: {e}")
        return False


def save_post_locally_and_publish(
    post_html: str,
    output_dir: Path,
    post_title: str,
    publish: bool = True,
    labels: list[str] | None = None,
) -> bool:
    """
    Save the post locally and optionally publish via Blogger API.
    Returns True on success.
    """
    saved_path = save_post_locally(post_html, post_title, output_dir)

    if publish and BLOG_ID and CLIENT_SECRETS_FILE:
        print(f"Publishing '{post_title}' to Blogger (blog ID: {BLOG_ID}) ...")
        ok = publish_to_blogger(
            post_html,
            post_title,
            BLOG_ID,
            labels or [],
            CLIENT_SECRETS_FILE,
        )
        if ok:
            print("Successfully published post.")
            return True
        else:
            print("Failed to publish post.")
            return False

    print("Skipping Blogger publish (PUBLISH false or env not configured).")
    return True
