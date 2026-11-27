"""
Figures for the Trends tab. For a single station: its snow season indicators by water year (Theil-Sen trend lines
with Mann-Kendall significance) or against the water year's ENSO index (least-squares line and correlation). For a
group of stations (snowgroups.py): the regional series with each station's anomalies behind it, with the Regional
Kendall trend, or against RONI. Indicators come from snowindicators.py.
"""
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import snowgroups as sg
import snowindicators as si

PANELS = ['peak_swe', 'peak_day', 'snow_on_day', 'snow_off_day', 'season_days', 'melt_rate', 'melt_rate_3d']
PHASE_COLORS = {'El Niño': 'rgb(255,110,95)', 'La Niña': 'rgb(0,175,245)', 'Neutral': 'rgb(128,128,128)',
                'No RONI': 'rgb(200,200,200)'}
STATION_DOT = 'rgba(90,90,90,0.28)'
COUNTS_CELL = (4, 2)           # where the group views show the stations contributing each year
SIGNIFICANT = 0.05
PERCENT_TICKS = [25, 35, 50, 70, 100, 140, 200, 300]

# Tick marks for date axes: the 1st and 15th of each month, as days of the water year (from 1 September before
# the water year to 15 September at its end).
_DATE_TICKS = [(int(si.water_year_day([d], 2002)[0]), d.strftime('%-d %b'))
               for d in pd.date_range('2001-09-01', '2002-09-30') if d.day in (1, 15)]


def enso_phase(value):
    if pd.isna(value):
        return 'No RONI'
    return 'El Niño' if value >= 0.5 else 'La Niña' if value <= -0.5 else 'Neutral'


def _fmt_p(p):
    if pd.isna(p):
        return ''
    text = 'p < 0.001' if p < 0.001 else f'p = {p:.2g}'
    return f'<b>{text}</b>' if p < SIGNIFICANT else text


def _fmt_value(col, v):
    label, units, is_date = si.INDICATORS[col]
    if is_date:
        return si.water_year_day_label(v)
    return f'{v:,.0f} {units}' if units in ('mm', 'days') else f'{v:.1f} {units}'


def _slope_text(col, slope_per_decade):
    _, units, is_date = si.INDICATORS[col]
    per = 'days' if is_date else units
    if per == 'mm/day':
        return f'{slope_per_decade:+.1f} mm/day per decade'
    return f'{slope_per_decade:+.1f} {per}/decade' if abs(slope_per_decade) < 10 else f'{slope_per_decade:+,.0f} {per}/decade'


def _group_slope_text(analysis):
    t = analysis['trend']
    if analysis['log']:
        return f'{100 * (math.exp(t["slope_per_decade"]) - 1):+.1f}%/decade'
    return f'{t["slope_per_decade"]:+.1f} days/decade'


def _to_display(values, is_log):
    values = np.asarray(values, dtype=float)
    return 100 * np.exp(values) if is_log else values


def _fmt_anomaly(v, is_log):
    return f'{v:.0f}% of normal' if is_log else f'{v:+.0f} days'


def _date_axis(fig, row, col):
    vals, text = zip(*_DATE_TICKS)
    fig.update_yaxes(tickmode='array', tickvals=list(vals), ticktext=list(text), row=row, col=col)


def _anomaly_axis(fig, row, col, is_log):
    if is_log:
        fig.update_yaxes(type='log', tickmode='array', tickvals=PERCENT_TICKS, ticksuffix='%', title_text='% of normal',
                         row=row, col=col)
    else:
        fig.update_yaxes(title_text='days from normal', zeroline=True, zerolinecolor='rgb(160,160,160)', row=row, col=col)


