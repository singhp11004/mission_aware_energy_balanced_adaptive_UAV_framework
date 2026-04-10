# UAV Swarm Privacy Framework - Workflow & Procedure

This document provides a step-by-step guide to setting up, configuring, and running the Mission-Aware Energy-Balanced Adaptive Privacy Framework (Z-MAPS).

## 1. Prerequisites

- **Python 3.8+** (Tested with Python 3.11)
- **pip** (Python package installer)
- **Virtual Environment** (Recommended)

## 2. Installation & Setup

It is highly recommended to run the simulation within a virtual environment to avoid dependency conflicts.

### Step 1: Create a Virtual Environment
Run the following command in the project root directory:

```bash
python3 -m venv venv
```

### Step 2: Activate the Virtual Environment

- **Linux/macOS:**
  ```bash
  source venv/bin/activate
  ```

- **Windows:**
  ```cmd
  venv\Scripts\activate
  ```

### Step 3: Install Dependencies
Install the required Python packages using `pip`:

```bash
pip install -r requirements.txt
```

## 3. Running the Simulation

The system enforces a 4-layer Z-MAPS functional architecture strictly isolated from monolithic testing wrappers. To execute the framework evaluation:

```bash
python3 main.py --mode eval --rounds 100
```

### Expected Output
The framework generates operational metrics continuously:

1.  **Initialization**: Sets up the IPPO models, establishes Cryptography engines, and constructs Dijkstra route mappings through $P \cdot d^2$ signal decay constraints. It identifies the 4-layer tactical stack initialization.
2.  **Round Progression**: Console updates every 10 rounds detailing:
    - Active drone count (Mission failure if < 3)
    - Average battery level persistence
    - Operational lifecycle phase shifts (e.g. `SURVEILLANCE` -> `ENGAGEMENT`)
3.  **Final Telemetry Report**: The system culminates with a "Z-MAPS RESULTS" summary:
    - Total message chunks processed
    - Delivery and Trace rates
    - Multipath deployment utilization percentages
    - Prioritization layer enhancement rates

## 4. IPPO-DM Training Mode

To engage the Independent Proximal Policy Optimization network generator directly:

```bash
python3 main.py --mode train --drones 50 --seed 42
```
This triggers parameter-shared Actor-Critic updates based on Dirichlet policy derivations, updating localized `.pt` checkpoint weights.

## 5. Configuration

Project settings can be fundamentally altered in `config.py`. Core configurable structures:

- **NUM_DRONES**: Total number of UAVs within the network topology (Default: 50).
- **SIMULATION_ROUNDS**: Base iteration counter duration (Default: 100).
- **MESSAGES_PER_ROUND**: Volume of simultaneous transmission demands generated per round matrix.
- **PHASE_CHANGE_INTERVAL**: Iterations required before shifting operational profiles (e.g. `TRANSIT` -> `PATROL`).

## 6. Outputs & Visualization

Upon completion, all execution outcomes establish graphical traces in the `outputs/` directory dynamically.

### Generated Graphs
- **Battery Distribution**: Remaining battery capability distributions across the node geometry.
- **Privacy vs. Energy**: Scatter plot isolating the statistical efficiency vs computational payload constraints.
- **Trace Success**: Adversary evasion trends representing layer-3 obfuscation stability boundaries.
- **Swarm Lifetime**: Core connectivity timeline stability maps.
- **Latency by Phase**: Phase transit speed analyses representing Dijkstra pathing complexities.
- **Traffic Composition**: Dummy density and noise-padding distribution layers.

## 7. Interpreting Expected Deliverables

- **Trace Success Rate**: Traces actively evaluate the multi-vector analytical engines against our obfuscation. Values below 30% signify near-total success scaling across heavy surveillance regimes.
- **Delivery Stability**: Representing X448 validation ratios and core edge traversals mapping properly across dynamic routing changes.
