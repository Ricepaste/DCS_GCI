import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from geometry import calculate_braa, calculate_speed, to_dms, sync_ordered_selection

def test_to_dms():
    assert to_dms(42.258333, True) == "N42°15'29\""
    assert to_dms(-41.869444, True) == "S41°52'09\""
    assert to_dms(41.869444, False) == "E41°52'09\""
    assert to_dms(-41.869444, False) == "W41°52'09\""

def test_sync_ordered_selection():
    # Test maintaining order and adding new items
    old_order = ['A', 'B']
    current = ['B', 'C', 'A'] # Random order from scene
    assert sync_ordered_selection(old_order, current) == ['A', 'B', 'C']
    
    # Test removing unselected items
    old_order = ['A', 'B', 'C']
    current = ['C', 'A']
    assert sync_ordered_selection(old_order, current) == ['A', 'C']
    
    # Test completely new selection
    old_order = ['A']
    current = ['B', 'C']
    assert sync_ordered_selection(old_order, current) == ['B', 'C']

def test_calculate_speed():
    # 30 m/s ~ 58 knots
    assert calculate_speed(30, 0) == 58
    # 40 m/s ~ 77 knots
    assert calculate_speed(0, 40) == 77
    # 30, 40 -> 50 m/s ~ 97 knots
    assert calculate_speed(30, 40) == 97

def test_calculate_braa_north():
    friendly = {'x': 0, 'z': 0, 'y': 10000 / 3.28084, 'vx': 0, 'vz': 0}
    target = {'x': 10000, 'z': 0, 'y': 20000 / 3.28084, 'vx': -200, 'vz': 0}
    
    # Target is straight North (x = 10000)
    braa = calculate_braa(friendly, target)
    assert braa['bearing'] == 0
    # Range is 10000m * 0.000539957 = 5.39 NM
    assert 5 <= braa['range'] <= 6
    assert braa['altitude'] == 20000
    assert braa['aspect'] == "HOT"

def test_calculate_braa_east():
    friendly = {'x': 0, 'z': 0, 'y': 0, 'vx': 0, 'vz': 0}
    target = {'x': 0, 'z': 10000, 'y': 0, 'vx': 200, 'vz': 0}
    
    # Target is straight East (z = 10000)
    braa = calculate_braa(friendly, target)
    assert braa['bearing'] == 90
    assert braa['aspect'] == "BEAM"

def test_get_sam_threat_range_nm():
    from geometry import get_sam_threat_range_nm
    assert get_sam_threat_range_nm("S-300PS 64H6E sr") is None
    assert get_sam_threat_range_nm("SA-10 S-300PS 5P85PT") is None
    assert get_sam_threat_range_nm("SA-10 S-300PS 30N6 TR") == 45.0
    assert get_sam_threat_range_nm("HAWK sr") is None
    assert get_sam_threat_range_nm("HAWK TR") == 24.0
    assert get_sam_threat_range_nm("HAWK ln") is None
    assert get_sam_threat_range_nm("Osa 9A33 ln") == 5.5
    assert get_sam_threat_range_nm("Tor 9A331") == 6.5
    assert get_sam_threat_range_nm("柴油發電車 (Generator)") is None
    assert get_sam_threat_range_nm("B-1B") is None
    assert get_sam_threat_range_nm("") is None
    assert get_sam_threat_range_nm(None) is None

def test_calculate_closure_rate():
    from geometry import calculate_closure_rate
    # Friendly flying North (+x) at 200 m/s (~388 kts)
    f = {'x': 0, 'z': 0, 'y': 3000, 'vx': 200, 'vz': 0}
    # Hostile 10km North flying South (-x) at 200 m/s (~388 kts) -> Head on
    h = {'x': 10000, 'z': 0, 'y': 3000, 'vx': -200, 'vz': 0}
    
    vc_kts, dist_nm = calculate_closure_rate(f, h)
    assert 5.0 <= dist_nm <= 5.5
    # Total closing speed: 400 m/s ~ 777 kts
    assert 770 <= vc_kts <= 785
    
    # Hostile flying away (+x) at 200 m/s -> Vc should be <= 0
    h_away = {'x': 10000, 'z': 0, 'y': 3000, 'vx': 200, 'vz': 0}
    vc_away, _ = calculate_closure_rate(f, h_away)
    assert vc_away <= 0
