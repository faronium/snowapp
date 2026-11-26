"""
The water-year SWE line plot for one station.
"""
import plotly.graph_objects as go

from snowdata import QUANTILES, SEASON_DAYS, season_quantiles, season_span

# Ranges are only drawn when at least this many complete seasons are available.
MIN_SEASONS_FOR_RANGE = 5

QUANTILE_DASH = {0.05: '3, 4', 0.25: None, 0.75: None, 0.95: '3, 4'}


def _band(x, lower, upper, **kwargs):
    """A filled polygon between two curves: along the lower one, then back along the upper one."""
    return go.Scatter(
        x=list(x) + list(x[::-1]),
        y=list(lower) + list(upper[::-1]),
        fill='toself',
        line_color='rgba(255,255,255,0)',
        hoverinfo='skip',
        **kwargs,
    )


def snow_lineplot(matrix, complete_seasons, selected_years, current_wy, fillarea, fillline, plottitle):
    """
    matrix:            season_matrix for the station (day of water year x water year)
    complete_seasons:  complete past seasons, used for the full-record median and ranges
    selected_years:    water years whose ENSO value is in the slider's range
    current_wy:        the current water year, always drawn in black
    fillarea/fillline: colours for the ENSO-selected range and median
    """
    m = matrix.iloc[:SEASON_DAYS]
    x = m.index
    selected = set(int(y) for y in selected_years)
    selected_complete = [wy for wy in complete_seasons if wy in selected]
    q_all = season_quantiles(m, complete_seasons)
    q_sel = season_quantiles(m, selected_complete)

    fig = go.Figure()
    # Full record: range and median, in grey.
    if len(complete_seasons) >= MIN_SEASONS_FOR_RANGE:
        fig.add_trace(_band(x, q_all[0.1587], q_all[0.8413], fillcolor='rgba(100,100,100,0.2)',
                            legendgroup='fullrecord', name='1σ range'))
    if complete_seasons:
        fig.add_trace(go.Scatter(x=x, y=q_all[0.5], line_color='rgb(100,100,100)', legendgroup='fullrecord',
                                 name=f'Median ({season_span(complete_seasons)})'))
    # Seasons in the selected ENSO range: range and median, in red or blue.
    if len(selected_complete) >= MIN_SEASONS_FOR_RANGE:
        fig.add_trace(_band(x, q_sel[0.1587], q_sel[0.8413], fillcolor=fillarea,
                            legendgroup='onisub', name='1σ selected range'))
    if selected_complete:
        n = len(selected_complete)
        fig.add_trace(go.Scatter(x=x, y=q_sel[0.5], line_color=fillline, legendgroup='onisub',
                                 name=f'Selected median ({n} season{"s" if n != 1 else ""})'))

    # Other percentiles of the full record, hidden until clicked in the legend.
    for q, dash in QUANTILE_DASH.items():
        if complete_seasons:
            fig.add_trace(go.Scatter(
                x=x, y=q_all[q], visible='legendonly', legend='legend3',
                name=f'{100 * q:0.1f}%-ile',
                line=dict(color='rgba(75,75,75,0.8)', width=1.25, dash=dash),
            ))

    # Individual seasons in the selected ENSO range, hidden until clicked in the legend.
    for wy in m.columns:
        if wy in selected and wy != current_wy:
            fig.add_trace(go.Scatter(x=x, y=m[wy], visible='legendonly', name=str(int(wy)), legend='legend2'))

    # The current season, if the station has data for it.
    if current_wy in m.columns:
        fig.add_trace(go.Scatter(x=x, y=m[current_wy], name=str(current_wy), line_color='rgb(0,0,0)',
                                 legend='legend2'))

    if not fig.data:
        fig.add_annotation(text='No data for this station', xref='paper', yref='paper', x=0.5, y=0.5,
                           showarrow=False, font=dict(size=16))

    fig.update_layout(
        title=dict(text=plottitle, font=dict(size=18), y=0.98, yanchor='top'),
        margin={'r': 0, 't': 35, 'l': 0, 'b': 0},
        xaxis=dict(
            type='category',
            tickfont=dict(size=14),
            tickmode='array',
            tickvals=['10-01', '11-01', '12-01', '01-01', '02-01', '03-01', '04-01', '05-01', '06-01', '07-01', '08-01'],
            ticktext=['1 Oct', '1 Nov', '1 Dec', '1 Jan', '1 Feb', '1 Mar', '1 Apr', '1 May', '1 Jun', '1 Jul', '1 Aug'],
        ),
        yaxis_title=dict(text='Snow Water Equivalent (mm)', font=dict(size=16)),
        yaxis=dict(tickfont=dict(size=14)),
        legend=dict(orientation='h', x=0.0, y=1),
        legend2=dict(orientation='h', yanchor='top', y=-0.10, xanchor='left', x=0.0),
        legend3=dict(orientation='v', y=1, x=0.85),
    )
    return fig
