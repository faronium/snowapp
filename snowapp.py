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
from dash import Dash, Input, Output, State, ctx, dcc, html, no_update

import datastore
import snowdata
from documentation import analysis_desc_md, footer_text_md, how_to_md
import snowmap
import snowtrendmap
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
    '''
    The Trends tab: snow season indicators for a station or a group of stations, by water year or against
    RONI, with a map of every station's trend (or ENSO relationship) for one indicator.
    '''
    options = [{'label': f"{sid} {row['name']} ({int(row['n_seasons']) if pd.notna(row['n_seasons']) else 0} complete seasons)",
                'value': sid} for sid, row in snap.stations.iterrows()]
    radio = dict(labelStyle={'display': 'block', 'margin': '4px 0'})
    controls = dbc.Card([
        dbc.CardHeader("Trend Controls", style=CARD_HEADER_STYLE),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Label("Station (or click one on a map)"),
                    dcc.Dropdown(id='trend-station', options=options, value=default_station, clearable=False),
                    html.Label("Map shows", className='mt-2'),
                    dcc.Dropdown(id='trend-map-indicator', clearable=False, value='snow_off_day',
                                 options=[{'label': snowtrendmap.si.INDICATORS[c][0], 'value': c} for c in PANELS]),
                ], width=12, lg=4),
                dbc.Col([
                    html.Label("Show"),
                    dcc.RadioItems(
                        id='trend-level', value='station', **radio,
                        options=[{'label': ' This station', 'value': 'station'},
                                 {'label': ' Its sub-basin (first two characters of the code)', 'value': 'subbasin'},
                                 {'label': ' Its region (first character)', 'value': 'region'},
                                 {'label': ' All of BC', 'value': 'bc'}],
                    ),
                ], width=12, lg=3),
                dbc.Col([
                    html.Label("View"),
                    dcc.RadioItems(id='trend-view', value='timeseries', **radio,
                                   options=[{'label': ' Indicators by water year', 'value': 'timeseries'},
                                            {'label': ' Indicators vs RONI', 'value': 'enso'}]),
                    html.Label("Period", className='mt-1'),
                    dcc.RadioItems(id='trend-period', value='1990', **radio,
                                   options=[{'label': ' Since 1990', 'value': '1990'},
                                            {'label': ' Full record', 'value': 'full'}]),
                ], width=12, lg=2),
                dbc.Col([
                    dcc.Checklist(id='trend-fixed', options=fixed_options(disabled=True), value=[],
                                  style={'opacity': 0.45}),
                    dcc.Checklist(id='trend-adjust', options=adjust_options(disabled=False), value=[],
                                  className='mt-2'),
                    dcc.Checklist(id='trend-fdr', value=[], className='mt-2', options=[{
                        'label': ' Map: control the false discovery rate across stations', 'value': 'fdr'}]),
                ], width=12, lg=3),
            ]),
        ]),
        dbc.CardFooter(
            "Indicators are calculated for each complete season. For a station, trends are Theil-Sen slopes with "
            "Mann-Kendall significance; for a group, its stations are combined into a regional series and tested "
            "with the Regional Kendall test. Lines against RONI are least-squares fits with Pearson correlation. "
            "Lines are solid where p < 0.05 and need at least 10 seasons. Methods are on the Analysis tab.",
            className='small text-muted',
        ),
    ], className='shadow')
    trend_map = html.Div([
        dcc.Graph(id='trend-map', config={'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d']},
                  style={'height': '78vh'}),
        snowmap.color_key('trend-legend', shown=True),
        mapbox_wordmark(),
        dcc.Store(id='trend-map-box'),
        dcc.Store(id='trend-map-fitted'),
    ], className='map-wrapper')
    return dbc.Tab([
        dbc.Row([dbc.Col([controls], width=12, className='mt-3 mb-4')]),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Trends Map", style=CARD_HEADER_STYLE),
                    dbc.CardBody([trend_map]),
                    dbc.CardFooter(id='trend-map-note', className='small text-muted'),
                ], className='shadow'),
            ], width=12, lg=4, className='mb-4'),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Indicators", style=CARD_HEADER_STYLE),
                    dbc.CardBody([dcc.Graph(id='trend-graph', style={'height': '78vh'})]),
                ], className='shadow'),
            ], width=12, lg=8, className='mb-4'),
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
            dcc.Store(id='resize-trigger'),
            dbc.Tabs(
                id='tabs',
                children=[
                    dbc.Tab([
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
                                ], className="shadow")
                            ], width=12, className="mt-3 mb-4"),
                        ]),
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


# Graphs first drawn while hidden (in a tab that isn't showing, or behind the intro dialog) keep plotly's default
# size of 700 x 450. Resize every visible graph when a tab is opened or the dialog closes, so maps and plots fill
# their panels (and the colour keys, which are sized to the panel, stay on the map).
snowapp.clientside_callback(
    '''function(tab, dialogOpen) {
        setTimeout(function() {
            if (!window.Plotly) { return; }
            document.querySelectorAll('.js-plotly-plot').forEach(function(gd) {
                if (gd.offsetParent !== null) {
                    var resized = window.Plotly.Plots.resize(gd);
                    // The Trends map can't be fitted while hidden: fit it now if that's still to do.
                    if (gd.closest('#trend-map') && window.snowappFitTrendMap) {
                        Promise.resolve(resized).then(function() { window.snowappFitTrendMap(); });
                    }
                }
            });
        }, 100);
        return window.dash_clientside.no_update;
    }''',
    Output('resize-trigger', 'data'),
    Input('tabs', 'active_tab'),
    Input('pageload-modal', 'is_open'),
)

