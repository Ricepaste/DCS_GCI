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

def test_radar_view_track_classification():
    backend = GCIBackend(port=0, stagger_updates=False)
    radar = RadarView(backend)
    
    # Check defaults
    assert radar.get_track_classification("Unknown1", default_is_hostile=True) == "UNKNOWN"
    assert radar.get_track_classification("Friend1", default_is_hostile=False) == "FRIENDLY"
    
    # Change classification
    radar.set_track_classification("Unknown1", "HOSTILE")
    assert radar.get_track_classification("Unknown1", default_is_hostile=True) == "HOSTILE"
    
    # Check that friendlies can also be reclassified
    radar.set_track_classification("Friend1", "UNKNOWN")
    assert radar.get_track_classification("Friend1", default_is_hostile=False) == "UNKNOWN"

def test_status_panel_saves_notes():
    from app import AircraftStatusPanel
    panel = AircraftStatusPanel()
    
    # Initial state
    assert panel.global_data == {}
    
    data = {'unit_name': 'TestPilot', 'y': 0, 'vx': 0, 'vz': 0, 'heading': 0}
    panel.update_data(data, "F-16C", False, "FRIENDLY")
    
    panel.notes_edit.setPlainText("CAP Station 1")
    
    # Switch to another unit to trigger save
    data2 = {'unit_name': 'OtherPilot', 'y': 0, 'vx': 0, 'vz': 0, 'heading': 0}
    panel.update_data(data2, "F-15C", False, "FRIENDLY")
    
    # Verify data was saved for TestPilot
    assert 'TestPilot' in panel.global_data
    assert panel.global_data['TestPilot']['notes'] == "CAP Station 1"

def test_radar_view_icon_shape_change():
    from PyQt6.QtWidgets import QGraphicsPolygonItem, QGraphicsRectItem, QGraphicsEllipseItem
    backend = GCIBackend(port=0, stagger_updates=False)
    radar = RadarView(backend)
    
    data = {'unit_name': 'Track1', 'x': 0, 'z': 0, 'y': 1000, 'vx': 0, 'vz': 0}
    
    # 1. Unknown -> Square (QGraphicsRectItem)
    radar._update_single_track(data, QColor(255, 255, 0), is_hostile=True, prefix='U')
    item = radar.track_items['Track1']['icon']
    assert isinstance(item, QGraphicsRectItem)
    
    # 2. Reclassify to Bandit -> Diamond (QGraphicsPolygonItem)
    radar._update_single_track(data, QColor(255, 0, 0), is_hostile=True, prefix='B')
    item = radar.track_items['Track1']['icon']
    assert isinstance(item, QGraphicsPolygonItem)
    
    # 3. Reclassify to Hostile -> Diamond (QGraphicsPolygonItem)
    radar._update_single_track(data, QColor(255, 0, 0), is_hostile=True, prefix='H')
    item = radar.track_items['Track1']['icon']
    assert isinstance(item, QGraphicsPolygonItem)
    
    # 4. Reclassify to Friendly -> Circle (QGraphicsEllipseItem)
    radar._update_single_track(data, QColor(0, 255, 0), is_hostile=False, prefix='F')
    item = radar.track_items['Track1']['icon']
    assert isinstance(item, QGraphicsEllipseItem)

def test_nctr_hostile_unit_type_visibility():
    backend = GCIBackend(port=0, stagger_updates=False)
    radar = RadarView(backend)
    
    hostile_data = {'unit_name': 'Flanker1', 'type': 'Su-27', 'x': 100000, 'z': 100000, 'y': 5000, 'vx': 0, 'vz': 0}
    
    # 1. Far away without AWACS NCTR -> should hide Su-27 and show only TN
    unit_type_str = radar.get_unit_type(hostile_data, is_hostile=True, tracks={'friendlies': []})
    assert unit_type_str == "UNKNOWN"
    
    # Render track
    radar._update_single_track(hostile_data, QColor(255, 255, 0), is_hostile=True, prefix='U')
    html = radar.track_items['Flanker1']['last_html']
    assert "Su-27" not in html

    # 2. Friendly AWACS close by (30 NM) facing target -> NCTR success
    hostile_data_moving = {'unit_name': 'Flanker1', 'type': 'Su-27', 'x': 100000, 'z': 100000, 'y': 5000, 'vx': 0, 'vz': -100}
    friendly_awacs = {'unit_name': 'Magic1', 'type': 'E-3A', 'x': 100000, 'z': 44440, 'y': 10000, 'vx': 0, 'vz': 100}
    unit_type_str_success = radar.get_unit_type(hostile_data_moving, is_hostile=True, tracks={'friendlies': [friendly_awacs]})
    assert unit_type_str_success == "Su-27"

def test_status_panel_update_data_without_heading():
    from app import AircraftStatusPanel
    panel = AircraftStatusPanel()
    data = {'unit_name': 'NoHdgPilot', 'y': 1000, 'vx': 10, 'vz': 10}
    # Should not raise KeyError: 'heading'
    panel.update_data(data, "Su-27", True, "HOSTILE")
    assert panel.lbl_hdg.text() == "045°"
