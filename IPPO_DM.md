# Z-MAPS: IPPO-DM AI Engine

The core machine learning innovation within Z-MAPS is the **Independent Proximal Policy Optimization with Dirichlet Modeling (IPPO-DM)**. Rather than explicitly writing hardcoded relay pathways, the system learns optimal paths iteratively.

This is managed across two core directories/files:
- `train_ippo.py`: The CLI Entrypoint for deep learning updates.
- `zmaps/routing/`: Contains `ippo_agent.py` and environment trainers.

---

## 1. Why IPPO over Centralized RL?
UAV swarms must be decentralized. Centralized agents tracking the entire board state fail when jammed or localized communication drops. Z-MAPS treats every drone as a localized learner, operating a shared parameter neural network but independently running observations. It maps the POMDP (Partially Observable Markov Decision Process) securely.

---

## 2. Dirichlet Modeling for Multipath Traffic Splitting
Unlike standard PPO predicting discrete steps (e.g. Route A or Route B), the Z-MAPS objective requires mapping multi-path routes.

The IPPO algorithm utilizes a **Dirichlet Output Distribution**:
*   The Neural Network's Actor output applies a `Softplus + 1` activation layer.
*   This configures concentration factors ($\alpha$) mapping a multi-path probability vector in continuous space.
*   A result might be $[0.40, 0.35, 0.25]$, successfully sending 40% of L1 data chunks over Path 1, 35% on Path 2, and 25% on Path 3.

---

## 3. RL Vector Space Variables

### State Observation Space
The state array generated through `swarm.py` forms a 32-dimensional float buffer tracking:
1. Local Agent Battery Level & Cooldown state.
2. Direct Neighbor Battery Levels & Cooldown constraints (up to `N` neighbors).
3. Active swarm health variables.

### Action Constraint Space
As dictated in Phase limits, the action distribution selects splitting percentages up to `k` paths continuously (mapped via Dijkstra lists). 

### Reward Function Processing
In `train_ippo.py`, environmental steps map rewards fundamentally based on competing metrics:
*   $+1.0$ for successful Delivery (Integrity Validated).
*   $-0.8$ penalty for high trace probability mapping by the Adversary layer.
*   $-0.2$ penalty dynamically scaled against heavy multi-path energy drains to encourage conservation unless specifically tasked mathematically.
