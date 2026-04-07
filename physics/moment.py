"""Seismic moment calculations."""
import numpy as np


def magnitude_to_moment(magnitude: float) -> float:
    """
    Convert moment magnitude to seismic moment.
    
    Args:
        magnitude: Moment magnitude (Mw)
        
    Returns:
        Seismic moment in N·m
        
    Formula: M0 = 10^(1.5 × (Mw + 6.07))
    """
    return 10 ** (1.5 * (magnitude + 6.07))


def moment_to_magnitude(moment: float) -> float:
    """
    Convert seismic moment to moment magnitude.
    
    Args:
        moment: Seismic moment in N·m
        
    Returns:
        Moment magnitude (Mw)
        
    Formula: Mw = (2/3) × log10(M0) - 6.07
    """
    return (2/3) * np.log10(moment) - 6.07


def calculate_patch_moment(slip: float, area_m2: float, mu: float = 3e10) -> float:
    """
    Calculate seismic moment for a patch.
    
    Args:
        slip: Slip in meters
        area_m2: Patch area in m²
        mu: Shear modulus in Pa (default: 3×10^10 Pa = 30 GPa)
        
    Returns:
        Seismic moment in N·m
        
    Formula: M0 = μ × A × D
    """
    return mu * area_m2 * slip


def calculate_total_moment(slips: np.ndarray, patch_area_m2: float, mu: float = 3e10) -> float:
    """
    Calculate total seismic moment from all patches.
    
    Args:
        slips: Array of slip values in meters
        patch_area_m2: Area of each patch in m²
        mu: Shear modulus in Pa
        
    Returns:
        Total seismic moment in N·m
    """
    return mu * patch_area_m2 * np.sum(slips)


def average_slip_from_moment(moment: float, area_m2: float, mu: float = 3e10) -> float:
    """
    Calculate average slip from seismic moment.
    
    Args:
        moment: Seismic moment in N·m
        area_m2: Fault area in m²
        mu: Shear modulus in Pa
        
    Returns:
        Average slip in meters
        
    Formula: D_avg = M0 / (μ × A)
    """
    return moment / (mu * area_m2)
