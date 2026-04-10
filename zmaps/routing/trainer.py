"""
IPPO-DM Trainer — PPO training loop for the multi-agent routing policy.

Implements:
  • Rollout buffer with per-drone trajectories
  • Generalised Advantage Estimation (GAE-λ)
  • Clipped PPO surrogate objective
  • Entropy bonus (Dirichlet entropy)
  • Periodic checkpointing and training curve logging
"""

from __future__ import annotations

import os
import sys
import json
import time
import random
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

import numpy as np
import torch

# Add project root to path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from zmaps.routing.ippo_agent import IPPOAgent, DEFAULT_HPARAMS
from zmaps.routing.environment import SwarmRoutingEnv, OBS_DIM


# ─────────────────────── Rollout Buffer ───────────────────────

class RolloutBuffer:
    """
    Stores transitions for one rollout (episode or fixed horizon).

    Each entry stores per-drone data for one round.
    """

    def __init__(self):
        self.obs: List[torch.Tensor] = []         # (num_agents, obs_dim)
        self.actions: List[torch.Tensor] = []     # (num_agents, k)
        self.log_probs: List[torch.Tensor] = []   # (num_agents,)
        self.rewards: List[float] = []             # scalar per step
        self.values: List[torch.Tensor] = []       # (num_agents,)
        self.dones: List[bool] = []
        self.agent_ids: List[List[int]] = []       # which drones were active

    def add(
        self,
        obs: torch.Tensor,
        actions: torch.Tensor,
        log_probs: torch.Tensor,
        reward: float,
        value: torch.Tensor,
        done: bool,
        agent_ids: List[int],
    ):
        self.obs.append(obs)
        self.actions.append(actions)
        self.log_probs.append(log_probs)
        self.rewards.append(reward)
        self.values.append(value)
        self.dones.append(done)
        self.agent_ids.append(agent_ids)

    def __len__(self):
        return len(self.rewards)

    def clear(self):
        self.__init__()


# ─────────────────────── GAE ───────────────────────

def compute_gae(
    rewards: List[float],
    values: List[float],
    dones: List[bool],
    gamma: float = 0.99,
    lam: float = 0.95,
    last_value: float = 0.0,
) -> Tuple[List[float], List[float]]:
    """
    Compute Generalised Advantage Estimation.

    Returns
    -------
    advantages : list[float]
    returns : list[float]  (advantages + values = returns)
    """
    advantages = []
    gae = 0.0
    T = len(rewards)

    # Append last value for bootstrapping
    vals = list(values) + [last_value]

    for t in reversed(range(T)):
        mask = 0.0 if dones[t] else 1.0
        delta = rewards[t] + gamma * vals[t + 1] * mask - vals[t]
        gae = delta + gamma * lam * mask * gae
        advantages.insert(0, gae)

    returns = [adv + v for adv, v in zip(advantages, values)]
    return advantages, returns


# ─────────────────────── Trainer ───────────────────────

