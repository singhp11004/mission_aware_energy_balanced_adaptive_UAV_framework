"""
Operational Phase Definitions for Z-MAPS.

Defines a 5-phase mission lifecycle that extends the original 3-phase
model (PATROL / SURVEILLANCE / THREAT) with TRANSIT and RECOVERY phases,
each carrying a distinct threat level and energy budget factor.

Backward-compatible: the old MissionPhase string constants are still
importable and map to corresponding OperationalPhase values.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional


# ─────────────────────── Operational Phases ───────────────────────

class OperationalPhase(str, Enum):
    """
    Five discrete operational phases for a UAV swarm mission.

    Order reflects a typical mission arc:
        TRANSIT → PATROL → SURVEILLANCE → ENGAGEMENT → RECOVERY
    """

    TRANSIT = "TRANSIT"
    PATROL = "PATROL"
    SURVEILLANCE = "SURVEILLANCE"
    ENGAGEMENT = "ENGAGEMENT"
    RECOVERY = "RECOVERY"

    # ── readable helpers ──

    @property
    def label(self) -> str:
        _labels = {
            "TRANSIT": "🚁 Transit",
            "PATROL": "🟢 Patrol",
            "SURVEILLANCE": "🟡 Surveillance",
            "ENGAGEMENT": "🔴 Engagement",
            "RECOVERY": "🔵 Recovery",
        }
        return _labels.get(self.value, self.value)


# ─────────────────────── Phase Metadata ───────────────────────

@dataclass(frozen=True)
class PhaseSpec:
    """Static metadata for an operational phase."""

    phase: OperationalPhase
    threat_level: float            # 0.0 (safe) → 1.0 (critical)
    energy_budget_factor: float    # multiplier; 1.0 = baseline
    max_jitter_ms: int             # upper bound on timing jitter
    min_routing_depth: int         # minimum relay hops
    description: str


PHASE_SPECS: Dict[OperationalPhase, PhaseSpec] = {
    OperationalPhase.TRANSIT: PhaseSpec(
        phase=OperationalPhase.TRANSIT,
        threat_level=0.1,
        energy_budget_factor=0.7,
        max_jitter_ms=30,
        min_routing_depth=1,
        description="Low-threat movement between operational areas; conserve energy.",
    ),
    OperationalPhase.PATROL: PhaseSpec(
        phase=OperationalPhase.PATROL,
        threat_level=0.25,
        energy_budget_factor=1.0,
        max_jitter_ms=50,
        min_routing_depth=2,
        description="Standard patrol with baseline security posture.",
    ),
    OperationalPhase.SURVEILLANCE: PhaseSpec(
        phase=OperationalPhase.SURVEILLANCE,
        threat_level=0.55,
        energy_budget_factor=1.3,
        max_jitter_ms=100,
        min_routing_depth=3,
        description="Active intelligence gathering; elevated OPSEC.",
    ),
    OperationalPhase.ENGAGEMENT: PhaseSpec(
        phase=OperationalPhase.ENGAGEMENT,
        threat_level=0.95,
        energy_budget_factor=1.8,
        max_jitter_ms=200,
        min_routing_depth=5,
        description="High-threat active engagement; maximum privacy, energy cost accepted.",
    ),
    OperationalPhase.RECOVERY: PhaseSpec(
        phase=OperationalPhase.RECOVERY,
        threat_level=0.35,
        energy_budget_factor=0.9,
        max_jitter_ms=60,
        min_routing_depth=2,
        description="Post-engagement withdrawal; moderate security, battery preservation.",
    ),
}


# ─────────────────────── Backward Compatibility ───────────────────────

# Map old 3-phase MissionPhase strings to OperationalPhase
LEGACY_PHASE_MAP: Dict[str, OperationalPhase] = {
    "PATROL": OperationalPhase.PATROL,
    "SURVEILLANCE": OperationalPhase.SURVEILLANCE,
    "THREAT": OperationalPhase.ENGAGEMENT,   # THREAT → ENGAGEMENT
}

# Reverse map for dashboard / legacy code
PHASE_TO_LEGACY: Dict[OperationalPhase, str] = {
    OperationalPhase.TRANSIT: "PATROL",
    OperationalPhase.PATROL: "PATROL",
    OperationalPhase.SURVEILLANCE: "SURVEILLANCE",
    OperationalPhase.ENGAGEMENT: "THREAT",
    OperationalPhase.RECOVERY: "SURVEILLANCE",
}


def to_operational_phase(legacy: str) -> OperationalPhase:
    """Convert a legacy MissionPhase string to OperationalPhase."""
    return LEGACY_PHASE_MAP.get(legacy, OperationalPhase.PATROL)


def to_legacy_phase(op_phase: OperationalPhase) -> str:
    """Convert an OperationalPhase back to a legacy 3-phase string."""
    return PHASE_TO_LEGACY.get(op_phase, "PATROL")


# ─────────────────────── Phase Sequencing ───────────────────────

# Default mission arc (cyclic)
DEFAULT_PHASE_SEQUENCE = [
    OperationalPhase.TRANSIT,
    OperationalPhase.PATROL,
    OperationalPhase.SURVEILLANCE,
    OperationalPhase.ENGAGEMENT,
    OperationalPhase.RECOVERY,
    OperationalPhase.PATROL,
]


class PhaseSequencer:
    """
    Controls phase transitions with hysteresis to prevent flip-flopping.

    Parameters
    ----------
    sequence : list[OperationalPhase]
        Ordered list of phases to cycle through.
    hysteresis_rounds : int
        Minimum rounds before allowing another transition.
    """

    def __init__(
        self,
        sequence: list[OperationalPhase] | None = None,
        hysteresis_rounds: int = 5,
    ):
        self.sequence = list(sequence or DEFAULT_PHASE_SEQUENCE)
        self.hysteresis_rounds = hysteresis_rounds
        self._index = 0
        self._rounds_since_transition = 0

    @property
    def current(self) -> OperationalPhase:
        return self.sequence[self._index]

    @property
    def current_spec(self) -> PhaseSpec:
        return PHASE_SPECS[self.current]

    def tick(self) -> None:
        """Advance the internal round counter (call once per simulation round)."""
        self._rounds_since_transition += 1

    def advance(self, force: bool = False) -> OperationalPhase:
        """
        Move to the next phase in sequence.

        Returns the new phase, or the current phase if hysteresis blocks
        the transition (unless *force* is True).
        """
        if not force and self._rounds_since_transition < self.hysteresis_rounds:
            return self.current

        self._index = (self._index + 1) % len(self.sequence)
        self._rounds_since_transition = 0
        return self.current

    def escalate(self, target: OperationalPhase = OperationalPhase.ENGAGEMENT) -> OperationalPhase:
        """Emergency escalation to a specific phase, bypassing hysteresis."""
        for i, phase in enumerate(self.sequence):
            if phase == target:
                self._index = i
                self._rounds_since_transition = 0
                return self.current
        # If target not in sequence, jump to highest threat
        self._index = max(
            range(len(self.sequence)),
            key=lambda i: PHASE_SPECS[self.sequence[i]].threat_level,
        )
        self._rounds_since_transition = 0
        return self.current

    def deescalate(self, target: OperationalPhase = OperationalPhase.PATROL) -> OperationalPhase:
        """De-escalate to a safer phase."""
        for i, phase in enumerate(self.sequence):
            if phase == target:
                self._index = i
                self._rounds_since_transition = 0
                return self.current
        self._index = 0
        self._rounds_since_transition = 0
        return self.current
