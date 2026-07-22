import math
import re

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
    Always returns (cut_heading_deg, time_to_intercept_sec, impact_x, impact_z).
    """
    # Relative position
    dx = target_x - hunter_x
    dz = target_z - hunter_z
    dist = math.hypot(dx, dz)
    los_angle = math.atan2(dz, dx)
    
    if dist < 1.0:
        return ((math.degrees(los_angle) + 360) % 360, 0.0, target_x, target_z)
        
    # Target velocity vector
    tv_mag = math.hypot(target_vx, target_vz)
    
    # If hunter is stationary or target is stationary
    if hunter_v <= 0 or tv_mag < 1.0:
        hdg = (math.degrees(los_angle) + 360) % 360
        v_eff = max(hunter_v, 1.0)
        return (hdg, dist / v_eff, target_x, target_z)
        
    # Law of sines for intercept triangle
    target_hdg = math.atan2(target_vz, target_vx)
    beta = target_hdg - los_angle
    
    sin_alpha = (tv_mag / hunter_v) * math.sin(beta)
    clamped_sin_alpha = max(-1.0, min(1.0, sin_alpha))
    alpha = math.asin(clamped_sin_alpha)
    
    intercept_hdg_rad = los_angle + alpha
    intercept_hdg_deg = (math.degrees(intercept_hdg_rad) + 360) % 360
    
    closing_v = hunter_v * math.cos(alpha) - tv_mag * math.cos(beta)
    if closing_v <= 0:
        closing_v = max(1.0, hunter_v)
        
    tti_sec = dist / closing_v
    impact_x = target_x + target_vx * tti_sec
    impact_z = target_z + target_vz * tti_sec
    
    return (intercept_hdg_deg, tti_sec, impact_x, impact_z)

def latlon_to_mgrs(lat, lon):
    try:
        import mgrs
        m = mgrs.MGRS()
        return m.toMGRS(lat, lon)
    except Exception:
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
    若 pyproj 模組不可用則使用線性估算，避免跳錯崩潰。
    """
    try:
        import pyproj
        proj = _get_dcs_proj(theatre)
        ref_easting, ref_northing = proj(ref_lon, ref_lat)
        easting = ref_easting + (dcs_z - ref_z)
        northing = ref_northing + (dcs_x - ref_x)
        lon, lat = proj(easting, northing, inverse=True)
        return lat, lon
    except Exception:
        dx = dcs_x - ref_x
        dz = dcs_z - ref_z
        lat = ref_lat + (dx / 111120.0)
        lon = ref_lon + (dz / (111120.0 * math.cos(math.radians(ref_lat))))
        return lat, lon

def latlon_to_dcs(lat, lon, ref_x, ref_z, ref_lat, ref_lon, theatre="Caucasus"):
    """
    Converts WGS84 Lat/Lon back to DCS Cartesian coordinates.
    """
    try:
        import pyproj
        proj = _get_dcs_proj(theatre)
        ref_easting, ref_northing = proj(ref_lon, ref_lat)
        target_easting, target_northing = proj(lon, lat)
        dcs_x = ref_x + (target_northing - ref_northing)
        dcs_z = ref_z + (target_easting - ref_easting)
        return dcs_x, dcs_z
    except Exception:
        dlat = lat - ref_lat
        dlon = lon - ref_lon
        dcs_x = ref_x + (dlat * 111120.0)
        dcs_z = ref_z + (dlon * 111120.0 * math.cos(math.radians(ref_lat)))
        return dcs_x, dcs_z

def generate_mgrs_grid(ref_x, ref_z, ref_lat, ref_lon, map_min_lat=39.0, map_max_lat=46.0, map_min_lon=28.0, map_max_lon=44.0):
    """
    Generates MGRS 10km grid lines and 100km labels within the lat/lon bounding box.
    Returns:
        lines: list of tuples ((dcs_x1, dcs_z1), (dcs_x2, dcs_z2))
        labels: list of dicts {"text": "37T FH", "x": dcs_x, "z": dcs_z}
    """
    try:
        import pyproj
        import mgrs
    except Exception:
        return [], []
    
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

