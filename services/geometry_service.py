"""Geometry service - fault discretization and patch generation."""
import numpy as np
from typing import List, Dict
from models.geometry import GeometryInput, FaultGeometry, PatchGeometry


def generate_fault_geometry(params: GeometryInput) -> FaultGeometry:
    """
    Generate fault geometry with discretized patches.
    
    Args:
        params: Geometry input parameters
        
    Returns:
        Complete fault geometry with patches
    """
    # Calculate number of patches
    n_along = int(np.ceil(params.length / params.patch_size))
    n_down = int(np.ceil(params.width / params.patch_size))
    
    # Convert angles to radians
    strike_rad = np.deg2rad(params.strike)
    dip_rad = np.deg2rad(params.dip)
    perp_rad = strike_rad + np.pi / 2
    
    # Generate patch centers
    patches = []
    for i in range(n_along):
        for j in range(n_down):
            # Position along strike and down dip
            along_dist = (i + 0.5) * (params.length / n_along)
            down_dist = (j + 0.5) * (params.width / n_down)
            
            # 3D coordinates
            x = (along_dist * np.cos(strike_rad) + 
                 down_dist * np.cos(perp_rad) * np.cos(dip_rad))
            y = (along_dist * np.sin(strike_rad) + 
                 down_dist * np.sin(perp_rad) * np.cos(dip_rad))
            z = params.top_depth + down_dist * np.sin(dip_rad)
            
            patches.append(PatchGeometry(
                x=float(x),
                y=float(y),
                z=float(z),
                along_idx=i,
                down_idx=j
            ))
    
    # Generate fault corners for visualization
    corners = _generate_fault_corners(
        params.length, params.width, params.top_depth,
        strike_rad, dip_rad, perp_rad
    )
    
    return FaultGeometry(
        length=params.length,
        width=params.width,
        dip=params.dip,
        top_depth=params.top_depth,
        patch_size=params.patch_size,
        strike=params.strike,
        n_along=n_along,
        n_down=n_down,
        patches=patches,
        corners=corners
    )


def _generate_fault_corners(
    length: float,
    width: float,
    top_depth: float,
    strike_rad: float,
    dip_rad: float,
    perp_rad: float
) -> List[Dict[str, float]]:
    """Generate 4 corners of the fault plane for visualization."""
    corners = [
        # Top-left (origin)
        {"x": 0.0, "y": 0.0, "z": top_depth},
        
        # Top-right (along strike)
        {
            "x": float(length * np.cos(strike_rad)),
            "y": float(length * np.sin(strike_rad)),
            "z": top_depth
        },
        
        # Bottom-right (along strike + down dip)
        {
            "x": float(length * np.cos(strike_rad) + 
                      width * np.cos(perp_rad) * np.cos(dip_rad)),
            "y": float(length * np.sin(strike_rad) + 
                      width * np.sin(perp_rad) * np.cos(dip_rad)),
            "z": float(top_depth + width * np.sin(dip_rad))
        },
        
        # Bottom-left (down dip only)
        {
            "x": float(width * np.cos(perp_rad) * np.cos(dip_rad)),
            "y": float(width * np.sin(perp_rad) * np.cos(dip_rad)),
            "z": float(top_depth + width * np.sin(dip_rad))
        }
    ]
    
    return corners


def get_patch_area_m2(length_km: float, width_km: float, n_along: int, n_down: int) -> float:
    """Calculate patch area in m²."""
    patch_length_km = length_km / n_along
    patch_width_km = width_km / n_down
    return patch_length_km * patch_width_km * 1e6  # Convert km² to m²
