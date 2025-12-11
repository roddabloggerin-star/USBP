# src/content_generator.py

from google import genai
from google.genai import types
from google.genai import errors
from typing import Dict, Any, List
import json
import time

# Define the Gemini model we are using
MODEL_NAME = "gemini-2.5-flash"

# Timeout constant (you can wire this into your HTTP stack if needed)
API_TIMEOUT_SECONDS = 120

# Initialize the Gemini client here.
client = genai.Client()

# --- Constants for token control / compaction ---
MAX_CITIES_PER_ZONE = 15           # Hard cap on how many cities per zone we send to Gemini
MAX_ALERTS_PER_CITY = 2            # Max alerts to include per city
KEY_HOURLY_INDICES = [0, 12]       # Representative hourly points (~now and ~12h later)

# Markers used inside model output instead of full HTML
IMAGE_MARKER = "[[IMAGE_TAG_HERE]]"
DISCLAIMER_MARKER = "[[DISCLAIMER_HERE]]"

# --- JSON Schemas ---

# Final blog post schema
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

# NOTE: The OUTLINE_SCHEMA is removed as we now only make one request.

# Define system instruction for the AI model to ensure quality and compliance
SYSTEM_INSTRUCTION = (
    "You are a professional weather journalist specializing in SEO-optimized blog content "
    "for the USA market. Your goal is to write a detailed, engaging, and high-value "
    "weather forecast article based on the provided data. "
    "CRITICAL RULES: "
    "1. The final content MUST be over 1000 words. Expand thoughtfully on topics like climate history, agricultural impact, travel advisories, and preparation tips."
    "2. Format the content using clean HTML tags (<h1>, <h2>, <p>, <ul>, <strong>, <em>, <a>, <img>)."
    "3. DO NOT use any phrases that mention AI generation, 'AI-generated', 'written by AI', 'bot', 'large language model', etc. The post must appear as if written by a human expert."
    "4. Focus on compounding value by providing rich, educational context around the weather."
    "5. Use US English and tailor the tone for a US audience."
    "6. **CRITICAL JSON RULE:** Ensure all string fields, especially 'content_html', are perfectly valid JSON by escaping all internal double quotes (use \\\" for quotes within the HTML string) and avoiding raw newlines."
    "7. Structure the article with a single <h1> main title and multiple relevant <h2> sections."
)

# ------------------------------
# COMPACT DATA PREPARATION (NO CHANGE)
# ------------------------------


def select_representative_cities(
    city_forecasts: Dict[str, Any],
    max_cities: int = MAX_CITIES_PER_ZONE
) -> List[str]:
    """
    Heuristic selection of representative cities:
      - prioritize cities with more active alerts
      - then by lower temperatures (to surface extremes)
      - fallback: preserves order when things are equal

    This is a defensive limit so upstream data cannot blow up tokens.
    """
    scored: List[tuple] = []

    for city, data in city_forecasts.items():
        alerts = data.get("alerts") or []
        alert_count = len(alerts)

        # current temp as tie-breaker (C if available)
        temp_val = None
        cur = data.get("current_conditions") or {}
        t_obj = cur.get("temperature")
        if isinstance(t_obj, dict):
            try:
                temp_val = float(t_obj.get("value") or 0.0)
            except Exception:
                temp_val = None

        # score: more alerts = higher, lower temp slightly prioritized
        score = (alert_count, - (temp_val if temp_val is not None else 0.0))
        scored.append((score, city))

    # sort descending by score
    scored.sort(reverse=True)
    selected = [c for (_, c) in scored[:max_cities]]

    return selected