SAM_THREAT_RANGES = {
    # SA-5 Gammon (S-200)
    "S-200": 130.0,
    "5566": 130.0,
    
    # SA-10 Grumble (S-300PS / S-300PMU)
    "S-300": 45.0,
    "64H6E": 45.0,
    "30N6": 45.0,
    "SA-10": 45.0,
    
    # Patriot (PAC-2 / PAC-3)
    "PATRIOT": 43.0,
    "AN/MPQ-53": 43.0,
    
    # SA-2 Guideline (S-75)
    "S-75": 23.0,
    "SA-2": 23.0,
    "FAN SONG": 23.0,
    
    # HAWK (MIM-23)
    "HAWK": 24.0,
    
    # SA-11 Gadfly / SA-17 Grizzly (Buk-M1-2 / Buk-M2)
    "BUK": 19.0,
    "9A310": 19.0,
    "9A317": 19.0,
    "9S18": 19.0,
    "SA-11": 19.0,
    "SA-17": 19.0,
    
    # SA-6 Gainful (2K12 Kub)
    "KUB": 13.5,
    "SA-6": 13.5,
    "STR": 13.5,
    
    # SA-3 Goa (S-125 Pechora)
    "S-125": 13.0,
    "LOW BLOW": 13.0,
    "SA-3": 13.0,
    
    # NASAMS
    "NASAMS": 13.0,
    
    # HQ-7 / Crotale
    "HQ-7": 8.0,
    "CROTALE": 8.0,
    
    # SA-15 Gauntlet (Tor-M1 / Tor-M2)
    "TOR": 6.5,
    "9A331": 6.5,
    "SA-15": 6.5,
    
    # SA-8 Gecko (9K33 Osa)
    "OSA": 5.5,
    "9A33": 5.5,
    "SA-8": 5.5,
    
    # Roland
    "ROLAND": 4.3,
    
    # SA-19 Grison (2S6 Tunguska)
    "2S6": 4.3,
    "TUNGUSKA": 4.3,
    "SA-19": 4.3,
    
    # SA-13 Gopher (9K35 Strela-10)
    "STRELA-10": 2.7,
    "9A35": 2.7,
    "SA-13": 2.7,
    
    # Avenger / Linebacker / Chaparral
    "AVENGER": 3.0,
    "LINEBACKER": 3.0,
    "CHAPARRAL": 3.0,
    
    # SA-9 Gaskin (9K31 Strela-1)
    "STRELA-1": 2.3,
    "9A31": 2.3,
    "SA-9": 2.3,
    
    # Gepard / Shilka / AAA / Vulcan
    "GEPARD": 2.2,
    "SHILKA": 1.4,
    "ZSU-23": 1.4,
    "VULCAN": 1.2,
}

