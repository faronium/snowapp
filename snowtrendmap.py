"""
The Trends tab's map: each station coloured by the trend in one snow season indicator, or by its correlation
with RONI, and zoomed to the station or group selected on the tab.

Colours run toward red for change toward less snow: later snow-on, lower peak SWE, earlier snow-off, a shorter
season and an earlier peak. Melt rate has no such direction and uses a sequential red scale (darker = higher).
Trends are per decade: days for dates and season length, and percent for peak SWE and melt rate (from the
Theil-Sen slope of their logarithm) so that large and small snowpacks can be compared.
"""
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import diverging, sample_colorscale, sequential

import snowgroups as sg
import snowindicators as si
import snowmap

LESS_SNOW = {'peak_swe': -1, 'peak_day': -1, 'snow_on_day': +1, 'snow_off_day': -1, 'season_days': -1,
             'melt_rate': None, 'melt_rate_3d': None}   # sign of change toward less snow; None: no direction
PERCENT = {'peak_swe', 'melt_rate', 'melt_rate_3d'}
TREND_RANGE = {'peak_swe': 15, 'peak_day': 10, 'snow_on_day': 10, 'snow_off_day': 10, 'season_days': 15,
               'melt_rate': 15, 'melt_rate_3d': 15}    # colours saturate beyond +/- this many units per decade
R_RANGE = 0.6                      # ... and beyond +/- this correlation
SIGNIFICANT = 0.05
FDR_Q = 0.10
OUT_COLOR = 'rgb(200,200,200)'     # stations that aren't part of the current analysis
FEW_COLOR = 'rgb(105,105,105)'     # fewer than si.MIN_TREND_SEASONS seasons in the period (small, opaque)
RING_COLOR = 'rgb(30,30,30)'       # ring around significant stations
SELECT_COLOR = 'rgb(0,220,120)'    # halo around the selected station (as on the main map)

# The view is set in the browser by fitting the map to a box (MapLibre's fitBounds, see snowapp.py), so the
# framing suits the map's real size. The centre and zoom estimated here, for a map of about this many pixels,
# are only the starting point.
MAP_WIDTH_PX, MAP_HEIGHT_PX = 510, 780
STATION_HALF_KM = 100.0
GROUP_MARGIN = 0.25
GROUP_MIN_HALF_KM = 50.0


# ---------------------------------------------------------------- statistics for every station

def units(col, stat):
    if stat == 'enso':
        return 'r with RONI'
    return '%/decade' if col in PERCENT else 'days/decade'


def station_stats(indicators, station_ids, col, enso, start=None, stat='trend', adjust_enso=False):
    """
    For each station: value (trend per decade in map units, or correlation with RONI), p and n (seasons),
    computed as in the Trends figures over the seasons from `start` on.
    """
    rows = {}
    for sid in station_ids:
        d = indicators.get(sid)
        if d is None or d.empty or col not in d:
            rows[sid] = (np.nan, np.nan, 0)
            continue
        v = d[col] if start is None else d.loc[d.index >= start, col]
        v = v.dropna()
        if stat == 'enso':
            r = si.enso_relationship(pd.Series(enso).reindex(v.index).to_numpy(), v.to_numpy())
            rows[sid] = (r.get('r', np.nan), r.get('p', np.nan), r['n'])
            continue
        raw = sg.station_adjusted(v, enso)[0] if adjust_enso else v
        t = si.trend(raw.index, raw.to_numpy())             # p and n exactly as in the station's figure
        if 'slope' not in t:
            rows[sid] = (np.nan, np.nan, t['n'])
            continue
        value = t['slope_per_decade']
        if col in PERCENT:
            logv = np.log(v.where(v > 0)).dropna()
            if adjust_enso:
                logv = sg.station_adjusted(logv, enso)[0]
            slope, _ = si.theil_sen(logv.index, logv.to_numpy())
            value = 100 * (math.exp(10 * slope) - 1)
        rows[sid] = (value, t['p'], t['n'])
    return pd.DataFrame.from_dict(rows, orient='index', columns=['value', 'p', 'n'])


# ---------------------------------------------------------------- colours and key

