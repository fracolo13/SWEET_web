"""
Helper functions for synthetic waveform summation.
"""
import os
import numpy as np
from typing import Optional, Dict, List, Tuple

# Check if S3 mode is enabled
USE_S3_TEMPLATES = os.getenv('USE_S3_TEMPLATES', 'false').lower() == 'true'

if USE_S3_TEMPLATES:
    try:
        from s3_helpers import get_s3_loader, load_template_from_s3
        S3_AVAILABLE = True
        print("[INFO] S3 template loading enabled")
    except ImportError as e:
        S3_AVAILABLE = False
        USE_S3_TEMPLATES = False
        print(f"[WARNING] S3 mode requested but import failed: {e}. Falling back to local.")


def moment2magnitude(moment: float) -> float:
    """
    Convert seismic moment (N·m) to moment magnitude.
    
    Args:
        moment: Seismic moment in N·m
        
    Returns:
        Moment magnitude Mw
    """
    if moment <= 0:
        return 0.0
    return (2.0 / 3.0) * (np.log10(moment) - 9.1)


def magnitude2moment(magnitude: float) -> float:
    """
    Convert moment magnitude to seismic moment (N·m).
    
    Args:
        magnitude: Moment magnitude Mw
        
    Returns:
        Seismic moment in N·m
    """
    return 10 ** (1.5 * magnitude + 9.1)


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Calculate great circle distance between two points on Earth.
    
    Args:
        lon1, lat1: First point coordinates (degrees)
        lon2, lat2: Second point coordinates (degrees)
        
    Returns:
        Distance in kilometers
    """
    # Convert to radians
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    
    # Earth radius in km
    r = 6371.0
    
    return c * r


def find_closest_magnitude(available_mags: List[float], target_mag: float) -> float:
    """
    Find closest available magnitude to target.
    
    Args:
        available_mags: List of available magnitudes
        target_mag: Target magnitude
        
    Returns:
        Closest available magnitude
    """
    if not available_mags:
        raise ValueError("No available magnitudes")
    
    return min(available_mags, key=lambda x: abs(x - target_mag))


def find_closest_vs30(available_vs30: List[float], target_vs30: float) -> float:
    """
    Find closest available VS30 value.
    
    Args:
        available_vs30: List of available VS30 values
        target_vs30: Target VS30
        
    Returns:
        Closest available VS30
    """
    if not available_vs30:
        raise ValueError("No available VS30 values")
    
    return min(available_vs30, key=lambda x: abs(x - target_vs30))


def get_available_templates_info(templates_dir: str) -> Dict[str, List]:
    """
    Scan preprocessed templates directory and return available parameters.
    Supports both local filesystem and S3 storage.
    
    Args:
        templates_dir: Path to preprocessed templates directory (or 'S3' for S3 mode)
        
    Returns:
        Dictionary with 'magnitudes', 'vs30', and 'distances' lists
    """
    # Use S3 if enabled
    if USE_S3_TEMPLATES and S3_AVAILABLE:
        try:
            loader = get_s3_loader()
            return loader.get_available_templates_info()
        except Exception as e:
            print(f"[ERROR] Failed to get S3 template info: {e}")
            raise
    
    # Local filesystem
    info = {
        'magnitudes': [],
        'vs30': [],
        'distances': []
    }
    
    if not os.path.isdir(templates_dir):
        return info
    
    vs30_set = set()
    mag_set = set()
    dist_set = set()
    
    # Scan directory structure: vs30_XXX/MX.X/XXXkm/
    for vs30_dir in os.listdir(templates_dir):
        if not vs30_dir.startswith('vs30_'):
            continue
            
        vs30_path = os.path.join(templates_dir, vs30_dir)
        if not os.path.isdir(vs30_path):
            continue
            
        # Extract VS30 value
        try:
            vs30_val = int(vs30_dir.split('_')[1])
            vs30_set.add(vs30_val)
        except (IndexError, ValueError):
            continue
        
        # Scan magnitude directories
        for mag_dir in os.listdir(vs30_path):
            if not mag_dir.startswith('M'):
                continue
                
            mag_path = os.path.join(vs30_path, mag_dir)
            if not os.path.isdir(mag_path):
                continue
            
            # Extract magnitude value
            try:
                mag_val = float(mag_dir[1:])
                mag_set.add(mag_val)
            except ValueError:
                continue
            
            # Scan distance directories
            for dist_dir in os.listdir(mag_path):
                if not dist_dir.endswith('km'):
                    continue
                    
                dist_path = os.path.join(mag_path, dist_dir)
                if not os.path.isdir(dist_path):
                    continue
                
                # Extract distance value
                try:
                    dist_val = int(dist_dir[:-2])
                    dist_set.add(dist_val)
                except ValueError:
                    continue
    
    info['magnitudes'] = sorted(list(mag_set))
    info['vs30'] = sorted(list(vs30_set))
    info['distances'] = sorted(list(dist_set))
    
    return info


def load_template(
    templates_dir: str,
    vs30: float,
    magnitude: float,
    distance_km: float,
    realization_idx: int
) -> Optional[np.ndarray]:
    """
    Load a preprocessed template envelope.
    Supports both local filesystem and S3 storage.
    
    Args:
        templates_dir: Path to preprocessed templates directory (or 'S3' for S3 mode)
        vs30: VS30 value
        magnitude: Magnitude
        distance_km: Source-to-station distance in km
        realization_idx: Realization index (0-based)
        
    Returns:
        Template array of shape (3, n_samples) [E, N, Z] or None if not found
    """
    # Construct path components
    vs30_dir = f'vs30_{int(vs30)}'
    mag_dir = f'M{magnitude:.1f}'
    dist_dir = f'{int(distance_km):03d}km'
    template_file = f'template_{realization_idx:02d}.npy'
    
    # Use S3 if enabled
    if USE_S3_TEMPLATES and S3_AVAILABLE:
        try:
            print(f'[DEBUG] Loading from S3: {vs30_dir}/{mag_dir}/{dist_dir}/{template_file}')
            template = load_template_from_s3(vs30_dir, mag_dir, dist_dir, template_file)
            print(f'[DEBUG] Loaded template shape: {template.shape}')
            return template
        except FileNotFoundError as e:
            print(f'[WARNING] Template not found in S3: {vs30_dir}/{mag_dir}/{dist_dir}/{template_file}')
            return None
        except Exception as e:
            print(f'[ERROR] Failed to load template from S3: {e}')
            import traceback
            traceback.print_exc()
            return None
    
    # Local filesystem
    template_path = os.path.join(
        templates_dir, vs30_dir, mag_dir, dist_dir, template_file
    )
    
    if not os.path.isfile(template_path):
        return None
    
    try:
        template = np.load(template_path)
        return template
    except Exception as e:
        print(f'[WARNING] Failed to load template {template_path}: {e}')
        return None


def find_closest_distance(available_dists: List[float], target_dist: float) -> float:
    """
    Find closest available distance bin.
    
    Args:
        available_dists: List of available distances
        target_dist: Target distance
        
    Returns:
        Closest available distance
    """
    if not available_dists:
        raise ValueError("No available distances")
    
    return min(available_dists, key=lambda x: abs(x - target_dist))
