"""
Configuration constants for UAV Swarm Simulation
"""

# Swarm Configuration
NUM_DRONES = 50
COMMAND_SERVER_ID = "CMD"
COMMUNICATION_RANGE = 0.3  # Normalized distance for NetworkX random geometric graph

# Battery Configuration
INITIAL_BATTERY = 100.0  # Percentage
LOW_BATTERY_THRESHOLD = 20.0  # Percentage
CRITICAL_BATTERY_THRESHOLD = 10.0  # Percentage

# Energy Cost Constants (in percentage units)
# Tuned so that 50 drones survive ~100 rounds at PATROL pace
ENERGY_ENCRYPTION = 0.15
ENERGY_RE_ENCRYPTION = 0.08
ENERGY_TRANSMISSION = 0.05
ENERGY_DUMMY_TRAFFIC = 0.03
ENERGY_RECEPTION = 0.02
ENERGY_ECDH_EXCHANGE = 0.08      # Key exchange cost
ENERGY_HMAC = 0.01              # HMAC computation
ENERGY_SIGNING = 0.06           # Ed25519 signing
ENERGY_HASHING = 0.005          # SHA-3 hashing
ENERGY_CHACHA20 = 0.10          # ChaCha20 (lighter than AES)

# Mission Phases
class MissionPhase:
    PATROL = "PATROL"
    SURVEILLANCE = "SURVEILLANCE"
    THREAT = "THREAT"

# Privacy Parameters per Mission Phase
MISSION_CONFIG = {
    MissionPhase.PATROL: {
        "routing_depth": 2,       # Number of relay hops
        "dummy_rate": 0.1,        # Probability of dummy traffic
        "timing_jitter_ms": 50,   # Random delay in ms
        "encryption_rounds": 1    # Number of re-encryption layers
    },
    MissionPhase.SURVEILLANCE: {
        "routing_depth": 3,
        "dummy_rate": 0.3,
        "timing_jitter_ms": 100,
        "encryption_rounds": 2
    },
    MissionPhase.THREAT: {
        "routing_depth": 5,
        "dummy_rate": 0.5,
        "timing_jitter_ms": 200,
        "encryption_rounds": 3
    }
}

# Cryptographic Configuration per Mission Phase
CRYPTO_CONFIG = {
    MissionPhase.PATROL: {
        "cipher": "AES-256-GCM",
        "hmac": False,
        "sign": False,
        "description": "Standard authenticated encryption",
    },
    MissionPhase.SURVEILLANCE: {
        "cipher": "AES-256-GCM",
        "hmac": True,
        "sign": True,
        "description": "Full auth + integrity + signatures",
    },
    MissionPhase.THREAT: {
        "cipher": "ChaCha20-Poly1305",
        "hmac": True,
        "sign": True,
        "description": "Max security — lightweight AEAD + dual auth",
    },
}

# Relay Selection Parameters
COOLDOWN_PENALTY = 0.5  # Penalty multiplier for recently used relays
COOLDOWN_DURATION = 5   # Number of rounds before cooldown expires
BATTERY_WEIGHT = 1.0    # Weight for battery level in relay selection

# Adversary Simulation Parameters
ADVERSARY_OBSERVATION_WINDOW = 10  # Number of messages to correlate
TRACE_SUCCESS_THRESHOLD = 0.7      # Confidence threshold for successful trace

# Simulation Parameters
SIMULATION_ROUNDS = 100
MESSAGES_PER_ROUND = 5
PHASE_CHANGE_INTERVAL = 30  # Rounds between phase changes

# Output Configuration
OUTPUT_DIR = "outputs"
