# src/content_generator.py (FIXED: Gemini Client Initialization)
from google import genai
from google.genai import types
from typing import Dict, Any, List
import json

# Define the Gemini model we are using
MODEL_NAME = "gemini-2.5-flash"

# CRITICAL FIX: Initialize the Gemini client here.
# It will automatically pick up the GEMINI_API_KEY from the environment.
client = genai.Client()

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
    "6. Structure the output as a valid JSON object containing exactly 'title', 'meta_description', and 'content_html'."
)

def format_forecast_for_gemini(city_data: Dict[str, Any], city_forecasts: Dict[str, Any]) -> str:
    """
    Formats the aggregated city data and forecast data into a single string
    for inclusion in the Gemini API prompt.
    """
    # ... (function content omitted for brevity, no changes needed)
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
    Calls the Gemini API to generate the blog post content.
    """
    
    formatted_data = format_forecast_for_gemini(city_data, city_forecasts)
    
    full_data_prompt = f"--- RAW DATA START ---\n\n{formatted_data}\n\n--- RAW DATA END ---"
    
    prompt_instruction = (
        f"**TOPIC:** Generate an over 1000-word weather blog post for the **{zone_name}** zone. "
        f"The content must be rich, detailed, and based solely on the data provided below. "
        "The post MUST contain: "
        "1. `title`: A strong, SEO-optimized title (max 70 characters)."
        "2. `meta_description`: A concise summary for search engines (max 160 characters)."
        "3. `content_html`: The full, over 1000-word HTML body. Embed the image tag and the required legal disclaimer."
    )
    
    # Combine prompts
    full_prompt = (
        prompt_instruction + "\n\n" + 
        full_data_prompt + "\n\n" +
        f"**IMPORTANT INSTRUCTIONS:**\n"
        f"1. Embed the image tag: `{image_tag}` near the beginning of the `content_html` body (e.g., after the first paragraph or H1)."
        f"2. Append the disclaimer HTML: `{disclaimer_html}` to the very end of the `content_html` body."
        f"3. Ensure the final `content_html` results in a total size that is safe for Blogger (well under 5MB)."
        f"4. The entire output MUST be a valid JSON object."
    )

    try:
        # Client is now globally available/initialized at the module level
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[full_prompt],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.7 # Add a little creativity for rich content
            )
        )
        
        # The response text should be a JSON string
        return json.loads(response.text)

    except Exception as e:
        print(f"An error occurred during content generation: {e}")
        return None