def _empty(message):
    fig = go.Figure()
    fig.add_annotation(text=message, xref='paper', yref='paper', x=0.5, y=0.5, showarrow=False, font=dict(size=16))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _grid(titles, with_counts=False):
    """
    A 4 x 2 grid for the seven panels. The eighth cell holds the number of stations contributing each year in
    the group views and is left empty for a single station.
    """
    fig = make_subplots(rows=4, cols=2, vertical_spacing=0.075, horizontal_spacing=0.09,
                        subplot_titles=list(titles) + ['Stations contributing each year' if with_counts else ''])
    if not with_counts:
        fig.update_xaxes(visible=False, row=COUNTS_CELL[0], col=COUNTS_CELL[1])
        fig.update_yaxes(visible=False, row=COUNTS_CELL[0], col=COUNTS_CELL[1])
    return fig


def _station_counts(fig, analyses):
    """
    Bar chart of the number of stations contributing to the regional series each year (the most for any
    indicator). Years with too few stations to enter the series are drawn lighter.
    """
    counts = pd.concat([_counts(a) for a in analyses.values() if not a['stations'].empty], axis=1)
    if counts.empty:
        return
    n = counts.max(axis=1).astype(int).sort_index()
    n = n[n > 0]
    used = n >= sg.MIN_STATIONS_PER_YEAR
    fig.add_trace(go.Bar(
        x=n.index, y=n.values, showlegend=False,
        marker=dict(color=['rgb(110,110,110)' if u else 'rgb(200,200,200)' for u in used], line=dict(width=0)),
        hovertext=[f'WY{wy}: {v} station{"s" if v != 1 else ""}' + ('' if u else ' (too few for the regional series)')
                   for wy, v, u in zip(n.index, n.values, used)],
        hoverinfo='text',
    ), row=COUNTS_CELL[0], col=COUNTS_CELL[1])
    fig.update_yaxes(title_text='stations', rangemode='tozero', row=COUNTS_CELL[0], col=COUNTS_CELL[1])
    fig.update_xaxes(title_text='Water year', row=COUNTS_CELL[0], col=COUNTS_CELL[1])


def _cell(k):
    return k // 2 + 1, k % 2 + 1


def _phase_legend(fig, with_stations=False):
    """Legend entries for the ENSO phases (and the faint station points); the data traces have no entries."""
    for phase in ['El Niño', 'Neutral', 'La Niña']:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', name=phase,
                                 marker=dict(size=9, color=PHASE_COLORS[phase])), row=1, col=1)
    if with_stations:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', name='Individual stations',
                                 marker=dict(size=6, color=STATION_DOT)), row=1, col=1)


GROUP_NOTE = 'larger markers: more stations reported that year'


def _layout(fig, title, *notes):
    subtitle = ' \u00b7 '.join(n for n in notes if n)
    fig.update_layout(
        title=dict(text=title, font=dict(size=17), y=0.99, yanchor='top',
                   subtitle=dict(text=subtitle or '', font=dict(size=12, color='rgb(110,110,110)'))),
        margin=dict(l=10, r=10, t=75, b=10),
        legend=dict(orientation='h', x=1, xanchor='right', y=1.07, yanchor='bottom'),
        hovermode='closest',
        plot_bgcolor='rgb(229,236,246)',
    )
    fig.update_annotations(font_size=13)
    return fig


def _points(fig, row, col, x, y, years, enso, hover, size=8):
    phases = [enso_phase(enso.get(wy)) for wy in years]
    fig.add_trace(go.Scatter(
        x=x, y=y, mode='markers', showlegend=False, hovertext=hover, hoverinfo='text',
        marker=dict(size=size, color=[PHASE_COLORS[p] for p in phases], line=dict(width=0.5, color='white')),
    ), row=row, col=col)


def _sizes(analysis, years):
    """Marker size for each year of a regional series: larger when more stations reported that year."""
    n = _counts(analysis)
    counts = np.array([n.get(wy, 0) for wy in years], dtype=float)
    top = max(counts.max(), 1) if len(counts) else 1
    return list(5 + 9 * np.sqrt(counts / top))


