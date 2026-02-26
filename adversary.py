"""
Adversary Module - Traffic analysis and sender identification simulation
"""

import random
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from config import ADVERSARY_OBSERVATION_WINDOW, TRACE_SUCCESS_THRESHOLD


class TrafficObserver:
    """Simulates an adversary observing network traffic"""
    
    def __init__(self):
        self.observed_messages: List[Dict] = []
        self.node_activity: Dict[int, List] = defaultdict(list)
        self.observation_window = ADVERSARY_OBSERVATION_WINDOW
        
    def observe_message(self, message_data: Dict):
        """
        Record observation of a message in the network.
        
        Args:
            message_data: Dictionary with observable message attributes
        """
        observation = {
            "timestamp": message_data.get("timestamp"),
            "first_visible_node": message_data.get("relay_path", [None])[0] if message_data.get("relay_path") else None,
            "message_size": len(str(message_data.get("encrypted_content", ""))),
            "hop_count": message_data.get("hop_count", 0),
            "is_dummy": message_data.get("is_dummy", False)
        }
        
        self.observed_messages.append(observation)
        
        # Track node activity
        for node_id in message_data.get("relay_path", []):
            self.node_activity[node_id].append(observation["timestamp"])
            
    def get_recent_observations(self) -> List[Dict]:
        """Get observations within the sliding window"""
        return self.observed_messages[-self.observation_window:]
    
    def analyze_traffic_pattern(self, node_id: int) -> Dict:
        """Analyze traffic pattern for a specific node"""
        activity = self.node_activity.get(node_id, [])
        
        if len(activity) < 2:
            return {
                "message_count": len(activity),
                "avg_interval": 0,
                "regularity_score": 0
            }
            
        # Calculate intervals between messages
        intervals = [activity[i+1] - activity[i] for i in range(len(activity) - 1)]
        avg_interval = sum(intervals) / len(intervals) if intervals else 0
        
        # Calculate regularity (lower variance = more regular = more suspicious if timing not randomized)
        variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals) if intervals else 0
        regularity = 1 / (1 + variance)  # Normalized 0-1
        
        return {
            "message_count": len(activity),
            "avg_interval": avg_interval,
            "regularity_score": regularity
        }


class SenderEstimator:
    """Attempts to estimate the original sender through traffic correlation"""
    
    def __init__(self, observer: TrafficObserver):
        self.observer = observer
        self.estimation_attempts: List[Dict] = []
        
    def estimate_sender(self, message_data: Dict, all_drone_ids: List[int]) -> Tuple[Optional[int], float]:
        """
        Attempt to identify the original sender of a message.
        
        Returns:
            Tuple of (estimated_sender_id, confidence)
        """
        if message_data.get("is_dummy"):
            # Dummy messages should be unidentifiable
            random_guess = random.choice(all_drone_ids) if all_drone_ids else None
            return random_guess, 0.1  # Low confidence
            
        relay_path = message_data.get("relay_path", [])
        hop_count = message_data.get("hop_count", 0)
        
        # Simulation: Higher hops = exponentially harder to trace
        # 1 hop: 0.30 difficulty → ~70% traceable
        # 2 hops: 0.51 difficulty → ~49% traceable
        # 3 hops: 0.66 difficulty → ~34% traceable
        # 5 hops: 0.83 difficulty → ~17% base (near 0% with dummy traffic)
        base_difficulty = 1 - (0.7 ** hop_count) if hop_count > 0 else 0
        
        # Check if we can observe the first relay
        if relay_path:
            first_relay = relay_path[0]
            # Analyze first relay's activity pattern
            pattern = self.observer.analyze_traffic_pattern(first_relay)
            
            # High regularity might leak information, but impact is
            # diminished by deep routing (more hops = less leak)
            pattern_leak = pattern["regularity_score"] * 0.15 / (1 + hop_count * 0.3)
        else:
            pattern_leak = 0.3  # Direct transmission is very traceable
            
        # Calculate trace probability
        trace_prob = max(0, 1 - base_difficulty + pattern_leak)
        trace_prob = min(1.0, trace_prob)  # Cap at 1.0
        
        # Attempt to guess sender
        actual_sender = message_data.get("sender_id")
        if random.random() < trace_prob and actual_sender is not None:
            estimated = actual_sender  # Successful trace
            confidence = trace_prob
        else:
            # Failed trace - random guess
            estimated = random.choice(all_drone_ids) if all_drone_ids else None
            confidence = 1.0 / len(all_drone_ids) if all_drone_ids else 0
            
        success = (estimated == actual_sender and confidence >= TRACE_SUCCESS_THRESHOLD)
            
        self.estimation_attempts.append({
            "actual_sender": actual_sender,
            "estimated_sender": estimated,
            "confidence": confidence,
            "hop_count": hop_count,
            "success": success
        })
        
        return estimated, confidence
    
    def get_trace_success_rate(self) -> float:
        """Calculate overall trace success rate"""
        if not self.estimation_attempts:
            return 0.0
            
        successes = sum(1 for a in self.estimation_attempts if a["success"])
        return successes / len(self.estimation_attempts)
    
    def get_trace_stats_by_hops(self) -> Dict[int, float]:
        """Get trace success rate grouped by hop count"""
        hop_stats: Dict[int, List[bool]] = defaultdict(list)
        
        for attempt in self.estimation_attempts:
            hop_count = attempt["hop_count"]
            hop_stats[hop_count].append(attempt["success"])
            
        return {
            hops: sum(results) / len(results) if results else 0
            for hops, results in hop_stats.items()
        }


class Adversary:
    """Main adversary simulation class"""
    
    def __init__(self):
        self.observer = TrafficObserver()
        self.estimator = SenderEstimator(self.observer)
        self.success_threshold = TRACE_SUCCESS_THRESHOLD
        
    def observe_transmission(self, message_data: Dict):
        """Observe a message transmission"""
        self.observer.observe_message(message_data)
        
    def attempt_trace(self, message_data: Dict, all_drone_ids: List[int]) -> Dict:
        """
        Attempt to trace the sender of a message.
        
        Returns:
            Dictionary with trace attempt results
        """
        estimated, confidence = self.estimator.estimate_sender(message_data, all_drone_ids)
        actual = message_data.get("sender_id")
        
        return {
            "estimated_sender": estimated,
            "actual_sender": actual,
            "confidence": confidence,
            "success": estimated == actual and confidence >= self.success_threshold,
            "is_dummy": message_data.get("is_dummy", False)
        }
    
    def analyze_phase_vulnerability(self, phase_messages: Dict[str, List]) -> Dict[str, float]:
        """
        Analyze trace success rate for different mission phases.
        
        Args:
            phase_messages: Dictionary mapping phase names to message lists
        """
        phase_vulnerability = {}
        
        for phase, messages in phase_messages.items():
            if not messages:
                phase_vulnerability[phase] = 0.0
                continue
                
            # Calculate average trace success for this phase
            successes = sum(1 for m in messages if m.get("traced", False))
            phase_vulnerability[phase] = successes / len(messages)
            
        return phase_vulnerability
    
    def get_statistics(self) -> Dict:
        """Get comprehensive adversary statistics"""
        return {
            "total_observations": len(self.observer.observed_messages),
            "trace_attempts": len(self.estimator.estimation_attempts),
            "overall_success_rate": self.estimator.get_trace_success_rate(),
            "success_by_hops": self.estimator.get_trace_stats_by_hops()
        }
