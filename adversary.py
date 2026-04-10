"""
Adversary Module — Multi-vector attack simulation with comprehensive logging.

Attack types:
  • TRAFFIC_ANALYSIS  — correlation-based sender identification
  • REPLAY            — re-inject a previously captured message
  • INTERCEPTION      — capture and suppress a message in transit
  • JAMMING           — block message delivery via signal jamming
"""

import random
import time
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from config import ADVERSARY_OBSERVATION_WINDOW, TRACE_SUCCESS_THRESHOLD


# ───────────────────── Attack Types ─────────────────────

class AttackType:
    TRAFFIC_ANALYSIS = "TRAFFIC_ANALYSIS"
    REPLAY = "REPLAY"
    INTERCEPTION = "INTERCEPTION"
    JAMMING = "JAMMING"

ALL_ATTACK_TYPES = [
    AttackType.TRAFFIC_ANALYSIS,
    AttackType.REPLAY,
    AttackType.INTERCEPTION,
    AttackType.JAMMING,
]


# ───────────────────── Attack Log ─────────────────────

class AttackRecord:
    """Single attack attempt record."""

    __slots__ = (
        "round_num", "attack_type", "target_msg_id", "sender_id",
        "success", "confidence", "hop_count", "phase",
        "is_dummy_target", "timestamp",
    )

    def __init__(self, round_num: int, attack_type: str, target_msg_id: str,
                 sender_id, success: bool, confidence: float,
                 hop_count: int, phase: str, is_dummy_target: bool):
        self.round_num = round_num
        self.attack_type = attack_type
        self.target_msg_id = target_msg_id
        self.sender_id = sender_id
        self.success = success
        self.confidence = confidence
        self.hop_count = hop_count
        self.phase = phase
        self.is_dummy_target = is_dummy_target
        self.timestamp = time.time()

    def to_dict(self) -> Dict:
        return {k: getattr(self, k) for k in self.__slots__}


class AttackLog:
    """Stores and queries all attack records."""

    def __init__(self):
        self.records: List[AttackRecord] = []
        self._by_round: Dict[int, List[AttackRecord]] = defaultdict(list)

    def add(self, rec: AttackRecord):
        self.records.append(rec)
        self._by_round[rec.round_num].append(rec)

    # ── queries ──

    def for_round(self, round_num: int) -> List[AttackRecord]:
        return self._by_round.get(round_num, [])

    def success_rate(self, attack_type: str = None) -> float:
        recs = [r for r in self.records if not r.is_dummy_target]
        if attack_type:
            recs = [r for r in recs if r.attack_type == attack_type]
        if not recs:
            return 0.0
        return sum(1 for r in recs if r.success) / len(recs)

    def success_rate_by_type(self) -> Dict[str, float]:
        return {t: self.success_rate(t) for t in ALL_ATTACK_TYPES}

    def count_by_type(self) -> Dict[str, int]:
        counts = {t: 0 for t in ALL_ATTACK_TYPES}
        for r in self.records:
            counts[r.attack_type] = counts.get(r.attack_type, 0) + 1
        return counts

    def round_summary(self, round_num: int) -> Dict:
        recs = self.for_round(round_num)
        total = len(recs)
        successes = sum(1 for r in recs if r.success)
        dummy_wasted = sum(1 for r in recs if r.is_dummy_target)
        by_type = {}
        for t in ALL_ATTACK_TYPES:
            t_recs = [r for r in recs if r.attack_type == t]
            by_type[t] = {
                "attempts": len(t_recs),
                "successes": sum(1 for r in t_recs if r.success),
            }
        return {
            "round": round_num,
            "total_attacks": total,
            "successes": successes,
            "success_rate": successes / total if total else 0.0,
            "dummy_wasted": dummy_wasted,
            "by_type": by_type,
        }

    def last_n(self, n: int = 50) -> List[Dict]:
        return [r.to_dict() for r in self.records[-n:]]


# ───────────────── Traffic Observer ─────────────────

class TrafficObserver:
    """Simulates an adversary observing network traffic."""

    def __init__(self):
        self.observed_messages: List[Dict] = []
        self.node_activity: Dict[int, List] = defaultdict(list)
        self.observation_window = ADVERSARY_OBSERVATION_WINDOW
        self.captured_messages: List[Dict] = []  # for replay attacks

    def observe_message(self, message_data: Dict):
        observation = {
            "timestamp": message_data.get("timestamp"),
            "first_visible_node": (
                message_data.get("relay_path", [None])[0]
                if message_data.get("relay_path") else None
            ),
            "message_size": len(str(message_data.get("encrypted_content", ""))),
            "hop_count": message_data.get("hop_count", 0),
            "is_dummy": message_data.get("is_dummy", False),
        }
        self.observed_messages.append(observation)

        for node_id in message_data.get("relay_path", []):
            self.node_activity[node_id].append(observation["timestamp"])

        # Capture a copy for potential replay
        if not message_data.get("is_dummy", False):
            self.captured_messages.append(message_data.copy())
            if len(self.captured_messages) > 100:
                self.captured_messages = self.captured_messages[-100:]

    def get_recent_observations(self) -> List[Dict]:
        return self.observed_messages[-self.observation_window:]

    def analyze_traffic_pattern(self, node_id: int) -> Dict:
        activity = self.node_activity.get(node_id, [])
        if len(activity) < 2:
            return {"message_count": len(activity), "avg_interval": 0, "regularity_score": 0}
        intervals = [activity[i + 1] - activity[i] for i in range(len(activity) - 1)]
        avg_interval = sum(intervals) / len(intervals) if intervals else 0
        variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals) if intervals else 0
        regularity = 1 / (1 + variance)
        return {
            "message_count": len(activity),
            "avg_interval": avg_interval,
            "regularity_score": regularity,
        }


