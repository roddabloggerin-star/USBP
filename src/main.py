#!/usr/bin/env python3
"""
USA Weather Blogger – High-Traffic AI Strategy Edition
Python 3.12 / GitHub Actions Safe

FINAL MODIFICATIONS for 1000+ Daily View Goal:
... (Previous strategies)
9. **FIX:** Implemented explicit style cycling in the main loop to force title variety.
10. **FIX:** Removed unsupported argument in Blogger API for Archive Page update.
11. **FIX:** Added colon stripping to filename generation to fix artifact upload error.
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

# NEW REQUIRED IMPORTS for Google Trends and Data Analysis
import pandas as pd
from pytrends.request import TrendReq
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
# State file now tracks views and post history for scaling (Strategy #7)
STATE_FILE = Path(env("STATE_FILE", "bot_state.json")) 

# Blogger Auth Files
TOKEN_FILE = Path(env("TOKEN_FILE", "token.json"))
CLIENT_SECRETS_FILE = Path(env("CLIENT_SECRETS_FILE", "client_secrets.json"))

# ============================================================
# Gemini Model & Schema
# ============================================================
client = genai.Client(
    api_key=GEMINI_API_KEY
)

# Define the primary model and the fallback model
MODEL_PREFERENCE = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]

SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "title": types.Schema(type=types.Type.STRING, description="The emotional, high-impact SEO title."),
        "meta_description": types.Schema(type=types.Type.STRING, description="A meta description optimized for high search CTR."),
        "content_html": types.Schema(type=types.Type.STRING, description="The complete blog post content in HTML format."),
        "labels": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description="5-10 SEO tags/labels for the post."),
    },
    # Required to ensure the model outputs all necessary data for publishing
    required=["title", "meta_description", "content_html", "labels"],
)

# Define the three title styles to enforce variety (Fix #4)
TITLE_STYLES = [
    "Style 1 (Utility/Guide)",
    "Style 2 (Emotional/Shock)",
    "Style 3 (Listicle/Actionable)"
]


# ============================================================
# State Management (Strategy #7 Insight)
# ============================================================
def get_state() -> Dict[str, Any]:
    """Retrieves state, including view history for scaling analysis."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            log.warning("State file corrupted, resetting.")
    return {"daily_views": 0, "last_view_check": str(datetime.now() - relativedelta(days=1)), "post_history": {}}

def save_state(state: Dict[str, Any]):
    """Saves the bot's state."""
    STATE_FILE.write_text(json.dumps(state, indent=2))

# ============================================================
# Google Trends (Topic Selection) - Strategy #3
# ============================================================
def get_trending_topics(keywords: List[str] = None) -> List[str]:
    """Fetches trending US weather keywords for the last 3 days."""
    log.info("Fetching trending topics from Google Trends (pytrends)...")
    
    # Target audience is US, timeframe is last 3 days
    pytrends = TrendReq(hl='en-US', tz=360) 
    
    # Use general, high-level weather terms to find related breakout queries
    if not keywords:
         # Base keywords for initial search to find "rising" topics
         keywords = ["Severe weather", "Storm alert", "Tornado warning", "Flood risk", "Heat advisory"]

    try:
        pytrends.build_payload(
            keywords, 
            cat=17, # Category 17 is 'Science' (closest to weather trend analysis)
            timeframe='now 3-d', # Last 3 days
            geo='US' # Target Audience: United States (Strategy #8)
        )
        
        # Fetch related queries - focusing on RISING (breakout) topics for traffic spikes
        related = pytrends.related_queries()
        
        all_rising_topics = []
        for kw in keywords:
            # Safely extract rising queries
            data = related.get(kw, {}).get('rising', None)
            if isinstance(data, pd.DataFrame) and not data.empty:
                # Extract the top 15 most popular "rising" queries
                all_rising_topics.extend(data['query'].head(15).tolist())

        # Use a Set to unique the list and ensure content diversity
        unique_topics = list(set(all_rising_topics))
        
        if not unique_topics:
            log.warning("Google Trends returned no rising topics. Falling back to base keywords.")
            return keywords

        log.info("Found %d unique trending topics. Posting the top %d.", len(unique_topics), POSTS_PER_RUN)
        # Return enough topics for the daily post count
        return unique_topics[:POSTS_PER_RUN * 2] 

    except Exception as e:
        log.error("Error fetching Google Trends data: %s. Using default keywords.", e)
        # Fallback to base keywords if API fails
        return keywords


