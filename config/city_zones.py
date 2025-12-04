# config/city_zones.py

"""
City → lat/lon mapping grouped into four custom zones.

grid_id/grid_x/grid_y populated by scripts/fill_nws_grid.py
"""

NWS_ZONES = {
    "Eastern Zone": {
        "id": "eastern",
        "cities": [
            {"city": "Boston, MA", "lat_lon": "42.3601,-71.0589", "grid_id": "BOX", "grid_x": 71, "grid_y": 90},
            {"city": "Worcester, MA", "lat_lon": "42.2626,-71.8023", "grid_id": "BOX", "grid_x": 47, "grid_y": 81},
            {"city": "Springfield, MA", "lat_lon": "42.1015,-72.5898", "grid_id": "BOX", "grid_x": 22, "grid_y": 69},
            {"city": "Providence, RI", "lat_lon": "41.8240,-71.4128", "grid_id": "BOX", "grid_x": 64, "grid_y": 64},
            {"city": "Hartford, CT", "lat_lon": "41.7658,-72.6734", "grid_id": "BOX", "grid_x": 22, "grid_y": 54},
            {"city": "New Haven, CT", "lat_lon": "41.3083,-72.9279", "grid_id": "OKX", "grid_x": 66, "grid_y": 68},
            {"city": "Bridgeport, CT", "lat_lon": "41.1792,-73.1894", "grid_id": "OKX", "grid_x": 58, "grid_y": 60},
            {"city": "Portland, ME", "lat_lon": "43.6591,-70.2568", "grid_id": "GYX", "grid_x": 72, "grid_y": 58},
            {"city": "Bangor, ME", "lat_lon": "44.8012,-68.7778", "grid_id": "CAR", "grid_x": 66, "grid_y": 62},
            {"city": "Baltimore, MD", "lat_lon": "39.2904,-76.6122", "grid_id": "LWX", "grid_x": 109, "grid_y": 91},
            {"city": "Wilmington, DE", "lat_lon": "39.7391,-75.5398", "grid_id": "PHI", "grid_x": 38, "grid_y": 64},
            {"city": "Newark, NJ", "lat_lon": "40.7357,-74.1724", "grid_id": "OKX", "grid_x": 27, "grid_y": 35},
            {"city": "Jersey City, NJ", "lat_lon": "40.7178,-74.0431", "grid_id": "OKX", "grid_x": 32, "grid_y": 35},
            {"city": "New York, NY", "lat_lon": "40.7128,-74.0060", "grid_id": "OKX", "grid_x": 33, "grid_y": 35},
            {"city": "Buffalo, NY", "lat_lon": "42.8864,-78.8784", "grid_id": "BUF", "grid_x": 36, "grid_y": 47},
        ],
    },

    "Southern Zone": {
        "id": "southern",
        "cities": [
            {"city": "Birmingham, AL", "lat_lon": "33.5186,-86.8104", "grid_id": "BMX", "grid_x": 59, "grid_y": 84},
            {"city": "Little Rock, AR", "lat_lon": "34.7465,-92.2896", "grid_id": "LZK", "grid_x": 82, "grid_y": 73},
            {"city": "Miami, FL", "lat_lon": "25.7617,-80.1918", "grid_id": "MFL", "grid_x": 110, "grid_y": 50},
            {"city": "Jacksonville, FL", "lat_lon": "30.3322,-81.6557", "grid_id": "JAX", "grid_x": 66, "grid_y": 65},
            {"city": "Tampa, FL", "lat_lon": "27.9506,-82.4572", "grid_id": "TBW", "grid_x": 71, "grid_y": 98},
            {"city": "Orlando, FL", "lat_lon": "28.5383,-81.3792", "grid_id": "MLB", "grid_x": 26, "grid_y": 68},
            {"city": "Atlanta, GA", "lat_lon": "33.7490,-84.3880", "grid_id": "FFC", "grid_x": 51, "grid_y": 87},
            {"city": "New Orleans, LA", "lat_lon": "29.9511,-90.0715", "grid_id": "LIX", "grid_x": 68, "grid_y": 88},
            {"city": "Baton Rouge, LA", "lat_lon": "30.4515,-91.1871", "grid_id": "LIX", "grid_x": 25, "grid_y": 109},
            {"city": "Jackson, MS", "lat_lon": "32.2988,-90.1848", "grid_id": "JAN", "grid_x": 76, "grid_y": 63},
            {"city": "Albuquerque, NM", "lat_lon": "35.0844,-106.6504", "grid_id": "ABQ", "grid_x": 98, "grid_y": 121},
            {"city": "Oklahoma City, OK", "lat_lon": "35.4676,-97.5164", "grid_id": "OUN", "grid_x": 97, "grid_y": 94},
            {"city": "Nashville, TN", "lat_lon": "36.1627,-86.7816", "grid_id": "OHX", "grid_x": 50, "grid_y": 57},
            {"city": "Houston, TX", "lat_lon": "29.7604,-95.3698", "grid_id": "HGX", "grid_x": 63, "grid_y": 95},
            {"city": "Dallas, TX", "lat_lon": "32.7767,-96.7970", "grid_id": "FWD", "grid_x": 89, "grid_y": 104},
        ],
    },

    "Central Zone": {
        "id": "central",
        "cities": [
            {"city": "Denver, CO", "lat_lon": "39.7392,-104.9903", "grid_id": "BOU", "grid_x": 63, "grid_y": 62},
            {"city": "Colorado Springs, CO", "lat_lon": "38.8339,-104.8214", "grid_id": "PUB", "grid_x": 90, "grid_y": 91},
            {"city": "Chicago, IL", "lat_lon": "41.8781,-87.6298", "grid_id": "LOT", "grid_x": 76, "grid_y": 73},
            {"city": "Indianapolis, IN", "lat_lon": "39.7684,-86.1581", "grid_id": "IND", "grid_x": 58, "grid_y": 69},
            {"city": "Des Moines, IA", "lat_lon": "41.5868,-93.6250", "grid_id": "DMX", "grid_x": 73, "grid_y": 49},
            {"city": "Wichita, KS", "lat_lon": "37.6872,-97.3301", "grid_id": "ICT", "grid_x": 62, "grid_y": 34},
            {"city": "Louisville, KY", "lat_lon": "38.2527,-85.7585", "grid_id": "LMK", "grid_x": 50, "grid_y": 78},
            {"city": "Detroit, MI", "lat_lon": "42.3314,-83.0458", "grid_id": "DTX", "grid_x": 66, "grid_y": 34},
            {"city": "Minneapolis, MN", "lat_lon": "44.9778,-93.2650", "grid_id": "MPX", "grid_x": 108, "grid_y": 72},
            {"city": "Kansas City, MO", "lat_lon": "39.0997,-94.5786", "grid_id": "EAX", "grid_x": 44, "grid_y": 51},
            {"city": "St. Louis, MO", "lat_lon": "38.6270,-90.1994", "grid_id": "LSX", "grid_x": 95, "grid_y": 74},
            {"city": "Omaha, NE", "lat_lon": "41.2565,-95.9345", "grid_id": "OAX", "grid_x": 83, "grid_y": 60},
            {"city": "Fargo, ND", "lat_lon": "46.8772,-96.7898", "grid_id": "FGF", "grid_x": 100, "grid_y": 57},
            {"city": "Sioux Falls, SD", "lat_lon": "43.5446,-96.7311", "grid_id": "FSD", "grid_x": 98, "grid_y": 64},
            {"city": "Milwaukee, WI", "lat_lon": "43.0389,-87.9065", "grid_id": "MKX", "grid_x": 88, "grid_y": 65},
        ],
    },

    "Western Zone": {
        "id": "western",
        "cities": [
            {"city": "Phoenix, AZ", "lat_lon": "33.4484,-112.0740", "grid_id": "PSR", "grid_x": 159, "grid_y": 58},
            {"city": "Tucson, AZ", "lat_lon": "32.2226,-110.9747", "grid_id": "TWC", "grid_x": 91, "grid_y": 49},
            {"city": "Mesa, AZ", "lat_lon": "33.4152,-111.8315", "grid_id": "PSR", "grid_x": 168, "grid_y": 55},
            {"city": "Los Angeles, CA", "lat_lon": "34.0522,-118.2437", "grid_id": "LOX", "grid_x": 155, "grid_y": 45},
            {"city": "San Diego, CA", "lat_lon": "32.7157,-117.1611", "grid_id": "SGX", "grid_x": 57, "grid_y": 14},
            {"city": "San Jose, CA", "lat_lon": "37.3382,-121.8863", "grid_id": "MTR", "grid_x": 99, "grid_y": 82},
            {"city": "San Francisco, CA", "lat_lon": "37.7749,-122.4194", "grid_id": "MTR", "grid_x": 85, "grid_y": 105},
            {"city": "Sacramento, CA", "lat_lon": "38.5816,-121.4944", "grid_id": "STO", "grid_x": 41, "grid_y": 68},
            {"city": "Fresno, CA", "lat_lon": "36.7378,-119.7871", "grid_id": "HNX", "grid_x": 52, "grid_y": 100},
            {"city": "Portland, OR", "lat_lon": "45.5152,-122.6784", "grid_id": "PQR", "grid_x": 113, "grid_y": 104},
            {"city": "Eugene, OR", "lat_lon": "44.0521,-123.0868", "grid_id": "PQR", "grid_x": 85, "grid_y": 39},
            {"city": "Las Vegas, NV", "lat_lon": "36.1699,-115.1398", "grid_id": "VEF", "grid_x": 123, "grid_y": 98},
            {"city": "Reno, NV", "lat_lon": "39.5296,-119.8138", "grid_id": "REV", "grid_x": 45, "grid_y": 106},
            {"city": "Salt Lake City, UT", "lat_lon": "40.7608,-111.8910", "grid_id": "SLC", "grid_x": 100, "grid_y": 175},
            {"city": "Seattle, WA", "lat_lon": "47.6062,-122.3321", "grid_id": "SEW", "grid_x": 125, "grid_y": 68},
        ],
    },

}

ZONE_ROTATION = ['Eastern Zone', 'Southern Zone', 'Central Zone', 'Western Zone']

