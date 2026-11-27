import numpy as np
import pandas as pd
import pytest

import snowindicators as si

WY = 2019   # water year 2019: 1 Oct 2018 to 30 Sep 2019 (not a leap year)


def season(start='2018-10-15', peak='2019-04-01', rise=5.0, fall=20.0, offset=0.0, floor=0.0, wy=WY):
    """
    A synthetic daily SWE record from 1 Jul of the year before the season to 30 Sep: bare ground, a linear rise of
    `rise` mm/day from `start` to `peak`, a linear fall of `fall` mm/day down to `floor`, all plus `offset`.
    """
    days = pd.date_range(f'{wy - 2}-07-01', f'{wy}-09-30')
    t0, tp = pd.Timestamp(start), pd.Timestamp(peak)
    up = rise * np.clip((days - t0).days.to_numpy() + 1, 0, None)
    top = rise * ((tp - t0).days + 1)
    down = top - fall * (days - tp).days.to_numpy()
    x = np.where(days <= tp, up, np.maximum(down, floor))
    x[days < t0] = 0
    return pd.Series(x + offset, index=days)


def wday(date, wy=WY):
    return int(si.water_year_day([pd.Timestamp(date)], wy)[0])


def one(series, wy=WY):
    return si.station_indicators(series, [wy]).loc[wy]


def test_water_year_day():
    assert wday('2018-10-01') == 0
    assert wday('2018-09-30') == -1
    assert wday('2019-03-01') == 151
    # In a leap year, 29 Feb shares a day with 28 Feb so 1 March is the same day number every year.
    assert wday('2020-02-29', 2020) == wday('2020-02-28', 2020) == wday('2019-02-28')
    assert wday('2020-03-01', 2020) == wday('2019-03-01')
    assert si.water_year_day_label(0) == '1 Oct' and si.water_year_day_label(-10) == '21 Sep'


def test_a_clean_season():
    r = one(season())
    # 5 mm on 15 Oct, 10 mm on 16 Oct: snow-on is the first day at least 10 mm above bare ground.
    assert r.snow_on_day == wday('2018-10-16')
    # Peak 5 * 169 = 845 mm on 1 Apr; falling 20 mm/day it is first below 10 mm on 13 May (5 mm).
    assert r.snow_off_day == wday('2019-05-13')
    assert r.season_days == r.snow_off_day - r.snow_on_day
    assert abs(r.peak_day - wday('2019-04-01')) <= 2 and abs(r.peak_swe - 845) <= 15
    assert r.melt_rate == pytest.approx(20)
    assert wday('2019-04-01') < r.melt_day < wday('2019-05-13')
    assert r.melt_rate_3d == pytest.approx(20)            # a steady melt: the same over 3 days
    assert wday('2019-04-01') < r.melt_day_3d < wday('2019-05-13')
    assert np.isnan(r.offset_mm)


def test_a_sensor_offset_shifts_bare_ground_not_the_dates():
    clean, off = one(season()), one(season(offset=30))
    assert off.snow_on_day == clean.snow_on_day and off.snow_off_day == clean.snow_off_day
    assert off.offset_mm == 30
    assert off.peak_swe == pytest.approx(clean.peak_swe + 30)      # peak SWE is taken as measured


def test_september_snow_is_dated_before_1_october():
    r = one(season(start='2018-09-20'))
    assert r.snow_on_day == wday('2018-09-21') < 0


def test_early_snow_that_melts_away_is_not_the_start_of_the_season():
    s = season(start='2018-11-01')
    early = pd.date_range('2018-10-05', '2018-10-12')
    s[early] = [10, 20, 30, 30, 20, 10, 0, 0]
    assert one(s).snow_on_day == wday('2018-11-02')


def test_a_gap_just_before_snow_on_leaves_it_blank():
    s = season()
    s['2018-10-01':'2018-10-20'] = np.nan
    r = one(s)
    assert np.isnan(r.snow_on_day) and np.isnan(r.season_days)
    assert not np.isnan(r.snow_off_day)


