"""GeoJSON data models for importing finite fault models."""
from pydantic import BaseModel, Field
from typing import List, Optional


class GeoJSONPatchProperties(BaseModel):
    """Properties extracted from GeoJSON feature."""
    slip: float = Field(..., description="Slip in meters")
    trup: float = Field(..., description="Rupture time in seconds")
    sf_moment: float = Field(..., description="Seismic moment in N·m")
    rise: float = Field(..., description="Rise time in seconds")
    t_fal: Optional[float] = Field(None, description="Fall time in seconds")


class GeoJSONPatch(BaseModel):
    """Single patch from GeoJSON with coordinates and properties."""
    centroid_lon: float
    centroid_lat: float
    centroid_depth: float
    slip: float
    trup: float
    sf_moment: float
    rise: float
    t_fal: Optional[float] = None


class GeoJSONFaultModel(BaseModel):
    """Complete fault model loaded from GeoJSON."""
    patches: List[GeoJSONPatch]
    total_moment: float
    computed_mw: float
    total_slip: float
    num_patches: int
