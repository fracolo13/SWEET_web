"""Station data models."""
from pydantic import BaseModel, Field
from typing import List, Optional


class Station(BaseModel):
    """Seismic station."""
    id: str
    name: str
    latitude: float
    longitude: float
    elevation: Optional[float] = 0.0


class StationInput(BaseModel):
    """Input for station configuration."""
    stations: List[Station]


class StationGrid(BaseModel):
    """Grid-based station configuration."""
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    spacing: float = Field(..., gt=0, description="Station spacing in km")
