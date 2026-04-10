"""
Bulk Synthetic Waveform Evaluation  –  M6.0 to M8.0
=====================================================

Stage 3 (visualisation) of the templates_fix workflow.

Run AFTER 01_sum_bulk_synthetics.py.

For each magnitude the script generates the following figures inside
    <DATA_ROOT>/<event_name>/results/

  1. summed_synthetics_overview.png       – N_STATIONS×3-component grid
  2. summed_synthetics_detail.png         – one representative station
  3. summed_synthetics_comparison.png     – stacked normalised traces
  4. summed_synthetics_statistics.png     – peak-amp / duration histograms
  5. pga_vs_distance.png                  – horiz. PGA vs distance (GMPE overlay)
  6. pgv_vs_distance.png                  – horiz. PGV vs distance (GMPE overlay)
  7. shakemap.png                         – PGA spatial map with fault outline
"""

import os, sys, warnings
import numpy as np
from scipy.signal import detrend as sp_detrend
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.interpolate import griddata
from obspy import read
warnings.filterwarnings('ignore')

# ── Import shared helpers ──────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from helpers import haversine_distance, moment2magnitude

# ── Optional: OpenQuake GMPE ──────────────────────────────────────────────────
OPENQUAKE_AVAILABLE = False
try:
    from openquake.hazardlib.gsim.boore_atkinson_2008 import BooreAtkinson2008
    from openquake.hazardlib import imt, const
    from openquake.hazardlib.contexts import RuptureContext, SitesContext, DistancesContext
    OPENQUAKE_AVAILABLE = True
    print("OpenQuake available – BA2008 GMPE predictions will be shown.")
except ImportError as exc:
    print(f"OpenQuake not available ({exc}) – GMPE curves will be skipped.")

# ── Optional: Cartopy (shakemap) ──────────────────────────────────────────────
CARTOPY_AVAILABLE = False
try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    CARTOPY_AVAILABLE = True
except ImportError:
    print("Cartopy not available – shakemap will use plain Matplotlib axes.")


# =============================================================================
# ▶▶  USER-EDITABLE PARAMETERS
# =============================================================================

# Magnitude sweep  (must match 00 and 01 scripts)
MAG_MIN   = 6.0
MAG_MAX   = 8.0
MAG_STEP  = 0.1

EVENT_NAME_PREFIX = 'SyntheticEvent_M'

# Data root
DATA_ROOT = '/Users/francescoacolosimo/Desktop/SED/envelopes_sweet/Data'

# Hypocentre (must match 00_generate_bulk_faults.py)
HYPO_LAT   = 24.0
HYPO_LON   = 120.0
HYPO_DEPTH = 10.0

# Which realisation to use for waveform / shakemap panels (1-based)
REFERENCE_REALIZATION = 1

# Maximum number of random stations shown in waveform overview
N_STATIONS = 10

# Maximum distance for PGA/PGV distance plots [km]
MAX_DISTANCE = 300.0

# GMPE parameters (Boore & Atkinson 2008)
GMPE_RAKE  = 0.0    # strike-slip
GMPE_DIP   = 90.0
GMPE_ZTOR  = 0.0
GMPE_VS30_REF = 760.0   # reference VS30 for GMPE curve

# =============================================================================
# END OF USER PARAMETERS
# =============================================================================


