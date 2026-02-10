"""
Relay Selector Module - Energy-weighted probabilistic relay selection
"""

import random
from typing import List, Dict, Optional, Tuple
from config import COOLDOWN_PENALTY, COOLDOWN_DURATION, BATTERY_WEIGHT


class RelaySelector:
    """Selects relay nodes based on energy-weighted probabilities"""
    
    def __init__(self):
        self.cooldown_penalty = COOLDOWN_PENALTY
        self.cooldown_duration = COOLDOWN_DURATION
        self.battery_weight = BATTERY_WEIGHT
        self.selection_history: List[Dict] = []
        
    def calculate_weight(self, drone) -> float:
        """
        Calculate selection weight for a drone based on:
        - Battery level (higher = more weight)
        - Cooldown status (recently used = penalty)
        
        Args:
            drone: Drone object with battery_level and cooldown_timer
        """
        # Base weight from battery level (normalized to 0-1)
        battery_score = drone.battery_level / 100.0
        
        # Apply cooldown penalty if recently used
        if drone.cooldown_timer > 0:
            cooldown_factor = 1 - (self.cooldown_penalty * 
                                   (drone.cooldown_timer / self.cooldown_duration))
        else:
            cooldown_factor = 1.0
            
        # Combine factors
        weight = (battery_score * self.battery_weight) * cooldown_factor
        
        # Ensure non-negative weight
        return max(0.01, weight)  # Minimum weight to avoid zero probability
    
    def normalize_probabilities(self, weights: List[float]) -> List[float]:
        """Convert weights to normalized probability distribution"""
        total = sum(weights)
        if total == 0:
            # Equal probability if all weights are zero
            return [1.0 / len(weights)] * len(weights)
        return [w / total for w in weights]
    
    def select_relay(self, candidates: List, exclude_ids: List[int] = None) -> Optional[object]:
        """
        Select a single relay node from candidates using weighted random selection.
        
        Args:
            candidates: List of Drone objects
            exclude_ids: List of drone IDs to exclude
        """
        exclude_ids = exclude_ids or []
        
        # Filter out excluded drones
        available = [d for d in candidates if d.drone_id not in exclude_ids 
                     and d.battery_level > 10]
        
        if not available:
            return None
            
        # Calculate weights
        weights = [self.calculate_weight(d) for d in available]
        probabilities = self.normalize_probabilities(weights)
        
        # Weighted random selection
        selected = random.choices(available, weights=probabilities, k=1)[0]
        
        # Record selection
        self._record_selection(selected, available, weights)
        
        return selected
    
    def select_relay_chain(self, candidates: List, num_relays: int,
                           source_id: int = None) -> List:
        """
        Select multiple relay nodes for multi-hop routing.
        
        Args:
            candidates: List of Drone objects
            num_relays: Number of relays needed
            source_id: Source drone ID to exclude
        """
        exclude_ids = [source_id] if source_id is not None else []
        chain = []
        
        for _ in range(num_relays):
            relay = self.select_relay(candidates, exclude_ids)
            if relay is None:
                break  # Not enough candidates
            chain.append(relay)
            exclude_ids.append(relay.drone_id)
            
        return chain
    
    def _record_selection(self, selected, candidates: List, weights: List[float]):
        """Record relay selection for analysis"""
        self.selection_history.append({
            "selected_id": selected.drone_id,
            "selected_battery": selected.battery_level,
            "candidate_count": len(candidates),
            "weights": weights.copy()
        })
        
    def get_selection_stats(self) -> Dict:
        """Get statistics on relay selections"""
        if not self.selection_history:
            return {"total_selections": 0}
            
        # Count selections per drone
        drone_counts: Dict[int, int] = {}
        for record in self.selection_history:
            drone_id = record["selected_id"]
            drone_counts[drone_id] = drone_counts.get(drone_id, 0) + 1
            
        return {
            "total_selections": len(self.selection_history),
            "unique_relays_used": len(drone_counts),
            "selection_distribution": drone_counts
        }


class LoadBalancer:
    """Ensures fair load distribution across relay nodes"""
    
    def __init__(self, selector: RelaySelector):
        self.selector = selector
        
    def calculate_gini_coefficient(self, values: List[float]) -> float:
        """
        Calculate Gini coefficient for fairness measurement.
        Lower value = more fair distribution.
        """
        if not values or sum(values) == 0:
            return 0.0
            
        n = len(values)
        sorted_values = sorted(values)
        
        # Calculate Gini
        numerator = sum((2 * i - n - 1) * x for i, x in enumerate(sorted_values, 1))
        denominator = n * sum(sorted_values)
        
        if denominator == 0:
            return 0.0
            
        return numerator / denominator
    
    def get_relay_fairness(self, drones: List) -> Dict:
        """
        Calculate fairness metrics for relay usage across drones.
        
        Args:
            drones: List of Drone objects
        """
        usage_counts = [d.relay_usage_count for d in drones]
        
        if not usage_counts or max(usage_counts) == 0:
            return {
                "gini": 0.0,
                "max_usage": 0,
                "min_usage": 0,
                "std_dev": 0.0
            }
            
        mean = sum(usage_counts) / len(usage_counts)
        variance = sum((x - mean) ** 2 for x in usage_counts) / len(usage_counts)
        std_dev = variance ** 0.5
        
        return {
            "gini": self.calculate_gini_coefficient(usage_counts),
            "max_usage": max(usage_counts),
            "min_usage": min(usage_counts),
            "mean_usage": mean,
            "std_dev": std_dev
        }
    
    def suggest_cooldown_adjustment(self, fairness_metrics: Dict) -> float:
        """
        Suggest cooldown penalty adjustment based on fairness.
        Higher Gini = increase penalty to encourage more fair distribution.
        """
        gini = fairness_metrics["gini"]
        
        if gini < 0.2:
            return 0.0  # Fair enough
        elif gini < 0.4:
            return 0.1  # Slight increase
        else:
            return 0.25  # Significant increase needed
