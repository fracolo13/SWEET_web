"""Kinematics service - slip distribution with physical constraints."""
import numpy as np
from typing import List
from models.geometry import FaultGeometry
from models.kinematics import KinematicsInput, FaultKinematics, PatchKinematics
from physics.moment import (
    magnitude_to_moment, 
    moment_to_magnitude,
    average_slip_from_moment,
    calculate_patch_moment
)
from physics.slip import generate_slip_distribution
from physics.stress_drop import apply_stress_drop_limit
from physics.rupture import calculate_rupture_times
from services.geometry_service import get_patch_area_m2


MU = 3e10  # Shear modulus in Pa (30 GPa)


def generate_fault_kinematics(
    geometry: FaultGeometry,
    params: KinematicsInput
) -> FaultKinematics:
    """
    Generate fault kinematics with physically constrained slip distribution.
    
    Args:
        geometry: Fault geometry
        params: Kinematics input parameters
        
    Returns:
        Complete fault kinematics with slip, moment, and rupture times
    """
    # Calculate target moment and average slip
    target_moment = magnitude_to_moment(params.magnitude)
    area_m2 = geometry.length * geometry.width * 1e6  # km² to m²
    average_slip = average_slip_from_moment(target_moment, area_m2, MU)
    
    # Hypocenter indices
    hypo_i = int(params.hypo_along * geometry.n_along)
    hypo_j = int(params.hypo_down * geometry.n_down)
    
    # Generate initial slip distribution
    slips = generate_slip_distribution(
        slip_type=params.slip_dist,
        n_along=geometry.n_along,
        n_down=geometry.n_down,
        average_slip=average_slip,
        hypo_i=hypo_i,
        hypo_j=hypo_j,
        rake=params.rake
    )
    
    # Apply stress-drop constraints
    patch_area_m2 = get_patch_area_m2(
        geometry.length, 
        geometry.width, 
        geometry.n_along, 
        geometry.n_down
    )
    
    slips = apply_stress_drop_limit(
        slips=slips,
        patch_area_m2=patch_area_m2,
        rake=params.rake,
        average_slip=average_slip,
        mu=MU
    )
    
    # Create patch kinematics
    patches = []
    total_moment = 0.0
    
    for idx, geom_patch in enumerate(geometry.patches):
        slip = float(slips[idx])
        moment = calculate_patch_moment(slip, patch_area_m2, MU)
        total_moment += moment
        
        patches.append(PatchKinematics(
            x=geom_patch.x,
            y=geom_patch.y,
            z=geom_patch.z,
            slip=slip,
            along_idx=geom_patch.along_idx,
            down_idx=geom_patch.down_idx,
            moment=moment
        ))
    
    # Calculate rupture times
    rupture_times = calculate_rupture_times(
        patches=[{
            'along_idx': p.along_idx,
            'down_idx': p.down_idx,
            'x': p.x, 'y': p.y, 'z': p.z
        } for p in patches],
        hypo_along=params.hypo_along,
        hypo_down=params.hypo_down,
        rupture_vel=params.rupture_vel,
        n_along=geometry.n_along,
        n_down=geometry.n_down,
        length=geometry.length,
        width=geometry.width
    )
    
    # Add rupture times to patches
    for i, patch in enumerate(patches):
        patch.rupture_time = float(rupture_times[i])
    
    # Calculate final statistics
    computed_mw = moment_to_magnitude(total_moment)
    avg_slip = float(np.mean(slips))
    
    return FaultKinematics(
        length=geometry.length,
        width=geometry.width,
        dip=geometry.dip,
        top_depth=geometry.top_depth,
        patch_size=geometry.patch_size,
        rake=params.rake,
        magnitude=params.magnitude,
        slip_dist=params.slip_dist,
        hypo_along=params.hypo_along,
        hypo_down=params.hypo_down,
        rupture_vel=params.rupture_vel,
        n_along=geometry.n_along,
        n_down=geometry.n_down,
        patches=patches,
        corners=geometry.corners,
        total_moment=total_moment,
        computed_mw=computed_mw,
        average_slip=avg_slip
    )
