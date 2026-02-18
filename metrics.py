"""
Metrics Module - Performance tracking and visualization
"""

import os
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Tuple
from collections import defaultdict
from config import OUTPUT_DIR, MissionPhase


class MetricsCollector:
    """Collects and tracks simulation metrics"""
    
    def __init__(self):
        self.round_metrics: List[Dict] = []
        self.phase_metrics: Dict[str, List] = defaultdict(list)
        self.battery_history: List[List[float]] = []
        self.latency_history: List[float] = []
        self.trace_history: List[bool] = []
        self.relay_usage_history: List[Dict[int, int]] = []
        
    def record_round(self, round_num: int, phase: str, 
                     battery_stats: Dict, messages_sent: int,
                     dummy_messages: int,
                     trace_success_rate: float, avg_latency: float):
        """Record metrics for a simulation round"""
        round_data = {
            "round": round_num,
            "phase": phase,
            "battery_mean": battery_stats["mean"],
            "battery_min": battery_stats["min"],
            "active_drones": battery_stats["active_count"],
            "messages_sent": messages_sent,
            "dummy_messages": dummy_messages,
            "trace_success_rate": trace_success_rate,
            "avg_latency": avg_latency
        }
        
        self.round_metrics.append(round_data)
        self.phase_metrics[phase].append(round_data)
        
    def record_battery_snapshot(self, batteries: List[float]):
        """Record battery levels for all drones"""
        self.battery_history.append(batteries.copy())
        
    def record_latency(self, latency: float):
        """Record message latency"""
        self.latency_history.append(latency)
        
    def record_trace_result(self, success: bool):
        """Record adversary trace attempt result"""
        self.trace_history.append(success)
        
    def record_relay_usage(self, usage_dict: Dict[int, int]):
        """Record relay usage distribution"""
        self.relay_usage_history.append(usage_dict.copy())
        
    def get_swarm_lifetime(self) -> int:
        """Get number of rounds until critical drone count"""
        for i, metrics in enumerate(self.round_metrics):
            if metrics["active_drones"] < 25:  # Below 50%
                return i
        return len(self.round_metrics)
    
    def get_energy_efficiency(self) -> float:
        """Calculate energy efficiency (messages per % battery)"""
        if not self.round_metrics:
            return 0.0
            
        total_messages = sum(m["messages_sent"] for m in self.round_metrics)
        initial_battery = 100.0 * 50  # 50 drones at 100%
        final_battery = self.round_metrics[-1]["battery_mean"] * 50
        battery_used = initial_battery - final_battery
        
        return total_messages / battery_used if battery_used > 0 else 0
    
    def get_privacy_effectiveness(self) -> Dict[str, float]:
        """Calculate privacy effectiveness per phase"""
        phase_trace_rates = {}
        
        for phase, metrics in self.phase_metrics.items():
            if metrics:
                avg_trace = sum(m["trace_success_rate"] for m in metrics) / len(metrics)
                # Lower trace rate = better privacy = higher effectiveness
                phase_trace_rates[phase] = 1 - avg_trace
                
        return phase_trace_rates
    
    def get_summary_stats(self) -> Dict:
        """Get comprehensive summary statistics"""
        if not self.round_metrics:
            return {}
            
        return {
            "total_rounds": len(self.round_metrics),
            "swarm_lifetime": self.get_swarm_lifetime(),
            "final_active_drones": self.round_metrics[-1]["active_drones"],
            "total_messages": sum(m["messages_sent"] for m in self.round_metrics),
            "avg_latency": sum(self.latency_history) / len(self.latency_history) if self.latency_history else 0,
            "overall_trace_rate": sum(self.trace_history) / len(self.trace_history) if self.trace_history else 0,
            "energy_efficiency": self.get_energy_efficiency(),
            "privacy_effectiveness": self.get_privacy_effectiveness()
        }


