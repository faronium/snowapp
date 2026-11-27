"""
The station maps: the main tab's figure, the basemap shared by both maps, and the HTML pieces layered over
the maps (colour keys and the Mapbox wordmark). The overlays are styled in assets/map-overlays.css.
"""
import os

import pandas as pd
import plotly.graph_objects as go
from dash import html
from plotly.colors import diverging, sample_colorscale

# ColorBrewer red-blue: red below the median, blue above. Colours saturate outside 25-175%.
ANOM_COLORSCALE = diverging.RdBu
ANOM_MIN, ANOM_MAX = 25, 175
ANOM_TICKS = [(175, '≥175'), (150, '150'), (125, '125'), (100, '100'), (75, '75'), (50, '50'), (25, '≤25')]
NO_ANOMALY_COLOR = 'rgb(200,200,200)'   # no recent reading, no median, or too little snow normally
PLAIN_COLOR = 'rgba(0,175,245,0.7)'

# Basemap. With a Mapbox token (a public "pk." token, URL-restricted to the site's domain in the Mapbox
# account), the map uses Mapbox Outdoors as raster tiles from the Static Tiles API. Plotly's map is drawn
# with MapLibre, which can't load mapbox:// styles directly, so this is the approach Mapbox documents for
# MapLibre. Without a token (e.g. local development) it falls back to OpenStreetMap.
MAPBOX_TOKEN = os.environ.get('MAPBOX_TOKEN', '').strip()
MAPBOX_STYLE = 'mapbox/outdoors-v12'
MAPBOX_ATTRIBUTION = (
    '<a href="https://www.mapbox.com/about/maps/" target="_blank">© Mapbox</a> '
    '<a href="https://www.openstreetmap.org/copyright" target="_blank">© OpenStreetMap</a> '
    '<a href="https://apps.mapbox.com/feedback/" target="_blank"><strong>Improve this map</strong></a>'
)


def uses_mapbox():
    return bool(MAPBOX_TOKEN)


def basemap_style():
    """The map style: Mapbox Outdoors raster tiles if a token is configured, otherwise OpenStreetMap."""
    if not uses_mapbox():
        return 'open-street-map'
    tiles = (f'https://api.mapbox.com/styles/v1/{MAPBOX_STYLE}/tiles/512/{{z}}/{{x}}/{{y}}@2x'
             f'?access_token={MAPBOX_TOKEN}')
    return {
        'version': 8,
        'sources': {
            'mapbox-outdoors': {
                'type': 'raster',
                'tiles': [tiles],
                'tileSize': 512,   # Mapbox recommends 512 px tiles; 256 px tiles take four times the requests
                'attribution': MAPBOX_ATTRIBUTION,
            },
        },
        'layers': [{'id': 'mapbox-outdoors', 'type': 'raster', 'source': 'mapbox-outdoors'}],
    }


def anomaly_colors(pct):
    """Marker colour for each percent-of-median value (NaN gets NO_ANOMALY_COLOR)."""
    pct = pd.Series(pct, dtype=float)
    colors = pd.Series(NO_ANOMALY_COLOR, index=pct.index, dtype=object)
    ok = pct.notna()
    if ok.any():
        scaled = (pct[ok].clip(ANOM_MIN, ANOM_MAX) - ANOM_MIN) / (ANOM_MAX - ANOM_MIN)
        colors[ok] = sample_colorscale(ANOM_COLORSCALE, scaled.tolist())
    return colors.tolist()


def draw_station_map(stations, show_anomaly, selected=None):
    """
    stations: DataFrame indexed by station_id with name, latitude, longitude, pct_of_median and hover
    (see datastore.build_snapshot); selected: the chosen station, highlighted in green. Clicking a marker
    reports the station_id as customdata[0].
    """
    fig = go.Figure()
    fig.add_trace(go.Scattermap(
        lon=stations['longitude'],
        lat=stations['latitude'],
        mode='markers',
        customdata=list(zip(stations.index, stations['hover'])),
        hovertemplate='%{customdata[1]}<extra></extra>',
        marker=dict(
            size=18,
            opacity=1.0,
            color=anomaly_colors(stations['pct_of_median']) if show_anomaly else PLAIN_COLOR,
        ),
        # The chosen station (from the list or a click) is highlighted; the others keep their look.
        selectedpoints=[i for i, sid in enumerate(stations.index) if sid == selected],
        selected=dict(marker={'size': 26, 'color': 'rgba(0,250,131,0.75)'}),
        unselected=dict(marker={'opacity': 1.0}),
        showlegend=False,
    ))
    fig.update_layout(
        clickmode='event',
        uirevision='station-map',     # keep the user's zoom when the map is redrawn for another station
        map={
            'zoom': 3,
            'center': dict(lat=52.5, lon=-126),
            'style': basemap_style(),
        },
        margin=dict(l=0, r=0, b=0, t=0),
        map_bounds={'west': -142, 'east': -110, 'south': 45, 'north': 61},
        hoverlabel=dict(bgcolor='white', font_size=14),
    )
    return fig


# ---------------------------------------------------------------- overlays

def key_children(colors_bottom_to_top, ticks, title):
    """
    Contents of a colour key: a vertical colour bar (colours listed from bottom to top), tick labels
    ((position from the top in %, label) pairs) and a title running up the right-hand side.
    """
    gradient = f'linear-gradient(to top, {", ".join(colors_bottom_to_top)})'
    return [
        html.Div(className='map-legend-bar', style={'background': gradient}),
        html.Div([html.Div(label, className='map-legend-tick', style={'top': f'{top:g}%'}) for top, label in ticks],
                 className='map-legend-ticks'),
        html.Div(title, className='map-legend-title'),
    ]


def color_key(key_id, children=None, shown=False):
    """
    A colour key laid over a map's top-right corner. Plotly can only place a colour bar at a fraction of the
    map's width and height, so it can't keep equal pixel gaps from the top and right edges as the map changes
    size; CSS (assets/map-overlays.css) can.
    """
    return html.Div(children or [], id=key_id, className='map-legend', style={'display': 'flex' if shown else 'none'})


def anomaly_legend():
    """The colour key for the anomaly colours (red, 25%, at the bottom), shown when anomalies are switched on."""
    span = ANOM_MAX - ANOM_MIN
    ticks = [(100 * (ANOM_MAX - value) / span, label) for value, label in ANOM_TICKS]
    return color_key('anom-legend', key_children(ANOM_COLORSCALE, ticks, '% of median'))


def mapbox_wordmark():
    """The Mapbox logo, which Mapbox requires on maps that use its tiles (none when not using Mapbox)."""
    if not uses_mapbox():
        return None
    return html.A('Mapbox', href='https://www.mapbox.com/', target='_blank', className='mapbox-logo',
                  title='Mapbox')
