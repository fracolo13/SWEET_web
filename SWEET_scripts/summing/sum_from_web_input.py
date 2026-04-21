"""
Web-Compatible Waveform Summation
==================================

This script sums synthetic waveforms from fault and station data provided
by the SWEET web interface.

Input format:
    - Subsources: JSON with centroid_lon, centroid_lat, centroid_depth, 
                  sf_moment, trup fields
    - Stations: JSON with station_code/name, latitude, longitude, vs30 fields
    - Template library: preprocessed templates directory

The script:
    1. Loads subsource and station data from JSON
    2. For each (subsource × station × component) combination:
       - Selects the closest preprocessed template with matching
         VS30, subsource magnitude and source-to-station distance
       - Time-shifts the template by the subsource rupture time t_rup
    3. Sums all subsource contributions for each station channel
    4. Writes one MSEED file per realisation

Usage:
    python sum_from_web_input.py --subsources subsources.json \\
                                  --stations stations.json \\
                                  --output output_dir
"""

import os
import sys
import json
import argparse
import numpy as np
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from obspy import Stream, Trace
from obspy.core import UTCDateTime

# Import shared helpers
sys.path.insert(0, os.path.dirname(__file__))
from helpers import (
    moment2magnitude, magnitude2moment,
    haversine_distance,
    find_closest_magnitude, find_closest_vs30, find_closest_distance,
    get_available_templates_info, load_template,
)


def _process_pair(args):
    """
    Process one (subsource, station) pair and return trace data.
    Designed to be called from a ThreadPoolExecutor.
    """
    (ss, ss_idx, sta,
     avail_mags, avail_vs30, avail_dists,
     templates_dir, real_idx, min_template_dist_km,
     moment_scale, amplitude_scale, sampling_rate) = args

    ss_mag   = ss['magnitude']
    ss_trup  = ss['trup']
    ss_lon   = ss['centroid_lon']
    ss_lat   = ss['centroid_lat']

    tmpl_mag = find_closest_magnitude(avail_mags, ss_mag)

    sta_code = sta['station_code']
    sta_name = sta['station']
    net_code = sta['network']
    sta_lat  = sta['latitude']
    sta_lon  = sta['longitude']
    sta_vs30 = sta['vs30']

    dist_km  = haversine_distance(ss_lon, ss_lat, sta_lon, sta_lat)
    tmpl_vs30 = find_closest_vs30(avail_vs30, sta_vs30)
    tmpl_dist = max(dist_km, min_template_dist_km)
    tmpl_dist = find_closest_distance(avail_dists, tmpl_dist)

    envelope = load_template(templates_dir, tmpl_vs30, tmpl_mag, tmpl_dist, real_idx)

    if envelope is None:
        return None, sta_code, ss_idx, dist_km

    if moment_scale:
        m0_sub  = float(ss['sf_moment'])
        m0_tmpl = magnitude2moment(tmpl_mag)
        scale   = (m0_sub / m0_tmpl) * amplitude_scale
    else:
        scale = amplitude_scale

    traces = []
    for comp_i, comp_lbl in enumerate(['E', 'N', 'Z']):
        tr = Trace()
        tr.data = envelope[comp_i, :].copy() * scale
        tr.stats.network        = str(net_code)[:2]
        tr.stats.station        = str(sta_name)[:5]
        tr.stats.location       = '00'
        tr.stats.channel        = f'HH{comp_lbl}'
        tr.stats.sampling_rate  = sampling_rate
        tr.stats.starttime      = UTCDateTime(0) + float(ss_trup)
        tr.stats.distance       = dist_km
        tr.stats.vs30           = float(sta_vs30)
        tr.stats.full_station_code = sta_code
        traces.append(((str(sta_name)[:5], f'HH{comp_lbl}'), tr))

    return traces, sta_code, ss_idx, dist_km


