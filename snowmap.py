"""
The station map: the figure, its basemap, and the HTML pieces layered over it (the anomaly colour legend
and the Mapbox wordmark). The overlays are styled in assets/map-overlays.css.
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


def draw_station_map(stations, show_anomaly):
    """
    stations: DataFrame indexed by station_id with name, latitude, longitude, pct_of_median and hover
    (see datastore.build_snapshot). Clicking a marker reports the station_id as customdata[0].
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
        selected=dict(marker={'size': 26, 'color': 'rgba(0,250,131,0.75)'}),
        showlegend=False,
    ))
    fig.update_layout(
        clickmode='event+select',
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

def anomaly_legend():
    """
    The colour key for the anomaly colours, as HTML laid over the map's top-right corner. Plotly can only
    place a colour bar at a fraction of the map's width and height, so it can't keep equal pixel gaps from
    the top and right edges as the map changes size; CSS can.
    """
    gradient = f'linear-gradient(to top, {", ".join(ANOM_COLORSCALE)})'   # first colour (red, 25%) at the bottom
    span = ANOM_MAX - ANOM_MIN
    ticks = [html.Div(label, className='anom-legend-tick', style={'top': f'{100 * (ANOM_MAX - value) / span:g}%'})
             for value, label in ANOM_TICKS]
    return html.Div(
        [
            html.Div(className='anom-legend-bar', style={'background': gradient}),
            html.Div(ticks, className='anom-legend-ticks'),
            html.Div('% of median', className='anom-legend-title'),
        ],
        id='anom-legend',
        className='anom-legend',
        style={'display': 'none'},
    )


def mapbox_wordmark():
    """The Mapbox logo, which Mapbox requires on maps that use its tiles (none when not using Mapbox)."""
    if not uses_mapbox():
        return None
    return html.A('Mapbox', href='https://www.mapbox.com/', target='_blank', className='mapbox-logo',
                  title='Mapbox')
