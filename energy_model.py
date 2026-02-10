"""
Energy Model Module - Energy consumption and battery management
"""

from config import (
    ENERGY_ENCRYPTION, ENERGY_RE_ENCRYPTION, ENERGY_TRANSMISSION,
    ENERGY_DUMMY_TRAFFIC, ENERGY_RECEPTION,
    LOW_BATTERY_THRESHOLD, CRITICAL_BATTERY_THRESHOLD, MISSION_CONFIG
)


class EnergyModel:
    """Manages energy consumption calculations for drone operations"""
    
    def __init__(self):
        self.base_costs = {
            "encryption": ENERGY_ENCRYPTION,
            "re_encryption": ENERGY_RE_ENCRYPTION,
            "transmission": ENERGY_TRANSMISSION,
            "dummy_traffic": ENERGY_DUMMY_TRAFFIC,
            "reception": ENERGY_RECEPTION
        }
        
    def calculate_encryption_cost(self, rounds: int = 1) -> float:
        """Calculate energy cost for encryption with multiple rounds"""
        base = self.base_costs["encryption"]
        re_encrypt = self.base_costs["re_encryption"] * max(0, rounds - 1)
        return base + re_encrypt
    
    def calculate_transmission_cost(self, hops: int = 1) -> float:
        """Calculate energy cost for multi-hop transmission"""
        return self.base_costs["transmission"] * hops
    
    def calculate_relay_cost(self, encryption_rounds: int = 1) -> float:
        """Calculate total energy cost for acting as a relay"""
        return (self.base_costs["reception"] + 
                self.base_costs["re_encryption"] * encryption_rounds +
                self.base_costs["transmission"])
    
    def calculate_dummy_cost(self) -> float:
        """Calculate energy cost for dummy traffic generation"""
        return self.base_costs["dummy_traffic"]
    
    def calculate_message_cost(self, mission_phase: str, is_sender: bool = True) -> float:
        """
        Calculate total energy cost for a message based on mission phase.
        
        Args:
            mission_phase: Current mission phase (PATROL, SURVEILLANCE, THREAT)
            is_sender: True if drone is the message sender, False if relay
        """
        config = MISSION_CONFIG[mission_phase]
        
        if is_sender:
            # Sender pays for encryption and initial transmission
            cost = self.calculate_encryption_cost(config["encryption_rounds"])
            cost += self.base_costs["transmission"]
        else:
            # Relay pays for re-encryption and retransmission
            cost = self.calculate_relay_cost(config["encryption_rounds"])
            
        return cost
    
    def get_low_battery_threshold(self) -> float:
        """Return low battery threshold"""
        return LOW_BATTERY_THRESHOLD
    
    def get_critical_threshold(self) -> float:
        """Return critical battery threshold"""
        return CRITICAL_BATTERY_THRESHOLD
    
    def is_low_battery(self, battery_level: float) -> bool:
        """Check if battery level is below low threshold"""
        return battery_level < LOW_BATTERY_THRESHOLD
    
    def is_critical_battery(self, battery_level: float) -> bool:
        """Check if battery level is critically low"""
        return battery_level < CRITICAL_BATTERY_THRESHOLD
    
    def get_battery_efficiency_factor(self, battery_level: float) -> float:
        """
        Calculate efficiency factor based on battery level.
        Lower battery = lower efficiency = higher effective cost.
        """
        if battery_level >= 80:
            return 1.0
        elif battery_level >= 50:
            return 1.1
        elif battery_level >= LOW_BATTERY_THRESHOLD:
            return 1.25
        else:
            return 1.5  # Critical battery penalty
        
    def estimate_remaining_operations(self, battery_level: float, mission_phase: str) -> int:
        """Estimate how many more message operations a drone can perform"""
        avg_cost = self.calculate_message_cost(mission_phase, is_sender=True)
        usable_battery = max(0, battery_level - CRITICAL_BATTERY_THRESHOLD)
        return int(usable_battery / avg_cost) if avg_cost > 0 else 0


class BatteryManager:
    """Manages battery updates and tracking for drones"""
    
    def __init__(self, energy_model: EnergyModel = None):
        self.energy_model = energy_model or EnergyModel()
        self.consumption_history = []
        
    def apply_energy_cost(self, drone, cost: float, operation: str = "unknown") -> bool:
        """
        Apply energy cost to a drone.
        Returns True if successful, False if insufficient battery.
        """
        efficiency = self.energy_model.get_battery_efficiency_factor(drone.battery_level)
        actual_cost = cost * efficiency
        
        success = drone.consume_energy(actual_cost)
        
        self.consumption_history.append({
            "drone_id": drone.drone_id,
            "operation": operation,
            "base_cost": cost,
            "actual_cost": actual_cost,
            "remaining_battery": drone.battery_level,
            "success": success
        })
        
        return success
    
    def get_consumption_stats(self):
        """Get statistics on energy consumption"""
        if not self.consumption_history:
            return {"total": 0, "count": 0, "average": 0}
            
        total = sum(h["actual_cost"] for h in self.consumption_history)
        count = len(self.consumption_history)
        return {
            "total": total,
            "count": count,
            "average": total / count if count > 0 else 0
        }
