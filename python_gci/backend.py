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
                telemetry = json.loads(json_str)
                
                with self.lock:
                    self.friendlies.clear()
                    self.hostiles.clear()
                    
                    for f in telemetry.get("friendlies", []):
                        self.friendlies[f.get("unit_name")] = f
                        
                    for h in telemetry.get("hostiles", []):
                        self.hostiles[h.get("unit_name")] = h
                        
                    self.last_update_time = time.time()
            except socket.timeout:
                pass
            except json.JSONDecodeError:
                print("Failed to decode JSON from DCS")
            except Exception as e:
                print(f"Error in backend: {e}")

    def get_tracks(self):
        with self.lock:
            return {
                "friendlies": list(self.friendlies.values()),
                "hostiles": list(self.hostiles.values()),
                "stale": time.time() - self.last_update_time > 3.0
            }
