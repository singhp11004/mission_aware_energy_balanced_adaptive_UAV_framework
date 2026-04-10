"""
Z-MAPS Main Framework — Mission-Aware Privacy Framework with IPPO-DM

The original legacy simulation wrapper has been deleted.
This is the default execution entrypoint utilizing the 4-layer tactical architecture
and Noise-Free Random Segmentation with Dijkstra Routing.
"""

import os
import random
import time
import argparse
import subprocess
import sys

from config import (
    NUM_DRONES, SIMULATION_ROUNDS, MESSAGES_PER_ROUND,
    PHASE_CHANGE_INTERVAL, COOLDOWN_DURATION, MissionPhase, OUTPUT_DIR
)
from swarm import UAVSwarm
from energy_model import EnergyModel, BatteryManager
from security import SecurityManager
from adversary import Adversary
from relay_selector import RelaySelector
from crypto_engine import CryptoEngine
from metrics import MetricsCollector, GraphGenerator

from zmaps.mission.phases import PhaseSequencer, to_legacy_phase
from zmaps.layers.data_acquisition import DataAcquisitionLayer
from zmaps.layers.prioritization import PrioritizationLayer
from zmaps.layers.communication import CommunicationLayer
from zmaps.layers.toc_integration import TOCIntegrationLayer
from zmaps.routing.multipath import MultipathRouter


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Z-MAPS: Mission-Aware Privacy Framework for UAV Swarms"
    )
    parser.add_argument(
        "--mode", choices=["eval", "train"], default="eval",
        help="Execution mode: eval (Z-MAPS + IPPO), train (train IPPO)"
    )
    parser.add_argument("--rounds", type=int, default=SIMULATION_ROUNDS)
    parser.add_argument("--drones", type=int, default=NUM_DRONES)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="Path to IPPO checkpoint for eval mode")
    args = parser.parse_args()

    random.seed(args.seed)

    if args.mode == "train":
        print("Delegating to train_ippo.py...")
        subprocess.run([sys.executable, "train_ippo.py",
                        "--drones", str(args.drones),
                        "--seed", str(args.seed)])
        return

    _run_zmaps_framework(args)


