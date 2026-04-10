# SWEET Waveform Summation and Analysis

This directory contains scripts for summing synthetic waveforms and analyzing results.

## Overview

The complete workflow:
1. **Sum waveforms**: Combine subsource contributions for each station
2. **Analyze results**: Extract PGA, PGV, duration, peak times
3. **Generate plots**: Waveform panels, ground motion vs distance, shakemaps
4. **Download results**: MSEED files, plots, statistics

## Files

### Core Scripts
- **`helpers.py`**: Utility functions (moment/magnitude, distance, template loading)
- **`sum_from_web_input.py`**: Web-compatible waveform summation
- **`analyze_from_web.py`**: Waveform analysis and plotting
- **`example_complete_workflow.py`**: Complete workflow demonstration

### Legacy Scripts
- **`01_sum_bulk_synthetics.py`**: Batch processing for multiple magnitude events
- **`02_plot_bulk_synthetics.py`**: Batch plotting with GMPE comparison

## Quick Start

### Complete Workflow (Web Interface)

```python
import requests

API_BASE = "http://localhost:5001"

# 1. Sum waveforms
response = requests.post(f"{API_BASE}/api/waveforms/sum", json={
    "subsources": subsources_from_grouping,
    "stations": stations_from_interface,
    "templates_dir": "/path/to/templates",
    "n_realizations": 1
})
result = response.json()
mseed_file = result['output_files'][0]

# 2. Analyze and plot
response = requests.post(f"{API_BASE}/api/waveforms/analyze", json={
    "mseed_file": mseed_file,
    "subsources": subsources_from_grouping,
    "stations": stations_from_interface,
    "title_prefix": "My Event"
})
analysis = response.json()

# 3. View results
print(f"Max PGA: {analysis['statistics']['pga_max']:.3f} m/s²")
print(f"Shakemap: {analysis['plots']['shakemap']}")

# 4. Download
response = requests.get(f"{API_BASE}/api/waveforms/download/summed_realization_01.mseed")
with open('waveform.mseed', 'wb') as f:
    f.write(response.content)
```

See `example_complete_workflow.py` for a full working example.

## API Endpoints

### 1. Sum Waveforms
**POST** `/api/waveforms/sum`

Sums synthetic waveforms from subsources and stations.

**Request:**
```json
{
  "subsources": [...],
  "stations": [...],
  "templates_dir": "/path/to/templates",
  "n_realizations": 1,
  "sampling_rate": 100.0,
  "moment_scale": false,
  "amplitude_scale": 1.0,
  "min_template_dist_km": 10.0
}
```

**Response:**
```json
{
  "num_subsources": 10,
  "num_stations": 50,
  "stations_with_templates": 48,
  "stations_missing_templates": 2,
  "realizations_generated": 1,
  "output_files": ["/tmp/sweet_waveforms_*/summed_realization_01.mseed"],
  "success": true,
  "message": "Generated 1 realizations for 48 stations"
}
```

### 2. Analyze Waveforms
**POST** `/api/waveforms/analyze`

Analyzes waveforms and generates plots.

**Request:**
```json
{
  "mseed_file": "/path/to/summed_realization_01.mseed",
  "subsources": [...],
  "stations": [...],
  "title_prefix": "Event Name"
}
```

**Response:**
```json
{
  "plots": {
    "waveform_overview": "/path/to/plots/waveform_overview.png",
    "pga_vs_distance": "/path/to/plots/pga_vs_distance.png",
    "pgv_vs_distance": "/path/to/plots/pgv_vs_distance.png",
    "shakemap": "/path/to/plots/shakemap.png"
  },
  "data": {
    "statistics": "/path/to/plots/statistics.json",
    "detailed_csv": "/path/to/plots/waveform_analysis.csv"
  },
  "statistics": {
    "num_stations": 48,
    "pga_max": 0.523,
    "pga_mean": 0.145,
    "pga_median": 0.098,
    "pgv_max": 0.0234,
    "pgv_mean": 0.0087,
    "pgv_median": 0.0065,
    "distance_min": 12.5,
    "distance_max": 145.3,
    "magnitude": 6.2
  },
  "chosen_stations": ["STA1", "STA2", ...]
}
```

### 3. Download MSEED File
**GET** `/api/waveforms/download/{filename}`

Downloads a waveform MSEED file.

**Example:**
```bash
curl -O http://localhost:5001/api/waveforms/download/summed_realization_01.mseed
```

### 4. Download Plot
**GET** `/api/waveforms/download-plot/{plot_type}?result_dir=/path`