# ── GMPE helper ───────────────────────────────────────────────────────────────
def _gmpe_curve(mag, depth, imt_obj, dist_km):
    """Return (median, upper_1sigma, lower_1sigma) arrays in physical units.

    For PGA  → m/s²   (BA2008 returns ln(PGA/g), multiply by 9.81)
    For PGV  → m/s    (BA2008 returns ln(PGV[cm/s]), divide by 100)
    Returns None on any failure.
    """
    if not OPENQUAKE_AVAILABLE:
        return None
    try:
        gmpe  = BooreAtkinson2008()
        d_arr = np.asarray(dist_km, dtype=float)
        n     = len(d_arr)

        rctx = RuptureContext()
        rctx.mag        = float(mag)
        rctx.rake       = GMPE_RAKE
        rctx.dip        = GMPE_DIP
        rctx.ztor       = float(GMPE_ZTOR)
        rctx.hypo_depth = float(depth)
        rctx.width      = 10.0 ** (-1.01 + 0.32 * float(mag))   # Coppersmith W

        sctx = SitesContext()
        sctx.sids        = np.arange(n)
        sctx.vs30        = np.full(n, GMPE_VS30_REF)
        sctx.vs30measured = np.full(n, True)
        sctx.z2pt5       = np.full(n, 1.0)

        dctx = DistancesContext()
        dctx.rjb  = d_arr
        dctx.rrup = d_arr
        dctx.rx   = np.zeros(n)
        dctx.ry0  = np.zeros(n)

        ln_mean, [sigma] = gmpe.get_mean_and_stddevs(
            sctx, rctx, dctx, imt_obj, [const.StdDev.TOTAL])

        # Use str(imt_obj) – canonical OQ method, works across all versions
        imt_name = str(imt_obj)
        if imt_name == 'PGA':
            factor = 9.81          # g → m/s²
        else:                      # PGV: OQ returns cm/s → m/s
            factor = 0.01
        med = np.exp(ln_mean) * factor
        up  = np.exp(ln_mean + sigma) * factor
        lo  = np.exp(ln_mean - sigma) * factor
        return med, up, lo
    except Exception as exc:
        import traceback
        print(f"    [GMPE warning] {exc}")
        traceback.print_exc()
        return None


def _gmpe_curve_rjb(mag, depth, imt_obj, rjb_arr, rrup_arr):
    """
    Like _gmpe_curve but accepts separate rjb and rrup arrays.
    rjb  = epicentral distance (Joyner-Boore, surface projection)
    rrup = hypocentral distance (closest to fault, here = hypocentral)
    This is the physically correct pairing for a point source.
    """
    if not OPENQUAKE_AVAILABLE:
        return None
    try:
        gmpe  = BooreAtkinson2008()
        rjb   = np.asarray(rjb_arr,  dtype=float)
        rrup  = np.asarray(rrup_arr, dtype=float)
        n     = len(rjb)

        rctx = RuptureContext()
        rctx.mag        = float(mag)
        rctx.rake       = GMPE_RAKE
        rctx.dip        = GMPE_DIP
        rctx.ztor       = float(GMPE_ZTOR)
        rctx.hypo_depth = float(depth)
        rctx.width      = 10.0 ** (-1.01 + 0.32 * float(mag))

        sctx = SitesContext()
        sctx.sids         = np.arange(n)
        sctx.vs30         = np.full(n, GMPE_VS30_REF)
        sctx.vs30measured = np.full(n, True)
        sctx.z2pt5        = np.full(n, 1.0)

        dctx = DistancesContext()
        dctx.rjb  = rjb
        dctx.rrup = rrup
        dctx.rx   = np.zeros(n)
        dctx.ry0  = np.zeros(n)

        ln_mean, [sigma] = gmpe.get_mean_and_stddevs(
            sctx, rctx, dctx, imt_obj, [const.StdDev.TOTAL])

        imt_name = str(imt_obj)
        factor = 9.81 if imt_name == 'PGA' else 0.01
        med = np.exp(ln_mean) * factor
        up  = np.exp(ln_mean + sigma) * factor
        lo  = np.exp(ln_mean - sigma) * factor
        return med, up, lo
    except Exception as exc:
        import traceback
        print(f"    [GMPE warning] {exc}")
        traceback.print_exc()
        return None


# ── PGA / PGV extraction ──────────────────────────────────────────────────────
def _stream_pga_pgv(stream, stations_df):
    """
    Return DataFrame with columns:
        station, lat, lon, vs30, dist_km, pga_h, pgv_h
    for every station that appears in *both* the stream and the CSV.
    pga_h and pgv_h are the combined horizontal (sqrt(N²+E²)) measures.
    """
    rows = []
    unique_stas = list({tr.stats.station for tr in stream})
    sta_map = {}
    for _, row in stations_df.iterrows():
        name = str(row['station'])[:5]
        sta_map[name] = row

    for sta in unique_stas:
        if sta not in sta_map:
            continue
        meta  = sta_map[sta]
        tr_n  = stream.select(station=sta, channel='HHN')
        tr_e  = stream.select(station=sta, channel='HHE')
        if not tr_n or not tr_e:
            continue
        dn, de = tr_n[0].data, tr_e[0].data
        # Instantaneous horizontal vector peak (correct; avoids double-counting
        # independent-component maxima that occur at different times)
        pga_h  = float(np.max(np.sqrt(dn**2 + de**2)))
        dt     = tr_n[0].stats.delta
        # Remove linear trend before integrating to prevent velocity drift
        dn_dt  = sp_detrend(dn, type='linear')
        de_dt  = sp_detrend(de, type='linear')
        vel_n  = np.cumsum(dn_dt) * dt
        vel_e  = np.cumsum(de_dt) * dt
        pgv_h  = float(np.max(np.sqrt(vel_n**2 + vel_e**2)))
        epi_km  = haversine_distance(
            HYPO_LON, HYPO_LAT, float(meta['longitude']), float(meta['latitude']))
        hypo_km = float(np.sqrt(epi_km**2 + HYPO_DEPTH**2))
        rows.append(dict(station=sta,
                         lat=float(meta['latitude']),
                         lon=float(meta['longitude']),
                         vs30=float(meta.get('vs30', 500)),
                         dist_km=hypo_km,
                         pga_h=pga_h,
                         pgv_h=pgv_h))
    return pd.DataFrame(rows)


