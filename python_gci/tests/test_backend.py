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

def test_backend_none_types():
    """Test that the backend correctly handles None types in telemetry data."""
    backend = GCIBackend(port=0, stagger_updates=False)
    
    # DCS can export None (null in JSON) for types or names
    malicious_payload = json.dumps({
        "friendlies": [
            {
                "unit_name": "Ghost",
                "player_name": None,
                "type": None,
                "x": 100, "z": 200, "y": 300,
                "vx": 50, "vz": 50, "vy": 0
            }
        ],
        "hostiles": [],
        "airbases": []
    })
    
    backend.parse_telemetry(malicious_payload)
    tracks = backend.get_tracks()
    
    assert len(tracks["friendlies"]) == 1
    friendly = tracks["friendlies"][0]
    assert friendly["unit_name"] == "Ghost"
    assert friendly["player_name"] is None
    assert friendly["type"] is None

def test_backend_starvation_prevention():
    """Test that rapid telemetry updates don't push apply_time indefinitely."""
    import time
    backend = GCIBackend(port=0, stagger_updates=True)
    
    payload1 = json.dumps({
        "friendlies": [
            {"unit_name": "T1", "x": 0, "z": 0, "y": 0, "vx": 0, "vz": 0}
        ]
    })
    
    backend.parse_telemetry(payload1)
    
    assert "T1" in backend.pending_updates
    initial_apply_time, _, _ = backend.pending_updates["T1"]
    
    # Simulate rapid update arriving right after
    time.sleep(0.01)
    backend.parse_telemetry(payload1)
    
    new_apply_time, _, _ = backend.pending_updates["T1"]
    assert initial_apply_time == new_apply_time, "apply_time was incorrectly overwritten!"

def test_dual_coalition_parsing():
    backend = GCIBackend(port=0, stagger_updates=False, coalition="blue")
    
    dual_payload = json.dumps({
        "blue": {
            "friendlies": [{"unit_name": "BlueFighter_1"}],
            "hostiles": [{"unit_name": "RedTarget_1"}]
        },
        "red": {
            "friendlies": [{"unit_name": "RedFighter_1"}],
            "hostiles": [{"unit_name": "BlueTarget_1"}]
        }
    })
    
    # 1. BLUE coalition parsing
    backend.parse_telemetry(dual_payload)
    tracks_blue = backend.get_tracks()
    assert len(tracks_blue["friendlies"]) == 1
    assert tracks_blue["friendlies"][0]["unit_name"] == "BlueFighter_1"
    assert len(tracks_blue["hostiles"]) == 1
    assert tracks_blue["hostiles"][0]["unit_name"] == "RedTarget_1"
    
    # 2. Switch to RED coalition
    backend.set_coalition("red")
    backend.parse_telemetry(dual_payload)
    tracks_red = backend.get_tracks()
    assert len(tracks_red["friendlies"]) == 1
    assert tracks_red["friendlies"][0]["unit_name"] == "RedFighter_1"
    assert len(tracks_red["hostiles"]) == 1
    assert tracks_red["hostiles"][0]["unit_name"] == "BlueTarget_1"
