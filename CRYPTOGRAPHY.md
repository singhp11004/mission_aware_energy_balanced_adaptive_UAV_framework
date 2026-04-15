# Z-MAPS: Cryptographic Engine Documentation

> [!WARNING]
> The Z-MAPS framework deprecates standard baseline cryptography (e.g., ECDSA, AES-GCM) in favor of deep-buffer, quantum-resistant, and high-velocity primitives.

The `crypto_engine.py` module forms a standardized, phase-adaptive cryptographic backend tailored for a high-resource UAV swarm environment. The engine utilizes state-based logic to switch between algorithms dynamically, depending on the mission phase's strict battery/security limitations.

---

## 1. Ephemeral Key Exchange: `X448`

Replaced NIST P-256 with the far superior **Curve448** via `X448`.
*   **Security Level**: Provides a 224-bit robust security margin.
*   **Usage**: Establishing secure session keys transiently across two interacting drones, natively discarding keys after transmission gaps to prevent subsequent compromise scenarios.

---

## 2. Primary AEAD Standard: `XChaCha20-Poly1305`

For payload security across the air interface, Z-MAPS utilizes **Extended-Nonce** ChaCha20.
*   **Why Not AES-GCM?**: Software-defined UAV processors map ChaCha20 operations with significantly less battery penalty compared to standard AES, which lacks hardware acceleration on lightweight IoT sensors.
*   **Why Extended Nonce?**: `XChaCha20` extends the 12-byte standard nonce to 24 bytes, creating functionally zero risk of collision when UAVs burst-transmit massive strings concurrently.

---

## 3. High-Integrity Commands: `Ed448` Signatures

Digital signatures are handled via the Goldilocks curve mechanism.
*   The Command Server (TOC) exclusively signs directional tasks (e.g., phase shifts, priority overrides) with `Ed448`.
*   Reduces potential adversarial network injections to an astronomically low probability vector.

---

## 4. Phase-Dictated Routing Engine (`CryptoEngine`)

The engine wraps payloads conditionally based on the active `MissionPhase`. E.g.,

### `PATROL` State
* **Cipher**: `XChaCha20-Poly1305`
* **HMAC**: `False`
* **Signed**: `False`
* *Logic*: Relies purely on the AEAD Poly1305 tag for authentication to reduce string byte-bloat and conserve transit energy.

### `ENGAGEMENT` State
* **Cipher**: `ChaCha20-Poly1305` + `HMAC-SHA512`
* **Signed**: `True`
* *Logic*: Switches slightly for processing performance and layers mandatory, unforgeable identity tracking over every sent packet at the cost of massive battery drain.

---

## 5. Onion Routing Encryption Structure
The function `onion_encrypt()` chains `XChaCha20-Poly1305` sequentially across defined relayed pathways (dictated by the RL Layer). It recursively bundles encrypted metadata, stripping off layers at each UAV node, ensuring intermediary bots possess zero contextual knowledge of the payload content modulo route progression.
