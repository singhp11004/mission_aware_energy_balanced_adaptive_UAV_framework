"""
Crypto Engine — Production-grade cryptographic systems for UAV swarm communication.

Implements:
  • X448                — Ephemeral key exchange between drones
  • XChaCha20-Poly1305  — Extended-nonce authenticated cryptography (Primary upgrade)
  • ChaCha20-Poly1305   — Lightweight AEAD for battery-constrained drones
  • HMAC-SHA512         — Message integrity / authentication codes
  • Ed448               — Digital signatures for command authentication
  • SHA-3 (Keccak-512)  — Cryptographic hashing / fingerprinting
"""

import os
import time
import hmac
import hashlib
import json
import base64
from collections import deque
from typing import Dict, List, Optional, Tuple

# PyCryptodome — symmetric ciphers
from Crypto.Cipher import AES, ChaCha20_Poly1305
from Crypto.Random import get_random_bytes

# Python cryptography lib — asymmetric ciphers
from cryptography.hazmat.primitives.asymmetric.x448 import X448PrivateKey, X448PublicKey
from cryptography.hazmat.primitives.asymmetric.ed448 import (
    Ed448PrivateKey, Ed448PublicKey,
)
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


# ─────────────────────────────────────────────────────────────
#  Crypto Operation Log  — records every operation for the UI
# ─────────────────────────────────────────────────────────────

class CryptoOpLog:
    """Thread-safe log of cryptographic operations for dashboard display."""

    def __init__(self, maxlen: int = 200):
        self.ops: deque = deque(maxlen=maxlen)

    def record(self, op_type: str, algorithm: str, *, drone_id: int = -1,
               input_hex: str = "", output_hex: str = "",
               key_hex: str = "", extra: Dict = None, elapsed_us: int = 0):
        self.ops.appendleft({
            "ts": time.time(),
            "op": op_type,
            "alg": algorithm,
            "drone": drone_id,
            "in": input_hex[:64],       # truncated for display
            "out": output_hex[:64],
            "key": key_hex[:32],
            "extra": extra or {},
            "us": elapsed_us,           # microseconds
        })

    def recent(self, n: int = 30) -> List[Dict]:
        return list(self.ops)[:n]

    def stats(self) -> Dict:
        """Aggregate timing statistics per algorithm."""
        from collections import defaultdict
        buckets: Dict[str, List[int]] = defaultdict(list)
        for op in self.ops:
            buckets[op["alg"]].append(op["us"])
        return {
            alg: {
                "count": len(times),
                "avg_us": sum(times) // max(len(times), 1),
                "max_us": max(times) if times else 0,
            }
            for alg, times in buckets.items()
        }


# ─────────────────────────────────────────────────────────────
#  1. X448 Key Exchange (Post-quantum capable sizes)
# ─────────────────────────────────────────────────────────────

class X448KeyPair:
    """X448 keypair for a single drone."""

    def __init__(self):
        self._private = X448PrivateKey.generate()
        self.public = self._private.public_key()

    def derive_shared_secret(self, peer_public: X448PublicKey) -> bytes:
        """Derive 32-byte shared secret via X448 + HKDF-SHA512."""
        raw = self._private.exchange(peer_public)
        return HKDF(
            algorithm=hashes.SHA512(),
            length=32,
            salt=None,
            info=b"uav-swarm-session-key",
        ).derive(raw)

    def public_key_bytes(self) -> bytes:
        return self.public.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )

    def fingerprint(self) -> str:
        """Short hex fingerprint of the public key."""
        return hashlib.sha3_512(self.public_key_bytes()).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────
#  2. XChaCha20-Poly1305  (Extended Nonce Authenticated Encryption)
# ─────────────────────────────────────────────────────────────

