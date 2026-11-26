import pandas as pd
import pytest

import datastore
import ingest
import snowdb

# A small file in BC's format, with a byte-order mark, Windows line endings, Forrest Kerr's 00:00 UTC
# readings and some hourly readings around 16:00.
SWE_CSV = (
    '﻿DATE(UTC),1A01P Yellowhead Lake,4D17P Forrest Kerr High Elevation Snow,3A25P Squamish River Upper\r\n'
    '2026-11-23 16:00,89,,500\r\n'
    '2026-11-24 00:00,,351,\r\n'
    '2026-11-24 15:00,,,509\r\n'
    '2026-11-24 16:00,90,,510\r\n'
    '2026-11-24 17:00,,,511\r\n'
    '2026-11-25 00:00,,364,\r\n'
)
SWE_CURRENT_CSV = 'DATE(UTC),1A01P Yellowhead Lake\n2026-11-25 16:00,95\n'

STATIONS_CSV = 'FID,SNOW_ASWS_STN_ID,LOCATION_ID,LOCATION_NAME,ELEVATION,STATUS,LATITUDE,LONGITUDE,OPERATOR,CAMERA_URL\n' + ''.join(
    f'x.{i},{i},S{i:03d}P,Station {i},1000,Active,50.0,-120.0,BC ENV,\n' for i in range(60))


def roni_text(n=600):
    rows = [f'{ingest.ENSO_SEASONS[i % 12]}  {1950 + i // 12}  {0.1:.2f}' for i in range(n)]
    return 'SEAS   YR  ANOM\n' + '\n'.join(rows) + '\n'


@pytest.fixture
def con(tmp_path):
    c = snowdb.connect(str(tmp_path / 'test.sqlite'))
    yield c
    c.close()


def obs(rows):
    return pd.DataFrame(rows, columns=['station_id', 'date', 'swe_mm'])


def all_swe(con):
    return con.execute('SELECT station_id, date, swe_mm, source FROM swe_daily ORDER BY station_id, date').fetchall()


# ---------------------------------------------------------------- parsing

def test_parse_swe_assigns_each_reading_to_the_nearest_report_time():
    parsed, names = ingest.parse_swe_csv(SWE_CSV)
    got = {(r.station_id, r.date): r.swe_mm for r in parsed.itertuples()}
    assert got == {
        ('1A01P', '2026-11-23'): 89, ('1A01P', '2026-11-24'): 90,
        # 00:00 UTC is 8 hours after the previous day's 16:00 report and 16 hours before the next.
        ('4D17P', '2026-11-23'): 351, ('4D17P', '2026-11-24'): 364,
        # Of the 15:00, 16:00 and 17:00 readings, the 16:00 one is kept.
        ('3A25P', '2026-11-23'): 500, ('3A25P', '2026-11-24'): 510,
    }
    assert names['4D17P'] == 'Forrest Kerr High Elevation Snow'


def test_parse_enso():
    e = ingest.parse_enso('SEAS   YR  ANOM\nDJF  1950 -1.19\nJFM  1950 -1.08\n')
    assert e.to_dict('records') == [{'season': 'DJF', 'year': 1950, 'value': -1.19},
                                    {'season': 'JFM', 'year': 1950, 'value': -1.08}]


def test_parse_enso_rejects_an_unexpected_format():
    with pytest.raises(ingest.SourceRejected):
        ingest.parse_enso('A B C\n1 2 3\n')


# ---------------------------------------------------------------- database semantics

def test_archive_replaces_current_rows_it_covers(con):
    snowdb.replace_swe(con, obs([('A', '2026-09-29', 1.0), ('A', '2026-09-30', 2.0), ('A', '2026-10-01', 3.0)]), 'current')
    snowdb.replace_swe(con, obs([('A', '2026-09-29', 10.0), ('A', '2026-09-30', 20.0)]), 'archive')
    assert all_swe(con) == [('A', '2026-09-29', 10.0, 'archive'), ('A', '2026-09-30', 20.0, 'archive'),
                            ('A', '2026-10-01', 3.0, 'current')]


def test_current_reload_keeps_last_year_until_the_archive_has_it(con):
    # On 1 October SWDaily.csv restarts with the new water year; last year's rows must survive.
    snowdb.replace_swe(con, obs([('A', '2026-09-30', 5.0)]), 'current')
    snowdb.replace_swe(con, obs([('A', '2026-10-01', 0.0)]), 'current')
    assert len(all_swe(con)) == 2


def test_current_reload_replaces_its_own_range_but_never_archive_rows(con):
    snowdb.replace_swe(con, obs([('A', '2026-10-01', 1.0)]), 'archive')
    snowdb.replace_swe(con, obs([('A', '2026-10-01', 99.0), ('A', '2026-10-02', 2.0), ('B', '2026-10-02', 7.0)]), 'current')
    # Next version of the file: A revised, B's value removed upstream.
    snowdb.replace_swe(con, obs([('A', '2026-10-01', 99.0), ('A', '2026-10-02', 3.0)]), 'current')
    assert all_swe(con) == [('A', '2026-10-01', 1.0, 'archive'), ('A', '2026-10-02', 3.0, 'current')]


