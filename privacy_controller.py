"""
Privacy Controller Module - Mission-aware privacy scaling and routing logic
"""

import random
import time
from typing import Dict, List, Tuple
from config import MissionPhase, MISSION_CONFIG


class PrivacyController:
    """Controls privacy parameters based on mission phase"""
    
    def __init__(self):
        self.current_phase = MissionPhase.PATROL
        self.phase_history: List[Tuple[float, str]] = []
        self._update_phase_history()
        
    def _update_phase_history(self):
        """Record phase change with timestamp"""
        self.phase_history.append((time.time(), self.current_phase))
        
    def set_phase(self, phase: str):
        """Update current mission phase"""
        if phase in [MissionPhase.PATROL, MissionPhase.SURVEILLANCE, MissionPhase.THREAT]:
            self.current_phase = phase
            self._update_phase_history()
            
    def get_routing_depth(self) -> int:
        """Get required routing depth (number of relay hops) for current phase"""
        return MISSION_CONFIG[self.current_phase]["routing_depth"]
    
    def get_dummy_rate(self) -> float:
        """Get dummy traffic injection rate for current phase"""
        return MISSION_CONFIG[self.current_phase]["dummy_rate"]
    
    def get_timing_jitter(self) -> int:
        """Get timing jitter (randomization) in milliseconds"""
        return MISSION_CONFIG[self.current_phase]["timing_jitter_ms"]
    
    def get_encryption_rounds(self) -> int:
        """Get number of encryption layers for current phase"""
        return MISSION_CONFIG[self.current_phase]["encryption_rounds"]
    
    def get_phase_config(self) -> Dict:
        """Get full configuration for current phase"""
        return MISSION_CONFIG[self.current_phase].copy()
    
    def should_inject_dummy(self) -> bool:
        """Probabilistically decide whether to inject dummy traffic"""
        return random.random() < self.get_dummy_rate()
    
    def apply_timing_jitter(self) -> float:
        """Calculate random delay in seconds for timing obfuscation"""
        jitter_ms = random.uniform(0, self.get_timing_jitter())
        return jitter_ms / 1000.0  # Convert to seconds
    
    def get_privacy_level(self) -> int:
        """Return numeric privacy level (1-3) for current phase"""
        levels = {
            MissionPhase.PATROL: 1,
            MissionPhase.SURVEILLANCE: 2,
            MissionPhase.THREAT: 3
        }
        return levels[self.current_phase]


class RoutingPolicy:
    """Defines routing policies based on mission requirements"""
    
    def __init__(self, privacy_controller: PrivacyController):
        self.privacy = privacy_controller
        
    def calculate_required_hops(self, source_battery: float, 
                                 distance_to_target: int = 1) -> int:
        """
        Calculate required relay hops based on privacy needs and battery.
        
        Args:
            source_battery: Battery level of source drone
            distance_to_target: Network distance to command server
        """
        base_hops = self.privacy.get_routing_depth()
        
        # Reduce hops if battery is low
        if source_battery < 30:
            base_hops = max(1, base_hops - 1)
        elif source_battery < 15:
            base_hops = 1  # Emergency direct routing
            
        # Ensure we have enough hops for the distance
        return max(base_hops, distance_to_target)
    
    def should_use_multipath(self) -> bool:
        """Determine if multipath routing should be used (higher privacy)"""
        return self.privacy.current_phase == MissionPhase.THREAT
    
    def get_path_redundancy(self) -> int:
        """Get number of redundant paths to use"""
        if self.privacy.current_phase == MissionPhase.THREAT:
            return 2
        return 1


