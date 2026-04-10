import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from zmaps.mission.phases import OperationalPhase, PhaseSequencer
from zmaps.layers.data_acquisition import DataAcquisitionLayer, DataType
from zmaps.layers.prioritization import PrioritizationLayer
from zmaps.mission.profiles import get_profile

def test_phase_sequencer_hysteresis():
    seq = PhaseSequencer(hysteresis_rounds=5)
    assert seq.current == OperationalPhase.TRANSIT
    
    # Needs 5 ticks before advancing
    seq.tick()
    seq.advance()
    assert seq.current == OperationalPhase.TRANSIT
    
    for _ in range(4):
        seq.tick()
    seq.advance()
    assert seq.current == OperationalPhase.PATROL

def test_data_acquisition_classification():
    l1 = DataAcquisitionLayer()
    
    # Target keyword
    packet = l1.collect(1, "Target acquired at sector 7G", OperationalPhase.ENGAGEMENT)
    assert packet.data_type == DataType.TARGET_ID
    
    # Alert keyword
    packet2 = l1.collect(2, "Emergency: threat detected", OperationalPhase.PATROL)
    assert packet2.data_type == DataType.ALERT
    
    # Default
    packet3 = l1.collect(3, "Heading 090, speed 20", OperationalPhase.TRANSIT)
    assert packet3.data_type == DataType.POSITION

def test_prioritization_logic():
    l1 = DataAcquisitionLayer()
    l2 = PrioritizationLayer()
    
    # Target in engagement = critical
    pkt_target = l1.collect(1, "hostile identified", OperationalPhase.ENGAGEMENT)
    msg_target = l2.prioritize(pkt_target)
    assert msg_target.priority >= 0.9  # very high priority
    assert msg_target.enhanced == True # Should get enhanced protection
    
    # Status in transit
    pkt_status = l1.collect(2, "battery normal", OperationalPhase.TRANSIT)
    msg_status = l2.prioritize(pkt_status)
    assert msg_status.priority < 0.5   # low priority
    assert msg_status.enhanced == False

    # Check phase specific overrides
    prof_target = get_profile(OperationalPhase.ENGAGEMENT)
    prof_status = get_profile(OperationalPhase.TRANSIT)

    assert msg_target.recommended_routing_depth >= prof_target.routing_depth
    assert msg_target.recommended_dummy_rate >= prof_target.dummy_rate
    assert msg_target.recommended_multipath == True
