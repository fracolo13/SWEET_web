"""
Complete Workflow Example: From Fault to Waveforms to Results
==============================================================

This script demonstrates the complete workflow:
1. Generate/load fault model with subsources
2. Define station locations
3. Sum synthetic waveforms
4. Analyze and generate plots
5. Download and display results
"""

import requests
import json
import os
from pathlib import Path

# Base URL for the API
API_BASE = "http://localhost:5001"


def example_complete_workflow():
    """Complete workflow from fault to analysis."""
    
    print("=" * 70)
    print("COMPLETE SWEET WAVEFORM WORKFLOW")
    print("=" * 70)
    
    # ========================================
    # Step 1: Load or create fault model
    # ========================================
    print("\n[1] Loading fault model...")
    
    # Option A: Use GeoJSON file
    # with open('fault_model.geojson') as f:
    #     geojson_data = json.load(f)
    # 
    # response = requests.post(f"{API_BASE}/api/geojson/group", json={
    #     "geojson_data": geojson_data,
    #     "target_magnitude": 6.0
    # })
    # result = response.json()
    # subsources = result['subsources']['grouped_patches']
    
    # Option B: Use example subsources
    subsources = [
        {
            "centroid_lon": 7.5,
            "centroid_lat": 46.0,
            "centroid_depth": 10.0,
            "sf_moment": 5.62e17,  # Mw 6.0
            "trup": 2.0,
            "rise": 1.0,
            "slip": 1.5,
            "magnitude": 6.0
        },
        {
            "centroid_lon": 7.52,
            "centroid_lat": 46.02,
            "centroid_depth": 10.5,
            "sf_moment": 5.62e17,
            "trup": 2.5,
            "rise": 1.0,
            "slip": 1.5,
            "magnitude": 6.0
        },
        {
            "centroid_lon": 7.48,
            "centroid_lat": 45.98,
            "centroid_depth": 9.5,
            "sf_moment": 5.62e17,
            "trup": 3.0,
            "rise": 1.0,
            "slip": 1.5,
            "magnitude": 6.0
        }
    ]
    
    print(f"✓ Loaded {len(subsources)} subsources")
    
    # ========================================
    # Step 2: Define stations
    # ========================================
    print("\n[2] Defining stations...")
    
    stations = [
        {
            "station_code": "STA1",
            "name": "STA1",
            "latitude": 46.1,
            "longitude": 7.6,
            "vs30": 500.0,
            "network": "CH"
        },
        {
            "station_code": "STA2",
            "name": "STA2",
            "latitude": 46.05,
            "longitude": 7.45,
            "vs30": 700.0,
            "network": "CH"
        },
        {
            "station_code": "STA3",
            "name": "STA3",
            "latitude": 45.95,
            "longitude": 7.55,
            "vs30": 300.0,
            "network": "CH"
        },
        {
            "station_code": "STA4",
            "name": "STA4",
            "latitude": 46.15,
            "longitude": 7.4,
            "vs30": 500.0,
            "network": "CH"
        }
    ]
    
    print(f"✓ Defined {len(stations)} stations")
    
    # ========================================
    # Step 3: Sum waveforms
    # ========================================
    print("\n[3] Summing waveforms...")
    
    waveform_request = {
        "subsources": subsources,
        "stations": stations,
        "templates_dir": "/Users/francescoacolosimo/Desktop/SED/envelopes_sweet/Data/synthetics/synthetics_filtered",
        "n_realizations": 1,
        "sampling_rate": 100.0,
        "moment_scale": False,
        "amplitude_scale": 1.0,
        "min_template_dist_km": 10.0
    }
    
    response = requests.post(f"{API_BASE}/api/waveforms/sum", json=waveform_request)
    
    if response.status_code != 200:
        print(f"❌ Error: {response.text}")
        return
    
    waveform_result = response.json()
    
    print(f"✓ Generated {waveform_result['realizations_generated']} realizations")
    print(f"  Stations with templates: {waveform_result['stations_with_templates']}")
    print(f"  Output files: {waveform_result['output_files']}")
    
    # ========================================
    # Step 4: Analyze waveforms and generate plots
    # ========================================
    print("\n[4] Analyzing waveforms and generating plots...")
    
    mseed_file = waveform_result['output_files'][0]
    
    analysis_request = {
        "mseed_file": mseed_file,
        "subsources": subsources,
        "stations": stations,
        "title_prefix": "Example Mw 6.0 Event"
    }
    
    response = requests.post(f"{API_BASE}/api/waveforms/analyze", json=analysis_request)
    
    if response.status_code != 200:
        print(f"❌ Error: {response.text}")
        return
    
    analysis_result = response.json()
    
    print(f"✓ Analysis complete!")
    print(f"  Stations analyzed: {analysis_result['statistics']['num_stations']}")
    print(f"  Max PGA: {analysis_result['statistics']['pga_max']:.3f} m/s²")
    print(f"  Mean PGA: {analysis_result['statistics']['pga_mean']:.3f} m/s²")
    print(f"  Max PGV: {analysis_result['statistics']['pgv_max']:.4f} m/s")
    
    print("\n  Generated plots:")
    for plot_name, plot_path in analysis_result['plots'].items():
        print(f"    - {plot_name}: {plot_path}")
    
    print("\n  Data files:")
    for data_name, data_path in analysis_result['data'].items():
        print(f"    - {data_name}: {data_path}")
    
    # ========================================
    # Step 5: Download results (optional)
    # ========================================
    print("\n[5] Results available for download:")
    print(f"  MSEED: GET {API_BASE}/api/waveforms/download/{os.path.basename(mseed_file)}")
    print(f"  Plots: GET {API_BASE}/api/waveforms/download-plot/<plot_type>?result_dir=<dir>")
    print(f"  Stats: GET {API_BASE}/api/waveforms/statistics?result_dir=<dir>")
    
    # ========================================
    # Summary
    # ========================================
    print("\n" + "=" * 70)
    print("WORKFLOW COMPLETE")
    print("=" * 70)
    print(f"""
Summary:
  • Subsources: {len(subsources)}
  • Stations: {len(stations)}
  • Realizations: {waveform_result['realizations_generated']}
  • Stations with waveforms: {waveform_result['stations_with_templates']}
  • PGA range: {analysis_result['statistics']['pga_max']:.3f} m/s²
  • PGV range: {analysis_result['statistics']['pgv_max']:.4f} m/s
  
Next steps:
  1. View plots in: {os.path.dirname(analysis_result['plots']['waveform_overview'])}
  2. Check detailed CSV: {analysis_result['data']['detailed_csv']}
  3. Download MSEED files for further analysis
  4. Integrate with frontend visualization
    """)