# ───────────────── Sender Estimator ─────────────────

class SenderEstimator:
    """Attempts to estimate the original sender through traffic correlation."""

    def __init__(self, observer: TrafficObserver):
        self.observer = observer
        self.estimation_attempts: List[Dict] = []

    def estimate_sender(self, message_data: Dict, all_drone_ids: List[int]) -> Tuple[Optional[int], float]:
        if message_data.get("is_dummy"):
            random_guess = random.choice(all_drone_ids) if all_drone_ids else None
            return random_guess, 0.1

        relay_path = message_data.get("relay_path", [])
        hop_count = message_data.get("hop_count", 0)

        base_difficulty = 1 - (0.7 ** hop_count) if hop_count > 0 else 0

        if relay_path:
            first_relay = relay_path[0]
            pattern = self.observer.analyze_traffic_pattern(first_relay)
            pattern_leak = pattern["regularity_score"] * 0.15 / (1 + hop_count * 0.3)
        else:
            pattern_leak = 0.3

        trace_prob = max(0, min(1.0, 1 - base_difficulty + pattern_leak))

        actual_sender = message_data.get("sender_id")
        if random.random() < trace_prob and actual_sender is not None:
            estimated = actual_sender
            confidence = trace_prob
        else:
            estimated = random.choice(all_drone_ids) if all_drone_ids else None
            confidence = 1.0 / len(all_drone_ids) if all_drone_ids else 0

        success = (estimated == actual_sender and confidence >= TRACE_SUCCESS_THRESHOLD)

        self.estimation_attempts.append({
            "actual_sender": actual_sender,
            "estimated_sender": estimated,
            "confidence": confidence,
            "hop_count": hop_count,
            "success": success,
        })
        return estimated, confidence

    def get_trace_success_rate(self) -> float:
        if not self.estimation_attempts:
            return 0.0
        successes = sum(1 for a in self.estimation_attempts if a["success"])
        return successes / len(self.estimation_attempts)

    def get_trace_stats_by_hops(self) -> Dict[int, float]:
        hop_stats: Dict[int, List[bool]] = defaultdict(list)
        for attempt in self.estimation_attempts:
            hop_stats[attempt["hop_count"]].append(attempt["success"])
        return {
            hops: sum(results) / len(results) if results else 0
            for hops, results in hop_stats.items()
        }


# ───────────────── Main Adversary ─────────────────