def _run_zmaps_framework(args):
    """Run the simulation using the Z-MAPS layered architecture."""
    print("=" * 60)
    print(" Z-MAPS: Zero-Knowledge Multi-Agent RL Framework")
    print(" for Mission-Aware Privacy")
    print("=" * 60)
    print()

    # Try loading IPPO agent
    ippo_agent = None
    ckpt_path = args.checkpoint or "outputs/checkpoints/ippo_final.pt"
    if os.path.isfile(ckpt_path):
        try:
            from zmaps.routing.ippo_agent import IPPOAgent
            ippo_agent = IPPOAgent()
            ippo_agent.load(ckpt_path)
            print(f"  ✓ Loaded IPPO checkpoint: {ckpt_path}")
        except Exception as e:
            print(f"  ⚠ Could not load IPPO checkpoint: {e}")
            ippo_agent = None
    else:
        print(f"  ⚠ No IPPO checkpoint found at {ckpt_path} — using uniform splits")

    # Init simulation components
    swarm = UAVSwarm(args.drones)
    energy = EnergyModel()
    battery = BatteryManager(energy)
    security = SecurityManager()
    adversary = Adversary()
    
    # NEW: provide swarm graph parameter for Dijkstra
    relay_sel = RelaySelector(swarm)
    crypto = CryptoEngine(args.drones)
    metrics = MetricsCollector()
    graph_gen = GraphGenerator(OUTPUT_DIR)

    # Z-MAPS layers
    router = MultipathRouter(agent=ippo_agent)
    l1 = DataAcquisitionLayer()
    l2 = PrioritizationLayer()
    l3 = CommunicationLayer(
        security=security, crypto=crypto, energy_model=energy,
        battery_mgr=battery, relay_selector=relay_sel,
        adversary=adversary, multipath_router=router,
    )
    l4 = TOCIntegrationLayer(swarm.command_server)
    sequencer = PhaseSequencer()

    print(f"  ✓ Swarm: {args.drones} drones, {swarm.network.number_of_edges()} links")
    print(f"  ✓ Z-MAPS layers initialized (4-layer stack)")
    print(f"  ✓ Multipath router: {'IPPO-DM' if ippo_agent else 'Uniform'}")
    print()
    print(f"Running Z-MAPS evaluation for {args.rounds} rounds...")
    print("-" * 60)

    t0 = time.time()
    total_msgs = 0
    total_dummy = 0

    for rnd in range(1, args.rounds + 1):
        adversary.set_round(rnd)
        swarm.update_round()
        sequencer.tick()

        if rnd > 1 and rnd % PHASE_CHANGE_INTERVAL == 0:
            old = sequencer.current
            sequencer.advance()
            print(f"\n📡 Round {rnd}: {old.label} → {sequencer.current.label}")

        phase = sequencer.current
        legacy_phase = to_legacy_phase(phase)
        swarm.set_mission_phase(legacy_phase)

        active = swarm.get_active_drones()
        if len(active) < 3:
            print(f"\n⚠ Swarm below operational threshold at round {rnd}")
            break

        senders = random.sample(active, min(MESSAGES_PER_ROUND, len(active)))
        round_sent = 0
        round_traces = 0
        round_dummy = 0
        round_latency_ms = 0.0

        for sender in senders:
            payload = f"Telemetry from Drone {sender.drone_id} at round {rnd} containing critical surveillance data for processing."
            
            # Layer 1 Data Acquisition: apply noise-free random segmentation chunking.
            # This returns multiple packet chunks from the single payload.
            packets = l1.collect(sender.drone_id, payload, phase)
            
            for packet in packets:
                # Layer 2 Prioritization
                pri_msg = l2.prioritize(packet)

                # In eval mode, inject a small inline router adapter right before transmit
                if ippo_agent is not None:
                    state_vec = swarm.get_drone_state_vector(sender.drone_id)
                    class _EvalRouterWrapper:
                        def __init__(self, r, v): self.r = r; self.v = v
                        def get_split_ratios(self, sender_id, num_paths, phase):
                            return self.r.get_split_ratios(sender_id, num_paths, phase, state_vector=self.v)
                        def get_stats(self): return self.r.get_stats()
                    l3.multipath_router = _EvalRouterWrapper(router, state_vec)

                available = swarm.get_available_relays(exclude_ids=[sender.drone_id])
                
                # Layer 3 Communication Network
                result = l3.transmit(pri_msg, sender, available, rnd, COOLDOWN_DURATION)
                
                if ippo_agent is not None:
                    l3.multipath_router = router # restore

                msg_dict = security.create_secure_message(
                    sender.drone_id, "CMD", packet.payload, 1
                ).to_dict()
                
                # Layer 4 TOC Integration
                result = l4.deliver(result, msg_dict, rnd)

                round_sent += 1
                if result.traced:
                    round_traces += 1

                if result.dummy_injected:
                    total_dummy += 1
                    round_dummy += 1
                    
                round_latency_ms += result.latency_ms

        total_msgs += round_sent
        bat = swarm.get_battery_stats()

        trace_rate = round_traces / round_sent if round_sent else 0
        avg_lat = round_latency_ms / round_sent if round_sent else 0.0
        
        metrics.record_round(
            rnd, phase.name.title(), bat, round_sent, round_dummy, trace_rate, avg_lat
        )
        if avg_lat > 0:
            metrics.record_latency(avg_lat)
        
        metrics.record_battery_snapshot(
            [d.battery_level for d in swarm.drones.values()]
        )

        if rnd % 10 == 0:
            print(f"  Round {rnd}: Active={bat['active_count']}, "
                  f"AvgBat={bat['mean']:.1f}%, Phase={phase.label}")

    elapsed = time.time() - t0
    print("-" * 60)
    print(f"Z-MAPS evaluation completed in {elapsed:.2f}s")

    # Report
    print()
    print("=" * 60)
    print("Z-MAPS RESULTS")
    print("=" * 60)

    toc_stats = l4.get_cumulative_stats()
    comm_stats = l3.get_stats()
    router_stats = router.get_stats()
    pri_stats = l2.get_stats()

    print(f"\n📊 Overview:")
    print(f"  • Total messages (chunks): {total_msgs}")
    print(f"  • Delivery rate: {toc_stats['delivery_rate']:.2%}")
    print(f"  • Trace rate: {toc_stats['trace_rate']:.2%}")
    print(f"  • Multipath transmissions: {comm_stats['multipath_transmissions']}")
    print(f"  • Multipath rate: {comm_stats['multipath_rate']:.2%}")

    print(f"\n🧠 Prioritization:")
    print(f"  • Messages prioritized: {pri_stats['messages_prioritized']}")
    print(f"  • Enhanced (high priority): {pri_stats['enhanced_count']} ({pri_stats['enhancement_rate']:.1%})")

    if router_stats.get('total_splits', 0) > 0:
        print(f"\n🔀 Multipath Router:")
        print(f"  • Total splits: {router_stats['total_splits']}")
        print(f"  • Agent used: {router_stats.get('agent_used_rate', 0):.1%}")

    # Generate plots
    usage_counts = [d.relay_usage_count for d in swarm.drones.values()]
    graph_gen.generate_all_plots(metrics, usage_counts)

    print(f"\nOutput saved to: {OUTPUT_DIR}/")
    print("=" * 60)

if __name__ == "__main__":
    main()