Downloads a plot image.

**Plot types:** `waveform_overview`, `pga_vs_distance`, `pgv_vs_distance`, `shakemap`

**Example:**
```bash
curl -O http://localhost:5001/api/waveforms/download-plot/shakemap?result_dir=/tmp/plots
```

### 5. Get Statistics
**GET** `/api/waveforms/statistics?result_dir=/path`

Returns analysis statistics as JSON.

**Example:**
```bash
curl http://localhost:5001/api/waveforms/statistics?result_dir=/tmp/plots
```

## Analysis Outputs

### Generated Plots

1. **Waveform Overview** (`waveform_overview.png`)
   - 3-component waveforms for 10 random stations
   - Shows N, E, Z components with peak amplitudes
   - Good for quick quality check

2. **PGA vs Distance** (`pga_vs_distance.png`)
   - Horizontal PGA vs hypocentral distance
   - Colored by VS30 value
   - Log-scale Y-axis
   - Includes statistics (max, mean PGA)

3. **PGV vs Distance** (`pgv_vs_distance.png`)
   - Horizontal PGV vs hypocentral distance
   - Colored by VS30 value
   - Log-scale Y-axis
   - Includes statistics (max, mean PGV)

4. **Shakemap** (`shakemap.png`)
   - Spatial distribution of PGA
   - USGS-style color scale (%g)
   - Shows stations, hypocenter, fault outline
   - Interpolated contours

### Data Files

1. **Statistics JSON** (`statistics.json`)
   - Summary statistics (PGA, PGV ranges)
   - Number of stations
   - Hypocenter location
   - Event magnitude

2. **Detailed CSV** (`waveform_analysis.csv`)
   - Per-station data
   - Columns: station, lat, lon, vs30, dist_km, pga_h, pgv_h, 
             pga_e, pga_n, pga_z, pgv_e, pgv_n, pgv_z,
             duration, peak_time

### Metrics Explained

- **PGA (Peak Ground Acceleration)**: Maximum ground acceleration
  - Units: m/s² or %g (1 g = 9.81 m/s²)
  - Horizontal: √(N² + E²) vector magnitude
  
- **PGV (Peak Ground Velocity)**: Maximum ground velocity
  - Units: m/s or cm/s
  - Obtained by integrating acceleration
  - More stable metric than PGA

- **Duration**: Total waveform length in seconds
- **Peak Time**: Time of maximum amplitude occurrence

## Frontend Integration Example

```javascript
// Generate and analyze waveforms
async function processWaveforms() {
    // 1. Sum waveforms
    const sumResponse = await fetch('/api/waveforms/sum', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            subsources: getSubsources(),
            stations: getStations(),
            templates_dir: '/path/to/templates',
            n_realizations: 1
        })
    });
    const sumResult = await sumResponse.json();
    
    // 2. Analyze
    const analysisResponse = await fetch('/api/waveforms/analyze', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            mseed_file: sumResult.output_files[0],
            subsources: getSubsources(),
            stations: getStations(),
            title_prefix: "My Event"
        })
    });
    const analysis = await analysisResponse.json();
    
    // 3. Display results
    document.getElementById('shakemap').src = analysis.plots.shakemap;
    document.getElementById('max-pga').textContent = 
        `${analysis.statistics.pga_max.toFixed(3)} m/s²`;
    
    // 4. Enable downloads
    addDownloadLink('Download MSEED', 
        `/api/waveforms/download/${sumResult.output_files[0].split('/').pop()}`);
}
```

See `example_complete_workflow.py` for more details.

## Command-Line Usage

### Method 1: Direct Python Script

```bash
python sum_from_web_input.py \
    --subsources subsources.json \
    --stations stations.json \
    --templates-dir /path/to/preprocessed/templates \
    --output output_waveforms \
    --n-realizations 1 \
    --sampling-rate 100 \
    --amplitude-scale 1.0 \
    --min-template-dist 10
```

### Method 2: Python API

```python
from sum_from_web_input import (
    load_subsources_from_json,
    load_stations_from_json,
    sum_waveforms
)

# Load data
subsources = load_subsources_from_json("subsources.json")
stations = load_stations_from_json("stations.json")

# Sum waveforms
stats = sum_waveforms(
    subsources=subsources,
    stations=stations,
    templates_dir="/path/to/templates",
    output_dir="output_waveforms",
    n_realizations=1,
    sampling_rate=100.0,
    moment_scale=False,
    amplitude_scale=1.0,
    min_template_dist_km=10.0
)

print(f"Processed {stats['num_subsources']} subsources")
print(f"Generated waveforms for {len(stats['stations_ok'])} stations")
```

