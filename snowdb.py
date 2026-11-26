"""
SQLite storage for the ENSO Snow BC app.

The database is a local copy of the public source files, kept up to date by ingest.py. Everything in it
can be rebuilt from those sources, so on hosts without a persistent disk (Heroku) it is simply rebuilt
when the app starts. On Railway it lives on a volume and survives restarts and deploys.

The location comes from the SNOWAPP_DB environment variable (default: ./data/snow.sqlite next to this file).
"""
import os
import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd

DEFAULT_DB_PATH = os.environ.get(
    'SNOWAPP_DB',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'snow.sqlite'),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS stations (
    station_id  TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    elevation   REAL,
    status      TEXT,
    latitude    REAL,
    longitude   REAL,
    operator    TEXT,
    camera_url  TEXT
);

-- One snow water equivalent value (mm) per station per day. source is 'archive' (BC's quality-controlled
-- archive of past water years) or 'current' (the current water year, not yet quality controlled).
CREATE TABLE IF NOT EXISTS swe_daily (
    station_id  TEXT NOT NULL,
    date        TEXT NOT NULL,
    swe_mm      REAL NOT NULL,
    source      TEXT NOT NULL,
    PRIMARY KEY (station_id, date)
) WITHOUT ROWID;

-- CPC Relative Oceanic Nino Index: one value per overlapping 3-month season (DJF, JFM, ... NDJ).
CREATE TABLE IF NOT EXISTS enso_index (
    season  TEXT NOT NULL,
    year    INTEGER NOT NULL,
    value   REAL NOT NULL,
    PRIMARY KEY (season, year)
);

-- Bookkeeping for each upstream source: the HTTP validators used for conditional requests and the
-- outcome of the most recent attempt.
CREATE TABLE IF NOT EXISTS source_state (
    source        TEXT PRIMARY KEY,
    url           TEXT,
    last_modified TEXT,
    etag          TEXT,
    last_checked  TEXT,
    last_success  TEXT,
    last_error    TEXT,
    n_rows        INTEGER
);

-- Small key/value store. data_version increases whenever an ingest changes the data, which tells
-- running app workers to reload.
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

STATION_COLUMNS = ['station_id', 'name', 'elevation', 'status', 'latitude', 'longitude', 'operator', 'camera_url']


def utcnow():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def connect(db_path=None):
    """Open (creating if needed) the database. WAL mode lets the app read while an ingest writes."""
    db_path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    con = sqlite3.connect(db_path, timeout=60, check_same_thread=False)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA synchronous=NORMAL')
    con.executescript(SCHEMA)
    return con


def _py(value):
    """Convert numpy scalars and NaN to plain Python values that sqlite3 can bind."""
    if value is None:
        return None
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, float) and value != value:
        return None
    return value


# ---------------------------------------------------------------- meta and source bookkeeping

def get_meta(con, key, default=None):
    row = con.execute('SELECT value FROM meta WHERE key = ?', (key,)).fetchone()
    return row[0] if row else default


def set_meta(con, key, value):
    with con:
        con.execute('INSERT INTO meta (key, value) VALUES (?, ?) '
                    'ON CONFLICT(key) DO UPDATE SET value = excluded.value', (key, str(value)))


def data_version(con):
    return int(get_meta(con, 'data_version', 0))


def bump_data_version(con):
    set_meta(con, 'data_version', data_version(con) + 1)


def get_source_state(con, source):
    con.row_factory = sqlite3.Row
    try:
        row = con.execute('SELECT * FROM source_state WHERE source = ?', (source,)).fetchone()
    finally:
        con.row_factory = None
    return dict(row) if row else {}


def record_source_check(con, source, url, error=None, last_modified=None, etag=None, n_rows=None, updated=False):
    """Note that a source was checked. On success the HTTP validators are stored for the next conditional request."""
    now = utcnow()
    with con:
        con.execute('INSERT INTO source_state (source, url) VALUES (?, ?) ON CONFLICT(source) DO NOTHING',
                    (source, url))
        con.execute('UPDATE source_state SET url = ?, last_checked = ?, last_error = ? WHERE source = ?',
                    (url, now, error, source))
        if error is None:
            con.execute('UPDATE source_state SET last_success = ? WHERE source = ?', (now, source))
        if updated:
            con.execute('UPDATE source_state SET last_modified = ?, etag = ?, n_rows = ? WHERE source = ?',
                        (last_modified, etag, n_rows, source))


def read_source_states(con):
    return pd.read_sql_query('SELECT * FROM source_state', con).set_index('source')


# ---------------------------------------------------------------- writes

