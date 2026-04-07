"""Rupture propagation calculations."""
import numpy as np
from typing import Tuple


def calculate_rupture_times(
    patches: list,
    hypo_along: float,
    hypo_down: float,
    rupture_vel: float,
    n_along: int,
    n_down: int,
    length: float,
    width: float
) -> np.ndarray:
    """
    Calculate rupture time for each patch based on distance from hypocenter.
    
    Args:
        patches: List of patch dictionaries with x, y, z coordinates
        hypo_along: Hypocenter position along strike (0-1)
        hypo_down: Hypocenter position down dip (0-1)
        rupture_vel: Rupture velocity in km/s
        n_along: Number of patches along strike
        n_down: Number of patches down dip
        length: Fault length in km
        width: Fault width in km
        
    Returns:
        Array of rupture times in seconds
    """
    # Hypocenter location in patch indices
    hypo_i = hypo_along * n_along
    hypo_j = hypo_down * n_down
    
    # Patch dimensions
    patch_length = length / n_along
    patch_width = width / n_down
    
    rupture_times = []
    
    for patch in patches:
        i = patch['along_idx']
        j = patch['down_idx']
        
        # Distance from hypocenter in patch units
        di = i - hypo_i
        dj = j - hypo_j
        
        # Convert to km
        dist_km = np.sqrt((di * patch_length)**2 + (dj * patch_width)**2)
        
        # Rupture time (seconds)
        rupture_time = dist_km / rupture_vel
        rupture_times.append(rupture_time)
    
    return np.array(rupture_times)


def generate_source_time_function(
    patches: list,
    time_step: float = 0.01,
    duration_factor: float = 0.5
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate source time function from all patches.
    
    Args:
        patches: List of patch dictionaries with moment and rupture_time
        time_step: Time step in seconds
        duration_factor: Rise time as fraction of patch dimension / rupture velocity
        
    Returns:
        (times, moment_rate) arrays
    """
    # Find time range
    max_time = max(p.get('rupture_time', 0) for p in patches)
    # Add extra time for rise/fall
    max_time += duration_factor * 2
    
    times = np.arange(0, max_time, time_step)
    moment_rate = np.zeros_like(times)
    
    # Add triangular STF for each patch
    for patch in patches:
        moment = patch['moment']
        t0 = patch.get('rupture_time', 0)
        duration = duration_factor
        
        # Triangular function: peak at t0 + duration/2
        peak_value = (2 * moment) / duration
        
        for idx, t in enumerate(times):
            if t0 <= t < t0 + duration / 2:
                # Rising edge
                moment_rate[idx] += peak_value * (t - t0) / (duration / 2)
            elif t0 + duration / 2 <= t < t0 + duration:
                # Falling edge
                moment_rate[idx] += peak_value * (t0 + duration - t) / (duration / 2)
    
    return times, moment_rate