def load_subsources_from_json(subsources_data):
    """
    Load subsources from JSON data (dict or file path).
    
    Expected format:
        [
            {
                "centroid_lon": float,
                "centroid_lat": float,
                "centroid_depth": float,
                "sf_moment": float,
                "trup": float,
                ...
            },
            ...
        ]
    Or:
        {
            "grouped_patches": [...],
            ...
        }
    
    Args:
        subsources_data: Dictionary or path to JSON file
        
    Returns:
        List of subsource dictionaries with computed magnitude
    """
    if isinstance(subsources_data, str):
        with open(subsources_data, 'r') as f:
            data = json.load(f)
    else:
        data = subsources_data
    
    # Handle different response formats
    if isinstance(data, dict):
        if 'grouped_patches' in data:
            subsources = data['grouped_patches']
        elif 'subsources' in data and 'grouped_patches' in data['subsources']:
            subsources = data['subsources']['grouped_patches']
        else:
            raise ValueError("Unknown subsource JSON format")
    elif isinstance(data, list):
        subsources = data
    else:
        raise ValueError("Subsources must be a list or dict")
    
    # Add computed magnitude if not present
    for ss in subsources:
        if 'magnitude' not in ss:
            ss['magnitude'] = moment2magnitude(ss['sf_moment'])
    
    print(f"Loaded {len(subsources)} subsources")
    return subsources


def load_stations_from_json(stations_data):
    """
    Load stations from JSON data (dict or file path).
    
    Expected format:
        [
            {
                "station_code": str or "name": str,
                "latitude": float,
                "longitude": float,
                "vs30": float (optional, defaults to 500),
                "network": str (optional, defaults to "XX"),
                ...
            },
            ...
        ]
    
    Args:
        stations_data: Dictionary or path to JSON file
        
    Returns:
        List of station dictionaries
    """
    if isinstance(stations_data, str):
        with open(stations_data, 'r') as f:
            data = json.load(f)
    else:
        data = stations_data
    
    # Handle different response formats
    if isinstance(data, dict):
        if 'stations' in data:
            stations = data['stations']
        else:
            raise ValueError("Unknown station JSON format")
    elif isinstance(data, list):
        stations = data
    else:
        raise ValueError("Stations must be a list or dict")
    
    # Normalize station format
    for sta in stations:
        # Ensure station_code exists
        if 'station_code' not in sta:
            if 'name' in sta:
                sta['station_code'] = sta['name']
            elif 'id' in sta:
                sta['station_code'] = sta['id']
            else:
                raise ValueError("Station must have station_code, name, or id")
        
        # Ensure station name exists
        if 'station' not in sta:
            sta['station'] = sta['station_code'][:5]
        
        # Set defaults
        if 'vs30' not in sta:
            sta['vs30'] = 500.0
        if 'network' not in sta:
            sta['network'] = 'XX'
    
    print(f"Loaded {len(stations)} stations")
    return stations


