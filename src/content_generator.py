# src/content_generator.py
from google import genai
from google.genai import types
from typing import Dict, Any, List
import json

# Define the Gemini model we are using
MODEL_NAME = "gemini-2.5-flash"

# Initialize the Gemini client here.
client = genai.Client()

# --- NEW: Define the JSON Schema for the expected output ---
BLOG_POST_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "title": types.Schema(
            type=types.Type.STRING,
            description="A strong, SEO-optimized blog post title (max 70 characters)."
        ),
        "meta_description": types.Schema(
            type=types.Type.STRING,
            description="A concise summary of the content for search engines (max 160 characters)."
        ),
        "content_html": types.Schema(
            type=types.Type.STRING,
            description="The full blog post content in HTML format, guaranteed to be over 1000 words. Must contain H1, H2, P, and the embedded image tag/disclaimer."
        ),
    },
    required=["title", "meta_description", "content_html"]
)
# --- END NEW SCHEMA ---

# Define system instruction for the AI model to ensure quality and compliance
SYSTEM_INSTRUCTION = (
    "You are a professional weather journalist specializing in SEO-optimized blog content "
    "for the USA market. Your goal is to write detailed, engaging, and high-value "
    "weather forecast articles based on the provided data. "
    "CRITICAL RULES: "
    "1. The final content MUST be over 1000 words. Expand thoughtfully on topics like climate history, agricultural impact, travel advisories, and preparation tips."
    "2. Format the content using clean HTML tags (<h1>, <h2>, <p>, <ul>, <strong>, <em>, <a>, <img>)."
    "3. DO NOT use any phrases that mention AI generation, 'AI-generated', 'written by AI', 'bot', 'large language model', etc. The post must appear as if written by a human expert."
    "4. Focus on compounding value by providing rich, educational context around the weather."
    "5. Use US English and tailor the tone for a US audience."
    # Rule 6 is now enforced by the response_schema.
)

def format_forecast_for_gemini(city_data: Dict[str, Any], city_forecasts: Dict[str, Any]) -> str:
    """
    Formats the aggregated city data and forecast data into a single string
    for inclusion in the Gemini API prompt.
    """
    output = []
    
    # 1. Zone Information
    output.append(f"--- WEATHER ZONE: {city_data['id'].upper()} ---")
    output.append(f"Primary City: {city_data['cities'][0]['city']}")
    
    # 2. Aggregated Forecasts
    output.append("\n--- AGGREGATED HOURLY FORECAST DATA (6-day window) ---\n")
    for city, forecast in city_forecasts.items():
        if not forecast:
            output.append(f"WARNING: Forecast data unavailable for {city}.")
            continue
            
        # The forecast is already structured as a dictionary of periods
        output.append(f"City: {city}")
        output.append("Forecast Periods:")
        
        # Iterate over the first 5 days/periods to keep the prompt size manageable
        for i, period in enumerate(forecast.get('periods', [])[:120]): # Cap to 5 days * 24 periods = 120
            
            # Simple, key details for the AI to interpret
            start_time = period.get('startTime')
            temperature = period.get('temperature')
            wind_speed = period.get('windSpeed')
            relative_humidity = period.get('relativeHumidity', {}).get('value')
            short_forecast = period.get('shortForecast')
            
            output.append(
                f"  - {start_time}: Temp={temperature}°F, Wind={wind_speed}, Humidity={relative_humidity}%, Forecast='{short_forecast}'"
            )
            
    return "\n".join(output)


def generate_blog_content(
    zone_name: str,
    city_data: Dict[str, Any],
    city_forecasts: Dict[str, Any],
    image_tag: str,
    disclaimer_html: str,
) -> Dict[str, str] | None:
    """
    Calls the Gemini API to generate the blog post content, guaranteeing JSON output via schema.
    """
    
    formatted_data = format_forecast_for_gemini(city_data, city_forecasts)
    
    full_data_prompt = f"--- RAW DATA START ---\n\n{formatted_data}\n\n--- RAW DATA END ---"
    
    prompt_instruction = (
        f"**TOPIC:** Generate an over 1000-word weather blog post for the **{zone_name}** zone. "
        "The content must be rich, detailed, and based solely on the data provided below. "
        "The final output JSON object MUST contain 'title', 'meta_description', and 'content_html'. "
    )
    
    # Combine prompts
    full_prompt = (
        prompt_instruction + "\n\n" + 
        full_data_prompt + "\n\n" +
        f"**IMPORTANT INSTRUCTIONS for content_html:**\n"
        f"1. Embed the image tag: `{image_tag}` near the beginning of the `content_html` body (e.g., after the first paragraph or H1)."
        f"2. Append the disclaimer HTML: `{disclaimer_html}` to the very end of the `content_html` body."
        f"3. Ensure the final `content_html` results in a total size that is safe for Blogger (well under 5MB)."
    )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[full_prompt],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                # CRITICAL FIX: Use response_schema to guarantee valid JSON output
                response_mime_type="application/json",
                response_schema=BLOG_POST_SCHEMA, 
                temperature=0.7 
            )
        )
        
        # The response.text is now guaranteed to be valid JSON
        return json.loads(response.text)

    except json.JSONDecodeError as e:
        print(f"FATAL: The model returned invalid JSON despite schema enforcement.")
        print(f"Error details: {e}")
        return None
    except Exception as e:
        print(f"An error occurred during content generation: {e}")
        return None