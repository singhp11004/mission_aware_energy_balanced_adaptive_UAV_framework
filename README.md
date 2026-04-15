# Z-MAPS: Zero-Knowledge Multi-Agent RL Framework for Mission-Aware Privacy

> A layered, reinforcement-learning-driven framework for secure UAV swarm communication that dynamically balances privacy protection against energy consumption using **Independent Proximal Policy Optimization with Dirichlet Modeling (IPPO-DM)** for traffic-adaptive multipath routing.

---

## 📌 Project Overview

### The Problem
In critical missions (military surveillance, disaster relief, border security), UAV swarms must transmit sensitive telemetry without revealing locations to adversaries. Traditional encryption protects message *content* but not *traffic patterns*. An adversary analyzing traffic flow can trace message sources, endangering the swarm.

Protecting against traffic analysis requires expensive measures like multi-hop routing and dummy traffic injection, which drain battery life. A static high-security approach grounds the swarm too quickly. Existing multi-hop networks suffer from **single-path bottlenecks** that cause congestion and detectable timing signatures.

### The Solution: Z-MAPS
This framework implements a **4-layer mission-centric architecture** with **RL-driven multipath routing** and optimized logical constructs:

| Layer | Name | Responsibility |
|:---:|:---|:---|
| **L1** | Data Acquisition | Noise-Free Random Chunk Segmentation (50-1000B), Data classification |
| **L2** | Prioritization | Semantic analysis, priority scoring, privacy envelope recommendation |
| **L3** | Communication | IPPO-DM Multipath, Dijkstra ($P \cdot d^2$) Weighted Transits, Dummy Noise |
| **L4** | TOC Integration | Command server delivery, ACK processing |

---

## 🚀 Advanced Project Upgrades

### 1. Quantum-Resistant Cryptography
Primitives scaling to match deep surveillance threat models optimally:
- **Key Exchange:** Transitioned from ECDH (P-256) to **X448**, achieving bleeding-edge session capabilities natively optimized against intercept algorithms.
- **Signatures:** Stepped from `Ed25519` to **Ed448** yielding superior resistance buffers.
- **Hashing Infrastructure:** Transitioned standard telemetry loops across natively from `SHA3-256` up to **SHA3-512**.

### 2. $P \cdot d^2$ Dijkstra Routing
Next-hop relay chaining avoids probabilistic mapping via deterministic routing logic. Swarm topologies continually reassess logical edge weights based on inverse square transmission costs and normalized battery decay metrics, processed globally by `networkx` (`nx.dijkstra_path`).

### 3. Noise-Free Random Segmentation
Layer 1 dynamically restricts monolithic payload transit behavior by stripping string constraints into independent chunk fragments scaled identically between 50 and 1000 bytes. This creates powerful observability decoupling under IPPO boundaries without bleeding battery resources into empty "dummy noise padding" parameters.

---

## 🧠 IPPO-DM: Traffic-Adaptive Multipath Routing

The core research contribution replaces single-path relay chains with **learned traffic splitting** using PPO + Dirichlet modeling.

### How It Works
1. Each drone runs a **parameter-shared Actor-Critic network** that observes local state.
2. The **actor head** outputs Dirichlet concentration parameters via `softplus+1`.
3. **Sampling from the Dirichlet** yields continuous split ratios `α = (α₁, …, αₖ)`.
4. Traffic is **forwarded in parallel** across `k` next-hop relay chains mapping deterministically via Dijkstra constraints.

---

## 🔄 5-Phase Operational Lifecycle

| Phase | Threat | Routing | Multipath | Dummy Rate | Cipher (AEAD) |
|:---|:---:|:---:|:---:|:---:|:---|
| 🚁 **TRANSIT** | 0.1 | 1 hop | ✗ | 5% | XChaCha20-Poly1305 |
| 🟢 **PATROL** | 0.25 | 2 hops | ✗ | 10% | XChaCha20-Poly1305 |
| 🟡 **SURVEILLANCE** | 0.55 | 3 hops | ✓ (2-path) | 30% | XChaCha20-Poly1305 + Ed448 |
| 🔴 **ENGAGEMENT** | 0.95 | 5 hops | ✓ (3-path) | 50% | ChaCha20-Poly1305 + Ed448 |
| 🔵 **RECOVERY** | 0.35 | 2 hops | ✓ (2-path) | 15% | XChaCha20-Poly1305 + HMAC |

---

## 🛠️ How to Run

### Prerequisites
```bash
pip install -r requirements.txt
```

### Z-MAPS Core Evaluation Engine 
```bash
python main.py --mode eval               # uses trained IPPO if available
python main.py --mode eval --checkpoint outputs/checkpoints/ippo_final.pt
```

### Train the IPPO-DM Agent
```bash
python train_ippo.py                     # full training (500 episodes)
python train_ippo.py --episodes 100      # quick training
```

---

## 📖 Complete Documentation Index

To explore the exact engineering details behind this multi-agent framework, please review our comprehensive module documentations:

*   **[EXPLANATION.md](EXPLANATION.md)** — High-level logic overview and the 4-layer tactical stack.
*   **[WORKFLOW.md](WORKFLOW.md)** — Environment setup and terminal execution arguments.
*   **[ARCHITECTURE.md](ARCHITECTURE.md)** — Swarm topology setup, agent configurations, and adversarial tracking environments.
*   **[CRYPTOGRAPHY.md](CRYPTOGRAPHY.md)** — Advanced phase-adaptive encryption logic (X448, XChaCha20, Ed448, SHA3).
*   **[IPPO_DM.md](IPPO_DM.md)** — Machine learning logic covering the Actor-Critic shared policies and Dirichlet modeling constraint sets.
*   **[ROUTING_AND_ENERGY.md](ROUTING_AND_ENERGY.md)** — The physics constraints behind trajectory mapping, energy depletion logic, and noise-free fragmentation.

---

## 📁 Project Structure

```
├── main.py                  # CLI entry point Evaluation/Training driver
├── train_ippo.py            # Standalone IPPO-DM training script
├── config.py                # Core constants and Hyperparameters
│
├── zmaps/                   # Z-MAPS Modular Package
│   ├── layers/              # The 4-Layer Architecture (L1-L4)
│   ├── mission/             # 5-Phase lifecycle and profile thresholds
│   └── routing/             # Custom IPPO-DM implementations
│
├── swarm.py                 # Topology, Edge computations, Drone state classes
├── energy_model.py          # Cost metrics scaling battery drain tracking
├── crypto_engine.py         # X448, Ed448, SHA3-512 backend hooks
├── adversary.py             # Heuristic traffic correlation modeling
├── privacy_controller.py    # Dummy and Jitter logic controllers
├── relay_selector.py        # Dijkstra topology navigation
└── metrics.py               # Visuals / performance graphing
```

---

## 📚 References

- **IPPO-DM**: Independent PPO with Dirichlet Modeling for multi-agent traffic splitting on the probability simplex
- **Mission-Centric Layered Architecture**: Data Acquisition → Prioritization → Communication → TOC Integration
- **Privacy-Energy Profiles**: Phase-specific parameter sets balancing security requirements against battery constraints

---

*Z-MAPS: Zero-Knowledge Multi-Agent Reinforcement Learning Framework for Mission-Aware Privacy*
