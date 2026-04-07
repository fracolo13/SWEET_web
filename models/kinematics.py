"""Kinematics data models."""
from pydantic import BaseModel, Field
from typing import Literal, List, Optional


class KinematicsInput(BaseModel):
    """Input parameters for fault kinematics."""
    magnitude: float = Field(..., ge=4.0, le=9.0, description="Target magnitude")
    rake: float = Field(..., ge=-180, le=180, description="Rake angle in degrees")
    slip_dist: Literal["uniform", "random", "gaussian", "asperity"] = "gaussian"
    hypo_along: float = Field(..., ge=0, le=1, description="Hypocenter along-strike fraction")
    hypo_down: float = Field(..., ge=0, le=1, description="Hypocenter down-dip fraction")
    rupture_vel: float = Field(..., gt=0, description="Rupture velocity in km/s")
    rise_time: Optional[float] = Field(None, gt=0, description="Rise time in seconds")


class PatchKinematics(BaseModel):
    """Kinematics of a single patch."""
    x: float
    y: float
    z: float
    slip: float
    along_idx: int
    down_idx: int
    moment: float
    rupture_time: Optional[float] = None


class FaultKinematics(BaseModel):
    """Complete fault kinematics."""
    length: float
    width: float
    dip: float
    top_depth: float
    patch_size: float
    rake: float
    magnitude: float
    slip_dist: str
    hypo_along: float
    hypo_down: float
    rupture_vel: float
    n_along: int
    n_down: int
    patches: List[PatchKinematics]
    corners: List[dict]
    total_moment: float
    computed_mw: float
    average_slip: float
