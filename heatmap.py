import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.animation as animation
from scipy.interpolate import griddata
import DatabaseHandler as db
import random

# List of floor plan images (replace with actual paths)
images = [
    "Floor1.png",
]

database_handler = db.DatabaseHandler()
database = database_handler.get_data()

# Load image function
def load_image(image_path):
    return mpimg.imread(image_path)

# Initial setup
current_image_index = 0
terrain_map = load_image(images[current_image_index])
print("Terrain map loaded.")

# Define the min/max latitudes & longitudes for scaling
min_lat, max_lat = 43.0370, 43.0380  # Adjust based on your map
min_lon, max_lon = -76.1330, -76.1310  # Adjust based on your map

# User position
user_x, user_y = 5, 5  # Starting position
step_size = 0.5  # Movement step

# Set up the figure
fig, ax = plt.subplots(figsize=(8, 6))

# Display floor plan with correct lat/lon scaling
terrain_display = ax.imshow(terrain_map, extent=[min_lon, max_lon, min_lat, max_lat], aspect='auto')

# Function to normalize coordinates within the latitude/longitude range
def normalize_coordinates(lat, lon):
    x = (lon - min_lon) / (max_lon - min_lon) * (max_lon - min_lon) + min_lon
    y = (lat - min_lat) / (max_lat - min_lat) * (max_lat - min_lat) + min_lat
    return x, y

# Function to extract WiFi data from the database
def extract_wifi_data(database):
    wifi_data_points = []
    
    for unique_id, data in database.items():
        location = data.get('location')
        if location is not None:
            download = data['download']
            lat, lon = float(location['latitude']), float(location['longitude'])
            
            # Normalize lat/lon
            x, y = normalize_coordinates(lat, lon)
            
            # Ensure x, y are within bounds
            if x < min_lon or x > max_lon:
                x = random.uniform(min_lon, max_lon)
            if y < min_lat or y > max_lat:
                y = random.uniform(min_lat, max_lat)
            if download > 500:
                download = 500  # Cap download speed
            
            wifi_data_points.append([x, y, download])  # Store (x, y, WiFi speed)
    
    return np.array(wifi_data_points)

# Function to generate fake WiFi data for testing
def generate_fake_data(num_entries=10):
    fake_entries = {}
    for i in range(num_entries):
        fake_entries[str(i + 100)] = {  # Unique ID for fake data
            "location": {
                "latitude": round(random.uniform(min_lat, max_lat), 6),
                "longitude": round(random.uniform(min_lon, max_lon), 6)
            },
            "download": random.randint(50, 500),  # Random speed in Mbps
            "upload": random.randint(10, 100),
            "ping": random.randint(5, 50)
        }
    return fake_entries

# Add fake data and update database
database.update(generate_fake_data(300)) 

# Extract WiFi data
wifi_data_points = extract_wifi_data(database)

#print(wifi_data_points)

# Function to generate heatmap data based on WiFi speeds
def generate_heatmap_data():
    """ Generate interpolated WiFi speed heatmap using lat/lon grid """
    X, Y = np.meshgrid(np.linspace(min_lon, max_lon, 100), np.linspace(min_lat, max_lat, 100))
    speeds = griddata(wifi_data_points[:, :2], wifi_data_points[:, 2], (X, Y), method='cubic', fill_value=np.nan)
    return speeds

# Generate initial heatmap data
heatmap_data = generate_heatmap_data()

# Overlay heatmap with correct lat/lon extent
heatmap = ax.imshow(heatmap_data, cmap="coolwarm", alpha=0.5, 
                    extent=[min_lon, max_lon, min_lat, max_lat], 
                    interpolation='bilinear', vmin=0, vmax=600)

# Add colorbar
cbar = plt.colorbar(heatmap, ax=ax, label="WiFi Speed (Mbps)")

# Function to update the heatmap dynamically
def update(frame):
    """ Updates the heatmap visualization """
    heatmap.set_data(generate_heatmap_data())  # Update heatmap based on latest data
    return terrain_display, heatmap

# Animate heatmap
ani = animation.FuncAnimation(fig, update, interval=1000)

# Show plot
plt.show()

print("Live WiFi Heatmap Running with Movement & Floor Navigation...")
