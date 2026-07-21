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

def generate_link16_tn(unit_name):
    """
    Generate a stable 4-digit Octal Link 16 Track Number (TN) from a unit name.
    """
    hash_val = sum(ord(c) * (i + 1) for i, c in enumerate(unit_name))
    octal_str = oct(hash_val % 4096)[2:] # 4096 is 10000 in octal (0-7777 range)
    return f"TN {octal_str.zfill(4)}"

def calculate_intercept_heading(hunter_x, hunter_z, hunter_v, target_x, target_z, target_vx, target_vz):
    """
    Calculate intercept course based on velocity vectors and positions.
    Returns (cut_heading_deg, time_to_intercept_sec, impact_x, impact_z) or None if impossible.
    """
    # Relative position
    dx = target_x - hunter_x
    dz = target_z - hunter_z
    dist = math.hypot(dx, dz)
    
    if dist < 1.0 or hunter_v <= 0:
        return None
        
    # Target velocity vector
    tv_mag = math.hypot(target_vx, target_vz)
    
    # If target is stationary, just point at it
    if tv_mag < 1.0:
        hdg = math.degrees(math.atan2(dz, dx))
        return ((hdg + 360) % 360, dist / hunter_v, target_x, target_z)
        
    # Law of sines for intercept triangle
    # Angle between LOS and Target velocity
    los_angle = math.atan2(dz, dx)
    target_hdg = math.atan2(target_vz, target_vx)
    
    # Angle beta (angle at the target between LOS and its travel direction)
    beta = target_hdg - los_angle
    
    # hunter_v / sin(beta) = target_v / sin(alpha)
    sin_alpha = (tv_mag / hunter_v) * math.sin(beta)
    
    # Check if intercept is possible (hunter is fast enough)
    if abs(sin_alpha) > 1.0:
        return None # Hunter too slow, cannot intercept
        
    alpha = math.asin(sin_alpha)
    
    # The intercept heading is LOS + alpha
    intercept_hdg_rad = los_angle + alpha
    intercept_hdg_deg = (math.degrees(intercept_hdg_rad) + 360) % 360
    
    # Calculate closing speed and time
    # closing velocity = hunter_v * cos(alpha) - target_v * cos(beta)
    closing_v = hunter_v * math.cos(alpha) - tv_mag * math.cos(beta)
    
    if closing_v <= 0:
        return None # Target is pulling away
        
    tti_sec = dist / closing_v
    
    # Calculate impact point
    impact_x = target_x + target_vx * tti_sec
    impact_z = target_z + target_vz * tti_sec
    
    return (intercept_hdg_deg, tti_sec, impact_x, impact_z)

def latlon_to_mgrs(lat, lon):
    try:
        import mgrs
        m = mgrs.MGRS()
        return m.toMGRS(lat, lon)
    except ImportError:
        return "MGRS_NA"

# DCS 各戰區的投影中央經線 (Central Meridian)
# DCS 使用 Transverse Mercator (lat_0=0, k=1) 搭配戰區專屬中央經線。
# 此值透過逆向工程 (最小化已知機場 DCS座標 與 coord.LOtoLL() 輸出之間的誤差) 確認。
DCS_THEATRE_CENTRAL_MERIDIANS = {
    "Caucasus": 33.0,
    "Syria": 36.0,
    "PersianGulf": 54.0,
    "Nevada": -117.0,
    "Marianas": 144.0,
    "Normandy": -1.0,
    "TheChannel": 2.0,
    "Sinai": 33.0,
    "SouthAtlantic": -57.0,
    "Kola": 33.0,
    "Afghanistan": 69.0,
}

def _get_dcs_proj(theatre="Caucasus"):
    """取得 DCS 戰區的 pyproj 投影物件 (快取)"""
    import pyproj
    lon_0 = DCS_THEATRE_CENTRAL_MERIDIANS.get(theatre, 33.0)
    return pyproj.Proj(f"+proj=tmerc +lat_0=0 +lon_0={lon_0} +k=1 +x_0=0 +y_0=0 +ellps=WGS84")

def dcs_to_latlon(dcs_x, dcs_z, ref_x, ref_z, ref_lat, ref_lon, theatre="Caucasus"):
    """
    Converts DCS Cartesian coordinates to WGS84 Lat/Lon.
    
    使用 DCS 戰區專屬的 Transverse Mercator 投影 (中央經線由戰區決定)。
    透過一個已知的參考點 (ref_x, ref_z, ref_lat, ref_lon) 校準投影座標偏移量，
    使得轉換精度在整張地圖上均勻且穩定 (< 250m 誤差)。
    """
    import pyproj
    proj = _get_dcs_proj(theatre)
    
    # 計算參考點在 DCS 投影平面上的偏移量
    ref_easting, ref_northing = proj(ref_lon, ref_lat)
    
    # DCS 座標到投影平面的轉換
    easting = ref_easting + (dcs_z - ref_z)
    northing = ref_northing + (dcs_x - ref_x)
    
    lon, lat = proj(easting, northing, inverse=True)
    return lat, lon

