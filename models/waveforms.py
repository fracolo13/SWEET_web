"""Waveform summation data models."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class StationData(BaseModel):
    """Station data for waveform summation."""
    station_code: Optional[str] = None
    name: Optional[str] = None
    id: Optional[str] = None
    latitude: float
    longitude: float
    vs30: Optional[float] = 500.0
    network: Optional[str] = "XX"
    station: Optional[str] = None


class SubsourceData(BaseModel):
    """Subsource data for waveform summation."""
    centroid_lon: float
    centroid_lat: float
    centroid_depth: float
    sf_moment: float
    trup: float
    magnitude: Optional[float] = None


class WaveformSummationInput(BaseModel):
    """Input parameters for waveform summation."""
    subsources: List[Dict[str, Any]]  # Flexible to accept various formats
    stations: List[Dict[str, Any]]  # Flexible to accept various formats
    templates_dir: str = Field(..., description="Path to preprocessed templates directory")
    n_realizations: int = Field(1, ge=1, le=100, description="Number of realizations")
    sampling_rate: float = Field(100.0, gt=0, description="Sampling rate in Hz")
    moment_scale: bool = Field(False, description="Apply moment ratio scaling")
    amplitude_scale: float = Field(1.0, gt=0, description="Global amplitude scaling factor")
    min_template_dist_km: float = Field(10.0, ge=0, description="Minimum template distance")


class WaveformSummationResult(BaseModel):
    """Result of waveform summation."""
    num_subsources: int
    num_stations: int
    stations_with_templates: int
    stations_missing_templates: int
    realizations_generated: int
    output_files: List[str]
    success: bool
    message: str
