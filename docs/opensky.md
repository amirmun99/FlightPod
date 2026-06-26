# OpenSky integration

FlightPaper queries the OpenSky Network REST API for state vectors in
a bounding box around the phone's location. Anonymous mode works fine
for personal use; the optional client-id/secret unlocks a higher rate
limit.

## Anonymous vs authenticated

| Mode | Polling cadence | Daily credits |
|---|---|---|
| Anonymous (default) | every 30–60 s recommended | ~400/day shared per IP |
| Authenticated (`OPENSKY_CLIENT_ID` + `OPENSKY_CLIENT_SECRET`) | every 5–10 s allowed | ~4000/day for the account |

To enable authenticated mode on the Pi:

```bash
sudo bash -c 'cat >> /etc/flightpaper/env <<EOF
OPENSKY_CLIENT_ID=your-client-id
OPENSKY_CLIENT_SECRET=your-secret
EOF'
sudo chmod 0600 /etc/flightpaper/env
sudo systemctl restart flightpaper
```

The systemd unit reads `/etc/flightpaper/env` via `EnvironmentFile`.
Setting these variables flips `opensky.auth_enabled = true` in the
loaded `AppConfig` (see
[`apps/pi/flightpaper/opensky/client.py`](../apps/pi/flightpaper/opensky/client.py)).

## Bounding-box math

Given the phone's `(lat, lon)` and a configured `radius_km`:

```
lat_delta = radius_km / 111.0
lon_delta = radius_km / (111.0 * cos(radians(lat)))
lamin = lat - lat_delta
lamax = lat + lat_delta
lomin = lon - lon_delta
lomax = lon + lon_delta
```

We clamp `lat` to `[-89.9, 89.9]` before applying the cosine to keep
`lon_delta` from blowing up at the poles. The exact code is in
[`apps/pi/flightpaper/utils/geo.py`](../apps/pi/flightpaper/utils/geo.py)
under `latlon_bbox`.

OpenSky expects the bbox as `lamin, lomin, lamax, lomax`. We pass the
clamped values directly; the API returns every state vector whose
last-known `(lat, lon)` falls inside the box.

## Polling interval interaction

Three configuration knobs determine the actual poll cadence:

```yaml
opensky:
  update_interval_seconds: 20            # baseline
  battery_saver_interval_seconds: 60     # used when battery_saver is on
  min_interval_seconds: 10               # hard floor (rate-limit safety)
```

The effective interval is:

```
target  = battery_saver ? battery_saver_interval : update_interval
effective = max(target, min_interval_seconds, backoff_until - now)
```

When OpenSky returns 429 we set `backoff_until = now + retry_after`
(if the header is present) or `now + 60` (otherwise) — see the
backoff helper in
[`apps/pi/flightpaper/opensky/rate_limit.py`](../apps/pi/flightpaper/opensky/rate_limit.py).

## Stale-data behavior

If OpenSky is unreachable or returns 429, the poller keeps the last
known good state vectors and marks them stale. Two things happen:

1. The radar / list pages keep rendering the last batch.
2. The status block reports `opensky.status = "stale"` and a non-`null`
   `last_update_age_seconds`. The companion app surfaces this on the
   Home screen.

We never silently drop stale aircraft — the user is told the data is
old. Aircraft older than `opensky.max_aircraft_age_seconds` (default
120) are filtered out of the rendered set even within the last good
batch.

## Rate-limit headers

OpenSky doesn't always return a `Retry-After`, but it does include
`X-Rate-Limit-Remaining` on success responses. We surface the most
recent value in `status.opensky.rate_limit_remaining` so the companion
app can warn when you're approaching the cap.

## Why anonymous mode is fine for most users

A walking pace generates a new bbox every minute or so, the OpenSky
API serves a couple hundred bytes per response, and the ~400/day
credit budget is generous enough for a half-day outing at a 60-second
cadence. Authenticated mode is only useful if you want a much faster
update cycle (e.g. running the device on a desk and refreshing every
5 s for hours).