# ── Fault outline from grouped centroids CSV ──────────────────────────────────
def _fault_outline(fault_csv_path):
    """Return (lon_min, lon_max, lat_min, lat_max, depth_max) or None."""
    if not os.path.isfile(fault_csv_path):
        return None
    df = pd.read_csv(fault_csv_path)
    return (df['centroid_lon'].min(), df['centroid_lon'].max(),
            df['centroid_lat'].min(), df['centroid_lat'].max(),
            df['centroid_depth'].max())


# =============================================================================
# PLOT FUNCTIONS
# =============================================================================

def plot_waveform_overview(stream, n_stations, out_dir, event_name):
    """Panel of n_stations random stations, 3 components each."""
    all_stas = list({tr.stats.station for tr in stream})
    if not all_stas:
        return
    chosen = np.random.choice(all_stas,
                              min(n_stations, len(all_stas)),
                              replace=False)
    fig, axes = plt.subplots(len(chosen), 3, figsize=(15, 2.4 * len(chosen)))
    if len(chosen) == 1:
        axes = axes.reshape(1, -1)

    for i, sta in enumerate(chosen):
        for j, comp in enumerate(['N', 'E', 'Z']):
            ax = axes[i, j]
            tr_sel = stream.select(station=sta, channel=f'HH{comp}')
            if tr_sel:
                d = tr_sel[0].data; t = tr_sel[0].times()
                ax.plot(t, d, 'k-', lw=0.5)
                ax.set_xlim(0, t[-1])
            else:
                ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                        transform=ax.transAxes, fontsize=8)
            ax.grid(alpha=0.25)
            if j == 0:
                ax.set_ylabel(f'{sta}', fontsize=9)
            if i == 0:
                ax.set_title(f'{comp}-component', fontsize=10, fontweight='bold')
            if i == len(chosen) - 1:
                ax.set_xlabel('Time (s)', fontsize=9)
            else:
                ax.set_xticklabels([])

    plt.suptitle(f'{event_name} – waveform overview ({len(chosen)} stations)',
                 fontsize=12, fontweight='bold', y=1.001)
    plt.tight_layout()
    fpath = os.path.join(out_dir, 'summed_synthetics_overview.png')
    plt.savefig(fpath, dpi=150, bbox_inches='tight'); plt.close()
    print(f'    Saved: overview → {os.path.basename(fpath)}')
    return chosen


def plot_waveform_detail(stream, station, out_dir, event_name):
    """Three-component plot for a single station."""
    fig, axes = plt.subplots(3, 1, figsize=(12, 7), sharex=True)
    for i, comp in enumerate(['N', 'E', 'Z']):
        ax = axes[i]
        tr_sel = stream.select(station=station, channel=f'HH{comp}')
        if tr_sel:
            t = tr_sel[0].times(); d = tr_sel[0].data
            ax.plot(t, d, 'k-', lw=0.8)
            mx = np.max(np.abs(d))
            ax.text(0.02, 0.95, f'Max: {mx:.2e}',
                    transform=ax.transAxes, fontsize=9, va='top',
                    bbox=dict(boxstyle='round', fc='white', alpha=0.8))
            ax.set_xlim(0, t[-1])
        ax.set_ylabel(f'{comp}-component', fontsize=10)
        ax.grid(alpha=0.25)
    axes[-1].set_xlabel('Time (s)', fontsize=10)
    plt.suptitle(f'{event_name} – station {station}',
                 fontsize=12, fontweight='bold', y=1.001)
    plt.tight_layout()
    fpath = os.path.join(out_dir, 'summed_synthetics_detail.png')
    plt.savefig(fpath, dpi=150, bbox_inches='tight'); plt.close()
    print(f'    Saved: detail → {os.path.basename(fpath)}')


