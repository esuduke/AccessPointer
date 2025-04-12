import cv2
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from scipy.interpolate import griddata

def generate_wifi_data(width, height, num_points=50):
    """Generate random WiFi speed measurements"""
    points = np.column_stack((
        np.random.randint(0, width, num_points),
        np.random.randint(0, height, num_points)
    ))
    speeds = np.random.uniform(10, 100, num_points)  # Random speeds between 10-100 Mbps
    return points, speeds

# Load and prepare floor plan
floor_img = cv2.imread('Floor1.png')
floor_img = cv2.cvtColor(floor_img, cv2.COLOR_BGR2RGB)

# Generate measurement data
measurement_points, wifi_speeds = generate_wifi_data(floor_img.shape[1], floor_img.shape[0], 100)

# Create interpolation grid
grid_x, grid_y = np.mgrid[0:floor_img.shape[1]:1, 0:floor_img.shape[0]:1]
grid = griddata(measurement_points, wifi_speeds, (grid_x, grid_y), method='cubic', fill_value=0)

# Smooth the heatmap
grid = cv2.GaussianBlur(grid, (51, 51), 0)

# Create plot
plt.figure(figsize=(12, 10))
plt.imshow(floor_img)

# Add heatmap overlay
heatmap = plt.imshow(grid.T, cmap='coolwarm', alpha=0.6,
                    extent=[0, floor_img.shape[1], floor_img.shape[0], 0])

# Add colorbar
cbar = plt.colorbar(heatmap)
cbar.set_label('WiFi Speed (Mbps)')

# Add measurement points
# plt.scatter(measurement_points[:, 0], measurement_points[:, 1],
#            c=wifi_speeds, cmap='RdYlGn', edgecolor='black',
#            s=50, label='Speed Measurements')

plt.title('WiFi Speed Distribution')
plt.legend()
plt.axis('off')
plt.tight_layout()
plt.show()
