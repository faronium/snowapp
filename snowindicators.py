"""
Snow season indicators for the Trends tab, and the trend and correlation statistics shown with them.

For each station and each complete season (snowdata.complete_seasons), from the daily SWE series:

  peak SWE, peak date      the highest 5-day running mean of SWE, taken as measured
  snow-on, snow-off        the first day of, and the first day after, the longest continuous stretch with
                           SWE at least SNOW_MM above bare ground. The search starts on 1 September so that
                           snow arriving in September at high stations is dated correctly.
  season length            days from snow-on to snow-off
  peak melt rate, date     the largest 5-day mean daily loss of SWE between the peak and snow-off

Bare ground. Some sensors read a steady non-zero value when there is no snow (an offset, often after
recalibration). A season's bare-ground level for snow-on is the lowest flat level (7-day standard deviation
under FLAT_STD_MM) in the July to September before it, and for snow-off the lowest flat level in the July to
September after it; 0 if there is no flat stretch to go by. A level that can't be bare ground (MAX_BARE_MM or
more, or both OFFSET_NOTE_MM or more and MAX_BARE_FRACTION of the season's peak or more) means a faulty
sensor, and the dates that depend on it are left blank.

Each value has its own data check and is left blank (NaN) when the data around it are missing.

Dates are days of the water year: 0 is 1 October; negative values fall in the September before; 29 February
counts as 28 February so that a given number is the same calendar day in every year.
"""
import calendar
import math

import numpy as np
import pandas as pd

FLAT_WINDOW = 7            # days, for finding flat (snow-free) stretches
FLAT_STD_MM = 2.0          # a stretch is flat if its standard deviation is below this
SNOW_MM = 10.0             # snow on the ground: at least this much above bare ground
OFFSET_NOTE_MM = 10.0      # bare-ground levels this high are noted as a sensor offset
MAX_BARE_MM = 100.0        # a flat level this high can't be bare ground
MAX_BARE_FRACTION = 0.25   # ... nor can one this large a share of the season's peak (if also >= OFFSET_NOTE_MM)
SMOOTH_DAYS = 5            # running mean for the peak and the melt rate
PEAK_COVERAGE = 0.8        # share of days with data needed within PEAK_HALF_WINDOW days of the peak
PEAK_HALF_WINDOW = 15
MELT_COVERAGE = 0.8        # share of days with data needed between the peak and snow-off
MIN_TREND_SEASONS = 10     # trends and correlations are shown only with at least this many seasons

INDICATORS = {   # column: (label, units, is a date)
    'peak_swe': ('Peak SWE', 'mm', False),
    'peak_day': ('Peak date', 'days', True),
    'snow_on_day': ('Snow-on date', 'days', True),
    'snow_off_day': ('Snow-off date', 'days', True),
    'season_days': ('Season length', 'days', False),
    'melt_rate': ('Peak melt rate', 'mm/day', False),
}
COLUMNS = list(INDICATORS) + ['melt_day', 'offset_mm']


# ---------------------------------------------------------------- dates

def water_year_day(dates, wy):
    """Day of water year wy (0 = 1 October of calendar year wy - 1) for each date; 29 Feb counts as 28 Feb."""
    dates = pd.DatetimeIndex(dates)
    days = np.asarray((dates - pd.Timestamp(wy - 1, 10, 1)).days)
    if calendar.isleap(wy):
        days = days - (dates >= pd.Timestamp(wy, 2, 29)).astype(int)
    return days


def water_year_day_label(day):
    """'15 Mar' style label for a day of the water year."""
    return (pd.Timestamp(2001, 10, 1) + pd.Timedelta(days=int(round(day)))).strftime('%-d %b')


# ---------------------------------------------------------------- one station

def _longest_run(mask):
    """(first, last) index of the longest run of True values, or None."""
    if not mask.any():
        return None
    edges = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    starts, ends = np.where(edges == 1)[0], np.where(edges == -1)[0] - 1
    k = int(np.argmax(ends - starts))
    return int(starts[k]), int(ends[k])


def _nanmin(a):
    a = a[~np.isnan(a)]
    return float(a.min()) if len(a) else np.nan


def _plausible_bare(level, peak):
    return level < MAX_BARE_MM and not (level >= OFFSET_NOTE_MM and level >= MAX_BARE_FRACTION * peak)