def plot_trace_comparison(stream, chosen_stations, out_dir, event_name):
    """Stacked normalised multi-station comparison."""
    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
    n = min(10, len(chosen_stations))
    cols = plt.cm.tab10(np.linspace(0, 1, n))
    comp_names = ['North', 'East', 'Vertical']

    for j, comp in enumerate(['N', 'E', 'Z']):
        ax = axes[j]
        for k, sta in enumerate(chosen_stations[:n]):
            tr_sel = stream.select(station=sta, channel=f'HH{comp}')
            if tr_sel:
                d = tr_sel[0].data; t = tr_sel[0].times()
                mx = np.max(np.abs(d))
                dn = d / mx if mx > 0 else d
                ax.plot(t, dn + k * 2.5, color=cols[k], lw=0.8,
                        alpha=0.85, label=sta)
        ax.set_ylabel(f'{comp_names[j]}\n(normalised)', fontsize=10)
        ax.set_yticks([]); ax.grid(alpha=0.25, axis='x')
        if j == 0:
            ax.legend(loc='upper right', fontsize=7, ncol=2)

    axes[-1].set_xlabel('Time (s)', fontsize=10)
    plt.suptitle(f'{event_name} – normalised trace comparison',
                 fontsize=12, fontweight='bold', y=1.001)
    plt.tight_layout()
    fpath = os.path.join(out_dir, 'summed_synthetics_comparison.png')
    plt.savefig(fpath, dpi=150, bbox_inches='tight'); plt.close()
    print(f'    Saved: comparison → {os.path.basename(fpath)}')


def plot_statistics(stream, out_dir, event_name):
    """Histograms: peak amplitude, duration, peak-time (Z-component)."""
    st_z = stream.select(channel='HHZ')
    if not st_z:
        return
    peak_amps = [np.max(np.abs(tr.data)) for tr in st_z]
    durations = [tr.stats.endtime - tr.stats.starttime for tr in st_z]
    max_times = [tr.times()[np.argmax(np.abs(tr.data))] for tr in st_z]

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))

    for ax, data, xlabel, title, col in [
        (axes[0, 0], peak_amps, 'Peak amplitude (m/s²)',
         'Peak amplitudes (Z)', 'steelblue'),
        (axes[0, 1], durations, 'Duration (s)',
         'Trace durations', 'coral'),
        (axes[1, 0], max_times, 'Time of peak (s)',
         'Peak arrival times', 'mediumseagreen'),
    ]:
        ax.hist(data, bins=50, color=col, edgecolor='k', alpha=0.75)
        ax.set_xlabel(xlabel, fontsize=10)
        ax.set_ylabel('Count', fontsize=10)
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.grid(alpha=0.25)
        if 'amplitude' in xlabel.lower():
            ax.set_yscale('log')

    # Summary text
    ax = axes[1, 1]; ax.axis('off')
    n = len(st_z)
    txt = (f"SUMMARY – Z component\n\n"
           f"Traces: {n}\n\n"
           f"Peak amplitude:\n"
           f"  mean   {np.mean(peak_amps):.2e}\n"
           f"  median {np.median(peak_amps):.2e}\n"
           f"  max    {np.max(peak_amps):.2e}\n\n"
           f"Duration:\n"
           f"  mean   {np.mean(durations):.1f} s\n"
           f"  median {np.median(durations):.1f} s\n\n"
           f"Peak time:\n"
           f"  mean   {np.mean(max_times):.1f} s\n"
           f"  median {np.median(max_times):.1f} s\n")
    ax.text(0.05, 0.95, txt, transform=ax.transAxes, fontsize=9,
            va='top', family='monospace',
            bbox=dict(boxstyle='round', fc='wheat', alpha=0.6))

    plt.suptitle(f'{event_name} – amplitude statistics',
                 fontsize=12, fontweight='bold', y=1.001)
    plt.tight_layout()
    fpath = os.path.join(out_dir, 'summed_synthetics_statistics.png')
    plt.savefig(fpath, dpi=150, bbox_inches='tight'); plt.close()
    print(f'    Saved: statistics → {os.path.basename(fpath)}')


