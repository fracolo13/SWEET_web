"""
Example: Complete waveform summation workflow with SWEET web data.

This script demonstrates:
1. Loading fault data from website output or GeoJSON
2. Loading/creating station list
3. Summing waveforms
4. Analyzing results
"""

import json
import sys
import os
import numpy as np
from pathlib import Path

# Add summing directory to path
summing_dir = Path(__file__).parent
sys.path.insert(0, str(summing_dir))

from sum_from_web_input import (
    load_subsources_from_json,
    load_stations_from_json,
    sum_waveforms
)


def example_1_from_json_files():
    """
    Example 1: Load data from JSON files and sum waveforms.
    """
    print("=" * 70)
    print("Example 1: From JSON Files")
    print("=" * 70)
    
    # Input files (create these from web interface)
    subsources_file = "example_subsources.json"
    stations_file = "example_stations.json"
    templates_dir = "/Users/francescoacolosimo/Desktop/SED/envelopes_sweet/Data/synthetics/synthetics_filtered"
    output_dir = "example_output_waveforms"
    
    # Check if files exist
    if not os.path.exists(subsources_file):
        print(f"ℹ️  {subsources_file} not found - creating example file")
        create_example_subsources(subsources_file)
    
    if not os.path.exists(stations_file):
        print(f"ℹ️  {stations_file} not found - creating example file")
        create_example_stations(stations_file)
    
    # Load data
    subsources = load_subsources_from_json(subsources_file)
    stations = load_stations_from_json(stations_file)
    
    # Sum waveforms
    stats = sum_waveforms(
        subsources=subsources,
        stations=stations,
        templates_dir=templates_dir,
        output_dir=output_dir,
        n_realizations=1,
        sampling_rate=100.0,
        moment_scale=False,  # Templates are GMPE-calibrated
        amplitude_scale=1.0,
        min_template_dist_km=10.0
    )
    
    print("\n✅ Waveform summation complete!")
    print(f"   Subsources:                {stats['num_subsources']}")
    print(f"   Stations:                  {stats['num_stations']}")
    print(f"   Stations with templates:   {len(stats['stations_ok'])}")
    print(f"   Missing templates:         {len(stats['stations_missing'])}")
    print(f"   Output directory:          {output_dir}")


def example_2_from_web_api_response():
    """
    Example 2: Load data from web API response format and sum waveforms.
    """
    print("=" * 70)
    print("Example 2: From Web API Response")
    print("=" * 70)
    
    # Simulate data from web API
    # This would come from /api/geojson/group endpoint
    web_response = {
        "subsources": {
            "grouped_patches": [
                {
                    "centroid_lon": 7.5,
                    "centroid_lat": 46.0,
                    "centroid_depth": 10.0,
                    "sf_moment": 5.62e17,  # Mw 6.0
                    "trup": 2.5,
                    "rise": 1.0,
                    "slip": 1.5,
                    "magnitude": 6.0
                },
                {
                    "centroid_lon": 7.52,
                    "centroid_lat": 46.02,
                    "centroid_depth": 10.5,
                    "sf_moment": 5.62e17,
                    "trup": 3.0,
                    "rise": 1.0,
                    "slip": 1.5,
                    "magnitude": 6.0
                }
            ]
        }
    }
    
    # Station data from web interface
    stations_data = [
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
        }
    ]
    
    templates_dir = "/Users/francescoacolosimo/Desktop/SED/envelopes_sweet/Data/synthetics/synthetics_filtered"
    output_dir = "web_api_waveforms"
    
    # Load data (handles API response format)
    subsources = load_subsources_from_json(web_response['subsources'])
    stations = load_stations_from_json(stations_data)
    
    # Sum waveforms
    stats = sum_waveforms(
        subsources=subsources,
        stations=stations,
        templates_dir=templates_dir,
        output_dir=output_dir,
        n_realizations=1
    )
    
    print("\n✅ Waveform summation complete!")
    print(f"   Output directory: {output_dir}")


