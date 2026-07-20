import math

def calculate_speed(vx, vz):
    """
    Calculate ground speed in knots from velocity vectors in m/s.
    """
    speed_m_s = math.sqrt(vx**2 + vz**2)
    return int(speed_m_s * 1.94384)

def to_dms(deg, is_lat):
    """Convert decimal degrees to standard DMS string format."""
    direction = "N" if is_lat and deg >= 0 else ("S" if is_lat else ("E" if deg >= 0 else "W"))
    deg = abs(deg)
    d = int(deg)
    m = int((deg - d) * 60)
    s = int((deg - d - m/60.0) * 3600)
    return f"{direction}{d:02d}°{m:02d}'{s:02d}\""

def sync_ordered_selection(old_order, current_names):
    """
    Synchronize the ordered selection list with the current selected items.
    Maintains the order of old items, and appends new items at the end.
    """
    new_order = [n for n in old_order if n in current_names]
    for name in current_names:
        if name not in new_order:
            new_order.append(name)
    return new_order

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
        
    if aspect <= 30:
        aspect_str = "HOT"
    elif aspect <= 60:
        aspect_str = "FLANK"
    elif aspect <= 120:
        aspect_str = "BEAM"
    else:
        aspect_str = "DRAG"
        
    return {
        "bearing": int(bearing_deg),
        "range": int(range_nm),
        "altitude": int(alt_ft / 1000) * 1000, # Round to thousands
        "aspect": aspect_str
    }
