"""
The app's in-memory view of the database, and the background refresh that keeps it current.

Each web server process holds one Snapshot: tables derived from the database that the Dash callbacks read.
A daemon thread in each process wakes every few minutes and
  1. runs the ingest (ingest.py) if it is due (every SNOWAPP_REFRESH_HOURS, default 3) and no other
     process is already running it, then
  2. rebuilds the snapshot if the database's data_version has changed.
On a fresh database the first ingest runs straight away; until it finishes, current() returns None and the
app shows a "loading" page. Callbacks never touch the database directly.
"""
import logging
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

import ingest
import snowdata
import snowdb
import snowindicators

log = logging.getLogger('snowapp.datastore')

DB_PATH = snowdb.DEFAULT_DB_PATH
REFRESH_HOURS = float(os.environ.get('SNOWAPP_REFRESH_HOURS', '3'))
POLL_SECONDS = 300


@dataclass
class Snapshot:
    version: int
    built_at: datetime
    stations: pd.DataFrame          # one row per station with data and a location (index: station_id)
    matrices: dict                  # station_id -> season_matrix (day of water year x water year)
    complete: dict                  # station_id -> list of complete past seasons (used for medians and ranges)
    indicators: dict                # station_id -> snow season indicators by water year (Trends tab)
    current_wy: int
    data_through: pd.Timestamp      # newest date in the snow data
    enso: pd.Series                 # ENSO value per water year
    enso_latest: tuple              # (season, year, value) of the newest seasonal value
    sources: pd.DataFrame = field(default_factory=pd.DataFrame)
    flagged: dict = field(default_factory=dict)   # station_id -> {water year: reason}, left out of statistics
    estimates: dict = field(default_factory=dict)  # station_id -> snowdata.flag_matrix (estimated days)

    @property
    def start_range(self):
        return snowdata.enso_start_range(self.enso_latest[2])


def build_snapshot(con):
    """Read the database and derive everything the callbacks need."""
    version = snowdb.data_version(con)
    swe, flags, counts = snowdata.clean(snowdb.read_swe(con))
    log.info('cleaning: removed %(spikes)d spikes; %(straight)d straight-line and %(filled)d filled days '
             'flagged as estimates', counts)
    current_wy = int(snowdata.water_year([swe.index.max()])[0])
    flagged = snowdata.read_flagged_seasons()

    matrices = {sid: snowdata.season_matrix(swe[sid]) for sid in swe.columns}
    estimates = {sid: snowdata.flag_matrix(flags[sid]) for sid in swe.columns}
    # A season is complete on the archive's own readings: days this app filled don't count.
    complete = {sid: snowdata.complete_seasons(m.where(estimates[sid] != snowdata.FILLED),
                                               exclude=[current_wy, *flagged.get(sid, {})])
                for sid, m in matrices.items()}
    medians, info = snowdata.station_climatologies(matrices, complete)
    anomalies = snowdata.current_anomalies(swe, medians)
    indicators = {sid: snowindicators.station_indicators(swe[sid], complete[sid],
                                                         filled=flags[sid] == snowdata.FILLED)
                  for sid in swe.columns}

    stations = snowdb.read_stations(con).set_index('station_id')
    stations = stations.join(info).join(anomalies)
    wy_start = pd.Timestamp(current_wy - 1, 10, 1)
    stations['active'] = stations.index.isin(swe.columns[swe.loc[swe.index >= wy_start].notna().any()])
    stations = stations[stations.index.isin(swe.columns) & stations['latitude'].notna()].sort_index()
    stations['hover'] = [_hover_text(sid, row) for sid, row in stations.iterrows()]

    enso = snowdb.read_enso(con)
    return Snapshot(
        version=version,
        built_at=datetime.now(timezone.utc),
        stations=stations,
        matrices=matrices,
        complete=complete,
        indicators=indicators,
        current_wy=current_wy,
        data_through=swe.index.max(),
        enso=snowdata.enso_by_water_year(enso),
        enso_latest=snowdata.latest_enso(enso),
        sources=snowdb.read_source_states(con),
        flagged=flagged,
        estimates=estimates,
    )


def _fmt_mm(value):
    return f'{value:,.0f} mm'


