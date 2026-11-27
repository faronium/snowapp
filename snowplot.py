"""
The water-year SWE line plot for one station.
"""
import numpy as np
import plotly.graph_objects as go
from plotly.colors import qualitative

from snowdata import ESTIMATE_NOTES, PLOT_DAYS, QUANTILES, season_quantiles, season_span
from snowindicators import water_year_day_label

# Colours for individual seasons (the current one is black).
SEASON_COLORS = qualitative.Plotly

# Season markers, drawn on a season's line and shown with it: (indicator column, symbol, label).
SEASON_MARKERS = [
    ('snow_on_day', 'triangle-up', 'Snow-on'),
    ('peak_day', 'diamond', 'Peak'),
    ('melt_day', 'triangle-down', 'Fastest melt'),
    ('snow_off_day', 'square', 'Snow-off'),
]
MARKER_KEY = '▲ snow-on  ◆ peak  ▼ fastest melt  ■ snow-off'
ESTIMATE_KEY = 'Grey shading: estimated values'
ESTIMATE_SHADE = 'rgba(60,60,60,0.35)'   # under a season's line where its values are estimates

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


def _wrap(text, width=70):
    """Break hover text into lines of about `width` characters."""
    lines, line = [], ''
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line); line = word
        else:
            line = f'{line} {word}'.strip()
    return '<br>'.join(lines + [line])


def _marker_text(col, label, wy, row):
    """Hover text for one season marker."""
    head = f'<b>{wy}</b> {label.lower() if col != "peak_day" else "peak"}: '
    if col == 'peak_day':
        return head + f'{row["peak_swe"]:.0f} mm on {water_year_day_label(row["peak_day"])} (5-day mean)'
    if col == 'melt_day':
        return head + f'{row["melt_rate"]:.1f} mm/day around {water_year_day_label(row["melt_day"])} (5-day mean)'
    return head + water_year_day_label(row[col])


def season_markers(season, row, wy, color, flags=None, **kwargs):
    """
    Markers on one season's line at its snow-on, peak, fastest-melt and snow-off dates (those it has).
    season: the season's daily SWE as plotted (index 'MM-DD' from 1 October); row: its indicators;
    flags: the season's estimate flags (snowdata.flag_matrix column), to note dates that fall on estimates.
    Snow-on in September is drawn at 1 October; dates past the end of the plot are left out.
    """
    x, y, symbols, text = [], [], [], []
    for col, symbol, label in SEASON_MARKERS:
        day = row.get(col, np.nan)
        if day is None or np.isnan(day) or day >= len(season):
            continue
        k = max(int(day), 0)
        x.append(season.index[k]); y.append(season.iloc[k]); symbols.append(symbol)
        note = ' (before 1 Oct)' if day < 0 else ''
        if flags is not None and day >= 0 and int(flags.iloc[k]) in ESTIMATE_NOTES:
            note += f'<br>on an {ESTIMATE_NOTES[int(flags.iloc[k])]}'
        text.append(_marker_text(col, label, wy, row) + note)
    if not x:
        return None
    return go.Scatter(
        x=x, y=y, mode='markers', showlegend=False, hovertemplate='%{text}<extra></extra>', text=text,
        marker=dict(symbol=symbols, size=12, color=color, line=dict(color='white', width=1.5)),
        **kwargs,
    )


def season_traces(x, season, wy, color, flags=None, flag_reason=None, **kwargs):
    """
    One season's line, with its estimated stretches shaded underneath and noted on hover.
    flags: the season's estimate flags (or None); flag_reason: for a flagged season, why it was flagged.
    """
    traces = []
    if flags is not None:
        estimated = flags.isin(list(ESTIMATE_NOTES)).to_numpy()
        if estimated.any():
            # Widen by a day each side so even a one-day estimate shows as a segment between its neighbours.
            shade = estimated | np.r_[estimated[1:], False] | np.r_[False, estimated[:-1]]
            traces.append(go.Scatter(
                x=x, y=np.where(shade, season.to_numpy(), np.nan), mode='lines', showlegend=False,
                line=dict(color=ESTIMATE_SHADE, width=9), hoverinfo='skip', **kwargs,
            ))
        notes = [f'<br><i>{ESTIMATE_NOTES[int(f)]}</i>' if int(f) in ESTIMATE_NOTES else '' for f in flags]
    else:
        notes = [''] * len(season)
    if flag_reason is not None:     # a faulty season: shown for reference, left out of every statistic
        name, line = f'{int(wy)} (flagged)', dict(color=color, dash='dot')
        head = f'<b>{int(wy)}</b> (flagged) %{{x}}: %{{y:.0f}} mm'
        tail = f'<br>Left out of medians, ranges and trends.<br>{_wrap(flag_reason)}'
    else:
        name, line = str(int(wy)), dict(color=color)
        head, tail = f'<b>{int(wy)}</b> %{{x}}: %{{y:.0f}} mm', ''
    traces.append(go.Scatter(x=x, y=season, name=name, line=line, customdata=notes,
                             hovertemplate=head + '%{customdata}' + tail + '<extra></extra>', **kwargs))
    return traces


def snow_lineplot(matrix, complete_seasons, selected_years, current_wy, fillarea, fillline, plottitle,
                  indicators=None, flagged=None, estimates=None):
    """
    matrix:            season_matrix for the station (day of water year x water year)
    complete_seasons:  complete past seasons, used for the full-record median and ranges
    selected_years:    water years whose ENSO value is in the slider's range
    current_wy:        the current water year, always drawn in black
    fillarea/fillline: colours for the ENSO-selected range and median
    indicators:        the station's season indicators (snowindicators.station_indicators), for markers on
                       each season's line; they show and hide with the season in the legend
    flagged:           {water year: reason} for the station's flagged seasons, drawn dotted and labelled
    estimates:         the station's estimate flags (snowdata.flag_matrix): estimated stretches are shaded
    """
    flagged = flagged or {}
    flags_for = lambda wy: (estimates[wy].iloc[:PLOT_DAYS]
                            if estimates is not None and wy in estimates.columns else None)
    m = matrix.iloc[:PLOT_DAYS]
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

    # Individual seasons in the selected ENSO range, hidden until clicked in the legend, each with its
    # season markers in the same legend group so they show and hide together.
    past = [wy for wy in m.columns if wy in selected and wy != current_wy]
    for i, wy in enumerate(past):
        color, group = SEASON_COLORS[i % len(SEASON_COLORS)], f'season-{int(wy)}'
        common = dict(visible='legendonly', legend='legend2', legendgroup=group)
        fig.add_traces(season_traces(x, m[wy], wy, color, flags_for(wy), flagged.get(wy), **common))
        if wy not in flagged and indicators is not None and wy in indicators.index:
            markers = season_markers(m[wy], indicators.loc[wy], int(wy), color, flags=flags_for(wy), **common)
            if markers is not None:
                fig.add_trace(markers)

    # The current season, if the station has data for it.
    if current_wy in m.columns:
        fig.add_traces(season_traces(x, m[current_wy], current_wy, '#000000', flags_for(current_wy),
                                     legend='legend2', legendgroup=f'season-{int(current_wy)}'))

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
        legend2=dict(orientation='h', yanchor='top', y=-0.10, xanchor='left', x=0.0,
                     title=dict(text=f'Seasons (click to show). Markers: {MARKER_KEY}. {ESTIMATE_KEY}.',
                                font=dict(size=13),
                                side='top')),
        legend3=dict(orientation='v', y=1, x=0.85),
    )
    return fig