class Adversary:
    """Multi-vector adversary simulation with comprehensive attack logging."""

    # Base probabilities for each attack type per phase
    ATTACK_PROBS = {
        "PATROL": {
            AttackType.TRAFFIC_ANALYSIS: 1.0,   # always attempted
            AttackType.REPLAY: 0.15,
            AttackType.INTERCEPTION: 0.10,
            AttackType.JAMMING: 0.08,
        },
        "SURVEILLANCE": {
            AttackType.TRAFFIC_ANALYSIS: 1.0,
            AttackType.REPLAY: 0.25,
            AttackType.INTERCEPTION: 0.20,
            AttackType.JAMMING: 0.15,
        },
        "THREAT": {
            AttackType.TRAFFIC_ANALYSIS: 1.0,
            AttackType.REPLAY: 0.35,
            AttackType.INTERCEPTION: 0.30,
            AttackType.JAMMING: 0.25,
        },
    }

    # Success probability modifiers per hop count
    INTERCEPT_BASE = 0.25   # base intercept chance (modified by hops)
    JAM_BASE = 0.15         # base jam chance
    REPLAY_BASE = 0.10      # base replay success

    def __init__(self):
        self.observer = TrafficObserver()
        self.estimator = SenderEstimator(self.observer)
        self.success_threshold = TRACE_SUCCESS_THRESHOLD
        self.attack_log = AttackLog()
        self._current_round = 0

    def set_round(self, round_num: int):
        self._current_round = round_num

    # ── core attack API ──

    def observe_transmission(self, message_data: Dict):
        self.observer.observe_message(message_data)

    def attempt_trace(self, message_data: Dict, all_drone_ids: List[int]) -> Dict:
        """Traffic analysis trace (always happens)."""
        estimated, confidence = self.estimator.estimate_sender(message_data, all_drone_ids)
        actual = message_data.get("sender_id")
        success = estimated == actual and confidence >= self.success_threshold
        is_dummy = message_data.get("is_dummy", False)

        self.attack_log.add(AttackRecord(
            round_num=self._current_round,
            attack_type=AttackType.TRAFFIC_ANALYSIS,
            target_msg_id=message_data.get("message_id", "?"),
            sender_id=actual,
            success=success,
            confidence=confidence,
            hop_count=message_data.get("hop_count", 0),
            phase=self._get_phase_str(message_data),
            is_dummy_target=is_dummy,
        ))

        return {
            "estimated_sender": estimated,
            "actual_sender": actual,
            "confidence": confidence,
            "success": success,
            "is_dummy": is_dummy,
        }

    def attempt_interception(self, message_data: Dict, phase: str) -> Dict:
        """Attempt to intercept (capture & suppress) a message."""
        hop_count = message_data.get("hop_count", 0)
        is_dummy = message_data.get("is_dummy", False)

        # Should we attempt?
        attempt_prob = self.ATTACK_PROBS.get(phase, {}).get(AttackType.INTERCEPTION, 0.1)
        if random.random() > attempt_prob:
            return {"attempted": False, "success": False}

        # Success decreases with hop count (harder to intercept deep chains)
        success_prob = self.INTERCEPT_BASE / (1 + hop_count * 0.5)
        success = random.random() < success_prob

        self.attack_log.add(AttackRecord(
            round_num=self._current_round,
            attack_type=AttackType.INTERCEPTION,
            target_msg_id=message_data.get("message_id", "?"),
            sender_id=message_data.get("sender_id"),
            success=success,
            confidence=success_prob,
            hop_count=hop_count,
            phase=phase,
            is_dummy_target=is_dummy,
        ))

        return {"attempted": True, "success": success}

    def attempt_replay(self, message_data: Dict, phase: str) -> Dict:
        """Attempt to replay a previously captured message."""
        is_dummy = message_data.get("is_dummy", False)

        attempt_prob = self.ATTACK_PROBS.get(phase, {}).get(AttackType.REPLAY, 0.1)
        if random.random() > attempt_prob or not self.observer.captured_messages:
            return {"attempted": False, "success": False}

        # Replay success depends on encryption rounds (more layers = harder)
        encryption_layers = message_data.get("encryption_layers", 1)
        success_prob = self.REPLAY_BASE / (1 + encryption_layers * 0.8)
        success = random.random() < success_prob

        self.attack_log.add(AttackRecord(
            round_num=self._current_round,
            attack_type=AttackType.REPLAY,
            target_msg_id=message_data.get("message_id", "?"),
            sender_id=message_data.get("sender_id"),
            success=success,
            confidence=success_prob,
            hop_count=message_data.get("hop_count", 0),
            phase=phase,
            is_dummy_target=is_dummy,
        ))

        return {"attempted": True, "success": success}

    def attempt_jamming(self, phase: str, msg_id: str = "?",
                        sender_id=None) -> Dict:
        """Attempt to jam/block message delivery."""
        attempt_prob = self.ATTACK_PROBS.get(phase, {}).get(AttackType.JAMMING, 0.05)
        if random.random() > attempt_prob:
            return {"attempted": False, "success": False}

        success = random.random() < self.JAM_BASE
        self.attack_log.add(AttackRecord(
            round_num=self._current_round,
            attack_type=AttackType.JAMMING,
            target_msg_id=msg_id,
            sender_id=sender_id,
            success=success,
            confidence=self.JAM_BASE,
            hop_count=0,
            phase=phase,
            is_dummy_target=False,
        ))

        return {"attempted": True, "success": success}

    # ── statistics ──

    def get_statistics(self) -> Dict:
        return {
            "total_observations": len(self.observer.observed_messages),
            "trace_attempts": len(self.estimator.estimation_attempts),
            "overall_success_rate": self.estimator.get_trace_success_rate(),
            "success_by_hops": self.estimator.get_trace_stats_by_hops(),
            "attack_counts": self.attack_log.count_by_type(),
            "attack_success_by_type": self.attack_log.success_rate_by_type(),
        }

    def get_round_summary(self, round_num: int = None) -> Dict:
        if round_num is None:
            round_num = self._current_round
        return self.attack_log.round_summary(round_num)

    def analyze_phase_vulnerability(self, phase_messages: Dict[str, List]) -> Dict[str, float]:
        phase_vulnerability = {}
        for phase, messages in phase_messages.items():
            if not messages:
                phase_vulnerability[phase] = 0.0
                continue
            successes = sum(1 for m in messages if m.get("traced", False))
            phase_vulnerability[phase] = successes / len(messages)
        return phase_vulnerability

    def _get_phase_str(self, message_data: Dict) -> str:
        return message_data.get("phase", "PATROL")
