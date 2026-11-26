#!/usr/bin/env python
'''
ENSO Snow BC: a Dash app that plots water-year snow water equivalent at BC's automated snow pillow
stations, with controls to filter seasons by ENSO state and a map of current snowpack relative to median.

Author: Faron Anslow
E-mail: faron.anslow@gmail.com

How the pieces fit together:
  ingest.py     downloads the source data (below) into a SQLite database (snowdb.py)
  datastore.py  keeps an in-memory snapshot of that database for the callbacks, and refreshes it in a
                background thread every few hours
  snowdata.py   the analysis: water years, medians and ranges, current anomalies, ENSO by water year
  snowmap.py, snowplot.py   the two figures
  documentation.py          the text on the Analysis and Help tabs

Data sources:
  Snow data:        https://www.env.gov.bc.ca/wsd/data_searches/snow/asws/data/
  Station metadata: BC Data Catalogue, WHSE_WATER_MANAGEMENT.SSL_SNOW_ASWS_STNS_SP
  RONI:             https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt
                    (CPC switched its official ENSO index from ONI to the Relative ONI on 1 Feb 2026.)
'''
import logging

import dash_bootstrap_components as dbc
import pandas as pd
from dash import Dash, Input, Output, State, dcc, html, no_update

import datastore
import snowdata
from documentation import analysis_desc_md, footer_text_md, how_to_md
from snowmap import anomaly_legend, draw_station_map, mapbox_wordmark
from snowplot import snow_lineplot
import snowgroups
from snowtrends import PANELS, group_timeseries, group_vs_enso, indicator_timeseries, indicator_vs_enso

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

DEFAULT_STATION = '3A25P'   # Squamish River Upper
MIN_SEASONS_FILTER = 20     # for the "require 20 complete seasons" option

fillninoarea = 'rgba(255,110,95,0.3)'
fillninoline = 'rgb(255,110,95)'
fillninaarea = 'rgba(0,175,245,0.3)'
fillninaline = 'rgb(0,175,245)'

# Define color scheme - using a cohesive color palette
COLORS = {
    'primary': '#3E92CC',      # Blue
    'secondary': '#2A628F',    # Darker Blue
    'success': '#13A76C',      # Green
    'warning': '#FF934F',      # Orange
    'danger': '#DB5461',       # Red
    'info': '#5BC0BE',         # Teal
    'light': '#F2F4F8',        # Light Gray
    'dark': '#292F36',         # Dark Gray
    'bg': '#F2F4F8',           # Light background
    'text': '#292F36',         # Text color
}
CARD_HEADER_STYLE = {'background-color': COLORS['secondary'], 'color': 'white', 'font-weight': 'bold'}

snowapp = Dash(
    __name__,
    external_stylesheets=[dbc.themes.SANDSTONE],
    meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1'}],
    title='ENSO Snow BC: exploring snow accumulation and El Nino/La Nina in British Columbia',
    # The layout is built per page load and may be the "loading" page, which lacks the main components.
    suppress_callback_exceptions=True,
)
server = snowapp.server

# Start loading/refreshing data as soon as the app is imported, and make sure the refresh thread is
# still alive on every request.
datastore.ensure_running()
server.before_request(datastore.ensure_running)


@server.route('/healthz')
def healthz():
    '''Health check for the hosting platform. Returns 200 while the first data load is still running.'''
    snap = datastore.current()
    return {
        'status': 'ok' if snap else 'loading',
        'data_version': snap.version if snap else None,
        'data_through': snap.data_through.strftime('%Y-%m-%d') if snap else None,
    }


modal_header_image_path = 'assets/20250322_135400_small.jpg'

