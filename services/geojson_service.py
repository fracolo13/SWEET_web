"""GeoJSON processing service - load finite fault models."""
import json
import numpy as np
from typing import List, Tuple
from models.geojson import GeoJSONFaultModel, GeoJSONPatch
from physics.moment import moment_to_magnitude


def calculate_centroid(polygon: List[List[float]]) -> Tuple[float, float, float]:
    """
    Calculate centroid from polygon coordinates.
    
    Args:
        polygon: List of [lon, lat, depth] coordinates
        
    Returns:
        (lon, lat, depth) centroid
    """
    lons = [point[0] for point in polygon]
    lats = [point[1] for point in polygon]
    depths = [point[2] for point in polygon]
    
    centroid_lon = sum(lons) / len(polygon)
    centroid_lat = sum(lats) / len(polygon)
    centroid_depth = sum(depths) / len(polygon)
    
    return centroid_lon, centroid_lat, centroid_depth


def load_geojson_fault_model(geojson_content: dict) -> GeoJSONFaultModel:
    """
    Load fault model from GeoJSON content.
    
    Args:
        geojson_content: Parsed GeoJSON dictionary
        
    Returns:
        GeoJSONFaultModel with patches and statistics
    """
    patches = []
    
    # Extract features
    for feature in geojson_content.get('features', []):
        # Get polygon coordinates
        coords = feature['geometry']['coordinates'][0]
        
        # Get properties
        props = feature['properties']
        
        # Calculate centroid
        centroid_lon, centroid_lat, centroid_depth = calculate_centroid(coords)
        
        # Create patch
        patch = GeoJSONPatch(
            centroid_lon=centroid_lon,
            centroid_lat=centroid_lat,
            centroid_depth=centroid_depth,
            slip=props['slip'],
            trup=props['trup'],
            sf_moment=props['sf_moment'],
            rise=props['rise'],
            t_fal=props.get('t_fal', None)  # Optional field
        )
        
        patches.append(patch)
    
    # Calculate statistics
    total_slip = sum(p.slip for p in patches)
    total_moment = sum(p.sf_moment for p in patches)
    computed_mw = moment_to_magnitude(total_moment)
    
    return GeoJSONFaultModel(
        patches=patches,
        total_moment=total_moment,
        computed_mw=computed_mw,
        total_slip=total_slip,
        num_patches=len(patches)
    )


def group_geojson_patches(
    patches: List[GeoJSONPatch],
    target_magnitude: float,
    lat_ref: float = None
) -> dict:
    """
    Group GeoJSON patches using KDTree spatial clustering.
    
    Args:
        patches: List of GeoJSON patches
        target_magnitude: Target magnitude for each subsource
        lat_ref: Reference latitude for coordinate normalization
        
    Returns:
        Dictionary with grouped patches and statistics
    """
    from scipy.spatial import KDTree
    from physics.moment import magnitude_to_moment, moment_to_magnitude
    
    # Get target moment
    moment_threshold = magnitude_to_moment(target_magnitude)
    
    # Extract centroids and properties
    centroids = [(p.centroid_lon, p.centroid_lat, p.centroid_depth) for p in patches]
    slips = [p.slip for p in patches]
    trups = [p.trup for p in patches]
    rises = [p.rise for p in patches]
    sf_moments = [p.sf_moment for p in patches]
    t_fals = [p.t_fal if p.t_fal is not None else 0.0 for p in patches]
    
    # Use mean latitude if not provided
    if lat_ref is None:
        lat_ref = np.mean([c[1] for c in centroids])
    
    # Approximate conversion factor for longitude and latitude to meters
    lon_factor = np.cos(np.radians(lat_ref)) * 111000
    lat_factor = 111000  # 1 degree latitude ≈ 111 km
    
    # Normalize coordinates to meters
    normalized_centroids = [
        [lon * lon_factor, lat * lat_factor, depth]
        for lon, lat, depth in centroids
    ]
    
    # Build KDTree
    tree = KDTree(normalized_centroids)
    
    # Group patches
    grouped_patches = []
    groups = []
    visited = [False] * len(centroids)
    
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
        
        # Find neighbors within large radius
        neighbors = tree.query_ball_point(normalized_centroids[i], r=1e30)
        
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
        
        # Calculate grouped centroid
        centroid_lon = sum(centroids[k][0] for k in group) / count
        centroid_lat = sum(centroids[k][1] for k in group) / count
        centroid_depth = sum(centroids[k][2] for k in group) / count
        
        grouped_patch = {
            'centroid_lon': centroid_lon,
            'centroid_lat': centroid_lat,
            'centroid_depth': centroid_depth,
            'slip': total_slip,
            'trup': total_trup / count,
            'rise': total_rise / count,
            't_fal': total_tfal / count,
            'sf_moment': total_sf_moment,
            'magnitude': moment_to_magnitude(total_sf_moment),
            'original_indices': group
        }
        
        grouped_patches.append(grouped_patch)
        groups.append(group)
    
    return {
        'grouped_patches': grouped_patches,
        'num_groups': len(grouped_patches),
        'original_patches': len(patches),
        'magnitude_distribution': [p['magnitude'] for p in grouped_patches],
        'groups': groups
    }
