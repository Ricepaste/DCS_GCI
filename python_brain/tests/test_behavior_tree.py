import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import py_trees
from battlefield_state import BattlefieldState
from bvr_decision_engine import build_bvr_tree

def test_bvr_tree_defensive_pump():
    state_matrix = BattlefieldState()
    # Mock json telemetry for a locked group
    mock_json = '{"group_name": "Red_CAP", "units": [{"name": "Pilot1", "is_locked": true, "has_missile_in_air": false}]}'
    state_matrix.update_from_json(mock_json)
    
    command_queue = []
    tree_root = build_bvr_tree("Red_CAP", state_matrix, command_queue)
    tree = py_trees.trees.BehaviourTree(tree_root)
    tree.setup(timeout=15)
    tree.tick()
    
    assert len(command_queue) == 1
    assert command_queue[0]["cmd"] == "pump"
    assert command_queue[0]["group"] == "Red_CAP"

def test_bvr_tree_offensive_crank():
    state_matrix = BattlefieldState()
    # Mock json telemetry for a group that fired a missile but is not locked
    mock_json = '{"group_name": "Red_CAP", "units": [{"name": "Pilot1", "is_locked": false, "has_missile_in_air": true}]}'
    state_matrix.update_from_json(mock_json)
    
    command_queue = []
    tree_root = build_bvr_tree("Red_CAP", state_matrix, command_queue)
    tree = py_trees.trees.BehaviourTree(tree_root)
    tree.setup(timeout=15)
    tree.tick()
    
    assert len(command_queue) == 1
    assert command_queue[0]["cmd"] == "crank"
    assert command_queue[0]["group"] == "Red_CAP"

def test_bvr_tree_idle():
    state_matrix = BattlefieldState()
    # Mock json telemetry for idle group
    mock_json = '{"group_name": "Red_CAP", "units": [{"name": "Pilot1", "is_locked": false, "has_missile_in_air": false}]}'
    state_matrix.update_from_json(mock_json)
    
    command_queue = []
    tree_root = build_bvr_tree("Red_CAP", state_matrix, command_queue)
    tree = py_trees.trees.BehaviourTree(tree_root)
    tree.setup(timeout=15)
    tree.tick()
    
    # Should be no commands issued
    assert len(command_queue) == 0