def compact_city_line(city: str, data: Dict[str, Any]) -> str:
    """
    Produce a single compact, pipe-delimited summary line for a city.

    Example:
      CITY_NAME|temp_C=12.3|desc=Mostly sunny|wind=8.0|alerts=1|alert_heads=Flood Watch|points=2025-01-01T12:00Z|72F|5kt|Sunny;;2025-01-01T00:00Z|65F|10kt|Showers
    """
    parts: List[str] = [city]

    # Current temperature (C) if available
    current = data.get("current_conditions") or {}
    temp_val = None
    t = current.get("temperature")
    if isinstance(t, dict):
        temp_val = t.get("value")
    parts.append(f"temp_C={temp_val if temp_val is not None else 'N/A'}")

    # Description (flattened)
    desc = current.get("textDescription") or "N/A"
    desc_short = desc.replace("\n", " ").replace("|", " ").strip()
    parts.append(f"desc={desc_short}")

    # Wind speed (metric value if available)
    w = current.get("windSpeed") or {}
    if isinstance(w, dict):
        w_val = w.get("value")
    else:
        w_val = w
    parts.append(f"wind={w_val if w_val is not None else 'N/A'}")

    # Alerts (count + short headlines)
    alerts = data.get("alerts") or []
    parts.append(f"alerts={len(alerts)}")
    if alerts:
        alert_heads: List[str] = []
        for al in alerts[:MAX_ALERTS_PER_CITY]:
            props = al.get("properties") or {}
            headline = (
                props.get("headline")
                or props.get("event")
                or "NoHeadline"
            )
            alert_heads.append(headline.replace("|", " ").replace("\n", " ").strip())
        parts.append("alert_heads=" + ";".join(alert_heads))

    # Hourly forecast: pick a few key points
    forecast = data.get("forecast_hourly") or {}
    periods = forecast.get("periods") or []
    hourly_parts: List[str] = []

    for idx in KEY_HOURLY_INDICES:
        if idx < len(periods):
            p = periods[idx]
            st = p.get("startTime", "N/A")
            tempf = p.get("temperature", "N/A")
            wf = p.get("windSpeed", "N/A")
            sf = (p.get("shortForecast") or "N/A").replace("|", " ").replace("\n", " ")

            hourly_parts.append(f"{st}|{tempf}|{wf}|{sf}")

    if hourly_parts:
        parts.append("points=" + ";;".join(hourly_parts))

    return "|".join(parts)


def format_forecast_for_gemini(
    city_data: Dict[str, Any],
    city_forecasts: Dict[str, Any]
) -> str:
    """
    Compact formatter to drastically reduce token usage while preserving
    essential context.

    It produces:
      - One header line with zone-level aggregates (avg temp, max wind, total alerts).
      - A line announcing how many representative cities are included.
      - One compact summary line per selected city (up to MAX_CITIES_PER_ZONE).
    """
    temps: List[float] = []
    total_alerts = 0
    max_wind_val = None

    # Aggregate basic stats across all cities
    for _, d in city_forecasts.items():
        cur = d.get("current_conditions") or {}
        t = cur.get("temperature")
        if isinstance(t, dict) and t.get("value") is not None:
            try:
                temps.append(float(t.get("value")))
            except Exception:
                pass

        alerts = d.get("alerts") or []
        total_alerts += len(alerts)

        w = cur.get("windSpeed")
        if isinstance(w, dict) and w.get("value") is not None:
            try:
                wv = float(w.get("value"))
                if max_wind_val is None or wv > max_wind_val:
                    max_wind_val = wv
            except Exception:
                pass

    avg_temp = round(sum(temps) / len(temps), 1) if temps else "N/A"
    max_wind = round(max_wind_val, 1) if max_wind_val is not None else "N/A"

    header = (
        f"ZONE={city_data.get('id', 'N/A')}"
        f"|PRIMARY={city_data.get('cities', [{}])[0].get('city', 'N/A')}"
        f"|AVG_TEMP_C={avg_temp}"
        f"|MAX_WIND={max_wind}"
        f"|TOTAL_ALERTS={total_alerts}"
    )

    lines: List[str] = [header]

    # Defensive city selection (never trust upstream data size)
    selected = select_representative_cities(city_forecasts, MAX_CITIES_PER_ZONE)
    if not selected:
        selected = list(city_forecasts.keys())[:MAX_CITIES_PER_ZONE]

    lines.append(f"REPRESENTATIVE_COUNT={len(selected)}")

    for city in selected:
        data = city_forecasts.get(city, {}) or {}
        lines.append(compact_city_line(city, data))

    compact_string = "\n".join(lines)
    return compact_string