def _scale_position(values, col, stat):
    """Position (0-1) of each value on the colour scale; 0 is the red end of the diverging scale."""
    rng = R_RANGE if stat == 'enso' else TREND_RANGE[col]
    v = np.clip(np.asarray(values, dtype=float), -rng, rng)
    sign = LESS_SNOW[col]
    if sign is None:
        return (v + rng) / (2 * rng)                         # sequential: light (low) to dark (high)
    return 0.5 - 0.5 * sign * v / rng                        # change toward less snow -> red end


def _scale(col):
    return sequential.Reds if LESS_SNOW[col] is None else diverging.RdBu


def value_colors(values, col, stat):
    values = np.asarray(values, dtype=float)
    colors = np.array([FEW_COLOR] * len(values), dtype=object)
    ok = ~np.isnan(values)
    if ok.any():
        colors[ok] = sample_colorscale(_scale(col), list(_scale_position(values[ok], col, stat)))
    return list(colors)


def _tick(v, stat, rng):
    text = f'{v:+.1f}' if stat == 'enso' else f'{v:+.0f}'
    text = '0' if v == 0 else text.replace('-', '−')
    if v == rng:
        return '≥' + text
    if v == -rng:
        return '≤' + text
    return text


def key(col, stat):
    """Colour key contents (snowmap.key_children) for an indicator and statistic."""
    rng = R_RANGE if stat == 'enso' else TREND_RANGE[col]
    bottom_to_top = np.linspace(-rng, rng, 11)
    colors = sample_colorscale(_scale(col), list(_scale_position(bottom_to_top, col, stat)))
    ticks = [(100 * (rng - v) / (2 * rng), _tick(v, stat, rng)) for v in np.linspace(rng, -rng, 5)]
    return snowmap.key_children(colors, ticks, f'{si.INDICATORS[col][0]}: {units(col, stat)}')


# ---------------------------------------------------------------- view

def _zoom_for(lat_min, lat_max, lon_min, lon_max):
    """Zoom level at which a box fits the map (MapLibre: the world is 512 * 2**zoom pixels wide)."""
    lon_span = max(lon_max - lon_min, 1e-6)
    merc = lambda lat: math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    y_span = max(merc(lat_max) - merc(lat_min), 1e-6)
    z_lon = math.log2(MAP_WIDTH_PX * 360 / (512 * lon_span))
    z_lat = math.log2(MAP_HEIGHT_PX * 2 * math.pi / (512 * y_span))
    return float(np.clip(min(z_lon, z_lat), 3.0, 9.0))


def view_for(lats, lons, level):
    """
    The map's view for a selection: a box [[west, south], [east, north]] about +/-100 km around a station, or
    around a group's stations (all stations for all of BC) with a margin, plus a centre and zoom estimated
    from it.
    """
    lats, lons = np.asarray(lats, dtype=float), np.asarray(lons, dtype=float)
    lat0, lon0 = float((lats.min() + lats.max()) / 2), float((lons.min() + lons.max()) / 2)
    km_lat, km_lon = 111.0, 111.0 * math.cos(math.radians(lat0))
    if level == 'station':
        half_lat, half_lon = STATION_HALF_KM / km_lat, STATION_HALF_KM / km_lon
    else:
        half_lat = max((lats.max() - lats.min()) / 2 * (1 + GROUP_MARGIN), GROUP_MIN_HALF_KM / km_lat)
        half_lon = max((lons.max() - lons.min()) / 2 * (1 + GROUP_MARGIN), GROUP_MIN_HALF_KM / km_lon)
    box = [[lon0 - half_lon, lat0 - half_lat], [lon0 + half_lon, lat0 + half_lat]]
    zoom = _zoom_for(lat0 - half_lat, lat0 + half_lat, lon0 - half_lon, lon0 + half_lon)
    return {'center': {'lat': lat0, 'lon': lon0}, 'zoom': zoom, 'box': box}


# ---------------------------------------------------------------- figure

def _fmt_p(p):
    return 'p < 0.001' if p < 0.001 else f'p = {p:.2g}'


