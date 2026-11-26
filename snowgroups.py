"""
Group analysis for the Trends tab: combining the snow season indicators of several stations (a sub-basin, a
region, or all of BC) into one regional series, and testing it for trends and ENSO relationships.

Station codes group naturally: the first character is the region and the first two the sub-basin (2D08P is in
region 2, sub-basin 2D).

The regional series. Each indicator value is modelled as  station level + year effect,  with both estimated
together by least squares from every station in the group. The year effects are the regional series. Estimating
the station levels together (rather than taking each station's own average) places stations with different
periods of record correctly against each other: a station that only covers recent years is compared with the
others in the years they share. Dates and season length are combined in days; peak SWE and melt rate on a log
scale, so year effects are ratios ("35% below normal") and large and small snowpacks contribute in proportion.
A year enters the series only if at least MIN_STATIONS_PER_YEAR stations reported it.

The trend test. Stations in a group share most of their year-to-year variation, so they are far from independent.
The Regional Kendall test (Helsel and Frans, 2006) sums the Mann-Kendall statistic over stations and corrects its
variance for the correlation between them (Dietz and Killeen, 1981; Hirsch and Slack, 1984, for missing years).
The regional slope is the median of every within-station pairwise slope (a pooled Theil-Sen slope).

ENSO adjustment. Optionally, the part of each year's value explained by that year's RONI (a least-squares fit of
the regional series on RONI) is removed before testing for a trend, which takes out much of the year-to-year
variation and can reveal smaller trends.
"""
import math
import warnings

import numpy as np
import pandas as pd

import snowindicators as si

LEVELS = {'station': 'Station', 'subbasin': 'Sub-basin', 'region': 'Region', 'bc': 'All of BC'}
LOG_INDICATORS = {'peak_swe', 'melt_rate'}
MIN_STATION_SEASONS = 5      # a station needs this many seasons of an indicator to be included in a group
MIN_STATIONS_PER_YEAR = 2    # a year enters the regional series only with at least this many stations
TREND_START = 1990           # default start of the trend period: the network is too sparse before this
FIXED_COVERAGE = 0.8         # 'same stations throughout': a station needs this share of the period's seasons


# ---------------------------------------------------------------- groups

def group_key(sid, level):
    """The group a station belongs to at a level: '2D' (sub-basin), '2' (region), 'BC', or the station itself."""
    return {'station': sid, 'subbasin': sid[:2], 'region': sid[:1], 'bc': 'BC'}[level]


def group_label(key, level):
    return {'station': key, 'subbasin': f'Sub-basin {key}', 'region': f'Region {key}', 'bc': 'All of BC'}[level]


def group_members(station_ids, sid, level):
    """Stations (from station_ids) in the same group as sid at the given level."""
    key = group_key(sid, level)
    return [s for s in station_ids if group_key(s, level) == key]



def restrict_period(indicators, members, start):
    """The members' indicator tables limited to water years from start on (all years if start is None)."""
    out = {}
    for sid in members:
        if sid in indicators:
            d = indicators[sid]
            out[sid] = d[d.index >= start] if start else d
    return out


def fixed_network(indicators, members, col):
    """
    Members with a value of col in at least FIXED_COVERAGE of the years from the group's first to its last
    season, so that the same stations make up the regional series throughout and its make-up can't drift.
    """
    years = [y for sid in members if sid in indicators for y in indicators[sid][col].dropna().index]
    if not years:
        return []
    span = max(years) - min(years) + 1
    return [sid for sid in members if sid in indicators
            and indicators[sid][col].notna().sum() >= FIXED_COVERAGE * span]

# ---------------------------------------------------------------- the regional series