# ============================================================
# Gemini Content Generation - Strategy #5 & #6 (WITH FALLBACK AND VARIETY)
# ============================================================
def generate_post(trending_topic: str, required_style: str) -> Dict[str, Any]:
    """Generates an evergreen, SEO-heavy blog post based on a trending topic, using fallback models.
    
    Args:
        trending_topic: The primary topic for the post.
        required_style: The title style to enforce (e.g., 'Style 2 (Emotional/Shock)'). (Fix #4)
    """
    
    current_date = datetime.now().strftime("%B %d, %Y")

    prompt = f"""
***TASK: High-Traffic, Evergreen, 2000+ Word USA Weather Blog Post***

**GOAL:** Generate a detailed, evergreen blog post of at least **2000 words** focused on the trending topic: **"{trending_topic}"**. The post must be written to appeal directly to a **United States audience** seeking utility, safety, and deep context.

**FOCUS:**
- **Topic:** "{trending_topic}" (Make sure the topic is the central theme)
- **Target:** US Audience
- **Date Context:** {current_date} (Use this for initial framing, but the core content must remain relevant for years).

**STRUCTURE & REQUIREMENTS (CRITICAL for SEO and 1000+ Daily Views):**

1.  **Content Length:** MUST exceed 2000 words. Achieve this by providing deep analysis, historical context, and comprehensive safety guides.
2.  **Title & Meta (FORCED VARIETY):** The `title` MUST be highly emotional, curiosity-driven, or a comprehensive guide for maximum CTR. **You MUST strictly follow the required title style for this post:** **{required_style}**
    * **Style 1 (Utility/Guide):** Use phrases like "The Ultimate Guide," "Complete Blueprint," or "Master Checklist."
    * **Style 2 (Emotional/Shock):** Use phrases like "The Shocking Truth About...," "Hidden Dangers of...," or "Why You Must Prepare for..."
    * **Style 3 (Listicle/Actionable):** Use numbered lists like "5 Ways to Prepare for...," "3 Essential Steps to...," or "7 Things to Know About..."
3.  **Source Linking (Strategy #5):** Include **more than 10** distinct, high-authority external hyperlinks (`<a href="...">...</a>`) spread throughout the content. These links must point to **plausible, high-authority sources** in the US (NOAA, FEMA, CDC, specific state/local government sites, academic journals). **Invent these link URLs and link text to be highly relevant to the content you generate.** Example: `<a href="https://www.fema.gov/disaster-safety/tornadoes">FEMA Tornado Safety Checklist</a>`.
4.  **Evergreen Sections (Strategy #6):** The content must be framed as a long-term resource. Include sections like:
    * **Historical Impact:** How has this type of weather event impacted the US in the last 10-20 years?
    * **Preparation Utility:** Highly actionable, state-by-state safety and preparation checklists.
    * **Future Trends:** Expert outlooks on how climate change affects this specific topic.
5.  **Labels (Tags):** MUST include a `labels` array with 5-10 relevant SEO keywords/categories.

**OUTPUT FORMAT:**
- Use standard, clean HTML markup (`<h1>`, `<h2>`, `<p>`, `<a>`, `<ul>`/`<ol>`).
- Your entire response MUST be a single JSON object matching the SCHEMA.
- The `content_html` field must contain ALL content.
"""
    
    # Loop through the preferred models for fallback logic
    for model_name in MODEL_PREFERENCE:
        log.info("Generating post content for topic: %s using model: %s", trending_topic, model_name)
        
        try:
            # 1. Attempt generation with the current model
            r = client.models.generate_content(
                model=model_name,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_schema=SCHEMA,
                    response_mime_type="application/json",
                    temperature=0.9,
                ),
            )
            # If successful, return the result immediately
            log.info("Successfully generated content using %s.", model_name)
            return json.loads(r.text)

        # We catch the base Exception or specific API exceptions (like ResourceExhausted)
        except (Exception, gapi_exceptions.ResourceExhausted) as e:
            # 2. Handle failure (e.g., rate limit, other API error)
            if model_name != MODEL_PREFERENCE[-1]:
                log.warning("Model %s failed: %s. Attempting fallback to next model...", model_name, e)
            else:
                # 3. If the last model failed, raise the error to stop the current post generation
                log.error("All models failed for topic %s: %s", trending_topic, e)
                raise # Re-raise the exception to be caught by the main loop

    # This line should be unreachable but is included for safety
    raise RuntimeError("Critical: Model generation failed after all fallback attempts.")


