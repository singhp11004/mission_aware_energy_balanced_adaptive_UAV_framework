"""
UAV Swarm Module - Drone class and network topology
"""

import random
import networkx as nx
from typing import Dict, List, Optional, Tuple
from config import (
    NUM_DRONES, COMMAND_SERVER_ID, COMMUNICATION_RANGE,
    INITIAL_BATTERY, MissionPhase
)


class Drone:
    """Represents a single UAV drone in the swarm"""
    
    def __init__(self, drone_id: int):
        self.drone_id = drone_id
        self.battery_level = INITIAL_BATTERY
        self.mission_state = MissionPhase.PATROL
        self.relay_usage_count = 0
        self.cooldown_timer = 0
        self.position = (random.random(), random.random())  # 2D position
        self.is_active = True
        self.messages_sent = 0
        self.messages_relayed = 0
        
    def consume_energy(self, amount: float) -> bool:
        """
        Consume energy from battery.
        Returns True if successful, False if insufficient battery.
        """
        if self.battery_level >= amount:
            self.battery_level -= amount
            self.battery_level = max(0, self.battery_level)
            return True
        return False
    
    def update_cooldown(self):
        """Decrease cooldown timer by 1 if active"""
        if self.cooldown_timer > 0:
            self.cooldown_timer -= 1
            
    def set_as_relay(self, cooldown_duration: int):
        """Mark drone as recently used relay"""
        self.relay_usage_count += 1
        self.cooldown_timer = cooldown_duration
        
    def is_available(self, min_battery: float = 10.0) -> bool:
        """Check if drone can participate in routing"""
        return self.is_active and self.battery_level >= min_battery
    
    def __repr__(self):
        return f"Drone({self.drone_id}, battery={self.battery_level:.1f}%, state={self.mission_state})"


class CommandServer:
    """Central command server for the swarm"""
    
    def __init__(self):
        self.server_id = COMMAND_SERVER_ID
        self.received_messages: List[Dict] = []
        self.position = (0.5, 0.5)  # Center position
        
    def receive_message(self, message: Dict):
        """Record received message"""
        self.received_messages.append(message)


class UAVSwarm:
    """Manages the UAV swarm network topology and communication"""
    
    def __init__(self, num_drones: int = NUM_DRONES):
        self.num_drones = num_drones
        self.drones: Dict[int, Drone] = {}
        self.command_server = CommandServer()
        self.network: Optional[nx.Graph] = None
        self.current_mission_phase = MissionPhase.PATROL
        self.round_number = 0
        
        self._initialize_drones()
        self._build_network_topology()
        
    def _initialize_drones(self):
        """Create all drones in the swarm"""
        for i in range(self.num_drones):
            self.drones[i] = Drone(drone_id=i)
            
    def _build_network_topology(self):
        """Build NetworkX random geometric graph for swarm topology"""
        # Create positions dictionary including command server
        positions = {i: drone.position for i, drone in self.drones.items()}
        positions[COMMAND_SERVER_ID] = self.command_server.position
        
        # Create random geometric graph
        self.network = nx.random_geometric_graph(
            self.num_drones + 1,  # +1 for command server
            COMMUNICATION_RANGE
        )
        
        # Relabel nodes to match our IDs
        mapping = {i: i if i < self.num_drones else COMMAND_SERVER_ID 
                   for i in range(self.num_drones + 1)}
        self.network = nx.relabel_nodes(self.network, mapping)
        
        # Store positions in graph
        nx.set_node_attributes(self.network, positions, 'pos')
        
        # Ensure connectivity to command server
        self._ensure_server_connectivity()
        
    def _ensure_server_connectivity(self):
        """Ensure at least some drones can reach command server"""
        server_neighbors = list(self.network.neighbors(COMMAND_SERVER_ID))
        if len(server_neighbors) < 5:
            # Add edges to closest drones
            drone_distances = []
            for drone_id, drone in self.drones.items():
                dist = ((drone.position[0] - 0.5)**2 + (drone.position[1] - 0.5)**2)**0.5
                drone_distances.append((drone_id, dist))
            drone_distances.sort(key=lambda x: x[1])
            
            for drone_id, _ in drone_distances[:10]:
                if not self.network.has_edge(drone_id, COMMAND_SERVER_ID):
                    self.network.add_edge(drone_id, COMMAND_SERVER_ID)
                    
    def get_neighbors(self, node_id) -> List:
        """Get neighboring nodes for a given node"""
        if node_id in self.network:
            return list(self.network.neighbors(node_id))
        return []
    
    def get_path_to_server(self, source_id: int) -> Optional[List]:
        """Find path from source drone to command server"""
        try:
            return nx.shortest_path(self.network, source_id, COMMAND_SERVER_ID)
        except nx.NetworkXNoPath:
            return None
        
    def get_available_relays(self, exclude_ids: List = None) -> List[Drone]:
        """Get list of drones available for relay duty"""
        exclude_ids = exclude_ids or []
        return [
            drone for drone_id, drone in self.drones.items()
            if drone.is_available() and drone_id not in exclude_ids
        ]
    
    def set_mission_phase(self, phase: str):
        """Update mission phase for all drones"""
        self.current_mission_phase = phase
        for drone in self.drones.values():
            drone.mission_state = phase
            
    def update_round(self):
        """Update swarm state for new round"""
        self.round_number += 1
        for drone in self.drones.values():
            drone.update_cooldown()
            
    def get_active_drones(self) -> List[Drone]:
        """Get list of currently active drones"""
        return [d for d in self.drones.values() if d.is_available()]
    
    def get_battery_stats(self) -> Dict:
        """Calculate battery statistics across swarm"""
        batteries = [d.battery_level for d in self.drones.values()]
        return {
            "mean": sum(batteries) / len(batteries),
            "min": min(batteries),
            "max": max(batteries),
            "active_count": len(self.get_active_drones())
        }
    
    def get_swarm_lifetime(self) -> int:
        """Return current round number as swarm lifetime indicator"""
        return self.round_number
    
    def is_operational(self, min_active_ratio: float = 0.5) -> bool:
        """Check if swarm is still operational"""
        active = len(self.get_active_drones())
        return active >= (self.num_drones * min_active_ratio)
