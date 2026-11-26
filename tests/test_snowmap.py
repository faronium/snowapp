import numpy as np
import pandas as pd
from plotly.colors import unlabel_rgb

import snowmap


def test_basemap_is_openstreetmap_without_a_token(monkeypatch):
    monkeypatch.setattr(snowmap, 'MAPBOX_TOKEN', '')
    assert snowmap.basemap_style() == 'open-street-map'
    assert snowmap.mapbox_wordmark() is None


def test_basemap_is_mapbox_outdoors_with_a_token(monkeypatch):
    monkeypatch.setattr(snowmap, 'MAPBOX_TOKEN', 'pk.test')
    style = snowmap.basemap_style()
    source = style['sources']['mapbox-outdoors']
    assert source['tiles'] == ['https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/tiles/512/{z}/{x}/{y}@2x'
                               '?access_token=pk.test']
    assert source['tileSize'] == 512
    assert '© Mapbox' in source['attribution'] and 'Improve this map' in source['attribution']
    assert style['layers'] == [{'id': 'mapbox-outdoors', 'type': 'raster', 'source': 'mapbox-outdoors'}]
    assert snowmap.mapbox_wordmark() is not None


def test_anomaly_colors_endpoints_and_missing_values():
    colors = snowmap.anomaly_colors([10, 25, 100, 175, 400, np.nan])
    rgb = lambda c: tuple(round(float(v)) for v in unlabel_rgb(c))
    assert rgb(colors[0]) == rgb(colors[1]) == rgb(snowmap.ANOM_COLORSCALE[0])     # at or below 25%: darkest red
    assert rgb(colors[3]) == rgb(colors[4]) == rgb(snowmap.ANOM_COLORSCALE[-1])    # at or above 175%: darkest blue
    assert colors[5] == snowmap.NO_ANOMALY_COLOR


def test_legend_ticks_line_up_with_the_colour_scale():
    legend = snowmap.anomaly_legend()
    bar, ticks, title = legend.children
    tops = {t.children: t.style['top'] for t in ticks.children}
    # 175% at the top of the bar, 25% at the bottom, evenly spaced in between.
    assert tops['≥175'] == '0%' and tops['100'] == '50%' and tops['≤25'] == '100%'
    assert bar.style['background'].startswith(f'linear-gradient(to top, {snowmap.ANOM_COLORSCALE[0]}')
    assert legend.style == {'display': 'none'}


def test_draw_station_map_uses_the_configured_basemap(monkeypatch):
    stations = pd.DataFrame({'name': ['A'], 'latitude': [50.0], 'longitude': [-120.0], 'pct_of_median': [80.0],
                             'hover': ['A']}, index=['S1'])
    monkeypatch.setattr(snowmap, 'MAPBOX_TOKEN', 'pk.test')
    fig = snowmap.draw_station_map(stations, show_anomaly=True)
    assert fig.layout.map.style['sources']['mapbox-outdoors']['tileSize'] == 512
    assert len(fig.data) == 1                      # no hidden colour-bar trace any more
