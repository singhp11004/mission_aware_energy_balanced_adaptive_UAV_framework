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
ENERGY_ENCRYPTION = 0.5
ENERGY_RE_ENCRYPTION = 0.3
ENERGY_TRANSMISSION = 0.2
ENERGY_DUMMY_TRAFFIC = 0.1
ENERGY_RECEPTION = 0.05

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
