import sys
import os
import json
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend import GCIBackend

def test_parse_track_data_valid():
    backend = GCIBackend(port=0, stagger_updates=False)
    
    # Simulate a valid JSON payload from DCS
    payload = {
        "friendlies": [
            {"unit_name": "F-16C_1", "x": 1000, "y": 5000, "z": 2000, "vx": 150, "vy": 0, "vz": 100, "coalition": 2, "type": "F-16C"}
        ],
        "hostiles": [
            {"unit_name": "MiG-29_1", "x": 50000, "y": 10000, "z": 10000, "vx": -200, "vy": 0, "vz": 0, "coalition": 1, "type": "MiG-29S"}
        ]
    }
    
    raw_data = json.dumps(payload)
    backend.parse_telemetry(raw_data)
    
    tracks = backend.get_tracks()
    
    assert len(tracks["friendlies"]) == 1
    assert tracks["friendlies"][0]["unit_name"] == "F-16C_1"
    assert tracks["friendlies"][0]["coalition"] == 2
    
    assert len(tracks["hostiles"]) == 1
    assert tracks["hostiles"][0]["unit_name"] == "MiG-29_1"
    assert tracks["hostiles"][0]["coalition"] == 1

def test_parse_track_data_invalid_json():
    backend = GCIBackend(port=0, stagger_updates=False)
    
    # Initial state should be empty
    assert len(backend.get_tracks()["friendlies"]) == 0
    
    # Sending broken JSON
    raw_data = "{ broken_json: [ "
    with pytest.raises(json.JSONDecodeError):
        backend.parse_telemetry(raw_data)
    
    # Should not crash, and should remain empty
    assert len(backend.get_tracks()["friendlies"]) == 0

def test_parse_track_data_missing_fields():
    backend = GCIBackend(port=0, stagger_updates=False)
    
    # Payload missing 'hostiles'
    payload = {
        "friendlies": [
            {"unit_name": "F-16C_1"}
        ]
    }
    
    raw_data = json.dumps(payload)
    backend.parse_telemetry(raw_data)
    
    tracks = backend.get_tracks()
    assert len(tracks["friendlies"]) == 1
    assert len(tracks["hostiles"]) == 0 # Default empty list if missing

def test_track_history_limit():
    backend = GCIBackend(port=0, stagger_updates=False)
    uid = "F-16C_1"
    
    # Send 15 updates for the same unit
    for i in range(15):
        payload = {
            "friendlies": [
                {"unit_name": uid, "x": i*10, "y": 5000, "z": i*10, "vx": 10, "vy": 0, "vz": 10, "coalition": 2, "type": "F-16C"}
            ]
        }
        raw_data = json.dumps(payload)
        backend.parse_telemetry(raw_data)
        backend.get_tracks() # Process the pending update
        
    tracks = backend.get_tracks()
    friendly = tracks["friendlies"][0]
    
    # The history list should be capped at 10 items
    assert len(friendly["history"]) == 10
    
    # The oldest items (0..4) should be popped, so the first remaining item is from i=4 (since current i=14 is appended AFTER)
    assert friendly["history"][0] == (40, 40) 
    assert friendly["history"][-1] == (130, 130)
