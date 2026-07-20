import math

def calculate_braa(friendly, target):
    """
    Calculate Bearing, Range, Altitude, Aspect (BRAA) from friendly to target.
    friendly, target: dicts with x, z, y(alt), vx, vz
    DCS Coordinates: x = North, z = East. y = Up (Altitude).
    """
    dx = target['z'] - friendly['z'] # East
    dy = target['x'] - friendly['x'] # North
    
    # Bearing
    bearing_rad = math.atan2(dx, dy)
    bearing_deg = (math.degrees(bearing_rad) + 360) % 360
    
    # Range
    distance_m = math.sqrt(dx**2 + dy**2)
    range_nm = distance_m * 0.000539957
    
    # Altitude
    alt_ft = target['y'] * 3.28084
    
    # Aspect
    # Target's heading
    target_heading_rad = math.atan2(target['vz'], target['vx'])
    target_heading_deg = (math.degrees(target_heading_rad) + 360) % 360
    
    # Angle from Target to Friendly
    angle_to_friendly = (math.degrees(math.atan2(-dx, -dy)) + 360) % 360
    
    aspect = abs(angle_to_friendly - target_heading_deg)
    if aspect > 180:
        aspect = 360 - aspect
        
    aspect_str = "HOT"
    if aspect < 45:
        aspect_str = "HOT"
    elif aspect < 135:
        aspect_str = "FLANK"
    else:
        aspect_str = "COLD"
        
    return {
        "bearing": int(bearing_deg),
        "range": int(range_nm),
        "altitude": int(alt_ft / 1000) * 1000, # Round to thousands
        "aspect": aspect_str
    }