# ============================================================
# Blogger API Handlers - Strategy #4 & #7
# ============================================================

# ... (rest of the helper functions: get_credentials, get_blog_page_views, etc.)

def get_blog_page_views(service, blog_id: str, state: Dict[str, Any]):
    """
    Retrieves the last 7 days of page view count for the blog.
    (Strategy #7: Performance Scaling)
    """
    log.info("Fetching last 7 days of page views...")
    try:
        # The Blogger API 'get' method for pageViews returns data in the format
        # {'kind': 'blogger#pageViews', 'blogId': '...', 'counts': [{'timeRange': 'SEVEN_DAYS', 'count': '106'}]}
        result = service.pageViews().get(blogId=blog_id, range='7DAYS').execute()
        
        # Safely extract the count, defaulting to 0 if not found
        views = int(result.get('counts', [{'count': '0'}])[0].get('count', '0'))
        
        # FIX #3: Use f-string logging to fix TypeError
        log.info(f"Blog Page View Count (Last 7 Days): {views}. Target: 7000+")
        
        # Update state with the latest view count
        state['daily_views'] = views
        state['last_view_check'] = str(datetime.now(timezone.utc))

        # This logic is for future scaling decisions, currently not used to change post count
        if views < 500:
            log.info("Blog traffic is low. Maintaining current post volume.")
        elif views >= 7000:
            log.info("Blog traffic is high! Consider increasing POSTS_PER_RUN if daily requests allow.")

    except HttpError as e:
        log.error("HTTP Error fetching page views: %s", e)
    except Exception as e:
        log.error("General Error fetching page views: %s", e)


# ... (publish_or_update_post)

def update_archive_page(service, blog_id: str):
    """
    Fetches all posts, generates an HTML archive, and updates the dedicated archive page.
    (New Step for SEO Crawl Depth and internal linking)
    """
    log.info("--- Starting Archive Page Update ---")
    
    # 1. Fetch all existing posts
    posts = []
    page_token = None
    while True:
        try:
            results = service.posts().list(
                blogId=blog_id,
                fetchBodies=False, # We don't need the full body, just title, URL, and published date
                maxResults=500,
                pageToken=page_token
            ).execute()
        except HttpError as e:
            log.error("HTTP Error fetching posts for archive: %s", e)
            return

        posts.extend(results.get('items', []))
        page_token = results.get('nextPageToken')
        if not page_token:
            break
            
    log.info("Fetched %d total published posts for the archive.", len(posts))

    if not posts:
        log.warning("No posts found to create an archive page.")
        return

    # 2. Sort posts by date (newest first)
    posts.sort(key=lambda p: p.get('published'), reverse=True)

    # 3. Generate HTML Content
    archive_html = "<h1>Complete Blog Index & Archive</h1>\n"
    archive_html += "<p>Below is a complete list of all our weather updates, guides, and safety tips, sorted by publication date.</p>\n"
    archive_html += "<ul>\n"
    
    for post in posts:
        title = post.get('title', 'Untitled Post')
        url = post.get('url', '#')
        published = post.get('published', '2000-01-01T00:00:00Z')
        date_str = datetime.fromisoformat(published.replace('Z', '+00:00')).strftime("%Y-%m-%d")
        archive_html += f'<li>[{date_str}] <a href="{url}">{title}</a></li>\n'
        
    archive_html += "</ul>"

    # 4. Define the page body
    body = {
        'title': 'Blog Index/Archive',
        'content': archive_html,
        'published': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    }

    # 5. Search for the existing Archive Page
    # The Blogger API doesn't have a reliable 'get by title' function, so we list and filter pages.
    archive_page_id = None
    try:
        pages_results = service.pages().list(blogId=blog_id).execute()
        for page in pages_results.get('items', []):
            if page.get('title') == 'Blog Index/Archive':
                archive_page_id = page['id']
                break
    except HttpError as e:
        log.error("HTTP Error listing pages: %s", e)
        # Continue to insertion if listing fails, as it might succeed
        pass

    # 6. Update or Insert the page
    try:
        if archive_page_id:
            log.info("Found existing Archive Page (ID: %s). Updating content...", archive_page_id)
            request = service.pages().patch(
                blogId=blog_id,
                pageId=archive_page_id,
                body=body,
                # FIX #1: Removed unsupported 'fetchBody' argument from pages().patch
            )
            request.execute()
            log.info("Successfully UPDATED Archive Page.")
        else:
            log.info("No existing Archive Page found. Inserting new page...")
            request = service.pages().insert(
                blogId=blog_id,
                body=body
            )
            result = request.execute()
            log.info("Successfully INSERTED new Archive Page (ID: %s).", result['id'])

    except HttpError as e:
        log.error("An unexpected error occurred during Archive Page update: %s", e)
    except Exception as e:
        log.error("An unexpected error occurred during Archive Page update: %s", e)
        
    log.info("--- Archive Page Update Complete ---")


