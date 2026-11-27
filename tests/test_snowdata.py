import numpy as np
import pandas as pd
import pytest

import snowdata as sd


def daily(start, end, value=1.0):
    return pd.Series(value, index=pd.date_range(start, end, freq='D'), dtype=float)


def test_water_year_boundaries():
    wy = sd.water_year(pd.to_datetime(['2025-09-30', '2025-10-01', '2026-01-01']))
    assert list(wy) == [2025, 2026, 2026]


def test_water_year_days_run_oct_to_sep_without_feb_29():
    assert len(sd.WY_MONTH_DAYS) == 365
    assert sd.WY_MONTH_DAYS[0] == '10-01' and sd.WY_MONTH_DAYS[-1] == '09-30'
    assert '02-29' not in sd.WY_MONTH_DAYS


def test_season_matrix_lines_up_leap_and_non_leap_years():
    idx = pd.date_range('2023-10-01', '2025-09-30', freq='D')        # water years 2024 (leap) and 2025
    s = pd.Series(idx.month * 100 + idx.day, index=idx, dtype=float)  # value encodes the calendar date
    m = sd.season_matrix(s)
    assert list(m.columns) == [2024, 2025]
    assert m.loc['03-01'].tolist() == [301, 301]                       # same calendar day in both years
    assert m.loc['09-30'].tolist() == [930, 930]
    assert m.notna().all().all()


def test_season_matrix_places_a_partial_season_on_the_right_days():
    # The old pivot-and-slice reordering scrambled seasons with less than a full year of data.
    m = sd.season_matrix(daily('2026-10-01', '2026-11-25', 5.0))
    assert list(m.columns) == [2027]
    assert m.index[0] == '10-01'
    assert m.loc['10-01', 2027] == 5 and m.loc['11-25', 2027] == 5
    assert np.isnan(m.loc['11-26', 2027]) and np.isnan(m.loc['09-30', 2027])


def test_complete_seasons_threshold_and_exclusion():
    full = daily('2020-10-01', '2021-09-30')
    gappy = daily('2021-10-01', '2022-09-30')
    gappy.iloc[:30] = np.nan                       # 244 of the 274 days to 1 July: 89%, below 95%
    current = daily('2022-10-01', '2023-09-30')
    m = sd.season_matrix(pd.concat([full, gappy, current]))
    assert sd.complete_seasons(m) == [2021, 2023]
    assert sd.complete_seasons(m, exclude=[2023]) == [2021]


def test_station_climatology_uses_the_given_complete_seasons():
    seasons = [daily(f'{y - 1}-10-01', f'{y}-09-30', float(y - 2000)) for y in (2001, 2002, 2003, 2004)]
    m = sd.season_matrix(pd.concat(seasons))
    complete = {'X': sd.complete_seasons(m, exclude=[2004])}         # the current season is left out
    medians, info = sd.station_climatologies({'X': m}, complete)
    assert medians.loc['01-15', 'X'] == 2.0       # median of 1, 2, 3
    assert info.loc['X', 'n_seasons'] == 3
    assert info.loc['X', 'span'] == '3 seasons, 2001–2003'
    complete = {'X': sd.complete_seasons(m, exclude=[2004, 2003])}   # and a flagged one
    medians, info = sd.station_climatologies({'X': m}, complete)
    assert medians.loc['01-15', 'X'] == 1.5 and info.loc['X', 'n_seasons'] == 2


def spiky(values):
    return pd.DataFrame({'S': np.asarray(values, dtype=float)}, index=pd.date_range('2004-01-01', periods=len(values)))


def cleaned(values):
    swe, flags, counts = sd.clean(spiky(values) if not isinstance(values, pd.DataFrame) else values)
    return swe['S'], flags['S'], counts


def test_spikes_are_removed_and_filled():
    level = [400.0] * 20
    one = level.copy(); one[10] = 0.0                       # one-day dropout
    two = level.copy(); two[10] = two[11] = 5.0              # two-day dropout
    summer = [0.0] * 20; summer[8] = 180.0                   # a jump at bare ground
    for values, gone, back_to in [(one, [10], 400), (two, [10, 11], 400), (summer, [8], 0)]:
        swe, flags, counts = cleaned(values)
        assert counts['spikes'] == len(gone) and list(np.where(flags == sd.FILLED)[0]) == gone
        assert (swe.iloc[gone] == back_to).all()


