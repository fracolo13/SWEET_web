import json
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import csv
from scipy.spatial import KDTree
from conversions import magnitude2moment, moment2magnitude, get_circular_uniform_slip_patch
import os
mag = 6
eq = 'Kumamoto'
base_path = f'/Users/francescoacolosimo/Desktop/MSc_thesis/Data/{eq}'

# Create directory if it doesn't exist
output_dir = f'/Users/francescoacolosimo/Desktop/MSc_thesis/Data/{eq}_{mag}'
os.makedirs(output_dir, exist_ok=True)
# Create additional directories if they don't exist
os.makedirs(f'{output_dir}/fault_csv', exist_ok=True)
os.makedirs(f'{output_dir}/station_csv', exist_ok=True)
os.makedirs(f'{output_dir}/generative', exist_ok=True)
os.makedirs(f'{output_dir}/generative/generative_tables', exist_ok=True)

# Load the GeoJSON file
with open(f'{base_path}/fault_csv/FFM.geojson') as f:
    data = json.load(f)

# Extract coordinates and properties
polygons = []
properties = []
for feature in data['features']:
    coords = feature['geometry']['coordinates'][0]
    props = feature['properties']
    polygons.append(coords)
    properties.append(props)

def calculate_centroid(polygon):
    lat = [point[1] for point in polygon]
    lon = [point[0] for point in polygon]
    depth = [point[2] for point in polygon]
    centroid = [sum(lon) / len(polygon), sum(lat) / len(polygon), sum(depth) / len(polygon)]
    return centroid

original_centroids = [calculate_centroid(polygon) for polygon in polygons]
slips = [prop['slip'] for prop in properties]
trups = [prop['trup'] for prop in properties]
sf_moments = [prop['sf_moment'] for prop in properties]
rises = [prop['rise'] for prop in properties]
# Handle missing 't_fal' key by providing a default value (e.g., 0 or None)

# File path to the parameter file
param_file = "/Users/francescoacolosimo/Desktop/MSc_thesis/Data/Kumamoto/basic_inversion.param"

# Initialize lists to store extracted data
lat_lon_depth_slip = []
t_fals = []

# Read the parameter file
with open(param_file, "r") as file:
    for line in file:
        # Skip lines that are comments or empty
        if line.startswith("#") or not line.strip():
            continue
        
        # Split the line into columns
        columns = line.split()
        
        # Check if the line contains the required number of columns
        if len(columns) >= 10:  # Ensure the line has at least 10 columns
            try:
                # Extract relevant values
                lat = float(columns[0])
                lon = float(columns[1])
                depth = float(columns[2])
                slip = float(columns[3])
                t_fal = float(columns[9])  # Extract the 10th column (t_fal)
                
                # Append to lists
                lat_lon_depth_slip.append((lat, lon, depth, slip))
                t_fals.append(t_fal)
            except ValueError:
                # Skip lines with invalid data
                continue



def group_centroids(centroids, slips, trups, rises, t_fals, sf_moments, moment_threshold, lat_ref):
    grouped_centroids = []
    grouped_slips = []
    grouped_trups = []
    grouped_rise = []
    grouped_t_fal = []
    grouped_sf_moments = []
    groups = []
    visited = [False] * len(centroids)

    # Approximate conversion factor for longitude and latitude to meters
    lon_factor = np.cos(np.radians(lat_ref)) * 111000
    lat_factor = 111000  # 1 degree latitude ≈ 111 km
    #depth_factor = 111000  # Convert depth meters to degree scale

    # Normalize coordinates to meters (here can introduce bias towards linking vertically or horizontally)
    normalized_centroids = [
        [lon * lon_factor, lat * lat_factor, depth] 
        for lon, lat, depth in centroids
    ]
    
    tree = KDTree(normalized_centroids)

    for i in range(len(centroids)):
        if visited[i]:
            continue
        group = [i]
        total_slip = slips[i]
        total_sf_moment = sf_moments[i]
        total_trup = trups[i]
        total_rise = rises[i]
        total_tfal = t_fals[i] 
        count = 1
        visited[i] = True

        neighbors = tree.query_ball_point(normalized_centroids[i], r=1e30)  # Adjust the radius based on the scale of cells

        for j in neighbors:
            if visited[j]:
                continue
            if total_sf_moment < moment_threshold:
                group.append(j)
                total_slip += slips[j]
                total_sf_moment += sf_moments[j]
                total_trup += trups[j]
                total_rise += rises[j]
                total_tfal += t_fals[j]
                count += 1
                visited[j] = True

        centroid_lon = sum(centroids[k][0] for k in group) / count
        centroid_lat = sum(centroids[k][1] for k in group) / count
        centroid_depth = sum(centroids[k][2] for k in group) / count
        grouped_centroids.append([centroid_lon, centroid_lat, centroid_depth])
        grouped_slips.append(total_slip)
        grouped_trups.append(total_trup / count)
        grouped_rise.append(total_rise / count)
        grouped_t_fal.append(total_tfal / count)  
        grouped_sf_moments.append(total_sf_moment)
        groups.append(group)

    return grouped_centroids, grouped_slips, grouped_trups, grouped_rise,grouped_t_fal, grouped_sf_moments, groups

