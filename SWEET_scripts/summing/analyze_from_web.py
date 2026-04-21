"""
Web-Compatible Waveform Analysis and Plotting
==============================================

This module analyzes synthetic waveforms and generates plots for the web interface.

Functions:
- analyze_waveforms(): Extract PGA, PGV, duration, peak times
- plot_waveform_overview(): Multi-station 3-component panel
- plot_pga_pgv_distance(): Ground motion vs distance plots
- plot_shakemap(): Spatial PGA map
- generate_all_plots(): Complete analysis suite
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.signal import detrend as sp_detrend
from scipy.interpolate import griddata
from obspy import read
import json
import base64
import io
from typing import Dict, List, Optional, Tuple
import sys

# Try to import plotly for interactive shakemap
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# Import helpers
sys.path.insert(0, os.path.dirname(__file__))
from helpers import haversine_distance, moment2magnitude


def file_to_base64_data_url(file_path: str) -> str:
    """Convert a file to a base64 data URL."""
    with open(file_path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('utf-8')
    
    # Determine MIME type
    ext = os.path.splitext(file_path)[1].lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.csv': 'text/csv',
        '.json': 'application/json'
    }
    mime_type = mime_types.get(ext, 'application/octet-stream')
    
    return f"data:{mime_type};base64,{data}"


def analyze_waveforms(
    mseed_file: str,
    stations: List[dict],
    hypo_lon: float,
    hypo_lat: float,
    hypo_depth: float
) -> pd.DataFrame:
    """
    Extract PGA, PGV, duration, and peak times from waveforms.
    
    Args:
        mseed_file: Path to MSEED file
        stations: List of station dictionaries
        hypo_lon, hypo_lat, hypo_depth: Hypocenter location
        
    Returns:
        DataFrame with columns: station, lat, lon, vs30, dist_km, 
                                pga_h, pgv_h, pga_e, pga_n, pga_z,
                                duration, peak_time
    """
    stream = read(mseed_file)
    
    # Create station lookup
    sta_map = {}
    for sta in stations:
        # Handle different naming conventions
        name = sta.get('station', sta.get('station_code', sta.get('name', '')))[:5]
        sta_map[name] = sta
    
    rows = []
    unique_stas = list({tr.stats.station for tr in stream})
    
    for sta in unique_stas:
        if sta not in sta_map:
            continue
        
        meta = sta_map[sta]
        
        # Get components
        tr_n = stream.select(station=sta, channel='HHN')
        tr_e = stream.select(station=sta, channel='HHE')
        tr_z = stream.select(station=sta, channel='HHZ')
        
        if not tr_n or not tr_e or not tr_z:
            continue
        
        dn, de, dz = tr_n[0].data, tr_e[0].data, tr_z[0].data
        dt = tr_n[0].stats.delta
        
        # PGA - horizontal vector peak
        pga_h = float(np.max(np.sqrt(dn**2 + de**2)))
        pga_e = float(np.max(np.abs(de)))
        pga_n = float(np.max(np.abs(dn)))
        pga_z = float(np.max(np.abs(dz)))
        
        # PGV - integrate to velocity
        dn_dt = sp_detrend(dn, type='linear')
        de_dt = sp_detrend(de, type='linear')
        dz_dt = sp_detrend(dz, type='linear')
        
        vel_n = np.cumsum(dn_dt) * dt
        vel_e = np.cumsum(de_dt) * dt
        vel_z = np.cumsum(dz_dt) * dt
        
        pgv_h = float(np.max(np.sqrt(vel_n**2 + vel_e**2)))
        pgv_e = float(np.max(np.abs(vel_e)))
        pgv_n = float(np.max(np.abs(vel_n)))
        pgv_z = float(np.max(np.abs(vel_z)))
        
        # Duration and peak time
        duration = float(tr_z[0].stats.endtime - tr_z[0].stats.starttime)
        peak_time = float(tr_z[0].times()[np.argmax(np.abs(dz))])
        
        # Distance calculations
        sta_lat = float(meta.get('latitude', 0))
        sta_lon = float(meta.get('longitude', 0))
        epi_km = haversine_distance(hypo_lon, hypo_lat, sta_lon, sta_lat)
        hypo_km = float(np.sqrt(epi_km**2 + hypo_depth**2))
        
        rows.append({
            'station': sta,
            'lat': sta_lat,
            'lon': sta_lon,
            'vs30': float(meta.get('vs30', 500)),
            'dist_epi_km': epi_km,
            'dist_hypo_km': hypo_km,
            'pga_h': pga_h,
            'pga_e': pga_e,
            'pga_n': pga_n,
            'pga_z': pga_z,
            'pgv_h': pgv_h,
            'pgv_e': pgv_e,
            'pgv_n': pgv_n,
            'pgv_z': pgv_z,
            'duration': duration,
            'peak_time': peak_time
        })
    
    return pd.DataFrame(rows)


def plot_waveform_overview(
    mseed_file: str,
    output_file: str,
    n_stations: int = 10,
    title: str = "Waveform Overview"
) -> List[str]:
    """
    Generate multi-station waveform overview plot.
    
    Args:
        mseed_file: Path to MSEED file
        output_file: Path to save plot
        n_stations: Number of stations to show
        title: Plot title
        
    Returns:
        List of station names shown
    """
    stream = read(mseed_file)
    all_stas = list({tr.stats.station for tr in stream})
    
    if not all_stas:
        return []
    
    chosen = np.random.choice(all_stas, min(n_stations, len(all_stas)), replace=False)
    
    fig, axes = plt.subplots(len(chosen), 3, figsize=(15, 2.4 * len(chosen)))
    if len(chosen) == 1:
        axes = axes.reshape(1, -1)
    
    for i, sta in enumerate(chosen):
        for j, comp in enumerate(['N', 'E', 'Z']):
            ax = axes[i, j]
            tr_sel = stream.select(station=sta, channel=f'HH{comp}')
            if tr_sel:
                d = tr_sel[0].data
                t = tr_sel[0].times()
                ax.plot(t, d, 'k-', lw=0.5)
                ax.set_xlim(0, t[-1])
                # Add peak amplitude annotation
                peak = np.max(np.abs(d))
                ax.text(0.98, 0.95, f'{peak:.2e}', transform=ax.transAxes,
                       ha='right', va='top', fontsize=7,
                       bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.7))
            ax.grid(alpha=0.25)
            if j == 0:
                ax.set_ylabel(f'{sta}', fontsize=9)
            if i == 0:
                ax.set_title(f'{comp}-component', fontsize=10, fontweight='bold')
            if i == len(chosen) - 1:
                ax.set_xlabel('Time (s)', fontsize=9)
            else:
                ax.set_xticklabels([])
    
    plt.suptitle(title, fontsize=12, fontweight='bold', y=1.001)
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    return list(chosen)


def plot_pga_pgv_distance(
    analysis_df: pd.DataFrame,
    output_dir: str,
    magnitude: float = None,
    hypo_depth: float = 10.0
) -> Tuple[str, str]:
    """
    Generate PGA and PGV vs distance plots.
    
    Args:
        analysis_df: DataFrame from analyze_waveforms()
        output_dir: Directory to save plots
        magnitude: Event magnitude (for GMPE comparison if available)
        hypo_depth: Hypocenter depth
        
    Returns:
        Tuple of (pga_file_path, pgv_file_path)
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # PGA plot
    fig, ax = plt.subplots(figsize=(12, 7))
    sc = ax.scatter(analysis_df['dist_hypo_km'], analysis_df['pga_h'],
                    c=analysis_df['vs30'], cmap='viridis',
                    s=50, alpha=0.7, edgecolors='k', linewidths=0.5)
    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label('VS30 (m/s)', fontsize=11)
    
    ax.set_xlabel('Hypocentral Distance (km)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Horizontal PGA √(N²+E²) (m/s²)', fontsize=11, fontweight='bold')
    ax.set_title(f'PGA vs Distance{f" (Mw {magnitude:.1f})" if magnitude else ""}',
                fontsize=12, fontweight='bold')
    ax.set_yscale('log')
    ax.grid(alpha=0.3)
    ax.set_xlim(left=0)
    
    plt.tight_layout()
    pga_file = os.path.join(output_dir, 'pga_vs_distance.png')
    plt.savefig(pga_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    # PGV plot
    fig, ax = plt.subplots(figsize=(12, 7))
    sc = ax.scatter(analysis_df['dist_hypo_km'], analysis_df['pgv_h'],
                    c=analysis_df['vs30'], cmap='viridis',
                    s=50, alpha=0.7, edgecolors='k', linewidths=0.5)
    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label('VS30 (m/s)', fontsize=11)
    
    ax.set_xlabel('Hypocentral Distance (km)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Horizontal PGV √(N²+E²) (m/s)', fontsize=11, fontweight='bold')
    ax.set_title(f'PGV vs Distance{f" (Mw {magnitude:.1f})" if magnitude else ""}',
                fontsize=12, fontweight='bold')
    ax.set_yscale('log')
    ax.grid(alpha=0.3)
    ax.set_xlim(left=0)
    
    plt.tight_layout()
    pgv_file = os.path.join(output_dir, 'pgv_vs_distance.png')
    plt.savefig(pgv_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    return pga_file, pgv_file


def plot_shakemap(
    analysis_df: pd.DataFrame,
    output_file: str,
    hypo_lon: float,
    hypo_lat: float,
    fault_outline: Optional[Tuple[float, float, float, float]] = None,
    title: str = "PGA Shakemap"
) -> str:
    """
    Generate spatial PGA shakemap overlaid on a map.
    
    Args:
        analysis_df: DataFrame from analyze_waveforms()
        output_file: Path to save plot
        hypo_lon, hypo_lat: Hypocenter location
        fault_outline: (lon_min, lon_max, lat_min, lat_max) or None
        title: Plot title
        
    Returns:
        Path to saved plot
    """
    if analysis_df.empty:
        return None
    
    # Convert PGA to %g
    pga_ms2 = analysis_df['pga_h'].values
    pga_pctg = pga_ms2 / 9.81 * 100.0
    
    if PLOTLY_AVAILABLE:
        # Use Plotly for interactive map-based shakemap
        # USGS-style PGA levels and colors
        pga_levels = [0, 0.046, 0.3, 2.76, 6.2, 11.5, 21.5, 40.1, 74.7, 139, 500]
        usgs_colors = ['#FFFFFF', '#BFCCFF', '#A0E6FF', '#80FFFF', '#7DF894',
                       '#FFFF00', '#FFAA00', '#FF8033', '#CC3300', '#880000']
        
        # Grid extent
        margin = 0.3
        lon_min = analysis_df['lon'].min() - margin
        lon_max = analysis_df['lon'].max() + margin
        lat_min = analysis_df['lat'].min() - margin
        lat_max = analysis_df['lat'].max() + margin
        
        # Interpolate PGA on a grid
        glon = np.linspace(lon_min, lon_max, 120)
        glat = np.linspace(lat_min, lat_max, 120)
        glo, gla = np.meshgrid(glon, glat)
        
        pts = analysis_df[['lon', 'lat']].values
        
        # Check for colinear data
        lat_range = analysis_df['lat'].max() - analysis_df['lat'].min()
        lon_range = analysis_df['lon'].max() - analysis_df['lon'].min()
        is_colinear = (lat_range < 0.01 or lon_range < 0.01)
        
        if is_colinear or len(analysis_df) < 4:
            grid = griddata(pts, pga_pctg, (glo, gla), method='nearest', fill_value=0.0)
        else:
            grid = griddata(pts, pga_pctg, (glo, gla), method='cubic', fill_value=0.0)
        
        grid = np.clip(grid, 0, 500)
        
        # Create plotly figure with mapbox
        fig = go.Figure()
        
        # Add contour layer
        fig.add_trace(go.Contour(
            x=glon,
            y=glat,
            z=grid,
            colorscale=list(zip(
                np.linspace(0, 1, len(usgs_colors)),
                usgs_colors
            )),
            contours=dict(
                start=0,
                end=500,
                size=20,
                showlabels=True,
                labelfont=dict(size=9, color='white')
            ),
            colorbar=dict(
                title="PGA (%g)",
                thickness=20,
                len=0.7,
                x=1.02
            ),
            hovertemplate='Lon: %{x:.4f}°<br>Lat: %{y:.4f}°<br>PGA: %{z:.2f} %g<extra></extra>',
            opacity=0.7,
            name='PGA Interpolation'
        ))
        
        # Add station markers
        fig.add_trace(go.Scatter(
            x=analysis_df['lon'],
            y=analysis_df['lat'],
            mode='markers',
            marker=dict(
                size=8,
                color=pga_pctg,
                colorscale=list(zip(
                    np.linspace(0, 1, len(usgs_colors)),
                    usgs_colors
                )),
                cmin=0,
                cmax=500,
                line=dict(color='black', width=1),
                showscale=False
            ),
            text=[f"Station: {row['station']}<br>PGA: {pga:.2f} %g" 
                  for _, row in analysis_df.iterrows() 
                  for pga in [row['pga_h'] / 9.81 * 100]],
            hoverinfo='text',
            name='Stations'
        ))
        
        # Add hypocenter
        fig.add_trace(go.Scatter(
            x=[hypo_lon],
            y=[hypo_lat],
            mode='markers',
            marker=dict(
                size=16,
                color='red',
                symbol='star',
                line=dict(color='black', width=2)
            ),
            text=[f'Hypocenter<br>Lon: {hypo_lon:.4f}°<br>Lat: {hypo_lat:.4f}°'],
            hoverinfo='text',
            name='Hypocenter'
        ))
        
        # Add fault outline if provided
        if fault_outline:
            flo_min, flo_max, fla_min, fla_max = fault_outline
            fig.add_trace(go.Scatter(
                x=[flo_min, flo_max, flo_max, flo_min, flo_min],
                y=[fla_min, fla_min, fla_max, fla_max, fla_min],
                mode='lines',
                line=dict(color='darkred', width=3, dash='dash'),
                hoverinfo='skip',
                name='Fault Extent'
            ))
        
        # Update layout to use mapbox
        center_lat = (lat_min + lat_max) / 2
        center_lon = (lon_min + lon_max) / 2
        
        fig.update_layout(
            title=dict(
                text=title,
                font=dict(size=16, color='#1f2937')
            ),
            mapbox=dict(
                style='open-street-map',
                center=dict(lat=center_lat, lon=center_lon),
                zoom=8
            ),
            showlegend=True,
            legend=dict(
                x=0.01,
                y=0.99,
                xanchor='left',
                yanchor='top',
                bgcolor='rgba(255, 255, 255, 0.9)',
                bordercolor='rgba(0, 0, 0, 0.2)',
                borderwidth=1
            ),
            width=1200,
            height=900,
            margin=dict(l=0, r=100, t=60, b=0)
        )
        
        # Convert to static image using kaleido if available
        try:
            img_bytes = fig.to_image(format='png', width=1200, height=900)
            with open(output_file, 'wb') as f:
                f.write(img_bytes)
            return output_file
        except Exception as e:
            print(f"[WARNING] Could not export Plotly figure to PNG: {e}")
            print("[INFO] Falling back to matplotlib shakemap")
            # Fall through to matplotlib version
    
    # Fallback: matplotlib version (original)
    # USGS-style PGA colormap
    pga_levels = [0, 0.046, 0.3, 2.76, 6.2, 11.5, 21.5, 40.1, 74.7, 139, 500]
    usgs_colors = ['#FFFFFF', '#BFCCFF', '#A0E6FF', '#80FFFF', '#7DF894',
                   '#FFFF00', '#FFAA00', '#FF8033', '#CC3300', '#880000']
    cmap = mcolors.ListedColormap(usgs_colors)
    norm = mcolors.BoundaryNorm(pga_levels, cmap.N)
    
    # Grid extent
    margin = 0.3
    lon_min = analysis_df['lon'].min() - margin
    lon_max = analysis_df['lon'].max() + margin
    lat_min = analysis_df['lat'].min() - margin
    lat_max = analysis_df['lat'].max() + margin
    
    # Interpolate PGA
    glon = np.linspace(lon_min, lon_max, 200)
    glat = np.linspace(lat_min, lat_max, 200)
    glo, gla = np.meshgrid(glon, glat)
    
    pts = analysis_df[['lon', 'lat']].values
    
    # Check for colinear data
    lat_range = analysis_df['lat'].max() - analysis_df['lat'].min()
    lon_range = analysis_df['lon'].max() - analysis_df['lon'].min()
    is_colinear = (lat_range < 0.01 or lon_range < 0.01)
    
    if is_colinear or len(analysis_df) < 4:
        grid = griddata(pts, pga_pctg, (glo, gla), method='nearest', fill_value=0.0)
    else:
        grid = griddata(pts, pga_pctg, (glo, gla), method='cubic', fill_value=0.0)
    
    grid = np.clip(grid, 0, 500)
    
    # Plot
    fig, ax = plt.subplots(figsize=(12, 10))
    
    cf = ax.contourf(glo, gla, grid, levels=pga_levels,
                     cmap=cmap, norm=norm, alpha=0.85, extend='max')
    
    sc = ax.scatter(analysis_df['lon'], analysis_df['lat'],
                    c=pga_pctg, cmap=cmap, norm=norm,
                    s=60, edgecolors='k', lw=0.7, zorder=8)
    
    # Hypocenter
    ax.scatter([hypo_lon], [hypo_lat], marker='*', color='red',
              s=400, edgecolors='k', lw=1, zorder=12, label='Hypocenter')
    
    # Fault outline
    if fault_outline:
        flo_min, flo_max, fla_min, fla_max = fault_outline
        rect_lons = [flo_min, flo_max, flo_max, flo_min, flo_min]
        rect_lats = [fla_min, fla_min, fla_max, fla_max, fla_min]
        ax.plot(rect_lons, rect_lats, 'k--', lw=2, alpha=0.9, label='Fault extent')
    
    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, orientation='vertical', shrink=0.75, pad=0.04)
    cbar.set_label('PGA (%g)', fontsize=11, fontweight='bold')
    cbar.set_ticks(pga_levels[:-1])
    cbar.set_ticklabels([str(v) for v in pga_levels[:-1]], fontsize=8)
    
    # Labels and grid
    ax.set_xlabel('Longitude', fontsize=11, fontweight='bold')
    ax.set_ylabel('Latitude', fontsize=11, fontweight='bold')
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.grid(alpha=0.3, lw=0.5)
    ax.legend(loc='upper left', fontsize=9, framealpha=0.9)
    
    # Statistics
    stats_txt = (f"Stations: {len(analysis_df)}\n"
                f"Max PGA: {pga_pctg.max():.2f} %g\n"
                f"Mean PGA: {pga_pctg.mean():.2f} %g")
    ax.text(0.98, 0.02, stats_txt, transform=ax.transAxes,
           fontsize=9, ha='right', va='bottom',
           bbox=dict(boxstyle='round', fc='white', alpha=0.9))
    
    plt.title(title, fontsize=13, fontweight='bold', pad=12)
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    return output_file


def generate_all_plots(
    mseed_file: str,
    stations: List[dict],
    subsources: List[dict],
    output_dir: str,
    title_prefix: str = "Synthetic Event"
) -> Dict:
    """
    Generate complete analysis suite.
    
    Args:
        mseed_file: Path to MSEED file
        stations: List of station dictionaries
        subsources: List of subsource dictionaries (for fault outline)
        output_dir: Directory to save plots
        title_prefix: Prefix for plot titles
        
    Returns:
        Dictionary with paths and statistics
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Calculate hypocenter (mean of subsources)
    if subsources:
        hypo_lon = np.mean([s['centroid_lon'] for s in subsources])
        hypo_lat = np.mean([s['centroid_lat'] for s in subsources])
        hypo_depth = np.mean([s['centroid_depth'] for s in subsources])
        magnitude = np.mean([s.get('magnitude', moment2magnitude(s['sf_moment'])) 
                            for s in subsources])
        
        # Fault outline
        lons = [s['centroid_lon'] for s in subsources]
        lats = [s['centroid_lat'] for s in subsources]
        fault_outline = (min(lons), max(lons), min(lats), max(lats))
    else:
        hypo_lon, hypo_lat, hypo_depth = 0, 0, 10
        magnitude = None
        fault_outline = None
    
    # Analyze waveforms
    analysis_df = analyze_waveforms(mseed_file, stations, hypo_lon, hypo_lat, hypo_depth)
    
    # Generate plots
    np.random.seed(42)
    chosen_stations = plot_waveform_overview(
        mseed_file,
        os.path.join(output_dir, 'waveform_overview.png'),
        n_stations=10,
        title=f"{title_prefix} - Waveform Overview"
    )
    
    pga_file, pgv_file = plot_pga_pgv_distance(
        analysis_df,
        output_dir,
        magnitude=magnitude,
        hypo_depth=hypo_depth
    )
    
    shakemap_file = plot_shakemap(
        analysis_df,
        os.path.join(output_dir, 'shakemap.png'),
        hypo_lon, hypo_lat,
        fault_outline=fault_outline,
        title=f"{title_prefix} - PGA Shakemap"
    )
    
    # Export statistics as JSON
    stats = {
        'num_stations': len(analysis_df),
        'pga_max': float(analysis_df['pga_h'].max()),
        'pga_mean': float(analysis_df['pga_h'].mean()),
        'pga_median': float(analysis_df['pga_h'].median()),
        'pgv_max': float(analysis_df['pgv_h'].max()),
        'pgv_mean': float(analysis_df['pgv_h'].mean()),
        'pgv_median': float(analysis_df['pgv_h'].median()),
        'distance_min': float(analysis_df['dist_hypo_km'].min()),
        'distance_max': float(analysis_df['dist_hypo_km'].max()),
        'hypocenter': {
            'longitude': hypo_lon,
            'latitude': hypo_lat,
            'depth': hypo_depth
        },
        'magnitude': magnitude
    }
    
    stats_file = os.path.join(output_dir, 'statistics.json')
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    
    # Export detailed CSV
    csv_file = os.path.join(output_dir, 'waveform_analysis.csv')
    analysis_df.to_csv(csv_file, index=False)
    
    # Also create a simple statistics CSV
    stats_csv_file = os.path.join(output_dir, 'statistics.csv')
    stats_df = pd.DataFrame([stats])
    stats_df.to_csv(stats_csv_file, index=False)
    
    # Convert all files to base64 data URLs
    waveform_overview_file = os.path.join(output_dir, 'waveform_overview.png')
    
    return {
        'plots': {
            'waveform_overview': file_to_base64_data_url(waveform_overview_file),
            'pga_vs_distance': file_to_base64_data_url(pga_file),
            'pgv_vs_distance': file_to_base64_data_url(pgv_file),
            'shakemap': file_to_base64_data_url(shakemap_file)
        },
        'data': {
            'statistics_csv': file_to_base64_data_url(stats_csv_file),
            'detailed_csv': file_to_base64_data_url(csv_file)
        },
        'statistics': stats,
        'chosen_stations': chosen_stations
    }
