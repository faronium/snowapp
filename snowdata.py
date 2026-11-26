"""
Analysis functions for the ENSO Snow BC app: water-year bookkeeping, per-station climatology, current
anomalies, and assignment of ENSO index values to water years.

These are plain functions of pandas objects, separate from data loading (ingest.py, snowdb.py) and from
the Dash app, so they can be tested and used from the notebook.
"""
import numpy as np
import pandas as pd

# Day labels ('MM-DD') for a water year, 1 October to 30 September. 29 February is dropped so that every
# season has the same 365 days and a given label is the same calendar day in every year.
WY_MONTH_DAYS = pd.date_range('2001-10-01', '2002-09-30').strftime('%m-%d').tolist()
# Position in WY_MONTH_DAYS, looked up by month * 100 + day.
_WY_DAY_LOOKUP = np.full(1232, -1)
for _i, _md in enumerate(WY_MONTH_DAYS):
    _WY_DAY_LOOKUP[int(_md[:2]) * 100 + int(_md[3:])] = _i

# The plot and the season statistics cover the first 321 days of the water year (1 October to 16 August),
# which takes in the end of melt at nearly every station while ignoring summer gaps in the data.
SEASON_DAYS = 321

# A season is "complete", and used for medians and ranges, if it has data on at least this fraction of those days.
COMPLETE_FRACTION = 0.95

# When the median SWE for the date is below this (mm), a percent of median is not meaningful and isn't shown.
LOW_SNOW_MM = 10.0

# A station's current anomaly uses its latest reading from the most recent RECENT_DAYS days of data.
RECENT_DAYS = 3

# Quantiles shown on the plot. 0.1587-0.8413 spans the same probability as +/-1 standard deviation of a
# normal distribution, but is computed directly from the data.
QUANTILES = [0.05, 0.1587, 0.25, 0.5, 0.75, 0.8413, 0.95]

# 3-month ENSO seasons that overlap the snow season. OND and NDJ belong to the water year that starts in
# that October, which is labelled by the following calendar year.
ENSO_SNOW_SEASONS = ['OND', 'NDJ', 'DJF', 'JFM', 'FMA', 'MAM']
ENSO_SEASON_ORDER = ['DJF', 'JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ']


# ---------------------------------------------------------------- water years and seasons

def water_year(dates):
    """Water year (1 October to 30 September) of each date, labelled by the calendar year in which it ends."""
    dates = pd.DatetimeIndex(dates)
    return pd.Index(dates.year + (dates.month >= 10).astype(int), name='water_year')


def season_matrix(series):
    """
    Reshape one station's daily SWE series (DatetimeIndex) into a table with a row for each day of the
    water year (WY_MONTH_DAYS, 1 October first) and a column for each water year that has data. Days without
    data are NaN, so partial seasons, such as the current one, line up on the right dates.
    """
    s = series.dropna()
    s = s[~((s.index.month == 2) & (s.index.day == 29))]
    if s.empty:
        return pd.DataFrame(index=pd.Index(WY_MONTH_DAYS), dtype=float)
    day = _WY_DAY_LOOKUP[s.index.month * 100 + s.index.day]
    years, year_pos = np.unique(water_year(s.index).to_numpy(), return_inverse=True)
    values = np.full((len(WY_MONTH_DAYS), len(years)), np.nan)
    values[day, year_pos] = s.to_numpy()
    return pd.DataFrame(values, index=pd.Index(WY_MONTH_DAYS), columns=pd.Index(years.astype(int)))


def complete_seasons(matrix, exclude=()):
    """Water years in a season_matrix with data on at least COMPLETE_FRACTION of the first SEASON_DAYS days."""
    coverage = matrix.iloc[:SEASON_DAYS].notna().mean()
    return [int(wy) for wy in coverage.index[coverage >= COMPLETE_FRACTION] if wy not in exclude]


def season_quantiles(matrix, seasons, quantiles=QUANTILES):
    """For each day of the water year, the given quantiles across the given seasons (columns are the quantiles)."""
    if len(seasons) == 0:
        return pd.DataFrame(np.nan, index=matrix.index, columns=quantiles)
    return matrix[list(seasons)].quantile(quantiles, axis=1, interpolation='midpoint').T