def _hover(name, sid, row, col, stat, significant, in_analysis=True):
    label = si.INDICATORS[col][0]
    head = f'<b>{name}</b> ({sid})<br>'
    if np.isnan(row['value']):
        return head + f'{label}: fewer than {si.MIN_TREND_SEASONS} seasons ({int(row["n"])})'
    if stat == 'enso':
        body = f'{label}: r = {row["value"]:+.2f} with RONI'
    else:
        body = f'{label}: {row["value"]:+.1f} {units(col, stat)}'
    note = ' (significant)' if significant else ('' if in_analysis else ' (outside the current selection)')
    return head + body + f'<br>{_fmt_p(row["p"])}, {int(row["n"])} seasons' + note


def significant_stations(stats, in_analysis, fdr=False):
    """
    Stations with a significant trend or correlation. With fdr, the false discovery rate is controlled across
    the stations in the current analysis (a single station is simply tested at p < 0.05).
    """
    p = stats['p'].to_numpy(dtype=float)
    plain = np.nan_to_num(p, nan=1.0) < SIGNIFICANT
    if not fdr or in_analysis.sum() <= 1:
        return pd.Series(plain & in_analysis, index=stats.index)
    sig = np.zeros(len(p), dtype=bool)
    sig[in_analysis] = si.fdr_significant(p[in_analysis], FDR_Q)
    return pd.Series(sig, index=stats.index)


def draw_trend_map(stations, stats, col, stat, selected, members, view, uirevision, fdr=False):
    """
    stations: DataFrame (index station_id) with name, latitude, longitude; stats: station_stats() for them;
    selected: the station chosen on the tab (green halo); members: the stations in the current analysis (the
    station itself, or its sub-basin or region), or None for all of BC; view: view_for().
    Only stations in the analysis are coloured; the others are light grey. Clicking a station reports its id
    as customdata[0].
    """
    stats = stats.reindex(stations.index)
    in_analysis = stations.index.isin(members) if members is not None else np.ones(len(stations), dtype=bool)
    has_value = stats['value'].notna().to_numpy()
    sig = significant_stations(stats, in_analysis, fdr).to_numpy() & has_value
    colors = np.array(value_colors(stats['value'], col, stat), dtype=object)
    colors[~in_analysis & has_value] = OUT_COLOR
    colors[~has_value] = FEW_COLOR
    size = np.where(has_value, 15, 8)
    opacity = np.where(has_value & ~in_analysis, 0.75, 1.0)
    hover = [_hover(r['name'], sid, stats.loc[sid], col, stat, bool(s), bool(a))
             for (sid, r), s, a in zip(stations.iterrows(), sig, in_analysis)]
    custom = list(zip(stations.index, hover))

    fig = go.Figure()

    def halo(mask, size_, color):
        if mask.any():
            fig.add_trace(go.Scattermap(
                lon=stations['longitude'][mask], lat=stations['latitude'][mask], mode='markers',
                marker=dict(size=size_, color=color), hoverinfo='skip', showlegend=False,
                customdata=[c for c, m in zip(custom, mask) if m],
            ))

    halo(np.asarray(stations.index == selected), 23, SELECT_COLOR)      # the selected station, outermost
    halo(sig, 19, RING_COLOR)                                           # significance ring
    fig.add_trace(go.Scattermap(
        lon=stations['longitude'], lat=stations['latitude'], mode='markers',
        marker=dict(size=list(size), color=list(colors), opacity=list(opacity)),
        customdata=custom, hovertemplate='%{customdata[1]}<extra></extra>', showlegend=False,
    ))
    # No map_bounds here: with a bounding box, MapLibre clamps the centre before plotly applies the new zoom,
    # which sent a jump from the all-of-BC view to a station off to central BC.
    fig.update_layout(
        clickmode='event',
        map={'center': view['center'], 'zoom': view['zoom'], 'style': snowmap.basemap_style()},
        margin=dict(l=0, r=0, b=0, t=0),
        hoverlabel=dict(bgcolor='white', font_size=14),
        uirevision=uirevision,
    )
    return fig


def key_note(fdr):
    test = 'false discovery rate controlled at 10% across the selection' if fdr else 'p < 0.05'
    return (f'Colours: stations in the current selection. Dark ring: significant ({test}). Light grey: outside the '
            f'selection. Small dark grey: fewer than {si.MIN_TREND_SEASONS} seasons in the period. Green halo: the '
            'selected station.')
