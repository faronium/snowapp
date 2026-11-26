"""
Fetch the upstream data sources and load them into the SQLite database (see snowdb.py).

The web app runs this on a schedule (see datastore.py). To run it by hand:

    python ingest.py            # check every source, load what changed
    python ingest.py --force    # download everything regardless

Each file is requested with a conditional GET, so a check that finds nothing new costs one small request
per source. A source that fails to download, parse or pass its sanity checks is logged and skipped, and
the database keeps the last good copy of its data.
"""
import argparse
import io
import logging
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

import snowdb

log = logging.getLogger('snowapp.ingest')

BC_SNOW_DATA = 'https://www.env.gov.bc.ca/wsd/data_searches/snow/asws/data'
URLS = {
    # Station metadata from the BC Data Catalogue's web feature service (all automated snow weather stations).
    'stations': ('https://openmaps.gov.bc.ca/geo/pub/wfs?service=WFS&version=2.0.0&request=GetFeature'
                 '&typeName=pub:WHSE_WATER_MANAGEMENT.SSL_SNOW_ASWS_STNS_SP&outputFormat=csv&srsName=EPSG:4326'),
    # Daily SWE, quality controlled, for all past water years. BC adds the previous water year some weeks into the new one.
    'swe_archive': f'{BC_SNOW_DATA}/SW_DailyArchive.csv',
    # Daily SWE for the current water year, updated through the day. Reset on 1 October.
    'swe_current': f'{BC_SNOW_DATA}/SWDaily.csv',
    # CPC's Relative Oceanic Nino Index, the official ENSO index since 1 February 2026.
    'enso': 'https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt',
}
# Order matters only for logging; each source is loaded independently.
SOURCES = ['stations', 'swe_archive', 'swe_current', 'enso']

# Snapshot of the station metadata, used only if the metadata service is unreachable on a fresh database.
STATIONS_SEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'snow', 'SNW_ASWS.csv')
# The metadata service doesn't support conditional requests, so it is fetched at most this often.
STATIONS_MAX_AGE = timedelta(hours=24)

# BC's daily values are reported at 16:00 UTC. A few stations report at other hours: the Forrest Kerr pillows at
# 00:00 UTC, and some stations hourly for parts of their record. Each reading is assigned to the nearest 16:00
# UTC reporting time, and where a station has several readings for one day the one closest to 16:00 is kept.
REPORT_HOUR_UTC = 16

ENSO_SEASONS = ['DJF', 'JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ']

HTTP_TIMEOUT = 120


class SourceRejected(Exception):
    """A downloaded file failed its sanity checks, so it was not loaded."""


# ---------------------------------------------------------------- parsing

def parse_swe_csv(text):
    """
    Parse a BC snow pillow CSV (a DATE(UTC) column, then one column per station named 'ID Name').

    Returns (obs, names): obs is a long DataFrame with one row per station per day (station_id,
    date as 'YYYY-MM-DD', swe_mm), and names maps station_id to the name in the column header.
    """
    raw = pd.read_csv(io.StringIO(text), index_col=0)
    raw = raw.loc[raw.index.notna(), [c for c in raw.columns if not str(c).startswith('Unnamed')]]
    times = pd.to_datetime(raw.index.str.strip(), format='%Y-%m-%d %H:%M').to_numpy()
    names = {}
    for col in raw.columns:
        sid, _, name = col.strip().partition(' ')
        names[sid] = name or sid
    station_ids = np.array([c.strip().partition(' ')[0] for c in raw.columns], dtype=object)
    values = raw.apply(pd.to_numeric, errors='coerce').to_numpy(dtype=float)
    del raw

    # Pull out only the non-empty cells (the table is about 70% empty).
    row, col = np.nonzero(~np.isnan(values))
    timestamp = pd.DatetimeIndex(times[row])
    report_time = pd.Timedelta(hours=REPORT_HOUR_UTC)
    # Readings from 04:00 UTC on day D up to 04:00 UTC on D+1 are nearest to 16:00 UTC on day D.
    day = (timestamp - report_time + pd.Timedelta(hours=12)).floor('D')
    codes, days = pd.factorize(day)
    obs = pd.DataFrame({
        'station_id': station_ids[col],
        'date': days.strftime('%Y-%m-%d').to_numpy(dtype=object)[codes],
        'swe_mm': values[row, col],
        'offset': np.abs((timestamp - (day + report_time)).to_numpy()),
    })
    if obs.duplicated(['station_id', 'date']).any():
        obs = obs.sort_values(['station_id', 'date', 'offset']).drop_duplicates(['station_id', 'date'], keep='first')
    return obs[['station_id', 'date', 'swe_mm']].reset_index(drop=True), names


