"""
Bulk Waveform Summation  –  M6.0 to M8.0
==========================================

Stage 2 of 2 in the templates_fix workflow.

Run AFTER 00_generate_bulk_faults.py.

For each magnitude in [MAG_MIN, MAG_MAX] (same sweep as Stage 1) the script:
  1. Loads grouped subsource centroids produced by Stage 1.
  2. Loads station locations (with VS30) from
         <event_dir>/station_csv/filtered_stations.csv
     (copied/shared with SyntheticEvent data, or created independently).
  3. For every (subsource × station × component) combination:
       • Selects the closest preprocessed template with matching
         VS30, subsource magnitude and source-to-station distance.
       • Time-shifts the template by the subsource rupture time t_rup.
  4. Sums all subsource contributions for each station channel.
  5. Repeats for N_REALIZATIONS independent noise realisations.
  6. Writes one MSEED file per realisation:
         <event_dir>/summed_synthetics/summed_realization_NN.mseed

Mirrors the logic of:
    ../Finite_rupture/02_sum_subsource_synthetics.py
"""

import os
import sys
import numpy as np
import pandas as pd
from collections import defaultdict
from obspy import Stream, Trace
from obspy.core import UTCDateTime

# ── Import shared helpers ──────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from helpers import (
    moment2magnitude, magnitude2moment,
    haversine_distance,
    find_closest_magnitude, find_closest_vs30,
    get_available_templates_info, load_template,
)


# =============================================================================
# ▶▶  USER-EDITABLE PARAMETERS
# =============================================================================

# ── Magnitude sweep  (must match 00_generate_bulk_faults.py) ─────────────────
MAG_MIN   = 6.0
MAG_MAX   = 8.0
MAG_STEP  = 0.1

EVENT_NAME_PREFIX = 'SyntheticEvent_M'   # e.g. SyntheticEvent_M7.0

# ── Data root ─────────────────────────────────────────────────────────────────
DATA_ROOT = '/Users/francescoacolosimo/Desktop/SED/envelopes_sweet/Data'

# ── Template library ──────────────────────────────────────────────────────────
# Points to the filtered library produced by 04_filter_templates.py.
# Each bin contains exactly ONE realization (best-fit or GMPE-rescaled).
PREPROCESSED_TEMPLATES_DIR = (
    f'{DATA_ROOT}/synthetics/synthetics_filtered'
)

# ── Station metadata CSV with station-to-template code mapping ───────────────
#   Leave empty string '' to skip this mapping.
METADATA_CSV = (
    f'{DATA_ROOT}/synthetics/'
    'metadata_envelopes_300_500_700_900vs30_100real_4_7mag_AZ70.hdf5.csv'
)

# ── Summation settings ────────────────────────────────────────────────────────
N_REALIZATIONS  = 1       # filtered library has 1 realization per bin
SAMPLING_RATE   = 100.0   # Hz

# ── Amplitude scaling ─────────────────────────────────────────────────────────
# MOMENT_SCALE: multiply each template by  M0_subsource / M0_template_mag.
#   True  → physically correct EGF scaling; appropriate when templates have
#           NOT been amplitude-calibrated externally.
#   False → use template as-is.  Set False when templates come from
#           04_filter_templates.py, which already rescaled each bin to the
#           BA2008 GMPE median PGA.  Applying moment ratio on top would be
#           a double-correction that kills PGA while barely affecting PGV.
MOMENT_SCALE    = False

# AMPLITUDE_SCALE: additional global scalar applied AFTER moment scaling.
#   1.0 = no change.  Reduce (e.g. 0.5) if summed PGAs are systematically too
#   high versus a GMPE reference; increase if too low.
AMPLITUDE_SCALE = 1.0

# MIN_TEMPLATE_DIST_KM: clamp the source-to-station distance passed to the
#   template lookup to this floor value.  Templates at < ~10 km have
#   unphysical near-field amplitudes (e.g. M6 @ 5 km → 41 m/s²) and must
#   not be used.  Any subsource–station pair closer than this will reuse
#   the template at MIN_TEMPLATE_DIST_KM instead.
MIN_TEMPLATE_DIST_KM = 10.0

# ── Station fallback ──────────────────────────────────────────────────────────
#   If a magnitude's station CSV is absent, attempt to borrow it from this
#   reference event (leave None to skip events with no stations).
FALLBACK_STATION_EVENT = None   # e.g. 'SyntheticEvent_M7.0'