modal = dbc.Modal(
    [
        dbc.ModalBody(
            [
                dbc.Row([
                    dbc.Col([
                        html.H3("Multi-year Snow Water Equivalent Stratified by ENSO Strength",
                                className="text-center my-4",
                                style={'color': COLORS['dark'], 'font-weight': 'bold'}),
                        html.Div([html.Img(src=modal_header_image_path, className="mb-4",
                                           style={'height': '20%', 'width': '20%'})],
                                 style={'textAlign': 'center'}),
                        html.P('''This app allows exploration of the strong relationship between the El Niño Southern Oscillation (ENSO) and
                            snow accumulation in British Columbia. ENSO is correlated with temperature and precipitation in winter and
                            spring. This relationship partially explains the variability
                            in the province's snowpack from year to year.'''),
                        footer_text_md(dcc),
                    ], width=12)
                ]),
            ]
        ),
        dbc.ModalFooter(
            dbc.Button("Close", id="close-modal", className="ml-auto")
        ),
    ],
    id="pageload-modal",
    is_open=True,
    size="xl",
)

reclengthselect = html.Div(
    [
        dcc.Checklist(
            options=[
                {'label': 'Active stations only?', 'value': 'rcy'},
                {'label': f'require {MIN_SEASONS_FILTER} complete seasons?', 'value': 'rtmy'},
            ],
            value=['rcy', 'rtmy'],
            id='record-length-current-check',
        )
    ],
)

anomselect = html.Div(
    [
        dcc.Checklist(
            options=[
                {'label': 'Plot station anomalies?', 'value': 'anomstat'},
            ],
            value=[],
            id='show-anoms-stat',
        ),
    ],
)


def make_slider(start_range):
    return html.Div(
        [
            html.P("Filter by La Niña/El Niño Strength:"),
            dcc.RangeSlider(
                min=-3,
                max=3,
                step=0.1,
                marks={
                    -2.7: {'label': 'Extreme La Niña', 'style': {'color': fillninaline, "fontSize": "14px"}},
                    -1.3: {'label': 'Mod. La Niña', 'style': {'color': fillninaline, "fontSize": "14px"}},
                    -0.50: {'label': 'Neutral', 'style': {'color': 'rgb(80,80,80)', "fontSize": "14px"}},
                    0.50: {'label': 'Neutral', 'style': {'color': 'rgb(80,80,80)', "fontSize": "14px"}},
                    1.3: {'label': 'Mod. El Niño', 'style': {'color': fillninoline, "fontSize": "14px"}},
                    2.7: {'label': 'Extreme El Niño', 'style': {'color': fillninoline, "fontSize": "14px"}}
                },
                value=list(start_range),
                updatemode='drag',
                id='oni-range-slider',
                className='mb-4',
            ),
        ],
    )


def make_station_map_graph(default_station):
    return html.Div(
        [
            dcc.Graph(
                id="snow-station-map",
                # The station plotted when the page opens, in the same form a click on the map produces.
                clickData={'points': [{'customdata': [default_station]}]},
                # Remove the selection tools, which would be confused with selecting a station by clicking.
                config={'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d']},
                style={'height': "70vh"},
            ),
            # Laid over the map (see assets/map-overlays.css).
            anomaly_legend(),
            mapbox_wordmark(),
        ],
        className='map-wrapper',
    )


snowgraph = html.Div(
    [
        dcc.Graph(
            id="snow-station-graph",
            config={
                'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'autoScale2d'],
                'modeBarButtonsToAdd': ['v1hovermode'],
            },
            style={'height': "70vh"}
        ),
    ],
)


ADJUST_LABEL = ' Remove the ENSO (RONI) signal before testing trends'


def adjust_options(disabled):
    return [{'label': ADJUST_LABEL, 'value': 'adjust', 'disabled': disabled}]


FIXED_LABEL = ' Same stations throughout (each reported at least 80% of the seasons)'


def fixed_options(disabled):
    return [{'label': FIXED_LABEL, 'value': 'fixed', 'disabled': disabled}]


