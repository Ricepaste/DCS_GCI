import socket
import json
import time
from battlefield_state import BattlefieldState
from bvr_decision_engine import build_bvr_tree
import py_trees

UDP_IP_LISTEN = "127.0.0.1"
UDP_PORT_LISTEN = 10080
UDP_IP_SEND = "127.0.0.1"
UDP_PORT_SEND = 10081

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP_LISTEN, UDP_PORT_LISTEN))
    sock.settimeout(0.1) # Non-blocking roughly
    
    state_matrix = BattlefieldState()
    command_queue = []
    
    ai_trees = {}
    
    print(f"DCS AI Brain Listening on {UDP_IP_LISTEN}:{UDP_PORT_LISTEN}...")
    
    while True:
        try:
            # 1. Receive Telemetry
            data, addr = sock.recvfrom(4096)
            json_str = data.decode('utf-8')
            state_matrix.update_from_json(json_str)
            
            parsed = json.loads(json_str)
            group_name = parsed.get("group_name")
            
            if group_name and group_name not in ai_trees:
                print(f"Initializing Behavior Tree for {group_name}")
                tree_root = build_bvr_tree(group_name, state_matrix, command_queue)
                ai_trees[group_name] = py_trees.trees.BehaviourTree(tree_root)
                ai_trees[group_name].setup(timeout=15)
                
        except socket.timeout:
            pass 
        except Exception as e:
            print(f"Main loop error: {e}")
            
        # 2. Tick Behavior Trees
        for g_name, tree in ai_trees.items():
            tree.tick()
            
        # 3. Send Commands
        while command_queue:
            cmd = command_queue.pop(0)
            try:
                msg = json.dumps(cmd).encode('utf-8')
                sock.sendto(msg, (UDP_IP_SEND, UDP_PORT_SEND))
                print(f"Sent command to DCS: {cmd}")
            except Exception as e:
                print(f"Failed to send command: {e}")
                
        time.sleep(0.1) # 10Hz tick rate

if __name__ == "__main__":
    main()
