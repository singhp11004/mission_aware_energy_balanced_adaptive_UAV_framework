"""
IPPO Agent — Independent Proximal Policy Optimization with Dirichlet
Modeling for traffic-adaptive multipath routing.

Each drone in the swarm runs an identical (parameter-shared) policy that
maps a local observation to a Dirichlet distribution over *k* next-hop
neighbors.  Sampling from this Dirichlet yields continuous split ratios
on the probability simplex.

Architecture
------------
    observation → [128] → ReLU → [64] → ReLU
                           ↓                ↓
                     Actor head         Critic head
                  (Dirichlet α)        (scalar V)

The actor head outputs raw concentration parameters via softplus+1
(ensuring α_i > 1 for a unimodal distribution).

Uses PyTorch for the neural network.
"""

from __future__ import annotations

import os
import math
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Dirichlet


# ─────────────────────── Hyperparameters ───────────────────────

DEFAULT_HPARAMS = {
    "obs_dim": 32,             # observation vector length
    "hidden_1": 128,
    "hidden_2": 64,
    "max_paths": 4,            # maximum next-hop neighbors
    "lr": 3e-4,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip_eps": 0.2,
    "entropy_coeff": 0.01,
    "value_coeff": 0.5,
    "max_grad_norm": 0.5,
    "ppo_epochs": 4,
    "mini_batch_size": 32,
}


# ─────────────────────── Network ───────────────────────

class ActorCritic(nn.Module):
    """
    Shared-trunk Actor-Critic network with a Dirichlet actor head.

    Parameters
    ----------
    obs_dim : int
        Observation vector dimensionality.
    hidden_1, hidden_2 : int
        Hidden layer sizes.
    max_paths : int
        Maximum number of action dimensions (next-hop neighbors).
    """

    def __init__(
        self,
        obs_dim: int = 32,
        hidden_1: int = 128,
        hidden_2: int = 64,
        max_paths: int = 4,
    ):
        super().__init__()

        # Shared feature extractor
        self.shared = nn.Sequential(
            nn.Linear(obs_dim, hidden_1),
            nn.ReLU(),
            nn.Linear(hidden_1, hidden_2),
            nn.ReLU(),
        )

        # Actor: outputs raw logits → softplus+1 → Dirichlet concentrations
        self.actor_head = nn.Linear(hidden_2, max_paths)

        # Critic: scalar state value
        self.critic_head = nn.Linear(hidden_2, 1)

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=math.sqrt(2))
                nn.init.zeros_(m.bias)
        # Smaller init for actor (policy) head
        nn.init.orthogonal_(self.actor_head.weight, gain=0.01)

    def forward(
        self, obs: torch.Tensor, num_paths: int = None
    ) -> Tuple[Dirichlet, torch.Tensor]:
        """
        Forward pass.

        Parameters
        ----------
        obs : Tensor (batch, obs_dim)
        num_paths : int or None
            If given, only the first *num_paths* concentrations are used.

        Returns
        -------
        dist : Dirichlet distribution
        value : Tensor (batch, 1)
        """
        features = self.shared(obs)

        # Actor
        raw = self.actor_head(features)   # (batch, max_paths)
        if num_paths is not None and num_paths < raw.shape[-1]:
            raw = raw[..., :num_paths]
        # softplus + 1 → concentrations > 1 (unimodal Dirichlet)
        concentrations = F.softplus(raw) + 1.0
        dist = Dirichlet(concentrations)

        # Critic
        value = self.critic_head(features)

        return dist, value


# ─────────────────────── Agent ───────────────────────

class IPPOAgent:
    """
    Independent PPO agent for a single drone (parameter-shared across swarm).

    Provides:
      - ``get_action``: inference (no grad) → split ratios
      - ``evaluate_action``: training → log_prob, entropy, value
      - ``save`` / ``load``: checkpoint management
    """

    def __init__(self, hparams: Optional[Dict] = None):
        self.hp = {**DEFAULT_HPARAMS, **(hparams or {})}
        self.device = torch.device("cpu")

        self.network = ActorCritic(
            obs_dim=self.hp["obs_dim"],
            hidden_1=self.hp["hidden_1"],
            hidden_2=self.hp["hidden_2"],
            max_paths=self.hp["max_paths"],
        ).to(self.device)

        self.optimizer = torch.optim.Adam(
            self.network.parameters(), lr=self.hp["lr"]
        )

    # ── inference ──

    @torch.no_grad()
    def get_action(
        self, state: List[float], num_paths: int = None
    ) -> List[float]:
        """
        Sample split ratios from the Dirichlet policy (inference mode).

        Parameters
        ----------
        state : list[float]
            Observation vector (will be zero-padded to obs_dim).
        num_paths : int
            Number of next-hop neighbors.

        Returns
        -------
        list[float]
            Split ratios summing to ≈ 1.0.
        """
        obs = self._to_tensor(state)
        dist, _ = self.network(obs, num_paths)
        action = dist.sample()                # (1, num_paths)
        ratios = action.squeeze(0).tolist()
        # Normalize to exactly 1.0 (numerical safety)
        s = sum(ratios)
        return [r / s for r in ratios]

    @torch.no_grad()
    def get_value(self, state: List[float]) -> float:
        """Return the critic's value estimate for a state."""
        obs = self._to_tensor(state)
        _, value = self.network(obs)
        return value.item()

    # ── training ──

    def evaluate_action(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        num_paths: int = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Evaluate actions under the current policy (training mode).

        Parameters
        ----------
        states : Tensor (batch, obs_dim)
        actions : Tensor (batch, num_paths)  — split ratios
        num_paths : int

        Returns
        -------
        log_probs : Tensor (batch,)
        entropy   : Tensor (batch,)
        values    : Tensor (batch, 1)
        """
        dist, values = self.network(states, num_paths)
        log_probs = dist.log_prob(actions)
        entropy = dist.entropy()
        return log_probs, entropy, values

    # ── persistence ──

    def save(self, path: str):
        """Save model weights and optimizer state."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        torch.save({
            "network": self.network.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "hparams": self.hp,
        }, path)

    def load(self, path: str):
        """Load model weights from checkpoint."""
        ckpt = torch.load(path, map_location=self.device, weights_only=False)
        self.network.load_state_dict(ckpt["network"])
        if "optimizer" in ckpt:
            self.optimizer.load_state_dict(ckpt["optimizer"])
        if "hparams" in ckpt:
            self.hp.update(ckpt["hparams"])

    # ── internal ──

    def _to_tensor(self, state: List[float]) -> torch.Tensor:
        """Convert a state list to a (1, obs_dim) tensor, zero-padded."""
        obs_dim = self.hp["obs_dim"]
        padded = list(state[:obs_dim]) + [0.0] * max(0, obs_dim - len(state))
        return torch.tensor([padded], dtype=torch.float32, device=self.device)