def upsert_stations(con, stations, mode='replace'):
    """
    Insert station metadata (DataFrame with STATION_COLUMNS). For stations already in the table, mode says
    what to do: 'replace' updates them (authoritative metadata), 'fill' updates only placeholder rows that
    have no location yet (bundled fallback metadata), 'keep' leaves them alone (placeholders for stations
    that appear in the snow data before the metadata).
    """
    df = stations.reindex(columns=STATION_COLUMNS)
    cols = ', '.join(STATION_COLUMNS)
    marks = ', '.join('?' * len(STATION_COLUMNS))
    update = 'UPDATE SET ' + ', '.join(f'{c} = excluded.{c}' for c in STATION_COLUMNS[1:])
    action = {'replace': update, 'fill': update + ' WHERE stations.latitude IS NULL', 'keep': 'NOTHING'}[mode]
    rows = [tuple(_py(v) for v in row) for row in df.itertuples(index=False)]
    with con:
        con.executemany(f'INSERT INTO stations ({cols}) VALUES ({marks}) ON CONFLICT(station_id) DO {action}', rows)


def replace_swe(con, obs, source):
    """
    Load one source file's observations (DataFrame: station_id, date 'YYYY-MM-DD', swe_mm), replacing
    the date range that file covers:

    - 'archive' replaces every row up to the archive's last date. This includes 'current' rows that the
      archive now supersedes after BC's yearly roll-over, and lets quality-control removals take effect.
    - 'current' replaces earlier 'current' rows from its first date onward, but never overwrites 'archive'
      rows. Rows from before the file's first date are kept: when BC resets SWDaily.csv on 1 October, the
      previous water year stays in the database until it appears in the archive (in 2026 that took until
      21 November).
    """
    # A generator, so the rows stream into SQLite without building a large list. numpy float64 is a float
    # subclass, so sqlite3 binds it directly.
    rows = zip(obs['station_id'].to_numpy(), obs['date'].to_numpy(), obs['swe_mm'].to_numpy(dtype=float))
    with con:
        if source == 'archive':
            con.execute('DELETE FROM swe_daily WHERE date <= ?', (obs['date'].max(),))
            con.executemany("INSERT INTO swe_daily (station_id, date, swe_mm, source) VALUES (?, ?, ?, 'archive')",
                            rows)
        elif source == 'current':
            con.execute("DELETE FROM swe_daily WHERE source = 'current' AND date >= ?", (obs['date'].min(),))
            con.executemany("INSERT INTO swe_daily (station_id, date, swe_mm, source) VALUES (?, ?, ?, 'current') "
                            "ON CONFLICT(station_id, date) DO NOTHING", rows)
        else:
            raise ValueError(f'unknown source {source!r}')


def replace_enso(con, enso):
    """Replace the ENSO index table (DataFrame: season, year, value). CPC revises recent values, so it is reloaded whole."""
    rows = [(str(s), int(y), float(v)) for s, y, v in zip(enso['season'], enso['year'], enso['value'])]
    with con:
        con.execute('DELETE FROM enso_index')
        con.executemany('INSERT INTO enso_index (season, year, value) VALUES (?, ?, ?)', rows)


# ---------------------------------------------------------------- reads

def read_stations(con):
    return pd.read_sql_query(f'SELECT {", ".join(STATION_COLUMNS)} FROM stations', con)


def read_swe(con):
    """
    All observations as a wide DataFrame: one row per date (DatetimeIndex), one column per station_id.
    Read one station at a time, which keeps peak memory low (fetching all ~800k rows at once as Python
    objects briefly needs a few hundred MB).
    """
    columns = {}
    station_ids = [row[0] for row in con.execute('SELECT DISTINCT station_id FROM swe_daily ORDER BY station_id')]
    for sid in station_ids:
        rows = con.execute(
            "SELECT CAST(julianday(date) - 2440587.5 AS INTEGER), swe_mm FROM swe_daily "
            "WHERE station_id = ? ORDER BY date", (sid,)).fetchall()
        days = np.fromiter((r[0] for r in rows), dtype='int64', count=len(rows))
        values = np.fromiter((r[1] for r in rows), dtype=float, count=len(rows))
        columns[sid] = pd.Series(values, index=pd.to_datetime(days, unit='D'))
    if not columns:
        return pd.DataFrame(index=pd.DatetimeIndex([]), dtype=float)
    return pd.DataFrame(columns).sort_index()


def read_enso(con):
    return pd.read_sql_query('SELECT season, year, value FROM enso_index', con)


def count_rows(con, table):
    return con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
