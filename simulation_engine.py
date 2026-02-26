"""
Simulation Engine — Stateful step-by-step wrapper around the exact same
logic used in main.py, plus CryptoEngine integration for dashboard crypto
visualisation.

Key design: every method mirrors UAVSimulation._send_message /
_execute_round exactly so that interactive results match CLI results.
"""

import random
import time
import networkx as nx
from collections import deque
from typing import Dict, List

from config import (
    NUM_DRONES, SIMULATION_ROUNDS, MESSAGES_PER_ROUND,
    PHASE_CHANGE_INTERVAL, COOLDOWN_DURATION, MissionPhase,
    MISSION_CONFIG,
)
from swarm import UAVSwarm
from energy_model import EnergyModel, BatteryManager
from security import SecurityManager
from privacy_controller import (
    PrivacyController, RoutingPolicy, DummyTrafficGenerator, MissionManager,
)
from relay_selector import RelaySelector, LoadBalancer
from adversary import Adversary
from crypto_engine import CryptoEngine


# ─────────────────────── Game State ───────────────────────

class GameState:
    """Read-only snapshot of the simulation for the UI layer."""

    def __init__(self):
        self.round_num = 0
        self.network = None
        self.phase = MissionPhase.PATROL

        # ── counts ──
        self.total_drones = 0
        self.active_drones = 0
        self.total_messages_sent = 0
        self.total_dummy_messages = 0

        # ── battery ──
        self.avg_battery = 100.0
        self.min_battery = 100.0
        self.max_battery = 100.0

        # ── adversary (data-driven) ──
        self.adversary_trace_rate = 0.0      # lifetime trace success rate
        self.round_trace_rate = 0.0          # this-round trace success rate
        self.adversary_observations = 0

        # ── score ──
        self.score = 0
        self.game_over = False

        # ── per-round stats ──
        self.round_stats: Dict = {}

        # ── event log ──
        self.events = deque(maxlen=200)

        # ── crypto (for inspector panel) ──
        self.last_crypto_bundle = None
        self.crypto_phase_config: Dict = {}

    # helpers
    def add_event(self, event: str):
        ts = time.strftime("%H:%M:%S")
        self.events.appendleft(f"[{ts}] {event}")


# ─────────────────────── Engine ───────────────────────

