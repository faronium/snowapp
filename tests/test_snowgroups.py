import numpy as np
import pandas as pd
import pytest

import snowgroups as sg
import snowindicators as si


def test_group_keys_follow_the_station_code():
    assert sg.group_key('2D08P', 'subbasin') == '2D'
    assert sg.group_key('2D08P', 'region') == '2'
    assert sg.group_key('2D08P', 'bc') == 'BC'
    assert sg.group_key('2D08P', 'station') == '2D08P'
    ids = ['2D08P', '2D02P', '2F01AP', '3A25P']
    assert sg.group_members(ids, '2D08P', 'subbasin') == ['2D08P', '2D02P']
    assert sg.group_members(ids, '2D08P', 'region') == ['2D08P', '2D02P', '2F01AP']
    assert sg.group_label('2', 'region') == 'Region 2'


def staggered(trend=-0.5, offset_b=30.0):
    """Station A 1970-2025 and station B 2005-2025, sharing a year effect with a trend; B sits 30 above A."""
    years = np.arange(1970, 2026)
    effect = trend * (years - years.mean()) + 5 * np.sin(years)             # shared trend plus shared wiggles
    a = pd.Series(100 + effect, index=years)
    b = pd.Series(100 + offset_b + effect, index=years).where(years >= 2005)
    return pd.DataFrame({'A': a, 'B': b}), effect


def test_two_way_places_a_short_record_correctly():
    wide, effect = staggered()
    levels, effects = sg.two_way(wide)
    assert levels['B'] - levels['A'] == pytest.approx(30)
    # Year effects (only years with 2+ stations) match the true shared effect up to a constant.
    true = pd.Series(effect, index=wide.index)[effects.index]
    assert np.allclose(effects - effects.mean(), true - true.mean())


def test_station_own_mean_anomalies_would_dilute_the_trend():
    # Why the levels are estimated together: B's own-mean anomalies hide the decline B shares with A.
    wide, _ = staggered(trend=-1.0)
    own = wide - wide.mean()
    composite = own.mean(axis=1)
    naive_slope, _ = si.theil_sen(composite.index, composite.to_numpy())
    rk = sg.regional_kendall(wide)
    assert rk['slope'] == pytest.approx(-1.0, abs=0.05)      # pooled within-station slope: the true trend
    assert naive_slope > -0.95                                # the own-mean composite is pulled towards zero


def test_largest_connected_drops_a_station_with_no_shared_years():
    wide = pd.DataFrame({'A': [1, 2, 3, np.nan, np.nan, np.nan], 'B': [1, 2, np.nan, np.nan, np.nan, np.nan],
                         'C': [np.nan, np.nan, np.nan, 5, 6, 7]}, index=range(2000, 2006))
    assert list(sg._largest_connected(wide).columns) == ['A', 'B']


def test_regional_kendall_with_identical_stations_matches_one_station():
    years = np.arange(1990, 2015)
    y = 0.3 * (years - 1990) + np.random.default_rng(3).normal(size=len(years)) * 3
    one = si.mann_kendall(years, y)
    rk = sg.regional_kendall(pd.DataFrame({'A': y, 'B': y, 'C': y}, index=years))
    # Perfectly correlated stations carry no extra information, so the p-value shouldn't shrink.
    assert rk['p'] == pytest.approx(one, rel=0.1)


def test_regional_kendall_gains_power_from_independent_stations():
    years = np.arange(1990, 2015)
    rng = np.random.default_rng(4)
    base = 0.15 * (years - 1990)
    wide = pd.DataFrame({k: base + rng.normal(size=len(years)) * 2 for k in 'ABCDEF'}, index=years)
    single = np.median([si.mann_kendall(years, wide[k].to_numpy()) for k in wide])
    rk = sg.regional_kendall(wide)
    assert rk['p'] < single
    assert rk['slope'] == pytest.approx(0.15, abs=0.08)


def test_regional_kendall_handles_missing_years():
    wide, _ = staggered()
    rk = sg.regional_kendall(wide)
    assert 0 <= rk['p'] < 0.05 and rk['var'] > 0