def _largest_connected(wide):
    """
    Keep the largest set of stations linked by shared years. Stations that share no year (directly or through
    other stations) with the rest can't be placed relative to them.
    """
    cols = list(wide.columns)
    parent = {c: c for c in cols}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    present = wide.notna()
    for _, row in present.iterrows():
        here = [c for c in cols if row[c]]
        for c in here[1:]:
            parent[find(c)] = find(here[0])
    groups = {}
    for c in cols:
        groups.setdefault(find(c), []).append(c)
    if not groups:
        return wide
    best = max(groups.values(), key=lambda g: int(present[g].values.sum()))
    return wide[best]


def two_way(wide, tol=1e-10, max_iter=500):
    """
    Least-squares fit of  value = station level + year effect  to a years x stations table (NaN for missing),
    by alternating means. Returns (levels, effects): station levels, and year effects centred so that their
    mean over the years with at least MIN_STATIONS_PER_YEAR stations is zero.
    """
    x = wide.to_numpy(dtype=float)
    ok = ~np.isnan(x)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)     # means of empty rows/columns are handled below
        return _two_way(wide, x, ok, tol, max_iter)


def _two_way(wide, x, ok, tol, max_iter):
    level = np.nanmean(x, axis=0)
    effect = np.zeros(x.shape[0])
    rows = ok.any(axis=1)
    for _ in range(max_iter):
        new_effect = np.where(rows, np.nanmean(np.where(ok, x - level, np.nan), axis=1), 0.0)
        new_level = np.nanmean(np.where(ok, x - new_effect[:, None], np.nan), axis=0)
        change = max(np.max(np.abs(new_effect - effect)), np.max(np.abs(new_level - level)))
        effect, level = new_effect, new_level
        if change < tol:
            break
    enough = ok.sum(axis=1) >= MIN_STATIONS_PER_YEAR
    shift = effect[enough].mean() if enough.any() else 0.0
    effects = pd.Series(effect - shift, index=wide.index)[enough]
    levels = pd.Series(level + shift, index=wide.columns)
    return levels, effects


# ---------------------------------------------------------------- the Regional Kendall test

def regional_kendall(wide):
    """
    Regional Kendall test on a years x stations table (NaN for missing). Returns {'S', 'var', 'p', 'slope'}, where
    slope is the pooled Theil-Sen slope per year (median of all within-station pairwise slopes).
    """
    years = wide.index.to_numpy(dtype=float)
    x = wide.to_numpy(dtype=float)
    n, g = x.shape
    i, j = np.triu_indices(n, k=1)
    diff = x[j] - x[i]                                     # pairs x stations
    sign = np.nan_to_num(np.sign(diff))                    # 0 where either year is missing
    s_station = sign.sum(axis=0)
    s = float(s_station.sum())

    # Variances: the usual Mann-Kendall variance for each station's own record, with the tie correction.
    var_station = np.zeros(g)
    for k in range(g):
        v = x[~np.isnan(x[:, k]), k]
        m = len(v)
        _, counts = np.unique(v, return_counts=True)
        ties = sum(t * (t - 1) * (2 * t + 5) for t in counts if t > 1)
        var_station[k] = (m * (m - 1) * (2 * m + 5) - ties) / 18.0

    # Covariances between stations (Dietz and Killeen, 1981), with missing years handled as in Hirsch and Slack
    # (1984): a missing value takes the middle rank and contributes no sign.
    kmat = sign.T @ sign                                   # K_gh = sum over pairs of sgn_g * sgn_h
    full = np.nan_to_num(np.sign(x[:, None, :] - x[None, :, :]))          # years x years x stations
    ranks = (n + 1 + full.sum(axis=1)) / 2.0               # years x stations
    cov = (kmat + 4.0 * ranks.T @ ranks - n * (n + 1) ** 2) / 3.0
    np.fill_diagonal(cov, var_station)
    var = float(cov.sum())

    p = np.nan
    if var > 0:
        z = (s - np.sign(s)) / math.sqrt(var)
        p = math.erfc(abs(z) / math.sqrt(2))
    dt = (years[j] - years[i])[:, None]
    slopes = (diff / dt)[~np.isnan(diff)]
    slope = float(np.median(slopes)) if len(slopes) else np.nan
    return {'S': s, 'var': var, 'p': p, 'slope': slope}