def sum_waveforms(
    subsources,
    stations,
    templates_dir,
    output_dir,
    n_realizations=1,
    sampling_rate=100.0,
    moment_scale=False,
    amplitude_scale=1.0,
    min_template_dist_km=10.0
):
    """
    Sum synthetic waveforms for all subsource-station pairs.
    
    Args:
        subsources: List of subsource dictionaries
        stations: List of station dictionaries
        templates_dir: Path to preprocessed templates directory
        output_dir: Output directory for MSEED files
        n_realizations: Number of realizations to generate
        sampling_rate: Sampling rate in Hz
        moment_scale: Apply moment ratio scaling (EGF approach)
        amplitude_scale: Additional global amplitude scaling factor
        min_template_dist_km: Minimum template distance (clamp near-field)
        
    Returns:
        Dictionary with processing statistics
    """
    import os
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Log configuration
    print('\n' + '='*80)
    print('WAVEFORM SUMMATION STARTING')
    print('='*80)
    print(f'Templates directory: {templates_dir}')
    print(f'Output directory: {output_dir}')
    print(f'Number of subsources: {len(subsources)}')
    print(f'Number of stations: {len(stations)}')
    print(f'Number of realizations: {n_realizations}')
    
    # Check S3 mode
    use_s3 = os.getenv('USE_S3_TEMPLATES', 'false').lower() == 'true'
    print(f'USE_S3_TEMPLATES environment variable: {os.getenv("USE_S3_TEMPLATES", "not set")}')
    print(f'S3 mode active: {use_s3}')
    
    if use_s3:
        print(f'S3_BUCKET_NAME: {os.getenv("S3_BUCKET_NAME", "not set")}')
        print(f'S3_TEMPLATES_PREFIX: {os.getenv("S3_TEMPLATES_PREFIX", "not set")}')
    print('='*80)
    
    # Scan available templates
    print('\nScanning preprocessed templates...')
    tmpl_info = get_available_templates_info(templates_dir)
    avail_mags = tmpl_info['magnitudes']
    avail_vs30 = tmpl_info['vs30']
    avail_dists = tmpl_info['distances']
    
    print(f'  Magnitudes:  {avail_mags}')
    print(f'  VS30 values: {avail_vs30}')
    print(f'  Distance bins: {len(avail_dists)} '
          f'({min(avail_dists) if avail_dists else "n/a"} - '
          f'{max(avail_dists) if avail_dists else "n/a"} km)')
    
    if not avail_mags:
        error_msg = f'No preprocessed templates found in {templates_dir}'
        if use_s3:
            error_msg += '\n  Check S3 configuration: bucket name, prefix, and credentials'
        else:
            error_msg += '\n  Templates directory does not exist or is empty'
            error_msg += f'\n  Set USE_S3_TEMPLATES=true to use S3 storage'
        raise ValueError(error_msg)
    
    stats = {
        'num_subsources': len(subsources),
        'num_stations': len(stations),
        'stations_ok': set(),
        'stations_missing': set(),
        'realizations_generated': 0
    }
    
    # Realization loop
    n_workers = min(32, (os.cpu_count() or 1) * 4)
    print(f'Using {n_workers} worker threads for template loading')

    for real_idx in range(n_realizations):
        print(f'\n── Realisation {real_idx + 1:02d}/{n_realizations} ──')

        # Build flat list of (subsource, station) tasks
        args_list = [
            (ss, ss_idx, sta,
             avail_mags, avail_vs30, avail_dists,
             templates_dir, real_idx, min_template_dist_km,
             moment_scale, amplitude_scale, sampling_rate)
            for ss_idx, ss in enumerate(subsources)
            for sta in stations
        ]

        traces_dict = defaultdict(list)
        templates_attempted = len(args_list)
        templates_loaded = 0
        templates_failed = 0

        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            for result in executor.map(_process_pair, args_list):
                result_traces, sta_code, ss_idx, dist_km = result
                if result_traces is None:
                    templates_failed += 1
                    if ss_idx == 0:
                        stats['stations_missing'].add(sta_code)
                else:
                    templates_loaded += 1
                    if ss_idx == 0:
                        stats['stations_ok'].add(sta_code)
                    for key, tr in result_traces:
                        traces_dict[key].append(tr)

        print(f'\n[SUMMARY] Realization {real_idx + 1}:')
        print(f'  Templates attempted: {templates_attempted}')
        print(f'  Templates loaded: {templates_loaded}')
        print(f'  Templates failed: {templates_failed}')
        print(f'  Templates found for {len(stats["stations_ok"])} stations, '
              f'missing for {len(stats["stations_missing"])} stations.')
        print(f'  Total traces collected: {sum(len(trs) for trs in traces_dict.values())}')
        print(f'  Unique (station, channel) pairs: {len(traces_dict)}')
        
        if not traces_dict:
            print('[ERROR] No traces collected! Check template loading.')
            print(f'[ERROR] Attempted {templates_attempted} template loads, all failed.')
            print(f'[ERROR] Templates loaded successfully: {templates_loaded}')
            print(f'[ERROR] Templates failed to load: {templates_failed}')
            
            # Provide specific guidance based on mode
            use_s3 = os.getenv('USE_S3_TEMPLATES', 'false').lower() == 'true'
            if use_s3:
                print('[ERROR] S3 mode is ENABLED. Check:')
                print(f'[ERROR]   - S3_BUCKET_NAME: {os.getenv("S3_BUCKET_NAME", "NOT SET")}')
                print(f'[ERROR]   - S3_TEMPLATES_PREFIX: {os.getenv("S3_TEMPLATES_PREFIX", "NOT SET")}')
                print('[ERROR]   - AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)')
                print('[ERROR]   - boto3 is installed')
                print('[ERROR]   - Templates exist in S3 bucket')
            else:
                print('[ERROR] S3 mode is DISABLED (using local filesystem)')
                print(f'[ERROR]   - Templates directory: {templates_dir}')
                print(f'[ERROR]   - Directory exists: {os.path.isdir(templates_dir)}')
                print('[ERROR]   - Set USE_S3_TEMPLATES=true to use S3')
            
            raise ValueError(f"No waveforms generated. Check that templates exist for VS30={avail_vs30}, Mag={avail_mags}, Dist={avail_dists}")
        
        # Sum contributions for every (station, channel)
        summed_traces = []
        for (sta_name, channel), trs in traces_dict.items():
            t0 = min(tr.stats.starttime for tr in trs)
            tend = max(tr.stats.endtime for tr in trs)
            npts = int((tend - t0) * sampling_rate) + 1
            
            buf = np.zeros(npts)
            for tr in trs:
                off = int((tr.stats.starttime - t0) * sampling_rate)
                buf[off: off + len(tr.data)] += tr.data
            
            out_tr = trs[0].copy()
            out_tr.data = buf
            out_tr.stats.starttime = t0
            out_tr.stats.npts = npts
            summed_traces.append(out_tr)
        
        # Write MSEED
        stream = Stream(traces=summed_traces)
        out_file = os.path.join(output_dir,
                               f'summed_realization_{real_idx + 1:02d}.mseed')
        stream.write(out_file, format='MSEED')
        print(f'  Saved ({len(stream)} traces) → {out_file}')
        
        stats['realizations_generated'] += 1
    
    return stats


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description='Sum synthetic waveforms from web interface data'
    )
    
    parser.add_argument('--subsources', required=True,
                       help='Path to subsources JSON file or JSON string')
    parser.add_argument('--stations', required=True,
                       help='Path to stations JSON file or JSON string')
    parser.add_argument('--templates-dir', required=True,
                       help='Path to preprocessed templates directory')
    parser.add_argument('--output', required=True,
                       help='Output directory for MSEED files')
    parser.add_argument('--n-realizations', type=int, default=1,
                       help='Number of realizations (default: 1)')
    parser.add_argument('--sampling-rate', type=float, default=100.0,
                       help='Sampling rate in Hz (default: 100)')
    parser.add_argument('--moment-scale', action='store_true',
                       help='Apply moment ratio scaling (EGF approach)')
    parser.add_argument('--amplitude-scale', type=float, default=1.0,
                       help='Additional amplitude scaling factor (default: 1.0)')
    parser.add_argument('--min-template-dist', type=float, default=10.0,
                       help='Minimum template distance in km (default: 10)')
    
    args = parser.parse_args()
    
    print('=' * 70)
    print('WEB-COMPATIBLE WAVEFORM SUMMATION')
    print('=' * 70)
    
    # Load data
    subsources = load_subsources_from_json(args.subsources)
    stations = load_stations_from_json(args.stations)
    
    # Sum waveforms
    stats = sum_waveforms(
        subsources=subsources,
        stations=stations,
        templates_dir=args.templates_dir,
        output_dir=args.output,
        n_realizations=args.n_realizations,
        sampling_rate=args.sampling_rate,
        moment_scale=args.moment_scale,
        amplitude_scale=args.amplitude_scale,
        min_template_dist_km=args.min_template_dist
    )
    
    print('\n' + '=' * 70)
    print('SUMMATION COMPLETE')
    print(f'Subsources: {stats["num_subsources"]}')
    print(f'Stations: {stats["num_stations"]}')
    print(f'Stations with templates: {len(stats["stations_ok"])}')
    print(f'Stations missing templates: {len(stats["stations_missing"])}')
    print(f'Realizations generated: {stats["realizations_generated"]}')
    print(f'Output: {args.output}')
    print('=' * 70)


if __name__ == '__main__':
    main()
