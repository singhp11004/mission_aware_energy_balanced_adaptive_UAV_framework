
import matplotlib.pyplot as plt
import os

def create_icon(filename, color, text=None):
    fig, ax = plt.subplots(figsize=(1, 1), dpi=100)
    circle = plt.Circle((0.5, 0.5), 0.4, color=color, alpha=0.9)
    ax.add_artist(circle)
    if text:
        ax.text(0.5, 0.5, text, color='white', ha='center', va='center', fontsize=20, fontweight='bold')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    # Transparent background
    fig.patch.set_alpha(0.0)
    plt.savefig(f"assets/{filename}", bbox_inches='tight', pad_inches=0, transparent=True)
    plt.close()

os.makedirs("assets", exist_ok=True)

# Blue Drone (Normal)
create_icon("drone_blue.png", "#3498db")

# Red Drone (Compromised/Adversary)
create_icon("drone_red.png", "#e74c3c")

# Base Station (Green)
create_icon("base_station.png", "#2ecc71", "B")

print("Assets created successfully.")
