"""
SWEET Backend API - FastAPI application
Handles fault discretization, kinematics, and subsource grouping
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pathlib import Path
import asyncio
import logging
import numpy as np
import os
import math
from typing import List, Dict

from models.geometry import GeometryInput, FaultGeometry
from models.kinematics import KinematicsInput, FaultKinematics
from models.subsources import SubsourceInput, SubsourceResult
from models.waveforms import WaveformSummationInput, WaveformSummationResult, WaveformAnalysisInput
from services.geometry_service import generate_fault_geometry
from services.kinematics_service import generate_fault_kinematics
from services.grouping_service import compute_subsource_groups

# GeoJSON workflow is disabled by default while focusing on synthetic workflow.
ENABLE_GEOJSON = os.getenv("ENABLE_GEOJSON", "false").lower() == "true"

if ENABLE_GEOJSON:
    from services.geojson_service import load_geojson_fault_model, group_geojson_patches

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from global_land_mask import globe
    LAND_MASK_AVAILABLE = True
except Exception:
    LAND_MASK_AVAILABLE = False

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

if ENABLE_GEOJSON:
    @app.post("/api/geojson/load")
    async def load_geojson(geojson_data: dict):
        """
        Load fault model from GeoJSON for kinematics visualization.
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
else:
    @app.post("/api/geojson/load")
    async def load_geojson(geojson_data: dict):
        raise HTTPException(
            status_code=503,
            detail="GeoJSON workflow is disabled. Set ENABLE_GEOJSON=true to re-enable."
        )


    @app.post("/api/geojson/group")
    async def group_geojson(
        geojson_data: dict,
        target_magnitude: float = 6.0,
        lat_ref: float = None
    ):
        raise HTTPException(
            status_code=503,
            detail="GeoJSON workflow is disabled. Set ENABLE_GEOJSON=true to re-enable."
        )


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
# STATION ENDPOINTS
# ========================================

