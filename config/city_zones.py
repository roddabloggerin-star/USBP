# config/city_zones.py

"""
City → lat/lon mapping grouped into four custom zones.

grid_id/grid_x/grid_y populated by scripts/fill_nws_grid.py
"""

NWS_ZONES = {
    "Eastern Zone": {
        "id": "eastern",
        "cities": [
            {"city": "New York, NY", "lat_lon": "40.7128,-74.0060", "grid_id": "OKX", "grid_x": 33, "grid_y": 35},
            {"city": "Boston, MA", "lat_lon": "42.3601,-71.0589", "grid_id": "BOX", "grid_x": 71, "grid_y": 90},
            {"city": "Baltimore, MD", "lat_lon": "39.2904,-76.6122", "grid_id": "LWX", "grid_x": 109, "grid_y": 91},
            {"city": "Newark, NJ", "lat_lon": "40.7357,-74.1724", "grid_id": "OKX", "grid_x": 27, "grid_y": 35},
            {"city": "Jersey City, NJ", "lat_lon": "40.7178,-74.0431", "grid_id": "OKX", "grid_x": 32, "grid_y": 35},
        ],
    },

    "Southern Zone": {
        "id": "southern",
        "cities": [
            {"city": "Houston, TX", "lat_lon": "29.7604,-95.3698", "grid_id": "HGX", "grid_x": 63, "grid_y": 95},
            {"city": "Dallas, TX", "lat_lon": "32.7767,-96.7970", "grid_id": "FWD", "grid_x": 89, "grid_y": 104},
            {"city": "Jacksonville, FL", "lat_lon": "30.3322,-81.6557", "grid_id": "JAX", "grid_x": 66, "grid_y": 65},
            {"city": "Atlanta, GA", "lat_lon": "33.7490,-84.3880", "grid_id": "FFC", "grid_x": 51, "grid_y": 87},
            {"city": "Miami, FL", "lat_lon": "25.7617,-80.1918", "grid_id": "MFL", "grid_x": 110, "grid_y": 50},
        ],
    },

    "Central Zone": {
        "id": "central",
        "cities": [
            {"city": "Chicago, IL", "lat_lon": "41.8781,-87.6298", "grid_id": "LOT", "grid_x": 76, "grid_y": 73},
            {"city": "Indianapolis, IN", "lat_lon": "39.7684,-86.1581", "grid_id": "IND", "grid_x": 58, "grid_y": 69},
            {"city": "Denver, CO", "lat_lon": "39.7392,-104.9903", "grid_id": "BOU", "grid_x": 63, "grid_y": 62},
            {"city": "Detroit, MI", "lat_lon": "42.3314,-83.0458", "grid_id": "DTX", "grid_x": 66, "grid_y": 34},
            {"city": "Milwaukee, WI", "lat_lon": "43.0389,-87.9065", "grid_id": "MKX", "grid_x": 88, "grid_y": 65},
        ],
    },

    "Western Zone": {
        "id": "western",
        "cities": [
            {"city": "Los Angeles, CA", "lat_lon": "34.0522,-118.2437", "grid_id": "LOX", "grid_x": 155, "grid_y": 45},
            {"city": "Phoenix, AZ", "lat_lon": "33.4484,-112.0740", "grid_id": "PSR", "grid_x": 159, "grid_y": 58},
            {"city": "San Diego, CA", "lat_lon": "32.7157,-117.1611", "grid_id": "SGX", "grid_x": 57, "grid_y": 14},
            {"city": "San Jose, CA", "lat_lon": "37.3382,-121.8863", "grid_id": "MTR", "grid_x": 99, "grid_y": 82},
            {"city": "San Francisco, CA", "lat_lon": "37.7749,-122.4194", "grid_id": "MTR", "grid_x": 85, "grid_y": 105},
        ],
    },
}

ZONE_ROTATION = ['Eastern Zone', 'Southern Zone', 'Central Zone', 'Western Zone']