# Fit the Trends map to the selection's box with MapLibre's fitBounds, which frames it for the map's real size
# on any screen. Only when the selection changes, so a hand-set zoom survives changes of indicator or settings.
snowapp.clientside_callback(
    '''function(target) {
        if (!target) { return window.dash_clientside.no_update; }
        window.snowappTrendBox = target;
        window.snowappFitTrendMap = function() {
            var t = window.snowappTrendBox, tries = 0;
            if (window.snowappFittedRevision === t.revision) { return; }
            (function attempt() {
                var gd = document.querySelector('#trend-map .js-plotly-plot');
                var fl = gd && gd._fullLayout;
                var map = fl && fl.map && fl.map._subplot && fl.map._subplot.map;
                // Wait until the map is visible and plotly has applied the figure for this selection; otherwise
                // plotly's own centre and zoom would overwrite the fit.
                if (!map || !gd.offsetParent || fl.uirevision !== t.revision) {
                    if (tries++ < 50) { setTimeout(attempt, 100); }
                    return;
                }
                setTimeout(function() {
                    map.resize();
                    // Keep the stations clear of the colour key in the top-right corner.
                    var key = document.getElementById('trend-legend');
                    var right = key && key.offsetWidth ? key.offsetWidth + 24 : 12;
                    // The originalEvent makes plotly record the fitted view as if the user had set it, so
                    // later figure updates for the same selection (uirevision) keep it.
                    map.fitBounds(t.box, {padding: {top: 12, bottom: 12, left: 12, right: right},
                                          animate: false, maxZoom: 9}, {originalEvent: {type: 'fit'}});
                    window.snowappFittedRevision = t.revision;
                }, 150);
            })();
        };
        window.snowappFitTrendMap();
        return window.dash_clientside.no_update;
    }''',
    Output('trend-map-fitted', 'data'),
    Input('trend-map-box', 'data'),
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
        indicators=snap.indicators.get(sid),
    )


# ---------------------------------------------------------------- Trends tab

@snowapp.callback(
    Output('trend-station', 'value'),
    Input('snow-station-map', 'clickData'),
    Input('trend-map', 'clickData'),
    prevent_initial_call=True,
)
def follow_map_click(main_click, trend_click):
    '''A click on either map selects that station on the Trends tab.'''
    snap = datastore.current()
    if snap is None:
        return no_update
    sid = station_from_click(trend_click if ctx.triggered_id == 'trend-map' else main_click, snap)
    return sid if sid in snap.stations.index else no_update


@snowapp.callback(
    Output('trend-map', 'figure'),
    Output('trend-legend', 'children'),
    Output('trend-map-note', 'children'),
    Output('trend-map-box', 'data'),
    Input('trend-station', 'value'),
    Input('trend-level', 'value'),
    Input('trend-view', 'value'),
    Input('trend-period', 'value'),
    Input('trend-adjust', 'value'),
    Input('trend-map-indicator', 'value'),
    Input('trend-fdr', 'value'),
)
def update_trend_map(sid, level, view, period, adjust, col, fdr):
    '''
    Every station coloured by the trend in (or ENSO correlation of) the chosen indicator, with the same period
    and ENSO setting as the figure, zoomed to the selected station or group.
    '''
    snap = datastore.current()
    if snap is None or sid is None:
        return no_update, no_update, no_update, no_update
    stat = 'enso' if view == 'enso' else 'trend'
    start = snowgroups.TREND_START if period == '1990' else None
    stations = snap.stations
    stats = snowtrendmap.station_stats(snap.indicators, stations.index, col, snap.enso, start, stat,
                                       adjust_enso=bool(adjust) and stat == 'trend')
    if level == 'bc':
        members, in_view, revision = None, stations, 'bc'
    else:
        members = snowgroups.group_members(list(stations.index), sid, level)
        in_view = stations.loc[members]
        # Keep a hand-set zoom while the selection stays the same (e.g. changing the indicator), re-centre otherwise.
        revision = sid if level == 'station' else f'{level}:{snowgroups.group_key(sid, level)}'
    view = snowtrendmap.view_for(in_view['latitude'], in_view['longitude'], level)
    fig = snowtrendmap.draw_trend_map(stations, stats, col, stat, sid, members, view, revision, fdr=bool(fdr))
    # The browser fits the map to this box (see fit_trend_map), once per change of selection.
    box = {'box': view['box'], 'revision': revision}
    return fig, snowtrendmap.key(col, stat), snowtrendmap.key_note(bool(fdr)), box


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
        title = f"{sid} {snap.stations['name'].get(sid, '')}"
        span = snowdata.season_span(list(indicators.index)) if len(indicators) else 'no complete seasons'
        if view == 'enso':
            return indicator_vs_enso(indicators, snap.enso, title, subtitle=f'Indicators vs RONI, {when} ({span})')
        return indicator_timeseries(indicators, snap.enso, title, adjust_enso=adjust,
                                    subtitle=f'Snow season indicators by water year, {when} ({span})')
    members = snowgroups.group_members(list(snap.indicators), sid, level)
    indicators = snowgroups.restrict_period(snap.indicators, members, start)
    analyses = {}
    for col in PANELS:
        use = snowgroups.fixed_network(indicators, members, col) if fixed else members
        analyses[col] = snowgroups.group_analysis(indicators, use, col, snap.enso, adjust_enso=adjust)
    label = snowgroups.group_label(snowgroups.group_key(sid, level), level)
    used = max(a['n_stations'] for a in analyses.values())
    title = f'{label}: {used} stations{", the same throughout" if fixed else ""}'
    if view == 'enso':
        return group_vs_enso(analyses, snap.enso, title, subtitle=f'Regional series vs RONI, {when}')
    return group_timeseries(analyses, snap.enso, title, subtitle=f'Regional series by water year, {when}')

if __name__ == '__main__':
    snowapp.run(debug=False)
