import sys
import os
import json
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend import GCIBackend

def test_parse_track_data_valid():
    backend = GCIBackend(port=0)
    
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
    backend = GCIBackend(port=0)
    
    # Initial state should be empty
    assert len(backend.get_tracks()["friendlies"]) == 0
    
    # Sending broken JSON
    raw_data = "{ broken_json: [ "
    with pytest.raises(json.JSONDecodeError):
        backend.parse_telemetry(raw_data)
    
    # Should not crash, and should remain empty
    assert len(backend.get_tracks()["friendlies"]) == 0

def test_parse_track_data_missing_fields():
    backend = GCIBackend(port=0)
    
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