def station_indicators(series, seasons):
    """
    Indicators for one station: series is its daily SWE (DatetimeIndex), seasons the water years to compute
    (normally its complete seasons). Returns a DataFrame indexed by water year with COLUMNS.
    """
    s = series.dropna()
    if s.empty or not len(seasons):
        return pd.DataFrame(columns=COLUMNS, dtype=float)
    # A continuous daily record with room for each season's search window, so seasons are plain array slices.
    start = pd.Timestamp(min(seasons) - 2, 7, 1)
    days = pd.date_range(start, pd.Timestamp(max(seasons), 9, 30))
    s = series.reindex(days)
    roll = s.rolling(FLAT_WINDOW, min_periods=FLAT_WINDOW - 1)
    arrays = {
        'x': s.to_numpy(dtype=float),
        'flat': roll.median().where(roll.std() < FLAT_STD_MM).to_numpy(dtype=float),
        'smooth': s.rolling(SMOOTH_DAYS, center=True, min_periods=3).mean().to_numpy(dtype=float),
        'loss': (-s.diff()).rolling(SMOOTH_DAYS, center=True, min_periods=3).mean().to_numpy(dtype=float),
    }
    pos = lambda year, month, day: (pd.Timestamp(year, month, day) - start).days
    rows = {int(wy): _season(arrays, pos, int(wy)) for wy in seasons}
    return pd.DataFrame.from_dict(rows, orient='index', columns=COLUMNS).sort_index()


def _season(arrays, pos, wy):
    out = dict.fromkeys(COLUMNS, np.nan)
    a, b = pos(wy - 1, 9, 1), pos(wy, 9, 30) + 1           # search window: 1 Sep to 30 Sep of the water year
    x, sm, loss = arrays['x'][a:b], arrays['smooth'][a:b], arrays['loss'][a:b]
    wday = np.arange(len(x)) - 30                          # 1 Sep is 30 days before 1 Oct
    if calendar.isleap(wy):
        wday[pos(wy, 2, 29) - a:] -= 1                     # 29 Feb counts as 28 Feb
    in_wy = wday >= 0
    if not np.any(~np.isnan(sm[in_wy])):
        return out

    # Peak: highest 5-day mean in the water year, as measured.
    ip = int(np.nanargmax(np.where(in_wy, sm, np.nan)))
    peak = float(sm[ip])
    lo, hi = max(0, ip - PEAK_HALF_WINDOW), min(len(x), ip + PEAK_HALF_WINDOW + 1)
    peak_ok = np.mean(~np.isnan(x[lo:hi])) >= PEAK_COVERAGE
    if peak_ok:
        out['peak_swe'], out['peak_day'] = peak, wday[ip]

    # Bare-ground levels from the summer before and the summer after the season.
    ref_on = _nanmin(arrays['flat'][pos(wy - 1, 7, 1):pos(wy - 1, 9, 30) + 1])
    ref_off = _nanmin(arrays['flat'][pos(wy, 7, 1):pos(wy, 9, 30) + 1])
    ref_on = 0.0 if np.isnan(ref_on) else ref_on
    ref_off = ref_on if np.isnan(ref_off) else ref_off
    if max(ref_on, ref_off) >= OFFSET_NOTE_MM:
        out['offset_mm'] = max(ref_on, ref_off)
    on_ok, off_ok = _plausible_bare(ref_on, peak), _plausible_bare(ref_off, peak)

    # Snow on the ground: at least SNOW_MM above bare ground (the snow-on level up to the peak, the snow-off
    # level after it). A gap in the data counts as snow only if there is snow on both sides of it.
    threshold = np.where(np.arange(len(x)) <= ip, ref_on, ref_off) + SNOW_MM
    snow = pd.Series(np.where(np.isnan(x), np.nan, (x >= threshold).astype(float)))
    bridged = (snow.ffill() * snow.bfill()).fillna(0).to_numpy() == 1
    run = _longest_run(bridged)
    if run is None or not (run[0] <= ip <= run[1]):
        return out
    first, last = run

    # Snow-on needs an observed snow-free day just before it (not a data gap, not the start of the search).
    if on_ok and first > 0 and not np.isnan(x[first - 1]):
        out['snow_on_day'] = wday[first]
    # Snow-off needs an observed snow-free day after the snowpack (not a gap, and not still snow on 30 Sep).
    if off_ok and last + 1 < len(x) and not np.isnan(x[last + 1]):
        out['snow_off_day'] = wday[last + 1]
    if not np.isnan(out['snow_on_day']) and not np.isnan(out['snow_off_day']):
        out['season_days'] = out['snow_off_day'] - out['snow_on_day']

    # Peak melt rate: largest 5-day mean daily loss between the peak and snow-off (or 30 Sep if the snow
    # lasted all summer), with enough data in between.
    if peak_ok and off_ok:
        stop = last + 1 if not np.isnan(out['snow_off_day']) else len(x) - 1
        seg = loss[ip + 1:stop + 1]
        if stop > ip and np.mean(~np.isnan(x[ip:stop + 1])) >= MELT_COVERAGE and np.any(~np.isnan(seg)):
            k = int(np.nanargmax(seg))
            if seg[k] > 0:
                out['melt_rate'], out['melt_day'] = float(seg[k]), wday[ip + 1 + k]
    return out


