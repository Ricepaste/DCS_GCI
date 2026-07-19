import json

class UnitState:
    def __init__(self, data):
        self.name = data.get("name", "Unknown")
        self.x = data.get("x", 0.0)
        self.z = data.get("z", 0.0) # DCS uses x for North/South, z for East/West
        self.y = data.get("y", 0.0) # Altitude
        self.heading = data.get("heading", 0.0)
        self.speed = data.get("speed", 0.0)
        self.is_locked = data.get("is_locked", False)
        self.has_missile_in_air = data.get("has_missile_in_air", False)

class BattlefieldState:
    def __init__(self):
        self.ai_groups = {} # Dictionary of group_name -> list of UnitState
        self.threats = {}
        
    def update_from_json(self, json_str):
        try:
            data = json.loads(json_str)
            group_name = data.get("group_name")
            if not group_name:
                return
            
            units = []
            for u_data in data.get("units", []):
                units.append(UnitState(u_data))
                
            self.ai_groups[group_name] = units
        except Exception as e:
            print(f"Error parsing telemetry: {e}")
            
    def get_group_state(self, group_name):
        return self.ai_groups.get(group_name, [])