def indicators_for(stations):
    """station_id -> indicator DataFrame with every indicator column set to the given series."""
    return {sid: pd.DataFrame({c: s for c in si.COLUMNS}) for sid, s in stations.items()}


def test_group_analysis_in_percent_for_peak_swe():
    years = np.arange(1980, 2020)
    ratio = np.where(years % 2 == 0, 1.2, 0.8)                 # alternate +20% / -20% years
    stations = {'2A01P': pd.Series(500 * ratio, index=years), '2A02P': pd.Series(2000 * ratio, index=years)}
    a = sg.group_analysis(indicators_for(stations), list(stations), 'peak_swe', pd.Series(0.0, index=years))
    assert a['log'] and a['n_stations'] == 2
    pct = 100 * np.exp(a['series'])
    assert pct[1980] / pct[1981] == pytest.approx(1.5)          # 1.2 / 0.8, the same at small and large stations


def test_group_analysis_needs_two_stations_per_year_and_five_seasons():
    years = np.arange(1980, 2000)
    stations = {'2A01P': pd.Series(np.arange(20.0), index=years),
                '2A02P': pd.Series(np.arange(20.0), index=years).where(years >= 1990),
                '2A03P': pd.Series(np.arange(20.0), index=years).where(years >= 1997)}   # only 3 seasons: left out
    a = sg.group_analysis(indicators_for(stations), list(stations), 'snow_off_day', pd.Series(0.0, index=years))
    assert a['n_stations'] == 2
    assert list(a['years']) == list(range(1990, 2000))


def test_removing_enso_reveals_a_masked_trend():
    years = np.arange(1970, 2026)
    rng = np.random.default_rng(5)
    roni = pd.Series(rng.normal(size=len(years)) * 1.0, index=years)
    shared = -0.15 * (years - 1970) + 12 * roni.to_numpy()      # a modest trend under a large ENSO signal
    stations = {f'1A0{k}P': pd.Series(shared + rng.normal(size=len(years)) * 2 + 10 * k, index=years) for k in range(5)}
    ind = indicators_for(stations)
    raw = sg.group_analysis(ind, list(stations), 'snow_off_day', roni)
    adj = sg.group_analysis(ind, list(stations), 'snow_off_day', roni, adjust_enso=True)
    assert adj['trend']['p'] < 0.01 < raw['trend']['p'] or adj['trend']['p'] < raw['trend']['p'] / 10
    assert adj['trend']['slope'] == pytest.approx(-0.15, abs=0.05)
    assert raw['enso_rel']['r'] > 0.8                            # the ENSO relationship itself is unchanged


def test_station_adjusted():
    years = np.arange(1990, 2020)
    roni = pd.Series(np.sin(years), index=years)
    values = pd.Series(100 + 5 * roni.to_numpy(), index=years)
    adjusted, slope = sg.station_adjusted(values, roni)
    assert slope == pytest.approx(5)
    assert adjusted.std() == pytest.approx(0, abs=1e-9)


def test_restrict_period():
    years = np.arange(1980, 2000)
    ind = indicators_for({'2A01P': pd.Series(1.0, index=years), '2A02P': pd.Series(2.0, index=years)})
    out = sg.restrict_period(ind, ['2A01P', '2A02P', '9Z99P'], 1990)
    assert set(out) == {'2A01P', '2A02P'}
    assert out['2A01P'].index.min() == 1990
    assert sg.restrict_period(ind, ['2A01P'], None)['2A01P'].index.min() == 1980


def test_fixed_network_keeps_stations_covering_the_period():
    years = np.arange(1990, 2010)                              # 20 seasons
    full = pd.Series(1.0, index=years)
    gappy = full.copy(); gappy.iloc[:3] = np.nan                # 17 of 20 = 85%: kept
    short = full.where(years >= 2000)                           # 10 of 20 = 50%: dropped
    ind = indicators_for({'2A01P': full, '2A02P': gappy, '2A03P': short})
    assert sg.fixed_network(ind, ['2A01P', '2A02P', '2A03P'], 'snow_off_day') == ['2A01P', '2A02P']
