import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from geometry import calculate_braa

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
    assert braa['aspect'] == "FLANK"
