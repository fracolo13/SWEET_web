"""Slip distribution generation with physical constraints."""
import numpy as np
from typing import Tuple, Literal


def generate_slip_distribution(
    slip_type: Literal["uniform", "random", "gaussian", "asperity"],
    n_along: int,
    n_down: int,
    average_slip: float,
    hypo_i: int,
    hypo_j: int,
    rake: float
) -> np.ndarray:
    """
    Generate slip distribution with rake-dependent patterns.
    
    Args:
        slip_type: Type of slip distribution
        n_along: Number of patches along strike
        n_down: Number of patches down dip
        average_slip: Target average slip in meters
        hypo_i: Hypocenter along-strike index
        hypo_j: Hypocenter down-dip index
        rake: Rake angle in degrees
        
    Returns:
        2D array of slip values in meters
    """
    # Determine fault mechanism
    is_strike_slip = (-45 <= rake <= 45) or rake >= 135 or rake <= -135
    is_reverse = 45 < rake < 135
    is_normal = -135 < rake < -45
    
    max_slip = average_slip * 2.0  # Peak slip is ~2x average
    
    # Initialize slip array
    slips = np.zeros((n_along, n_down))
    
    for i in range(n_along):
        for j in range(n_down):
            di = (i - hypo_i) / n_along
            dj = (j - hypo_j) / n_down
            
            if slip_type == "uniform":
                # Uniform with small perturbations
                slips[i, j] = average_slip * (0.9 + np.random.random() * 0.2)
                
            elif slip_type == "random":
                # Random with rake-dependent envelope
                dist = _calc_rake_distance(di, dj, is_strike_slip, is_reverse, is_normal)
                envelope = np.exp(-dist / 0.4)
                slips[i, j] = max_slip * np.random.random() * (0.3 + 0.7 * envelope)
                
            elif slip_type == "gaussian":
                # Gaussian with rake-dependent distance
                dist = _calc_rake_distance(di, dj, is_strike_slip, is_reverse, is_normal)
                slips[i, j] = max_slip * np.exp(-dist / 0.25) * (0.8 + np.random.random() * 0.4)
                
            elif slip_type == "asperity":
                # Multiple asperities with rake-dependent positions
                asperities = _get_asperity_positions(is_strike_slip, is_reverse, is_normal)
                slip_vals = []
                for (asp_i, asp_j, strength) in asperities:
                    d = np.sqrt((di - asp_i)**2 + (dj - asp_j)**2)
                    slip_vals.append(max_slip * strength * np.exp(-d / 0.15))
                slips[i, j] = max(slip_vals) * (0.8 + np.random.random() * 0.4)
    
    # Normalize to maintain correct average slip
    slips = slips.flatten()
    slip_mean = np.mean(slips)
    slips = (slips / slip_mean) * average_slip
    
    return slips


def _calc_rake_distance(di: float, dj: float, is_strike_slip: bool, 
                        is_reverse: bool, is_normal: bool) -> float:
    """Calculate distance metric based on fault mechanism."""
    if is_strike_slip:
        # Strike-slip: rupture propagates along strike, limited down-dip
        return np.sqrt((di * 0.6)**2 + (dj * 1.8)**2)
    elif is_reverse:
        # Reverse/thrust: biased updip (negative dj)
        weight = 0.6 if dj < 0 else 2.0
        return np.sqrt((di * 1.0)**2 + (dj * weight)**2)
    elif is_normal:
        # Normal: biased downdip (positive dj)
        weight = 0.6 if dj > 0 else 2.0
        return np.sqrt((di * 1.0)**2 + (dj * weight)**2)
    else:
        return np.sqrt(di**2 + dj**2)


def _get_asperity_positions(is_strike_slip: bool, is_reverse: bool, 
                            is_normal: bool) -> list:
    """Get asperity positions based on fault mechanism."""
    if is_strike_slip:
        # Asperities spread along strike
        return [(-0.2, 0.0, 1.2), (0.1, 0.0, 0.8), (0.3, 0.0, 0.6)]
    elif is_reverse:
        # Asperities favor updip
        return [(0.0, -0.2, 1.2), (0.1, -0.1, 0.8), (-0.1, -0.15, 0.6)]
    elif is_normal:
        # Asperities favor downdip
        return [(0.0, 0.2, 1.2), (0.1, 0.15, 0.8), (-0.1, 0.1, 0.6)]
    else:
        # Generic distribution
        return [(-0.1, 0.0, 1.0), (0.1, 0.1, 0.8), (0.0, -0.1, 0.6)]