def season_span(seasons):
    """'24 seasons, 1991-2026' style description of a list of water years."""
    if not seasons:
        return 'no complete seasons'
    n = len(seasons)
    return f'{n} season{"s" if n != 1 else ""}, {min(seasons)}–{max(seasons)}'


# ---------------------------------------------------------------- climatology and anomalies

def station_climatologies(matrices, current_wy):
    """
    For each station (dict of station_id -> season_matrix): the median SWE for each day of the water year
    across the station's complete seasons, excluding the current one. This is the same median drawn as the
    grey line on the plot.

    Returns (medians, info): medians is a DataFrame (day of water year x station); info is indexed by
    station with n_seasons, first_season, last_season and span (text for display).
    """
    medians, info = {}, {}
    for sid, matrix in matrices.items():
        seasons = complete_seasons(matrix, exclude=[current_wy])
        medians[sid] = matrix[seasons].median(axis=1) if seasons else pd.Series(np.nan, index=matrix.index)
        info[sid] = {
            'n_seasons': len(seasons),
            'first_season': min(seasons) if seasons else None,
            'last_season': max(seasons) if seasons else None,
            'span': season_span(seasons),
        }
    medians = pd.DataFrame(medians, index=WY_MONTH_DAYS)
    info = pd.DataFrame.from_dict(info, orient='index')
    return medians, info


def current_anomalies(swe, medians, recent_days=RECENT_DAYS, low_snow_mm=LOW_SNOW_MM):
    """
    Each station's latest reading from the most recent `recent_days` days of `swe` (wide: date x station),
    compared with that station's median for the same day of the water year.

    Returns a DataFrame indexed by station: obs_date, swe_mm, median_mm, pct_of_median and anom_status, which
    is 'ok', 'no_recent' (no reading in the window), 'no_median' (no complete seasons to compare
    with) or 'low_snow' (median below low_snow_mm, so no percentage is given).
    """
    recent = swe[swe.index > swe.index.max() - pd.Timedelta(days=recent_days)]
    rows = {}
    for sid in swe.columns:
        valid = recent[sid].dropna()
        if valid.empty:
            rows[sid] = (pd.NaT, np.nan, np.nan, np.nan, 'no_recent')
            continue
        obs_date, value = valid.index[-1], float(valid.iloc[-1])
        md = obs_date.strftime('%m-%d')
        md = '02-28' if md == '02-29' else md
        median = medians[sid].get(md, np.nan) if sid in medians.columns else np.nan
        if pd.isna(median):
            rows[sid] = (obs_date, value, np.nan, np.nan, 'no_median')
        elif median < low_snow_mm:
            rows[sid] = (obs_date, value, median, np.nan, 'low_snow')
        else:
            rows[sid] = (obs_date, value, median, 100.0 * value / median, 'ok')
    return pd.DataFrame.from_dict(
        rows, orient='index', columns=['obs_date', 'swe_mm', 'median_mm', 'pct_of_median', 'anom_status'])


# ---------------------------------------------------------------- ENSO

def enso_by_water_year(enso):
    """
    One ENSO index value per water year, from seasonal values (DataFrame: season, year, value): among the
    OND to MAM seasons, the value of largest magnitude, keeping its sign (ties go to the positive value).
    The current water year uses whichever of its seasons have been published so far.
    """
    e = enso[enso['season'].isin(ENSO_SNOW_SEASONS)].copy()
    e['water_year'] = e['year'] + e['season'].isin(['OND', 'NDJ']).astype(int)
    by_year = e.groupby('water_year')['value']
    low, high = by_year.min(), by_year.max()
    result = high.where(high.abs() >= low.abs(), low)
    result.name = 'enso'
    return result


def latest_enso(enso):
    """The most recent seasonal value: (season, year, value)."""
    order = {s: i for i, s in enumerate(ENSO_SEASON_ORDER)}
    e = enso.assign(_order=enso['season'].map(order)).sort_values(['year', '_order'])
    last = e.iloc[-1]
    return last['season'], int(last['year']), float(last['value'])


def enso_start_range(latest_value):
    """Initial slider range for the most recent ENSO value, using CPC's +/-0.5 thresholds."""
    if latest_value >= 0.5:
        return [0.5, 3]
    if latest_value <= -0.5:
        return [-3, -0.5]
    return [-0.5, 0.5]
