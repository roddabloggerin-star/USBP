# scripts/fill_nws_grid.py (CLEANED REWRITING LOGIC)

# ... (imports and get_grid_data function remain the same)

def rewrite_config(NWS_ZONES: dict, ZONE_ROTATION: list) -> None:
    """Rewrites config/city_zones.py with the updated grid data."""
    print(f"Rewriting {CONFIG_PATH} with {len(NWS_ZONES)} zones and updated grid data...")
    
    new_content = '# config/city_zones.py\n\n'
    new_content += '"""\n'
    new_content += 'City → lat/lon mapping grouped into four custom zones.\n\n'
    new_content += 'grid_id/grid_x/grid_y populated by scripts/fill_nws_grid.py\n'
    new_content += '"""\n\n'
    new_content += 'NWS_ZONES = {\n'
    
    for zone_name, zone_data in NWS_ZONES.items():
        new_content += f'    "{zone_name}": {{\n'
        new_content += f'        "id": "{zone_data["id"]}",\n'
        new_content += f'        "cities": [\n'
        for city in zone_data['cities']:
            # Clean, predictable formatting for the dictionary elements
            city_str = "{" + ", ".join([
                f'"{k}": "{v}"' if isinstance(v, str) else f'"{k}": {v}' 
                for k, v in city.items()
            ]) + "}"
            new_content += f'            {city_str},\n'
        new_content += f'        ],\n'
        new_content += f'    }},\n\n'
    
    new_content += '}\n\n'
    new_content += f'ZONE_ROTATION = {repr(ZONE_ROTATION)}\n' # repr() is fine for a simple list

    # Write the new content to the file, explicitly using UTF-8 encoding
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Config file successfully updated.")
    except IOError as e:
        print(f"Error writing config file: {e}")

# ... (main execution block calls the rewritten function)