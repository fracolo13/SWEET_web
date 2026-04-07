"""
SWEET Backend API - FastAPI application
Handles fault discretization, kinematics, and subsource grouping
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import logging
import numpy as np

from models.geometry import GeometryInput, FaultGeometry
from models.kinematics import KinematicsInput, FaultKinematics
from models.subsources import SubsourceInput, SubsourceResult
from models.geojson import GeoJSONFaultModel
from services.geometry_service import generate_fault_geometry
from services.kinematics_service import generate_fault_kinematics
from services.grouping_service import compute_subsource_groups
from services.geojson_service import load_geojson_fault_model, group_geojson_patches

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SWEET API",
    description="Synthetic Waveform Emulation and Exploration Tool - Backend API",
    version="2.0"
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root endpoint - serve the main HTML
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main application page."""
    html_path = Path(__file__).parent / "sweet_web_v2.html"
    if html_path.exists():
        return html_path.read_text()
    return "<h1>SWEET Backend API</h1><p>Visit /docs for API documentation</p>"


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "SWEET API"}


# ========================================
# GEOJSON ENDPOINTS
# ========================================

@app.post("/api/geojson/load")
async def load_geojson(geojson_data: dict):
    """
    Load fault model from GeoJSON for kinematics visualization.
    
    This endpoint handles:
    - Parsing GeoJSON finite fault model
    - Extracting patch centroids, slip, rupture time, moment
    - Calculating total moment and magnitude
    - Returns data compatible with kinematics visualization
    
    Args:
        geojson_data: GeoJSON dictionary with fault patches
        
    Returns:
        Fault model formatted for kinematics window visualization
    """
    try:
        logger.info("Loading GeoJSON fault model")
        
        fault_model = load_geojson_fault_model(geojson_data)
        
        # Calculate grid dimensions (approximate square grid)
        num_patches = fault_model.num_patches
        n_along = int(np.ceil(np.sqrt(num_patches)))
        n_down = int(np.ceil(num_patches / n_along))
        
        # Calculate approximate dimensions from patch spread
        lons = [p.centroid_lon for p in fault_model.patches]
        lats = [p.centroid_lat for p in fault_model.patches]
        depths = [p.centroid_depth for p in fault_model.patches]
        
        # Approximate dimensions in km (rough estimate)
        length = (max(lons) - min(lons)) * 111  # degrees to km
        width = np.sqrt((max(lats) - min(lats))**2 * 111**2 + (max(depths) - min(depths))**2)
        
        # Create patches in format expected by frontend
        patches = []
        for idx, p in enumerate(fault_model.patches):
            patches.append({
                'x': p.centroid_lon,
                'y': p.centroid_lat,
                'z': p.centroid_depth,
                'slip': p.slip,
                'moment': p.sf_moment,
                'rupture_time': p.trup,
                'alongIdx': idx % n_along,
                'downIdx': idx // n_along
            })
        
        result = {
            'patches': patches,
            'totalMoment': fault_model.total_moment,
            'computedMw': fault_model.computed_mw,
            'averageSlip': fault_model.total_slip / num_patches,
            'nAlong': n_along,
            'nDown': n_down,
            'length': length,
            'width': width,
            'numPatches': num_patches
        }
        
        logger.info(f"Loaded {num_patches} patches, "
                   f"Mw={fault_model.computed_mw:.2f}, "
                   f"M0={fault_model.total_moment:.2e} N·m")
        
        return result
        
    except Exception as e:
        logger.error(f"Error loading GeoJSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/geojson/group")