def _line(fig, row, col, xs, ys, p):
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode='lines', showlegend=False, hoverinfo='skip',
        line=dict(color='rgb(40,40,40)', width=2, dash='solid' if p < SIGNIFICANT else 'dash'),
    ), row=row, col=col)


# ---------------------------------------------------------------- one station

def indicator_timeseries(indicators, enso, title, adjust_enso=False, subtitle=''):
    """Each indicator by water year, coloured by ENSO phase, with a Theil-Sen trend line when n >= 10."""
    if indicators.empty:
        return _empty('No snow season indicators for this station')
    years = indicators.index.to_numpy()
    series, titles, trends = {}, [], []
    for col in PANELS:
        # Peak SWE and melt rates are fitted on the log scale (as for groups and the map), so a trend is a
        # steady percentage change and a fall from 75% to 50% of normal counts more than one from 150% to 125%.
        is_log = col in sg.LOG_INDICATORS
        values = indicators[col]
        fit = np.log(values.where(values > 0)) if is_log else values
        if adjust_enso:
            fit, _ = sg.station_adjusted(fit, enso)
        series[col] = np.exp(fit) if is_log else fit
        t = si.trend(years, fit)
        t['log'] = is_log
        trends.append(t)
        label = si.INDICATORS[col][0]
        slope = (f'{100 * (math.exp(t["slope_per_decade"]) - 1):+.1f}%/decade' if is_log
                 else _slope_text(col, t['slope_per_decade'])) if 'slope' in t else ''
        titles.append(f'{label}: {slope}, {_fmt_p(t["p"])}' if 'slope' in t
                      else f'{label}: too few seasons for a trend (n = {t["n"]})')
    fig = _grid(titles)
    for k, col in enumerate(PANELS):
        row, c = _cell(k)
        v = series[col]
        ok = v.notna().to_numpy()
        hover = [f'WY{wy}: {_fmt_value(col, val)}{" (ENSO removed)" if adjust_enso else ""}'
                 f'<br>RONI {enso.get(wy, np.nan):+.2f} ({enso_phase(enso.get(wy))})'
                 for wy, val in zip(years[ok], v[ok])]
        _points(fig, row, c, years[ok], v[ok], years[ok], enso, hover)
        t = trends[k]
        if 'slope' in t:
            if t['log']:                                    # a steady percentage change: a gentle curve in mm
                xs = np.linspace(years[ok].min(), years[ok].max(), 30)
                _line(fig, row, c, xs, np.exp(t['intercept'] + t['slope'] * xs), t['p'])
            else:
                xs = np.array([years[ok].min(), years[ok].max()])
                _line(fig, row, c, xs, t['intercept'] + t['slope'] * xs, t['p'])
        if si.INDICATORS[col][2]:
            _date_axis(fig, row, c)
        else:
            fig.update_yaxes(title_text=si.INDICATORS[col][1], row=row, col=c)
    _phase_legend(fig)
    return _layout(fig, title, subtitle, 'ENSO signal removed' if adjust_enso else '')