@app.post("/api/stations/generate")
async def generate_stations_endpoint(params: dict):
    """
    Generate random stations around a hypocenter.

    Optional land-only filtering uses global_land_mask when available.
    """
    try:
        num_stations = int(params.get("num_stations", 10))
        max_distance = float(params.get("max_distance", 200.0))
        hypo_lat = float(params.get("hypo_lat", 35.0))
        hypo_lon = float(params.get("hypo_lon", -118.0))
        avoid_water = bool(params.get("avoid_water", True))

        if num_stations < 1 or num_stations > 500:
            raise HTTPException(status_code=400, detail="num_stations must be between 1 and 500")
        if max_distance <= 0:
            raise HTTPException(status_code=400, detail="max_distance must be > 0")

        # Allow extra draws for offshore regions where water filtering may reject many points.
        max_attempts = max(1000, num_stations * 60)
        stations = []
        attempts = 0

        while len(stations) < num_stations and attempts < max_attempts:
            attempts += 1

            angle = np.random.random() * 2.0 * np.pi
            distance = np.sqrt(np.random.random()) * max_distance

            delta_lat = (distance * math.cos(angle)) / 111.0
            delta_lon = (distance * math.sin(angle)) / (111.0 * math.cos(math.radians(hypo_lat)))

            lat = hypo_lat + delta_lat
            lon = hypo_lon + delta_lon

            if avoid_water and LAND_MASK_AVAILABLE:
                if not globe.is_land(lat, lon):
                    continue

            stations.append({
                "name": f"ST{len(stations) + 1:03d}",
                "lat": float(lat),
                "lon": float(lon),
                "distance": float(round(distance, 1))
            })

        return {
            "stations": stations,
            "requested": num_stations,
            "generated": len(stations),
            "attempts": attempts,
            "avoid_water": avoid_water,
            "land_mask_available": LAND_MASK_AVAILABLE,
            "warning": (
                "Could not place all stations on land with current settings. "
                "Try increasing max distance or disable water filtering."
                if len(stations) < num_stations and avoid_water and LAND_MASK_AVAILABLE
                else None
            )
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating stations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# WAVEFORM SUMMATION ENDPOINTS
# ========================================

@app.post("/api/waveforms/sum", response_model=WaveformSummationResult)
async def sum_waveforms_endpoint(params: WaveformSummationInput):
    """
    Sum synthetic waveforms from subsources and stations.
    
    This endpoint handles:
    - Loading subsource and station data from the web interface
    - Matching each subsource-station pair to appropriate templates
    - Time-shifting templates by rupture time
    - Summing contributions for each station
    - Generating MSEED output files
    
    Args:
        params: Waveform summation parameters including subsources, stations, and config
        
    Returns:
        Summation result with statistics and output file paths
    """
    try:
        import sys
        import os
        import tempfile
        from pathlib import Path
        
        # Add summing scripts to path
        summing_dir = Path(__file__).parent / "SWEET_scripts" / "summing"
        sys.path.insert(0, str(summing_dir))
        
        from sum_from_web_input import (
            load_subsources_from_json,
            load_stations_from_json,
            sum_waveforms
        )
        
        logger.info(f"Starting waveform summation: {len(params.subsources)} subsources, "
                   f"{len(params.stations)} stations")
        
        # Load and normalize data
        subsources = load_subsources_from_json(params.subsources)
        stations = load_stations_from_json(params.stations)
        
        # Resolve templates directory (handle relative paths)
        templates_dir = params.templates_dir
        
        # Check if S3 mode is enabled
        use_s3 = os.getenv('USE_S3_TEMPLATES', 'false').lower() == 'true'
        
        logger.info(f"Template configuration:")
        logger.info(f"  - templates_dir parameter: {templates_dir}")
        logger.info(f"  - USE_S3_TEMPLATES env: {os.getenv('USE_S3_TEMPLATES', 'not set')}")
        logger.info(f"  - S3 mode: {use_s3}")
        
        if use_s3:
            logger.info("Using S3 for template storage")
            logger.info(f"  - S3_BUCKET_NAME: {os.getenv('S3_BUCKET_NAME', 'NOT SET')}")
            logger.info(f"  - S3_TEMPLATES_PREFIX: {os.getenv('S3_TEMPLATES_PREFIX', 'NOT SET')}")
            # In S3 mode, templates_dir is just a prefix/path in the bucket
            # No need to check if local directory exists
        else:
            # Local mode: resolve and validate directory
            logger.info("Using local filesystem for templates")
            if not os.path.isabs(templates_dir):
                # Convert relative path to absolute (relative to workspace root)
                templates_dir = str(Path(__file__).parent / templates_dir)
                logger.info(f"  - Resolved to absolute path: {templates_dir}")
            
            if not os.path.isdir(templates_dir):
                logger.error(f"Templates directory not found: {templates_dir}")
                raise HTTPException(status_code=400, 
                                  detail=f"Templates directory not found: {templates_dir}")
            logger.info(f"  - Directory exists: True")
        
        # Create output directory (use temp dir on server)
        output_dir = tempfile.mkdtemp(prefix="sweet_waveforms_")
        
        # Sum waveforms (run in thread pool to avoid blocking the event loop)
        stats = await asyncio.to_thread(
            sum_waveforms,
            subsources=subsources,
            stations=stations,
            templates_dir=templates_dir,
            output_dir=output_dir,
            n_realizations=params.n_realizations,
            sampling_rate=params.sampling_rate,
            moment_scale=params.moment_scale,
            amplitude_scale=params.amplitude_scale,
            min_template_dist_km=params.min_template_dist_km
        )
        
        # Get output files
        output_files = [
            os.path.join(output_dir, f"summed_realization_{i+1:02d}.mseed")
            for i in range(params.n_realizations)
        ]
        
        logger.info(f"Waveform summation complete: {stats['realizations_generated']} "
                   f"realizations, {len(stats['stations_ok'])} stations")
        
        return WaveformSummationResult(
            num_subsources=stats['num_subsources'],
            num_stations=stats['num_stations'],
            stations_with_templates=len(stats['stations_ok']),
            stations_missing_templates=len(stats['stations_missing']),
            realizations_generated=stats['realizations_generated'],
            output_files=output_files,
            success=True,
            message=f"Generated {stats['realizations_generated']} realizations "
                   f"for {len(stats['stations_ok'])} stations"
        )
        
    except Exception as e:
        logger.error(f"Error in waveform summation: {e}", exc_info=True)
        import traceback
        error_detail = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)


