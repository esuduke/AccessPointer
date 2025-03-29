import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from scipy.interpolate import griddata
import DatabaseHandler as db
import os
import time

# Config (building bounds)
FLOOR_PLAN_PATH = "Floor1.png"
OUTPUT_PATH = "static/heatmap.png"
MIN_LAT = 43.037306
MAX_LAT = 43.037944
MIN_LON = -76.132889
MAX_LON = -76.132222
GRID_SIZE = 100

# Ensure static directory exists
os.makedirs("static", exist_ok=True)

# Load floor plan image
try:
    terrain_map = mpimg.imread(FLOOR_PLAN_PATH)
except FileNotFoundError:
    raise FileNotFoundError(f"Floor plan image '{FLOOR_PLAN_PATH}' not found.")

# Database handler
database_handler = db.DatabaseHandler()

def clamp(val, min_val, max_val):
    return max(min_val, min(val, max_val))

def normalize_coordinates(lat, lon):
    # Clamp lat/lon to building bounds
    lat = clamp(lat, MIN_LAT, MAX_LAT)
    lon = clamp(lon, MIN_LON, MAX_LON)

    # Normalize to 0–100 grid
    x = (lon - MIN_LON) / (MAX_LON - MIN_LON) * GRID_SIZE
    y = (lat - MIN_LAT) / (MAX_LAT - MIN_LAT) * GRID_SIZE

    # ✅ Rotate 90° CLOCKWISE (SW → NW, SE → NE, etc.)
    x_rotated = GRID_SIZE - y
    y_rotated = x
    return x_rotated, y_rotated


def extract_wifi_data(database):
    points = []
    # print(f"[Heatmap] Total entries from database: {len(database)}")

    for unique_id, entry in database.items():
        loc = entry.get("location")
        if not loc:
            # print(f"[Heatmap] Skipping ID {unique_id}: no location.")
            continue
        try:
            lat = float(loc["latitude"])
            lon = float(loc["longitude"])
            x, y = normalize_coordinates(lat, lon)

            speed = min(entry.get("download", 0), 500)
            points.append([x, y, speed])
            # print(f"[Heatmap] Included: ID {unique_id}, x={x:.2f}, y={y:.2f}, speed={speed}")
        except Exception as e:
            print(f"[Heatmap] Skipping ID {unique_id}: error -> {e}")
    # print(f"[Heatmap] Usable WiFi points: {len(points)}")
    return np.array(points)

def generate_heatmap(wifi_points, session_locations={}):
    # print("[Heatmap] Generating heatmap...")

    if wifi_points.shape[0] < 3:
        print("[Heatmap] Not enough data points to generate heatmap.")
        return None

    X, Y = np.meshgrid(np.linspace(0, 100, GRID_SIZE), np.linspace(0, 100, GRID_SIZE))

    # Interpolation with fallback
    for method in ['cubic', 'linear', 'nearest']:
        try:
            Z = griddata(wifi_points[:, :2], wifi_points[:, 2], (X, Y), method=method, fill_value=0)
            # print(f"[Heatmap] Interpolation succeeded with method: {method}")
            break
        except Exception as e:
            print(f"[Heatmap] Interpolation failed with method '{method}': {e}")
            Z = None

    if Z is None:
        print("[Heatmap] All interpolation methods failed. Skipping heatmap generation.")
        return

    # Plotting
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(terrain_map, extent=[0, 100, 0, 100], aspect='auto')
    ax.imshow(Z, cmap="coolwarm", alpha=0.5, extent=[0, 100, 0, 100], vmin=0, vmax=500)

    # Optional: visualize raw WiFi points
    if wifi_points.shape[0] > 0:
        ax.scatter(wifi_points[:, 0], wifi_points[:, 1], c='black', s=10, label='WiFi Points')

    # Optional: plot user locations
    for sid, (lat, lon) in session_locations.items():
        ux, uy = normalize_coordinates(lat, lon)
        ax.plot(ux, uy, 'ko', markersize=5)
        ax.text(ux + 1, uy + 1, sid[:4], fontsize=6, color='black')

    plt.colorbar(ax.images[1], ax=ax, label="WiFi Speed (Mbps)")

    # print(f"[Heatmap] Attempting to save to: {os.path.abspath(OUTPUT_PATH)}")
    plt.savefig(OUTPUT_PATH, bbox_inches="tight")
    plt.close(fig)
    # print(f"[Heatmap] Heatmap saved to {OUTPUT_PATH}")

def loop_generate_heatmap():
    while True:
        try:
            database = database_handler.get_data()
            wifi_points = extract_wifi_data(database)
            generate_heatmap(wifi_points, session_locations={})
        except Exception as e:
            print(f"[Heatmap] Error: {e}")
        time.sleep(30)

if __name__ == "__main__":
    loop_generate_heatmap()
