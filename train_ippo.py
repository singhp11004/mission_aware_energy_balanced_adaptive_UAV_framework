#!/usr/bin/env python3
"""
IPPO-DM Training Script — Z-MAPS Multipath Routing

Trains the Independent PPO agent with Dirichlet Modeling for
traffic-adaptive multipath routing in the UAV swarm.

Usage:
    python train_ippo.py                         # full training (500 episodes)
    python train_ippo.py --episodes 100          # short run
    python train_ippo.py --episodes 50 --lr 1e-3 # custom LR
    python train_ippo.py --resume outputs/checkpoints/ippo_ep200.pt

Output:
    outputs/checkpoints/ippo_final.pt            # trained model
    outputs/training/training_history.json        # training curves
"""

import argparse
import os
import sys
import random

import numpy as np

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from zmaps.routing.trainer import IPPOTrainer
from zmaps.routing.ippo_agent import DEFAULT_HPARAMS


def main():
    parser = argparse.ArgumentParser(
        description="Z-MAPS IPPO-DM Training — Multipath Routing Agent"
    )
    parser.add_argument(
        "--episodes", type=int, default=500,
        help="Number of training episodes (default: 500)"
    )
    parser.add_argument(
        "--max-steps", type=int, default=100,
        help="Max rounds per episode (default: 100)"
    )
    parser.add_argument(
        "--lr", type=float, default=None,
        help="Learning rate (default: 3e-4)"
    )
    parser.add_argument(
        "--drones", type=int, default=50,
        help="Number of drones in the swarm (default: 50)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)"
    )
    parser.add_argument(
        "--checkpoint-dir", type=str, default="outputs/checkpoints",
        help="Directory for model checkpoints"
    )
    parser.add_argument(
        "--log-dir", type=str, default="outputs/training",
        help="Directory for training logs"
    )
    parser.add_argument(
        "--checkpoint-interval", type=int, default=50,
        help="Save checkpoint every N episodes (default: 50)"
    )
    parser.add_argument(
        "--resume", type=str, default=None,
        help="Path to checkpoint to resume training from"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress verbose output"
    )

    args = parser.parse_args()

    # Set seeds
    random.seed(args.seed)
    np.random.seed(args.seed)

    import torch
    torch.manual_seed(args.seed)

    # Build hyperparameters
    hparams = dict(DEFAULT_HPARAMS)
    if args.lr is not None:
        hparams["lr"] = args.lr

    # Create trainer
    trainer = IPPOTrainer(
        num_drones=args.drones,
        hparams=hparams,
        checkpoint_dir=args.checkpoint_dir,
        log_dir=args.log_dir,
    )

    # Resume from checkpoint if requested
    if args.resume:
        if os.path.isfile(args.resume):
            print(f"📂 Resuming from checkpoint: {args.resume}")
            trainer.agent.load(args.resume)
        else:
            print(f"⚠️  Checkpoint not found: {args.resume} — training from scratch")

    # Train
    history = trainer.train(
        num_episodes=args.episodes,
        max_steps=args.max_steps,
        checkpoint_interval=args.checkpoint_interval,
        verbose=not args.quiet,
    )

    # Summary
    if not args.quiet:
        print("\n📊 Training Summary:")
        print(f"  Final reward:        {history['reward'][-1]:+.3f}")
        print(f"  Final delivery rate: {history['delivery_rate'][-1]:.2%}")
        print(f"  Final trace rate:    {history['trace_rate'][-1]:.2%}")
        print(f"  Policy loss:         {history['policy_loss'][-1]:.6f}")
        print(f"  Value loss:          {history['value_loss'][-1]:.6f}")


if __name__ == "__main__":
    main()
