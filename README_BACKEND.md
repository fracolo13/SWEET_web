# SWEET Backend API

**Synthetic Waveform Emulation and Exploration Tool - Backend**

## Architecture

### Separation of Concerns

**Frontend (sweet_web_v2.html):**
- ✅ UI logic (sliders, tabs, forms)
- ✅ Plotly rendering and visualization
- ✅ Lightweight previews (geometry outlines)
- ✅ User interaction handling

**Backend (FastAPI):**
- 🚨 Physically constrained calculations
- 🚨 Numerically heavy computations
- 🚨 Reproducibility-critical operations
- 🚨 Fault discretization
- 🚨 Slip & moment distribution with stress-drop limits
- 🚨 Rupture time computation
- 🚨 Subsource grouping (BFS algorithm)
- 🚨 (Future) Waveform synthesis

## Project Structure

```
sweet/
├── app.py                      # FastAPI entry point
├── models/                     # Pydantic data models
│   ├── __init__.py
│   ├── geometry.py            # Fault geometry models
│   ├── kinematics.py          # Slip/moment models
│   ├── subsources.py          # Subsource grouping models
│   └── stations.py            # Station configuration models
├── physics/                    # Physics calculations
│   ├── __init__.py
│   ├── moment.py              # Moment-magnitude conversions
│   ├── slip.py                # Slip distribution generation
│   ├── rupture.py             # Rupture time calculations
│   └── stress_drop.py         # Stress-drop constraints
├── services/                   # Business logic layer
│   ├── __init__.py
│   ├── geometry_service.py    # Fault discretization
│   ├── kinematics_service.py  # Slip distribution with constraints
│   └── grouping_service.py    # Subsource BFS grouping
└── requirements.txt            # Python dependencies
```

## API Endpoints

### Geometry

**POST /api/geometry/generate**
- Generate fault geometry with discretized patches
- Input: `GeometryInput` (length, width, dip, patch_size, etc.)
- Output: `FaultGeometry` (patches with 3D coordinates)

### Kinematics

**POST /api/kinematics/generate**
- Generate slip distribution with physical constraints
- Input: `FaultGeometry` + `KinematicsInput` (magnitude, rake, slip_dist, etc.)
- Output: `FaultKinematics` (slip, moment, rupture times per patch)
- Enforces stress-drop limits: 3 MPa (normal/strike-slip), 4 MPa (reverse/thrust)

**POST /api/kinematics/compute**
- Convenience endpoint: geometry + kinematics in one call
- Input: `GeometryInput` + `KinematicsInput`
- Output: `FaultKinematics`

### Subsources

**POST /api/subsources/group**
- Group patches into subsources using spatial BFS
- Input: `FaultKinematics` + `SubsourceInput` (target_magnitude)
- Output: `SubsourceResult` (groups, statistics, magnitude distribution)

### GeoJSON (Fast Track)

**POST /api/geojson/load**
- Load finite fault model from GeoJSON
- Input: GeoJSON dictionary with fault patches
- Output: `GeoJSONFaultModel` (patches with centroids, slip, moment, rupture time)
- Extracts: slip, trup, sf_moment, rise, t_fal from properties

**POST /api/geojson/group**
- Load GeoJSON and group patches in one step
- Input: GeoJSON + target_magnitude
- Output: Fault model + grouped subsources
- **Skip directly to subsources page** - no need for geometry/kinematics setup
- Uses KDTree spatial clustering like reference scripts

### Utilities

**GET /api/moment/mag-to-moment/{magnitude}**
- Convert Mw to M₀

**GET /api/moment/moment-to-mag/{moment}**
- Convert M₀ to Mw

**GET /api/stress-drop/limit/{rake}**
- Get stress-drop limit for fault mechanism

## Physics Implementation

### Stress-Drop Constraints

Maximum moment per patch enforced by:
```
M₀_max = (16/7) × (Δσ_max / √π) × A^1.5
```

Where:
- Δσ_max = 4 MPa for reverse/thrust (45° < rake < 135°)
- Δσ_max = 3 MPa for normal/strike-slip
- A = patch area in m²

### Slip Distribution Types

