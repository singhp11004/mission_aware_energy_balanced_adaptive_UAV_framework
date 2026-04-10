"""
Layer 4 — Tactical Operations Center (TOC) Integration

Handles the final delivery of messages to the Command Server, processes
ACKs, aggregates delivery statistics, and provides a feedback loop to
recommend phase escalation when delivery rates degrade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

from zmaps.layers.communication import TransmissionResult
from zmaps.mission.phases import OperationalPhase

if TYPE_CHECKING:
    from swarm import CommandServer


# ─────────────────────── Delivery Record ───────────────────────

@dataclass
class DeliveryRecord:
    """Single delivery attempt record for audit trail."""

    round_num: int
    msg_id: str
    sender_id: int
    reached_server: bool
    ack_status: Optional[str]  # "ACK", "NACK", or None
    traced: bool
    intercepted: bool
    jammed: bool
    priority: float
    multipath_used: bool
    latency_ms: float
    energy_cost: float


# ─────────────────────── TOC Integration Layer ───────────────────────

class TOCIntegrationLayer:
    """
    Layer 4: Manages the interface between the swarm and the ground-based
    Tactical Operations Center (command server).

    Responsibilities:
      - Deliver messages to the CommandServer and record ACKs.
      - Track per-round delivery statistics.
      - Provide a phase-escalation signal when delivery rate drops below
        a configurable threshold.
      - Maintain an audit trail of all delivery attempts.

    Parameters
    ----------
    command_server : CommandServer
        The swarm's ground-truth command server.
    escalation_threshold : float
        If the delivery rate in a round falls below this, the TOC
        recommends escalation (default 0.6 = 60%).
    """

    def __init__(self, command_server, escalation_threshold: float = 0.60):
        self.server = command_server
        self.escalation_threshold = escalation_threshold

        # ── per-round tracking ──
        self._round_stats: Dict[int, Dict] = {}
        self._delivery_log: List[DeliveryRecord] = []

        # ── cumulative ──
        self.total_delivered: int = 0
        self.total_dropped: int = 0
        self.total_traced: int = 0

    # ────────────────── public API ──────────────────

    def deliver(
        self,
        result: TransmissionResult,
        msg_dict: Dict,
        round_num: int,
    ) -> TransmissionResult:
        """
        Attempt to deliver a message to the Command Server.

        Updates *result* in-place with the server ACK and records
        delivery statistics.

        Parameters
        ----------
        result : TransmissionResult
            Output from the Communication layer.
        msg_dict : dict
            Serialised message dict for the CommandServer.
        round_num : int
            Current simulation round.
        """
        rs = self._ensure_round_stats(round_num)

        if result.reached_server:
            ack = self.server.receive_message(msg_dict, round_num)
            result.server_ack = ack["status"]
            self.total_delivered += 1
            rs["delivered"] += 1
        else:
            self.server.record_drop(round_num)
            result.server_ack = None
            self.total_dropped += 1
            rs["dropped"] += 1

        if result.traced:
            self.total_traced += 1
            rs["traced"] += 1

        rs["total"] += 1

        # Record audit entry
        self._delivery_log.append(DeliveryRecord(
            round_num=round_num,
            msg_id=result.msg_id,
            sender_id=result.sender_id,
            reached_server=result.reached_server,
            ack_status=result.server_ack,
            traced=result.traced,
            intercepted=result.intercepted,
            jammed=result.jammed,
            priority=result.priority,
            multipath_used=result.multipath_used,
            latency_ms=result.latency_ms,
            energy_cost=result.energy_cost,
        ))

        return result

    def should_escalate(self, round_num: int) -> bool:
        """
        Return True if the delivery rate in the given round fell below
        the escalation threshold, suggesting the phase should be raised.
        """
        rs = self._round_stats.get(round_num)
        if rs is None or rs["total"] == 0:
            return False
        delivery_rate = rs["delivered"] / rs["total"]
        return delivery_rate < self.escalation_threshold

    # ────────────────── statistics ──────────────────

    def get_round_stats(self, round_num: int) -> Dict:
        """Return delivery statistics for a given round."""
        return self._round_stats.get(round_num, {
            "total": 0, "delivered": 0, "dropped": 0, "traced": 0,
        })

    def get_cumulative_stats(self) -> Dict:
        total = self.total_delivered + self.total_dropped
        return {
            "total_delivered": self.total_delivered,
            "total_dropped": self.total_dropped,
            "total_traced": self.total_traced,
            "delivery_rate": self.total_delivered / total if total > 0 else 1.0,
            "trace_rate": self.total_traced / total if total > 0 else 0.0,
        }

    def get_delivery_log(self, n: int = 50) -> List[Dict]:
        """Return the last *n* delivery records as dicts."""
        records = self._delivery_log[-n:]
        return [
            {
                "round": r.round_num,
                "msg_id": r.msg_id,
                "sender_id": r.sender_id,
                "delivered": r.reached_server,
                "ack": r.ack_status,
                "traced": r.traced,
                "priority": r.priority,
                "multipath": r.multipath_used,
                "latency_ms": round(r.latency_ms, 2),
                "energy": round(r.energy_cost, 4),
            }
            for r in records
        ]

    # ────────────────── internal ──────────────────

    def _ensure_round_stats(self, round_num: int) -> Dict:
        """Get or create the stats dict for a round."""
        if round_num not in self._round_stats:
            self._round_stats[round_num] = {
                "total": 0,
                "delivered": 0,
                "dropped": 0,
                "traced": 0,
            }
        return self._round_stats[round_num]
