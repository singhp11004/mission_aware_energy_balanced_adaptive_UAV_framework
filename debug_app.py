
import os
import sys
import traceback

print("=== DEBUG START ===")

try:
    print("1. Testing Imports...")
    # Add current directory to path just in case
    sys.path.append(os.getcwd())
    
    from simulation_engine import SimulationEngine, MissionPhase
    import networkx as nx
    from pyvis.network import Network
    print("   Imports successful.")
    
    print("2. Testing Engine Initialization...")
    engine = SimulationEngine()
    print(f"   Engine initialized. Phase: {engine.state.phase}")
    
    print("3. Testing Simulation Step...")
    engine.step()
    print(f"   Step complete. Round: {engine.state.round_num}")
    print(f"   Metrics: {engine.state.metrics}")
    
    print("4. Testing PyVis Generation...")
    net = Network(height="600px", width="100%", bgcolor="#0E1117", font_color="white")
    
    for node_id, drone in engine.swarm.drones.items():
        net.add_node(node_id, label=str(node_id))
        
    # Check output path
    out_path = "debug_graph.html"
    print(f"   Saving graph to {out_path}...")
    net.save_graph(out_path)
    
    if os.path.exists(out_path):
        print("   Graph file created successfully.")
    else:
        print("   ERROR: Graph file not created.")
        
    print("\n=== DEBUG SUCCESS ===")

except Exception as e:
    print(f"\n=== DEBUG FAILED ===")
    print(f"Error: {e}")
    traceback.print_exc()
