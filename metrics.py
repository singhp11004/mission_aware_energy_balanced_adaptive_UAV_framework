"""
Metrics Module - Performance tracking and visualization
"""

import os
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from typing import Dict, List, Tuple
from collections import defaultdict
from config import OUTPUT_DIR, OperationalPhase

# Apply sleek modern Seaborn theme
sns.set_theme(style="darkgrid", palette="deep")

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
    


class GraphGenerator:
    """Generates modern visualization graphs for evaluation metrics"""
    
    ZMAPS_PHASES = ["Transit", "Patrol", "Surveillance", "Engagement", "Recovery"]
    PHASE_COLORS = {
        "Transit": "#3498db",       # Blue
        "Patrol": "#2ecc71",        # Green
        "Surveillance": "#e67e22",  # Orange
        "Engagement": "#e74c3c",    # Red
        "Recovery": "#9b59b6"       # Purple
    }

    def __init__(self, output_dir: str = OUTPUT_DIR):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def _get_active_phases(self, phase_metrics: Dict) -> List[str]:
        return [p for p in self.ZMAPS_PHASES if p in phase_metrics and phase_metrics[p]]

    def plot_battery_distribution(self, battery_history: List[List[float]], save_name: str = "battery_distribution.png"):
        """Plot battery level distribution over time"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # Left: Battery over time
        ax1 = axes[0]
        sample_indices = [0, 10, 25, 40, 49]  
        for idx in sample_indices:
            if idx < len(battery_history[0]):
                drone_batteries = [round_b[idx] for round_b in battery_history]
                sns.lineplot(x=range(len(drone_batteries)), y=drone_batteries, ax=ax1, label=f'Drone {idx}', alpha=0.8)
        
        ax1.set_xlabel('Simulation Round')
        ax1.set_ylabel('Battery Level (%)')
        ax1.set_title('Battery Depletion (Sample Drones)')
        
        # Right: KDE Distribution at key points
        ax2 = axes[1]
        checkpoints = [max(0, len(battery_history)//4), 
                       max(0, len(battery_history)//2), 
                       max(0, len(battery_history)-1)]
        
        for cp in checkpoints:
            sns.kdeplot(battery_history[cp], ax=ax2, fill=True, label=f'Round {cp}', alpha=0.4)
            
        ax2.set_xlabel('Battery Level (%)')
        ax2.set_ylabel('Density')
        ax2.set_title('Swarm Battery Probability Density')
        ax2.legend()
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=200)
        plt.close()
        
    def plot_privacy_energy_tradeoff(self, phase_metrics: Dict[str, List], save_name: str = "privacy_energy_tradeoff.png"):
        """Plot privacy vs energy consumption tradeoff as a grouped bar chart."""
        import pandas as pd
        fig, ax = plt.subplots(figsize=(11, 6))

        active_phases = self._get_active_phases(phase_metrics)
        rows = []
        for phase in active_phases:
            metrics = phase_metrics[phase]
            avg_trace = sum(m["trace_success_rate"] for m in metrics) / len(metrics)
            privacy = 1.0 - avg_trace
            # energy: average battery drop per round in this phase
            if len(metrics) >= 2:
                energy = (metrics[0]["battery_mean"] - metrics[-1]["battery_mean"]) / len(metrics)
            else:
                energy = 0.0
            rows.append({"Phase": phase, "Privacy Effectiveness": privacy, "Energy Cost (%/round)": energy})

        df = pd.DataFrame(rows)
        x = np.arange(len(df))
        w = 0.35
        colors_priv = [self.PHASE_COLORS[p] for p in df["Phase"]]

        bars1 = ax.bar(x - w/2, df["Privacy Effectiveness"], w, label='Privacy Effectiveness',
                       color=colors_priv, alpha=0.85, edgecolor='white', linewidth=0.8)
        ax2 = ax.twinx()
        bars2 = ax2.bar(x + w/2, df["Energy Cost (%/round)"], w, label='Energy Cost (%/round)',
                        color='#34495e', alpha=0.6, edgecolor='white', linewidth=0.8)

        ax.set_xticks(x)
        ax.set_xticklabels(df["Phase"], fontweight='bold')
        ax.set_ylabel('Privacy Effectiveness (1 − Trace Rate)', fontweight='bold')
        ax.set_ylim(0, 1.15)
        ax2.set_ylabel('Energy Cost per Round (%)', fontweight='bold', color='#34495e')

        # Value labels
        for bar, val in zip(bars1, df["Privacy Effectiveness"]):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                    f'{val:.0%}', ha='center', va='bottom', fontweight='bold', fontsize=10)
        for bar, val in zip(bars2, df["Energy Cost (%/round)"]):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                     f'{val:.3f}%', ha='center', va='bottom', fontsize=9, color='#34495e')

        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=True)
        ax.set_title('Privacy vs Energy Cost Tradeoff by Mission Phase', fontsize=13, fontweight='bold')

        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=200)
        plt.close()
        
    def plot_trace_success_by_phase(self, round_metrics: List[Dict], save_name: str = "trace_success_by_phase.png"):
        """Plot adversary trace success over time + privacy effectiveness per phase."""
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))

        rounds = [m["round"] for m in round_metrics]
        trace_rates = [m["trace_success_rate"] for m in round_metrics]
        phases = [m["phase"] for m in round_metrics]
        colors = [self.PHASE_COLORS.get(p, '#95a5a6') for p in phases]

        # ── Left: scatter with phase-coloured background bands ──
        ax1 = axes[0]
        # Draw phase background bands
        phase_runs = []
        cur_phase = phases[0]
        start_r = rounds[0]
        for i in range(1, len(phases)):
            if phases[i] != cur_phase:
                phase_runs.append((cur_phase, start_r, rounds[i-1]))
                cur_phase = phases[i]
                start_r = rounds[i]
        phase_runs.append((cur_phase, start_r, rounds[-1]))
        for pname, r0, r1 in phase_runs:
            ax1.axvspan(r0 - 0.5, r1 + 0.5, alpha=0.10,
                        color=self.PHASE_COLORS.get(pname, '#95a5a6'))
            ax1.text((r0 + r1) / 2, 1.02, pname, ha='center', va='bottom',
                     fontsize=8, fontweight='bold',
                     color=self.PHASE_COLORS.get(pname, '#555'))

        ax1.scatter(rounds, trace_rates, c=colors, alpha=0.7, s=35, edgecolors='white', linewidths=0.4)
        ax1.set_xlabel('Mission Round')
        ax1.set_ylabel('Adversary Trace Success Rate')
        ax1.set_title('Trace Success Over Time')
        ax1.set_ylim(-0.05, 1.1)

        # ── Right: bar chart showing Privacy Effectiveness (1 - trace) ──
        ax2 = axes[1]
        active_phases = []
        effectiveness = []
        bar_colors = []
        for phase in self.ZMAPS_PHASES:
            rates = [m["trace_success_rate"] for m in round_metrics if m["phase"] == phase]
            if rates:
                active_phases.append(phase)
                effectiveness.append(1.0 - (sum(rates) / len(rates)))
                bar_colors.append(self.PHASE_COLORS[phase])

        if active_phases:
            import pandas as pd
            df = pd.DataFrame({"Phase": active_phases, "Privacy Effectiveness": effectiveness})
            bars = sns.barplot(data=df, x="Phase", y="Privacy Effectiveness",
                               hue="Phase", palette=self.PHASE_COLORS, legend=False, ax=ax2)
            ax2.set_ylabel('Privacy Effectiveness (1 − Trace Rate)')
            ax2.set_title('Privacy Strength by Phase')
            ax2.set_ylim(0, 1.15)

            for index, bar in enumerate(bars.patches):
                ax2.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.02,
                        f'{effectiveness[index]:.0%}', ha='center', va='bottom', fontweight='bold')

        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=200)
        plt.close()
        
    def plot_relay_fairness(self, usage_counts: List[int], save_name: str = "relay_fairness.png"):
        """Plot relay usage distribution and fairness curves"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        ax1 = axes[0]
        sns.histplot(usage_counts, bins=min(20, len(set(usage_counts))+1), color='#2980b9', kde=True, ax=ax1)
        mean_usage = np.mean(usage_counts)
        ax1.axvline(mean_usage, color='#e74c3c', linestyle='--', label=f'Mean: {mean_usage:.1f}')
        ax1.set_xlabel('Transmissions Relayed Count')
        ax1.set_ylabel('Number of UAVs')
        ax1.set_title('Load Distribution Across Nodes')
        ax1.legend()
        
        ax2 = axes[1]
        sorted_usage = np.sort(usage_counts)
        cumsum = np.cumsum(sorted_usage)
        if cumsum[-1] > 0:
            cumsum = cumsum / cumsum[-1]
            x = np.linspace(0, 1, len(cumsum))
            ax2.plot(x, cumsum, '-', color='#8e44ad', linewidth=2, label='Lorenz Curve')
            ax2.plot([0, 1], [0, 1], 'r--', label='Perfect Equality Allocation')
            ax2.fill_between(x, cumsum, x, alpha=0.1, color='#8e44ad')
            
            gini = RelayFairnessAnalyzer.calculate_gini(usage_counts)
            ax2.set_title(f'Relay Exhaustion Profile (Gini: {gini:.3f})')
        else:
            ax2.set_title('Relay Fairness (No Usage)')
            
        ax2.set_xlabel('Cumulative % of UAV Fleet')
        ax2.set_ylabel('Cumulative % of Total Relays')
        ax2.legend()
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=200)
        plt.close()
        
    def plot_swarm_lifetime(self, round_metrics: List[Dict], save_name: str = "swarm_lifetime.png"):
        """Plot swarm battery drain timeline with phase-coloured bands."""
        fig, ax = plt.subplots(figsize=(12, 6))

        rounds = [m["round"] for m in round_metrics]
        battery_mean = [m["battery_mean"] for m in round_metrics]
        battery_min = [m["battery_min"] for m in round_metrics]
        phases = [m["phase"] for m in round_metrics]

        # Phase background bands
        phase_runs = []
        cur_phase = phases[0]
        start_r = rounds[0]
        for i in range(1, len(phases)):
            if phases[i] != cur_phase:
                phase_runs.append((cur_phase, start_r, rounds[i-1]))
                cur_phase = phases[i]
                start_r = rounds[i]
        phase_runs.append((cur_phase, start_r, rounds[-1]))
        for pname, r0, r1 in phase_runs:
            ax.axvspan(r0 - 0.5, r1 + 0.5, alpha=0.12,
                       color=self.PHASE_COLORS.get(pname, '#ccc'))
            ax.text((r0 + r1) / 2, 101, pname, ha='center', va='bottom',
                    fontsize=9, fontweight='bold',
                    color=self.PHASE_COLORS.get(pname, '#555'))

        ax.plot(rounds, battery_mean, color='#2c3e50', linewidth=2.5, label='Mean Battery')
        ax.fill_between(rounds, battery_min, battery_mean, alpha=0.15, color='#e74c3c', label='Min–Mean Range')
        ax.plot(rounds, battery_min, color='#e74c3c', linewidth=1.2, linestyle='--', alpha=0.7, label='Min Battery')

        ax.set_xlabel('Mission Round', fontweight='bold')
        ax.set_ylabel('Battery Level (%)', fontweight='bold')
        ax.set_title('Swarm Battery Lifetime & Phase Transitions', fontsize=13, fontweight='bold')
        ax.set_ylim(0, 108)
        ax.legend(loc='lower left', frameon=True)

        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=200)
        plt.close()
        
    def plot_latency_by_phase(self, phase_metrics: Dict[str, List], save_name: str = "latency_by_phase.png"):
        """Plot communication latency across Z-MAPS operational phases."""
        import pandas as pd
        fig, ax = plt.subplots(figsize=(10, 6))

        active_phases = self._get_active_phases(phase_metrics)
        avgs = []

        for phase in active_phases:
            metrics = phase_metrics[phase]
            total_latency = sum(m["avg_latency"] for m in metrics)
            count = len(metrics)
            avgs.append((total_latency / count) if count > 0 else 0)

        if active_phases:
            df = pd.DataFrame({"Phase": active_phases, "Latency": avgs})
            bars = sns.barplot(data=df, x="Phase", y="Latency",
                               hue="Phase", palette=self.PHASE_COLORS, legend=False, ax=ax)
            ax.set_ylabel('Average Communication Latency (ms)', fontweight='bold')
            ax.set_title('Mean Multipath Latency by Mission Phase', fontsize=13, fontweight='bold')

            for index, bar in enumerate(bars.patches):
                ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1,
                        f'{avgs[index]:.1f} ms', ha='center', va='bottom', fontweight='bold')

        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=200)
        plt.close()

    def plot_traffic_composition(self, round_metrics: List[Dict], save_name: str = "traffic_composition.png"):
        """Plot stacked area of real vs dummy traffic with phase bands."""
        fig, ax = plt.subplots(figsize=(12, 6))

        rounds = np.array([m["round"] for m in round_metrics])
        real_msgs = np.array([m["messages_sent"] for m in round_metrics])
        dummy_msgs = np.array([m.get("dummy_messages", 0) for m in round_metrics])
        phases = [m["phase"] for m in round_metrics]

        # Phase background bands
        phase_runs = []
        cur_phase = phases[0]
        start_r = rounds[0]
        for i in range(1, len(phases)):
            if phases[i] != cur_phase:
                phase_runs.append((cur_phase, start_r, rounds[i-1]))
                cur_phase = phases[i]
                start_r = rounds[i]
        phase_runs.append((cur_phase, start_r, rounds[-1]))

        ymax = max(real_msgs + dummy_msgs) + 2
        for pname, r0, r1 in phase_runs:
            ax.axvspan(r0 - 0.5, r1 + 0.5, alpha=0.08,
                       color=self.PHASE_COLORS.get(pname, '#ccc'))
            ax.text((r0 + r1) / 2, ymax, pname, ha='center', va='bottom',
                    fontsize=8, fontweight='bold',
                    color=self.PHASE_COLORS.get(pname, '#555'))

        ax.stackplot(rounds, real_msgs, dummy_msgs,
                     labels=['Real Messages', 'Dummy Cover Traffic'],
                     colors=['#2980b9', '#f39c12'], alpha=0.85)

        ax.set_xlabel('Mission Round', fontweight='bold')
        ax.set_ylabel('Messages per Round', fontweight='bold')
        ax.set_title('Network Traffic Composition Over Time', fontsize=13, fontweight='bold')
        ax.legend(loc='upper left', frameon=True)

        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=200)
        plt.close()

    def plot_energy_consumption_rate(self, phase_metrics: Dict[str, List], save_name: str = "energy_consumption_rate.png"):
        """Plot battery drain rate per round by phase."""
        import pandas as pd
        fig, ax = plt.subplots(figsize=(10, 6))

        active_phases = self._get_active_phases(phase_metrics)
        rates = []

        for phase in active_phases:
            metrics = phase_metrics[phase]
            if len(metrics) < 2:
                rates.append(0)
            else:
                drop = metrics[0]["battery_mean"] - metrics[-1]["battery_mean"]
                rates.append(drop / len(metrics))

        if active_phases:
            df = pd.DataFrame({"Phase": active_phases, "Rate": rates})
            bars = sns.barplot(data=df, x="Phase", y="Rate",
                               hue="Phase", palette=self.PHASE_COLORS, legend=False, ax=ax)
            ax.set_ylabel('Avg Battery Drain per Round (%)', fontweight='bold')
            ax.set_title('Energy Consumption Rate by Mission Phase', fontsize=13, fontweight='bold')

            for index, bar in enumerate(bars.patches):
                ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.005,
                        f'{rates[index]:.3f}%', ha='center', va='bottom', fontweight='bold')

        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, save_name), dpi=200)
        plt.close()

    def generate_all_plots(self, metrics: MetricsCollector, relay_usage: List[int]):
        """Compile the entire visual evaluation suite cleanly"""
        print("Rendering Z-MAPS high-res evaluation plots...")
        
        if metrics.battery_history:
            self.plot_battery_distribution(metrics.battery_history)
            
        if metrics.phase_metrics:
            self.plot_privacy_energy_tradeoff(metrics.phase_metrics)
            self.plot_latency_by_phase(metrics.phase_metrics)
            self.plot_energy_consumption_rate(metrics.phase_metrics)
            
        if metrics.round_metrics:
            self.plot_trace_success_by_phase(metrics.round_metrics)
            self.plot_swarm_lifetime(metrics.round_metrics)
            self.plot_traffic_composition(metrics.round_metrics)
            
        if relay_usage:
            self.plot_relay_fairness(relay_usage)
            
        print(f"  ✓ Validated and exported 8 visual metrics to {self.output_dir}/")
