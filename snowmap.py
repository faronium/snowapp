"""
The station map.
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import diverging, sample_colorscale

# ColorBrewer red-blue: red below the median, blue above. Colours saturate outside 25-175%.
ANOM_COLORSCALE = diverging.RdBu
ANOM_MIN, ANOM_MAX = 25, 175
NO_ANOMALY_COLOR = 'rgb(200,200,200)'   # no recent reading, no median, or too little snow normally
PLAIN_COLOR = 'rgba(0,175,245,0.7)'


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
    if show_anomaly:
        # A trace with no points, there only to draw the colour bar for the colours computed above.
        fig.add_trace(go.Scattermap(
            lon=[None], lat=[None], mode='markers', hoverinfo='skip', showlegend=False,
            marker=dict(
                color=[100], colorscale=ANOM_COLORSCALE, cmin=ANOM_MIN, cmax=ANOM_MAX, showscale=True,
                colorbar=dict(
                    title=dict(text='% of median', side='right'),
                    tickvals=[25, 50, 75, 100, 125, 150, 175],
                    ticktext=['≤25', '50', '75', '100', '125', '150', '≥175'],
                    thickness=12, len=0.5, x=0.99, xanchor='right', y=0.5,
                    bgcolor='rgba(255,255,255,0.75)',
                ),
            ),
        ))
    fig.update_layout(
        clickmode='event+select',
        map={
            'zoom': 3,
            'center': dict(lat=52.5, lon=-126),
            'style': 'open-street-map',
        },
        margin=dict(l=0, r=0, b=0, t=0),
        map_bounds={'west': -142, 'east': -110, 'south': 45, 'north': 61},
        hoverlabel=dict(bgcolor='white', font_size=14),
    )
    return fig