@app.post("/api/waveforms/analyze")
async def analyze_waveforms_endpoint(params: WaveformAnalysisInput):
    """
    Analyze waveforms and generate plots.
    
    This endpoint handles:
    - Extracting PGA, PGV, duration statistics
    - Generating waveform overview plots
    - Creating PGA/PGV vs distance plots
    - Generating shakemap
    - Exporting statistics and detailed CSV
    
    Args:
        params: Analysis parameters including mseed_file, subsources, stations, title_prefix
        
    Returns:
        Dictionary with plot paths, statistics, and data files
    """
    try:
        import sys
        from pathlib import Path
        
        # Add summing scripts to path
        summing_dir = Path(__file__).parent / "SWEET_scripts" / "summing"
        sys.path.insert(0, str(summing_dir))
        
        from analyze_from_web import generate_all_plots
        
        logger.info(f"Analyzing waveforms from {params.mseed_file}")
        
        if not os.path.exists(params.mseed_file):
            raise HTTPException(status_code=404, detail=f"MSEED file not found: {params.mseed_file}")
        
        # Create output directory
        output_dir = os.path.join(os.path.dirname(params.mseed_file), 'plots')
        
        # Generate all plots and analysis (returns base64 data URLs)
        result = generate_all_plots(
            mseed_file=params.mseed_file,
            stations=params.stations,
            subsources=params.subsources,
            output_dir=output_dir,
            title_prefix=params.title_prefix
        )
        
        logger.info(f"Analysis complete: {result['statistics']['num_stations']} stations analyzed")
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing waveforms: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@app.get("/api/waveforms/download/{filename}")
async def download_waveform_file(filename: str):
    """
    Download a waveform MSEED file.
    
    Args:
        filename: Name of the file (e.g., 'summed_realization_01.mseed')
        
    Returns:
        File download response
    """
    # This is a simplified version - in production, you'd want to:
    # 1. Validate the filename
    # 2. Check user permissions
    # 3. Track the file path properly
    
    # For now, we'll look in a temp directory
    # In practice, you'd get this from a session or database
    import tempfile
    temp_dirs = [d for d in os.listdir(tempfile.gettempdir()) 
                 if d.startswith('sweet_waveforms_')]
    
    if not temp_dirs:
        raise HTTPException(status_code=404, detail="No waveform files found")
    
    # Search for the file
    for temp_dir in temp_dirs:
        file_path = os.path.join(tempfile.gettempdir(), temp_dir, filename)
        if os.path.exists(file_path):
            return FileResponse(
                file_path,
                media_type='application/octet-stream',
                filename=filename
            )
    
    raise HTTPException(status_code=404, detail=f"File not found: {filename}")


@app.get("/api/waveforms/download-plot/{plot_type}")
async def download_plot(plot_type: str, result_dir: str):
    """
    Download a plot image.
    
    Args:
        plot_type: Type of plot ('waveform_overview', 'pga_vs_distance', 
                   'pgv_vs_distance', 'shakemap')
        result_dir: Directory containing the plots
        
    Returns:
        Image file download response
    """
    plot_files = {
        'waveform_overview': 'waveform_overview.png',
        'pga_vs_distance': 'pga_vs_distance.png',
        'pgv_vs_distance': 'pgv_vs_distance.png',
        'shakemap': 'shakemap.png'
    }
    
    if plot_type not in plot_files:
        raise HTTPException(status_code=400, 
                          detail=f"Invalid plot type. Choose from: {list(plot_files.keys())}")
    
    file_path = os.path.join(result_dir, plot_files[plot_type])
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, 
                          detail=f"Plot not found: {plot_files[plot_type]}")
    
    return FileResponse(
        file_path,
        media_type='image/png',
        filename=plot_files[plot_type]
    )


@app.get("/api/waveforms/statistics")
async def get_waveform_statistics(result_dir: str):
    """
    Get waveform analysis statistics.
    
    Args:
        result_dir: Directory containing the analysis results
        
    Returns:
        Statistics dictionary
    """
    import json
    
    stats_file = os.path.join(result_dir, 'statistics.json')
    
    if not os.path.exists(stats_file):
        raise HTTPException(status_code=404, detail="Statistics file not found")
    
    with open(stats_file, 'r') as f:
        stats = json.load(f)
    
    return stats


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