def plot_pga_distance(all_data_df, mag, depth, out_dir, event_name):
    """
    Horizontal PGA vs distance scatter (VS30-coloured, realisation-edged)
    + BA2008 GMPE median ± 1σ.
    """
    if all_data_df.empty:
        print('    [SKIP] PGA plot – no data.')
        return

    fig, ax = plt.subplots(figsize=(13, 7))
    reals   = sorted(all_data_df['realization'].unique())
    ec_cols = plt.cm.tab10(np.linspace(0, 1, len(reals)))
    vmin    = all_data_df['vs30'].min()
    vmax    = all_data_df['vs30'].max()
    sc = None

    for k, r in enumerate(reals):
        sub = all_data_df[all_data_df['realization'] == r]
        sc  = ax.scatter(sub['dist_km'], sub['pga_h'],
                         c=sub['vs30'], cmap='viridis',
                         vmin=vmin, vmax=vmax,
                         s=35, alpha=0.65,
                         edgecolors=ec_cols[k], linewidths=0.8,
                         label=f'Real. {r:02d}')

    if sc is not None:
        cbar = plt.colorbar(sc, ax=ax)
        cbar.set_label('VS30 (m/s)', fontsize=11, rotation=270, labelpad=18)

    # GMPE: BA2008 uses rjb (epicentral for point source) and rrup (hypocentral)
    # dist_g here is hypocentral; derive rjb = sqrt(max(rhypo²−depth²,0))
    d_max   = all_data_df['dist_km'].max()
    dist_g  = np.linspace(float(depth), d_max * 1.05, 200)   # hypocentral
    rjb_g   = np.sqrt(np.maximum(dist_g**2 - float(depth)**2, 0.0))
    res = _gmpe_curve_rjb(mag, depth, imt.PGA(), rjb_g, dist_g)
    if res is not None:
        med, up, lo = res
        ax.plot(dist_g, med, 'k-', lw=2.5,
                label=f'BA08 PGA (VS30={GMPE_VS30_REF:.0f})', zorder=10)
        ax.fill_between(dist_g, lo, up, color='gray', alpha=0.2,
                        label='BA08 ±1σ', zorder=9)

    ax.set_xlabel(f'Hypocentral distance (km)  [depth={HYPO_DEPTH:.0f} km]',
                 fontsize=11, fontweight='bold')
    ax.set_ylabel('Horizontal PGA  √(N²+E²)  [m/s²]', fontsize=11, fontweight='bold')
    ax.set_title(f'{event_name}  –  PGA vs Hypocentral Distance\n'
                 f'({len(reals)} realisations | {len(all_data_df)} points)',
                 fontsize=12, fontweight='bold')
    ax.set_yscale('log'); ax.grid(alpha=0.3)
    ax.set_xlim(left=0, right=all_data_df['dist_km'].max() * 1.05)
    ax.legend(loc='upper right', fontsize=8, ncol=2, framealpha=0.9)

    plt.tight_layout()
    fpath = os.path.join(out_dir, 'pga_vs_distance.png')
    plt.savefig(fpath, dpi=150, bbox_inches='tight'); plt.close()
    print(f'    Saved: PGA vs distance → {os.path.basename(fpath)} '
          f'({len(all_data_df)} points, {len(reals)} realisations)')


