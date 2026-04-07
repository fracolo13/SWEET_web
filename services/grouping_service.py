"""Subsource grouping service - spatial BFS grouping algorithm."""
import numpy as np
from typing import List, Tuple, Set
from collections import deque
from models.kinematics import FaultKinematics
from models.subsources import SubsourceInput, SubsourceResult, SubsourceGroup
from physics.moment import magnitude_to_moment, moment_to_magnitude


def compute_subsource_groups(
    kinematics: FaultKinematics,
    params: SubsourceInput
) -> SubsourceResult:
    """
    Group patches into subsources based on target magnitude using spatial BFS.
    
    Args:
        kinematics: Fault kinematics with patch moments
        params: Subsource grouping parameters
        
    Returns:
        Subsource grouping result with groups and statistics
    """
    target_moment = magnitude_to_moment(params.target_magnitude)
    
    # Create moment grid
    moment_grid = np.zeros((kinematics.n_along, kinematics.n_down))
    for patch in kinematics.patches:
        moment_grid[patch.along_idx, patch.down_idx] = patch.moment
    
    # Track visited patches
    visited = np.zeros((kinematics.n_along, kinematics.n_down), dtype=bool)
    groups = []
    
    # Process patches starting from highest moment
    patch_order = sorted(
        [(p.moment, p.along_idx, p.down_idx) for p in kinematics.patches],
        reverse=True
    )
    
    for _, start_i, start_j in patch_order:
        if visited[start_i, start_j]:
            continue
        
        # Start new group with BFS
        group = _bfs_grouping(
            start_i, start_j,
            moment_grid,
            visited,
            target_moment,
            kinematics.n_along,
            kinematics.n_down
        )
        
        if group:
            groups.append(group)
    
    # Calculate group statistics
    group_results = []
    magnitudes = []
    
    for group_patches in groups:
        total_moment = sum(moment_grid[i, j] for i, j in group_patches)
        magnitude = moment_to_magnitude(total_moment)
        
        group_results.append(SubsourceGroup(
            patches=group_patches,
            total_moment=total_moment,
            magnitude=magnitude
        ))
        magnitudes.append(magnitude)
    
    total_patches = kinematics.n_along * kinematics.n_down
    avg_patches = total_patches / len(groups) if groups else 0
    
    return SubsourceResult(
        groups=group_results,
        num_groups=len(groups),
        avg_patches_per_group=avg_patches,
        magnitude_distribution=magnitudes
    )


def _bfs_grouping(
    start_i: int,
    start_j: int,
    moment_grid: np.ndarray,
    visited: np.ndarray,
    target_moment: float,
    n_along: int,
    n_down: int
) -> List[Tuple[int, int]]:
    """
    Breadth-first search grouping from a starting patch.
    
    Args:
        start_i: Starting patch along-strike index
        start_j: Starting patch down-dip index
        moment_grid: Grid of patch moments
        visited: Grid tracking visited patches
        target_moment: Target moment for group
        n_along: Number of patches along strike
        n_down: Number of patches down dip
        
    Returns:
        List of (i, j) patch indices in the group
    """
    if visited[start_i, start_j]:
        return []
    
    group = []
    group_moment = 0.0
    queue = deque([(start_i, start_j)])
    visited[start_i, start_j] = True
    
    while queue and group_moment < target_moment:
        i, j = queue.popleft()
        group.append((i, j))
        group_moment += moment_grid[i, j]
        
        if group_moment >= target_moment:
            break
        
        # Get 4-connected neighbors (left, right, up, down)
        neighbors = _get_neighbors(i, j, n_along, n_down, visited)
        
        # Sort neighbors by moment (prioritize high-moment patches)
        neighbors.sort(key=lambda pos: moment_grid[pos[0], pos[1]], reverse=True)
        
        # Add neighbors to queue
        for ni, nj in neighbors:
            if not visited[ni, nj]:
                visited[ni, nj] = True
                queue.append((ni, nj))
    
    return group


def _get_neighbors(
    i: int,
    j: int,
    n_along: int,
    n_down: int,
    visited: np.ndarray
) -> List[Tuple[int, int]]:
    """
    Get valid 4-connected neighbors.
    
    Args:
        i: Along-strike index
        j: Down-dip index
        n_along: Total patches along strike
        n_down: Total patches down dip
        visited: Visited grid
        
    Returns:
        List of valid neighbor (i, j) positions
    """
    neighbors = []
    
    # Left, Right, Up, Down
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    
    for di, dj in directions:
        ni, nj = i + di, j + dj
        if 0 <= ni < n_along and 0 <= nj < n_down and not visited[ni, nj]:
            neighbors.append((ni, nj))
    
    return neighbors
