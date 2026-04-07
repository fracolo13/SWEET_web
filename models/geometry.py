"""Geometry data models."""
from pydantic import BaseModel, Field
from typing import Literal, List, Optional


class GeometryInput(BaseModel):
    """Input parameters for fault geometry."""
    mode: Literal["plane", "listric"] = "plane"
    length: float = Field(..., gt=0, description="Fault length in km")
    width: float = Field(..., gt=0, description="Fault width in km")
    dip: float = Field(..., ge=0, le=90, description="Fault dip in degrees")
    top_depth: float = Field(..., ge=0, description="Top depth in km")
    patch_size: float = Field(..., gt=0, description="Patch size in km")
    strike: float = Field(default=0, ge=0, lt=360, description="Strike in degrees")


class PatchGeometry(BaseModel):
    """Geometry of a single patch."""
    x: float
    y: float
    z: float
    along_idx: int
    down_idx: int


class FaultGeometry(BaseModel):
    """Complete fault geometry."""
    length: float
    width: float
    dip: float
    top_depth: float
    patch_size: float
    strike: float
    n_along: int
    n_down: int
    patches: List[PatchGeometry]
    corners: List[dict]  # [{x, y, z}, ...]