def _hover_text(sid, row):
    """Hover text for a station on the map."""
    lines = [f'<b>{row["name"]}</b> ({sid})']
    details = []
    if pd.notna(row.get('elevation')):
        details.append(f'{row["elevation"]:,.0f} m')
    if isinstance(row.get('operator'), str) and row['operator']:
        details.append(row['operator'])
    if details:
        lines.append(' · '.join(details))
    lines.append('')
    status = row.get('anom_status')
    if not isinstance(status, str) or status == 'no_recent':
        lines.append(f'No reading in the last {snowdata.RECENT_DAYS} days')
    else:
        day = row['obs_date'].strftime('%d %b %Y')
        lines.append(f'SWE {_fmt_mm(row["swe_mm"])} on {day}')
        if status == 'no_median':
            lines.append('No complete past seasons to compare with')
        else:
            lines.append(f'Median for this date {_fmt_mm(row["median_mm"])} ({row["span"]})')
            if status == 'low_snow':
                lines.append('Too little snow normally on this date for a percentage')
            else:
                lines.append(f'<b>{row["pct_of_median"]:.0f}% of median</b>')
    return '<br>'.join(lines)


# ---------------------------------------------------------------- shared state and refresh thread

_snapshot = None
_thread = None
_thread_lock = threading.Lock()


def current():
    """The latest snapshot, or None until the first one has been built."""
    return _snapshot


@contextmanager
def _ingest_lock(blocking):
    """
    Cross-process lock so only one web server process runs the ingest at a time. Yields True if acquired.
    Uses flock, which is available on Linux and macOS; elsewhere every process just runs its own ingest.
    """
    try:
        import fcntl
    except ImportError:
        yield True
        return
    with open(DB_PATH + '.lock', 'w') as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _ingest_due(con):
    if snowdb.data_version(con) == 0:
        return True
    last = snowdb.get_meta(con, 'last_ingest_attempt')
    if last is None:
        return True
    last = datetime.strptime(last, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).total_seconds() >= REFRESH_HOURS * 3600


def refresh_once(force_ingest=False):
    """One pass of the refresh loop: ingest if due, then reload the snapshot if the data changed."""
    global _snapshot
    con = snowdb.connect(DB_PATH)
    try:
        empty = snowdb.data_version(con) == 0
        if force_ingest or _ingest_due(con):
            # On an empty database, wait for whichever process is already loading it rather than skipping.
            with _ingest_lock(blocking=empty) as acquired:
                if acquired and (force_ingest or _ingest_due(con)):
                    snowdb.set_meta(con, 'last_ingest_attempt', snowdb.utcnow())
                    started = time.monotonic()
                    ingest.run_ingest(con)
                    log.info('ingest finished in %.1f s', time.monotonic() - started)
        version = snowdb.data_version(con)
        if version > 0 and (_snapshot is None or _snapshot.version != version):
            started = time.monotonic()
            _snapshot = build_snapshot(con)
            log.info('loaded data version %d (snow data through %s) in %.1f s', version,
                     _snapshot.data_through.date(), time.monotonic() - started)
        elif _snapshot is not None:
            # Keep the "last checked" times on the page current even when nothing changed.
            _snapshot.sources = snowdb.read_source_states(con)
    finally:
        con.close()


def _run():
    while True:
        try:
            refresh_once()
        except Exception:
            log.exception('data refresh failed; will retry')
        time.sleep(POLL_SECONDS if _snapshot is not None else 60)


def ensure_running():
    """Start the refresh thread in this process if it isn't running (safe to call on every request)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    with _thread_lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_run, name='snow-data-refresh', daemon=True)
            _thread.start()


def status_text(snap):
    """One line describing how current the data are, for the page."""
    if snap is None:
        return ''
    season, year, value = snap.enso_latest
    parts = [f'Snow data through {snap.data_through:%d %b %Y}', f'RONI through {season} {year} ({value:+.2f})']
    if 'last_checked' in snap.sources and snap.sources['last_checked'].notna().any():
        checked = pd.to_datetime(snap.sources['last_checked']).max()
        parts.append(f'sources last checked {checked:%d %b %H:%M} UTC')
    return ' · '.join(parts)