def plot_pgv_distance(all_data_df, mag, depth, out_dir, event_name):
    """Horizontal PGV vs distance + BA2008 GMPE."""
    if all_data_df.empty:
        print('    [SKIP] PGV plot – no data.')
        return

    fig, ax = plt.subplots(figsize=(13, 7))
    reals   = sorted(all_data_df['realization'].unique())
    ec_cols = plt.cm.tab10(np.linspace(0, 1, len(reals)))
    vmin    = all_data_df['vs30'].min()
    vmax    = all_data_df['vs30'].max()
    sc = None

    for k, r in enumerate(reals):
        sub = all_data_df[all_data_df['realization'] == r]
        sc  = ax.scatter(sub['dist_km'], sub['pgv_h'],
                         c=sub['vs30'], cmap='viridis',
                         vmin=vmin, vmax=vmax,
                         s=35, alpha=0.65,
                         edgecolors=ec_cols[k], linewidths=0.8,
                         label=f'Real. {r:02d}')

    if sc is not None:
        cbar = plt.colorbar(sc, ax=ax)
        cbar.set_label('VS30 (m/s)', fontsize=11, rotation=270, labelpad=18)

    d_max   = all_data_df['dist_km'].max()
    dist_g  = np.linspace(float(depth), d_max * 1.05, 200)
    rjb_g   = np.sqrt(np.maximum(dist_g**2 - float(depth)**2, 0.0))
    res = _gmpe_curve_rjb(mag, depth, imt.PGV(), rjb_g, dist_g)
    if res is not None:
        med, up, lo = res
        ax.plot(dist_g, med, 'k-', lw=2.5,
                label=f'BA08 PGV (VS30={GMPE_VS30_REF:.0f})', zorder=10)
        ax.fill_between(dist_g, lo, up, color='gray', alpha=0.2,
                        label='BA08 ±1σ', zorder=9)

    ax.set_xlabel(f'Hypocentral distance (km)  [depth={HYPO_DEPTH:.0f} km]',
                 fontsize=11, fontweight='bold')
    ax.set_ylabel('Horizontal PGV  √(N²+E²)  [m/s]', fontsize=11, fontweight='bold')
    ax.set_title(f'{event_name}  –  PGV vs Hypocentral Distance\n'
                 f'({len(reals)} realisations | {len(all_data_df)} points)',
                 fontsize=12, fontweight='bold')
    ax.set_yscale('log'); ax.grid(alpha=0.3)
    ax.set_xlim(left=0, right=all_data_df['dist_km'].max() * 1.05)
    ax.legend(loc='upper right', fontsize=8, ncol=2, framealpha=0.9)

    plt.tight_layout()
    fpath = os.path.join(out_dir, 'pgv_vs_distance.png')
    plt.savefig(fpath, dpi=150, bbox_inches='tight'); plt.close()
    print(f'    Saved: PGV vs distance → {os.path.basename(fpath)}')


