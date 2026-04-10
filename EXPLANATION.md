# Z-MAPS Logic & Architecture: Technical Explanation Guide

This guide provides a comprehensive technical breakdown of the **Z-MAPS** (Zero-Knowledge Multi-Agent Reinforcement Learning Framework for Mission-Aware Privacy) framework. It is intended to help you explain the system's underlying logic and autonomous decision-making processes.

---

## 🚀 1. The 4-Layer Tactical Engine

Z-MAPS operates through a decoupled, 4-layer mission-centric stack. Each layer has a specific tactical responsibility:

### 📥 Layer 1: Data Acquisition & Noise-Free Fragmentation
*   **Semantic Mapping:** Ingests raw telemetry and identifies the payload type (e.g., `PATROL`, `TARGET_ID`).
*   **Recursive Segmentation:** To avoid the battery-draining overhead of traditional "padding" (adding empty bytes to make packets look the same size), Z-MAPS recursively shatters a single payload into random blocks sized between **50B and 1000B**. 
*   **Result:** These fragments transit the network asynchronously, naturally obscuring the original message's size signature.

### ⚖️ Layer 2: Semantic Prioritization
*   **Priority Scoring:** Evaluates the urgency of each fragment. For example, a `TARGET_ID` packet in an `ENGAGEMENT` zone receives a maximum priority score.
*   **Policy Recommendation:** Based on the priority and mission phase, this layer recommends a **Privacy Envelope**:
    *   **Routing Depth:** How many relays to use?
    *   **Multipath Splits:** How many parallel paths to split traffic across?
    *   **Timing Jitter:** How much random delay to inject at each hop?

### 🧠 Layer 3: Communication & IPPO-DM Routing
*   **The Brain:** This is where the **IPPO-DM** (Independent Proximal Policy Optimization with Dirichlet Modeling) agent resides.
*   **Traffic Splitting:** For high-priority traffic, the agent calculates optimal split ratios on the probability simplex. If $k=3$ paths are requested, the agent might decide to send 40% through Path A, 35% through Path B, and 25% through Path C based on local congestion and adversary activity.
*   **Dijkstra $P \cdot d^2$ Chaining:** Relays are selected using a weighted Dijkstra algorithm where edge weights grow with the square of the distance ($d^2$) and the inverse of the relay's battery level.

### 🏁 Layer 4: TOC (Tactical Operations Center) Integration
*   **Reassembly:** The TOC server collects fragments, validates their integrity using **SHA3-512** hashes, and decrypts the final payload.
*   **ACK Feedback:** Sends acknowledgments back to the source, completing the loop and recording system-wide delivery metrics.

---

## 🔄 2. The 5-Phase Mission Lifecycle

The swarm automatically adapts its security posture based on the mission context:

1.  🚁 **TRANSIT:** Low-threat movement. Focuses on **maximum energy conservation**. (Single-path, minimal encryption).
2.  🟢 **PATROL:** Baseline security. Standard multi-hop routing with low dummy traffic.
3.  🟡 **SURVEILLANCE:** Elevated threat. Enables **IPPO-DM Multipath** (2 paths) and asymmetric signatures (**Ed448**).
4.  🔴 **ENGAGEMENT:** Maximum privacy. Uses **3-parallel path routing**, maximum dummy injection, and **ChaCha20-Poly1305** for speed/security.
5.  🔵 **RECOVERY:** Returning to base. Balances remaining battery against moderate security needs.

---

## 🔐 3. Modernized Cryptographic Stack

Z-MAPS utilizes bleeding-edge, quantum-resistant primitives:
*   **XChaCha20-Poly1305:** Authenticated encryption with 192-bit nonces to prevent collision in high-velocity streams.
*   **X448 Key Exchange:** Established session keys with 224-bit security strength (superior to standard P-256).
*   **Ed448 Signatures:** Gold-standard identity verification for Command Server instructions.
*   **SHA3-512:** Keccak-based hashing for absolute integrity validation.

---

## 📊 4. Interpreting Output Metrics

After a simulation run, check the `outputs/` folder for high-resolution performance analysis:

*   **`privacy_energy_tradeoff.png`**: Look for the "Engagement" phase. You should see maximum privacy effectiveness (near 100%) but with a corresponding peak in energy cost per round.
*   **`traffic_composition.png`**: Shows the "sea" of dummy packets. In high-threat phases, the volume of dummy traffic should significantly expand to bury the real data.
*   **`relay_fairness.png`**: The Lorenz Curve and Gini coefficient. A low Gini coefficient (<0.2) means the framework is successfully distributing the load across all drones, preventing single-drone battery exhaustion.
*   **`trace_success_by_phase.png`**: The goal is to see the trace rate drop as the mission progresses into higher phases.

---

## 🛠️ 5. Evaluation Command Reference

To run the Z-MAPS evaluation with pre-trained IPPO-DM weights:
```bash
python main.py --mode eval --rounds 100
```
This will yield a final "Z-MAPS RESULTS" summary in your terminal, detailing delivery rates, trace mitigation, and routing utilization.

---
*Technical Documentation — Mission-Aware Energy-Balanced Adaptive UAV Framework*