def xchacha_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> Dict[str, str]:
    """XChaCha20-Poly1305 encrypt. Returns {nonce, ciphertext, tag} as hex."""
    # 24-byte nonce forces XChaCha20 mode in PyCryptodome 
    nonce = get_random_bytes(24)
    cipher = ChaCha20_Poly1305.new(key=key, nonce=nonce)
    if aad:
        cipher.update(aad)
    ct, tag = cipher.encrypt_and_digest(plaintext)
    return {
        "nonce": nonce.hex(),
        "ciphertext": ct.hex(),
        "tag": tag.hex(),
    }


def xchacha_decrypt(key: bytes, bundle: Dict[str, str], aad: bytes = b"") -> bytes:
    """XChaCha20-Poly1305 decrypt + verify."""
    cipher = ChaCha20_Poly1305.new(key=key, nonce=bytes.fromhex(bundle["nonce"]))
    if aad:
        cipher.update(aad)
    return cipher.decrypt_and_verify(
        bytes.fromhex(bundle["ciphertext"]),
        bytes.fromhex(bundle["tag"]),
    )



# ─────────────────────────────────────────────────────────────
#  3. ChaCha20-Poly1305  (Lightweight AEAD)
# ─────────────────────────────────────────────────────────────

def chacha_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> Dict[str, str]:
    """ChaCha20-Poly1305 encrypt.  Returns {nonce, ciphertext, tag} as hex."""
    cipher = ChaCha20_Poly1305.new(key=key)
    if aad:
        cipher.update(aad)
    ct, tag = cipher.encrypt_and_digest(plaintext)
    return {
        "nonce": cipher.nonce.hex(),
        "ciphertext": ct.hex(),
        "tag": tag.hex(),
    }


def chacha_decrypt(key: bytes, bundle: Dict[str, str], aad: bytes = b"") -> bytes:
    """ChaCha20-Poly1305 decrypt + verify."""
    cipher = ChaCha20_Poly1305.new(key=key, nonce=bytes.fromhex(bundle["nonce"]))
    if aad:
        cipher.update(aad)
    return cipher.decrypt_and_verify(
        bytes.fromhex(bundle["ciphertext"]),
        bytes.fromhex(bundle["tag"]),
    )


# ─────────────────────────────────────────────────────────────
#  4. HMAC-SHA512
# ─────────────────────────────────────────────────────────────

def hmac_sha512(key: bytes, message: bytes) -> str:
    """Compute HMAC-SHA512 and return hex digest."""
    return hmac.new(key, message, hashlib.sha512).hexdigest()


def hmac_verify(key: bytes, message: bytes, expected_hex: str) -> bool:
    """Constant-time HMAC verification."""
    computed = hmac.new(key, message, hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed, expected_hex)


# ─────────────────────────────────────────────────────────────
#  5. Ed448 Digital Signatures
# ─────────────────────────────────────────────────────────────

class Ed448Signer:
    """Ed448 keypair for signing / verification."""

    def __init__(self):
        self._private = Ed448PrivateKey.generate()
        self.public = self._private.public_key()

    def sign(self, data: bytes) -> str:
        """Sign data; return hex-encoded signature."""
        return self._private.sign(data).hex()

    def verify(self, data: bytes, signature_hex: str) -> bool:
        """Verify signature; returns True or False."""
        try:
            self.public.verify(bytes.fromhex(signature_hex), data)
            return True
        except Exception:
            return False

    def public_key_hex(self) -> str:
        raw = self.public.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return raw.hex()


# ─────────────────────────────────────────────────────────────
#  6. SHA-3 Hashing
# ─────────────────────────────────────────────────────────────

def sha3_hash(data: bytes) -> str:
    """SHA-3 (Keccak-512) hash, hex."""
    return hashlib.sha3_512(data).hexdigest()


# ─────────────────────────────────────────────────────────────
#  CryptoEngine  — unified interface used by simulation_engine
# ─────────────────────────────────────────────────────────────