def make_trends_tab(snap, default_station):
    '''The Trends tab: snow season indicators for one station, by water year or against RONI.'''
    options = [{'label': f"{sid} {row['name']} ({row['n_seasons']} complete seasons)", 'value': sid}
               for sid, row in snap.stations.iterrows()]
    return dbc.Tab([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Snow Season Indicators", style=CARD_HEADER_STYLE),
                    dbc.CardBody([
                        html.Label("Station (or click one on the map)"),
                        dcc.Dropdown(id='trend-station', options=options, value=default_station, clearable=False),
                        html.Label("Show", className='mt-3'),
                        dcc.RadioItems(
                            id='trend-level',
                            options=[{'label': ' This station', 'value': 'station'},
                                     {'label': ' Its sub-basin (first two characters of the code)', 'value': 'subbasin'},
                                     {'label': ' Its region (first character)', 'value': 'region'},
                                     {'label': ' All of BC', 'value': 'bc'}],
                            value='station',
                            labelStyle={'display': 'block', 'margin': '6px 0'},
                        ),
                        html.Label("View", className='mt-3'),
                        dcc.RadioItems(
                            id='trend-view',
                            options=[{'label': ' Indicators by water year', 'value': 'timeseries'},
                                     {'label': ' Indicators vs RONI', 'value': 'enso'}],
                            value='timeseries',
                            labelStyle={'display': 'block', 'margin': '6px 0'},
                        ),
                        html.Label("Period", className='mt-3'),
                        dcc.RadioItems(
                            id='trend-period',
                            options=[{'label': ' Since 1990', 'value': '1990'},
                                     {'label': ' Full record', 'value': 'full'}],
                            value='1990',
                            labelStyle={'display': 'block', 'margin': '6px 0'},
                        ),
                        dcc.Checklist(
                            id='trend-fixed',
                            options=fixed_options(disabled=True),
                            value=[],
                            style={'opacity': 0.45},
                        ),
                        dcc.Checklist(
                            id='trend-adjust',
                            options=adjust_options(disabled=False),
                            value=[],
                            className='mt-2',
                        ),
                        html.P(
                            "Indicators are calculated for each complete season. For a station, trend lines are "
                            "Theil-Sen slopes with Mann-Kendall significance; for a group, the regional series "
                            "combines its stations and trends use the Regional Kendall test. Lines against RONI are "
                            "least-squares fits with Pearson correlation. Lines are solid where p < 0.05 and dashed "
                            "otherwise, and need at least 10 seasons (or years). Methods are on the Analysis tab.",
                            className='small text-muted mt-3 mb-0',
                        ),
                    ]),
                ], className='shadow mb-4'),
            ], width=12, lg=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Indicators", style=CARD_HEADER_STYLE),
                    dbc.CardBody([dcc.Graph(id='trend-graph', style={'height': '85vh'})]),
                ], className='shadow mb-4'),
            ], width=12, lg=9),
        ]),
    ], label='Trends')


def loading_layout():
    '''Shown until the first data load finishes (about a minute after a restart on a fresh database).'''
    return dbc.Container([
        html.H3('Loading the latest snow data…', className='mt-5'),
        html.P('This takes about a minute after the app restarts. The page will reload by itself.'),
        dcc.Interval(id='loading-poll', interval=5000),
        dcc.Store(id='loading-ready'),
    ], style={'padding': '20px'})


