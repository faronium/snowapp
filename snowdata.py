"""
Analysis functions for the ENSO Snow BC app: water-year bookkeeping, per-station climatology, current
anomalies, and assignment of ENSO index values to water years.

These are plain functions of pandas objects, separate from data loading (ingest.py, snowdb.py) and from
the Dash app, so they can be tested and used from the notebook.
"""
from pathlib import Path

import numpy as np
import pandas as pd

# Day labels ('MM-DD') for a water year, 1 October to 30 September. 29 February is dropped so that every
# season has the same 365 days and a given label is the same calendar day in every year.
WY_MONTH_DAYS = pd.date_range('2001-10-01', '2002-09-30').strftime('%m-%d').tolist()
# Position in WY_MONTH_DAYS, looked up by month * 100 + day.
_WY_DAY_LOOKUP = np.full(1232, -1)
for _i, _md in enumerate(WY_MONTH_DAYS):
    _WY_DAY_LOOKUP[int(_md[:2]) * 100 + int(_md[3:])] = _i

# The water-year plot runs from 1 October to 16 August (the first 321 days), past the end of melt at nearly
# every station.
PLOT_DAYS = 321

# A season is "complete" (used for medians, ranges, the map's normals and the Trends indicators) if it has data on
# at least COMPLETE_FRACTION of the days from 1 October to 1 July. The window stops at 1 July so that low, warm
# stations that melt out early still qualify; stations keep reporting (zeros, or a steady offset) after melt-out.
COMPLETE_DAYS = WY_MONTH_DAYS.index('07-01') + 1
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
    """Water years in a season_matrix with data on at least COMPLETE_FRACTION of the days from 1 Oct to 1 Jul."""
    coverage = matrix.iloc[:COMPLETE_DAYS].notna().mean()
    return [int(wy) for wy in coverage.index[coverage >= COMPLETE_FRACTION] if wy not in exclude]


# ---------------------------------------------------------------- cleaning

# Spikes: one or two readings far from the level on both sides of them, which then comes back.
SPIKE_MM = 50.0            # at least this far from the level before and the level after...
SPIKE_FRACTION = 0.25      # ...and at least this share of that level
SPIKE_SIDE_DAYS = 3        # the level on each side: the median of this many days

# Straight-line stretches: the archive fills some gaps (and some whole periods between occasional readings)
# with straight lines. Snow doesn't come or go at a steady rate, so a run of daily changes that all lie within
# STRAIGHT_BAND_MM of each other (the archive is in whole mm) is an estimate when it is at least this long and
# this steep: (days, mm a day).
STRAIGHT_BAND_MM = 1.0
STRAIGHT_RULES = [(10, 3.0), (30, 1.0)]

# Gaps of up to this many days are filled with a straight line, as the archive itself does.
MAX_FILL_DAYS = 14

# What each daily value is (the flags returned by clean()).
MEASURED, STRAIGHT, FILLED = 0, 1, 2
NO_DATA = -1
ESTIMATE_NOTES = {STRAIGHT: 'estimate: a straight line in the archive', FILLED: 'estimate: a gap filled by this app'}

# Seasons left out of all statistics after review (sensor faults no rule can tell from real weather).
FLAGGED_SEASONS_PATH = Path(__file__).with_name('flagged_seasons.csv')


def _spikes(x):
    """Boolean mask of the spikes in one station's continuous daily series (numpy array, NaN for no data)."""
    s = pd.Series(x)
    # Medians of whatever readings there are in the days on each side (a neighbouring day may be missing).
    before = s.rolling(SPIKE_SIDE_DAYS, min_periods=1).median().shift(1)
    after = s[::-1].rolling(SPIKE_SIDE_DAYS, min_periods=1).median()[::-1].shift(-1)
    off_before, off_after = s - before, s - after
    limit = (SPIKE_FRACTION * ((before + after) / 2).abs()).clip(lower=SPIKE_MM)
    spike = (off_before.abs() > limit) & (off_after.abs() > limit) & (np.sign(off_before) == np.sign(off_after))
    return spike.to_numpy()