def plot_shakemap(shake_df, fault_outline, out_dir, event_name):
    """
    Spatial PGA map.  Uses Cartopy if available, otherwise plain Matplotlib.
    *fault_outline* is (lon_min, lon_max, lat_min, lat_max, depth_max) or None.
    """
    if shake_df.empty:
        print('    [SKIP] Shakemap – no PGA data.')
        return

    # ── PGA colourmap (USGS-style MMI thresholds) ─────────────────────────────
    pga_levels = [0, 0.046, 0.3, 2.76, 6.2, 11.5, 21.5, 40.1, 74.7, 139, 500]
    usgs_colors = ['#FFFFFF', '#BFCCFF', '#A0E6FF', '#80FFFF', '#7DF894',
                   '#FFFF00', '#FFAA00', '#FF8033', '#CC3300', '#880000']
    cmap  = mcolors.ListedColormap(usgs_colors)
    norm  = mcolors.BoundaryNorm(pga_levels, cmap.N)

    # ── Grid extent ────────────────────────────────────────────────────────────
    margin  = 0.3
    lon_min = shake_df['lon'].min() - margin
    lon_max = shake_df['lon'].max() + margin
    lat_min = shake_df['lat'].min() - margin
    lat_max = shake_df['lat'].max() + margin

    # ── Interpolate PGA onto a regular grid ───────────────────────────────────
    glon = np.linspace(lon_min, lon_max, 200)
    glat = np.linspace(lat_min, lat_max, 200)
    glo, gla = np.meshgrid(glon, glat)
    pts   = shake_df[['lon', 'lat']].values
    vals  = shake_df['pga_h'].values          # m/s² – convert to %g for display
    pga_pctg = vals / 9.81 * 100.0
    
    # Check if data is essentially 1D (colinear stations) - requires 2D variation for cubic
    lat_range = shake_df['lat'].max() - shake_df['lat'].min()
    lon_range = shake_df['lon'].max() - shake_df['lon'].min()
    is_colinear = (lat_range < 0.01 or lon_range < 0.01)
    
    if is_colinear:
        # Fall back to nearest-neighbor interpolation for 1D/colinear data
        grid = griddata(pts, vals / 9.81 * 100.0, (glo, gla),
                       method='nearest', fill_value=0.0)
        print('    [INFO] Stations are colinear – using nearest-neighbor interpolation')
    else:
        grid = griddata(pts, vals / 9.81 * 100.0, (glo, gla),
                       method='cubic', fill_value=0.0)
    grid  = np.clip(grid, 0, 500)

    # ── Figure ─────────────────────────────────────────────────────────────────
    if CARTOPY_AVAILABLE:
        fig = plt.figure(figsize=(13, 11))
        ax  = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        ax.set_extent([lon_min, lon_max, lat_min, lat_max],
                      crs=ccrs.PlateCarree())
        ax.add_feature(cfeature.COASTLINE, lw=0.5)
        ax.add_feature(cfeature.BORDERS,   lw=0.5)
        ax.add_feature(cfeature.LAND,      color='lightgray', alpha=0.4)
        ax.add_feature(cfeature.OCEAN,     color='lightblue', alpha=0.25)
        transform = ccrs.PlateCarree()
        ax.contourf(glo, gla, grid, levels=pga_levels,
                    cmap=cmap, norm=norm, alpha=0.85, transform=transform,
                    extend='max')
        sc = ax.scatter(shake_df['lon'], shake_df['lat'],
                        c=pga_pctg, cmap=cmap, norm=norm,
                        s=55, edgecolors='k', lw=0.7,
                        transform=transform, zorder=8)
        ax.gridlines(draw_labels=True, lw=0.4, alpha=0.5)
    else:
        fig, ax = plt.subplots(figsize=(11, 9))
        transform = None
        cf = ax.contourf(glo, gla, grid, levels=pga_levels,
                         cmap=cmap, norm=norm, alpha=0.85, extend='max')
        sc = ax.scatter(shake_df['lon'], shake_df['lat'],
                        c=pga_pctg, cmap=cmap, norm=norm,
                        s=55, edgecolors='k', lw=0.7, zorder=8)
        ax.set_xlabel('Longitude', fontsize=11, fontweight='bold')
        ax.set_ylabel('Latitude',  fontsize=11, fontweight='bold')
        ax.set_xlim(lon_min, lon_max)
        ax.set_ylim(lat_min, lat_max)
        ax.grid(alpha=0.3, lw=0.5)

    # ── Fault outline (bounding box from centroids) ────────────────────────────
    if fault_outline is not None:
        flo_min, flo_max, fla_min, fla_max, _ = fault_outline
        rect_lons = [flo_min, flo_max, flo_max, flo_min, flo_min]
        rect_lats = [fla_min, fla_min, fla_max, fla_max, fla_min]
        kw = dict(color='black', lw=2.0, ls='--', alpha=0.9, label='Fault extent')
        if CARTOPY_AVAILABLE:
            ax.plot(rect_lons, rect_lats, transform=ccrs.PlateCarree(), **kw)
        else:
            ax.plot(rect_lons, rect_lats, **kw)

    # ── Hypocentre star ────────────────────────────────────────────────────────
    kw_hypo = dict(marker='*', color='red', s=350, edgecolors='k',
                   lw=1, zorder=12, label='Hypocentre')
    if CARTOPY_AVAILABLE:
        ax.scatter([HYPO_LON], [HYPO_LAT], transform=ccrs.PlateCarree(), **kw_hypo)
    else:
        ax.scatter([HYPO_LON], [HYPO_LAT], **kw_hypo)

    # ── Colorbar ────────────────────────────────────────────────────────────────
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, orientation='vertical',
                        shrink=0.75, pad=0.04, aspect=28)
    cbar.set_label('PGA  (%g)', fontsize=11, fontweight='bold')
    cbar.set_ticks(pga_levels[:-1])
    cbar.set_ticklabels([str(v) for v in pga_levels[:-1]], fontsize=8)

    # ── Legend + stats ─────────────────────────────────────────────────────────
    ax.legend(loc='upper left', fontsize=9, framealpha=0.9)
    stats_txt = (f"Stations: {len(shake_df)}\n"
                 f"Max PGA: {pga_pctg.max():.2f} %g\n"
                 f"Mean PGA: {pga_pctg.mean():.2f} %g\n"
                 f"Min PGA: {pga_pctg.min():.2f} %g")
    ax.text(0.98, 0.02, stats_txt, transform=ax.transAxes,
            fontsize=9, ha='right', va='bottom',
            bbox=dict(boxstyle='round,pad=0.4', fc='white', alpha=0.9))

    plt.title(f'{event_name}  –  PGA Shakemap  (realization {REFERENCE_REALIZATION:02d})',
              fontsize=13, fontweight='bold', pad=12)
    plt.tight_layout()
    fpath = os.path.join(out_dir, 'shakemap.png')
    plt.savefig(fpath, dpi=150, bbox_inches='tight'); plt.close()
    print(f'    Saved: shakemap → {os.path.basename(fpath)}')


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':

    magnitudes = np.round(
        np.arange(MAG_MIN, MAG_MAX + MAG_STEP * 0.5, MAG_STEP), 4
    ).tolist()

    print('=' * 70)
    print('BULK SYNTHETIC WAVEFORM EVALUATION')
    print(f'Magnitudes: {magnitudes}')
    print('=' * 70)

    for mag in magnitudes:
        event_name = f'{EVENT_NAME_PREFIX}{mag:.1f}'
        event_dir  = os.path.join(DATA_ROOT, event_name)
        synth_dir  = os.path.join(event_dir, 'summed_synthetics')
        out_dir    = os.path.join(event_dir, 'results', 'summed_synthetics_plots')
        os.makedirs(out_dir, exist_ok=True)

        print(f'\n{"═" * 60}')
        print(f'  EVENT  {event_name}')
        print(f'{"═" * 60}')

        # ── Reference realization for waveform / shakemap panels ──────────
        ref_mseed = os.path.join(synth_dir,
                                 f'summed_realization_{REFERENCE_REALIZATION:02d}.mseed')
        if not os.path.isfile(ref_mseed):
            print(f'  [SKIP] Reference MSEED not found: {ref_mseed}')
            print('  → Run 01_sum_bulk_synthetics.py first.')
            continue

        stations_csv = os.path.join(event_dir, 'station_csv', 'filtered_stations.csv')
        if not os.path.isfile(stations_csv):
            print(f'  [SKIP] Station CSV not found: {stations_csv}')
            continue

        stations_df = pd.read_csv(stations_csv)
        if 'vs30' not in stations_df.columns:
            stations_df['vs30'] = 500

        print(f'  Loading reference stream (realization {REFERENCE_REALIZATION:02d}) …')
        stream_ref = read(ref_mseed)
        print(f'  {len(stream_ref)} traces, {len({tr.stats.station for tr in stream_ref})} stations')

        # ── Waveform panels ───────────────────────────────────────────────
        np.random.seed(42)
        chosen = plot_waveform_overview(stream_ref, N_STATIONS,
                                        out_dir, event_name)
        if chosen is not None and len(chosen) > 0:
            plot_waveform_detail(stream_ref, chosen[0], out_dir, event_name)
            plot_trace_comparison(stream_ref, chosen, out_dir, event_name)
        plot_statistics(stream_ref, out_dir, event_name)

        # ── Accumulate PGA / PGV from all available realisations ─────────
        all_rows = []
        available_reals = []
        for r in range(1, 11):
            fp = os.path.join(synth_dir, f'summed_realization_{r:02d}.mseed')
            if os.path.isfile(fp):
                available_reals.append(r)

        print(f'  Accumulating PGA/PGV from {len(available_reals)} realisations …')
        for r in available_reals:
            fp = os.path.join(synth_dir, f'summed_realization_{r:02d}.mseed')
            st = read(fp)
            df_r = _stream_pga_pgv(st, stations_df)
            df_r['realization'] = r
            all_rows.append(df_r)

        all_data = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
        # Filter by max distance
        if not all_data.empty:
            all_data = all_data[all_data['dist_km'] <= MAX_DISTANCE]

        plot_pga_distance(all_data, mag, HYPO_DEPTH, out_dir, event_name)
        plot_pgv_distance(all_data, mag, HYPO_DEPTH, out_dir, event_name)

        # ── Shakemap (reference realization) ──────────────────────────────
        shake_df = _stream_pga_pgv(stream_ref, stations_df)
        grouped_csv = os.path.join(
            event_dir, 'fault_csv',
            f'grouped_centroids_data_{event_name}.csv')
        fault_bb = _fault_outline(grouped_csv)

        plot_shakemap(shake_df, fault_bb, out_dir, event_name)

        print(f'\n  ✓  {event_name} complete.  '
              f'Results: {out_dir}')

    print('\n' + '=' * 70)
    print('EVALUATION COMPLETE')
    print(f'Magnitudes: M{MAG_MIN:.1f} – M{MAG_MAX:.1f}')
    print('=' * 70)
