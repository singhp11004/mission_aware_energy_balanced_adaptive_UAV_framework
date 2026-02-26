# Ultra-Premium Interactive UAV Simulation Design

This final design iteration pushes the boundaries of web-based simulation, incorporating "Adversary View", 3D visualization, custom assets, and a "Gamified" operational mode.

## 1. Core Vision: "Twin Perspectives"

The application will offer two distinct modes of operation, selectable via a toggle:
*   **God Mode (Blue Team)**: See all drones, true battery levels, actual paths, and network health.
*   **Adversary Mode (Red Team)**: See only what the adversary sees—intercepted encrypted packets and estimated traffic flows. This powerfully demonstrates the privacy technology in action.

## 2. Ultra-Premium Features

### A. "Adversary View" (The Killer Feature)
*   **Visuals**: Switch the graph to a "Matrix" style theme (Black/Green).
*   **Data Hiding**: Hide battery levels and drone IDs.
*   **Traffic Analysis**: Show "Suspected Flows" (probabilistic paths) vs. "Actual Flows".
*   **Success Metric**: Display the adversary's "Confidence Score" in real-time. If it hits 100%, the drone turns bright red (Compromised).

### B. Cinematic Visualization
*   **Custom Assets**: Replace dot nodes with small `.png` or SVG icons (Drone, Base Station, Attacker).
*   **3D Graph Mode**: Use `streamlit-agraph` for a 3D rotating view of the swarm.
*   **Sound FX**: Audio feedback for critical events (using `st.audio` with invisible players):
    *   *Low Battery Warning*
    *   *Attack Detected Siren*
    *   *Phase Change Confirmation*

### C. Gamification & Active Control (Maximum Interactivity)
*   **Mission Objectives**: Give the user a goal, e.g., "Survive 100 Rounds with >50% Swarm Integrity".
*   **Active Countermeasures**:
    *   **Deploy Decoys**: Button to spawn 5 temporary dummy nodes to distract the adversary (Cost: 10% Energy).
    *   **EMP Blast**: Temporarily blind the adversary's tracking for 5 rounds (Cost: 20% Energy).
    *   **Emergency Reroute**: Force a topology shuffle.
*   **Scoring System**: Calculate a "Command Score" based on (Privacy Kept + Energy Saved).

## 3. Revised Architecture

### Layout Structure
1.  **Top Bar (Heads-Up Display)**
    *   **Mode Toggle**: 🔵 God Mode / 🔴 Adversary Mode.
    *   **Phase Indicator**: Large glowing text (e.g., "STATUS: THREAT LEVEL MID").
    *   **Global Health**: System integrity percentage.
    *   **Score**: Current Command Score.

2.  **Main Viewport**
    *   **PyVis/Agraph Component**: The primary interactive element.
    *   **Context Menu**: Right-click simulation to "Inspect" or "Jam".

3.  **Command Console (Bottom)**
    *   **Terminal**: Rolling log of encrypted/decrypted messages.
    *   **Countermeasures Bar**: Buttons for Decoys, EMP, Reroute.
    *   **Controls**: Play/Pause, Step, Speed Dial.

## 4. Implementation Details

### Custom Assets
*   `assets/drone_blue.png`: Normal drone.
*   `assets/drone_red.png`: Compromised/Attacking drone.
*   `assets/base_station.png`: Command Server.

### Audio Integration
*   Simple localized WAV files played via `st.audio(..., autoplay=True)`.

### PDF Generation
*   Use `fpdf` library to compile text stats and saved plot images into a downloadable report.

## 5. Execution Plan

1.  **Phase 1**: Core Engine Refactor (`simulation_engine.py`) to support state yielding and active intervention.
2.  **Phase 2**: Dual-View Logic (God vs. Adversary state filtering).
3.  **Phase 3**: Asset Integration (Icons & Sounds).
4.  **Phase 4**: Gamification Logic (Scoring, Objectives, Cooldowns).

## 6. Required Libraries
```bash
pip install streamlit pyvis streamlit-agraph fpdf
```
