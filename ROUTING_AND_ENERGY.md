# Z-MAPS: Routing Logic and Energy Constraints

This document explores the granular physics surrounding movement, battery conservation, and mathematical pathway rendering within Z-MAPS' core modules.

## 1. Network Pathing Initialization: `relay_selector.py`

Z-MAPS ignores standard proxy bounce chains for rigorous, continuously recalculated network graphs utilizing Python's `NetworkX` library.

### Dijkstra with Weighted P·d² Calculations
The engine does not strictly select pathways based on minimum hops. Transmission cost directly maps to the inverse transmission distance.

*   $d$: Floating-point mathematical geometric distance between Agent U and Agent V on a mapped topology string.
*   $P_{cost}$: Scales upwards dynamically based on $d^2$. Sending massive packets over long radio ranges instantly spikes $P_{cost}$ resulting in the `NetworkX.dijkstra_path` naturally seeking smaller geometric intermediate node hops.
*   **Battery Fairness Weight:** The node battery acts as an inverse multiplier against the edge. A relay agent with critical battery dynamically creates a heavier computational weight against the network edge pushing RL IPPO flows elsewhere, guaranteeing standard deviation lifetimes.

### Multi-path Splitting Parameters
Once `relay_selector.py` grabs the shortest routes, it calculates discrete alternative parallel lines. Under threat condition `ENGAGEMENT`, $k=3$ paths are required, and are forced through topologically distinct intermediate drone channels.

---

## 2. Battery Life Physics: `energy_model.py`

Battery optimization works synchronously with the `swarm.py` tracker.
1.  **Baseline Decay**: Standard positional hover algorithms execute normalized baseline subtractions.
2.  **Radio Decay**: Burst-transmissions decrease energy directly proportional to multi-path fragment sizes.
3.  **Phase Caps**: At `TRANSIT`, energy decay drops to absolute minimalist caps. `ENGAGEMENT` utilizes multi-path and dummy flow logic dropping reserves ~140% faster.

---

## 3. Privacy Bounds Mapping: `privacy_controller.py`

Traditionally, privacy bounds in Multi-hop networks demand dummy-packet injection frameworks pushing empty bytes around to artificially raise network congestion maps confusing adversarial modeling. Z-MAPS integrates **Noise-Free Fragmentation**:
*   Instead of dummy strings draining `energy_model.py` buffers, the Data Acquisition layer directly strips payload bounds.
*   A high-priority payload is shattered into random size blocks mapping continuously between `50B` and `1000B`.
*   The `privacy_controller.py` injects artificial latency logic (Jitter) against the flow constraints making real data blocks behave mathematically identically to cover-status packets rendering heuristic trackers fundamentally blind.
