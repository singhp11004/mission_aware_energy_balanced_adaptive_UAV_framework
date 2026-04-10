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
    """Central command server for the swarm — with processing & ACK tracking."""

    def __init__(self):
        self.server_id = COMMAND_SERVER_ID
        self.received_messages: List[Dict] = []
        self.position = (0.5, 0.5)  # Center position

        # ── stats ──
        self.stats = {
            "received": 0,
            "processed": 0,
            "integrity_ok": 0,
            "integrity_fail": 0,
            "acks_sent": 0,
            "dropped": 0,          # from jamming / interception
        }
        self.round_stats: Dict[int, Dict] = {}   # per-round breakdown
        self.ack_log: List[Dict] = []             # ACK records

    def receive_message(self, message: Dict, round_num: int = 0):
        """Record received message, process it, and prepare ACK."""
        self.received_messages.append(message)
        self.stats["received"] += 1

        # Integrity check (simulation: fail if re_encrypted flag missing
        # on messages that went through relays)
        integrity_ok = True
        if message.get("hop_count", 0) > 0:
            # Simulate: 2% random integrity failure
            integrity_ok = random.random() > 0.02
        if message.get("is_dummy", False):
            integrity_ok = True  # Dummy always passes (no real payload)

        if integrity_ok:
            self.stats["processed"] += 1
            self.stats["integrity_ok"] += 1
        else:
            self.stats["integrity_fail"] += 1

        # Send ACK back to sender
        ack = {
            "msg_id": message.get("message_id", "?"),
            "sender_id": message.get("sender_id"),
            "round": round_num,
            "status": "ACK" if integrity_ok else "NACK",
        }
        self.ack_log.append(ack)
        self.stats["acks_sent"] += 1

        # Per-round tracking
        rs = self.round_stats.setdefault(round_num, {
            "received": 0, "processed": 0,
            "integrity_fail": 0, "acks": 0, "dropped": 0,
        })
        rs["received"] += 1
        rs["processed"] += int(integrity_ok)
        rs["integrity_fail"] += int(not integrity_ok)
        rs["acks"] += 1

        return {"status": "ACK" if integrity_ok else "NACK", "integrity_ok": integrity_ok}

    def record_drop(self, round_num: int = 0):
        """Record a message that was dropped (jammed / intercepted)."""
        self.stats["dropped"] += 1
        rs = self.round_stats.setdefault(round_num, {
            "received": 0, "processed": 0,
            "integrity_fail": 0, "acks": 0, "dropped": 0,
        })
        rs["dropped"] += 1


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
        
        self.update_edge_weights()

    def update_edge_weights(self):
        """Update edge weights dynamically based on distance to simulate energy cost W = (d^2) / battery."""
        pos = nx.get_node_attributes(self.network, 'pos')
        for u, v in self.network.edges():
            pos_u = pos[u]
            pos_v = pos[v]
            
            # calculate distance squared
            d_sq = (pos_u[0] - pos_v[0])**2 + (pos_u[1] - pos_v[1])**2
            
            # approximate transmission power P cost factor
            P_cost = max(0.0001, d_sq * 100) # scale up slightly
            
            # battery factor: lower battery means higher perceived cost to relay
            battery_u = self.drones[u].battery_level if u in self.drones else 100
            battery_v = self.drones[v].battery_level if v in self.drones else 100
            
            battery_factor = max(1.0, (battery_u + battery_v) / 2)
            weight = P_cost / (battery_factor / 100.0)
            
            self.network[u][v]['weight'] = weight
        
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
        """Update swarm state for new round: timers, movement, and weights"""
        self.round_number += 1
        pos = nx.get_node_attributes(self.network, 'pos')
        new_pos = {}
        for drone in self.drones.values():
            drone.update_cooldown()
            # Random movement jitter
            x, y = drone.position
            nx_val, ny_val = x + random.uniform(-0.02, 0.02), y + random.uniform(-0.02, 0.02)
            drone.position = (max(0.0, min(1.0, nx_val)), max(0.0, min(1.0, ny_val)))
            new_pos[drone.drone_id] = drone.position
            
        new_pos[COMMAND_SERVER_ID] = self.command_server.position
        nx.set_node_attributes(self.network, new_pos, 'pos')
        self.update_edge_weights()
            
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

    # ─────────────────── Z-MAPS extensions ───────────────────

    def get_neighbors_with_metrics(self, drone_id: int) -> List[Dict]:
        """
        Return neighbor drone IDs with their current battery and queue depth.
        Used by the IPPO-DM environment for observation building.
        """
        neighbors = self.get_neighbors(drone_id)
        result = []
        for nid in neighbors:
            if isinstance(nid, int) and nid in self.drones:
                d = self.drones[nid]
                result.append({
                    "drone_id": nid,
                    "battery": d.battery_level,
                    "cooldown": d.cooldown_timer,
                    "relay_count": d.relay_usage_count,
                    "is_available": d.is_available(),
                    "queue_depth": getattr(d, "_queue_depth", 0),
                })
        return result

    def get_drone_state_vector(self, drone_id: int, max_neighbors: int = 10) -> List[float]:
        """
        Build a fixed-size observation vector for a single drone.
        Compatible with the IPPO agent's obs_dim.
        """
        if drone_id not in self.drones:
            return [0.0] * 32

        drone = self.drones[drone_id]
        obs = [0.0] * 32

        # Own state
        obs[0] = drone.battery_level / 100.0
        obs[1] = min(drone.cooldown_timer / 10.0, 1.0)
        obs[2] = min(drone.relay_usage_count / 50.0, 1.0)

        # Neighbor batteries
        neighbors = self.get_neighbors_with_metrics(drone_id)
        for i, n in enumerate(neighbors[:max_neighbors]):
            obs[3 + i] = n["battery"] / 100.0

        # Active neighbor count
        obs[20] = min(len(neighbors) / max_neighbors, 1.0)

        return obs
