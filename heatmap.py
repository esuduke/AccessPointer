import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.animation as animation
from matplotlib.backend_bases import KeyEvent
from scipy.interpolate import griddata
import DatabaseHandler as db
import random

# List of floor plan images (replace with actual paths)
images = ["Floor1.png"]

database_handler = db.DatabaseHandler()
database = database_handler.get_data()

# Load image function
def load_image(image_path):
    return mpimg.imread(image_path)

# Initial setup
current_image_index = 0
terrain_map = load_image(images[current_image_index])
print("Terrain map loaded.")

# User position
user_x, user_y = 5, 5  # Starting position
step_size = 0.5  # Movement step

# Set up the figure
fig, ax = plt.subplots(figsize=(8, 6))
terrain_display = ax.imshow(terrain_map, extent=[0, 100, 0, 100], aspect='auto')

# Function to normalize the latitude and longitude to fit within a grid
def normalize_coordinates(lat, lon, min_lat, max_lat, min_lon, max_lon, grid_size=100):
    # Normalize latitude and longitude to fit within the grid size
    normalized_x = (lon - min_lon) / (max_lon - min_lon) * grid_size
    normalized_y = (lat - min_lat) / (max_lat - min_lat) * grid_size
    return normalized_x, normalized_y

# NEW Function to extract WiFi data from the database
def extract_wifi_data(database):
    wifi_data_points = []
    
    # Define the floor plan's lat, lon boundaries
    min_lat, max_lat = 43.0370, 43.0380  # Adjust to fit your floor plan's latitude range
    min_lon, max_lon = -76.1330, -76.1310  # Adjust to fit your floor plan's longitude range
    
    for unique_id, data in database.items():
        location = data.get('location')
        if location is not None:
            # Assuming `data` contains WiFi speed information like download, upload, and ping
            download = data['download']
            upload = data['upload']
            ping = data['ping']
            lat, lon = location['latitude'], location['longitude']
            lat = float(lat)
            lon = float(lon)
            
            # Normalize the latitude and longitude to grid coordinates
            x, y = normalize_coordinates(lat, lon, min_lat, max_lat, min_lon, max_lon)
            if x < 0 :
                x = random.uniform(0, 10) 
            if y < 0 :
                y = random.uniform(0, 10)
            if download > 500:
                download = 500
                
            wifi_data_points.append([x, y, download])  # Here we use `download` as WiFi speed
    
    return np.array(wifi_data_points)

# Generate fake data for testing
def generate_fake_data(num_entries=10):
    fake_entries = {}
    for i in range(num_entries):
        fake_entries[str(i + 100)] = {  # Unique ID for fake data
            "location": {
                "latitude": round(random.uniform(43.030, 43.050), 6),
                "longitude": round(random.uniform(-76.140, -76.120), 6)
            },
            "download": random.randint(50, 500),  # Random speed in Mbps
            "upload": random.randint(10, 100),
            "ping": random.randint(5, 50)
        }
    return fake_entries

database.update(generate_fake_data(20))  # Add fake data to the database

# Extract WiFi data from the database
wifi_data_points = extract_wifi_data(database)

# Function to generate heatmap data based on WiFi speeds
def generate_heatmap_data():
    """ Generate interpolated WiFi speed heatmap """
    X, Y = np.meshgrid(np.linspace(0, 100, 100), np.linspace(0, 100, 100))
    speeds = griddata(wifi_data_points[:, :2], wifi_data_points[:, 2], (X, Y), method='cubic', fill_value=400)
    return speeds

# Generate initial heatmap data
heatmap_data = generate_heatmap_data()

# Overlay heatmap
heatmap = ax.imshow(heatmap_data, cmap="coolwarm", alpha=0.5, extent=[0, 100, 0, 100], interpolation='bilinear', vmin=0, vmax=700)

# Colorbar
cbar = plt.colorbar(heatmap, ax=ax, label="WiFi Speed (Mbps)")

# Function to update the heatmap dynamically
def update(frame):
    """ Updates the heatmap visualization """
    global wifi_data_points
    # If you want to simulate data updates, you can add new data points here
    # For example, add random changes to the WiFi data points
    wifi_data_points = np.append(wifi_data_points, np.random.rand(20, 3) * [100, 100, 500], axis=0)
    heatmap_data = generate_heatmap_data()  # Update heatmap based on latest data
    heatmap.set_data(heatmap_data)  # Set new heatmap data
    return terrain_display, heatmap

# Animate heatmap
ani = animation.FuncAnimation(fig, update, interval=1000)  # Update every second (1000 ms)

# Show plot
plt.show()
