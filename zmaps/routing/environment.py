"""
Gym-compatible Environment for IPPO-DM training.

Wraps the UAV swarm simulation as a multi-agent environment where each
drone independently selects Dirichlet traffic-splitting ratios.

Observation → State vector per drone.
Action      → Dirichlet split ratios per drone.
Reward      → Composite: delivery_rate − energy − trace + balance.
"""

from __future__ import annotations

import sys
import os
import random
from typing import Dict, List, Optional, Tuple

import numpy as np

# Add project root to path for existing module imports
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import NUM_DRONES, MESSAGES_PER_ROUND, COOLDOWN_DURATION
from swarm import UAVSwarm, Drone
from energy_model import EnergyModel, BatteryManager
from security import SecurityManager
from adversary import Adversary
from relay_selector import RelaySelector
from crypto_engine import CryptoEngine

from zmaps.mission.phases import (
    OperationalPhase, PhaseSequencer, PHASE_SPECS, to_legacy_phase,
)
from zmaps.mission.profiles import get_profile
from zmaps.layers.data_acquisition import DataAcquisitionLayer
from zmaps.layers.prioritization import PrioritizationLayer
from zmaps.layers.communication import CommunicationLayer
from zmaps.layers.toc_integration import TOCIntegrationLayer
from zmaps.routing.multipath import MultipathRouter


# ─────────────────────── Constants ───────────────────────

MAX_NEIGHBORS = 10      # zero-pad neighbor features to this size
OBS_DIM = 32            # total observation vector length per drone

# Reward weights (tunable)
W_DELIVERY = 1.0
W_ENERGY = 0.3
W_TRACE = 0.5
W_BALANCE = 0.2


# ─────────────────────── Observation Builder ───────────────────────

def build_observation(
    drone: Drone,
    swarm: UAVSwarm,
    phase: OperationalPhase,
    recent_delivery_rate: float = 1.0,
    msg_priority: float = 0.5,
) -> List[float]:
    """
    Build a fixed-size observation vector for a single drone.

    Layout (32 features):
      [0]       own battery (normalised 0-1)
      [1]       own cooldown timer (normalised 0-1)
      [2]       relay usage count (normalised 0-1, cap at 50)
      [3..12]   neighbor battery levels (zero-padded to MAX_NEIGHBORS)
      [13..17]  phase one-hot (5 phases)
      [18]      message priority
      [19]      recent delivery rate
      [20]      number of active neighbors (normalised)
      [21..31]  neighbor queue depths (placeholder zeros)
    """
    obs = [0.0] * OBS_DIM

    # Own state
    obs[0] = drone.battery_level / 100.0
    obs[1] = min(drone.cooldown_timer / 10.0, 1.0)
    obs[2] = min(drone.relay_usage_count / 50.0, 1.0)

    # Neighbor batteries
    neighbors = swarm.get_neighbors(drone.drone_id)
    neighbor_drones = [
        swarm.drones[n]
        for n in neighbors
        if isinstance(n, int) and n in swarm.drones
    ]
    for i, nd in enumerate(neighbor_drones[:MAX_NEIGHBORS]):
        obs[3 + i] = nd.battery_level / 100.0

    # Phase one-hot
    phase_idx = list(OperationalPhase).index(phase)
    obs[13 + phase_idx] = 1.0

    # Priority + delivery
    obs[18] = msg_priority
    obs[19] = recent_delivery_rate

    # Active neighbor count
    obs[20] = min(len(neighbor_drones) / MAX_NEIGHBORS, 1.0)

    return obs


# ─────────────────────── Environment ───────────────────────