def _straight(x):
    """
    Boolean mask of the values inside straight-line stretches (the readings at either end are kept as
    measured): days covered by a window of STRAIGHT_RULES days whose daily changes all lie within
    STRAIGHT_BAND_MM of each other and average at least the rule's rate, up or down.
    """
    change = pd.Series(x).diff()
    inside = np.zeros(len(x), dtype=bool)
    for days, rate in STRAIGHT_RULES:
        window = change.rolling(days, min_periods=days)
        ok = ((window.max() - window.min()) <= STRAIGHT_BAND_MM) & (window.mean().abs() >= rate)
        # A window of changes ending on day t spans the values t - days .. t; its inside is t - days + 1 .. t - 1.
        covered = ok.astype(float)[::-1].rolling(days - 1, min_periods=1).max()[::-1].shift(-1)
        inside |= covered.fillna(0).to_numpy() > 0
    return inside


def _fill(x):
    """Fill gaps of up to MAX_FILL_DAYS days between two readings with a straight line: (filled x, mask)."""
    s = pd.Series(x)
    missing = s.isna()
    gap_length = missing.groupby((~missing).cumsum()).transform('sum')
    line = s.interpolate(limit_area='inside')
    fill = (missing & (gap_length <= MAX_FILL_DAYS) & line.notna()).to_numpy()
    out = x.copy()
    out[fill] = line.to_numpy()[fill]
    return out, fill


def clean(swe):
    """
    Clean the daily SWE (wide: date x station), station by station:

    1. Remove one- and two-day spikes, such as a midwinter drop to zero or a jump of hundreds of mm that
       comes straight back. A reading is a spike when it differs from both the median of the readings in the
       SPIKE_SIDE_DAYS days before it and the median of those in the days after it, in the same direction,
       by more than SPIKE_MM and SPIKE_FRACTION of that level. A storm or melt that stays (a step) is kept,
       and so is the latest reading, which has nothing after it to compare with.
    2. Flag straight-line stretches in the archive as estimates (kept, not removed).
    3. Fill gaps of up to MAX_FILL_DAYS days with a straight line, flagged as estimates. The latest reading
       is never extended forward.

    Returns (swe on continuous days, flags of the same shape with MEASURED, STRAIGHT, FILLED or NO_DATA as
    int8, counts {'spikes', 'straight', 'filled'}).
    """
    if swe.empty:
        return swe.copy(), pd.DataFrame(index=swe.index, columns=swe.columns, dtype='int8'), \
            {'spikes': 0, 'straight': 0, 'filled': 0}
    days = pd.date_range(swe.index.min(), swe.index.max())
    daily = swe.reindex(days)                   # continuous days, so the windows are calendar days
    flags = np.full(daily.shape, NO_DATA, dtype=np.int8)
    counts = {'spikes': 0, 'straight': 0, 'filled': 0}
    for k, sid in enumerate(daily.columns):
        x = daily[sid].to_numpy(dtype=float).copy()
        spike = _spikes(x)
        x[spike] = np.nan
        straight = _straight(x)
        x, filled = _fill(x)
        f = np.where(np.isnan(x), NO_DATA, MEASURED).astype(np.int8)
        f[straight] = STRAIGHT
        f[filled] = FILLED
        daily[sid] = x
        flags[:, k] = f
        counts['spikes'] += int(spike.sum())
        counts['straight'] += int(straight.sum())
        counts['filled'] += int(filled.sum())
    return daily, pd.DataFrame(flags, index=days, columns=daily.columns), counts


def flag_matrix(flags):
    """One station's flags from clean() as a season_matrix (day of water year x water year), int8."""
    return season_matrix(flags.where(flags != NO_DATA).astype(float)).fillna(NO_DATA).astype(np.int8)


def read_flagged_seasons(path=FLAGGED_SEASONS_PATH):
    """station_id -> {water year: reason} from the reviewed list of faulty seasons (empty if there is none)."""
    path = Path(path)
    if not path.exists():
        return {}
    table = pd.read_csv(path, comment='#', dtype={'station_id': str}, skipinitialspace=True)
    flagged = {}
    for row in table.itertuples(index=False):
        flagged.setdefault(row.station_id.strip(), {})[int(row.water_year)] = str(row.reason).strip()
    return flagged


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

def station_climatologies(matrices, complete):
    """
    For each station (dict of station_id -> season_matrix): the median SWE for each day of the water year
    across the station's complete seasons (dict of station_id -> water years, which leave out the current
    season and flagged ones). This is the same median drawn as the grey line on the plot.

    Returns (medians, info): medians is a DataFrame (day of water year x station); info is indexed by
    station with n_seasons, first_season, last_season and span (text for display).
    """
    medians, info = {}, {}
    for sid, matrix in matrices.items():
        seasons = list(complete.get(sid, []))
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
