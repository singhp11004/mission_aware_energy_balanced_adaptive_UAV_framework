"""
Layer 3 — Communication Control

Orchestrates encryption, routing (single-path or IPPO-DM multipath),
dummy traffic injection, and timing jitter for each PrioritizedMessage.

This layer is the bridge between the high-level prioritization logic
and the low-level crypto/routing primitives.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

from zmaps.layers.prioritization import PrioritizedMessage
from zmaps.mission.phases import OperationalPhase, to_legacy_phase
from zmaps.mission.profiles import get_profile

if TYPE_CHECKING:
    from security import SecurityManager
    from crypto_engine import CryptoEngine
    from energy_model import EnergyModel, BatteryManager
    from relay_selector import RelaySelector
    from adversary import Adversary


# ─────────────────────── Transmission Result ───────────────────────

@dataclass
class TransmissionResult:
    """Outcome of transmitting a single PrioritizedMessage."""

    msg_id: str = ""
    sender_id: int = -1
    relay_chains: List[List[int]] = field(default_factory=list)  # one per path
    hop_count: int = 0
    phase: str = ""
    priority: float = 0.0
    multipath_used: bool = False
    split_ratios: List[float] = field(default_factory=list)

    # ── delivery ──
    reached_server: bool = False
    server_ack: Optional[str] = None

    # ── adversary ──
    traced: bool = False
    trace_confidence: float = 0.0
    intercepted: bool = False
    jammed: bool = False

    # ── cost ──
    energy_cost: float = 0.0
    latency_ms: float = 0.0
    jitter_ms: float = 0.0

    # ── dummy ──
    is_dummy: bool = False
    dummy_injected: bool = False


# ─────────────────────── Communication Layer ───────────────────────

class CommunicationLayer:
    """
    Layer 3: Takes PrioritizedMessages and produces TransmissionResults.

    Modes:
      - **Single-path** (TRANSIT / PATROL): uses RelaySelector to pick
        one relay chain, same behaviour as the original simulation.
      - **Multipath** (SURVEILLANCE / ENGAGEMENT / RECOVERY): invokes
        the IPPO-DM agent (if available) or falls back to uniform
        splitting, forwarding across *k* parallel next-hop chains.

    Parameters
    ----------
    security : SecurityManager
    crypto : CryptoEngine
    energy_model : EnergyModel
    battery_mgr : BatteryManager
    relay_selector : RelaySelector
    adversary : Adversary
    multipath_router : optional MultipathRouter (injected when IPPO is loaded)
    """

    def __init__(
        self,
        security,
        crypto,
        energy_model,
        battery_mgr,
        relay_selector,
        adversary,
        multipath_router=None,
    ):
        self.security = security
        self.crypto = crypto
        self.energy = energy_model
        self.battery = battery_mgr
        self.relay_selector = relay_selector
        self.adversary = adversary
        self.multipath_router = multipath_router

        # statistics
        self.total_transmitted: int = 0
        self.multipath_transmissions: int = 0

    # ────────────────── public API ──────────────────

    def transmit(
        self,
        message: PrioritizedMessage,
        sender,                           # Drone object
        available_relays: list,           # list[Drone]
        round_num: int,
        cooldown_duration: int = 5,
    ) -> TransmissionResult:
        """
        Encrypt, route, and forward a single message.

        Returns a TransmissionResult describing what happened.
        """
        start_t = time.time()
        packet = message.packet
        phase_str = to_legacy_phase(packet.phase)
        result = TransmissionResult(
            sender_id=sender.drone_id,
            phase=phase_str,
            priority=message.priority,
        )

        # ── 1. Energy check for sender ──
        sender_cost = self.energy.calculate_message_cost(phase_str, is_sender=True)
        if not self.battery.apply_energy_cost(sender, sender_cost, "send"):
            return result  # not enough battery
        result.energy_cost += sender_cost
        sender.messages_sent += 1

        # ── 2. Create secure message ──
        sec_msg = self.security.create_secure_message(
            sender_id=sender.drone_id,
            receiver_id="CMD",
            payload=packet.payload,
            encryption_rounds=get_profile(packet.phase).encryption_rounds,
        )
        result.msg_id = sec_msg.message_id

        # ── 3. Crypto (for inspector panel) ──
        crypto_bundle = self.crypto.encrypt_message(
            packet.payload, phase_str, sender.drone_id
        )

        # ── 4. Routing ──
        routing_depth = message.recommended_routing_depth
        use_multipath = (
            message.recommended_multipath
            and self.multipath_router is not None
            and len(available_relays) >= message.recommended_split_paths * 2
        )

        if use_multipath:
            result = self._multipath_forward(
                result, sec_msg, sender, available_relays,
                message, routing_depth, cooldown_duration, phase_str,
            )
            self.multipath_transmissions += 1
        else:
            result = self._singlepath_forward(
                result, sec_msg, sender, available_relays,
                routing_depth, cooldown_duration, phase_str,
            )

        # ── 5. Timing jitter ──
        max_jitter = message.recommended_jitter_ms
        jitter_s = random.uniform(0, max_jitter) / 1000.0
        result.jitter_ms = jitter_s * 1000

        # ── 6. Adversary attacks ──
        msg_dict = sec_msg.to_dict()
        msg_dict["phase"] = phase_str

        # Traffic analysis (always)
        self.adversary.observe_transmission(msg_dict)
        drone_ids = list(range(50))  # approximate
        trace = self.adversary.attempt_trace(msg_dict, drone_ids)
        result.traced = trace["success"]
        result.trace_confidence = trace.get("confidence", 0)

        # Interception
        intercept = self.adversary.attempt_interception(msg_dict, phase_str)
        result.intercepted = intercept.get("success", False)

        # Replay (passive — doesn't block)
        self.adversary.attempt_replay(msg_dict, phase_str)

        # Jamming
        jam = self.adversary.attempt_jamming(
            phase_str, msg_id=sec_msg.message_id, sender_id=sender.drone_id
        )
        result.jammed = jam.get("success", False)

        # ── 7. Delivery ──
        result.reached_server = not result.intercepted and not result.jammed
        result.latency_ms = (time.time() - start_t) * 1000 + result.jitter_ms

        # ── 8. Dummy injection ──
        if random.random() < message.recommended_dummy_rate:
            dummy_cost = self.energy.calculate_dummy_cost()
            if self.battery.apply_energy_cost(sender, dummy_cost, "dummy"):
                dummy_msg = self.security.create_dummy_message(sender.drone_id)
                dummy_dict = dummy_msg.to_dict()
                dummy_dict["phase"] = phase_str
                self.adversary.observe_transmission(dummy_dict)
                result.dummy_injected = True

        self.total_transmitted += 1
        return result

    # ────────────────── internal routing ──────────────────

    def _singlepath_forward(
        self, result, sec_msg, sender, available_relays,
        routing_depth, cooldown_duration, phase_str,
    ) -> TransmissionResult:
        """Standard single relay chain."""
        num_relays = min(routing_depth, len(available_relays))
        relay_chain = []

        if num_relays > 0:
            chain = self.relay_selector.select_relay_chain(
                available_relays, num_relays, source_id=sender.drone_id
            )
            for relay in chain:
                relay_cost = self.energy.calculate_message_cost(
                    phase_str, is_sender=False
                )
                if not self.battery.apply_energy_cost(relay, relay_cost, "relay"):
                    break
                result.energy_cost += relay_cost
                sec_msg = self.security.process_at_relay(sec_msg, relay.drone_id)
                relay.set_as_relay(cooldown_duration)
                relay.messages_relayed += 1
                relay_chain.append(relay.drone_id)

        result.relay_chains = [relay_chain]
        result.hop_count = len(relay_chain)
        result.multipath_used = False
        return result

    def _multipath_forward(
        self, result, sec_msg, sender, available_relays,
        message, routing_depth, cooldown_duration, phase_str,
    ) -> TransmissionResult:
        """
        IPPO-DM multipath: split traffic across k parallel chains.

        Falls back to uniform splitting if the IPPO agent is in
        inference-only mode or doesn't provide split ratios.
        """
        k = message.recommended_split_paths
        total_relays = min(routing_depth * k, len(available_relays))

        # Get split ratios from IPPO agent or uniform fallback
        if self.multipath_router is not None:
            split_ratios = self.multipath_router.get_split_ratios(
                sender_id=sender.drone_id,
                num_paths=k,
                phase=message.packet.phase,
            )
        else:
            split_ratios = [1.0 / k] * k

        result.split_ratios = split_ratios
        result.multipath_used = True

        # Allocate relays to paths
        per_path = max(1, total_relays // k)
        used_ids = {sender.drone_id}
        all_chains: List[List[int]] = []

        for path_idx in range(k):
            path_relays = []
            candidates = [r for r in available_relays if r.drone_id not in used_ids]
            n = min(per_path, len(candidates))
            if n == 0:
                all_chains.append([])
                continue

            chain = self.relay_selector.select_relay_chain(
                candidates, n, source_id=sender.drone_id
            )
            for relay in chain:
                relay_cost = self.energy.calculate_message_cost(
                    phase_str, is_sender=False
                )
                if not self.battery.apply_energy_cost(relay, relay_cost, "relay"):
                    break
                result.energy_cost += relay_cost
                sec_msg_copy = self.security.process_at_relay(sec_msg, relay.drone_id)
                relay.set_as_relay(cooldown_duration)
                relay.messages_relayed += 1
                path_relays.append(relay.drone_id)
                used_ids.add(relay.drone_id)

            all_chains.append(path_relays)

        result.relay_chains = all_chains
        result.hop_count = max((len(c) for c in all_chains), default=0)
        return result

    # ────────────────── stats ──────────────────

    def get_stats(self) -> Dict:
        return {
            "total_transmitted": self.total_transmitted,
            "multipath_transmissions": self.multipath_transmissions,
            "multipath_rate": (
                self.multipath_transmissions / self.total_transmitted
                if self.total_transmitted > 0
                else 0.0
            ),
        }