# ------------------------------
# CONTENT GENERATION (REFACTORED TO SINGLE CALL)
# ------------------------------


def generate_blog_content(
    zone_name: str,
    city_data: Dict[str, Any],
    city_forecasts: Dict[str, Any],
    image_tag: str,
    disclaimer_html: str,
) -> Dict[str, str] | None:
    """
    Refactored to a single-step generation to produce a 1000+ word blog post
    in a single API call, reducing the run's API request count to one.
    """

    # Basic debug of inputs
    try:
        print(f"DEBUG: number of cities in city_forecasts = {len(city_forecasts)}")
    except Exception:
        pass
    print(f"DEBUG: len(image_tag) = {len(image_tag)} chars")
    print(f"DEBUG: len(disclaimer_html) = {len(disclaimer_html)} chars")

    # 1) Build compact data
    compact_data = format_forecast_for_gemini(city_data, city_forecasts)

    # 2) Build the single, combined prompt
    final_prompt = (
        f"WEATHER ZONE DATA (COMPACT):\n{compact_data}\n\n"
        f"ZONE NAME: {zone_name}\n\n"
        "TASK: Based only on the compact data above, write a full HTML weather blog post for the zone "
        f"'{zone_name}' for a US audience. The content MUST adhere to all rules in the System Instruction.\n\n"
        "CONSTRAINTS:\n"
        "- The post MUST be at least 1000 words.\n"
        "- Use a single <h1> for the main title and multiple <h2> headings to structure the content (e.g., 'Current Conditions', 'Looking Ahead: The Hourly Forecast', 'Weather Advisories', 'Preparedness Tips').\n"
        "- Use <p> for paragraphs and <ul>/<li> where lists make sense.\n"
        "- The tone should be expert, clear, and helpful for a US audience interested in practical weather, travel, and preparedness insights.\n"
        "- Do NOT mention AI, models, or anything about being generated.\n"
        f"- Insert the literal marker {IMAGE_MARKER} near the beginning of the article (after the <h1> or first paragraph). "
        "Do NOT modify this marker text.\n"
        f"- Insert the literal marker {DISCLAIMER_MARKER} at the very end of the article content. "
        "Do NOT modify this marker text.\n"
        "- Provide a short, SEO-focused 'title' (max 70 characters) and 'meta_description' (max 160 characters).\n"
        "- Return ONLY a JSON object with the fields: 'title', 'meta_description', 'content_html'. "
        "The 'content_html' must be a single HTML string (no markdown, no extra JSON)."
    )

    # Debug: prompt size and token count
    print(f"\n--- Starting Single-Call Generation ---\n")
    print(f"DEBUG: len(final_prompt) = {len(final_prompt)} chars")
    try:
        tok = client.models.count_tokens(model=MODEL_NAME, contents=[final_prompt])
        print(f"DEBUG: final_prompt token count estimate: {tok.total_tokens}")
    except Exception:
        pass

    # 3) Final generation with retry on 429
    MAX_RETRIES = 5
    BASE_DELAY = 5

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[final_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=BLOG_POST_SCHEMA,
                    temperature=0.6,
                ),
            )
            result = json.loads(response.text)

            # Inject the real image tag and disclaimer HTML where the markers are
            content = result.get("content_html", "")
            if content:
                content = content.replace(IMAGE_MARKER, image_tag)
                content = content.replace(DISCLAIMER_MARKER, disclaimer_html)
                result["content_html"] = content

            return result

        except errors.ClientError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY * (2 ** attempt)
                print(f"Content generation rate-limited (429). Retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES}).")
                time.sleep(delay)
                continue
            print(f"FATAL: Gemini API Client Error (code={e.code}) on single-call generation.")
            print(f"Details: {e}")
            return None

        except json.JSONDecodeError as e:
            print("FATAL: The model returned invalid JSON in the content generation step.")
            print(f"Details: {e}")
            return None

        except Exception as e:
            print(f"Unexpected error during content generation: {e}")
            return None

    # If the loop somehow finishes without returning, fail explicitly
    return None