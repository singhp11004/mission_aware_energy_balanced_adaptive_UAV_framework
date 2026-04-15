# Z-MAPS: System Architecture Guide

This document systematically details the fundamental structural components forming the baseline of the Z-MAPS simulation environment. It covers the topology representations, configuration management, and threat logging.

---

## 1. `swarm.py` — Swarm Topology and Agent State

The `swarm.py` module maintains the physical location, battery lifecycle, and topological networking of all UAV agents and the central Command Server (TOC).

### 1.1 `Drone` Class
Each multi-rotor drone is an independent `Drone` object initialized with:
*   **Battery Level Tracking:** Initialized via `INITIAL_BATTERY`. It drops progressively as the drone transmits or relays data.
*   **Mission State:** Begins at `PATROL` and shifts synchronously based on swarm alerts.
*   **Cooldown and Usage Count:** Tracks how often the drone is selected as a relay to prevent rapid localized battery exhaustion.
*   **Position Data:** represented as a 2D float coordinate array, randomly adjusting each round to simulate localized hovering/movement.

### 1.2 `CommandServer` Class (TOC)
The Tactical Operations Center (TOC) acts as the central data sink (`COMMAND_SERVER_ID = -1`).
*   **Packet Reassembly:** Reconstructs payload fragments.
*   **Integrity Assurance:** Logs failures (dropped packets/tampering).
*   **Acknowledge (ACK) Logs:** Bounces delivery receipts back to `Drone` sources.

### 1.3 `UAVSwarm` Class (Network Graph)
Utilizes the `networkx` library to build a **Random Geometric Graph (RGG)**.
1.  **Topology Calculation:** Each drone connects to neighbors within a `COMMUNICATION_RANGE`. Edge matrices reset each round based on positional drift.
2.  **Edge Weight Updates:** Updates `networkx` weighted graph objects, computing `$P_{cost} \cdot d^2$` and penalizing nodes with lower battery reserves.
3.  **State Vector Generation:** Supports standard RL `get_drone_state_vector()` calls mapping neighbor battery, active cooldowns, and relay metrics into array inputs for IPPO algorithms.

---

## 2. `config.py` — Mission Parameters

This acts as the single source of truth for tuning the framework's operating logic.
*   **`NUM_DRONES`**: Total agents (Default: 50).
*   **`INITIAL_BATTERY`**: Starting charge (Default: 100.0).
*   **Phase Configurations**: Enums and dictionary matrices mapping constraints to the 5 lifecycle phases:
    1. `TRANSIT`
    2. `PATROL`
    3. `SURVEILLANCE`
    4. `ENGAGEMENT`
    5. `RECOVERY`

---

## 3. `adversary.py` — Threat Intelligence Environment

To test the system against realistic intelligence gathering, this module maps a continuous threat actor.
*   **`Adversary` Class:** Heuristically analyzes traffic flowing through the swarm.
*   **Correlation Logic:** Tracks sequential hop-chains. If a packet enters a node and a similar size packet leaves within a short delta, the adversary probabilistically links the transmission path.
*   **Metrics:** Outputs trace success ratios, acting as the primary evaluation parameter against the IPPO proxy routing layers.

---

## 4. `metrics.py` — Global Performance Capture

Handles the continuous serialization of simulation data into `matplotlib` subplots:
*   `plot_swarm_state()`: Real-time network graphing (Nodes and weighted edges).
*   `evaluate_system_performance()`: Produces final PDF/Image breakdowns comparing base performance metrics in the `/outputs` folder against static frameworks.