class RelayFairnessAnalyzer:
    """Analyzes fairness of relay selection"""
    
    @staticmethod
    def calculate_gini(values: List[float]) -> float:
        """Calculate Gini coefficient (0 = perfect equality, 1 = maximum inequality)"""
        if not values or sum(values) == 0:
            return 0.0
            
        n = len(values)
        sorted_values = sorted(values)
        
        cumsum = np.cumsum(sorted_values)
        return (2 * sum((i + 1) * v for i, v in enumerate(sorted_values)) / 
                (n * sum(sorted_values))) - (n + 1) / n
    
    @staticmethod
    def analyze_distribution(usage_counts: List[int]) -> Dict:
        """Analyze usage distribution statistics"""
        if not usage_counts:
            return {"gini": 0, "cv": 0, "max_min_ratio": 0}
            
        mean = np.mean(usage_counts)
        std = np.std(usage_counts)
        
        return {
            "gini": RelayFairnessAnalyzer.calculate_gini(usage_counts),
            "cv": std / mean if mean > 0 else 0,  # Coefficient of variation
            "max_min_ratio": max(usage_counts) / min(usage_counts) if min(usage_counts) > 0 else float('inf'),
            "mean": mean,
            "std": std
        }


class GraphGenerator:
    """Generates visualization graphs for metrics"""
    
    def __init__(self, output_dir: str = OUTPUT_DIR):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def plot_battery_distribution(self, battery_history: List[List[float]], 
                                   save_name: str = "battery_distribution.png"):
        """Plot battery level distribution over time"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # Left: Battery over time for sample drones
        ax1 = axes[0]
        sample_indices = [0, 10, 25, 40, 49]  # Sample drones
        for idx in sample_indices:
            if idx < len(battery_history[0]):
                drone_batteries = [round_b[idx] for round_b in battery_history]
                ax1.plot(drone_batteries, label=f'Drone {idx}', alpha=0.7)
        
        ax1.set_xlabel('Simulation Round')
        ax1.set_ylabel('Battery Level (%)')
        ax1.set_title('Battery Depletion Over Time (Sample Drones)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Right: Battery distribution at key points
        ax2 = axes[1]
        checkpoints = [0, len(battery_history)//4, len(battery_history)//2, 
                       3*len(battery_history)//4, len(battery_history)-1]
        checkpoints = [c for c in checkpoints if c < len(battery_history)]
        
        for cp in checkpoints:
            ax2.hist(battery_history[cp], bins=20, alpha=0.5, 
                    label=f'Round {cp}')
        
        ax2.set_xlabel('Battery Level (%)')
        ax2.set_ylabel('Number of Drones')
        ax2.set_title('Battery Distribution at Different Points')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=150)
        plt.close()
        
    def plot_privacy_energy_tradeoff(self, phase_metrics: Dict[str, List],
                                      save_name: str = "privacy_energy_tradeoff.png"):
        """Plot privacy vs energy consumption tradeoff"""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        phases = [MissionPhase.PATROL, MissionPhase.SURVEILLANCE, MissionPhase.THREAT]
        colors = ['green', 'orange', 'red']
        
        for phase, color in zip(phases, colors):
            if phase in phase_metrics and phase_metrics[phase]:
                metrics = phase_metrics[phase]
                
                # Calculate privacy (1 - trace rate) and energy consumption
                privacy_scores = [1 - m["trace_success_rate"] for m in metrics]
                battery_drops = []
                for i, m in enumerate(metrics):
                    if i > 0:
                        battery_drop = metrics[i-1]["battery_mean"] - m["battery_mean"]
                        battery_drops.append(max(0, battery_drop))
                    else:
                        battery_drops.append(0)
                
                if len(privacy_scores) > 1:
                    ax.scatter(battery_drops[1:], privacy_scores[1:], 
                              c=color, label=phase, alpha=0.6, s=50)
        
        ax.set_xlabel('Energy Consumption per Round (%)')
        ax.set_ylabel('Privacy Score (1 - Trace Rate)')
        ax.set_title('Privacy-Energy Tradeoff by Mission Phase')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=150)
        plt.close()
        
    def plot_trace_success_by_phase(self, round_metrics: List[Dict],
                                     save_name: str = "trace_success_by_phase.png"):
        """Plot adversary trace success rate by mission phase"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # Left: Trace rate over time
        ax1 = axes[0]
        rounds = [m["round"] for m in round_metrics]
        trace_rates = [m["trace_success_rate"] for m in round_metrics]
        phases = [m["phase"] for m in round_metrics]
        
        # Color by phase
        phase_colors = {
            MissionPhase.PATROL: 'green',
            MissionPhase.SURVEILLANCE: 'orange',
            MissionPhase.THREAT: 'red'
        }
        colors = [phase_colors.get(p, 'gray') for p in phases]
        
        ax1.scatter(rounds, trace_rates, c=colors, alpha=0.5, s=20)
        ax1.set_xlabel('Simulation Round')
        ax1.set_ylabel('Trace Success Rate')
        ax1.set_title('Adversary Trace Success Over Time')
        ax1.grid(True, alpha=0.3)
        
        # Right: Average by phase (bar chart)
        ax2 = axes[1]
        phase_avgs = {}
        for phase in [MissionPhase.PATROL, MissionPhase.SURVEILLANCE, MissionPhase.THREAT]:
            phase_metrics_list = [m["trace_success_rate"] for m in round_metrics if m["phase"] == phase]
            if phase_metrics_list:
                phase_avgs[phase] = sum(phase_metrics_list) / len(phase_metrics_list)
                
        if phase_avgs:
            phases_list = list(phase_avgs.keys())
            avgs = list(phase_avgs.values())
            colors_list = [phase_colors.get(p, 'gray') for p in phases_list]
            
            bars = ax2.bar(phases_list, avgs, color=colors_list, alpha=0.7)
            ax2.set_ylabel('Average Trace Success Rate')
            ax2.set_title('Privacy Vulnerability by Mission Phase')
            ax2.set_ylim(0, 1)
            
            # Add value labels
            for bar, avg in zip(bars, avgs):
                ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                        f'{avg:.2f}', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=150)
        plt.close()
        
    def plot_relay_fairness(self, usage_counts: List[int],
                            save_name: str = "relay_fairness.png"):
        """Plot relay usage distribution"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # Left: Usage histogram
        ax1 = axes[0]
        ax1.hist(usage_counts, bins=20, color='steelblue', alpha=0.7, edgecolor='black')
        ax1.axvline(np.mean(usage_counts), color='red', linestyle='--', 
                   label=f'Mean: {np.mean(usage_counts):.1f}')
        ax1.set_xlabel('Relay Usage Count')
        ax1.set_ylabel('Number of Drones')
        ax1.set_title('Distribution of Relay Usage Across Drones')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Right: Lorenz curve for fairness
        ax2 = axes[1]
        sorted_usage = np.sort(usage_counts)
        cumsum = np.cumsum(sorted_usage)
        cumsum = cumsum / cumsum[-1]  # Normalize
        x = np.linspace(0, 1, len(cumsum))
        
        ax2.plot(x, cumsum, 'b-', linewidth=2, label='Lorenz Curve')
        ax2.plot([0, 1], [0, 1], 'r--', label='Perfect Equality')
        ax2.fill_between(x, cumsum, x, alpha=0.2)
        
        gini = RelayFairnessAnalyzer.calculate_gini(usage_counts)
        ax2.set_xlabel('Cumulative % of Drones')
        ax2.set_ylabel('Cumulative % of Relay Usage')
        ax2.set_title(f'Relay Usage Fairness (Gini: {gini:.3f})')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=150)
        plt.close()
        
    def plot_swarm_lifetime(self, round_metrics: List[Dict],
                            save_name: str = "swarm_lifetime.png"):
        """Plot swarm operational status over time"""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        rounds = [m["round"] for m in round_metrics]
        active = [m["active_drones"] for m in round_metrics]
        battery_mean = [m["battery_mean"] for m in round_metrics]
        
        ax.plot(rounds, active, 'b-', linewidth=2, label='Active Drones')
        ax.axhline(25, color='red', linestyle='--', alpha=0.7, label='50% Threshold')
        
        ax2 = ax.twinx()
        ax2.plot(rounds, battery_mean, 'g-', linewidth=2, alpha=0.7, label='Mean Battery')
        ax2.set_ylabel('Mean Battery Level (%)', color='green')
        
        ax.set_xlabel('Simulation Round')
        ax.set_ylabel('Active Drones', color='blue')
        ax.set_title('Swarm Lifetime and Battery Status')
        
        # Combined legend
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
        
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=150)
        plt.close()
        
    def plot_latency_by_phase(self, phase_metrics: Dict[str, List],
                              save_name: str = "latency_by_phase.png"):
        """Plot average latency by mission phase"""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        phases = [MissionPhase.PATROL, MissionPhase.SURVEILLANCE, MissionPhase.THREAT]
        colors = ['green', 'orange', 'red']
        avg_latencies = []
        plot_phases = []
        
        for phase in phases:
            if phase in phase_metrics and phase_metrics[phase]:
                metrics = phase_metrics[phase]
                # Calculate simple average of latencies in this phase
                total_latency = sum(m["avg_latency"] for m in metrics)
                count = len(metrics)
                avg = total_latency / count if count > 0 else 0
                avg_latencies.append(avg)
                plot_phases.append(phase)
            else:
                avg_latencies.append(0)
                plot_phases.append(phase)
                
        bars = ax.bar(plot_phases, avg_latencies, color=colors, alpha=0.7)
        
        ax.set_ylabel('Average Latency (ms)')
        ax.set_title('Communication Latency by Mission Phase')
        ax.grid(axis='y', alpha=0.3)
        
        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f} ms',
                    ha='center', va='bottom')
            
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=150)
        plt.close()

    def plot_traffic_composition(self, round_metrics: List[Dict],
                                 save_name: str = "traffic_composition.png"):
        """Plot composition of real vs dummy traffic over time"""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        rounds = [m["round"] for m in round_metrics]
        real_msgs = [m["messages_sent"] for m in round_metrics]
        dummy_msgs = [m.get("dummy_messages", 0) for m in round_metrics]
        
        # Stackplot
        ax.stackplot(rounds, real_msgs, dummy_msgs, 
                     labels=['Real Messages', 'Dummy Traffic'],
                     colors=['#3498db', '#95a5a6'], alpha=0.8)
        
        ax.set_xlabel('Simulation Round')
        ax.set_ylabel('Messages per Round')
        ax.set_title('Network Traffic Composition: Real vs Dummy')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=150)
        plt.close()

    def plot_energy_consumption_rate(self, phase_metrics: Dict[str, List],
                                     save_name: str = "energy_consumption_rate.png"):
        """Plot energy consumption rate per round by phase"""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        phases = [MissionPhase.PATROL, MissionPhase.SURVEILLANCE, MissionPhase.THREAT]
        colors = ['green', 'orange', 'red']
        consumption_rates = []
        plot_phases = []
        
        for phase in phases:
            if phase in phase_metrics and phase_metrics[phase]:
                metrics = phase_metrics[phase]
                if len(metrics) < 2:
                    consumption_rates.append(0)
                    plot_phases.append(phase)
                    continue
                    
                # Calculate total drop in this phase
                start_battery = metrics[0]["battery_mean"]
                end_battery = metrics[-1]["battery_mean"]
                total_drop = start_battery - end_battery
                
                # Rate per round
                rate = total_drop / len(metrics) if len(metrics) > 0 else 0
                consumption_rates.append(rate)
                plot_phases.append(phase)
            else:
                consumption_rates.append(0)
                plot_phases.append(phase)
                
        bars = ax.bar(plot_phases, consumption_rates, color=colors, alpha=0.7)
        
        ax.set_ylabel('Avg Battery Drain per Round (%)')
        ax.set_title('Energy Consumption Rate by Mission Phase')
        ax.grid(axis='y', alpha=0.3)
        
        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}%',
                    ha='center', va='bottom')
            
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=150)
        plt.close()

    def generate_all_plots(self, metrics: MetricsCollector, relay_usage: List[int]):
        """Generate all visualization plots"""
        print("Generating visualization plots...")
        
        if metrics.battery_history:
            self.plot_battery_distribution(metrics.battery_history)
            print("  ✓ Battery distribution plot")
            
        if metrics.phase_metrics:
            self.plot_privacy_energy_tradeoff(metrics.phase_metrics)
            print("  ✓ Privacy-energy tradeoff plot")
            
            # New plots requiring phase metrics
            self.plot_latency_by_phase(metrics.phase_metrics)
            print("  ✓ Latency by phase plot")
            
            self.plot_energy_consumption_rate(metrics.phase_metrics)
            print("  ✓ Energy consumption rate plot")
            
        if metrics.round_metrics:
            self.plot_trace_success_by_phase(metrics.round_metrics)
            print("  ✓ Trace success by phase plot")
            
            self.plot_swarm_lifetime(metrics.round_metrics)
            print("  ✓ Swarm lifetime plot")
            
            # New plots requiring round metrics
            self.plot_traffic_composition(metrics.round_metrics)
            print("  ✓ Traffic composition plot")
            
        if relay_usage:
            self.plot_relay_fairness(relay_usage)
            print("  ✓ Relay fairness plot")
            
        print(f"\nAll plots saved to: {self.output_dir}/")