def parse_enso(text):
    """Parse CPC's RONI.ascii.txt (columns SEAS YR ANOM) into a DataFrame: season, year, value."""
    df = pd.read_csv(io.StringIO(text), sep=r'\s+')
    df.columns = [c.upper() for c in df.columns]
    missing = {'SEAS', 'YR', 'ANOM'} - set(df.columns)
    if missing:
        raise SourceRejected(f'ENSO file is missing columns {sorted(missing)}')
    df = df.rename(columns={'SEAS': 'season', 'YR': 'year', 'ANOM': 'value'})[['season', 'year', 'value']]
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    df = df.dropna()
    df = df[df['season'].isin(ENSO_SEASONS)]
    df['year'] = df['year'].astype(int)
    return df.reset_index(drop=True)


def parse_stations(text):
    """Parse the BC WFS station metadata CSV into snowdb.STATION_COLUMNS."""
    df = pd.read_csv(io.StringIO(text))
    df = df.rename(columns={
        'LOCATION_ID': 'station_id', 'LOCATION_NAME': 'name', 'ELEVATION': 'elevation', 'STATUS': 'status',
        'LATITUDE': 'latitude', 'LONGITUDE': 'longitude', 'OPERATOR': 'operator', 'CAMERA_URL': 'camera_url',
    })
    missing = {'station_id', 'name', 'latitude', 'longitude'} - set(df.columns)
    if missing:
        raise SourceRejected(f'station metadata is missing columns {sorted(missing)}')
    return df.reindex(columns=snowdb.STATION_COLUMNS).drop_duplicates('station_id')


def parse_stations_seed(path=STATIONS_SEED):
    """The bundled snapshot of station metadata (older column names, no operator or camera)."""
    df = pd.read_csv(path, encoding='utf-8-sig').rename(columns={
        'LCTN_ID': 'station_id', 'LCTN_NM': 'name', 'ELEVATION': 'elevation', 'STATUS': 'status',
        'LATITUDE': 'latitude', 'LONGITUDE': 'longitude',
    })
    return df.reindex(columns=snowdb.STATION_COLUMNS).drop_duplicates('station_id')


# ---------------------------------------------------------------- loading (parse, check, write)

def load_stations(con, text):
    stations = parse_stations(text)
    if len(stations) < 50:
        raise SourceRejected(f'only {len(stations)} stations in the metadata')
    snowdb.upsert_stations(con, stations)
    return len(stations)


def _load_swe(con, text, source):
    obs, names = parse_swe_csv(text)
    if obs.empty:
        raise SourceRejected('no observations in the file')
    latest = pd.Timestamp(obs['date'].max())
    if latest > pd.Timestamp.now() + pd.Timedelta(days=2):
        raise SourceRejected(f'observations dated in the future ({latest.date()})')
    if source == 'swe_archive':
        previous = snowdb.get_source_state(con, source).get('n_rows')
        if previous and len(obs) < 0.9 * previous:
            raise SourceRejected(f'archive shrank from {previous} to {len(obs)} values; keeping the previous copy')
    # Stations that are in the data but not in the metadata get a placeholder row (name only, no location)
    # until the metadata catches up.
    stubs = pd.DataFrame({'station_id': list(names), 'name': list(names.values())})
    snowdb.upsert_stations(con, stubs, mode='keep')
    snowdb.replace_swe(con, obs, 'archive' if source == 'swe_archive' else 'current')
    return len(obs)


