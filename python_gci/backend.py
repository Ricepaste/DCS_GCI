import socket
import json
import threading
import time

class GCIBackend:
    def __init__(self, host="0.0.0.0", port=10082):
        self.host = host
        self.port = port
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
        
        self.lock = threading.Lock()

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
                print("Failed to decode JSON from DCS")
            except Exception as e:
                print(f"Error in backend: {e}")

    def parse_telemetry(self, json_str):
        telemetry = json.loads(json_str)
        
        with self.lock:
            self.friendlies.clear()
            self.hostiles.clear()
            
            for f in telemetry.get("friendlies", []):
                uid = f.get("unit_name")
                if uid not in self.history:
                    self.history[uid] = []
                f['history'] = list(self.history[uid])
                self.friendlies[uid] = f
                # Append current position for the next sweep
                self.history[uid].append((f.get("x", 0), f.get("z", 0)))
                if len(self.history[uid]) > 10:
                    self.history[uid].pop(0)
                
            for h in telemetry.get("hostiles", []):
                uid = h.get("unit_name")
                if uid not in self.history:
                    self.history[uid] = []
                h['history'] = list(self.history[uid])
                self.hostiles[uid] = h
                # Append current position for the next sweep
                self.history[uid].append((h.get("x", 0), h.get("z", 0)))
                if len(self.history[uid]) > 10:
                    self.history[uid].pop(0)
                
            self.airbases = telemetry.get("airbases", [])
                
            self.last_update_time = time.time()

    def get_tracks(self):
        with self.lock:
            return {
                "friendlies": list(self.friendlies.values()),
                "hostiles": list(self.hostiles.values()),
                "airbases": self.airbases,
                "stale": time.time() - self.last_update_time > 3.0
            }
