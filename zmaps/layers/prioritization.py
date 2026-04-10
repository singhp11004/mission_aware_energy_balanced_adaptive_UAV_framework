"""
Layer 2 — Prioritization Logic

Performs semantic analysis on TelemetryPackets to assign a priority
score (0.0–1.0).  High-priority messages receive enhanced privacy
parameters (deeper routing, more dummy cover, dedicated multipath).

Priority rules are phase-aware: the same data type may have different
urgency depending on whether the swarm is in TRANSIT vs ENGAGEMENT.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from zmaps.layers.data_acquisition import DataType, TelemetryPacket
from zmaps.mission.phases import OperationalPhase, PHASE_SPECS
from zmaps.mission.profiles import PrivacyEnergyProfile, get_profile


# ─────────────────────── Prioritized Message ───────────────────────

@dataclass
class PrioritizedMessage:
    """
    A telemetry packet annotated with a priority score and
    recommended privacy envelope.
    """

    packet: TelemetryPacket
    priority: float                         # 0.0 (low) → 1.0 (critical)
    recommended_routing_depth: int = 2
    recommended_dummy_rate: float = 0.1
    recommended_jitter_ms: int = 50
    recommended_multipath: bool = False
    recommended_split_paths: int = 1
    enhanced: bool = False                  # True if priority exceeded threshold


# ─────────────────────── Priority Rules ───────────────────────

# Base priority per data type (phase-independent)
_BASE_PRIORITY: Dict[DataType, float] = {
    DataType.TARGET_ID: 0.85,
    DataType.ALERT: 0.90,
    DataType.SURVEILLANCE_FEED: 0.60,
    DataType.POSITION: 0.35,
    DataType.STATUS: 0.20,
    DataType.COMMAND_ACK: 0.15,
}

# Phase-specific multipliers  (applied on top of base)
_PHASE_MULTIPLIER: Dict[OperationalPhase, Dict[DataType, float]] = {
    OperationalPhase.TRANSIT: {
        DataType.TARGET_ID: 0.6,       # unlikely during transit
        DataType.STATUS: 1.3,          # battery awareness matters
    },
    OperationalPhase.PATROL: {},       # use base
    OperationalPhase.SURVEILLANCE: {
        DataType.SURVEILLANCE_FEED: 1.4,
        DataType.TARGET_ID: 1.2,
    },
    OperationalPhase.ENGAGEMENT: {
        DataType.TARGET_ID: 1.25,      # → pushes to 1.0 cap
        DataType.ALERT: 1.15,
        DataType.STATUS: 0.7,          # deprioritize routine
    },
    OperationalPhase.RECOVERY: {
        DataType.STATUS: 1.5,          # health reports critical
        DataType.ALERT: 1.1,
    },
}


def _compute_priority(data_type: DataType, phase: OperationalPhase) -> float:
    """Combine base priority with phase-specific multiplier, capped at 1.0."""
    base = _BASE_PRIORITY.get(data_type, 0.3)
    mult = _PHASE_MULTIPLIER.get(phase, {}).get(data_type, 1.0)
    return min(1.0, base * mult)


# ─────────────────────── Prioritization Layer ───────────────────────

class PrioritizationLayer:
    """
    Layer 2: Assigns priority scores to TelemetryPackets and produces
    PrioritizedMessages with recommended privacy parameters.
    """

    def __init__(self):
        self.messages_prioritized: int = 0
        self.enhanced_count: int = 0

    def prioritize(self, packet: TelemetryPacket) -> PrioritizedMessage:
        """Score and annotate a single telemetry packet."""
        phase = packet.phase
        priority = _compute_priority(packet.data_type, phase)
        profile = get_profile(phase)

        # Determine if this message gets enhanced protection
        enhanced = priority >= profile.priority_threshold

        if enhanced:
            # Boost privacy parameters above the phase baseline
            rec_depth = max(profile.routing_depth, profile.routing_depth + 1)
            rec_dummy = min(1.0, profile.dummy_rate + 0.15)
            rec_jitter = profile.timing_jitter_ms   # keep phase jitter (minimize delay for tactical data)
            rec_multipath = True
            rec_splits = max(profile.split_paths, 2)
            self.enhanced_count += 1
        else:
            rec_depth = profile.routing_depth
            rec_dummy = profile.dummy_rate
            rec_jitter = profile.timing_jitter_ms
            rec_multipath = profile.multipath_enabled
            rec_splits = profile.split_paths

        self.messages_prioritized += 1

        return PrioritizedMessage(
            packet=packet,
            priority=priority,
            recommended_routing_depth=rec_depth,
            recommended_dummy_rate=rec_dummy,
            recommended_jitter_ms=rec_jitter,
            recommended_multipath=rec_multipath,
            recommended_split_paths=rec_splits,
            enhanced=enhanced,
        )

    def prioritize_batch(
        self, packets: List[TelemetryPacket]
    ) -> List[PrioritizedMessage]:
        """Prioritize a list of packets and return sorted by priority (desc)."""
        messages = [self.prioritize(p) for p in packets]
        messages.sort(key=lambda m: m.priority, reverse=True)
        return messages

    def get_stats(self) -> Dict:
        return {
            "messages_prioritized": self.messages_prioritized,
            "enhanced_count": self.enhanced_count,
            "enhancement_rate": (
                self.enhanced_count / self.messages_prioritized
                if self.messages_prioritized > 0
                else 0.0
            ),
        }
