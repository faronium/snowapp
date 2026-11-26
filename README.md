## ENSO Snow BC

A [Dash](https://dash.plotly.com/) web app, live at [www.ensosnowbc.ca](https://www.ensosnowbc.ca), for exploring the
relationship between the El Niño Southern Oscillation (ENSO) and snow accumulation in British Columbia. It shows
water-year snow water equivalent (SWE) at BC's automated snow pillow stations. The seasons can be filtered by ENSO
strength (CPC's Relative Oceanic Niño Index, RONI), and a map colours each station by its current SWE as a
percentage of its median for the date.

The Analysis and Help tabs in the app explain the plots and controls.

### How it works

```
BC snow data, station metadata, CPC RONI
        │  ingest.py: conditional downloads every 3 hours, sanity checks, replace what each file covers
        ▼
SQLite database (snowdb.py)                ./data/snow.sqlite, or $SNOWAPP_DB
        │  datastore.py: in-memory snapshot, rebuilt when the data change
        ▼
Dash app (snowapp.py) ── snowmap.py, snowplot.py (figures) ── snowdata.py (analysis)
```

* **`ingest.py`** fetches each source with a conditional GET, so a check that finds nothing new costs one small
  request per source. Each downloaded file is parsed, checked, and then replaces the date range it covers. A
  source that fails is logged and skipped, and the database keeps its last good data.
* **`datastore.py`** runs the ingest in a background thread inside the web process every `SNOWAPP_REFRESH_HOURS`
  (default 3). When the data change, it rebuilds the tables the callbacks read. On a fresh database the first load
  takes about a minute, and the page shows a "loading" message that reloads by itself.
* **`snowdata.py`** holds the analysis: water years, complete seasons, medians and ranges, current anomalies, and
  ENSO values by water year. These are plain functions of pandas objects, covered by the tests.
* **`snowapp.ipynb`** is a scratch notebook that imports the modules for exploring the data. The app doesn't use it.

### Running locally

```bash
python3 -m venv ~/venvs/snowapp       # under WSL, a venv on the Linux side imports much faster than one under /mnt/c
source ~/venvs/snowapp/bin/activate
pip install -r requirements-dev.txt
python ingest.py                      # build or update ./data/snow.sqlite (first run under a minute)
python snowapp.py                     # http://127.0.0.1:8050
pytest                                # 33 tests, a few seconds, no network needed
```

Settings, all optional:

| Environment variable    | Default              | Meaning                                    |
|-------------------------|----------------------|--------------------------------------------|
| `SNOWAPP_DB`            | `./data/snow.sqlite` | Location of the SQLite database            |
| `SNOWAPP_REFRESH_HOURS` | `3`                  | How often the app checks the sources       |

The database can be deleted at any time; it is rebuilt from the sources. To look inside it:
`sqlite3 data/snow.sqlite "SELECT * FROM source_state"`. The tables are `stations`, `swe_daily`, `enso_index`,
`source_state` and `meta`, described in `snowdb.py`.

### Deploying

The app runs as `gunicorn snowapp:server`. Gunicorn picks up `gunicorn.conf.py` (one process, four threads) on
both platforms. Python 3.12 comes from `.python-version`.

**Heroku**: `git push heroku main`. The `Procfile` gives the start command. Heroku's disk is wiped at every
restart, so the database is rebuilt each time the dyno starts, roughly daily.

**Railway** (set up in the dashboard; Railway no longer accepts new `railway.toml` files):

1. New service from the GitHub repo, `main` branch. Railway's builder (Railpack) installs `requirements.txt`.
2. Settings → Deploy: set the **Custom Start Command** to `gunicorn snowapp:server`. Railpack would otherwise
   guess a Flask command that points at the wrong module. Set the **Healthcheck Path** to `/healthz`.
3. Add a **Volume** mounted at `/data`, and the variable `SNOWAPP_DB=/data/snow.sqlite`, so the database
   survives restarts and deploys.
4. Settings → Networking: generate a `*.up.railway.app` domain to test, then add the custom domain.

### Data notes

* **ENSO index**: CPC made the [Relative Oceanic Niño Index](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/)
  its official ENSO index on 1 February 2026, replacing the ONI. RONI is used throughout. A water year's value is
  the largest-magnitude RONI among the OND to MAM seasons, with OND and NDJ assigned to the following water year.
* **Daily values**: BC reports at 16:00 UTC. A few stations report at other times: the Forrest Kerr pillows at
  00:00 UTC, and some stations hourly for parts of their record. Each reading is assigned to the nearest 16:00 UTC
  report time, and the reading closest to 16:00 is kept for each station and day.
* **Complete seasons**: a past water year with data on at least 95% of the days from 1 October to 16 August.
  Medians, ranges and the "20 complete seasons" filter use only these. The current season is never included.
* **Map anomaly**: a station's latest reading from the last 3 days of data, as a percentage of its median for that
  date. Stations are grey when the median is under 10 mm, or when there is no recent reading or no complete season.
* **Water-year roll-over**: BC restarts `SWDaily.csv` on 1 October but adds the finished water year to the archive
  weeks later (21 November in 2026). The database keeps the finished year's data in the meantime.

### Data sources

* Snow water equivalent: [BC automated snow weather stations](https://www.env.gov.bc.ca/wsd/data_searches/snow/asws/data/),
  BC Ministry of Environment and Climate Change Strategy and partners.
* Station metadata: BC Data Catalogue, `WHSE_WATER_MANAGEMENT.SSL_SNOW_ASWS_STNS_SP`. `snow/SNW_ASWS.csv` is a
  snapshot, used only if the catalogue can't be reached when the database is first built.
  See `snow/BC_Data_Catalogue_License.txt`.
* RONI: NOAA Climate Prediction Center, `https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt`.

#### Disclaimer
This tool is intended for educational or entertainment purposes only. Official analysis of the snow and
water supply status for British Columbia is available from the
[BC River Forecast Centre](https://www2.gov.bc.ca/gov/content/environment/air-land-water/water/drought-flooding-dikes-dams/river-forecast-centre/snow-survey-water-supply-bulletin).
The author makes no warranty
nor is liable for anything associated with or resulting from the use of the app or the underlying data.
No claims for data correctness or accuracy are made. This application is not affiliated with the Government
of British Columbia, BC Hydro, Rio Tinto or Metro Vancouver.

#### Author and Contact Information
Faron Anslow
<faron.anslow@gmail.com>