class IPPOTrainer:
    """
    PPO training loop for the IPPO-DM agent.

    Parameters
    ----------
    num_drones : int
    hparams : dict (override defaults from ippo_agent.DEFAULT_HPARAMS)
    checkpoint_dir : str
    log_dir : str
    """

    def __init__(
        self,
        num_drones: int = 50,
        hparams: Optional[Dict] = None,
        checkpoint_dir: str = "outputs/checkpoints",
        log_dir: str = "outputs/training",
    ):
        self.hp = {**DEFAULT_HPARAMS, **(hparams or {})}
        self.num_drones = num_drones
        self.checkpoint_dir = checkpoint_dir
        self.log_dir = log_dir

        os.makedirs(checkpoint_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)

        self.agent = IPPOAgent(self.hp)
        self.env = SwarmRoutingEnv(num_drones=num_drones)
        self.buffer = RolloutBuffer()

        # Training history
        self.history: Dict[str, List[float]] = defaultdict(list)

    # ────────────────── main training loop ──────────────────

    def train(
        self,
        num_episodes: int = 500,
        max_steps: int = 100,
        checkpoint_interval: int = 50,
        verbose: bool = True,
    ) -> Dict[str, List[float]]:
        """
        Run the full training loop.

        Parameters
        ----------
        num_episodes : int
            Number of training episodes.
        max_steps : int
            Maximum rounds per episode.
        checkpoint_interval : int
            Save checkpoint every N episodes.
        verbose : bool
            Print progress.

        Returns
        -------
        history : dict of training metrics lists.
        """
        if verbose:
            print("=" * 60)
            print(" IPPO-DM Training — Z-MAPS Multipath Routing")
            print("=" * 60)
            print(f"  Episodes: {num_episodes}")
            print(f"  Max steps/episode: {max_steps}")
            print(f"  Obs dim: {self.hp['obs_dim']}, Max paths: {self.hp['max_paths']}")
            print(f"  LR: {self.hp['lr']}, Clip ε: {self.hp['clip_eps']}")
            print("-" * 60)

        t0 = time.time()

        for ep in range(1, num_episodes + 1):
            ep_reward, ep_info = self._run_episode(max_steps)

            # Record history
            self.history["episode"].append(ep)
            self.history["reward"].append(ep_reward)
            self.history["delivery_rate"].append(ep_info.get("avg_delivery", 0))
            self.history["trace_rate"].append(ep_info.get("avg_trace", 0))
            self.history["avg_energy"].append(ep_info.get("avg_energy", 0))
            self.history["policy_loss"].append(ep_info.get("policy_loss", 0))
            self.history["value_loss"].append(ep_info.get("value_loss", 0))
            self.history["entropy"].append(ep_info.get("entropy", 0))
            self.history["rounds"].append(ep_info.get("rounds", 0))

            if verbose and ep % 10 == 0:
                elapsed = time.time() - t0
                print(
                    f"  Ep {ep:4d}/{num_episodes} | "
                    f"R={ep_reward:+.3f} | "
                    f"Del={ep_info.get('avg_delivery', 0):.2%} | "
                    f"Trace={ep_info.get('avg_trace', 0):.2%} | "
                    f"Rnds={ep_info.get('rounds', 0)} | "
                    f"{elapsed:.1f}s"
                )

            if ep % checkpoint_interval == 0:
                ckpt = os.path.join(self.checkpoint_dir, f"ippo_ep{ep}.pt")
                self.agent.save(ckpt)
                if verbose:
                    print(f"    💾 Checkpoint: {ckpt}")

        # Final save
        final_path = os.path.join(self.checkpoint_dir, "ippo_final.pt")
        self.agent.save(final_path)
        self._save_history()

        if verbose:
            total_t = time.time() - t0
            print("-" * 60)
            print(f"  Training complete in {total_t:.1f}s")
            print(f"  Final checkpoint: {final_path}")
            print(f"  History saved to: {self.log_dir}/training_history.json")
            print("=" * 60)

        return dict(self.history)

    # ────────────────── single episode ──────────────────

    def _run_episode(self, max_steps: int) -> Tuple[float, Dict]:
        """Run one episode, collect data, and update the policy."""
        self.env.max_rounds = max_steps
        all_obs = self.env.reset()
        self.buffer.clear()

        total_reward = 0.0
        step_deliveries: List[float] = []
        step_traces: List[float] = []
        step_energies: List[float] = []

        for step in range(max_steps):
            active_ids = sorted(all_obs.keys())
            if not active_ids:
                break

            # Build batch observation tensor
            obs_list = [all_obs[did] for did in active_ids]
            obs_tensor = torch.tensor(obs_list, dtype=torch.float32)

            # Get actions from policy
            k = min(self.hp["max_paths"], 3)  # practical path count
            dist, values = self.agent.network(obs_tensor, k)
            actions = dist.sample()        # (num_agents, k)
            log_probs = dist.log_prob(actions)

            # Convert to environment actions dict
            env_actions: Dict[int, List[float]] = {}
            for idx, did in enumerate(active_ids):
                ratios = actions[idx].tolist()
                s = sum(ratios)
                env_actions[did] = [r / s for r in ratios]

            # Environment step
            next_obs, reward, done, info = self.env.step(env_actions)

            # Store transition
            self.buffer.add(
                obs=obs_tensor,
                actions=actions,
                log_probs=log_probs,
                reward=reward,
                value=values.squeeze(-1).mean(),  # shared reward → mean value
                done=done,
                agent_ids=active_ids,
            )

            total_reward += reward
            step_deliveries.append(info.get("delivery_rate", 0))
            step_traces.append(info.get("trace_rate", 0))
            step_energies.append(info.get("energy_cost", 0))

            all_obs = next_obs
            if done:
                break

        # PPO update
        update_info = self._ppo_update()

        ep_info = {
            "rounds": len(self.buffer),
            "avg_delivery": np.mean(step_deliveries) if step_deliveries else 0,
            "avg_trace": np.mean(step_traces) if step_traces else 0,
            "avg_energy": np.mean(step_energies) if step_energies else 0,
            **update_info,
        }

        return total_reward, ep_info

    # ────────────────── PPO update ──────────────────

    def _ppo_update(self) -> Dict[str, float]:
        """Perform multiple PPO epochs on the collected buffer."""
        if len(self.buffer) < 2:
            return {"policy_loss": 0, "value_loss": 0, "entropy": 0}

        gamma = self.hp["gamma"]
        lam = self.hp["gae_lambda"]
        clip_eps = self.hp["clip_eps"]
        ent_coeff = self.hp["entropy_coeff"]
        val_coeff = self.hp["value_coeff"]
        max_grad = self.hp["max_grad_norm"]

        # Compute GAE
        rewards = self.buffer.rewards
        values_list = [v.item() if isinstance(v, torch.Tensor) else v for v in self.buffer.values]
        dones = self.buffer.dones

        advantages, returns = compute_gae(rewards, values_list, dones, gamma, lam)
        advantages_t = torch.tensor(advantages, dtype=torch.float32)
        returns_t = torch.tensor(returns, dtype=torch.float32)

        # Normalise advantages
        if len(advantages_t) > 1:
            advantages_t = (advantages_t - advantages_t.mean()) / (advantages_t.std() + 1e-8)

        # Flatten buffer for mini-batch updates
        old_log_probs = torch.stack([lp.mean() for lp in self.buffer.log_probs])

        total_pg_loss = 0.0
        total_v_loss = 0.0
        total_ent = 0.0
        n_updates = 0

        k = min(self.hp["max_paths"], 3)

        for _ in range(self.hp["ppo_epochs"]):
            for t in range(len(self.buffer)):
                obs_t = self.buffer.obs[t]
                act_t = self.buffer.actions[t]

                # Re-evaluate under current policy
                dist, new_values = self.agent.network(obs_t, k)

                # Clamp actions to valid simplex range for log_prob
                act_clamped = torch.clamp(act_t, 1e-6, 1.0 - 1e-6)
                act_clamped = act_clamped / act_clamped.sum(dim=-1, keepdim=True)

                new_log_probs = dist.log_prob(act_clamped)
                entropy = dist.entropy()

                # Per-agent mean
                new_lp_mean = new_log_probs.mean()
                entropy_mean = entropy.mean()
                value_mean = new_values.squeeze(-1).mean()

                # Ratio
                ratio = torch.exp(new_lp_mean - old_log_probs[t].detach())

                # Clipped surrogate
                adv = advantages_t[t]
                surr1 = ratio * adv
                surr2 = torch.clamp(ratio, 1 - clip_eps, 1 + clip_eps) * adv
                policy_loss = -torch.min(surr1, surr2)

                # Value loss
                value_loss = val_coeff * (returns_t[t] - value_mean).pow(2)

                # Total loss
                loss = policy_loss + value_loss - ent_coeff * entropy_mean

                self.agent.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    self.agent.network.parameters(), max_grad
                )
                self.agent.optimizer.step()

                total_pg_loss += policy_loss.item()
                total_v_loss += value_loss.item()
                total_ent += entropy_mean.item()
                n_updates += 1

        n = max(n_updates, 1)
        return {
            "policy_loss": total_pg_loss / n,
            "value_loss": total_v_loss / n,
            "entropy": total_ent / n,
        }

    # ────────────────── utilities ──────────────────

    def _save_history(self):
        """Save training history to JSON."""
        path = os.path.join(self.log_dir, "training_history.json")
        # Convert numpy/tensor types to plain Python
        clean = {}
        for k, v in self.history.items():
            clean[k] = [
                float(x) if isinstance(x, (np.floating, torch.Tensor)) else x
                for x in v
            ]
        with open(path, "w") as f:
            json.dump(clean, f, indent=2)