def test_steps_small_wiggles_and_the_latest_reading_are_kept():
    step = [300.0] * 10 + [400.0] * 10                       # a storm that stays
    wiggle = [400.0] * 20; wiggle[10] = 440.0                # under 50 mm and under 25% of the level
    latest = [300.0] * 19 + [420.0]                          # newest reading jumps: nothing after it yet
    for values in (step, wiggle, latest):
        swe, flags, counts = cleaned(values)
        assert counts['spikes'] == 0 and (flags == sd.MEASURED).all() and (swe.to_numpy() == values).all()


def test_spike_next_to_missing_days():
    values = [600.0] * 20
    values[9] = 0.0                                    # a dropout followed by two missing days
    values[10], values[11], values[12] = 650.0, np.nan, np.nan
    swe, flags, counts = cleaned(values)
    assert counts['spikes'] == 1 and flags.iloc[9] == sd.FILLED and swe.notna().all()


def test_straight_lines_are_flagged_but_kept():
    filler = np.r_[[100.0] * 5, 100 + np.round(np.arange(1, 21) * 4.25), [190.0] * 5]   # 4, 4, 5, 4 ... mm a day
    swe, flags, counts = cleaned(filler)
    assert (swe.to_numpy() == filler).all()                                             # nothing removed
    inside = np.where(flags == sd.STRAIGHT)[0]
    assert inside.min() == 5 and inside.max() == 24          # the readings at either end (100, 190) count as measured
    slow = np.r_[100 + np.arange(36) * 1.5]                  # 1.5 mm a day for 35 days: an estimate too
    assert (cleaned(np.round(slow))[1] == sd.STRAIGHT).sum() > 25
    rng = np.random.default_rng(1)
    weather = 100 + np.cumsum(rng.choice([0, 0, 1, 2, 8, 15, 30], size=60))            # snow comes in storms
    assert (cleaned(weather.astype(float))[1] == sd.MEASURED).all()
    calm = 300 + np.cumsum(rng.choice([0, 1, 2], size=20))                               # slow gain, short
    assert (cleaned(calm.astype(float))[1] == sd.MEASURED).all()


def test_gaps_up_to_two_weeks_are_filled_with_a_straight_line():
    values = np.r_[[0.0] * 3, [np.nan] * 14, [140.0] * 3, [np.nan] * 15, [140.0] * 3, [np.nan] * 2]
    swe, flags, counts = cleaned(values)
    assert list(swe.iloc[3:17].round(1)) == list(np.round(np.arange(1, 15) * 140 / 15, 1))   # 14-day gap: filled
    assert (flags.iloc[3:17] == sd.FILLED).all() and counts['filled'] == 14
    assert swe.iloc[20:35].isna().all() and (flags.iloc[20:35] == sd.NO_DATA).all()      # 15 days: left empty
    assert swe.iloc[-2:].isna().all()                                                    # never past the latest


def test_clean_uses_calendar_days():
    swe = spiky([400.0] * 20).drop(pd.Timestamp('2004-01-05'))        # a day missing from the table
    swe.loc[pd.Timestamp('2004-01-12'), 'S'] = 0.0
    out, flags, counts = sd.clean(swe)
    assert len(out) == 20 and counts['spikes'] == 1 and counts['filled'] == 2
    assert flags.loc['2004-01-05', 'S'] == sd.FILLED and out.loc['2004-01-12', 'S'] == 400


def test_flag_matrix():
    flags = pd.Series(sd.MEASURED, index=pd.date_range('2003-10-01', '2004-09-30'), dtype='int8')
    flags.loc['2004-01-10':'2004-01-12'] = sd.STRAIGHT
    m = sd.flag_matrix(flags)
    assert m.dtypes.unique().tolist() == [np.int8] and m.loc['01-11', 2004] == sd.STRAIGHT
    assert m.loc['01-13', 2004] == sd.MEASURED