def get_sam_display_name(unit_type):
    """
    Returns a short display name for the SAM site (e.g. 'SA-10', 'HAWK') based on the DCS unit type.
    """
    if not unit_type:
        return ""
    type_upper = str(unit_type).upper()
    
    # Check for specific families first
    if "S-300" in type_upper or "SA-10" in type_upper or "64H6" in type_upper or "30N6" in type_upper:
        return "SA-10 (S-300)"
    if "PATRIOT" in type_upper or "MPQ-53" in type_upper:
        return "Patriot"
    if "HAWK" in type_upper:
        return "HAWK"
    if "BUK" in type_upper or "SA-11" in type_upper or "SA-17" in type_upper or "9A310" in type_upper or "9S18" in type_upper:
        return "SA-11 (Buk)"
    if "TOR" in type_upper or "SA-15" in type_upper or "9A331" in type_upper:
        return "SA-15 (Tor)"
    if "OSA" in type_upper or "SA-8" in type_upper or "9A33" in type_upper:
        return "SA-8 (Osa)"
    if "TUNGUSKA" in type_upper or "2S6" in type_upper or "SA-19" in type_upper:
        return "SA-19 (2S6)"
    if "S-200" in type_upper or "5566" in type_upper:
        return "SA-5 (S-200)"
    if "S-75" in type_upper or "SA-2" in type_upper or "FAN SONG" in type_upper:
        return "SA-2 (S-75)"
    if "S-125" in type_upper or "SA-3" in type_upper or "LOW BLOW" in type_upper:
        return "SA-3 (S-125)"
    if "KUB" in type_upper or "SA-6" in type_upper or "STR" in type_upper:
        return "SA-6 (Kub)"
    if "NASAMS" in type_upper:
        return "NASAMS"
    if "HQ-7" in type_upper or "CROTALE" in type_upper:
        return "HQ-7"
    if "STRELA-10" in type_upper or "SA-13" in type_upper or "9A35" in type_upper:
        return "SA-13 (Strela-10)"
    if "STRELA-1" in type_upper or "SA-9" in type_upper or "9A31" in type_upper:
        return "SA-9 (Strela-1)"
    if "GEPARD" in type_upper: return "Gepard"
    if "SHILKA" in type_upper or "ZSU-23" in type_upper: return "Shilka"
    if "AVENGER" in type_upper: return "Avenger"
    if "LINEBACKER" in type_upper: return "Linebacker"
    if "ROLAND" in type_upper: return "Roland"
    if "VULCAN" in type_upper: return "Vulcan"
    if "CHAPARRAL" in type_upper: return "Chaparral"
    
    return "SAM"

def get_sam_threat_range_nm(unit_type):
    """
    Returns SAM engagement range in Nautical Miles for known DCS air defense / SAM types.
    Returns None if not a recognized SAM/Air defense unit, or if it is a standalone launcher.
    """
    if not unit_type:
        return None
    type_upper = str(unit_type).upper()
    
    # 1. 判斷是否為一體防空車 (TELAR / SPAAG) 或火控雷達 (FCR/TR/STR)
    # 我們刻意排除了搜索雷達 (SR, 64H6E, 9S18) 以免同一個陣地畫出兩個重疊的威脅圈
    telar_or_radar = [
        "9A331", "TUNGUSKA", "2S6", "STRELA", "GEPARD", "SHILKA", "VULCAN", 
        "AVENGER", "LINEBACKER", "ROLAND", "BUK", "9A310", "9A317", "CHAPARRAL",
        " TR", "STR", "MPQ", "30N6", "FAN SONG", "LOW BLOW", "S-200_RADAR", "9A33"
    ]
    
    # 2. 判斷是否為純發射車或無關單位 (Launcher / Generator)
    launcher_only = [" LN", "_LN", " LAUNCHER", "_LAUNCHER", "5P85", "5P73", "2P25", "M192", "M901", "GENERATOR"]
    
    # "TOR" has to be exact word to prevent matching "GENERATOR"
    if re.search(r'\bTOR\b', type_upper) or re.search(r'\bOSA\b', type_upper):
        is_telar_or_radar = True
    else:
        is_telar_or_radar = any(k in type_upper for k in telar_or_radar)
        
    is_launcher = any(k in type_upper for k in launcher_only)
    
    # 如果它是純發射車或發電機，且「不是」一體防空車（例如 Osa 雖然名字帶 LN 但它是一體的），就不畫威脅圈
    if is_launcher and not is_telar_or_radar:
        return None
        
    # 如果是搜索雷達，也不畫威脅圈 (避免與火控雷達重疊)
    if " SR" in type_upper or "64H6E" in type_upper or "9S18" in type_upper or "5N66" in type_upper:
        return None
        
    for key, range_nm in SAM_THREAT_RANGES.items():
        if key in type_upper:
            return range_nm
    return None