class SwarmRoutingEnv:
    """
    Multi-agent environment for IPPO-DM training.

    Each ``step()`` executes one simulation round where each active
    sender uses the IPPO agent to determine traffic-splitting ratios.

    The environment tracks and returns a reward signal that balances
    delivery, energy, privacy, and load fairness.

    Parameters
    ----------
    num_drones : int
    phase_change_interval : int
        Rounds between automatic phase transitions.
    max_rounds : int
        Episode length cap.
    """

    def __init__(
        self,
        num_drones: int = NUM_DRONES,
        phase_change_interval: int = 20,
        max_rounds: int = 100,
    ):
        self.num_drones = num_drones
        self.phase_change_interval = phase_change_interval
        self.max_rounds = max_rounds

        # These will be initialised in reset()
        self.swarm: Optional[UAVSwarm] = None
        self.energy_model: Optional[EnergyModel] = None
        self.battery_mgr: Optional[BatteryManager] = None
        self.security: Optional[SecurityManager] = None
        self.adversary: Optional[Adversary] = None
        self.relay_selector: Optional[RelaySelector] = None
        self.crypto: Optional[CryptoEngine] = None

        # Layers
        self.l1: Optional[DataAcquisitionLayer] = None
        self.l2: Optional[PrioritizationLayer] = None
        self.l3: Optional[CommunicationLayer] = None
        self.l4: Optional[TOCIntegrationLayer] = None

        self.sequencer: Optional[PhaseSequencer] = None
        self.round_num = 0
        self._recent_deliveries: List[bool] = []

    # ────────────────── Gym-like API ──────────────────

    def reset(self) -> Dict[int, List[float]]:
        """
        Reset the environment and return initial observations for all drones.

        Returns
        -------
        dict[int, list[float]]
            Mapping from drone_id to observation vector.
        """
        self.swarm = UAVSwarm(self.num_drones)
        self.energy_model = EnergyModel()
        self.battery_mgr = BatteryManager(self.energy_model)
        self.security = SecurityManager()
        self.adversary = Adversary()
        self.relay_selector = RelaySelector()
        self.crypto = CryptoEngine(self.num_drones)

        self.l1 = DataAcquisitionLayer()
        self.l2 = PrioritizationLayer()
        self.l3 = CommunicationLayer(
            security=self.security,
            crypto=self.crypto,
            energy_model=self.energy_model,
            battery_mgr=self.battery_mgr,
            relay_selector=self.relay_selector,
            adversary=self.adversary,
            multipath_router=None,   # will be set by trainer
        )
        self.l4 = TOCIntegrationLayer(self.swarm.command_server)
        self.sequencer = PhaseSequencer()
        self.round_num = 0
        self._recent_deliveries = []

        return self._get_all_observations()

    def step(
        self,
        actions: Dict[int, List[float]],
    ) -> Tuple[Dict[int, List[float]], float, bool, Dict]:
        """
        Execute one round with the given actions.

        Parameters
        ----------
        actions : dict[int, list[float]]
            Mapping from drone_id to split ratios (used when that drone
            is a sender in this round).

        Returns
        -------
        observations : dict[int, list[float]]
        reward : float (scalar, shared across agents for simplicity)
        done : bool
        info : dict
        """
        self.round_num += 1
        self.adversary.set_round(self.round_num)
        self.swarm.update_round()
        self.sequencer.tick()

        # Phase transition
        if self.round_num > 1 and self.round_num % self.phase_change_interval == 0:
            self.sequencer.advance()
        phase = self.sequencer.current
        legacy = to_legacy_phase(phase)
        self.swarm.set_mission_phase(legacy)

        # Get active drones and select senders
        active = self.swarm.get_active_drones()
        if len(active) < 3:
            obs = self._get_all_observations()
            return obs, -1.0, True, {"reason": "too_few_drones"}

        senders = random.sample(active, min(MESSAGES_PER_ROUND, len(active)))

        # Execute messages
        round_deliveries = 0
        round_traces = 0
        round_energy = 0.0
        round_total = 0

        for sender in senders:
            payload = f"Telemetry from Drone {sender.drone_id} at round {self.round_num}"
            packet = self.l1.collect(sender.drone_id, payload, phase)
            pri_msg = self.l2.prioritize(packet)

            # Set multipath router with sender's split ratios
            class _InlineRouter:
                """Tiny wrapper to pass pre-computed split ratios."""
                def __init__(self, ratios):
                    self._ratios = ratios
                def get_split_ratios(self, **kw):
                    return self._ratios

            split_ratios = actions.get(sender.drone_id, [1.0])
            self.l3.multipath_router = _InlineRouter(split_ratios)

            available = self.swarm.get_available_relays(exclude_ids=[sender.drone_id])
            result = self.l3.transmit(
                pri_msg, sender, available, self.round_num, COOLDOWN_DURATION
            )

            # Deliver via TOC layer
            msg_dict = self.security.create_secure_message(
                sender.drone_id, "CMD", payload, 1
            ).to_dict()
            result = self.l4.deliver(result, msg_dict, self.round_num)

            round_total += 1
            if result.reached_server:
                round_deliveries += 1
            if result.traced:
                round_traces += 1
            round_energy += result.energy_cost

        # Delivery tracking
        delivery_rate = round_deliveries / round_total if round_total > 0 else 0
        self._recent_deliveries.append(delivery_rate > 0.5)
        if len(self._recent_deliveries) > 20:
            self._recent_deliveries = self._recent_deliveries[-20:]

        # Load balance (Gini of relay usage)
        usages = [d.relay_usage_count for d in self.swarm.drones.values()]
        mean_usage = sum(usages) / len(usages) if usages else 1
        gini = self._gini(usages)
        balance_score = 1.0 - gini   # higher is better

        # Trace rate
        trace_rate = round_traces / round_total if round_total > 0 else 0

        # Energy normalised (per-drone average cost as fraction of INITIAL_BATTERY)
        energy_norm = round_energy / (round_total * 100.0) if round_total > 0 else 0

        # ── Composite reward ──
        reward = (
            W_DELIVERY * delivery_rate
            - W_ENERGY * energy_norm
            - W_TRACE * trace_rate
            + W_BALANCE * balance_score
        )

        # Done condition
        done = (
            self.round_num >= self.max_rounds
            or not self.swarm.is_operational(min_active_ratio=0.3)
        )

        obs = self._get_all_observations()
        info = {
            "round": self.round_num,
            "phase": phase.value,
            "delivery_rate": delivery_rate,
            "trace_rate": trace_rate,
            "energy_cost": round_energy,
            "balance_score": balance_score,
            "reward": reward,
        }

        return obs, reward, done, info

    # ────────────────── helpers ──────────────────

    def _get_all_observations(self) -> Dict[int, List[float]]:
        """Return observations for all active drones."""
        phase = self.sequencer.current if self.sequencer else OperationalPhase.PATROL
        recent_dr = (
            sum(self._recent_deliveries) / len(self._recent_deliveries)
            if self._recent_deliveries
            else 1.0
        )
        return {
            did: build_observation(
                drone, self.swarm, phase, recent_dr, 0.5
            )
            for did, drone in self.swarm.drones.items()
            if drone.is_active
        }

    @staticmethod
    def _gini(values: List[float]) -> float:
        """Calculate Gini coefficient."""
        if not values or sum(values) == 0:
            return 0.0
        n = len(values)
        sv = sorted(values)
        num = sum((2 * i - n - 1) * x for i, x in enumerate(sv, 1))
        den = n * sum(sv)
        return num / den if den else 0.0
