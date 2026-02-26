# Simulation Explanation Guide: Mission-Aware UAV Framework

This guide explains the **Interactive Dashboard (`app.py`)** for the "Mission-Aware Energy-Balanced Adaptive Privacy Framework". Use this document to demonstrate the system's capabilities to your professor or peers.

---

## 🚀 1. Overview
The dashboard visualizes a swarm of **50 UAVs** (Unmanned Aerial Vehicles) performing a mission while defending against a sophisticated **Adversary**.

**Key Goal:** Balance **Privacy** (avoiding detection) with **Energy Efficiency** (battery life) by dynamically adapting security protocols based on the **Mission Phase**.

---

## 🎯 2. Dashboard Components

### 🖥️ HUD (Heads-Up Display) - Top Bar
*   **ROUND**: Current simulation step (1 round approx = 1-3 seconds real-time).
*   **SCORE**: Points for successful message delivery. *Penalized* if traced.
*   **PHASE**: Current mission state (PATROL 🟢 / SURVEILLANCE 🟡 / THREAT 🔴).
    *   *See Section 3 for details.*
*   **DRONES**: Operations status (Active / Total). If < 30% active, mission fails.
*   **AVG BATTERY**: Fleet-wide average battery level.
*   **TRACE SUCCESS**: The **Adversary's Success Rate**.
    *   **High % (red)** = Bad. Adversary is successfully tracing messages.
    *   **Low % (green)** = Good. Privacy measures are working.

### 🗺️ Tactical Map (Left Panel)
*   **Nodes**: Individual drones.
    *   **Green**: High battery (>70%).
    *   **Yellow/Orange**: Medium battery.
    *   **Red**: Critical battery (<15%).
*   **Edges**: Communication links between drones.
*   **Blue Diamond**: The **Command Server (CMD)**. All messages must reach here.

### 🔐 Crypto Inspector (Right Panel)
This panel proves that **real cryptography** is happening, not just a simulation number.
*   **Cipher**: Shows the active encryption algorithm (e.g., `AES-256-GCM` or `ChaCha20-Poly1305`).
*   **Plaintext**: The original message content (e.g., "Telemetry from Drone 12...").
*   **Ciphertext**: The actual encrypted hex output.
*   **Integrity Checks**:
    *   **Nonce**: Unique number used once per message.
    *   **Auth Tag**: MAC (Message Authentication Code) ensuring no tampering.
    *   **Hash**: SHA3-256 fingerprint of the message.
*   **ECDH Sessions**: Shows active **Diffie-Hellman Key Exchanges** between drones and the command server.

---

## 🔄 3. Adaptive Mission Phases
 The system automatically switches phases based on round number (or manual override).

### 🟢 **PATROL Phase (Standard Security)**
*   **Goal**: Save battery while maintaining basic security.
*   **Crypto**: `AES-256-GCM` (Fast, hardware-accelerated).
*   **Routing**: 2 Hops (Short paths).
*   **Defense**: Low implementation (10% dummy traffic).
*   **Result**: High trace rates (~80%), but very low energy cost.

### 🟡 **SURVEILLANCE Phase (High Security)**
*   **Goal**: Increase protection as mission sensitivity rises.
*   **Crypto**: `AES-256-GCM` + **HMAC-SHA256** (Double integrity check) + **Ed25519 Signatures** (Non-repudiation).
*   **Routing**: 3 Hops (Harder to trace).
*   **Defense**: Medium implementation (30% dummy traffic).
*   **Result**: Trace rates drop to ~40-60%.

### 🔴 **THREAT Phase (Maximum Privacy)**
*   **Goal**: Zero tolerance for tracking. High energy cost accepted.
*   **Crypto**: `ChaCha20-Poly1305` (Resistant to side-channel attacks) + HMAC + Signatures.
*   **Routing**: 5 Hops (Deep onion routing).
*   **Defense**: High implementation (50% dummy traffic).
*   **Result**: **Trace Rate drops to near 0%**. The adversary is blind.

---

## 🕵️ 4. The Adversary Logic
The red "TRACE SUCCESS" metric is calculated based on:
1.  **Hop Count**: More relays = harder to traceback to the source.
2.  **Traffic Volume**: Constant traffic patterns are easier to analyze.
3.  **Dummy Traffic**: Fake messages confuse the adversary's statistical models.

**Scoring:**
*   **+20 Points**: Message delivered safely.
*   **+30 Bonus**: Message delivered *without* being traced.
*   **+5 Points**: Dummy message sent (strategic deception).
*   **Phase Bonus**: Extra points for surviving high-threat phases.

---

## 🎮 5. Gamification & Controls
*   **Step / Play**: Step through rounds manually or auto-play.
*   **Deploy Decoys**: Spends score to flood the network with fake messages, lowering adversary confidence.
*   **EMP Blast**: Emergency measure. Costs massive score (1000 pts) but blindly resets the adversary's knowledge to zero.
*   **Escalate Phase**: Manually force the swarm into THREAT mode to demonstrate high-security protocols.

---

## 📝 6. How to Run for Demo

1.  **Open Terminal**:
    ```bash
    streamlit run app.py
    ```
2.  **In Browser**:
    *   Click **START** to watch the autonomous system.
    *   Observe the **TRACE SUCCESS** drop as phases change.
    *   Point out the **Crypto Inspector** showing live encryption.
    *   Click **Deploy Decoys** to show active countermeasures.

---
*Created for Professor Presentation - Mission-Aware Energy-Balanced Adaptive UAV Framework*
