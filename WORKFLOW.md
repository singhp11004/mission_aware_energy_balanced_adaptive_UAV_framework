# UAV Swarm Privacy Framework - Workflow & Procedure

This document provides a step-by-step guide to setting up, configuring, and running the Mission-Aware Energy-Balanced Adaptive Privacy Framework simulation.

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

To execute the simulation, run the `main.py` script:

```bash
python3 main.py
```

### Expected Output
The simulation will print progress to the console, including:

1.  **Initialization**: Setting up the swarm, energy models, and privacy controllers.
2.  **Round Progression**: Updates every 10 rounds showing:
    - Active drone count
    - Average battery level
    - Current mission phase (e.g., PATROL, SURVEILLANCE, THREAT)
3.  **Phase Transitions**: Notifications when the mission phase changes.
4.  **Final Report**: A comprehensive summary of:
    - Statistics (Total messages, efficiency, etc.)
    - Privacy Analysis (Trace attempts vs. successes)
    - Relay Fairness
    - Verification of graph generation.

## 4. Running the Interactive Dashboard

For a visual, real-time experience:

```bash
streamlit run app.py
```

This will launch a web interface where you can:
-   Watch the swarm operate in **God Mode** or **Adversary Mode**.
-   Trigger events like **Decoy Deployment** and **EMP Blasts**.
-   Monitor real-time metrics for privacy and energy.

## 5. Configuration

Project settings can be modified in `config.py`. Key parameters include:

- **NUM_DRONES**: Total number of UAVs in the swarm (Default: 50).
- **SIMULATION_ROUNDS**: Total duration of the simulation (Default: 100).
- **MESSAGES_PER_ROUND**: Number of messages generated per round.
- **PHASE_CHANGE_INTERVAL**: How often the mission phase updates.

## 6. Outputs & Visualization

Upon completion, the simulation generates results in the `outputs/` directory.

### Generated Graphs
- **Battery Distribution**: Histogram of remaining battery levels.
- **Privacy vs. Energy**: Scatter plot showing the trade-off between privacy cost and energy consumption.
- **Trace Success**: Line graph of adversary success rates over time/phases.
- **Swarm Lifetime**: Active drone count over simulation rounds.
- **Relay Fairness**: Bar chart of message relay distribution among drones.
- **Latency by Phase**: Bar chart comparing communication delay across different privacy levels.
- **Traffic Composition**: Stacked area chart visualising the ratio of real vs. dummy noise traffic.
- **Energy Consumption Rate**: Bar chart showing how fast battery drains in each mission phase.

## 7. Interpreting Results

- **Trace Success Rate**: A lower trace success rate indicates better privacy.
- **0% Trace Success**: In high-security phases (like `THREAT`), it is expected to see **0% trace success**. This means the privacy measures (5-hop routing, dummy traffic, jitter) were sufficient to reduce the adversary's confidence below their actionable threshold. It does **not** mean the simulation is broken; it means the defense is working.