class CryptoEngine:
    """
    Unified cryptographic engine for the UAV swarm.

    Each drone gets:
      • An X448 keypair  (key exchange)
      • An Ed448 keypair  (signing)

    The engine mediates all encryption, signature, and integrity
    operations and logs everything for real-time dashboard display.
    """

    # Algorithm selection per mission phase
    PHASE_CRYPTO = {
        "PATROL": {
            "cipher": "XChaCha20-Poly1305",
            "hmac": False,
            "sign": False,
            "description": "Extended-nonce authenticated encryption",
        },
        "SURVEILLANCE": {
            "cipher": "XChaCha20-Poly1305",
            "hmac": True,
            "sign": True,
            "description": "Full authentication + integrity",
        },
        "THREAT": {
            "cipher": "ChaCha20-Poly1305",
            "hmac": True,
            "sign": True,
            "description": "Max security — lightweight AEAD + dual auth",
        },
    }

    def __init__(self, num_drones: int = 50):
        self.log = CryptoOpLog()

        # Per-drone keypairs
        self.ecdh_keys: Dict[int, X448KeyPair] = {}
        self.signers: Dict[int, Ed448Signer] = {}
        self.session_keys: Dict[str, bytes] = {}  # "src-dst" -> 32 bytes

        for i in range(num_drones):
            self.ecdh_keys[i] = X448KeyPair()
            self.signers[i] = Ed448Signer()

        # Base station keys
        self.ecdh_keys[-1] = X448KeyPair()  # CMD
        self.signers[-1] = Ed448Signer()

    # ─────────── key exchange ───────────

    def establish_session(self, src_id: int, dst_id: int) -> bytes:
        """Perform X448 key exchange between two nodes."""
        t0 = time.perf_counter_ns()
        src_kp = self.ecdh_keys.get(src_id)
        dst_kp = self.ecdh_keys.get(dst_id)
        if not src_kp or not dst_kp:
            return get_random_bytes(32)
        shared = src_kp.derive_shared_secret(dst_kp.public)
        elapsed = (time.perf_counter_ns() - t0) // 1000
        pair_key = f"{src_id}-{dst_id}"
        self.session_keys[pair_key] = shared
        self.log.record(
            "KEY_EXCHANGE", "X448",
            drone_id=src_id,
            key_hex=shared.hex(),
            extra={"peer": dst_id, "fingerprint": dst_kp.fingerprint()},
            elapsed_us=elapsed,
        )
        return shared

    # ─────────── encrypt ───────────

    def encrypt_message(self, plaintext: str, phase: str,
                        sender_id: int, receiver_id: int = -1) -> Dict:
        """
        Full encrypt pipeline for a message.
        Returns a CryptoBundle dict with all crypto artifacts.
        """
        cfg = self.PHASE_CRYPTO.get(phase, self.PHASE_CRYPTO["PATROL"])

        # 1. Derive session key via ECDH
        session_key = self.establish_session(sender_id, receiver_id)

        plain_bytes = plaintext.encode("utf-8")
        aad = f"uav:{sender_id}:{receiver_id}:{phase}".encode()

        # 2. Hash plaintext (SHA-3)
        t0 = time.perf_counter_ns()
        msg_hash = sha3_hash(plain_bytes)
        us = (time.perf_counter_ns() - t0) // 1000
        self.log.record("HASH", "SHA3-512", drone_id=sender_id,
                        input_hex=plain_bytes.hex()[:32],
                        output_hex=msg_hash, elapsed_us=us)

        # 3. Encrypt with selected cipher
        t0 = time.perf_counter_ns()
        if cfg["cipher"] == "ChaCha20-Poly1305":
            enc_bundle = chacha_encrypt(session_key, plain_bytes, aad)
        else:
            enc_bundle = xchacha_encrypt(session_key, plain_bytes, aad)
        us = (time.perf_counter_ns() - t0) // 1000
        self.log.record(
            "ENCRYPT", cfg["cipher"], drone_id=sender_id,
            input_hex=plain_bytes.hex()[:32],
            output_hex=enc_bundle["ciphertext"][:32],
            key_hex=session_key.hex()[:16],
            elapsed_us=us,
        )

        # 4. HMAC (optional)
        hmac_tag = ""
        if cfg["hmac"]:
            t0 = time.perf_counter_ns()
            hmac_tag = hmac_sha512(session_key, enc_bundle["ciphertext"].encode())
            us = (time.perf_counter_ns() - t0) // 1000
            self.log.record("HMAC", "HMAC-SHA512", drone_id=sender_id,
                            output_hex=hmac_tag, elapsed_us=us)

        # 5. Sign (optional)
        signature = ""
        if cfg["sign"]:
            signer = self.signers.get(sender_id)
            if signer:
                t0 = time.perf_counter_ns()
                signature = signer.sign(enc_bundle["ciphertext"].encode())
                us = (time.perf_counter_ns() - t0) // 1000
                self.log.record(
                    "SIGN", "Ed448", drone_id=sender_id,
                    output_hex=signature[:32],
                    extra={"pubkey": signer.public_key_hex()[:16]},
                    elapsed_us=us,
                )

        return {
            "cipher": cfg["cipher"],
            "encrypted": enc_bundle,
            "hash": msg_hash,
            "hmac": hmac_tag,
            "signature": signature,
            "sender_pubkey": self.signers[sender_id].public_key_hex() if sender_id in self.signers else "",
            "aad": aad.decode(),
            "phase": phase,
            "plaintext_preview": plaintext[:40],
        }

    # ─────────── decrypt ───────────

    def decrypt_message(self, bundle: Dict, receiver_id: int,
                        sender_id: int) -> Optional[str]:
        """Decrypt and verify a CryptoBundle."""
        pair_key = f"{sender_id}-{receiver_id}"
        session_key = self.session_keys.get(pair_key)
        if not session_key:
            session_key = self.establish_session(sender_id, receiver_id)

        aad = bundle.get("aad", "").encode()
        enc = bundle["encrypted"]

        # Verify HMAC
        if bundle.get("hmac"):
            if not hmac_verify(session_key, enc["ciphertext"].encode(), bundle["hmac"]):
                self.log.record("HMAC_FAIL", "HMAC-SHA512", drone_id=receiver_id)
                return None

        # Verify signature
        if bundle.get("signature"):
            signer = self.signers.get(sender_id)
            if signer and not signer.verify(enc["ciphertext"].encode(), bundle["signature"]):
                self.log.record("SIG_FAIL", "Ed448", drone_id=receiver_id)
                return None

        # Decrypt
        try:
            if bundle["cipher"] == "ChaCha20-Poly1305":
                plain = chacha_decrypt(session_key, enc, aad)
            else:
                plain = xchacha_decrypt(session_key, enc, aad)
            return plain.decode("utf-8")
        except Exception:
            self.log.record("DECRYPT_FAIL", bundle["cipher"], drone_id=receiver_id)
            return None

    # ─────────── onion wrap  (multi-relay) ───────────

    def onion_encrypt(self, plaintext: str, phase: str,
                      sender_id: int, relay_ids: List[int]) -> Dict:
        """
        Onion-encrypt: each relay layer adds its own AES-GCM wrapping
        using an ECDH-derived key from sender → relay.
        """
        current = plaintext.encode("utf-8")
        layers = []

        # Wrap from outermost relay inward (reverse order)
        for relay_id in reversed(relay_ids):
            key = self.establish_session(sender_id, relay_id)
            aad = f"onion-layer:{sender_id}:{relay_id}".encode()
            t0 = time.perf_counter_ns()
            enc = xchacha_encrypt(key, current, aad)
            us = (time.perf_counter_ns() - t0) // 1000
            self.log.record(
                "ONION_LAYER", "XChaCha20-Poly1305", drone_id=sender_id,
                output_hex=enc["ciphertext"][:24],
                extra={"relay": relay_id, "layer": len(layers) + 1},
                elapsed_us=us,
            )
            current = json.dumps(enc).encode("utf-8")
            layers.append({"relay": relay_id, "nonce": enc["nonce"][:8]})

        return {
            "onion_payload": current.hex(),
            "layers": layers,
            "total_layers": len(layers),
        }

    # ─────────── status helpers ───────────

    def get_drone_keys_info(self) -> List[Dict]:
        """Return public key info for all drones (for dashboard)."""
        info = []
        for did, kp in self.ecdh_keys.items():
            if did == -1:
                label = "CMD"
            else:
                label = f"D{did}"
            info.append({
                "id": did,
                "label": label,
                "ecdh_fp": kp.fingerprint(),
                "ed448_pk": self.signers[did].public_key_hex()[:16] if did in self.signers else "",
            })
        return info

    def get_phase_config(self, phase: str) -> Dict:
        return self.PHASE_CRYPTO.get(phase, self.PHASE_CRYPTO["PATROL"])

    # ─────────── self-test ───────────

    def self_test(self) -> Dict:
        """Run a comprehensive self-test of all crypto primitives."""
        results = {}

        # 1. X448
        try:
            k = self.establish_session(0, 1)
            results["X448"] = "✅ OK" if len(k) == 32 else "❌ FAIL"
        except Exception as e:
            results["X448"] = f"❌ {e}"

        # 2. XChaCha20-Poly1305 roundtrip
        try:
            key = get_random_bytes(32)
            enc = xchacha_encrypt(key, b"hello world", b"aad")
            dec = xchacha_decrypt(key, enc, b"aad")
            results["XChaCha20-Poly1305"] = "✅ OK" if dec == b"hello world" else "❌ FAIL"
        except Exception as e:
            results["XChaCha20-Poly1305"] = f"❌ {e}"

        # 3. ChaCha20
        try:
            key = get_random_bytes(32)
            enc = chacha_encrypt(key, b"chacha test", b"aad")
            dec = chacha_decrypt(key, enc, b"aad")
            results["ChaCha20-Poly1305"] = "✅ OK" if dec == b"chacha test" else "❌ FAIL"
        except Exception as e:
            results["ChaCha20-Poly1305"] = f"❌ {e}"

        # 4. HMAC
        try:
            key = get_random_bytes(32)
            tag = hmac_sha512(key, b"integrity test")
            ok = hmac_verify(key, b"integrity test", tag)
            results["HMAC-SHA512"] = "✅ OK" if ok else "❌ FAIL"
        except Exception as e:
            results["HMAC-SHA512"] = f"❌ {e}"

        # 5. Ed448
        try:
            sig = self.signers[0].sign(b"sign me")
            ok = self.signers[0].verify(b"sign me", sig)
            results["Ed448"] = "✅ OK" if ok else "❌ FAIL"
        except Exception as e:
            results["Ed448"] = f"❌ {e}"

        # 6. SHA-3
        try:
            h = sha3_hash(b"keccak test")
            results["SHA3-512"] = "✅ OK" if len(h) == 128 else "❌ FAIL"
        except Exception as e:
            results["SHA3-512"] = f"❌ {e}"

        # 7. Full encrypt/decrypt roundtrip
        try:
            bundle = self.encrypt_message("secret payload", "THREAT", 0)
            plain = self.decrypt_message(bundle, -1, 0)
            results["Full Roundtrip"] = "✅ OK" if plain == "secret payload" else "❌ FAIL"
        except Exception as e:
            results["Full Roundtrip"] = f"❌ {e}"

        # 8. Onion encryption
        try:
            onion = self.onion_encrypt("onion data", "THREAT", 0, [1, 2, 3])
            results["Onion Routing"] = "✅ OK" if onion["total_layers"] == 3 else "❌ FAIL"
        except Exception as e:
            results["Onion Routing"] = f"❌ {e}"

        return results