def serve_layout():
    '''Built on every page load, so the slider default and data status reflect the latest data.'''
    snap = datastore.current()
    if snap is None:
        return loading_layout()
    default_station = DEFAULT_STATION if DEFAULT_STATION in snap.stations.index else snap.stations.index[0]
    return dbc.Container(
        children=[
            modal,
            dbc.Tabs(
                children=[
                    dbc.Tab([
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("Snow Pillow Location Map", style=CARD_HEADER_STYLE),
                                    dbc.CardBody([make_station_map_graph(default_station)]),
                                ], className="shadow")
                            ], width=12, lg=4, className="mb-4"),
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("Water-year Snow Water Equivalent", style=CARD_HEADER_STYLE),
                                    dbc.CardBody([snowgraph]),
                                ], className="shadow")
                            ], width=12, lg=8, className="mb-4"),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("Data Selection Controls", style=CARD_HEADER_STYLE),
                                    dbc.CardBody([
                                        dbc.Row([
                                            dbc.Col([reclengthselect], width=2),
                                            dbc.Col([anomselect], width=2),
                                            dbc.Col([make_slider(snap.start_range)], width=8),
                                        ]),
                                    ]),
                                    dbc.CardFooter(datastore.status_text(snap), className='small text-muted'),
                                ])
                            ], width=12, className="mt-4"),
                        ]),
                    ], label='ENSO Snow BC'),
                    make_trends_tab(snap, default_station),
                    dbc.Tab(label='Analysis', children=[analysis_desc_md(dcc)]),
                    dbc.Tab(label='Help', children=[how_to_md(dcc)]),
                ]
            ),
            footer_text_md(dcc),
        ],
        id='page-content', fluid=True, style={'background-color': COLORS['bg'], "padding": "20px"},
    )


snowapp.layout = serve_layout


# ---------------------------------------------------------------- loading page: reload once data is ready

@snowapp.callback(Output('loading-ready', 'data'), Input('loading-poll', 'n_intervals'))
def check_loaded(_):
    return datastore.current() is not None


snowapp.clientside_callback(
    '''function(ready) {
        if (ready) { window.location.reload(); }
        return window.dash_clientside.no_update;
    }''',
    Output('loading-poll', 'disabled'),
    Input('loading-ready', 'data'),
)


# ---------------------------------------------------------------- main page

@snowapp.callback(
    Output("pageload-modal", "is_open"),
    Input("close-modal", "n_clicks"),
    State("pageload-modal", "is_open"),
)
def toggle_modal(n_clicks, is_open):
    if n_clicks:
        return False
    return is_open


@snowapp.callback(
    Output('snow-station-map', 'figure'),
    Output('anom-legend', 'style'),
    Input('record-length-current-check', 'value'),
    Input('show-anoms-stat', 'value'),
)
def make_station_map(reccheck, anomstat):
    '''
    Draw the station map, filtered by the checklist: 'rcy' keeps stations with data in the current
    water year, 'rtmy' keeps stations with at least MIN_SEASONS_FILTER complete seasons. The colour
    key is shown only when the stations are coloured by anomaly.
    '''
    snap = datastore.current()
    if snap is None:
        return no_update, no_update
    stations = snap.stations
    if 'rcy' in reccheck:
        stations = stations[stations['active']]
    if 'rtmy' in reccheck:
        stations = stations[stations['n_seasons'] >= MIN_SEASONS_FILTER]
    show_anomaly = bool(anomstat)
    legend_style = {'display': 'flex' if show_anomaly else 'none'}
    return draw_station_map(stations, show_anomaly=show_anomaly), legend_style


def station_from_click(click_data, snap):
    '''The station_id of the clicked marker (customdata[0]), falling back to the default station.'''
    try:
        sid = click_data['points'][0]['customdata'][0]
    except (TypeError, KeyError, IndexError):
        sid = None
    if sid not in snap.matrices:
        sid = DEFAULT_STATION if DEFAULT_STATION in snap.matrices else next(iter(snap.matrices))
    return sid


@snowapp.callback(
    Output('snow-station-graph', 'figure'),
    Input('oni-range-slider', 'value'),
    Input('snow-station-map', 'clickData'),
)
def update_line_chart(onirange, clickData):
    '''
    Plot the selected station's water years, with the median and range of the full record and of the
    seasons whose ENSO (RONI) value falls in the slider's range.
    '''
    snap = datastore.current()
    if snap is None:
        return no_update
    sid = station_from_click(clickData, snap)
    lo, hi = onirange
    selected_years = snap.enso.index[(snap.enso >= lo) & (snap.enso <= hi)]
    if (lo + hi) / 2 > 0:
        fillarea, fillline = fillninoarea, fillninoline
    else:
        fillarea, fillline = fillninaarea, fillninaline
    name = snap.stations['name'].get(sid, '')
    plottitle = f"Hydrologic Year SWE for {sid} {name}, Relative Oceanic Niño Index (RONI) {lo} to {hi}"
    return snow_lineplot(
        snap.matrices[sid],
        snap.complete[sid],
        selected_years,
        snap.current_wy,
        fillarea,
        fillline,
        plottitle=plottitle,
    )


