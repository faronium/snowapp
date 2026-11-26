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
             'melt_rate': None}    # sign of change toward less snow; None: no direction (sequential colours)
PERCENT = {'peak_swe', 'melt_rate'}
TREND_RANGE = {'peak_swe': 15, 'peak_day': 10, 'snow_on_day': 10, 'snow_off_day': 10, 'season_days': 15,
               'melt_rate': 15}    # colours saturate beyond +/- this many units per decade
R_RANGE = 0.6                      # ... and beyond +/- this correlation
SIGNIFICANT = 0.05
FDR_Q = 0.10
FEW_COLOR = 'rgb(185,185,185)'     # fewer than si.MIN_TREND_SEASONS seasons in the period
RING_COLOR = 'rgb(30,30,30)'       # ring around significant stations
SELECT_COLOR = 'rgb(0,220,120)'    # halo around the selected station or group (as on the main map)

# Approximate size of the map in pixels, for choosing a zoom level that fits a selection.
MAP_WIDTH_PX, MAP_HEIGHT_PX = 470, 560
BC_VIEW = {'center': {'lat': 52.5, 'lon': -126.0}, 'zoom': 3.0}
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
    """Map centre and zoom: about +/-100 km around a station, a group's stations with a margin, or all of BC."""
    lats, lons = np.asarray(lats, dtype=float), np.asarray(lons, dtype=float)
    if level == 'bc' or len(lats) == 0:
        return dict(BC_VIEW)
    lat0 = float((lats.min() + lats.max()) / 2)
    km_lat, km_lon = 111.0, 111.0 * math.cos(math.radians(lat0))
    if level == 'station':
        half_lat, half_lon = STATION_HALF_KM / km_lat, STATION_HALF_KM / km_lon
    else:
        half_lat = max((lats.max() - lats.min()) / 2 * (1 + GROUP_MARGIN), GROUP_MIN_HALF_KM / km_lat)
        half_lon = max((lons.max() - lons.min()) / 2 * (1 + GROUP_MARGIN), GROUP_MIN_HALF_KM / km_lon)
    lon0 = float((lons.min() + lons.max()) / 2)
    zoom = _zoom_for(lat0 - half_lat, lat0 + half_lat, lon0 - half_lon, lon0 + half_lon)
    return {'center': {'lat': lat0, 'lon': lon0}, 'zoom': zoom}


# ---------------------------------------------------------------- figure

def _fmt_p(p):
    return 'p < 0.001' if p < 0.001 else f'p = {p:.2g}'


def _hover(name, sid, row, col, stat, significant):
    label = si.INDICATORS[col][0]
    head = f'<b>{name}</b> ({sid})<br>'
    if np.isnan(row['value']):
        return head + f'{label}: fewer than {si.MIN_TREND_SEASONS} seasons ({int(row["n"])})'
    if stat == 'enso':
        body = f'{label}: r = {row["value"]:+.2f} with RONI'
    else:
        body = f'{label}: {row["value"]:+.1f} {units(col, stat)}'
    return head + body + f'<br>{_fmt_p(row["p"])}, {int(row["n"])} seasons' + (' (significant)' if significant else '')


def significant_stations(stats, fdr=False):
    p = stats['p'].to_numpy(dtype=float)
    if fdr:
        return pd.Series(si.fdr_significant(p, FDR_Q), index=stats.index)
    return pd.Series(np.nan_to_num(p, nan=1.0) < SIGNIFICANT, index=stats.index)


def draw_trend_map(stations, stats, col, stat, selected, view, uirevision, fdr=False):
    """
    stations: DataFrame (index station_id) with name, latitude, longitude; stats: station_stats() for them;
    selected: station ids of the current selection (one station or a group), or None for no highlight;
    view: view_for().
    Clicking a station reports its id as customdata[0].
    """
    stats = stats.reindex(stations.index)
    sig = significant_stations(stats, fdr)
    has_value = stats['value'].notna()
    highlight = selected is not None                     # None: no selection to highlight (all of BC)
    selected = stations.index.isin(selected) if highlight else np.ones(len(stations), dtype=bool)
    colors = value_colors(stats['value'], col, stat)
    base = np.where(has_value, np.where(sig, 1.0, 0.55), 0.8)
    opacity = np.where(selected, base, base * 0.6)
    size = np.where(has_value, 15, 8)
    hover = [_hover(r['name'], sid, stats.loc[sid], col, stat, bool(sig[sid])) for sid, r in stations.iterrows()]
    custom = list(zip(stations.index, hover))

    fig = go.Figure()

    def halo(mask, size_, color):
        if mask.any():
            fig.add_trace(go.Scattermap(
                lon=stations['longitude'][mask], lat=stations['latitude'][mask], mode='markers',
                marker=dict(size=size_, color=color), hoverinfo='skip', showlegend=False,
                customdata=[c for c, m in zip(custom, mask) if m],
            ))

    if highlight:
        halo(np.asarray(selected), 27, SELECT_COLOR)                  # selection, outermost
    halo(np.asarray(sig & has_value), 20, RING_COLOR)                 # significance ring
    fig.add_trace(go.Scattermap(
        lon=stations['longitude'], lat=stations['latitude'], mode='markers',
        marker=dict(size=list(size), color=colors, opacity=list(opacity)),
        customdata=custom, hovertemplate='%{customdata[1]}<extra></extra>', showlegend=False,
    ))
    fig.update_layout(
        clickmode='event',
        map={**view, 'style': snowmap.basemap_style()},
        map_bounds={'west': -142, 'east': -110, 'south': 45, 'north': 61},
        margin=dict(l=0, r=0, b=0, t=0),
        hoverlabel=dict(bgcolor='white', font_size=14),
        uirevision=uirevision,
    )
    return fig


def key_note(fdr):
    test = 'false discovery rate controlled at 10%, Benjamini-Hochberg' if fdr else 'p < 0.05'
    return (f'Dark ring: significant ({test}). Faded: not significant. Small grey: fewer than '
            f'{si.MIN_TREND_SEASONS} seasons in the period. Green halo: the current selection.')
