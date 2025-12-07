# --- File: src/main.py (DEBUGGED) ---
import os
import json
import random
# ... (Other imports)
from config.city_zones import NWS_ZONES
from src.blogger_api_util import create_post
from src.post_storage import save_and_index_post
from src.blog_content_generator import generate_blog_post
from src.nws_data_fetcher import fetch_nws_data
from src.zone_rotation import get_next_zone

# ... (API client initialization remains the same)

def main():
    # ... (Zone Rotation, Data Fetching, and Content Generation logic remains the same)
    
    # --- CRITICAL POINT 1: Ensure AI Content is used ---
    # The result of generate_blog_post is a JSON object string.
    # The code correctly parses it:
    # ai_post_data = json.loads(content_json_str)
    
    # 1. Get the final, generated content variables
    generated_title = ai_post_data.get('title')
    generated_html_content = ai_post_data.get('content_html')
    
    if not generated_title or not generated_html_content:
        print("CRITICAL ERROR: AI generation failed to return a title or content.")
        return

    # --- CRITICAL POINT 2: Control Live Publish Status ---
    # This logic correctly checks the environment variable.
    is_publish_live = os.environ.get('PUBLISH', 'false').lower() == 'true'
    
    # Determine the status for printing and for the API call
    publish_status = "LIVE" if is_publish_live else "DRAFT"
    
    print(f"\n--- Preparing to create post for {zone_name} as a {publish_status} post ---")

    # --- CRITICAL POINT 3: Call the Posting Function with the correct flag ---
    post = create_post(
        title=generated_title,
        content_html=generated_html_content,
        is_draft=not is_publish_live  # This correctly inverts the boolean: 
                                       # if is_publish_live=True, then is_draft=False
    )

    if post:
        print(f"✅ Successfully created post ({publish_status} ID): {post.get('id')}")
        print(f"🔗 View URL: {post.get('url')}")
        
        # ... (save_and_index_post logic remains the same)
    else:
        print("❌ Post creation failed. Check API call logs.")


if __name__ == '__main__':
    # --- CRITICAL FIX: Only run the main logic, do not add any test calls here ---
    main()
    
    # REMOVED any line that looked like: 
    # post = create_post("Test from script", "<p>This is a test post.</p>", is_draft=True)