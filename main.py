"""
Main Simulation Module - UAV Swarm Privacy Framework
Mission-Aware Energy-Balanced Adaptive Privacy Framework for UAV Swarm Communication
"""

import random
import time
from typing import Dict, List

from config import (
    NUM_DRONES, SIMULATION_ROUNDS, MESSAGES_PER_ROUND,
    PHASE_CHANGE_INTERVAL, COOLDOWN_DURATION, MissionPhase, OUTPUT_DIR
)
from swarm import UAVSwarm
from energy_model import EnergyModel, BatteryManager
from security import SecurityManager
from privacy_controller import PrivacyController, RoutingPolicy, DummyTrafficGenerator, MissionManager
from relay_selector import RelaySelector, LoadBalancer
from adversary import Adversary
from metrics import MetricsCollector, GraphGenerator


class UAVSimulation:
    """Main simulation orchestrator"""
    
    def __init__(self, num_drones: int = NUM_DRONES):
        print("=" * 60)
        print("Mission-Aware Energy-Balanced Adaptive Privacy Framework")
        print("for UAV Swarm Communication")
        print("=" * 60)
        print()
        
        # Initialize components
        print("Initializing simulation components...")
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
        self.metrics = MetricsCollector()
        self.graph_gen = GraphGenerator(OUTPUT_DIR)
        
        # Simulation state
        self.current_round = 0
        self.total_messages_sent = 0
        self.total_dummy_messages = 0
        
        print(f"  ✓ Initialized swarm with {num_drones} drones")
        print(f"  ✓ Network connectivity: {self.swarm.network.number_of_edges()} links")
        print()
        
    def run_simulation(self, num_rounds: int = SIMULATION_ROUNDS):
        """Run the complete simulation"""
        print(f"Starting simulation for {num_rounds} rounds...")
        print("-" * 60)
        
        start_time = time.time()
        
        for round_num in range(num_rounds):
            self.current_round = round_num
            
            # Check if swarm is still operational
            if not self.swarm.is_operational(min_active_ratio=0.3):
                print(f"\n⚠ Swarm below operational threshold at round {round_num}")
                break
                
            # Phase transitions
            if round_num > 0 and round_num % PHASE_CHANGE_INTERVAL == 0:
                old_phase = self.privacy.current_phase
                new_phase = self.mission_manager.transition_to_next_phase()
                self.swarm.set_mission_phase(new_phase)
                print(f"\n📡 Round {round_num}: Phase transition {old_phase} → {new_phase}")
                
            # Execute round
            round_stats = self._execute_round(round_num)
            
            # Collect metrics
            self._collect_round_metrics(round_num, round_stats)
            
            # Progress update every 10 rounds
            if (round_num + 1) % 10 == 0:
                stats = self.swarm.get_battery_stats()
                print(f"  Round {round_num + 1}: Active={stats['active_count']}, "
                      f"AvgBattery={stats['mean']:.1f}%, Phase={self.privacy.current_phase}")
                      
        elapsed = time.time() - start_time
        print("-" * 60)
        print(f"Simulation completed in {elapsed:.2f} seconds")
        print()
        
        # Generate final reports
        self._generate_final_report()
        
    def _execute_round(self, round_num: int) -> Dict:
        """Execute a single simulation round"""
        round_stats = {
            "messages_sent": 0,
            "dummy_messages": 0,
            "successful_traces": 0,
            "total_latency": 0
        }
        
        # Update swarm state
        self.swarm.update_round()
        
        # Get configuration for current phase
        phase_config = self.privacy.get_phase_config()
        routing_depth = phase_config["routing_depth"]
        encryption_rounds = phase_config["encryption_rounds"]
        
        # Select random senders for this round
        active_drones = self.swarm.get_active_drones()
        if len(active_drones) < 3:
            return round_stats
            
        senders = random.sample(active_drones, min(MESSAGES_PER_ROUND, len(active_drones)))
        
        for sender in senders:
            # Send real message
            latency = self._send_message(sender, routing_depth, encryption_rounds)
            if latency > 0:
                round_stats["messages_sent"] += 1
                round_stats["total_latency"] += latency
                
            # Maybe inject dummy traffic
            if self.privacy.should_inject_dummy():
                self._send_dummy_message(sender)
                round_stats["dummy_messages"] += 1
                
        self.total_messages_sent += round_stats["messages_sent"]
        self.total_dummy_messages += round_stats["dummy_messages"]
        
        return round_stats
        
    def _send_message(self, sender, routing_depth: int, encryption_rounds: int) -> float:
        """Send a message from sender to command server through relays"""
        start_time = time.time()
        
        # Calculate energy cost for sender
        sender_cost = self.energy_model.calculate_message_cost(
            self.privacy.current_phase, is_sender=True
        )
        
        if not self.battery_manager.apply_energy_cost(sender, sender_cost, "send"):
            return 0  # Not enough battery
            
        sender.messages_sent += 1
        
        # Create secure message
        payload = f"Telemetry from Drone {sender.drone_id} at round {self.current_round}"
        message = self.security.create_secure_message(
            sender_id=sender.drone_id,
            receiver_id="CMD",
            payload=payload,
            encryption_rounds=encryption_rounds
        )
        
        # Select relay chain
        available_relays = self.swarm.get_available_relays(exclude_ids=[sender.drone_id])
        num_relays = min(routing_depth, len(available_relays))
        
        if num_relays > 0:
            relay_chain = self.relay_selector.select_relay_chain(
                available_relays, num_relays, source_id=sender.drone_id
            )
            
            # Process through relays
            for relay in relay_chain:
                relay_cost = self.energy_model.calculate_message_cost(
                    self.privacy.current_phase, is_sender=False
                )
                
                if not self.battery_manager.apply_energy_cost(relay, relay_cost, "relay"):
                    break
                    
                message = self.security.process_at_relay(message, relay.drone_id)
                relay.set_as_relay(COOLDOWN_DURATION)
                relay.messages_relayed += 1
                
        # Apply timing jitter
        jitter = self.privacy.apply_timing_jitter()
        
        # Adversary observation and trace attempt
        self.adversary.observe_transmission(message.to_dict())
        drone_ids = list(self.swarm.drones.keys())
        trace_result = self.adversary.attempt_trace(message.to_dict(), drone_ids)
        self.metrics.record_trace_result(trace_result["success"])
        
        # Deliver to command server
        self.swarm.command_server.receive_message(message.to_dict())
        
        latency = (time.time() - start_time) * 1000 + jitter * 1000  # ms
        self.metrics.record_latency(latency)
        
        return latency
        
    def _send_dummy_message(self, sender):
        """Generate and send dummy traffic"""
        dummy_cost = self.energy_model.calculate_dummy_cost()
        
        if self.battery_manager.apply_energy_cost(sender, dummy_cost, "dummy"):
            dummy = self.security.create_dummy_message(sender.drone_id)
            
            # Adversary sees dummy traffic too
            self.adversary.observe_transmission(dummy.to_dict())
            
    def _collect_round_metrics(self, round_num: int, round_stats: Dict):
        """Collect and record metrics for the round"""
        battery_stats = self.swarm.get_battery_stats()
        adversary_stats = self.adversary.get_statistics()
        
        avg_latency = (round_stats["total_latency"] / round_stats["messages_sent"] 
                       if round_stats["messages_sent"] > 0 else 0)
        
        self.metrics.record_round(
            round_num=round_num,
            phase=self.privacy.current_phase,
            battery_stats=battery_stats,
            messages_sent=round_stats["messages_sent"],
            trace_success_rate=adversary_stats["overall_success_rate"],
            avg_latency=avg_latency
        )
        
        # Record battery snapshot
        batteries = [d.battery_level for d in self.swarm.drones.values()]
        self.metrics.record_battery_snapshot(batteries)
        
    def _generate_final_report(self):
        """Generate final simulation report and visualizations"""
        print("=" * 60)
        print("SIMULATION RESULTS")
        print("=" * 60)
        
        # Summary statistics
        summary = self.metrics.get_summary_stats()
        
        print("\n📊 Overall Statistics:")
        print(f"  • Total rounds completed: {summary.get('total_rounds', 0)}")
        print(f"  • Estimated swarm lifetime: {summary.get('swarm_lifetime', 0)} rounds")
        print(f"  • Final active drones: {summary.get('final_active_drones', 0)}/{NUM_DRONES}")
        print(f"  • Total messages sent: {summary.get('total_messages', 0)}")
        print(f"  • Total dummy messages: {self.total_dummy_messages}")
        print(f"  • Energy efficiency: {summary.get('energy_efficiency', 0):.2f} messages/% battery")
        
        # Adversary analysis
        adversary_stats = self.adversary.get_statistics()
        print("\n🔒 Privacy Analysis (Adversary Performance):")
        print(f"  • Overall trace success rate: {adversary_stats['overall_success_rate']:.2%}")
        
        privacy_eff = summary.get('privacy_effectiveness', {})
        for phase, effectiveness in privacy_eff.items():
            print(f"  • {phase} privacy effectiveness: {effectiveness:.2%}")
            
        # Trace success by hop count
        print("\n📈 Trace Success by Hop Count:")
        for hops, rate in sorted(adversary_stats.get('success_by_hops', {}).items()):
            print(f"  • {hops} hops: {rate:.2%} trace success")
            
        # Relay fairness
        usage_counts = [d.relay_usage_count for d in self.swarm.drones.values()]
        fairness = self.load_balancer.get_relay_fairness(list(self.swarm.drones.values()))
        
        print("\n⚖️ Relay Fairness:")
        print(f"  • Gini coefficient: {fairness['gini']:.3f} (lower = more fair)")
        print(f"  • Usage range: {fairness['min_usage']} - {fairness['max_usage']}")
        print(f"  • Standard deviation: {fairness['std_dev']:.2f}")
        
        # Generate graphs
        print("\n📉 Generating visualization graphs...")
        self.graph_gen.generate_all_plots(self.metrics, usage_counts)
        
        print("\n" + "=" * 60)
        print("Simulation completed successfully!")
        print(f"Output graphs saved to: {OUTPUT_DIR}/")
        print("=" * 60)


def main():
    """Main entry point"""
    # Set random seed for reproducibility
    random.seed(42)
    
    # Create and run simulation
    sim = UAVSimulation(num_drones=NUM_DRONES)
    sim.run_simulation(num_rounds=SIMULATION_ROUNDS)


if __name__ == "__main__":
    main()
