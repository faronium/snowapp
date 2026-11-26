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


def test_view_zooms_to_the_selection():
    assert tm.view_for([], [], 'bc') == tm.BC_VIEW
    station = tm.view_for([50.0], [-123.0], 'station')
    assert station['center'] == {'lat': 50.0, 'lon': -123.0}
    assert 6.0 < station['zoom'] < 7.5                                       # about +/-100 km on a ~470 px map
    lone = tm.view_for([50.0], [-123.0], 'subbasin')                         # one-station group: +/-50 km minimum
    assert lone['zoom'] > station['zoom']
    wide = tm.view_for([49.0, 56.0], [-128.0, -118.0], 'region')
    assert wide['zoom'] < station['zoom'] and wide['center'] == {'lat': 52.5, 'lon': -123.0}


def test_station_stats_in_percent_per_decade():
    years = np.arange(1990, 2020)
    swe = pd.Series(1000 * 0.98 ** (years - 1990), index=years)            # -2% a year
    ind = {'S1': pd.DataFrame({c: swe for c in si.COLUMNS})}
    stats = tm.station_stats(ind, ['S1', 'S2'], 'peak_swe', pd.Series(0.0, index=years), start=1990)
    assert stats.loc['S1', 'value'] == pytest.approx(100 * (0.98 ** 10 - 1), rel=1e-6)   # about -18.3%/decade
    assert stats.loc['S1', 'p'] < 0.001 and stats.loc['S1', 'n'] == 30
    assert np.isnan(stats.loc['S2', 'value']) and stats.loc['S2', 'n'] == 0


def test_draw_trend_map_highlights_only_a_selection():
    stations = pd.DataFrame({'name': ['A', 'B'], 'latitude': [50.0, 51.0], 'longitude': [-123.0, -124.0]}, index=['S1', 'S2'])
    stats = pd.DataFrame({'value': [-5.0, np.nan], 'p': [0.01, np.nan], 'n': [20, 4]}, index=['S1', 'S2'])
    view = tm.view_for([50.0], [-123.0], 'station')
    fig = tm.draw_trend_map(stations, stats, 'snow_off_day', 'trend', ['S1'], view, 'S1')
    assert len(fig.data) == 3                     # selection halo, significance ring, stations
    assert fig.layout.uirevision == 'S1' and fig.layout.map.zoom == pytest.approx(view['zoom'])
    fig = tm.draw_trend_map(stations, stats, 'snow_off_day', 'trend', None, tm.BC_VIEW, 'bc')
    assert len(fig.data) == 2                     # no halo for all of BC
