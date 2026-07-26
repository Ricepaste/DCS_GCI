import socket
import json
import threading
import time

class GCIServer:
    def __init__(self, tcp_host="0.0.0.0", tcp_port=10088, udp_port=10088):
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.running = False
        
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_sock.bind(("0.0.0.0", self.udp_port))
        self.udp_sock.settimeout(1.0)
        
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_sock.bind((self.tcp_host, self.tcp_port))
        self.tcp_sock.listen(5)
        self.tcp_sock.settimeout(1.0)
        
        self.clients = []
        self.lock = threading.Lock()
        
    def start(self):
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        threading.Thread(target=self._udp_listen_loop, daemon=True).start()
        
    def stop(self):
        self.running = False
        try:
            self.udp_sock.close()
        except:
            pass
        try:
            self.tcp_sock.close()
        except:
            pass
        with self.lock:
            for c in self.clients:
                try:
                    c.close()
                except:
                    pass
            self.clients.clear()
        
    def _accept_loop(self):
        print(f"[Server] TCP Listening on {self.tcp_host}:{self.tcp_port}")
        while self.running:
            try:
                client, addr = self.tcp_sock.accept()
                client.settimeout(2.0)
                print(f"[Server] Client connected: {addr}")
                with self.lock:
                    self.clients.append(client)
            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    print(f"[Server] Accept error: {e}")
                    
    def _udp_listen_loop(self):
        print(f"[Server] UDP Listening on {self.udp_port}")
        while self.running:
            try:
                data, addr = self.udp_sock.recvfrom(65536)
                self._broadcast(data)
            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    print(f"[Server] UDP error: {e}")
                    
    def _broadcast(self, data):
        # We prefix data with its length + newline to handle TCP stream framing
        payload = f"{len(data)}\n".encode('utf-8') + data
        with self.lock:
            disconnected = []
            for c in self.clients:
                try:
                    c.sendall(payload)
                except Exception:
                    disconnected.append(c)
            
            for c in disconnected:
                print("[Server] Client disconnected")
                self.clients.remove(c)
                try:
                    c.close()
                except:
                    pass

class GCIBackend:
    def __init__(self, host="127.0.0.1", port=10088, stagger_updates=True, coalition="blue", protocol="tcp"):
        self.host = host
        self.port = port
        self.stagger_updates = stagger_updates
        self.coalition = coalition.lower()
        self.protocol = protocol.lower() # "tcp" or "udp"
        self.sock = None
        self.connected = False
        
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

    def set_coalition(self, coalition):
        with self.lock:
            self.coalition = coalition.lower()
            self.friendlies.clear()
            self.hostiles.clear()
            self.pending_updates.clear()

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
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

    def send_command(self, cmd_dict):
        """傳送控制指令至 DCS Lua Exporter (UDP 10089 端口)"""
        try:
            cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            payload = json.dumps(cmd_dict).encode('utf-8')
            target_ip = self.host if hasattr(self, 'host') and self.host else "127.0.0.1"
            cmd_sock.sendto(payload, (target_ip, 10089))
            cmd_sock.close()
            return True
        except Exception as e:
            print(f"[Backend] Failed to send command to DCS: {e}")
            return False

    def _listen_loop(self):
        if self.protocol == "udp":
            self._listen_udp()
        else:
            self._listen_tcp()

    def _listen_udp(self):
        print(f"GCI Backend listening on Direct UDP port {self.port}")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", self.port))
        self.sock.settimeout(1.0)
        self.connected = True
        
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65536)
                json_str = data.decode('utf-8')
                self.parse_telemetry(json_str)
            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    print(f"UDP recv error: {e}")
                    
        if self.sock:
            self.sock.close()

    def _listen_tcp(self):
        print(f"GCI Backend connecting to TCP {self.host}:{self.port}")
        buffer = b""
        
        while self.running:
            if not self.connected:
                if not self.running:
                    break
                try:
                    if self.sock:
                        self.sock.close()
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.settimeout(2.0)
                    self.sock.connect((self.host, self.port))
                    self.connected = True
                    print(f"Connected to {self.host}:{self.port}")
                except Exception as e:
                    time.sleep(1)
                    continue
                    
            try:
                chunk = self.sock.recv(65536)
                if not chunk:
                    raise ConnectionError("Server disconnected")
                buffer += chunk
                
                # Parse framing: "LENGTH\nJSON_PAYLOAD"
                while b'\n' in buffer:
                    header, rest = buffer.split(b'\n', 1)
                    try:
                        expected_len = int(header)
                    except ValueError:
                        # Malformed stream, drop buffer
                        buffer = b""
                        break
                        
                    if len(rest) >= expected_len:
                        payload = rest[:expected_len]
                        buffer = rest[expected_len:]
                        
                        json_str = payload.decode('utf-8')
                        self.parse_telemetry(json_str)
                    else:
                        break # Not enough data yet
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Connection lost: {e}")
                    self.connected = False
        
        if self.sock:
            self.sock.close()
            
        with open("backend.log", "a") as f:
            f.write(f"[{time.time()}] Thread stopped.\n")

    def parse_telemetry(self, json_str):
        with open("backend.log", "a") as f:
            f.write(f"[{time.time()}] Received payload of length {len(json_str)}\n")
        
        telemetry = json.loads(json_str)
        current_time = time.time()
        
        c = getattr(self, 'coalition', 'blue').lower()
        # 判斷是否為分拆陣營封包 (如果含有 blue 或 red 的 key)
        has_split_coalition = "blue" in telemetry or "red" in telemetry
        
        if has_split_coalition:
            if c in telemetry and isinstance(telemetry[c], dict):
                side_data = telemetry[c]
            else:
                # 封包為另一陣營的分拆封包，丟棄不解析
                return
        else:
            # 舊版單一陣營或測試用扁平封包，直接使用根節點
            side_data = telemetry
        
        with self.lock:
            # We do NOT clear self.friendlies and self.hostiles here anymore
            # Updates are placed into a pending queue to stagger their UI rendering
            
            for f in side_data.get("friendlies", []):
                uid = f.get("unit_name")
                self.last_seen_time[uid] = current_time
                if uid in self.pending_updates:
                    old_apply_time, _, _ = self.pending_updates[uid]
                    self.pending_updates[uid] = (old_apply_time, True, f)
                else:
                    delay = self._get_stagger_delay(uid)
                    self.pending_updates[uid] = (current_time + delay, True, f)
                
            for h in side_data.get("hostiles", []):
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
                    is_ground = data.get("category") in [2, 3] # Group.Category.GROUND (2), SHIP (3)
                    
                    if not is_ground:
                        if uid not in self.history:
                            self.history[uid] = []
                        data['history'] = list(self.history[uid])
                    else:
                        data['history'] = []

                    if is_friendly:
                        self.friendlies[uid] = data
                    else:
                        self.hostiles[uid] = data
                        
                    if not is_ground:
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
