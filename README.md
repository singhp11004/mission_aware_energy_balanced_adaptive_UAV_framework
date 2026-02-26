# Mission-Aware Energy-Balanced Adaptive Privacy Framework

A Python-based simulation environment for modeling secure communication in UAV (Unmanned Aerial Vehicle) swarms. The framework adaptively balances privacy protection against energy consumption based on current mission threat levels.

## 📌 Project Overview

### The Need
In critical missions (military surveillance, disaster relief, border security), UAV swarms must transmit sensitive telemetry without revealing their locations to adversaries. Traditional encryption protects the *content* of messages but not the *traffic patterns*. An adversary analyzing traffic flow (Traffic Analysis) can trace the source of a transmission, endangering the UAV.

Protecting against traffic analysis requires expensive measures like multi-hop routing and dummy traffic injection, which drain battery life. A static high-security approach would ground the swarm too quickly.

### The Solution
This project implements a **Mission-Aware Framework** that dynamically adjusts privacy parameters.
- **Low Threat (PATROL)**: Minimal protection to conserve energy.
- **High Threat (THREAT)**: Maximum protection (deep routing, high noise) to ensure survival, even at high energy cost.

---

## ⚙️ Core Processes & Methodology

### 1. Adaptive Privacy Controller (`privacy_controller.py`)
The system monitors the mission phase and adjusts three key privacy mechanisms:
-   **Routing Depth (Hops)**: The number of intermediate relays a message must pass through.
    -   *Patrol*: 2 hops.
    -   *Threat*: 5 hops (much harder to trace).
-   **Dummy Traffic Injection**: Fake messages sent to confuse traffic analysis.
    -   *Patrol*: 10% rate.
    -   *Threat*: 50% rate (creates a "fog of war").
-   **Timing Jitter**: Random delays introduced to disrupt timing correlation attacks.

### 2. Energy-Aware Operations (`energy_model.py`)
Every action consumes battery. The framework models the cost of:
-   **Transmission**: Varies by distance and number of hops.
-   **Encryption/Decryption**: Computation cost.
-   **Dummy Traffic**: The "price of privacy."
-   **Relaying**: Energy cost for helping other drones.

Detailed battery physics, including critical-level efficiency penalties, are simulated.

### 3. Adversary Simulation (`adversary.py`)
A simulated "Global Passive Adversary" observes all network traffic.
-   **Traffic Analysis**: Correlates message timing and hop counts to guess the source.
-   **Trace Success**: The adversary succeeds if they can identify the sender with >70% confidence.
-   **Goal**: The framework aims to keep this success rate at **0%** during high-threat phases.

### 4. Swarm Intelligence (`swarm.py` & `relay_selector.py`)
-   **Decentralized Routing**: Drones select relays based on connectivity and battery levels.
-   **Load Balancing**: Ensures no single drone is exhausted by relay duties (verified by Gini coefficient metrics).

---

## 🚀 Use Cases

1.  **Military Reconnaissance**: UAVs patrolling a hostile border. When an enemy radar is detected (Phase: THREAT), the swarm switches to high-privacy mode to prevent the enemy from locating the patrol.
2.  **Dissident/Journalist Protection**: Secure communication networks in oppressive regimes where physical location tracing is a threat.
3.  **Critical Infrastructure Monitoring**: Protecting the location of sensitive sensors monitoring pipelines or power grids from sabotage.

---

## 📊 Results Achieved

The simulation consistently demonstrates the effectiveness of the adaptive approach:

| Mission Phase | Privacy Level | Trace Success | Energy Cost | Result Interpretation |
| :--- | :--- | :--- | :--- | :--- |
| **PATROL** | Low | ~91% | Low | Adversary can trace easy targets, but swarm saves battery for long duration. |
| **SURVEILLANCE** | Medium | ~60-80% | Medium | Balanced approach. |
| **THREAT** | **Maximum** | **0%** | **High** | **Perfect Defense.** The adversary is completely blinded by dummy traffic and deep routing. |

> **Note**: A "0% Trace Success" in THREAT mode is a **positive result**. It means the defense mechanisms successfully prevented the adversary from identifying the source.

---

## 🛠️ How to Run

1.  **Clone the repository**.
2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Run the simulation**:
    ```bash
    python3 main.py
    ```
4.  **View Results**: Check the console output and the `outputs/` directory for generated graphs.

## 🎮 Interactive Dashboard (New!)

Experience the simulation in real-time with our "Mission Control" dashboard.

1.  **Install additional dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Launch the dashboard**:
    ```bash
    streamlit run app.py
    ```
3.  **Features**:
    *   **Twin Perspectives**: Toggle between *God Mode* (full visibility) and *Adversary Mode* (intercepted traffic).
    *   **Active Countermeasures**: Deploy decoys or trigger EMP blasts to save the swarm.
    *   **Real-time Telemetry**: Watch the adversary's confidence score rise and fall.

For a detailed step-by-step guide, see [WORKFLOW.md](WORKFLOW.md).