# ---------------------------------------------------------------- statistics

def _normal_p(z):
    """Two-sided p-value for a standard normal statistic."""
    return math.erfc(abs(z) / math.sqrt(2))


def theil_sen(x, y):
    """Theil-Sen slope (median of pairwise slopes) and intercept for the line y = intercept + slope * x."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    i, j = np.triu_indices(len(x), k=1)
    dx = x[j] - x[i]
    keep = dx != 0
    if not keep.any():
        return np.nan, np.nan
    slope = float(np.median((y[j] - y[i])[keep] / dx[keep]))
    return slope, float(np.median(y - slope * x))


def mann_kendall(x, y):
    """Two-sided Mann-Kendall test for a monotonic trend in y ordered by x, with the correction for tied values."""
    order = np.argsort(x)
    y = np.asarray(y, dtype=float)[order]
    n = len(y)
    if n < 3:
        return np.nan
    i, j = np.triu_indices(n, k=1)
    s = float(np.sign(y[j] - y[i]).sum())
    _, counts = np.unique(y, return_counts=True)
    ties = sum(t * (t - 1) * (2 * t + 5) for t in counts if t > 1)
    var = (n * (n - 1) * (2 * n + 5) - ties) / 18.0
    if var <= 0:
        return np.nan
    z = (s - np.sign(s)) / math.sqrt(var)
    return _normal_p(z)


def correlation(x, y):
    """Pearson correlation and its two-sided p-value (Fisher z approximation)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    n = len(x)
    if n < 4 or np.std(x) == 0 or np.std(y) == 0:
        return np.nan, np.nan
    r = float(np.corrcoef(x, y)[0, 1])
    if abs(r) >= 1:
        return r, 0.0
    return r, _normal_p(math.atanh(r) * math.sqrt(n - 3))


def trend(years, values):
    """
    Trend of an indicator over water years: n, and when n >= MIN_TREND_SEASONS the Theil-Sen slope per decade,
    its intercept and the Mann-Kendall p-value.
    """
    ok = ~np.isnan(np.asarray(values, dtype=float))
    x, y = np.asarray(years, dtype=float)[ok], np.asarray(values, dtype=float)[ok]
    result = {'n': int(len(x))}
    if len(x) >= MIN_TREND_SEASONS:
        slope, intercept = theil_sen(x, y)
        result.update(slope_per_decade=10 * slope, slope=slope, intercept=intercept, p=mann_kendall(x, y))
    return result


def enso_relationship(enso_values, values):
    """Correlation of an indicator with the water year's ENSO index: n, and r and p when n >= MIN_TREND_SEASONS."""
    x, y = np.asarray(enso_values, dtype=float), np.asarray(values, dtype=float)
    ok = ~np.isnan(x) & ~np.isnan(y)
    result = {'n': int(ok.sum())}
    if ok.sum() >= MIN_TREND_SEASONS:
        r, p = correlation(x[ok], y[ok])
        if not np.isnan(r):                                 # NaN when either variable doesn't vary
            result['r'], result['p'] = r, p
            result['slope'], result['intercept'] = np.polyfit(x[ok], y[ok], 1)
    return result


def fdr_significant(pvalues, q=0.10):
    """
    Which p-values are significant when controlling the false discovery rate at q (Benjamini and Hochberg,
    1995): the largest k with p(k) <= q * k / m sets the cut-off. Wilks (2016) recommends q = 0.10 for maps of
    spatially correlated local tests, which keeps the chance of a falsely "significant" map near 0.05.
    """
    p = np.asarray(pvalues, dtype=float)
    ok = ~np.isnan(p)
    significant = np.zeros(len(p), dtype=bool)
    m = int(ok.sum())
    if m == 0:
        return significant
    ranked = np.sort(p[ok])
    below = ranked <= q * np.arange(1, m + 1) / m
    if below.any():
        cutoff = ranked[np.max(np.where(below)[0])]
        significant[ok] = p[ok] <= cutoff
    return significant