def example_download_files():
    """Example of downloading files from the API."""
    
    print("\n" + "=" * 70)
    print("DOWNLOAD EXAMPLE")
    print("=" * 70)
    
    # Download MSEED file
    filename = "summed_realization_01.mseed"
    response = requests.get(f"{API_BASE}/api/waveforms/download/{filename}")
    
    if response.status_code == 200:
        with open(f"downloaded_{filename}", 'wb') as f:
            f.write(response.content)
        print(f"✓ Downloaded MSEED: downloaded_{filename}")
    else:
        print(f"❌ Error downloading MSEED: {response.text}")
    
    # Download plot
    result_dir = "/path/to/results"  # Replace with actual path
    plot_type = "shakemap"
    
    response = requests.get(f"{API_BASE}/api/waveforms/download-plot/{plot_type}", 
                          params={"result_dir": result_dir})
    
    if response.status_code == 200:
        with open(f"downloaded_{plot_type}.png", 'wb') as f:
            f.write(response.content)
        print(f"✓ Downloaded plot: downloaded_{plot_type}.png")
    else:
        print(f"❌ Error downloading plot: {response.text}")


def example_frontend_javascript():
    """
    Example JavaScript code for frontend integration.
    This would be used in the web interface.
    """
    
    js_code = '''
// Frontend JavaScript Example
// ============================

async function generateAndAnalyzeWaveforms() {
    try {
        // 1. Get subsources and stations from UI
        const subsources = getCurrentSubsources();
        const stations = getCurrentStations();
        
        // 2. Sum waveforms
        showProgress("Summing waveforms...");
        const sumResponse = await fetch('/api/waveforms/sum', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                subsources: subsources,
                stations: stations,
                templates_dir: '/path/to/templates',
                n_realizations: 1,
                sampling_rate: 100.0,
                moment_scale: false,
                amplitude_scale: 1.0,
                min_template_dist_km: 10.0
            })
        });
        
        const sumResult = await sumResponse.json();
        console.log(`Generated ${sumResult.realizations_generated} realizations`);
        
        // 3. Analyze and plot
        showProgress("Analyzing waveforms...");
        const analysisResponse = await fetch('/api/waveforms/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                mseed_file: sumResult.output_files[0],
                subsources: subsources,
                stations: stations,
                title_prefix: "My Earthquake Event"
            })
        });
        
        const analysisResult = await analysisResponse.json();
        
        // 4. Display results
        displayStatistics(analysisResult.statistics);
        displayPlots(analysisResult.plots);
        
        // 5. Enable downloads
        enableDownloads(sumResult.output_files, analysisResult.plots);
        
        showSuccess("Waveform generation complete!");
        
    } catch (error) {
        showError(`Error: ${error.message}`);
        console.error(error);
    }
}

function displayStatistics(stats) {
    document.getElementById('num-stations').textContent = stats.num_stations;
    document.getElementById('max-pga').textContent = `${stats.pga_max.toFixed(3)} m/s²`;
    document.getElementById('mean-pga').textContent = `${stats.pga_mean.toFixed(3)} m/s²`;
    document.getElementById('max-pgv').textContent = `${stats.pgv_max.toFixed(4)} m/s`;
    document.getElementById('magnitude').textContent = `Mw ${stats.magnitude.toFixed(1)}`;
}

function displayPlots(plots) {
    // Display shakemap
    const shakemapImg = document.getElementById('shakemap-img');
    shakemapImg.src = plots.shakemap;
    
    // Display other plots in gallery
    const plotGallery = document.getElementById('plot-gallery');
    plotGallery.innerHTML = '';
    
    for (const [name, path] of Object.entries(plots)) {
        const img = document.createElement('img');
        img.src = path;
        img.alt = name;
        img.className = 'plot-thumbnail';
        img.onclick = () => openPlotModal(path);
        plotGallery.appendChild(img);
    }
}

function enableDownloads(mseedFiles, plots) {
    // MSEED downloads
    const mseedList = document.getElementById('mseed-download-list');
    mseedList.innerHTML = '';
    
    mseedFiles.forEach(file => {
        const link = document.createElement('a');
        link.href = `/api/waveforms/download/${file.split('/').pop()}`;
        link.textContent = file.split('/').pop();
        link.download = true;
        link.className = 'download-link';
        mseedList.appendChild(link);
        mseedList.appendChild(document.createElement('br'));
    });
    
    // Plot downloads
    const plotList = document.getElementById('plot-download-list');
    plotList.innerHTML = '';
    
    for (const [name, path] of Object.entries(plots)) {
        const link = document.createElement('a');
        link.href = path;
        link.textContent = `${name}.png`;
        link.download = true;
        link.className = 'download-link';
        plotList.appendChild(link);
        plotList.appendChild(document.createElement('br'));
    }
}
    '''
    
    print(js_code)
    
    # Save to file
    with open('frontend_example.js', 'w') as f:
        f.write(js_code)
    
    print("\n✓ Saved frontend example to: frontend_example.js")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--frontend-example':
        example_frontend_javascript()
    else:
        try:
            example_complete_workflow()
        except requests.exceptions.ConnectionError:
            print("\n❌ Could not connect to API server.")
            print("   Make sure the FastAPI server is running:")
            print("   python app.py")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
