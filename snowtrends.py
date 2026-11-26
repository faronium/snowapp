"""
Figures for the Trends tab: a station's snow season indicators by water year (with Theil-Sen trend lines and
Mann-Kendall significance) or against the water year's ENSO index (with a fitted line and correlation).
Indicators come from snowindicators.py.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import snowindicators as si

PANELS = ['peak_swe', 'peak_day', 'snow_on_day', 'snow_off_day', 'season_days', 'melt_rate']
PHASE_COLORS = {'El Niño': 'rgb(255,110,95)', 'La Niña': 'rgb(0,175,245)', 'Neutral': 'rgb(128,128,128)',
                'No RONI': 'rgb(200,200,200)'}
SIGNIFICANT = 0.05

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


def _date_axis(fig, row, col):
    vals, text = zip(*_DATE_TICKS)
    fig.update_yaxes(tickmode='array', tickvals=list(vals), ticktext=list(text), row=row, col=col)


def _empty(message):
    fig = go.Figure()
    fig.add_annotation(text=message, xref='paper', yref='paper', x=0.5, y=0.5, showarrow=False, font=dict(size=16))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _grid(titles):
    return make_subplots(rows=3, cols=2, subplot_titles=titles, vertical_spacing=0.11, horizontal_spacing=0.09)


def _phase_legend(fig):
    """One legend entry per ENSO phase (the points themselves are drawn without legend entries)."""
    for phase in ['El Niño', 'Neutral', 'La Niña']:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', name=phase,
                                 marker=dict(size=9, color=PHASE_COLORS[phase])), row=1, col=1)


def _layout(fig, title):
    fig.update_layout(
        title=dict(text=title, font=dict(size=17), y=0.99, yanchor='top'),
        margin=dict(l=10, r=10, t=75, b=10),
        legend=dict(orientation='h', x=1, xanchor='right', y=1.07, yanchor='bottom'),
        hovermode='closest',
        plot_bgcolor='rgb(229,236,246)',
    )
    fig.update_annotations(font_size=13)
    return fig


def indicator_timeseries(indicators, enso, title):
    """Each indicator by water year, coloured by ENSO phase, with a Theil-Sen trend line when n >= 10."""
    if indicators.empty:
        return _empty('No complete seasons for this station')
    years = indicators.index.to_numpy()
    phases = [enso_phase(enso.get(wy)) for wy in years]
    titles, traces = [], []
    for col in PANELS:
        label = si.INDICATORS[col][0]
        t = si.trend(years, indicators[col])
        if 'slope' in t:
            titles.append(f'{label}: {_slope_text(col, t["slope_per_decade"])}, {_fmt_p(t["p"])}')
        else:
            titles.append(f'{label}: too few seasons for a trend (n = {t["n"]})')
        traces.append(t)
    fig = _grid(titles)
    for k, col in enumerate(PANELS):
        row, c = k // 2 + 1, k % 2 + 1
        v = indicators[col]
        ok = v.notna().to_numpy()
        hover = [f'WY{wy}: {_fmt_value(col, val)}<br>RONI {enso.get(wy, np.nan):+.2f} ({ph})'
                 for wy, val, ph, o in zip(years, v, phases, ok) if o]
        fig.add_trace(go.Scatter(
            x=years[ok], y=v[ok], mode='markers', showlegend=False, hovertext=hover, hoverinfo='text',
            marker=dict(size=8, color=[PHASE_COLORS[p] for p, o in zip(phases, ok) if o], line=dict(width=0.5, color='white')),
        ), row=row, col=c)
        t = traces[k]
        if 'slope' in t:
            xs = np.array([years[ok].min(), years[ok].max()])
            fig.add_trace(go.Scatter(
                x=xs, y=t['intercept'] + t['slope'] * xs, mode='lines', showlegend=False, hoverinfo='skip',
                line=dict(color='rgb(40,40,40)', width=2, dash='solid' if t['p'] < SIGNIFICANT else 'dash'),
            ), row=row, col=c)
        if si.INDICATORS[col][2]:
            _date_axis(fig, row, c)
        else:
            fig.update_yaxes(title_text=si.INDICATORS[col][1], row=row, col=c)
    _phase_legend(fig)
    return _layout(fig, title)


def indicator_vs_enso(indicators, enso, title):
    """Each indicator against the water year's RONI, with a least-squares line and correlation when n >= 10."""
    if indicators.empty:
        return _empty('No complete seasons for this station')
    years = indicators.index.to_numpy()
    x = np.array([enso.get(wy, np.nan) for wy in years], dtype=float)
    phases = [enso_phase(v) for v in x]
    titles, rels = [], []
    for col in PANELS:
        label = si.INDICATORS[col][0]
        r = si.enso_relationship(x, indicators[col])
        rels.append(r)
        if 'r' in r:
            titles.append(f'{label}: r = {r["r"]:+.2f}, {_fmt_p(r["p"])} (n = {r["n"]})')
        else:
            titles.append(f'{label}: too few seasons (n = {r["n"]})')
    fig = _grid(titles)
    for k, col in enumerate(PANELS):
        row, c = k // 2 + 1, k % 2 + 1
        y = indicators[col].to_numpy(dtype=float)
        ok = ~np.isnan(x) & ~np.isnan(y)
        hover = [f'WY{wy}: {_fmt_value(col, val)}<br>RONI {e:+.2f} ({ph})'
                 for wy, val, e, ph, o in zip(years, y, x, phases, ok) if o]
        fig.add_trace(go.Scatter(
            x=x[ok], y=y[ok], mode='markers', showlegend=False, hovertext=hover, hoverinfo='text',
            marker=dict(size=8, color=[PHASE_COLORS[p] for p, o in zip(phases, ok) if o], line=dict(width=0.5, color='white')),
        ), row=row, col=c)
        r = rels[k]
        if 'r' in r:
            xs = np.array([x[ok].min(), x[ok].max()])
            fig.add_trace(go.Scatter(
                x=xs, y=r['intercept'] + r['slope'] * xs, mode='lines', showlegend=False, hoverinfo='skip',
                line=dict(color='rgb(40,40,40)', width=2, dash='solid' if r['p'] < SIGNIFICANT else 'dash'),
            ), row=row, col=c)
        if si.INDICATORS[col][2]:
            _date_axis(fig, row, c)
        else:
            fig.update_yaxes(title_text=si.INDICATORS[col][1], row=row, col=c)
        fig.update_xaxes(zeroline=True, zerolinecolor='rgb(160,160,160)', row=row, col=c)
    for c in (1, 2):
        fig.update_xaxes(title_text='Relative Oceanic Niño Index (RONI)', row=3, col=c)
    _phase_legend(fig)
    return _layout(fig, title)
