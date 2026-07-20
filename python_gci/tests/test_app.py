import sys
import os
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import RadarView
from backend import GCIBackend

# Ensure a QApplication exists for testing QGraphicsView/Scene
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

def test_radar_view_toggle_airbases():
    backend = GCIBackend(port=0, stagger_updates=False)
    radar = RadarView(backend)
    
    # By default, airbases should be visible
    assert radar.show_airbases == True
    
    # Since airbases are empty by default in this test, let's inject a fake one
    radar.airbases = {"FakeBase": {"x": 0, "z": 0}}
    radar.draw_airbases()
    
    # Verify the items are visible initially
    for item in radar.airbase_items:
        assert item.isVisible() == True
        
    # Toggle off
    radar.toggle_airbases()
    assert radar.show_airbases == False
    for item in radar.airbase_items:
        assert item.isVisible() == False
        
    # Toggle on
    radar.toggle_airbases()
    assert radar.show_airbases == True
    for item in radar.airbase_items:
        assert item.isVisible() == True

def test_radar_view_history_dots_rendered():
    backend = GCIBackend(port=0, stagger_updates=False)
    radar = RadarView(backend)
    
    # Mock data with history
    data = {
        'unit_name': 'TestFighter',
        'x': 100, 'z': 100, 'y': 1000,
        'vx': 10, 'vz': 10,
        'history': [(0, 0), (50, 50), (100, 100)]
    }
    
    # First render
    radar._update_single_track(data, color=QColor(255, 0, 0), is_hostile=True)
    items = radar.track_items['TestFighter']
    
    # It should have 3 history dots created
    assert len(items['history_dots']) == 3
    
    # Simulate history growing
    data['history'].append((150, 150))
    radar._update_single_track(data, color=QColor(255, 0, 0), is_hostile=True)
    
    assert len(items['history_dots']) == 4
    
    # Simulate history shrinking (e.g. backend reset or object recycled)
    data['history'] = [(150, 150)]
    radar._update_single_track(data, color=QColor(255, 0, 0), is_hostile=True)
    
    assert len(items['history_dots']) == 1
