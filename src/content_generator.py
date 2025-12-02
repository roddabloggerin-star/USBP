# src/content_generator.py
from google import genai
from google.genai import types
from typing import Dict, Any, List
import json

# Define the Gemini model we are using
MODEL_NAME = "gemini-2.5-flash"

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
    Creates a structured, detailed prompt string from the fetched weather data for Gemini.
    """
    prompt = f"## Weather Data for {city_data['city']} (Current Conditions and 24-Hour Forecast)\n"
    
    # Extract only the next 24 hours (24 periods) for conciseness
    forecast_periods = city_forecasts.get('periods', [])[:24]
    
    for period in forecast_periods:
        # Extract relevant details for the AI to elaborate on
        start_time = period['startTime'].split('T')[1].split(':')[:2]
        time_str = f"{start_time[0]}:{start_time[1]}"
        
        prompt += (
            f"- Time: {period['name']} ({time_str}): "
            f"Temp: {period['temperature']}°F, Wind: {period['windSpeed']} {period['windDirection']}, "
            f"Humidity: {period.get('relativeHumidity', {}).get('value', 'N/A')}%, "
            f"Short Forecast: {period['shortForecast']}. Detailed: {period['detailedForecast']}\n"
        )
        
    return prompt


def generate_blog_content(zone_name: str, all_zone_forecast_data: List[Dict[str, Any]], image_base64: str) -> Dict[str, str]:
    """
    Calls the Gemini API to generate the full blog post, title, and meta description.
    """
    try:
        # Client automatically uses the GEMINI_API_KEY environment variable
        client = genai.Client()
    except Exception as e:
        print(f"Error initializing Gemini client: {e}. Check GEMINI_API_KEY.")
        return {"title": "Error", "meta_description": "Error", "content_html": "<p>API Client Error</p>"}


    # Concatenate all city data into one large prompt input
    full_data_prompt = f"Generate an SEO-optimized blog post for the **{zone_name}** region of the USA. The post must cover the current and near-future hourly weather forecasts for the following cities, provided as structured data:\n\n"
    
    for city_forecast_item in all_zone_forecast_data:
        full_data_prompt += format_forecast_for_gemini(city_forecast_item['city_config'], city_forecast_item['forecast_data'])
        full_data_prompt += "\n---\n" # Separator

    # HTML for the disclaimer
    disclaimer_html = (
        '<p style="font-size: 0.8em; color: #666; margin-top: 30px; text-align: center;">'
        '**Disclaimer:** This post is created using the public data provided by the National Weather Service. '
        'Please check the Original source for more information: <a href="https://www.weather.gov/" target="_blank" rel="nofollow noopener">https://www.weather.gov/</a>.'
        '</p>'
    )
    
    # Base64 image tag for the top of the post (below the H1 title)
    image_tag = f'<img src="{image_base64}" alt="Current Weather Map for {zone_name} Zone" style="max-width: 100%; height: auto; display: block; margin: 15px auto; border: 1px solid #ccc;"/>'

    # Primary Instruction Prompt
    prompt_instruction = (
        f"Based on the combined weather data above, write a single, detailed, HTML-formatted blog post of **over 1000 words** for the {zone_name} zone. "
        "Include regional summaries and city-specific details. "
        "Output the three required fields in a JSON structure:\n"
        "1. `title`: An engaging, SEO-rich title (max 60 characters)."
        "2. `meta_description`: A summary for search engines (max 160 characters)."
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
        return {"title": "Error Generating Post", "meta_description": "Content generation failed", "content_html": f"<p>Error: {e}</p>"}