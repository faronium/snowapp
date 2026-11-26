# Gunicorn settings. Gunicorn reads this file automatically when started from this directory, so the same
# `gunicorn snowapp:server` command works on Heroku (Procfile) and Railway (start command in the dashboard).
#
# One process with several threads: each process keeps its own in-memory copy of the data and runs its own
# refresh thread (see datastore.py), so more processes would only multiply memory use. This also overrides the
# WEB_CONCURRENCY=2 that Heroku's Python buildpack sets for a 512 MB dyno.
workers = 1
threads = 4

# Allow slow requests (a figure for a station with a long record) without the worker being killed.
timeout = 120

# No bind setting: when the PORT environment variable is set (Heroku and Railway both set it), gunicorn
# listens on 0.0.0.0:$PORT; otherwise on 127.0.0.1:8000.