# ============================================================
# Main Execution
# ============================================================

def main():
    log.info("Starting run. Target posts this run: %d (Strategy #2).", POSTS_PER_RUN)
    
    # 1. Initialize API Service and check views (if PUBLISH is true)
    service = None
    state = get_state()
    
    if PUBLISH:
        try:
            # Service initialization also handles credential refresh
            service = get_blogger_service()
            get_blog_page_views(service, BLOG_ID, state)
        except Exception as e:
            log.error("Failed to initialize Blogger service or fetch views: %s. Cannot publish.", e)
            if PUBLISH:
                 # If we can't publish, we exit the entire script to avoid errors.
                 return 
    
    # 2. Get trending topics (or defaults)
    trending_topics = get_trending_topics()
    topics_to_post = trending_topics[:POSTS_PER_RUN]

    for i, topic in enumerate(topics_to_post):
        # FIX #4: Cycle through title styles to enforce variety
        title_style = TITLE_STYLES[i % len(TITLE_STYLES)] 
        log.info("--- Post %d/%d: Processing topic: %s (Style: %s) ---", i + 1, POSTS_PER_RUN, topic, title_style)

        try:
            # 3. Generate Content (Evergreen, 10+ links, US Audience)
            # Pass the required style to the generation function
            post = generate_post(topic, title_style)
            
            # 4. Save a local backup
            # FIX #2: Explicitly remove colons and other invalid characters from filename
            post_title_safe = (
                post['title'].lower()
                .replace(' ', '-')
                .replace('/', '-')
                .replace('\\', '-')
                .replace(':', '') # <-- THIS IS THE FIX for artifact upload error
                .strip()
            )
            # Truncate after cleaning
            post_title_safe = post_title_safe[:50]

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            fname = OUTPUT_DIR / f"{timestamp}-{post_title_safe}.html"
            OUTPUT_DIR.mkdir(exist_ok=True)
            Path(fname).write_text(post['content_html'], encoding="utf-8")
            log.info("Saved local backup to %s", fname)

            # 5. Publish or Update (Strategy #4)
            if PUBLISH:
                publish_or_update_post(post, BLOG_ID)
            else:
                log.info("PUBLISH is set to false. Skipping Blogger API interaction.")

        except Exception as e:
            log.error("CRITICAL ERROR during post generation/publishing for topic %s: %s. Continuing to next post.", topic, e)
            # The error for model failure is handled inside generate_post, so we continue the main loop here.
            continue
            
    log.info("Completed run of %d posts.", len(topics_to_post))
    
    # 6. UPDATE ARCHIVE PAGE (New Step for SEO Crawl Depth)
    if PUBLISH and service:
        # Re-using the service object from the initial view check
        update_archive_page(service, BLOG_ID)
        
    # Save final state
    save_state(state)
    log.info("Final state saved successfully.")

if __name__ == "__main__":
    main()