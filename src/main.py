#!/usr/bin/env python3
"""
USA Weather Blogger – High-Traffic AI Strategy Edition
Python 3.12 / GitHub Actions Safe

FINAL MODIFICATIONS for 1000+ Daily View Goal:
1. Removed NWS real-time weather data and hardcoded city data (per request).
2. Integrated 'pytrends' (Google Trends API) for trending topic selection.
3. ADJUSTED daily post target to 4 posts per run (20 Gemini requests total) to comply with free-tier limit.
4. Implemented Blogger API logic to CHECK, UPDATE, or INSERT posts (Strategy #4).
5. Enhanced Gemini prompt for 2000+ word evergreen content and 10+ source links (Strategy #5 & #6).
6. Added blog-wide view tracking for performance scaling insight (Strategy #7).
7. Target Audience is set to United States (Strategy #8).
8. Added model fallback logic (flash -> flash-lite) for robust operation.
9. **NEW:** Modified prompt to enforce title variety (Guide, Emotional, Listicle).
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
def generate_post(trending_topic: str) -> Dict[str, Any]:
    """Generates an evergreen, SEO-heavy blog post based on a trending topic, using fallback models."""
    
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
2.  **Title & Meta (NEW VARIETY):** The `title` MUST be highly emotional, curiosity-driven, or a comprehensive guide for maximum CTR. **VARY the title format** using one of the following high-impact styles for each post:
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
                 raise
                 
    # This line should be unreachable but is included for safety
    raise RuntimeError("Critical: Model generation failed after all fallback attempts.")


# ============================================================
# Blogger API Handlers - Strategy #4 & #7
# ============================================================
BLOGGER_SCOPE = ["https://www.googleapis.com/auth/blogger"]
# NEW CONSTANT: Title of the static archive page that will be constantly updated
ARCHIVE_PAGE_TITLE = "Blog Index/Archive"

def get_authenticated_service():
    """ Handles OAuth 2.0 flow and returns an authenticated Blogger service."""
    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, BLOGGER_SCOPE)
        except Exception:
            pass 

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            log.warning("Starting interactive OAuth 2.0 flow. Run this script locally ONCE to generate token.json.")
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, BLOGGER_SCOPE
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('blogger', 'v3', credentials=creds)


def get_existing_post_id(service, blog_id: str, title: str) -> Optional[str]:
    """ Searches for an existing post by title (approximation)."""
    try:
        # Search API doesn't support exact title search, so we list and filter.
        # Max results 50 should cover posts recent enough for updates.
        results = service.posts().list(blogId=blog_id, maxResults=50).execute()
        
        for post in results.get('items', []):
            if post['title'].lower().strip() == title.lower().strip():
                log.info("Found existing post with matching title: %s", post['id'])
                return post['id']
                
        return None
        
    except HttpError as e:
        log.error("Failed to list posts from Blogger API: %s", e)
        return None


def get_blog_page_views(service, blog_id: str, state: Dict[str, Any]):
    """ Retrieves total page views for the blog (Strategy #7 Insight)."""
    try:
        # Blogger API only provides blog-level views. Use '7DAYS' for tracking goal progress.
        result = service.pageViews().get(blogId=blog_id, range='7DAYS').execute()
        views = result.get('counts', [0])[0]
        
        # Update the state file
        state['daily_views'] = views
        state['last_view_check'] = str(datetime.now())
        save_state(state)
        
        log.info("Blog Page View Count (Last 7 Days): %d. Target: 7000+", views)

    except HttpError as e:
        log.error("Failed to get Page Views from Blogger API: %s", e)


def publish_or_update_post(post: Dict[str, Any], blog_id: str):
    """ STRATEGY #4: Checks for existing post, updates it if found, or inserts a new one.
        SEO Enhancement: Injects a canonical link after publishing.
    """
    log.info("Attempting to publish/update post...")
    
    try:
        service = get_authenticated_service()
        existing_post_id = get_existing_post_id(service, blog_id, post['title'])
        
        # Construct the post body
        body = {
            'kind': 'blogger#post',
            'blog': {'id': blog_id},
            'title': post['title'],
            'content': post['content_html'],
            'labels': post.get('labels', []) # Includes SEO Labels/Tags
        }
        
        if existing_post_id:
            # UPDATE existing post 
            log.info("Updating existing post ID %s to refresh content...", existing_post_id)
            
            # Update the published time to now to push it to the top of the blog feed
            body['published'] = datetime.now(timezone.utc).isoformat()
            
            request = service.posts().patch(
                blogId=blog_id, 
                postId=existing_post_id, 
                body=body,
                fetchBody=False 
            )
            result = request.execute()
            log.info("Successfully UPDATED post: %s", result.get('url'))
        
        else:
            # INSERT new post
            log.info("No existing post found. Inserting new post...")
            request = service.posts().insert(blogId=blog_id, body=body, isDraft=False)
            result = request.execute()
            log.info("Successfully INSERTED new post: %s", result.get('url'))
            
        
        # --- NEW SEO IMPLEMENTATION: SET CANONICAL LINK ---
        final_post_url = result.get('url')
        if final_post_url:
            # 1. Create the canonical tag
            canonical_tag = f'<link rel="canonical" href="{final_post_url}">'
            log.info("Injecting canonical link: %s", canonical_tag)
            
            # 2. Add the canonical tag to the start of the HTML content
            updated_content_html = canonical_tag + post['content_html']
            
            # 3. Prepare the body for the second PATCH request (Canonical injection)
            canonical_body = {
                # Only update the content field with the new content + canonical tag
                'content': updated_content_html,
                # Set published time again to ensure it refreshes 
                'published': datetime.now(timezone.utc).isoformat() 
            }
            
            # 4. Patch the post again with the canonical link included in the content
            canonical_request = service.posts().patch(
                blogId=blog_id,
                postId=result.get('id'),
                body=canonical_body,
                fetchBody=False
            )
            canonical_request.execute()
            log.info("Canonical link successfully patched into post content.")
        # --- END NEW SEO IMPLEMENTATION ---

        return final_post_url

    except HttpError as e:
        log.error("Failed to interact with Blogger API (HTTP Error: %s).", e.resp.status)
    except Exception as e:
        log.error("An unexpected error occurred during publishing: %s", e)


# ============================================================
# Archive Page Management (SEO Crawl Depth)
# ============================================================
def update_archive_page(service, blog_id: str):
    """
    Fetches all posts, generates a sorted list of links, and updates/creates 
    a static Archive Page ("Blog Index/Archive"). Ensures every post is linked.
    """
    log.info("--- Starting Archive Page Update ---")
    
    try:
        # 1. Fetch ALL published posts (Blogger API pages through results using 'nextPageToken')
        all_posts = []
        page_token = None
        
        while True:
            # maxResults=50 is the maximum allowed per request
            request = service.posts().list(
                blogId=blog_id, 
                maxResults=50, 
                orderBy='PUBLISHED', # Important for sorting
                status='LIVE',       # Only published posts
                pageToken=page_token
            )
            result = request.execute()
            all_posts.extend(result.get('items', []))
            
            page_token = result.get('nextPageToken')
            if not page_token:
                break
        
        log.info("Fetched %d total published posts for the archive.", len(all_posts))

        # 2. Generate Archive HTML (Sorted by newest first)
        # The Blogger API 'orderBy' should handle the sort, but we ensure it here.
        all_posts.sort(key=lambda p: p['published'], reverse=True) 

        archive_html = f'<h1>{ARCHIVE_PAGE_TITLE}</h1>'
        archive_html += '<p>This index provides direct links to every comprehensive weather resource on our blog.</p>'
        archive_html += '<ul>\n'
        
        for post in all_posts:
            # Format the date for display
            pub_date = datetime.strptime(post['published'][:19], '%Y-%m-%dT%H:%M:%S').strftime('%Y-%m-%d')
            archive_html += f'    <li><a href="{post["url"]}">{post["title"]}</a> - ({pub_date})</li>\n'
            
        archive_html += '</ul>'

        # 3. Find/Create the Archive Page
        archive_page_id = None
        page_token = None
        
        # Search for the existing Archive Page by its title
        while True:
            request = service.pages().list(blogId=blog_id, pageToken=page_token)
            result = request.execute()
            
            for page in result.get('items', []):
                # Check for the exact title provided by the user
                if page['title'].strip() == ARCHIVE_PAGE_TITLE:
                    archive_page_id = page['id']
                    break
            
            page_token = result.get('nextPageToken')
            if not page_token or archive_page_id:
                break

        body = {
            'kind': 'blogger#page',
            'blog': {'id': blog_id},
            'title': ARCHIVE_PAGE_TITLE,
            'content': archive_html,
        }

        if archive_page_id:
            # 4a. Update existing page
            log.info("Found existing Archive Page (ID: %s). Updating content...", archive_page_id)
            request = service.pages().patch(
                blogId=blog_id,
                pageId=archive_page_id,
                body=body,
                fetchBody=False
            )
            request.execute()
            log.info("Successfully updated Archive Page.")
        else:
            # 4b. Insert new page
            log.info("Archive Page not found. Creating a new one...")
            request = service.pages().insert(blogId=blog_id, body=body, isDraft=False) # Publish immediately
            result = request.execute()
            log.info("Successfully created new Archive Page: %s", result.get('url'))

    except HttpError as e:
        log.error("Failed to manage Archive Page via Blogger API (HTTP Error: %s).", e.resp.status)
    except Exception as e:
        log.error("An unexpected error occurred during Archive Page update: %s", e)
        
    log.info("--- Archive Page Update Complete ---")


# ============================================================
# Main Execution - Strategy #2, #7, #8
# ============================================================
def main():
    state = get_state()
    log.info("Starting run. Target posts this run: %d (Strategy #2). Total Daily Requests: 20", POSTS_PER_RUN)
    
    # 1. Performance Scaling Insight (Strategy #7)
    service = None
    if PUBLISH:
        service = get_authenticated_service()
        get_blog_page_views(service, BLOG_ID, state)

    # 2. Get Trending Topics (Strategy #3)
    trending_topics = get_trending_topics()
    
    # Use the highest-priority topics for the 4 posts
    topics_to_post = trending_topics[:POSTS_PER_RUN]

    for i, topic in enumerate(topics_to_post):
        # We will use one Gemini request per post, total 4 requests
        log.info("--- Post %d/%d: Processing topic: %s ---", i + 1, POSTS_PER_RUN, topic)

        try:
            # 3. Generate Content (Evergreen, 10+ links, US Audience)
            # This call now includes model fallback logic and the new title variety instruction
            post = generate_post(topic)
            
            # 4. Save a local backup
            post_title_safe = post['title'].lower().replace(' ', '-').replace('/', '-').replace('/', '-').strip()[:50]
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            fname = OUTPUT_DIR / f"{timestamp}-{post_title_safe}.html"
            OUTPUT_DIR.mkdir(exist_ok=True)
            Path(fname).write_text(post['content_html'], encoding="utf-8")
            log.info("Saved local backup to %s", fname)

            # 5. Publish or Update (Strategy #4)
            if PUBLISH:
                # service is guaranteed to be set if PUBLISH is true
                publish_or_update_post(post, BLOG_ID)
            else:
                log.info("PUBLISH is set to false. Skipping Blogger API interaction.")

        except Exception as e:
            log.error("CRITICAL ERROR during post generation/publishing for topic %s: %s. Continuing to next post.", topic, e)
            # The error for model failure is handled inside generate_post, so we continue the main loop here.
            continue
            
    log.info("Completed run of %d posts.", POSTS_PER_RUN)
    
    # 6. UPDATE ARCHIVE PAGE (New Step for SEO Crawl Depth)
    if PUBLISH and service:
        # Re-using the service object from the initial view check
        update_archive_page(service, BLOG_ID)
        
    # Save final state
    save_state(state)

if __name__ == "__main__":
    main()