def indicator_vs_enso(indicators, enso, title, subtitle=''):
    """Each indicator against the water year's RONI, with a least-squares line and correlation when n >= 10."""
    if indicators.empty:
        return _empty('No snow season indicators for this station')
    years = indicators.index.to_numpy()
    x = np.array([enso.get(wy, np.nan) for wy in years], dtype=float)
    titles, rels = [], []
    for col in PANELS:
        r = si.enso_relationship(x, indicators[col])
        rels.append(r)
        label = si.INDICATORS[col][0]
        titles.append(f'{label}: r = {r["r"]:+.2f}, {_fmt_p(r["p"])} (n = {r["n"]})' if 'r' in r
                      else f'{label}: too few seasons (n = {r["n"]})')
    fig = _grid(titles)
    for k, col in enumerate(PANELS):
        row, c = _cell(k)
        y = indicators[col].to_numpy(dtype=float)
        ok = ~np.isnan(x) & ~np.isnan(y)
        hover = [f'WY{wy}: {_fmt_value(col, val)}<br>RONI {e:+.2f} ({enso_phase(e)})'
                 for wy, val, e in zip(years[ok], y[ok], x[ok])]
        _points(fig, row, c, x[ok], y[ok], years[ok], enso, hover)
        r = rels[k]
        if 'r' in r:
            xs = np.array([x[ok].min(), x[ok].max()])
            _line(fig, row, c, xs, r['intercept'] + r['slope'] * xs, r['p'])
        if si.INDICATORS[col][2]:
            _date_axis(fig, row, c)
        else:
            fig.update_yaxes(title_text=si.INDICATORS[col][1], row=row, col=c)
        fig.update_xaxes(zeroline=True, zerolinecolor='rgb(160,160,160)', row=row, col=c)
    for row, c in ((4, 1), (3, 2)):         # the lowest indicator panel in each column
        fig.update_xaxes(title_text='Relative Oceanic Niño Index (RONI)', row=row, col=c)
    _phase_legend(fig)
    return _layout(fig, title, subtitle)


# ---------------------------------------------------------------- a group of stations

def _station_cloud(fig, row, col, analysis, x_of_year):
    """Each station's anomalies (value minus its own level), faint, behind the regional series."""
    st = analysis['stations']
    if st.empty:
        return
    long = st.rename_axis(index='wy', columns='sid').reset_index().melt(id_vars='wy', var_name='sid', value_name='v').dropna()
    xs = np.array([x_of_year(wy) for wy in long['wy']], dtype=float)
    keep = ~np.isnan(xs)
    ys = _to_display(long['v'], analysis['log'])
    hover = [f'{sid} WY{wy}: {_fmt_anomaly(v, analysis["log"])}' for sid, wy, v in zip(long['sid'], long['wy'], ys)]
    fig.add_trace(go.Scatter(
        x=xs[keep], y=ys[keep], mode='markers', showlegend=False, hovertext=[h for h, k in zip(hover, keep) if k],
        hoverinfo='text', marker=dict(size=5, color=STATION_DOT),
    ), row=row, col=col)


def _fit_range(fig, row, col, analysis, series_display):
    """
    Y range covering the regional series and the middle 98% of the station points, so that a few extreme
    station values don't squash the panel (the toolbar's autoscale still shows everything).
    """
    st = analysis['stations']
    pts = _to_display(st.to_numpy().ravel(), analysis['log']) if not st.empty else np.array([])
    pts = pts[~np.isnan(pts)]
    ser = np.asarray(series_display, dtype=float)
    ser = ser[~np.isnan(ser)]
    if not len(ser):
        return
    lo, hi = ser.min(), ser.max()
    if len(pts):
        q1, q99 = np.percentile(pts, [1, 99])
        lo, hi = min(lo, q1), max(hi, q99)
    if analysis['log']:
        lo, hi = np.log10(lo), np.log10(hi)
    pad = 0.06 * (hi - lo if hi > lo else 1.0)
    fig.update_yaxes(range=[lo - pad, hi + pad], row=row, col=col)


def _counts(analysis):
    st = analysis['stations']
    return st.notna().sum(axis=1) if not st.empty else pd.Series(dtype=int)