def test_a_gap_in_midwinter_is_bridged():
    s = season()
    s['2019-01-05':'2019-01-25'] = np.nan
    assert one(s).snow_on_day == wday('2018-10-16')


def test_a_stuck_sensor_after_melt_blanks_snow_off_and_melt():
    r = one(season(floor=559))                  # melts from 845 mm down to 559 mm and stays there
    assert np.isnan(r.snow_off_day) and np.isnan(r.melt_rate) and np.isnan(r.season_days)
    assert not np.isnan(r.snow_on_day) and not np.isnan(r.peak_swe)


def test_a_small_steady_level_after_melt_is_bare_ground():
    r = one(season(floor=26))                   # re-zeroed sensor reading 26 mm all summer
    assert r.offset_mm == 26
    assert r.snow_off_day == wday('2019-05-12')   # first day below 26 + 10 mm: 845 - 20 * 41 = 25 on 12 May


def test_snow_that_lasts_all_summer_has_no_snow_off_but_a_melt_rate():
    r = one(season(fall=2))
    assert np.isnan(r.snow_off_day)
    assert r.melt_rate == pytest.approx(2)


def test_leap_year_season():
    r = one(season(start='2019-10-15', peak='2020-04-01', wy=2020), wy=2020)
    assert r.snow_on_day == wday('2018-10-16')                     # same day number as in a non-leap year
    assert abs(r.peak_day - wday('2019-04-01')) <= 2


# ---------------------------------------------------------------- statistics

def test_theil_sen_ignores_an_outlier():
    x = np.arange(2000, 2020)
    y = 2.0 * x + 1
    y[5] += 500
    slope, intercept = si.theil_sen(x, y)
    assert slope == pytest.approx(2.0)
    assert intercept == pytest.approx(1.0)


def test_mann_kendall():
    x = np.arange(20)
    assert si.mann_kendall(x, x * 1.0) < 0.001
    assert np.isnan(si.mann_kendall(x, np.ones(20)))          # all values tied
    rng = np.random.default_rng(0)
    assert si.mann_kendall(x, rng.normal(size=20)) > 0.05


def test_trend_needs_ten_seasons():
    assert si.trend(range(9), range(9)) == {'n': 9}
    t = si.trend(range(10), [2 * v for v in range(10)])
    assert t['n'] == 10 and t['slope_per_decade'] == pytest.approx(20) and t['p'] < 0.01


def test_enso_relationship():
    x = np.linspace(-2, 2, 30)
    r = si.enso_relationship(x, 100 - 50 * x)
    assert r['r'] == pytest.approx(-1) and r['p'] == 0 and r['slope'] == pytest.approx(-50)
    assert si.enso_relationship(x[:9], x[:9]) == {'n': 9}
    rng = np.random.default_rng(1)
    noisy = si.enso_relationship(x, rng.normal(size=30))
    assert abs(noisy['r']) < 0.5 and noisy['p'] > 0.01


def test_a_short_burst_of_melt_shows_more_in_the_3_day_rate():
    days = pd.date_range('2018-09-01', '2019-09-30')
    peak = pd.Timestamp('2019-04-15')
    up = np.clip((days - pd.Timestamp('2018-11-01')).days * 5.0, 0, None)
    down = 800 - (days - peak).days * 20.0
    swe = pd.Series(np.where(days <= peak, np.minimum(up, 800), down), index=days).clip(lower=0)
    burst = (days > pd.Timestamp('2019-05-01')) & (days <= pd.Timestamp('2019-05-03'))
    swe[days > pd.Timestamp('2019-05-01')] -= 60 * np.minimum((days[days > pd.Timestamp('2019-05-01')] - pd.Timestamp('2019-05-01')).days, 3)
    swe = swe.clip(lower=0)
    r = si.station_indicators(swe, [2019]).loc[2019]
    assert r.melt_rate_3d == pytest.approx(80) and r.melt_rate == pytest.approx(56)   # 3 days at 80; 5 days avg 56
    assert abs(r.melt_day_3d - si.water_year_day([pd.Timestamp('2019-05-02')], 2019)[0]) <= 1
