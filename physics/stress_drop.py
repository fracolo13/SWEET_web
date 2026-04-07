"""Stress drop calculations and constraints."""
import numpy as np


def max_patch_moment(area_m2: float, delta_sigma_max: float) -> float:
    """
    Calculate maximum seismic moment for a patch based on stress-drop limit.
    
    Args:
        area_m2: Patch area in m²
        delta_sigma_max: Maximum stress drop in Pa
        
    Returns:
        Maximum seismic moment in N·m
        
    Formula: M0_max = (16/7) × (Δσ_max / √π) × A^1.5
    """
    return (16.0 / 7.0) * (delta_sigma_max / np.sqrt(np.pi)) * (area_m2 ** 1.5)


def get_stress_drop_limit(rake: float) -> float:
    """
    Get stress drop limit based on fault mechanism.
    
    Args:
        rake: Rake angle in degrees
        
    Returns:
        Stress drop limit in Pa
        
    Limits:
        - Reverse/thrust (45° < rake < 135°): 4 MPa = 4×10^6 Pa
        - Normal/strike-slip: 3 MPa = 3×10^6 Pa
    """
    # Determine fault type from rake
    is_reverse = 45 < rake < 135
    
    # Return appropriate stress drop limit (in Pa)
    return 4e6 if is_reverse else 3e6


def apply_stress_drop_limit(
    slips: np.ndarray,
    patch_area_m2: float,
    rake: float,
    average_slip: float,
    mu: float = 3e10
) -> np.ndarray:
    """
    Apply stress-drop limit to slip distribution.
    
    Args:
        slips: Array of slip values in meters
        patch_area_m2: Patch area in m²
        rake: Rake angle in degrees
        average_slip: Target average slip in meters
        mu: Shear modulus in Pa
        
    Returns:
        Array of slip values capped by stress-drop limit
    """
    # Get stress drop limit
    delta_sigma_max = get_stress_drop_limit(rake)
    
    # Calculate maximum allowed moment and slip
    max_moment = max_patch_moment(patch_area_m2, delta_sigma_max)
    max_slip_allowed = max_moment / (mu * patch_area_m2)
    
    # Cap slip values
    num_capped = np.sum(slips > max_slip_allowed)
    slips_capped = np.minimum(slips, max_slip_allowed)
    
    # If patches were capped, redistribute to maintain total moment
    if num_capped > 0:
        current_mean = np.mean(slips_capped)
        deficit = average_slip - current_mean
        
        if deficit > 0:
            # Identify uncapped patches
            uncapped_mask = slips_capped < max_slip_allowed
            num_uncapped = np.sum(uncapped_mask)
            
            if num_uncapped > 0:
                # Distribute deficit proportionally
                boost = deficit * (len(slips) / num_uncapped)
                slips_capped[uncapped_mask] = np.minimum(
                    slips_capped[uncapped_mask] + boost,
                    max_slip_allowed
                )
    
    return slips_capped


def calculate_stress_drop(moment: float, area_m2: float) -> float:
    """
    Calculate average stress drop from moment and area.
    
    Args:
        moment: Seismic moment in N·m
        area_m2: Fault area in m²
        
    Returns:
        Stress drop in Pa
        
    Formula: Δσ = (7/16) × M0 × (π/A)^1.5
    """
    return (7.0 / 16.0) * moment * (np.pi / area_m2) ** 1.5