# ---------------------------------------------------------------- one indicator for one group

def _ols(x, y):
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def group_analysis(indicators, members, col, enso, adjust_enso=False):
    """
    Everything the Trends figures need for one indicator and a group of stations.

    indicators: station_id -> indicator DataFrame (snowindicators.station_indicators); members: station ids;
    col: indicator column; enso: RONI by water year; adjust_enso: remove the RONI-explained part before the trend.

    Values are in model units: days for dates and season length, natural log for peak SWE and melt rate.
    Returns a dict with: years, series (regional year effects), stations (station anomalies, years x stations),
    n_stations, log (bool), trend {n, slope, slope_per_decade, intercept, p} when the series has at least
    si.MIN_TREND_SEASONS years, and enso_rel {n, r, p, slope, intercept} likewise.
    """
    cols = {sid: indicators[sid][col] for sid in members if sid in indicators and col in indicators[sid]}
    wide = pd.DataFrame(cols).sort_index() if cols else pd.DataFrame()
    is_log = col in LOG_INDICATORS
    out = {'log': is_log, 'n_stations': 0, 'years': np.array([]), 'series': pd.Series(dtype=float),
           'stations': pd.DataFrame(), 'trend': {'n': 0}, 'enso_rel': {'n': 0}, 'adjusted': adjust_enso}
    if wide.empty:
        return out
    if is_log:
        wide = np.log(wide.where(wide > 0))
    wide = wide.loc[:, wide.notna().sum() >= MIN_STATION_SEASONS]
    if wide.shape[1] == 0:
        return out
    wide = _largest_connected(wide.dropna(how='all'))
    levels, effects = two_way(wide)
    out['n_stations'] = int(wide.shape[1])
    if effects.empty:
        return out

    roni = pd.Series(enso).reindex(effects.index).astype(float)
    have = roni.notna()
    rel = {'n': int(have.sum())}
    if have.sum() >= si.MIN_TREND_SEASONS:
        r, p = si.correlation(roni[have], effects[have])
        if not np.isnan(r):                                 # NaN when RONI or the series doesn't vary
            rel['r'], rel['p'] = r, p
            rel['slope'], rel['intercept'] = _ols(roni[have], effects[have])
    out['enso_rel'] = rel

    series, data = effects, wide
    if adjust_enso and 'slope' in rel:
        mean_roni = roni[have].mean()
        all_roni = pd.Series(enso).reindex(wide.index).astype(float).fillna(mean_roni)
        series = effects - rel['slope'] * (roni.fillna(mean_roni) - mean_roni)
        data = wide.sub(rel['slope'] * (all_roni - mean_roni), axis=0)
    out['years'] = series.index.to_numpy()
    out['series'] = series
    out['stations'] = data.sub(levels, axis=1)

    trend = {'n': int(len(series))}
    if len(series) >= si.MIN_TREND_SEASONS:
        rk = regional_kendall(data)
        slope = rk['slope']
        trend.update(slope=slope, slope_per_decade=10 * slope, p=rk['p'],
                     intercept=float(np.median(series.to_numpy() - slope * series.index.to_numpy())))
    out['trend'] = trend
    return out


def station_adjusted(values, enso):
    """A single station's indicator with the part explained by RONI removed (least squares), and the fitted slope."""
    roni = pd.Series(enso).reindex(values.index).astype(float)
    ok = values.notna() & roni.notna()
    if ok.sum() < si.MIN_TREND_SEASONS or roni[ok].std() == 0:
        return values, np.nan
    slope, _ = _ols(roni[ok], values[ok])
    return values - slope * (roni.fillna(roni[ok].mean()) - roni[ok].mean()), slope
