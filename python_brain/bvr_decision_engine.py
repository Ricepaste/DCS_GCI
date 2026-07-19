import py_trees
from py_trees.common import Status

class CheckThreat(py_trees.behaviour.Behaviour):
    def __init__(self, name, group_name, state_matrix):
        super().__init__(name)
        self.group_name = group_name
        self.state_matrix = state_matrix

    def update(self):
        units = self.state_matrix.get_group_state(self.group_name)
        if not units:
            return Status.FAILURE
        
        lead = units[0]
        if lead.is_locked:
            return Status.SUCCESS
        return Status.FAILURE

class ExecutePump(py_trees.behaviour.Behaviour):
    def __init__(self, name, group_name, command_queue):
        super().__init__(name)
        self.group_name = group_name
        self.command_queue = command_queue

    def update(self):
        self.command_queue.append({
            "cmd": "pump",
            "group": self.group_name
        })
        return Status.SUCCESS

class CheckOffensive(py_trees.behaviour.Behaviour):
    def __init__(self, name, group_name, state_matrix):
        super().__init__(name)
        self.group_name = group_name
        self.state_matrix = state_matrix

    def update(self):
        units = self.state_matrix.get_group_state(self.group_name)
        if not units:
            return Status.FAILURE
        
        lead = units[0]
        if lead.has_missile_in_air:
            return Status.SUCCESS
        return Status.FAILURE

class ExecuteCrank(py_trees.behaviour.Behaviour):
    def __init__(self, name, group_name, command_queue):
        super().__init__(name)
        self.group_name = group_name
        self.command_queue = command_queue

    def update(self):
        self.command_queue.append({
            "cmd": "crank",
            "group": self.group_name,
            "direction": "right" 
        })
        return Status.SUCCESS

def build_bvr_tree(group_name, state_matrix, command_queue):
    """
    Builds the behavior tree for a single AI Group.
    Priority: Defend (Pump) -> Support Missile (Crank) -> Default (Idle/Engage)
    """
    root = py_trees.composites.Selector(name=f"BVR_Decision_{group_name}", memory=False)
    
    # Branch 1: Defensive (If Locked -> Pump)
    defensive_sequence = py_trees.composites.Sequence(name="Defensive_Branch", memory=False)
    check_threat = CheckThreat("Check_Threat", group_name, state_matrix)
    pump = ExecutePump("Pump", group_name, command_queue)
    defensive_sequence.add_children([check_threat, pump])
    
    # Branch 2: Offensive/Support (If Missile in air -> Crank)
    offensive_sequence = py_trees.composites.Sequence(name="Offensive_Branch", memory=False)
    check_offensive = CheckOffensive("Check_Offensive", group_name, state_matrix)
    crank = ExecuteCrank("Crank", group_name, command_queue)
    offensive_sequence.add_children([check_offensive, crank])
    
    # Default: Idle/Success
    idle = py_trees.behaviours.Success(name="Idle_State")
    
    root.add_children([defensive_sequence, offensive_sequence, idle])
    return root