def example_3_analyze_results():
    """
    Example 3: Read and analyze the output waveforms.
    """
    print("=" * 70)
    print("Example 3: Analyze Results")
    print("=" * 70)
    
    from obspy import read
    
    mseed_file = "example_output_waveforms/summed_realization_01.mseed"
    
    if not os.path.exists(mseed_file):
        print(f"⚠️  {mseed_file} not found - run example_1 first")
        return
    
    # Read MSEED
    st = read(mseed_file)
    
    print(f"\nLoaded {len(st)} traces from {mseed_file}")
    print("\nTrace information:")
    print("-" * 70)
    
    for tr in st[:5]:  # Show first 5 traces
        # Calculate PGA and PGV
        pga = np.max(np.abs(tr.data))  # m/s²
        vel = np.cumsum(tr.data) / tr.stats.sampling_rate  # integrate to velocity
        pgv = np.max(np.abs(vel))  # m/s
        
        print(f"{tr.stats.network}.{tr.stats.station}.{tr.stats.channel}")
        print(f"  Duration:  {tr.stats.endtime - tr.stats.starttime:.1f} s")
        print(f"  Samples:   {tr.stats.npts}")
        print(f"  PGA:       {pga:.4f} m/s²")
        print(f"  PGV:       {pgv:.6f} m/s")
        if hasattr(tr.stats, 'distance'):
            print(f"  Distance:  {tr.stats.distance:.1f} km")
        if hasattr(tr.stats, 'vs30'):
            print(f"  VS30:      {tr.stats.vs30:.0f} m/s")
        print()
    
    if len(st) > 5:
        print(f"... and {len(st) - 5} more traces")
    
    # Calculate overall statistics
    print("\nOverall Statistics:")
    print("-" * 70)
    all_pgas = [np.max(np.abs(tr.data)) for tr in st]
    print(f"PGA range:    {min(all_pgas):.4f} - {max(all_pgas):.4f} m/s²")
    print(f"PGA median:   {np.median(all_pgas):.4f} m/s²")


def create_example_subsources(filename):
    """Create example subsources JSON file."""
    subsources = [
        {
            "centroid_lon": 7.5,
            "centroid_lat": 46.0,
            "centroid_depth": 10.0,
            "sf_moment": 5.62e17,  # Mw 6.0
            "trup": 2.0,
            "rise": 1.0,
            "slip": 1.5
        },
        {
            "centroid_lon": 7.52,
            "centroid_lat": 46.02,
            "centroid_depth": 10.5,
            "sf_moment": 5.62e17,
            "trup": 2.5,
            "rise": 1.0,
            "slip": 1.5
        },
        {
            "centroid_lon": 7.48,
            "centroid_lat": 45.98,
            "centroid_depth": 9.5,
            "sf_moment": 5.62e17,
            "trup": 3.0,
            "rise": 1.0,
            "slip": 1.5
        }
    ]
    
    with open(filename, 'w') as f:
        json.dump(subsources, f, indent=2)
    
    print(f"Created {filename}")


def create_example_stations(filename):
    """Create example stations JSON file."""
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
        }
    ]
    
    with open(filename, 'w') as f:
        json.dump(stations, f, indent=2)
    
    print(f"Created {filename}")


def main():
    """Run examples."""
    print("\n" + "=" * 70)
    print("SWEET Waveform Summation Examples")
    print("=" * 70 + "\n")
    
    # Run examples
    try:
        example_1_from_json_files()
    except Exception as e:
        print(f"\n❌ Example 1 failed: {e}")
    
    print("\n" + "=" * 70 + "\n")
    
    try:
        example_2_from_web_api_response()
    except Exception as e:
        print(f"\n❌ Example 2 failed: {e}")
    
    print("\n" + "=" * 70 + "\n")
    
    try:
        example_3_analyze_results()
    except Exception as e:
        print(f"\n❌ Example 3 failed: {e}")


if __name__ == '__main__':
    main()