class DummyTrafficGenerator:
    """Generates dummy traffic for traffic analysis resistance"""
    
    def __init__(self, privacy_controller: PrivacyController):
        self.privacy = privacy_controller
        self.dummy_count = 0
        self.pattern_types = ["random", "periodic", "burst"]
        
    def generate_dummy_schedule(self, num_real_messages: int) -> List[bool]:
        """
        Generate a schedule indicating when to inject dummy messages.
        Returns a list of booleans (True = inject dummy after this position)
        """
        schedule = []
        rate = self.privacy.get_dummy_rate()
        
        for _ in range(num_real_messages):
            if random.random() < rate:
                schedule.append(True)
                self.dummy_count += 1
            else:
                schedule.append(False)
                
        return schedule
    
    def get_dummy_payload_size(self) -> int:
        """Get size of dummy payload to match real message sizes"""
        # Return size in bytes - should match typical message size
        base_size = 64
        variation = random.randint(-16, 16)
        return base_size + variation
    
    def get_statistics(self) -> Dict:
        """Return dummy traffic statistics"""
        return {
            "total_dummy_messages": self.dummy_count,
            "current_rate": self.privacy.get_dummy_rate()
        }


class MissionManager:
    """Manages mission phase transitions"""
    
    def __init__(self, privacy_controller: PrivacyController):
        self.privacy = privacy_controller
        self.phase_sequence = [
            MissionPhase.PATROL,
            MissionPhase.SURVEILLANCE,
            MissionPhase.THREAT,
            MissionPhase.SURVEILLANCE,
            MissionPhase.PATROL
        ]
        self.current_index = 0
        
    def transition_to_next_phase(self):
        """Move to next phase in sequence"""
        self.current_index = (self.current_index + 1) % len(self.phase_sequence)
        new_phase = self.phase_sequence[self.current_index]
        self.privacy.set_phase(new_phase)
        return new_phase
    
    def escalate_to_threat(self):
        """Emergency escalation to THREAT phase"""
        self.privacy.set_phase(MissionPhase.THREAT)
        # Find THREAT in sequence
        for i, phase in enumerate(self.phase_sequence):
            if phase == MissionPhase.THREAT:
                self.current_index = i
                break
                
    def deescalate_to_patrol(self):
        """Return to safe PATROL phase"""
        self.privacy.set_phase(MissionPhase.PATROL)
        self.current_index = 0
        
    def get_phase_duration_factor(self) -> float:
        """Get expected duration factor for current phase"""
        factors = {
            MissionPhase.PATROL: 1.0,
            MissionPhase.SURVEILLANCE: 0.7,
            MissionPhase.THREAT: 0.5  # Shorter, high-intensity
        }
        return factors[self.privacy.current_phase]


# ─────────────────────── Z-MAPS Extensions ───────────────────────

# Multipath toggle per legacy phase
PHASE_MULTIPATH = {
    MissionPhase.PATROL: False,
    MissionPhase.SURVEILLANCE: True,
    MissionPhase.THREAT: True,
}


def should_use_multipath(phase: str) -> bool:
    """Check if multipath routing should be active for the given phase."""
    return PHASE_MULTIPATH.get(phase, False)


# Semantic priority for data content (keyword-based heuristic)
_PRIORITY_KEYWORDS = {
    "target": 0.95,
    "hostile": 0.90,
    "alert": 0.90,
    "emergency": 0.95,
    "threat": 0.85,
    "video": 0.60,
    "image": 0.55,
    "surveillance": 0.65,
    "battery": 0.30,
    "status": 0.25,
    "telemetry": 0.35,
    "position": 0.30,
}


def get_priority_for_data_type(payload: str, phase: str = "PATROL") -> float:
    """
    Assign a priority score (0.0–1.0) to a payload based on its content
    and the current mission phase.

    Used by the Prioritization layer for backward-compatible code paths.
    """
    lower = payload.lower()
    base = 0.3  # default

    for keyword, score in _PRIORITY_KEYWORDS.items():
        if keyword in lower:
            base = max(base, score)
            break

    # Phase amplifier
    phase_amp = {
        MissionPhase.PATROL: 1.0,
        MissionPhase.SURVEILLANCE: 1.15,
        MissionPhase.THREAT: 1.30,
    }
    return min(1.0, base * phase_amp.get(phase, 1.0))