1. **Uniform**: Constant slip with small perturbations
2. **Random**: Random with rake-dependent envelope
3. **Gaussian**: Gaussian decay from hypocenter
4. **Asperity**: Multiple high-slip patches

All distributions:
- Respect stress-drop limits
- Maintain target magnitude
- Use rake-dependent spatial patterns

### Subsource Grouping

**Algorithm**: Breadth-First Search (BFS)
- Start from highest-moment patches
- Group 4-connected neighbors (left/right/up/down)
- Continue until group reaches target moment threshold
- Prioritize high-moment neighbors within each group

## Installation

```bash
# Create virtual environment
conda create -n sweet_web python=3.10
conda activate sweet_web

# Install dependencies
pip install -r requirements.txt
```

## Running the Server

```bash
# Development mode with hot reload
uvicorn app:app --reload --port 5001

# Production mode
uvicorn app:app --host 0.0.0.0 --port 5001
```

Server will run at: `http://localhost:5001`

API documentation at: `http://localhost:5001/docs`

## Deploying on Render

This repository includes a `render.yaml` blueprint for one-click deployment.

### Option A: Blueprint (recommended)

1. Push this repository to GitHub
2. In Render, choose **New +** → **Blueprint**
3. Select this repository
4. Render reads `render.yaml` and creates the web service automatically

### Option B: Manual Web Service

- **Environment**: Python
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python -m uvicorn app:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/health`

After deployment, your app will be available at your Render service URL, and API docs at `/docs`.

## Usage Example

```python
import requests

# 1. Generate geometry
geometry_resp = requests.post('http://localhost:5000/api/geometry/generate', json={
    "mode": "plane",
    "length": 20.0,
    "width": 15.0,
    "dip": 45.0,
    "top_depth": 2.0,
    "patch_size": 2.0,
    "strike": 0.0
})
geometry = geometry_resp.json()

# 2. Generate kinematics
kinematics_resp = requests.post('http://localhost:5000/api/kinematics/generate', json={
    "geometry": geometry,
    "params": {
        "magnitude": 6.5,
        "rake": 90.0,
        "slip_dist": "gaussian",
        "hypo_along": 0.5,
        "hypo_down": 0.5,
        "rupture_vel": 2.5
    }
})
kinematics = kinematics_resp.json()

# 3. Group subsources
subsources_resp = requests.post('http://localhost:5000/api/subsources/group', json={
    "kinematics": kinematics,
    "params": {
        "target_magnitude": 5.5
    }
})
subsources = subsources_resp.json()

print(f"Created {subsources['num_groups']} subsources")
print(f"Magnitude range: {min(subsources['magnitude_distribution']):.2f} - "
      f"{max(subsources['magnitude_distribution']):.2f}")
```

### GeoJSON Fast Track

```python
import requests
import json

# Load GeoJSON file
with open('FFM.geojson') as f:
    geojson_data = json.load(f)

# Option 1: Load only (for visualization)
fault_resp = requests.post('http://localhost:5001/api/geojson/load', 
                          json=geojson_data)
fault_model = fault_resp.json()
print(f"Loaded {fault_model['num_patches']} patches")
print(f"Computed Mw: {fault_model['computed_mw']:.2f}")

# Option 2: Load and group in one step (skip to subsources)
result_resp = requests.post('http://localhost:5001/api/geojson/group', 
                           json={
                               'geojson_data': geojson_data,
                               'target_magnitude': 6.0
                           })
result = result_resp.json()

print(f"Original patches: {result['subsources']['original_patches']}")
print(f"Grouped into: {result['subsources']['num_groups']} subsources")
print(f"Magnitudes: {result['subsources']['magnitude_distribution']}")
```

## Testing

```bash
# Health check
curl http://localhost:5000/health

# API documentation
open http://localhost:5000/docs
```

## Future Enhancements

- [ ] Waveform synthesis endpoint
- [ ] Station grid generation
- [ ] GeoJSON import/export
- [ ] Real-time computation streaming
- [ ] Caching for repeated calculations
- [ ] Parallel processing for large faults
- [ ] Database storage for fault models