async def group_geojson(
    geojson_data: dict,
    target_magnitude: float = 6.0,
    lat_ref: float = None
):
    """
    Load GeoJSON and group patches into subsources.
    
    This endpoint combines loading and grouping in one step,
    allowing direct navigation to subsources page.
    
    Args:
        geojson_data: GeoJSON dictionary with fault patches
        target_magnitude: Target magnitude for each subsource
        lat_ref: Reference latitude for coordinate normalization (optional)
        
    Returns:
        Dictionary with fault model, grouped subsources, and statistics
    """
    try:
        logger.info(f"Loading and grouping GeoJSON with target Mw={target_magnitude}")
        
        # Load fault model
        fault_model = load_geojson_fault_model(geojson_data)
        
        # Group patches
        grouped_result = group_geojson_patches(
            patches=fault_model.patches,
            target_magnitude=target_magnitude,
            lat_ref=lat_ref
        )
        
        logger.info(f"Created {grouped_result['num_groups']} subsources from "
                   f"{grouped_result['original_patches']} patches")
        
        return {
            'fault_model': fault_model.dict(),
            'subsources': grouped_result
        }
        
    except Exception as e:
        logger.error(f"Error processing GeoJSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# GEOMETRY ENDPOINTS
# ========================================

@app.post("/api/geometry/generate", response_model=FaultGeometry)
async def generate_geometry(params: GeometryInput):
    """
    Generate fault geometry with discretized patches.
    
    This endpoint handles:
    - Fault discretization into patches
    - 3D coordinate calculation for each patch
    - Corner point generation for visualization
    
    Args:
        params: Geometry parameters (length, width, dip, patch_size, etc.)
        
    Returns:
        Complete fault geometry with patch coordinates
    """
    try:
        logger.info(f"Generating geometry: {params.length}x{params.width} km, "
                   f"dip={params.dip}°, patch_size={params.patch_size} km")
        
        geometry = generate_fault_geometry(params)
        
        logger.info(f"Generated {geometry.n_along}x{geometry.n_down} = "
                   f"{len(geometry.patches)} patches")
        
        return geometry
        
    except Exception as e:
        logger.error(f"Error generating geometry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# KINEMATICS ENDPOINTS
# ========================================

@app.post("/api/kinematics/generate", response_model=FaultKinematics)
async def generate_kinematics(
    geometry: FaultGeometry,
    params: KinematicsInput
):
    """
    Generate fault kinematics with physically constrained slip distribution.
    
    This endpoint handles:
    - Slip distribution generation (uniform, random, gaussian, asperity)
    - Stress-drop limit enforcement (3 MPa for normal/strike-slip, 4 MPa for reverse)
    - Moment calculation per patch
    - Rupture time computation
    - Total moment and magnitude calculation
    
    Args:
        geometry: Pre-computed fault geometry
        params: Kinematics parameters (magnitude, rake, slip_dist, etc.)
        
    Returns:
        Complete fault kinematics with slip, moment, and rupture times
    """
    try:
        logger.info(f"Generating kinematics: Mw={params.magnitude}, rake={params.rake}°, "
                   f"distribution={params.slip_dist}")
        
        kinematics = generate_fault_kinematics(geometry, params)
        
        logger.info(f"Generated kinematics: computed Mw={kinematics.computed_mw:.2f}, "
                   f"total moment={kinematics.total_moment:.2e} N·m, "
                   f"avg slip={kinematics.average_slip:.3f} m")
        
        return kinematics
        
    except Exception as e:
        logger.error(f"Error generating kinematics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kinematics/compute")
async def compute_full_kinematics(
    geometry_params: GeometryInput,
    kinematics_params: KinematicsInput
):
    """
    Compute complete fault kinematics from geometry parameters.
    
    This is a convenience endpoint that combines geometry generation
    and kinematics computation in one call.
    
    Args:
        geometry_params: Geometry parameters
        kinematics_params: Kinematics parameters
        
    Returns:
        Complete fault kinematics
    """
    try:
        # Generate geometry
        geometry = generate_fault_geometry(geometry_params)
        
        # Generate kinematics
        kinematics = generate_fault_kinematics(geometry, kinematics_params)
        
        return kinematics
        
    except Exception as e:
        logger.error(f"Error computing full kinematics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# SUBSOURCE ENDPOINTS
# ========================================

@app.post("/api/subsources/group", response_model=SubsourceResult)
async def group_subsources(
    kinematics: FaultKinematics,
    params: SubsourceInput
):
    """
    Group patches into subsources using spatial BFS algorithm.
    
    This endpoint handles:
    - Spatial grouping of neighboring patches
    - Moment-based grouping until target magnitude reached
    - Magnitude distribution calculation
    - Group statistics (count, avg patches per group)
    
    Args:
        kinematics: Pre-computed fault kinematics
        params: Subsource parameters (target_magnitude)
        
    Returns:
        Subsource grouping result with groups and statistics
    """
    try:
        logger.info(f"Grouping subsources: target Mw={params.target_magnitude}")
        
        result = compute_subsource_groups(kinematics, params)
        
        logger.info(f"Created {result.num_groups} subsources, "
                   f"avg {result.avg_patches_per_group:.1f} patches/subsource")
        
        return result
        
    except Exception as e:
        logger.error(f"Error grouping subsources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# UTILITY ENDPOINTS
# ========================================

@app.get("/api/moment/mag-to-moment/{magnitude}")
async def magnitude_to_moment_endpoint(magnitude: float):
    """Convert moment magnitude to seismic moment."""
    from physics.moment import magnitude_to_moment
    moment = magnitude_to_moment(magnitude)
    return {"magnitude": magnitude, "moment_nm": moment}


@app.get("/api/moment/moment-to-mag/{moment}")
async def moment_to_magnitude_endpoint(moment: float):
    """Convert seismic moment to moment magnitude."""
    from physics.moment import moment_to_magnitude
    magnitude = moment_to_magnitude(moment)
    return {"moment_nm": moment, "magnitude": magnitude}


@app.get("/api/stress-drop/limit/{rake}")
async def stress_drop_limit_endpoint(rake: float):
    """Get stress drop limit based on fault mechanism."""
    from physics.stress_drop import get_stress_drop_limit
    limit_pa = get_stress_drop_limit(rake)
    limit_mpa = limit_pa / 1e6
    
    mechanism = "reverse/thrust" if 45 < rake < 135 else "normal/strike-slip"
    
    return {
        "rake": rake,
        "mechanism": mechanism,
        "stress_drop_limit_pa": limit_pa,
        "stress_drop_limit_mpa": limit_mpa
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