def latlon_to_dcs(lat, lon, ref_x, ref_z, ref_lat, ref_lon, theatre="Caucasus"):
    """
    Converts WGS84 Lat/Lon back to DCS Cartesian coordinates.
    """
    import pyproj
    proj = _get_dcs_proj(theatre)
    
    ref_easting, ref_northing = proj(ref_lon, ref_lat)
    target_easting, target_northing = proj(lon, lat)
    
    dcs_x = ref_x + (target_northing - ref_northing)
    dcs_z = ref_z + (target_easting - ref_easting)
    return dcs_x, dcs_z

def generate_mgrs_grid(ref_x, ref_z, ref_lat, ref_lon, map_min_lat=39.0, map_max_lat=46.0, map_min_lon=28.0, map_max_lon=44.0):
    """
    Generates MGRS 10km grid lines and 100km labels within the lat/lon bounding box.
    Returns:
        lines: list of tuples ((dcs_x1, dcs_z1), (dcs_x2, dcs_z2))
        labels: list of dicts {"text": "37T FH", "x": dcs_x, "z": dcs_z}
    """
    import pyproj
    import mgrs
    
    m = mgrs.MGRS()
    lines = []
    labels = []
    
    min_zone = int(math.floor((map_min_lon + 180) / 6)) + 1
    max_zone = int(math.floor((map_max_lon + 180) / 6)) + 1
    
    for zone in range(min_zone, max_zone + 1):
        proj_utm = pyproj.Proj(proj='utm', zone=zone, ellps='WGS84')
        
        # Calculate approximate UTM bounds for this zone and lat bounds
        # Northing goes roughly from 0 at equator.
        min_northing = map_min_lat * 111000
        max_northing = map_max_lat * 112000
        
        # Round to 100km bounds
        min_n_100k = int(min_northing // 100000) * 100000
        max_n_100k = int(max_northing // 100000) * 100000 + 100000
        
        # UTM easting ranges from 166k to 834k max at equator, use 100k to 900k
        for e100 in range(1, 9):
            easting = e100 * 100000
            for n100 in range(int(min_n_100k), int(max_n_100k), 100000):
                # Center point for label
                lon_c, lat_c = proj_utm(easting + 50000, n100 + 50000, inverse=True)
                if map_min_lat <= lat_c <= map_max_lat and map_min_lon <= lon_c <= map_max_lon:
                    # check if this center is actually in this zone
                    c_zone = int(math.floor((lon_c + 180) / 6)) + 1
                    if c_zone == zone:
                        dcs_x, dcs_z = latlon_to_dcs(lat_c, lon_c, ref_x, ref_z, ref_lat, ref_lon)
                        try:
                            # 100km square name
                            mgrs_str = m.toMGRS(lat_c, lon_c)
                            square_id = mgrs_str[:5] # e.g. "37T" and "FH", wait, toMGRS output is 37TFH1234567890
                            if len(mgrs_str) >= 5:
                                text = f"{mgrs_str[:3]} {mgrs_str[3:5]}"
                                labels.append({"text": text, "x": dcs_x, "z": dcs_z})
                        except:
                            pass
                
                # Draw 10km grid lines inside this 100km square
                for step in range(0, 100000, 10000):
                    # Vertical line (constant easting)
                    lon1, lat1 = proj_utm(easting + step, n100, inverse=True)
                    lon2, lat2 = proj_utm(easting + step, n100 + 100000, inverse=True)
                    # only draw if inside the map lon bounds roughly to avoid extending out of zone
                    z1 = int(math.floor((lon1 + 180) / 6)) + 1
                    z2 = int(math.floor((lon2 + 180) / 6)) + 1
                    if z1 == zone and z2 == zone:
                        dx1, dz1 = latlon_to_dcs(lat1, lon1, ref_x, ref_z, ref_lat, ref_lon)
                        dx2, dz2 = latlon_to_dcs(lat2, lon2, ref_x, ref_z, ref_lat, ref_lon)
                        lines.append(((dx1, dz1), (dx2, dz2)))
                    
                    # Horizontal line (constant northing)
                    lon1, lat1 = proj_utm(easting, n100 + step, inverse=True)
                    lon2, lat2 = proj_utm(easting + 100000, n100 + step, inverse=True)
                    z1 = int(math.floor((lon1 + 180) / 6)) + 1
                    z2 = int(math.floor((lon2 + 180) / 6)) + 1
                    if z1 == zone and z2 == zone:
                        dx1, dz1 = latlon_to_dcs(lat1, lon1, ref_x, ref_z, ref_lat, ref_lon)
                        dx2, dz2 = latlon_to_dcs(lat2, lon2, ref_x, ref_z, ref_lat, ref_lon)
                        lines.append(((dx1, dz1), (dx2, dz2)))

    return lines, labels
