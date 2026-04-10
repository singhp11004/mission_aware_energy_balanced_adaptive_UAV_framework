"""
Privacy-Energy Profiles for each Operational Phase.

Each profile is a complete specification of the cryptographic, routing,
and traffic-obfuscation parameters that the Communication layer should
enforce while the swarm operates in a given phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from zmaps.mission.phases import OperationalPhase, PHASE_SPECS


# ─────────────────────── Profile Dataclass ───────────────────────

@dataclass(frozen=True)
class PrivacyEnergyProfile:
    """Complete privacy-energy configuration for a single phase."""

    # ── routing ──
    routing_depth: int              # relay hops
    multipath_enabled: bool         # use IPPO-DM multipath?
    split_paths: int                # number of parallel paths (1 = single)

    # ── dummy traffic ──
    dummy_rate: float               # probability of injecting dummy per message

    # ── timing ──
    timing_jitter_ms: int           # upper bound on random delay

    # ── crypto ──
    encryption_rounds: int          # onion layers
    cipher_suite: str               # "AES-256-GCM" or "ChaCha20-Poly1305"
    hmac_enabled: bool
    signing_enabled: bool

    # ── priority ──
    priority_threshold: float       # messages above this get enhanced protection

    # ── descriptive ──
    description: str = ""


# ─────────────────────── Default Profiles ───────────────────────

PHASE_PROFILES: Dict[OperationalPhase, PrivacyEnergyProfile] = {

    OperationalPhase.TRANSIT: PrivacyEnergyProfile(
        routing_depth=1,
        multipath_enabled=False,
        split_paths=1,
        dummy_rate=0.05,
        timing_jitter_ms=30,
        encryption_rounds=1,
        cipher_suite="AES-256-GCM",
        hmac_enabled=False,
        signing_enabled=False,
        priority_threshold=0.8,
        description="Minimal protection — conserve battery during transit.",
    ),

    OperationalPhase.PATROL: PrivacyEnergyProfile(
        routing_depth=2,
        multipath_enabled=False,
        split_paths=1,
        dummy_rate=0.10,
        timing_jitter_ms=50,
        encryption_rounds=1,
        cipher_suite="AES-256-GCM",
        hmac_enabled=False,
        signing_enabled=False,
        priority_threshold=0.7,
        description="Baseline patrol — standard single-path routing.",
    ),

    OperationalPhase.SURVEILLANCE: PrivacyEnergyProfile(
        routing_depth=3,
        multipath_enabled=True,
        split_paths=2,
        dummy_rate=0.30,
        timing_jitter_ms=100,
        encryption_rounds=2,
        cipher_suite="AES-256-GCM",
        hmac_enabled=True,
        signing_enabled=True,
        priority_threshold=0.5,
        description="Elevated security — dual-path with integrity checks.",
    ),

    OperationalPhase.ENGAGEMENT: PrivacyEnergyProfile(
        routing_depth=5,
        multipath_enabled=True,
        split_paths=3,
        dummy_rate=0.50,
        timing_jitter_ms=200,
        encryption_rounds=3,
        cipher_suite="ChaCha20-Poly1305",
        hmac_enabled=True,
        signing_enabled=True,
        priority_threshold=0.3,
        description="Maximum privacy — deep multipath, heavy dummy cover.",
    ),

    OperationalPhase.RECOVERY: PrivacyEnergyProfile(
        routing_depth=2,
        multipath_enabled=True,
        split_paths=2,
        dummy_rate=0.15,
        timing_jitter_ms=60,
        encryption_rounds=1,
        cipher_suite="AES-256-GCM",
        hmac_enabled=True,
        signing_enabled=False,
        priority_threshold=0.6,
        description="Post-engagement — moderate security, battery preservation.",
    ),
}


def get_profile(phase: OperationalPhase) -> PrivacyEnergyProfile:
    """Return the privacy-energy profile for a given phase."""
    return PHASE_PROFILES[phase]


def get_profile_as_dict(phase: OperationalPhase) -> Dict:
    """Return the profile as a plain dict (for backward-compat config consumers)."""
    p = PHASE_PROFILES[phase]
    return {
        "routing_depth": p.routing_depth,
        "dummy_rate": p.dummy_rate,
        "timing_jitter_ms": p.timing_jitter_ms,
        "encryption_rounds": p.encryption_rounds,
        "multipath_enabled": p.multipath_enabled,
        "split_paths": p.split_paths,
        "cipher_suite": p.cipher_suite,
        "hmac": p.hmac_enabled,
        "sign": p.signing_enabled,
        "priority_threshold": p.priority_threshold,
    }


# ─────────────────────── Legacy Bridge ───────────────────────

def legacy_mission_config() -> Dict[str, Dict]:
    """
    Generate a MISSION_CONFIG dict compatible with the original config.py
    format, for modules that haven't been migrated yet.
    """
    from zmaps.mission.phases import PHASE_TO_LEGACY

    config: Dict[str, Dict] = {}
    for op_phase, profile in PHASE_PROFILES.items():
        legacy_key = PHASE_TO_LEGACY.get(op_phase, "PATROL")
        # Only keep the first mapping (highest-threat wins for dupes)
        if legacy_key not in config or (
            PHASE_SPECS[op_phase].threat_level
            > PHASE_SPECS[
                next(k for k, v in PHASE_TO_LEGACY.items() if v == legacy_key)
            ].threat_level
        ):
            config[legacy_key] = {
                "routing_depth": profile.routing_depth,
                "dummy_rate": profile.dummy_rate,
                "timing_jitter_ms": profile.timing_jitter_ms,
                "encryption_rounds": profile.encryption_rounds,
            }
    return config