# ---------------------------------------------------------------- Trends tab

@snowapp.callback(
    Output('trend-station', 'value'),
    Input('snow-station-map', 'clickData'),
    prevent_initial_call=True,
)
def follow_map_click(clickData):
    '''Clicking a station on the map also selects it on the Trends tab.'''
    snap = datastore.current()
    if snap is None:
        return no_update
    sid = station_from_click(clickData, snap)
    return sid if sid in snap.stations.index else no_update


@snowapp.callback(
    Output('trend-fixed', 'options'),
    Output('trend-fixed', 'style'),
    Input('trend-level', 'value'),
)
def toggle_fixed(level):
    '''"Same stations throughout" only applies to groups, so grey it out for a single station.'''
    disabled = level == 'station'
    return fixed_options(disabled), ({'opacity': 0.45} if disabled else {})


@snowapp.callback(
    Output('trend-adjust', 'options'),
    Output('trend-adjust', 'style'),
    Input('trend-view', 'value'),
)
def toggle_adjust(view):
    '''Removing the ENSO signal only applies to trends, so grey it out in the "vs RONI" view.'''
    disabled = view == 'enso'
    return adjust_options(disabled), ({'opacity': 0.45} if disabled else {})


@snowapp.callback(
    Output('trend-graph', 'figure'),
    Input('trend-station', 'value'),
    Input('trend-level', 'value'),
    Input('trend-view', 'value'),
    Input('trend-period', 'value'),
    Input('trend-fixed', 'value'),
    Input('trend-adjust', 'value'),
)
def update_trend_graph(sid, level, view, period, fixed, adjust):
    snap = datastore.current()
    if snap is None or sid is None:
        return no_update
    adjust = bool(adjust) and view == 'timeseries'    # removing ENSO only applies to the trend view
    start = snowgroups.TREND_START if period == '1990' else None
    when = f'since {start}' if start else 'full record'
    if level == 'station':
        indicators = snowgroups.restrict_period(snap.indicators, [sid], start).get(sid, pd.DataFrame())
        name = snap.stations['name'].get(sid, '')
        span = snowdata.season_span(list(indicators.index)) if len(indicators) else 'no complete seasons'
        if view == 'enso':
            return indicator_vs_enso(indicators, snap.enso, f'{sid} {name}: indicators vs RONI, {when} ({span})')
        return indicator_timeseries(indicators, snap.enso, f'{sid} {name}: snow season indicators, {when} ({span})',
                                    adjust_enso=adjust)
    members = snowgroups.group_members(list(snap.indicators), sid, level)
    indicators = snowgroups.restrict_period(snap.indicators, members, start)
    analyses = {}
    for col in PANELS:
        use = snowgroups.fixed_network(indicators, members, col) if fixed else members
        analyses[col] = snowgroups.group_analysis(indicators, use, col, snap.enso, adjust_enso=adjust)
    label = snowgroups.group_label(snowgroups.group_key(sid, level), level)
    used = max(a['n_stations'] for a in analyses.values())
    title = f'{label}: {used} stations{", the same throughout" if fixed else ""}, {when}'
    if view == 'enso':
        return group_vs_enso(analyses, snap.enso, f'{title}, regional series vs RONI')
    return group_timeseries(analyses, snap.enso, f'{title}, regional series by water year')

if __name__ == '__main__':
    snowapp.run(debug=False)