# =============================================================================
# END OF USER PARAMETERS
# =============================================================================


# ── Load optional station-to-template mapping ─────────────────────────────────
station_template_map: dict = {}
if METADATA_CSV and os.path.isfile(METADATA_CSV):
    try:
        meta = pd.read_csv(METADATA_CSV, usecols=['station_code', 'template_code'])
        for _, row in meta.drop_duplicates('station_code').iterrows():
            station_template_map[row['station_code']] = row['template_code']
        print(f'Loaded {len(station_template_map)} station→template mappings '
              f'from metadata CSV.')
    except Exception as exc:
        print(f'[WARNING] Could not load metadata CSV: {exc}')


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':

    magnitudes = np.round(
        np.arange(MAG_MIN, MAG_MAX + MAG_STEP * 0.5, MAG_STEP), 4
    ).tolist()

    print('=' * 70)
    print('BULK WAVEFORM SUMMATION')
    print(f'Magnitudes: {magnitudes}')
    print(f'Template dir: {PREPROCESSED_TEMPLATES_DIR}')
    print('=' * 70)

    # ── Scan available templates once (shared across all magnitudes) ──────────
    print('\nScanning preprocessed templates …')
    tmpl_info = get_available_templates_info(PREPROCESSED_TEMPLATES_DIR)
    avail_mags  = tmpl_info['magnitudes']
    avail_vs30  = tmpl_info['vs30']
    avail_dists = tmpl_info['distances']
    print(f'  Magnitudes:  {avail_mags}')
    print(f'  VS30 values: {avail_vs30}')
    print(f'  Distance bins: {len(avail_dists)} '
          f'({min(avail_dists) if avail_dists else "n/a"} – '
          f'{max(avail_dists) if avail_dists else "n/a"} km)')
    print(f'  Realisations requested: {N_REALIZATIONS}')

    if not avail_mags:
        print('\n[ERROR] No processed templates found – '
              'check PREPROCESSED_TEMPLATES_DIR and run preprocess_hdf5_templates.py.')
        sys.exit(1)

    # ── Event loop ────────────────────────────────────────────────────────────
    for mag in magnitudes:
        event_name = f'{EVENT_NAME_PREFIX}{mag:.1f}'
        event_dir  = os.path.join(DATA_ROOT, event_name)
        out_dir    = os.path.join(event_dir, 'summed_synthetics')
        os.makedirs(out_dir, exist_ok=True)

        print(f'\n{"═" * 60}')
        print(f'  EVENT  {event_name}')
        print(f'{"═" * 60}')

        # ── Load subsources ────────────────────────────────────────────────
        subsources_csv = os.path.join(
            event_dir, 'fault_csv',
            f'grouped_centroids_data_{event_name}.csv')

        if not os.path.isfile(subsources_csv):
            print(f'  [SKIP] Subsource CSV not found:\n  {subsources_csv}')
            print(f'  → Run 00_generate_bulk_faults.py first.')
            continue

        subsources = pd.read_csv(subsources_csv)
        subsources['magnitude'] = subsources['sf_moment'].apply(moment2magnitude)
        print(f'  Subsources loaded: {len(subsources)}')

        # ── Load stations ──────────────────────────────────────────────────
        stations_csv = os.path.join(event_dir, 'station_csv', 'filtered_stations.csv')

        if not os.path.isfile(stations_csv) and FALLBACK_STATION_EVENT:
            fallback_csv = os.path.join(
                DATA_ROOT, FALLBACK_STATION_EVENT,
                'station_csv', 'filtered_stations.csv')
            if os.path.isfile(fallback_csv):
                print(f'  [INFO] Using fallback stations: {FALLBACK_STATION_EVENT}')
                stations_csv = fallback_csv

        if not os.path.isfile(stations_csv):
            print(f'  [SKIP] Station CSV not found:\n  {stations_csv}')
            print('  → Create filtered_stations.csv or set FALLBACK_STATION_EVENT.')
            continue

        stations = pd.read_csv(stations_csv)
        if 'vs30' not in stations.columns:
            print('  [WARNING] No vs30 column – assigning default 500 m/s.')
            stations['vs30'] = 500
        print(f'  Stations loaded:  {len(stations)}')

        # ── Realisation loop ───────────────────────────────────────────────
        for real_idx in range(N_REALIZATIONS):
            print(f'\n  ── Realisation {real_idx + 1:02d}/{N_REALIZATIONS} ──')

            traces_dict: dict = defaultdict(list)
            sta_ok,  sta_miss = set(), set()

            # ── Subsource loop ─────────────────────────────────────────────
            for ss_idx, ss in subsources.iterrows():
                ss_mag  = ss['magnitude']
                ss_trup = ss['trup']
                ss_lon  = ss['centroid_lon']
                ss_lat  = ss['centroid_lat']

                tmpl_mag = find_closest_magnitude(avail_mags, ss_mag)

                # ── Station loop ───────────────────────────────────────────
                for _, sta in stations.iterrows():
                    sta_code = sta['station_code']
                    sta_name = sta['station']
                    net_code = sta['network']
                    sta_lat  = sta['latitude']
                    sta_lon  = sta['longitude']
                    sta_vs30 = sta['vs30']

                    dist_km  = haversine_distance(ss_lon, ss_lat, sta_lon, sta_lat)
                    tmpl_vs30 = find_closest_vs30(avail_vs30, sta_vs30)

                    # Clamp near-field distances to avoid unphysical templates
                    tmpl_dist = max(dist_km, MIN_TEMPLATE_DIST_KM)

                    envelope = load_template(
                        PREPROCESSED_TEMPLATES_DIR,
                        tmpl_vs30, tmpl_mag, tmpl_dist, real_idx,
                    )

                    if envelope is None:
                        if ss_idx == 0:
                            sta_miss.add(sta_code)
                        continue

                    if ss_idx == 0:
                        sta_ok.add(sta_code)

                    # ── Optional moment-ratio scaling (EGF approach) ────────
                    # Scale template amplitude by  M0_subsource / M0_template
                    # so that contributions are proportional to the exact
                    # subsource moment, not just the nearest template moment.
                    if MOMENT_SCALE:
                        m0_sub  = float(ss['sf_moment'])          # N·m
                        m0_tmpl = magnitude2moment(tmpl_mag)      # N·m
                        moment_ratio = m0_sub / m0_tmpl
                    else:
                        moment_ratio = 1.0

                    scale = moment_ratio * AMPLITUDE_SCALE

                    # envelope shape: (3, N_samples)  [East, North, Vertical]
                    for comp_i, comp_lbl in enumerate(['E', 'N', 'Z']):
                        tr = Trace()
                        tr.data = envelope[comp_i, :].copy() * scale
                        tr.stats.network      = str(net_code)[:2]
                        tr.stats.station      = str(sta_name)[:5]
                        tr.stats.location     = '00'
                        tr.stats.channel      = f'HH{comp_lbl}'
                        tr.stats.sampling_rate = SAMPLING_RATE
                        tr.stats.starttime    = UTCDateTime(0) + float(ss_trup)
                        # preserve metadata
                        tr.stats.distance          = dist_km
                        tr.stats.vs30              = float(sta_vs30)
                        tr.stats.full_station_code = sta_code
                        traces_dict[(str(sta_name)[:5], f'HH{comp_lbl}')].append(tr)

            print(f'    Templates found for {len(sta_ok)} stations, '
                  f'missing for {len(sta_miss)} stations.')

            # ── Sum contributions for every (station, channel) ─────────────
            summed_traces = []
            for (sta_name, channel), trs in traces_dict.items():
                t0   = min(tr.stats.starttime for tr in trs)
                tend = max(tr.stats.endtime   for tr in trs)
                npts = int((tend - t0) * SAMPLING_RATE) + 1

                buf = np.zeros(npts)
                for tr in trs:
                    off = int((tr.stats.starttime - t0) * SAMPLING_RATE)
                    buf[off: off + len(tr.data)] += tr.data

                out_tr = trs[0].copy()
                out_tr.data            = buf
                out_tr.stats.starttime = t0
                out_tr.stats.npts      = npts
                summed_traces.append(out_tr)

            # ── Write MSEED ────────────────────────────────────────────────
            stream = Stream(traces=summed_traces)
            out_file = os.path.join(out_dir,
                                    f'summed_realization_{real_idx + 1:02d}.mseed')
            stream.write(out_file, format='MSEED')
            print(f'    Saved ({len(stream)} traces) → {out_file}')

        print(f'\n  ✓  {event_name} complete.  '
              f'Output: {out_dir}')

    print('\n' + '=' * 70)
    print('BULK SUMMATION COMPLETE')
    print(f'Events processed: M{MAG_MIN:.1f} – M{MAG_MAX:.1f}')
    print('=' * 70)
