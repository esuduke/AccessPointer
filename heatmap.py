import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from scipy.interpolate import griddata
import DatabaseHandler as db
import os
import time
import numpy as np


# Config (building bounds)
FLOOR_PLAN_PATH = "Floor1.png"
OUTPUT_PATH = "static/heatmap.png"

# Updated building bounds (min/max latitudes and longitudes)
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
            #print("\nThis is lat and lon:", lat, lon)
            x, y = normalize_coordinates(lat, lon)
           # print("\nThis is x and y :", x,y)

            speed = min(entry.get("download", 0), 500)
            points.append([x, y, speed])
            # print(f"[Heatmap] Included: ID {unique_id}, x={x:.2f}, y={y:.2f}, speed={speed}")
        except Exception as e:
            print(f"[Heatmap] Skipping ID {unique_id}: error -> {e}")
    # print(f"[Heatmap] Usable WiFi points: {len(points)}")
    return np.array(points)

def generate_fake_wifi_data(num_points=10):
    """Generate fake WiFi data points within the building bounds."""
    fake_data = {}

    for i in range(num_points):
        lat = np.random.uniform(MIN_LAT, MAX_LAT)
        lon = np.random.uniform(MIN_LON, MAX_LON)
        speed = np.random.uniform(1, 500)  # Random WiFi speed between 1 and 500 Mbps
        x,y = normalize_coordinates(lat, lon)
        fake_data[f"fake_{i}"] = {
            "location": {"latitude": lat, "longitude": lon},
            "x": x,  # Store x
            "y": y,  # Store y
            "download": speed
        }

    return fake_data

def update_data_point(lat, lon, speed, unique_id, database):
    x, y = normalize_coordinates(lat, lon)
    database[unique_id] = {"location": {"latitude": lat, "longitude": lon}, "x": x, "y": y, "download": speed}
    print(f"Data point '{unique_id}' updated.")

# Example usage:


# Example usage:

def generate_heatmap(wifi_points, session_locations={}):
    if wifi_points.shape[0] < 3:
        print("[Heatmap] Not enough data points to generate heatmap.")
        return None

    X, Y = np.meshgrid(np.linspace(0, 100, GRID_SIZE), np.linspace(0, 100, GRID_SIZE))

    try:
        Z = griddata(wifi_points[:, :2], wifi_points[:, 2], (X, Y), method="nearest", fill_value=np.nan)
    except Exception as e:
        print(f"[Heatmap] Interpolation failed: {e}")
        return

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(terrain_map, extent=[0, 100, 0, 100], aspect="auto")
    heatmap = ax.imshow(Z, cmap="coolwarm", alpha=0.5, extent=[0, 100, 0, 100], vmin=0, vmax=700)

    if wifi_points.shape[0] > 0:
        ax.scatter(wifi_points[:, 0], wifi_points[:, 1], c="black", s=10, label="WiFi Points")

    for sid, (lat, lon) in session_locations.items():
        ux, uy = normalize_coordinates(lat, lon)
        ax.plot(ux, uy, "ko", markersize=5)
        ax.text(ux + 1, uy + 1, sid[:4], fontsize=6, color="black")

    plt.colorbar(heatmap, ax=ax, label="WiFi Speed (Mbps)")
   # plt.axis("off")  # Hide extra axes

    # Show the heatmap instead of saving and reloading it
    plt.show()

def main():
    database = database_handler.get_data()
    update_data_point(43.037925, -76.132871, 380, "specific_point", database)
    #database.update(generate_fake_wifi_data(40))
    print(extract_wifi_data(database))
    wifi_points = extract_wifi_data(database)
    generate_heatmap(wifi_points, session_locations={})

if __name__ == "__main__":
    main()

#if __name__ == "__main__":
 #   loop_generate_heatmap()