def load_swe_archive(con, text):
    return _load_swe(con, text, 'swe_archive')


def load_swe_current(con, text):
    return _load_swe(con, text, 'swe_current')


def load_enso(con, text):
    enso = parse_enso(text)
    if len(enso) < 500:
        raise SourceRejected(f'only {len(enso)} ENSO index values in the file')
    snowdb.replace_enso(con, enso)
    return len(enso)


LOADERS = {
    'stations': load_stations,
    'swe_archive': load_swe_archive,
    'swe_current': load_swe_current,
    'enso': load_enso,
}


# ---------------------------------------------------------------- fetching

def fetch(url, state, force=False):
    """
    GET url, sending the validators saved from the last successful download so an unchanged file comes
    back as 304 Not Modified. Returns (text, last_modified, etag), with text None if unchanged.
    """
    headers = {}
    if not force and state.get('last_success'):
        if state.get('etag'):
            headers['If-None-Match'] = state['etag']
        if state.get('last_modified'):
            headers['If-Modified-Since'] = state['last_modified']
    resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
    if resp.status_code == 304:
        return None, state.get('last_modified'), state.get('etag')
    resp.raise_for_status()
    return resp.content.decode('utf-8-sig', errors='replace'), resp.headers.get('Last-Modified'), resp.headers.get('ETag')


def _recently_succeeded(state, max_age):
    if not state.get('last_success'):
        return False
    last = datetime.strptime(state['last_success'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last < max_age


def run_ingest(con, force=False, sources=SOURCES):
    """
    Check each source and load whatever changed. Never raises for a source failure; returns a dict of
    source -> outcome ('updated (n rows)', 'unchanged', 'skipped', or 'error: ...').
    """
    outcomes = {}
    changed = False
    for source in sources:
        url = URLS[source]
        state = snowdb.get_source_state(con, source)
        if source == 'stations' and not force and _recently_succeeded(state, STATIONS_MAX_AGE):
            outcomes[source] = 'skipped (checked within 24 h)'
            continue
        try:
            text, last_modified, etag = fetch(url, state, force=force)
            if text is None:
                snowdb.record_source_check(con, source, url)
                outcomes[source] = 'unchanged'
                continue
            n_rows = LOADERS[source](con, text)
            snowdb.record_source_check(con, source, url, last_modified=last_modified, etag=etag,
                                       n_rows=n_rows, updated=True)
            outcomes[source] = f'updated ({n_rows} rows)'
            changed = True
        except Exception as exc:  # network errors, HTTP errors, parse failures, SourceRejected
            log.warning('%s: %s: %s', source, type(exc).__name__, exc)
            snowdb.record_source_check(con, source, url, error=f'{type(exc).__name__}: {exc}'[:500])
            outcomes[source] = f'error: {type(exc).__name__}: {exc}'
    if outcomes.get('stations', '').startswith('error'):
        # Fall back to the bundled metadata for stations the database has no location for yet.
        snowdb.upsert_stations(con, parse_stations_seed(), mode='fill')
    if changed:
        snowdb.bump_data_version(con)
    snowdb.set_meta(con, 'last_ingest', snowdb.utcnow())
    for source, outcome in outcomes.items():
        log.info('ingest %s: %s', source, outcome)
    return outcomes


def main():
    parser = argparse.ArgumentParser(description='Update the ENSO Snow BC database from the upstream sources.')
    parser.add_argument('--db', default=None, help=f'database path (default {snowdb.DEFAULT_DB_PATH})')
    parser.add_argument('--force', action='store_true', help='download every source even if unchanged')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    con = snowdb.connect(args.db)
    try:
        run_ingest(con, force=args.force)
        print(f'data_version={snowdb.data_version(con)}  stations={snowdb.count_rows(con, "stations")}  '
              f'swe rows={snowdb.count_rows(con, "swe_daily")}  enso rows={snowdb.count_rows(con, "enso_index")}')
    finally:
        con.close()


if __name__ == '__main__':
    main()