def group_timeseries(analyses, enso, title, subtitle=''):
    """The regional series of each indicator by water year, with the Regional Kendall trend when n >= 10 years."""
    if all(a['series'].empty for a in analyses.values()):
        return _empty('Not enough stations with snow season indicators in this group')
    adjusted = any(a['adjusted'] for a in analyses.values())
    titles = []
    for col in PANELS:
        a, label = analyses[col], si.INDICATORS[col][0]
        t = a['trend']
        if 'slope' in t:
            titles.append(f'{label}: {_group_slope_text(a)}, {_fmt_p(t["p"])} ({t["n"]} years, {a["n_stations"]} stations)')
        elif a['n_stations'] == 0 or a['series'].empty:
            titles.append(f'{label}: not enough stations')
        else:
            titles.append(f'{label}: too few years for a trend (n = {t["n"]})')
    fig = _grid(titles, with_counts=True)
    for k, col in enumerate(PANELS):
        row, c = _cell(k)
        a = analyses[col]
        _anomaly_axis(fig, row, c, a['log'])
        if a['series'].empty:
            continue
        _station_cloud(fig, row, c, a, lambda wy: wy)
        years, n_by_year = a['series'].index.to_numpy(), _counts(a)
        y = _to_display(a['series'], a['log'])
        hover = [f'WY{wy}: {_fmt_anomaly(v, a["log"])} ({int(n_by_year.get(wy, 0))} stations)'
                 f'<br>RONI {enso.get(wy, np.nan):+.2f} ({enso_phase(enso.get(wy))})' for wy, v in zip(years, y)]
        _points(fig, row, c, years, y, years, enso, hover, size=_sizes(a, years))
        _fit_range(fig, row, c, a, y)
        t = a['trend']
        if 'slope' in t:
            xs = np.array([years.min(), years.max()], dtype=float)
            _line(fig, row, c, xs, _to_display(t['intercept'] + t['slope'] * xs, a['log']), t['p'])
    _station_counts(fig, analyses)
    _phase_legend(fig, with_stations=True)
    return _layout(fig, title, subtitle, 'ENSO signal removed' if adjusted else '', GROUP_NOTE)


def group_vs_enso(analyses, enso, title, subtitle=''):
    """The regional series of each indicator against RONI, with a least-squares line and correlation."""
    if all(a['series'].empty for a in analyses.values()):
        return _empty('Not enough stations with snow season indicators in this group')
    titles = []
    for col in PANELS:
        a, label = analyses[col], si.INDICATORS[col][0]
        r = a['enso_rel']
        titles.append(f'{label}: r = {r["r"]:+.2f}, {_fmt_p(r["p"])} ({r["n"]} years, {a["n_stations"]} stations)' if 'r' in r
                      else f'{label}: too few years (n = {r["n"]})')
    fig = _grid(titles, with_counts=True)
    roni = lambda wy: enso.get(wy, np.nan)
    for k, col in enumerate(PANELS):
        row, c = _cell(k)
        a = analyses[col]
        _anomaly_axis(fig, row, c, a['log'])
        fig.update_xaxes(zeroline=True, zerolinecolor='rgb(160,160,160)', row=row, col=c)
        if a['series'].empty:
            continue
        _station_cloud(fig, row, c, a, roni)
        years = a['series'].index.to_numpy()
        x = np.array([roni(wy) for wy in years], dtype=float)
        ok = ~np.isnan(x)
        y = _to_display(a['series'], a['log'])
        hover = [f'WY{wy}: {_fmt_anomaly(v, a["log"])}<br>RONI {e:+.2f} ({enso_phase(e)})'
                 for wy, v, e in zip(years[ok], y[ok], x[ok])]
        _points(fig, row, c, x[ok], y[ok], years[ok], enso, hover, size=_sizes(a, years[ok]))
        _fit_range(fig, row, c, a, y)
        r = a['enso_rel']
        if 'r' in r:
            xs = np.array([x[ok].min(), x[ok].max()])
            _line(fig, row, c, xs, _to_display(r['intercept'] + r['slope'] * xs, a['log']), r['p'])
    for row, c in ((4, 1), (3, 2)):         # the lowest indicator panel in each column
        fig.update_xaxes(title_text='Relative Oceanic Niño Index (RONI)', row=row, col=c)
    _station_counts(fig, analyses)
    _phase_legend(fig, with_stations=True)
    return _layout(fig, title, subtitle, GROUP_NOTE)