def test_station_placeholders_filled_by_seed_and_replaced_by_metadata(con):
    def one(**cols):
        return pd.DataFrame({k: [v] for k, v in cols.items()})
    snowdb.upsert_stations(con, one(station_id='A', name='From header'), mode='keep')
    snowdb.upsert_stations(con, one(station_id='A', name='Seed', latitude=50.0, longitude=-120.0), mode='fill')
    assert con.execute('SELECT name, latitude FROM stations').fetchone() == ('Seed', 50.0)
    snowdb.upsert_stations(con, one(station_id='A', name='Other seed', latitude=1.0, longitude=1.0), mode='fill')
    assert con.execute('SELECT name FROM stations').fetchone() == ('Seed',)
    snowdb.upsert_stations(con, one(station_id='A', name='Official', latitude=50.1, longitude=-120.1), mode='replace')
    assert con.execute('SELECT name, latitude FROM stations').fetchone() == ('Official', 50.1)


# ---------------------------------------------------------------- run_ingest with fake downloads

def fake_sources(monkeypatch, responses):
    '''responses: source -> file text, None (unchanged), or an exception to raise.'''
    def fake_fetch(url, state, force=False):
        source = next(s for s, u in ingest.URLS.items() if u == url)
        response = responses[source]
        if isinstance(response, Exception):
            raise response
        return response, 'Thu, 26 Nov 2026 16:02:04 GMT', '"etag"'
    monkeypatch.setattr(ingest, 'fetch', fake_fetch)


GOOD = {'stations': STATIONS_CSV, 'swe_archive': SWE_CSV, 'swe_current': SWE_CURRENT_CSV, 'enso': roni_text()}


def test_run_ingest_loads_every_source(con, monkeypatch):
    fake_sources(monkeypatch, GOOD)
    out = ingest.run_ingest(con)
    assert all(v.startswith('updated') for v in out.values()), out
    assert snowdb.data_version(con) == 1
    assert snowdb.count_rows(con, 'swe_daily') == 7
    assert snowdb.get_source_state(con, 'swe_archive')['etag'] == '"etag"'


def test_unchanged_sources_do_not_bump_the_version(con, monkeypatch):
    fake_sources(monkeypatch, GOOD)
    ingest.run_ingest(con)
    fake_sources(monkeypatch, dict.fromkeys(GOOD))
    out = ingest.run_ingest(con, force=True)
    assert set(out.values()) == {'unchanged'}
    assert snowdb.data_version(con) == 1


def test_a_failed_source_keeps_the_last_good_data(con, monkeypatch):
    fake_sources(monkeypatch, GOOD)
    ingest.run_ingest(con)
    before = all_swe(con)
    fake_sources(monkeypatch, {'stations': ConnectionError('site down'), 'swe_archive': 'garbage\nnot a date,1\n',
                               'swe_current': None, 'enso': None})
    out = ingest.run_ingest(con, force=True)
    assert out['stations'].startswith('error') and out['swe_archive'].startswith('error')
    assert all_swe(con) == before
    assert snowdb.data_version(con) == 1
    state = snowdb.get_source_state(con, 'swe_archive')
    assert state['last_error'] and state['last_success']


def test_an_archive_that_shrinks_a_lot_is_rejected(con, monkeypatch):
    fake_sources(monkeypatch, GOOD)
    ingest.run_ingest(con)
    fake_sources(monkeypatch, {**dict.fromkeys(GOOD), 'swe_archive': 'DATE(UTC),1A01P Yellowhead Lake\n2026-11-23 16:00,89\n'})
    out = ingest.run_ingest(con, force=True)
    assert 'shrank' in out['swe_archive']
    assert snowdb.count_rows(con, 'swe_daily') == 7


# ---------------------------------------------------------------- snapshot

def test_build_snapshot(con):
    dates = pd.date_range('2023-10-01', '2026-11-25')
    rows = [('A', d.strftime('%Y-%m-%d'), 100.0) for d in dates]
    rows += [('B', d.strftime('%Y-%m-%d'), 50.0) for d in dates if d >= pd.Timestamp('2026-10-01')]
    snowdb.replace_swe(con, obs(rows), 'current')
    snowdb.upsert_stations(con, pd.DataFrame({'station_id': ['A', 'B', 'C'], 'name': ['Alpha', 'Beta', 'No data'],
                                              'latitude': [50, 51, 52], 'longitude': [-120, -121, -122]}))
    snowdb.replace_enso(con, pd.DataFrame({'season': ['OND', 'ASO'], 'year': [2025, 2026], 'value': [-0.7, 1.2]}))
    snowdb.bump_data_version(con)
    snap = datastore.build_snapshot(con)
    assert snap.current_wy == 2027
    assert snap.start_range == [0.5, 3]
    assert list(snap.stations.index) == ['A', 'B']           # C has no data, so it isn't mapped
    assert snap.stations.loc['A', 'anom_status'] == 'ok'
    assert snap.stations.loc['A', 'pct_of_median'] == 100
    assert snap.stations.loc['A', 'n_seasons'] == 3
    assert snap.stations.loc['B', 'anom_status'] == 'no_median'
    assert snap.stations['active'].all()
    assert '100% of median' in snap.stations.loc['A', 'hover']
