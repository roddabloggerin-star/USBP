# src/content_generator.py
from google import genai
from google.genai import types
from typing import Dict, Any, List
import json

# Define the Gemini model we are using
MODEL_NAME = "gemini-2.5-flash"

# --- CRITICAL FIX: Add the Timeout Constant to prevent hanging ---
API_TIMEOUT_SECONDS = 120 # Set a 2-minute (120 seconds) timeout for content generation
# --- END CRITICAL FIX ---

# Initialize the Gemini client here.
client = genai.Client()

# --- Define the JSON Schema for the expected output ---
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
    "1. The final content MUST be over 700 words. Expand thoughtfully on topics like climate history, agricultural impact, travel advisories, and preparation tips."
    "2. Format the content using clean HTML tags (<h1>, <h2>, <p>, <ul>, <strong>, <em>, <a>, <img>)."
    "3. DO NOT use any phrases that mention AI generation, 'AI-generated', 'written by AI', 'bot', 'large language model', etc. The post must appear as if written by a human expert."
    "4. Focus on compounding value by providing rich, educational context around the weather."
    "5. Use US English and tailor the tone for a US audience."
    "6. **CRITICAL JSON RULE:** Ensure all string fields, especially 'content_html', are perfectly valid JSON by escaping all internal double quotes (use \\\" for quotes within the HTML string) and avoiding raw newlines."
)

def format_forecast_for_gemini(city_data: Dict[str, Any], city_forecasts: Dict[str, Any]) -> str:
    """
    Formats the aggregated city data, including current conditions and alerts,
    into a single string for inclusion in the Gemini API prompt.
    
    NOTE: This function filters the hourly forecast data to the NEXT 24 PERIODS.
    """
    output = []
    
    # 1. Zone Information
    output.append(f"--- WEATHER ZONE: {city_data['id'].upper()} ---")
    output.append(f"Primary City: {city_data['cities'][0]['city']}")
    
    # 2. Aggregated Weather Data (Current, Alerts, 24-Hour Forecast)
    output.append("\n--- AGGREGATED CITY WEATHER DATA ---\n")
    for city, data in city_forecasts.items():
        output.append(f"\n--- CITY: {city} ---\n")
        
        # --- ALERTS (Point 2 of request) ---
        alerts = data.get('alerts', [])
        if alerts:
            output.append(f"*** ACTIVE WEATHER ALERTS ({len(alerts)}) - CRITICAL: ***")
            for alert in alerts:
                props = alert.get('properties', {})
                headline = props.get('headline', 'No Headline')
                severity = props.get('severity', 'Unknown')
                event = props.get('event', 'Unknown Event')
                # Include the full text description as well
                description = props.get('description', '').replace('\n', ' ').strip()
                output.append(f"  - ALERT: {event} | Severity: {severity} | Headline: {headline} | Description: {description}")
        else:
            output.append("No active weather alerts for this city.")
            
        # --- CURRENT CONDITIONS (Point 1 of request) ---
        current = data.get('current_conditions', {})
        if current:
            temp_f = current.get('temperature', {}).get('value') # NWS returns Celsius for temperature, we will instruct AI to convert
            text_desc = current.get('textDescription')
            wind_speed = current.get('windSpeed', {}).get('value')
            
            # Convert NWS Celsius to Fahrenheit for easier blog integration (optional but helpful)
            if temp_f is not None:
                 # Standard NWS observation temperature is in Celsius. AI will use this in prompt
                output.append("\nCURRENT CONDITIONS (NWS C/metric):")
                output.append(f"  - Temperature: {temp_f}°C") 
            
            output.append(f"  - Description: {text_desc}")
            output.append(f"  - Wind Speed: {wind_speed} knots") 
        else:
             output.append("Current condition data unavailable.")
        
        # --- 24-HOUR HOURLY FORECAST (Point 3 of request) ---
        forecast = data.get('forecast_hourly', {})
        if forecast:
            output.append("\nNEXT 24 HOURS HOURLY FORECAST:")
            # CRITICAL: Filter periods to the first 24 only
            periods = forecast.get('periods', [])[:24] 
            
            for period in periods:
                start_time = period.get('startTime')
                temperature = period.get('temperature') # This is usually Fahrenheit for hourly forecast
                wind_speed = period.get('windSpeed')
                short_forecast = period.get('shortForecast')
                
                output.append(
                    f"  - {start_time}: Temp={temperature}°F, Wind={wind_speed}, Forecast='{short_forecast}'"
                )
        else:
            output.append("Hourly forecast data unavailable.")
            
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
            # CRITICAL FIX: Timeout parameter moved here, outside of config
            # timeout=API_TIMEOUT_SECONDS, 
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
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
        # This will catch the Timeout error if the request takes longer than 120s
        print(f"An error occurred during content generation: {e}")
        return None