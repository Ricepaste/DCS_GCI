import socket
import json
import threading
import time

class GCIBackend:
    def __init__(self, host="0.0.0.0", port=10088, stagger_updates=True):
        self.host = host
        self.port = port
        self.stagger_updates = stagger_updates
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.sock.settimeout(1.0)
        
        self.running = False
        self.thread = None
        
        self.friendlies = {}
        self.hostiles = {}
        self.airbases = []
        self.history = {} # unit_name -> list of (x, z) tuples
        self.last_update_time = time.time()
        
        self.pending_updates = {} # uid -> (apply_time, is_friendly, data)
        self.last_seen_time = {} # uid -> time.time()
        
        self.lock = threading.Lock()

    def _get_stagger_delay(self, uid):
        if not self.stagger_updates:
            return 0.0
        # Deterministic delay between 0.0 and 3.9 seconds based on unit name
        checksum = sum(ord(c) for c in str(uid))
        return (checksum % 40) / 10.0

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _listen_loop(self):
        print(f"GCI Backend Listening on {self.host}:{self.port}")
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65536)
                json_str = data.decode('utf-8')
                self.parse_telemetry(json_str)
            except socket.timeout:
                pass
            except json.JSONDecodeError:
                with open("backend.log", "a") as f:
                    f.write(f"[{time.time()}] Failed to decode JSON from DCS\n")
            except Exception as e:
                with open("backend.log", "a") as f:
                    f.write(f"[{time.time()}] Error in backend: {e}\n")
        
        with open("backend.log", "a") as f:
            f.write(f"[{time.time()}] Thread stopped.\n")

    def parse_telemetry(self, json_str):
        with open("backend.log", "a") as f:
            f.write(f"[{time.time()}] Received payload of length {len(json_str)}\n")
        
        telemetry = json.loads(json_str)
        current_time = time.time()
        
        with self.lock:
            # We do NOT clear self.friendlies and self.hostiles here anymore
            # Updates are placed into a pending queue to stagger their UI rendering
            
            for f in telemetry.get("friendlies", []):
                uid = f.get("unit_name")
                self.last_seen_time[uid] = current_time
                if uid in self.pending_updates:
                    old_apply_time, _, _ = self.pending_updates[uid]
                    self.pending_updates[uid] = (old_apply_time, True, f)
                else:
                    delay = self._get_stagger_delay(uid)
                    self.pending_updates[uid] = (current_time + delay, True, f)
                
            for h in telemetry.get("hostiles", []):
                uid = h.get("unit_name")
                self.last_seen_time[uid] = current_time
                if uid in self.pending_updates:
                    old_apply_time, _, _ = self.pending_updates[uid]
                    self.pending_updates[uid] = (old_apply_time, False, h)
                else:
                    delay = self._get_stagger_delay(uid)
                    self.pending_updates[uid] = (current_time + delay, False, h)
                
            self.airbases = telemetry.get("airbases", [])
            self.last_update_time = current_time

    def get_tracks(self):
        current_time = time.time()
        
        with self.lock:
            # 1. Apply pending updates that are due
            to_remove_pending = []
            for uid, (apply_time, is_friendly, data) in self.pending_updates.items():
                if current_time >= apply_time:
                    if uid not in self.history:
                        self.history[uid] = []
                    
                    data['history'] = list(self.history[uid])
                    
                    if is_friendly:
                        self.friendlies[uid] = data
                    else:
                        self.hostiles[uid] = data
                        
                    # Append current position for the next sweep
                    self.history[uid].append((data.get("x", 0), data.get("z", 0)))
                    if len(self.history[uid]) > 10:
                        self.history[uid].pop(0)
                        
                    to_remove_pending.append(uid)
            
            for uid in to_remove_pending:
                del self.pending_updates[uid]
                
            # 2. Remove stale tracks (missed 2 consecutive 4.0s UDP packets)
            to_remove_stale = []
            for uid, seen_time in self.last_seen_time.items():
                if current_time - seen_time > 8.5:
                    to_remove_stale.append(uid)
                    
            for uid in to_remove_stale:
                if uid in self.friendlies: del self.friendlies[uid]
                if uid in self.hostiles: del self.hostiles[uid]
                if uid in self.history: del self.history[uid]
                if uid in self.pending_updates: del self.pending_updates[uid]
                del self.last_seen_time[uid]

            return {
                "friendlies": list(self.friendlies.values()),
                "hostiles": list(self.hostiles.values()),
                "airbases": self.airbases,
                "stale": current_time - self.last_update_time > 8.5
            }
