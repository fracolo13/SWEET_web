"""Subsources data models."""
from pydantic import BaseModel, Field
from typing import List, Tuple


class SubsourceInput(BaseModel):
    """Input parameters for subsource grouping."""
    target_magnitude: float = Field(..., ge=5.0, le=6.5, description="Target subsource magnitude")


class SubsourceGroup(BaseModel):
    """A group of patches forming a subsource."""
    patches: List[Tuple[int, int]]  # List of (along_idx, down_idx)
    total_moment: float
    magnitude: float


class SubsourceResult(BaseModel):
    """Result of subsource grouping."""
    groups: List[SubsourceGroup]
    num_groups: int
    avg_patches_per_group: float
    magnitude_distribution: List[float]
