"""
Layer 1 — Data Acquisition

Responsible for collecting raw telemetry from drones, classifying data
types, and producing structured TelemetryPacket objects for the
Prioritization layer.
"""

from __future__ import annotations

import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from zmaps.mission.phases import OperationalPhase


# ─────────────────────── Data Types ───────────────────────

class DataType(str, Enum):
    """Classification of telemetry data types."""

    POSITION = "POSITION"               # GPS / INS position update
    TARGET_ID = "TARGET_ID"             # Target identification data
    SURVEILLANCE_FEED = "SURV_FEED"     # Video / sensor feed
    STATUS = "STATUS"                   # Battery, health, state
    ALERT = "ALERT"                     # Emergency alert / threat detection
    COMMAND_ACK = "CMD_ACK"             # Acknowledgement of a command


# ─────────────────────── Telemetry Packet ───────────────────────

@dataclass
class TelemetryPacket:
    """
    A structured unit of telemetry produced by the Data Acquisition layer.

    Attributes
    ----------
    drone_id : int
        Originating drone.
    data_type : DataType
        Classification of the payload content.
    payload : str
        Raw telemetry content.
    size_bytes : int
        Approximate payload size (for energy modeling).
    timestamp : float
        Collection time (Unix epoch seconds).
    phase : OperationalPhase
        Operational phase at the time of collection.
    metadata : dict
        Arbitrary key-value metadata (sensor readings, etc.).
    """

    drone_id: int
    data_type: DataType
    payload: str
    size_bytes: int = 64
    timestamp: float = field(default_factory=time.time)
    phase: OperationalPhase = OperationalPhase.PATROL
    metadata: Dict = field(default_factory=dict)


# ─────────────────────── Classifier ───────────────────────

class TelemetryClassifier:
    """
    Rule-based classifier that assigns a DataType to raw payloads.

    In a production system this would use NLP / semantic analysis;
    here we use keyword heuristics that match the simulation's
    payload patterns.
    """

    KEYWORD_MAP = {
        "target": DataType.TARGET_ID,
        "hostile": DataType.TARGET_ID,
        "identified": DataType.TARGET_ID,
        "alert": DataType.ALERT,
        "emergency": DataType.ALERT,
        "threat": DataType.ALERT,
        "video": DataType.SURVEILLANCE_FEED,
        "image": DataType.SURVEILLANCE_FEED,
        "feed": DataType.SURVEILLANCE_FEED,
        "battery": DataType.STATUS,
        "health": DataType.STATUS,
        "status": DataType.STATUS,
        "ack": DataType.COMMAND_ACK,
    }

    @classmethod
    def classify(cls, payload: str) -> DataType:
        """Return the best-matching DataType for a payload string."""
        lower = payload.lower()
        for keyword, dtype in cls.KEYWORD_MAP.items():
            if keyword in lower:
                return dtype
        # Default to POSITION (most common telemetry)
        return DataType.POSITION


# ─────────────────────── Data Acquisition Layer ───────────────────────

class DataAcquisitionLayer:
    """
    Layer 1: Collects telemetry from active drones and emits
    structured TelemetryPacket objects.

    Parameters
    ----------
    classifier : TelemetryClassifier or None
        Custom classifier; defaults to the built-in rule-based one.
    """

    def __init__(self, classifier: Optional[TelemetryClassifier] = None):
        self.classifier = classifier or TelemetryClassifier()
        self.packets_collected: int = 0

    def collect(
        self,
        drone_id: int,
        payload: str,
        phase: OperationalPhase,
        *,
        metadata: Optional[Dict] = None,
    ) -> List[TelemetryPacket]:
        """
        Collect a single telemetry payload, implementing 'Noise-Free Random Segmentation'.
        The payload is chunked into random sizes (50 to 1000 bytes) without using dummy
        padding overlays. Returns a list of segments as independent packets.
        """
        data_type = self.classifier.classify(payload)
        
        # We must chunk the payload string into random lengths [50, 1000]
        payload_bytes = payload.encode("utf-8")
        
        if not payload_bytes:
            # Handle empty
            return []
            
        packets = []
        idx = 0
        while idx < len(payload_bytes):
            chunk_size = random.randint(50, 1000)
            chunk_bytes = payload_bytes[idx:idx + chunk_size]
            
            chunk_packet = TelemetryPacket(
                drone_id=drone_id,
                data_type=data_type,
                payload=chunk_bytes.decode('utf-8', errors='ignore'),
                size_bytes=len(chunk_bytes),
                phase=phase,
                metadata=metadata or {},
            )
            packets.append(chunk_packet)
            idx += chunk_size
            self.packets_collected += 1
            
        return packets

    def collect_batch(
        self,
        payloads: List[Dict],
        phase: OperationalPhase,
    ) -> List[TelemetryPacket]:
        """
        Collect multiple payloads at once.

        Each element of *payloads* must have keys ``drone_id`` and ``payload``,
        with an optional ``metadata`` dict.
        """
        return [
            self.collect(
                drone_id=p["drone_id"],
                payload=p["payload"],
                phase=phase,
                metadata=p.get("metadata"),
            )
            for p in payloads
        ]

    def get_stats(self) -> Dict:
        return {"packets_collected": self.packets_collected}
