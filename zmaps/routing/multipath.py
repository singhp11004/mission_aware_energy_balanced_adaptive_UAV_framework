"""
Multipath Router — Parallel next-hop forwarding with learned traffic
splitting ratios from the IPPO-DM agent.

When multipath routing is enabled (SURVEILLANCE / ENGAGEMENT / RECOVERY),
the router splits traffic across *k* next-hop neighbors.  Each path
receives a fraction α_i (where Σα_i = 1) determined by the IPPO policy.

Falls back to uniform splitting when no trained agent is available.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, TYPE_CHECKING

from zmaps.mission.phases import OperationalPhase

if TYPE_CHECKING:
    from zmaps.routing.ippo_agent import IPPOAgent


class MultipathRouter:
    """
    Manages traffic splitting across multiple parallel relay chains.

    Parameters
    ----------
    agent : IPPOAgent or None
        Trained IPPO policy.  If None, uniform splitting is used.
    max_paths : int
        Maximum number of parallel paths (caps the profile's split_paths).
    """

    def __init__(self, agent: Optional["IPPOAgent"] = None, max_paths: int = 4):
        self.agent = agent
        self.max_paths = max_paths

        # statistics
        self.split_history: List[Dict] = []

    def get_split_ratios(
        self,
        sender_id: int,
        num_paths: int,
        phase: OperationalPhase,
        *,
        state_vector: Optional[List[float]] = None,
    ) -> List[float]:
        """
        Return traffic split ratios α = [α_1, …, α_k] on the simplex.

        If a trained agent is available and a state vector is provided,
        the ratios come from the Dirichlet policy.  Otherwise the router
        uses a uniform 1/k split.

        Parameters
        ----------
        sender_id : int
            Drone requesting the split.
        num_paths : int
            Number of paths to split over.
        phase : OperationalPhase
            Current operational phase.
        state_vector : list[float] or None
            IPPO observation vector for this drone.

        Returns
        -------
        list[float]
            Split ratios summing to 1.0.
        """
        k = min(num_paths, self.max_paths)
        if k <= 1:
            return [1.0]

        if self.agent is not None and state_vector is not None:
            ratios = self.agent.get_action(state_vector, k)
        else:
            # Uniform fallback with slight randomness
            ratios = self._uniform_split(k)

        # Record for analysis
        self.split_history.append({
            "sender_id": sender_id,
            "num_paths": k,
            "ratios": ratios,
            "phase": phase.value if isinstance(phase, OperationalPhase) else str(phase),
            "agent_used": self.agent is not None and state_vector is not None,
        })

        return ratios

    @staticmethod
    def _uniform_split(k: int) -> List[float]:
        """Uniform 1/k split with a small Dirichlet perturbation."""
        # Dir(α=5,5,…,5) is concentrated near uniform
        raw = [random.gammavariate(5.0, 1.0) for _ in range(k)]
        total = sum(raw)
        return [r / total for r in raw]

    def get_stats(self) -> Dict:
        if not self.split_history:
            return {"total_splits": 0}

        agent_count = sum(1 for s in self.split_history if s["agent_used"])
        return {
            "total_splits": len(self.split_history),
            "agent_used_count": agent_count,
            "agent_used_rate": agent_count / len(self.split_history),
        }