def test_read_flagged_seasons(tmp_path):
    path = tmp_path / 'flags.csv'
    path.write_text('# comment line\nstation_id,name,water_year,reason\n1C20P,Boss,2004,"Sensor fault, see notes"\n')
    assert sd.read_flagged_seasons(path) == {'1C20P': {2004: 'Sensor fault, see notes'}}
    assert sd.read_flagged_seasons(tmp_path / 'missing.csv') == {}
    repo = sd.read_flagged_seasons()                                     # the reviewed list in the repo
    assert 2004 in repo['1C20P'] and 2009 in repo['1A03P']


def test_current_anomalies_statuses():
    dates = pd.date_range('2026-11-20', '2026-11-25')
    swe = pd.DataFrame({
        'ok': [np.nan] * 4 + [50, np.nan],   # latest reading the day before the newest date
        'stale': [40] + [np.nan] * 5,         # nothing in the last 3 days
        'low': [5] * 6,                       # median below the low-snow floor
        'nomed': [30] * 6,                    # no complete seasons
    }, index=dates, dtype=float)
    medians = pd.DataFrame({'ok': 100.0, 'stale': 100.0, 'low': 4.0, 'nomed': np.nan}, index=sd.WY_MONTH_DAYS)
    a = sd.current_anomalies(swe, medians)
    assert a.loc['ok', 'anom_status'] == 'ok'
    assert a.loc['ok', 'pct_of_median'] == 50
    assert a.loc['ok', 'obs_date'] == pd.Timestamp('2026-11-24')
    assert a.loc['stale', 'anom_status'] == 'no_recent' and np.isnan(a.loc['stale', 'pct_of_median'])
    assert a.loc['low', 'anom_status'] == 'low_snow' and np.isnan(a.loc['low', 'pct_of_median'])
    assert a.loc['nomed', 'anom_status'] == 'no_median'


def test_current_anomalies_ignore_a_partly_filled_newest_row():
    # The November 2026 live bug: the newest row held only some stations, and everyone else got no anomaly.
    swe = pd.DataFrame({'A': [90, 95, np.nan], 'B': [10, 11, 12]},
                       index=pd.date_range('2026-11-23', '2026-11-25'), dtype=float)
    medians = pd.DataFrame({'A': 100.0, 'B': 20.0}, index=sd.WY_MONTH_DAYS)
    a = sd.current_anomalies(swe, medians)
    assert a.loc['A', 'pct_of_median'] == 95
    assert a.loc['B', 'pct_of_median'] == 60


def test_enso_by_water_year_assigns_ond_ndj_to_next_year():
    enso = pd.DataFrame({
        'season': ['OND', 'NDJ', 'DJF', 'JFM', 'FMA', 'MAM', 'AMJ'],
        'year': [2025, 2025, 2026, 2026, 2026, 2026, 2026],
        'value': [-0.6, -0.9, -0.7, 0.4, 0.2, 0.1, 2.5],
    })
    by_wy = sd.enso_by_water_year(enso)
    assert list(by_wy.index) == [2026]            # AMJ is outside the snow season and is ignored
    assert by_wy[2026] == -0.9


@pytest.mark.parametrize('values, expected', [([-1.2, 0.8], -1.2), ([-0.8, 1.2], 1.2), ([-1.0, 1.0], 1.0),
                                              ([0.3, 0.6], 0.6), ([-0.3, -0.6], -0.6)])
def test_enso_extremum_keeps_sign_of_largest_magnitude(values, expected):
    enso = pd.DataFrame({'season': ['DJF', 'JFM'], 'year': [2000, 2000], 'value': values})
    assert sd.enso_by_water_year(enso)[2000] == expected


def test_latest_enso_orders_seasons_within_a_year():
    enso = pd.DataFrame({'season': ['ASO', 'JJA', 'NDJ'], 'year': [2026, 2026, 2025], 'value': [1.97, 1.36, -0.5]})
    assert sd.latest_enso(enso) == ('ASO', 2026, 1.97)


@pytest.mark.parametrize('value, expected', [(1.97, [0.5, 3]), (0.5, [0.5, 3]), (0.1, [-0.5, 0.5]),
                                             (-0.49, [-0.5, 0.5]), (-0.5, [-3, -0.5]), (-1.1, [-3, -0.5])])
def test_enso_start_range(value, expected):
    # The old version could never return the neutral range.
    assert sd.enso_start_range(value) == expected
