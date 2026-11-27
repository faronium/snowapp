import math

import numpy as np
import pandas as pd
import pytest

import snowindicators as si
import snowtrendmap as tm


def test_fdr_benjamini_hochberg():
    p = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216]
    # Thresholds k * 0.05 / 10: only the two smallest p-values pass (0.039 > 0.015).
    assert list(si.fdr_significant(p, q=0.05)) == [True, True] + [False] * 8
    # At q = 0.10 the cut-off is the largest k with p(k) <= k * 0.01: k = 6 (0.06 <= 0.06), so the 3rd and
    # 4th values count too even though they miss their own thresholds.
    assert list(si.fdr_significant(p, q=0.10)) == [True] * 6 + [False] * 4
    assert list(si.fdr_significant([np.nan, 0.5])) == [False, False]


@pytest.mark.parametrize('col, toward_less_snow', [
    ('snow_off_day', -10), ('snow_on_day', +10), ('peak_swe', -15), ('season_days', -15), ('peak_day', -10)])
def test_red_marks_change_toward_less_snow(col, toward_less_snow):
    assert tm._scale_position([toward_less_snow], col, 'trend')[0] == 0        # the red end of RdBu
    assert tm._scale_position([-toward_less_snow], col, 'trend')[0] == 1       # the blue end
    assert tm._scale_position([0], col, 'trend')[0] == 0.5


def test_melt_rate_uses_a_sequential_scale():
    assert list(tm._scale_position([-15, 0, 15], 'melt_rate', 'trend')) == [0, 0.5, 1]
    assert tm._scale('melt_rate')[0] != tm._scale('snow_off_day')[0]


def test_correlation_colours_follow_the_same_directions():
    assert tm._scale_position([-0.6], 'snow_off_day', 'enso')[0] == 0          # earlier snow-off in El Niño: red
    assert tm._scale_position([+0.6], 'snow_on_day', 'enso')[0] == 0           # later snow-on in El Niño: red


def test_key_puts_red_where_the_values_are():
    bar, ticks, title = tm.key('snow_off_day', 'trend')
    gradient = bar.style['background']
    first = gradient.split('(', 1)[1].split(', rgb')[0]
    assert first.startswith('to top') and 'rgb(103' in gradient.split('to top, ')[1][:20]   # red at the bottom
    assert ticks.children[0].children.startswith('≥+10') and title.children == 'Snow-off date: days/decade'


def test_view_boxes_for_a_station_a_group_and_bc():
    station = tm.view_for([50.0], [-123.0], 'station')
    assert station['center'] == {'lat': 50.0, 'lon': -123.0}
    (w, s), (e, n) = station['box']
    assert (n - s) * 111 == pytest.approx(200)                              # +/-100 km north-south
    assert (e - w) * 111 * math.cos(math.radians(50)) == pytest.approx(200)  # and east-west
    lone = tm.view_for([50.0], [-123.0], 'subbasin')                         # one-station group: +/-50 km minimum
    assert lone['box'][1][1] - lone['box'][0][1] == pytest.approx(100 / 111)
    bc = tm.view_for([49.0, 59.5], [-135.0, -115.0], 'bc')                  # all stations, with a margin
    (w, s), (e, n) = bc['box']
    assert w < -135 and e > -115 and s < 49 and n > 59.5
    assert bc['zoom'] < station['zoom']


def test_station_stats_in_percent_per_decade():
    years = np.arange(1990, 2020)
    swe = pd.Series(1000 * 0.98 ** (years - 1990), index=years)            # -2% a year
    ind = {'S1': pd.DataFrame({c: swe for c in si.COLUMNS})}
    stats = tm.station_stats(ind, ['S1', 'S2'], 'peak_swe', pd.Series(0.0, index=years), start=1990)
    assert stats.loc['S1', 'value'] == pytest.approx(100 * (0.98 ** 10 - 1), rel=1e-6)   # about -18.3%/decade
    assert stats.loc['S1', 'p'] < 0.001 and stats.loc['S1', 'n'] == 30
    assert np.isnan(stats.loc['S2', 'value']) and stats.loc['S2', 'n'] == 0


def stations_and_stats():
    stations = pd.DataFrame({'name': ['A', 'B', 'C', 'D'], 'latitude': [50.0, 51.0, 52.0, 53.0],
                             'longitude': [-123.0, -124.0, -125.0, -126.0]}, index=['S1', 'S2', 'S3', 'S4'])
    stats = pd.DataFrame({'value': [-5.0, 2.0, np.nan, -8.0], 'p': [0.01, 0.5, np.nan, 0.001], 'n': [20, 20, 4, 20]},
                         index=stations.index)
    return stations, stats


def test_only_stations_in_the_analysis_are_coloured():
    stations, stats = stations_and_stats()
    view = tm.view_for([50.0, 51.0], [-123.0, -124.0], 'subbasin')
    fig = tm.draw_trend_map(stations, stats, 'snow_off_day', 'trend', 'S2', ['S1', 'S2', 'S3'], view, 'subbasin:x')
    halo, ring, main = fig.data
    assert [c[0] for c in halo.customdata] == ['S2']                 # only the chosen station
    assert [c[0] for c in ring.customdata] == ['S1']                 # S4 is significant but outside the selection
    colors, opacity, size = list(main.marker.color), list(main.marker.opacity), list(main.marker.size)
    assert colors[3] == tm.OUT_COLOR and opacity[3] < 1              # outside: light grey
    assert colors[2] == tm.FEW_COLOR and opacity[2] == 1 and size[2] < size[0]   # too few seasons: small, opaque
    assert colors[0] not in (tm.OUT_COLOR, tm.FEW_COLOR) and opacity[0] == 1
    assert fig.layout.map.bounds.west is None                         # no bounding box to clamp the view
    assert fig.layout.uirevision == 'subbasin:x'


def test_fdr_counts_only_the_stations_in_the_analysis():
    stations, stats = stations_and_stats()
    stats['p'] = [0.04, 0.5, np.nan, 0.001]
    # S1 alone at p = 0.04: tested plainly at p < 0.05 when it is the whole analysis.
    one = tm.significant_stations(stats, np.array([True, False, False, False]), fdr=True)
    assert list(one) == [True, False, False, False]
    everyone = tm.significant_stations(stats, np.ones(4, dtype=bool), fdr=True)
    assert everyone['S4'] and not everyone['S2']


def test_station_trends_for_peak_swe_are_in_percent_and_match_the_figure():
    import snowtrends
    years = np.arange(1995, 2020)
    rng = np.random.default_rng(3)
    swe = pd.Series(1000 * 0.97 ** (years - 1995) * np.exp(rng.normal(0, 0.15, len(years))), index=years)
    ind = pd.DataFrame({c: swe for c in si.COLUMNS})
    enso = pd.Series(rng.normal(0, 1, len(years)), index=years)
    fig = snowtrends.indicator_timeseries(ind, enso, 'S1')
    title = fig.layout.annotations[0].text
    assert title.startswith('Peak SWE: -') and '%/decade' in title
    stats = tm.station_stats({'S1': ind}, ['S1'], 'peak_swe', enso)
    assert f"{stats.loc['S1', 'value']:+.1f}%/decade" in title             # the map and the figure agree
    assert stats.loc['S1', 'p'] == pytest.approx(si.mann_kendall(years, swe.to_numpy()))   # p doesn't depend on the scale