# Define the moment threshold 
moment_threshold = magnitude2moment(mag)
# moment_threshold =  2.2382057133190464e+17
lat_ref = np.mean([centroid[1] for centroid in original_centroids])  

# Group centroids
grouped_centroids, grouped_slips, grouped_trups, grouped_rise, grouped_t_fal, grouped_sf_moments, groups = group_centroids(original_centroids, slips, trups, rises, t_fals, sf_moments, moment_threshold, lat_ref)

# Save grouped centroids to a CSV file
with open(f'{output_dir}/fault_csv/grouped_centroids_data_{eq}_{mag}.csv', 'w', newline='') as csvfile:
    fieldnames = ['centroid_lon', 'centroid_lat', 'centroid_depth', 'slip', 'trup', 'rise','t_fal', 'sf_moment']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for centroid, slip, trup, rise,t_fal, sf_moment in zip(grouped_centroids, grouped_slips, grouped_trups, grouped_rise, grouped_t_fal, grouped_sf_moments):
        writer.writerow({
            'centroid_lon': centroid[0],
            'centroid_lat': centroid[1],
            'centroid_depth': centroid[2],
            'slip': slip,
            'trup': trup,
            'rise': rise,  # Corrected key to match fieldnames
            't_fal': t_fal,
            'sf_moment': sf_moment
        })


# Plot the grouped centroids in 3D
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

colors = plt.cm.viridis(np.linspace(0, 1, len(groups)))

# Plot the original centroids and link them with lines
for group, color in zip(groups, colors):
    group_centroids = np.array([original_centroids[i] for i in group])
    ax.scatter(group_centroids[:, 0], group_centroids[:, 1], group_centroids[:, 2], color=color, marker='o')
    
    # Draw lines between the centroids in the group
    for i in range(len(group_centroids) - 1):
        for j in range(i + 1, len(group_centroids)):
            line = np.array([group_centroids[i], group_centroids[j]])
            ax.plot(line[:, 0], line[:, 1], line[:, 2], color=color, alpha=0.5)

# Plot the new centroids in red
grouped_centroids = np.array(grouped_centroids)  # Convert to numpy array for easier indexing
ax.scatter(grouped_centroids[:, 0], grouped_centroids[:, 1], grouped_centroids[:, 2], color='red', marker='o', label='New Centroids')

# Create a surface plot, plotting the slip values
faces = []
for i in range(len(grouped_centroids) - 1):
    for j in range(i + 1, len(grouped_centroids)):
        faces.append([grouped_centroids[i], grouped_centroids[j]])

poly = Poly3DCollection(faces, alpha=0.5)
poly.set_facecolor(plt.cm.viridis(np.array(grouped_slips) / max(grouped_slips)))
ax.add_collection3d(poly)

# Set axis labels and title
ax.set_box_aspect([1, 1, 0.3])
ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
ax.set_zlabel('Depth')
plt.title('Grouped Centroids with Slip Surface')

# Add a legend
ax.legend(loc='upper left', bbox_to_anchor=(1.05, 1), title="Legend")

plt.show()