class SimulationEngine:
    """
    Interactive simulation engine.
    Mirrors main.py exactly, but yields state after each round.
    """

    def __init__(self, num_drones: int = NUM_DRONES):
        self.num_drones = num_drones

        # ---- core modules (same as main.py) ----
        self.swarm = UAVSwarm(num_drones)
        self.energy_model = EnergyModel()
        self.battery_manager = BatteryManager(self.energy_model)
        self.security = SecurityManager()
        self.privacy = PrivacyController()
        self.routing = RoutingPolicy(self.privacy)
        self.dummy_generator = DummyTrafficGenerator(self.privacy)
        self.mission_manager = MissionManager(self.privacy)
        self.relay_selector = RelaySelector()
        self.load_balancer = LoadBalancer(self.relay_selector)
        self.adversary = Adversary()

        # ---- crypto engine (new) ----
        self.crypto = CryptoEngine(num_drones)

        # ---- cumulative counters ----
        self.total_messages_sent = 0
        self.total_dummy_messages = 0
        self.cumulative_latency = 0.0

        # ---- state for UI ----
        self.state = GameState()
        self.state.network = self.swarm.network
        self.state.total_drones = num_drones
        self.state.active_drones = num_drones
        self.state.crypto_phase_config = self.crypto.get_phase_config(
            MissionPhase.PATROL
        )

        # ---- history for charts ----
        self.history: Dict[str, List] = {
            "rounds": [],
            "messages": [],
            "dummy": [],
            "trace_rate": [],
            "battery_avg": [],
            "battery_min": [],
            "score": [],
            "encrypt_us": [],
            "phase": [],
        }

        self.state.add_event("🚀 MISSION INITIALIZED — Swarm online")
        self.state.add_event(
            f"📡 {num_drones} drones | "
            f"{self.swarm.network.number_of_edges()} links"
        )

    # ────────────────────────── STEP ──────────────────────────

    def step(self):
        """Execute one round — exact mirror of main.py._execute_round."""
        if self.state.game_over:
            return self.state

        self.state.round_num += 1
        round_num = self.state.round_num

        round_stats = {
            "messages_sent": 0,
            "dummy_messages": 0,
            "successful_traces": 0,
            "trace_attempts": 0,
            "total_latency": 0.0,
        }

        # 1. Update swarm
        self.swarm.update_round()
        self._simulate_movement()

        # 2. Phase transition (mirrors main.py lines 74-78)
        if round_num > 1 and round_num % PHASE_CHANGE_INTERVAL == 0:
            old_phase = self.privacy.current_phase
            new_phase = self.mission_manager.transition_to_next_phase()
            self.swarm.set_mission_phase(new_phase)
            self.state.phase = new_phase
            self.state.crypto_phase_config = self.crypto.get_phase_config(
                new_phase
            )
            self.state.add_event(f"📡 PHASE: {old_phase} → {new_phase}")
            cfg = self.state.crypto_phase_config
            self.state.add_event(
                f"🔐 Crypto: {cfg['cipher']}"
                + (" +HMAC" if cfg["hmac"] else "")
                + (" +Ed25519" if cfg["sign"] else "")
            )

        # 3. Get active drones
        active_drones = self.swarm.get_active_drones()
        self.state.active_drones = len(active_drones)
        if len(active_drones) < 3:
            self.state.add_event("⚠️ Too few drones to send messages")
        else:
            # Select senders (mirrors main.py line 123)
            num_senders = min(MESSAGES_PER_ROUND, len(active_drones))
            senders = random.sample(active_drones, num_senders)

            for sender in senders:
                latency = self._send_message(sender, round_stats)
                if latency > 0:
                    round_stats["messages_sent"] += 1
                    round_stats["total_latency"] += latency

                # Maybe inject dummy (mirrors main.py lines 133-135)
                if self.privacy.should_inject_dummy():
                    self._send_dummy_message(sender, round_stats)

        # 4. Update cumulative counters
        self.total_messages_sent += round_stats["messages_sent"]
        self.total_dummy_messages += round_stats["dummy_messages"]
        self.cumulative_latency += round_stats["total_latency"]

        # 5. Compute adversary stats from ACTUAL adversary module
        adv_stats = self.adversary.get_statistics()
        self.state.adversary_trace_rate = adv_stats["overall_success_rate"]
        self.state.adversary_observations = adv_stats["total_observations"]
        if round_stats["trace_attempts"] > 0:
            self.state.round_trace_rate = (
                round_stats["successful_traces"] / round_stats["trace_attempts"]
            )
        else:
            self.state.round_trace_rate = 0.0

        # 6. Battery stats
        bat = self.swarm.get_battery_stats()
        self.state.avg_battery = bat["mean"]
        self.state.min_battery = bat["min"]
        self.state.max_battery = bat["max"]

        # 7. Score  (higher = better)
        #    +20 per message delivered
        #    +30 bonus per message NOT traced
        #    +5 per dummy (adds cover)
        #    Phase bonus for operating in tough phases
        untouched = round_stats["messages_sent"] - round_stats["successful_traces"]
        phase_bonus = {"PATROL": 0, "SURVEILLANCE": 10, "THREAT": 25}.get(
            self.state.phase, 0
        )
        round_score = (
            round_stats["messages_sent"] * 20
            + untouched * 30
            + round_stats["dummy_messages"] * 5
            + phase_bonus
        )
        self.state.score += round_score

        # 8. Record round stats
        self.state.round_stats = round_stats
        self.state.total_messages_sent = self.total_messages_sent
        self.state.total_dummy_messages = self.total_dummy_messages

        # 9. Check game over
        if not self.swarm.is_operational(min_active_ratio=0.3):
            self.state.game_over = True
            self.state.add_event("💀 CRITICAL: Swarm below 30% — MISSION FAILED")

        # 10. Record history
        self.history["rounds"].append(round_num)
        self.history["messages"].append(round_stats["messages_sent"])
        self.history["dummy"].append(round_stats["dummy_messages"])
        self.history["trace_rate"].append(
            self.state.adversary_trace_rate * 100
        )
        self.history["battery_avg"].append(self.state.avg_battery)
        self.history["battery_min"].append(self.state.min_battery)
        self.history["score"].append(self.state.score)
        self.history["phase"].append(self.state.phase)

        # Crypto timing
        crypto_stats = self.crypto.log.stats()
        avg_enc = 0
        for alg in ["AES-256-GCM", "ChaCha20-Poly1305"]:
            if alg in crypto_stats:
                avg_enc = crypto_stats[alg]["avg_us"]
                break
        self.history["encrypt_us"].append(avg_enc)

        # cap history to 200 points
        for k in self.history:
            if len(self.history[k]) > 200:
                self.history[k] = self.history[k][-200:]

        return self.state

    # ────────────────── message sending (mirrors main.py._send_message) ──

    def _send_message(self, sender, round_stats: Dict) -> float:
        """
        Send a message from sender through relay chain.
        Uses SecurityManager + CryptoEngine.
        Returns latency in ms, or 0 on failure.
        """
        start_time = time.time()
        phase_config = self.privacy.get_phase_config()

        # Energy (same as main.py lines 147-152)
        sender_cost = self.energy_model.calculate_message_cost(
            self.privacy.current_phase, is_sender=True
        )
        if not self.battery_manager.apply_energy_cost(sender, sender_cost, "send"):
            return 0

        sender.messages_sent += 1

        # Create secure message via SecurityManager (main.py lines 157-163)
        payload = f"Telemetry from Drone {sender.drone_id} at round {self.state.round_num}"
        message = self.security.create_secure_message(
            sender_id=sender.drone_id,
            receiver_id="CMD",
            payload=payload,
            encryption_rounds=phase_config["encryption_rounds"],
        )

        # Also do real crypto for the inspector panel
        crypto_bundle = self.crypto.encrypt_message(
            payload, self.privacy.current_phase, sender.drone_id
        )
        self.state.last_crypto_bundle = crypto_bundle

        # Select relay chain (main.py lines 166-171)
        available_relays = self.swarm.get_available_relays(
            exclude_ids=[sender.drone_id]
        )
        routing_depth = phase_config["routing_depth"]
        num_relays = min(routing_depth, len(available_relays))

        relay_chain = []
        if num_relays > 0:
            relay_chain = self.relay_selector.select_relay_chain(
                available_relays, num_relays, source_id=sender.drone_id
            )
            # Process through relays (main.py lines 174-185)
            for relay in relay_chain:
                relay_cost = self.energy_model.calculate_message_cost(
                    self.privacy.current_phase, is_sender=False
                )
                if not self.battery_manager.apply_energy_cost(
                    relay, relay_cost, "relay"
                ):
                    break
                message = self.security.process_at_relay(message, relay.drone_id)
                relay.set_as_relay(COOLDOWN_DURATION)
                relay.messages_relayed += 1

        # Timing jitter (main.py line 188)
        jitter = self.privacy.apply_timing_jitter()

        # Adversary observation & trace (main.py lines 191-193)
        self.adversary.observe_transmission(message.to_dict())
        drone_ids = list(self.swarm.drones.keys())
        trace_result = self.adversary.attempt_trace(
            message.to_dict(), drone_ids
        )

        round_stats["trace_attempts"] += 1
        if trace_result["success"]:
            round_stats["successful_traces"] += 1
            self.state.add_event(
                f"🚨 TRACE: D{sender.drone_id} via "
                f"{message.hop_count}-hop ({self.state.phase})"
            )

        # Deliver to command server (main.py line 202)
        self.swarm.command_server.receive_message(message.to_dict())

        latency = (time.time() - start_time) * 1000 + jitter * 1000
        return latency

    def _send_dummy_message(self, sender, round_stats: Dict):
        """Generate dummy traffic — mirrors main.py._send_dummy_message."""
        dummy_cost = self.energy_model.calculate_dummy_cost()
        if self.battery_manager.apply_energy_cost(sender, dummy_cost, "dummy"):
            dummy = self.security.create_dummy_message(sender.drone_id)
            self.adversary.observe_transmission(dummy.to_dict())
            round_stats["dummy_messages"] += 1

    # ────────────────── movement ──────────────────

    def _simulate_movement(self):
        """Jitter node positions for visual dynamism."""
        if self.swarm.network is None:
            return
        pos = nx.get_node_attributes(self.swarm.network, "pos")
        if not pos:
            return
        new_pos = {}
        for nid, coord in pos.items():
            if isinstance(coord, (tuple, list)) and len(coord) == 2:
                x, y = coord
                new_pos[nid] = (
                    max(0.0, min(1.0, x + random.uniform(-0.015, 0.015))),
                    max(0.0, min(1.0, y + random.uniform(-0.015, 0.015))),
                )
        if new_pos:
            nx.set_node_attributes(self.swarm.network, new_pos, "pos")

    # ────────────────── player actions ──────────────────

    def deploy_decoy(self):
        """Deploy dummy nodes to confuse adversary."""
        self.state.add_event("🛡️ DECOY SQUADRON DEPLOYED — injecting noise")
        # Inject 10 dummy observations to dilute adversary data
        for _ in range(10):
            fake_sender = random.choice(list(self.swarm.drones.keys()))
            dummy = self.security.create_dummy_message(fake_sender)
            self.adversary.observe_transmission(dummy.to_dict())

    def trigger_emp(self):
        """Reset adversary's observation history."""
        self.state.add_event("⚡ EMP BLAST — Adversary tracking reset")
        # Reset the adversary completely
        self.adversary = Adversary()

    def escalate_threat(self):
        """Manually escalate to THREAT phase."""
        old = self.privacy.current_phase
        self.mission_manager.escalate_to_threat()
        self.swarm.set_mission_phase(MissionPhase.THREAT)
        self.state.phase = MissionPhase.THREAT
        self.state.crypto_phase_config = self.crypto.get_phase_config(
            MissionPhase.THREAT
        )
        self.state.add_event(f"🔴 MANUAL: {old} → THREAT")
        self.state.add_event("🔐 Crypto: ChaCha20-Poly1305 +HMAC +Ed25519")
