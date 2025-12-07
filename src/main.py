import os
import logging
from src.config import (
    GEMINI_API_KEY,
    BLOGGER_API_KEY,
    BLOG_ID,
    BLOG_BASE_URL,
    CLIENT_SECRETS_FILE,
    PUBLISH,
    NWS_USER_AGENT
)
from src.weather import WeatherService
from src.blogger import BloggerService
from src.content_generator import ContentGenerator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    try:
        # Initialize services
        weather_service = WeatherService(NWS_USER_AGENT)
        blogger_service = BloggerService(
            client_secrets_file=CLIENT_SECRETS_FILE,
            api_key=BLOGGER_API_KEY,
            blog_id=BLOG_ID,
            blog_base_url=BLOG_BASE_URL
        )
        content_generator = ContentGenerator(GEMINI_API_KEY)
        
        # Get weather data
        weather_data = weather_service.get_weather()
        
        # Generate content
        content = content_generator.generate_content(weather_data)
        
        # Save content to file
        os.makedirs("output_posts", exist_ok=True)
        with open("output_posts/weather_post.html", "w") as f:
            f.write(content)
        
        # Publish if enabled
        if PUBLISH:
            post_id = blogger_service.create_post(
                title=content["title"],
                content=content["content"],
                labels=content["labels"]
            )
            logger.info(f"Published post with ID: {post_id}")
        else:
            logger.info("Content generated but not published (PUBLISH=false)")
            
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
        raise

if __name__ == "__main__":
    main()