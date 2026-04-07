import json
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from conversions import magnitude2moment, moment2magnitude, get_circular_uniform_slip_patch

base_path = '/Users/francescoacolosimo/Desktop/MSc_thesis/Data/Ridgecrest/'
with open(f'{base_path}/fault_csv/FFM.geojson') as f:
    data = json.load(f)

# Extract coordinates and properties from geojson
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

centroids = [calculate_centroid(polygon) for polygon in polygons]
slips = [prop['slip'] for prop in properties]
trups = [prop['trup'] for prop in properties]
rise = [prop['rise'] for prop in properties]
sf_moments = [prop['sf_moment'] for prop in properties]


fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

# Plot polygons with shades based on slip
for polygon, slip in zip(polygons, slips):
    poly = Poly3DCollection([polygon], alpha=0.5)
    poly.set_facecolor(plt.cm.viridis(slip / max(slips)))
    ax.add_collection3d(poly)

# Plot centroids 
centroids = np.array(centroids)
ax.scatter(centroids[:, 0], centroids[:, 1], centroids[:, 2], color='red')

ax.set_xlim([centroids[:, 0].min(), centroids[:, 0].max()])
ax.set_ylim([centroids[:, 1].min(), centroids[:, 1].max()])
ax.set_zlim([centroids[:, 2].min(), centroids[:, 2].max()])

ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
ax.set_zlabel('Depth')
plt.show()

import csv
from datetime import datetime
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
csv_filename = f'{base_path}/fault_csv/centroids_data.csv'
with open(csv_filename, 'w', newline='') as csvfile:
    fieldnames = ['centroid_lon', 'centroid_lat', 'centroid_depth', 'slip', 'trup', 'sf_moment', 'rise']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

    writer.writeheader()
    for centroid, slip, trup, rise, sf_moment in zip(centroids, slips, trups, rise, sf_moments):
        writer.writerow({
            'centroid_lon': centroid[0],
            'centroid_lat': centroid[1],
            'centroid_depth': centroid[2],
            'slip': slip,
            'trup': trup,
            'sf_moment': sf_moment,
            'rise': rise
        })


total_slip = sum(slips)
total_moment = sum(sf_moments)
magnitude_est = moment2magnitude(total_moment)
print(f'Total slip: {total_slip}')
print(f'Total moment: {total_moment}')
print(f'Magnitude estimated on moment: {magnitude_est}')