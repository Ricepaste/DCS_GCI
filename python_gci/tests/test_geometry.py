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
