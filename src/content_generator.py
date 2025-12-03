# src/content_generator.py (CLEANED PROMPT INSTRUCTION)

def generate_blog_content(
    # ... (function signature remains the same)
    ):
    
    # ... (image_base64 and image_tag creation remains the same)
    
    # CRITICAL CHANGE: Separate data to be used from output instructions
    # This keeps the final instruction set clean and unambiguous for the model.
    data_for_model = (
        f"ZONE: {zone_name} ({zone_id})\n"
        f"CITY DATA: {city_data}\n"
        f"WEATHER FORECASTS: {city_forecasts}\n"
        f"IMAGE HTML TAG TO EMBED: {image_tag}\n"
        f"LEGAL DISCLAIMER HTML TO APPEND: {disclaimer_html}"
    )

    prompt_instruction = (
        "Your task is to generate a comprehensive weather blog post. "
        "The output MUST be a valid JSON object with the keys 'title', 'meta_description', and 'content_html'. "
        "Your content must follow all CRITICAL RULES and use the provided data. "
        "The image tag MUST be embedded inside the 'content_html' body, and the disclaimer MUST be appended to the end."
    )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            # Pass the data block and the instruction block as contents
            contents=[data_for_model, prompt_instruction],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.7 
            )
        )
        # ... (rest of the function is correct)