### Method 3: Analyze Existing MSEED

```python
from analyze_from_web import generate_all_plots

result = generate_all_plots(
    mseed_file='summed_realization_01.mseed',
    stations=stations_list,
    subsources=subsources_list,
    output_dir='plots',
    title_prefix='My Event'
)

print(f"Plots saved to: {result['plots']}")
print(f"Statistics: {result['statistics']}")
```

## Parameters

### Required Parameters

- **subsources**: List of subsource dictionaries with:
  - `centroid_lon`, `centroid_lat`, `centroid_depth`: Location (degrees, km)
  - `sf_moment`: Seismic moment (N·m)
  - `trup`: Rupture time (seconds)
  - `magnitude`: Optional, computed from moment if not provided

- **stations**: List of station dictionaries with:
  - `station_code`/`name`/`id`: Station identifier
  - `latitude`, `longitude`: Location (degrees)
  - `vs30`: Optional, defaults to 500 m/s
  - `network`: Optional, defaults to "XX"

- **templates_dir**: Path to preprocessed templates directory
  - Structure: `vs30_XXX/MX.X/XXXkm/template_NN.npy`

- **output_dir**: Where to save MSEED files

### Optional Parameters

- **n_realizations** (default: 1): Number of noise realizations
- **sampling_rate** (default: 100.0 Hz): Waveform sampling rate
- **moment_scale** (default: False): Apply EGF moment ratio scaling
  - Set to `False` if templates are already GMPE-calibrated
  - Set to `True` for physically correct EGF scaling
- **amplitude_scale** (default: 1.0): Global amplitude multiplier
- **min_template_dist_km** (default: 10.0): Minimum distance to avoid near-field artifacts

## Template Library

Templates must be preprocessed and organized as:
```
templates_dir/
  vs30_300/
    M5.0/
      001km/
        template_00.npy  # shape: (3, n_samples) [E, N, Z]
      005km/
        template_00.npy
      ...
    M5.1/
      ...
  vs30_500/
    ...
```

Each `.npy` file contains a (3, n_samples) array with East, North, Vertical components.

## Output

MSEED files are written to the output directory:
- `summed_realization_01.mseed`
- `summed_realization_02.mseed` (if n_realizations > 1)
- ...

Each file contains all station channels with summed contributions from all subsources.

## Integration with Web Interface

The API endpoint at `/api/waveforms/sum` can be called from the web interface:

1. User selects fault geometry and generates kinematics
2. System groups patches into subsources
3. User places or uploads stations
4. User clicks "Generate Waveforms"
5. Frontend sends subsources + stations to API
6. Backend processes and returns waveform files
7. Frontend allows download or visualization

## Example: Complete Workflow

```python
# 1. Generate fault model (from web interface or script)
from services.geojson_service import load_geojson_fault_model, group_geojson_patches

# Load GeoJSON fault
with open("fault_model.geojson") as f:
    geojson_data = json.load(f)

fault_model = load_geojson_fault_model(geojson_data)

# Group into subsources
result = group_geojson_patches(
    patches=fault_model.patches,
    target_magnitude=6.0
)
subsources = result['grouped_patches']

# 2. Define stations
stations = [
    {
        "station_code": "STA1",
        "latitude": 46.1,
        "longitude": 7.6,
        "vs30": 500.0,
        "network": "CH"
    },
    # ... more stations
]

# 3. Sum waveforms
from sum_from_web_input import sum_waveforms

stats = sum_waveforms(
    subsources=subsources,
    stations=stations,
    templates_dir="/path/to/templates",
    output_dir="waveforms",
    n_realizations=1
)

print(f"✓ Generated waveforms for {len(stats['stations_ok'])} stations")
```

## Troubleshooting

### "No preprocessed templates found"
- Check that `templates_dir` exists and contains the expected structure
- Verify template files are `.npy` format with shape (3, n_samples)

### "Station missing templates"
- The template library may not have the required VS30/magnitude/distance combination
- Check available templates with `get_available_templates_info(templates_dir)`
- Consider expanding the template library or adjusting search tolerance

### "Near-field artifacts"
- Set `min_template_dist_km` to at least 10 km
- Templates at very close distances have unphysical amplitudes

### "Amplitudes too high/low"
- Adjust `amplitude_scale` parameter
- If templates are GMPE-calibrated, use `moment_scale=False`
- If using raw EGF templates, use `moment_scale=True`
