# FlightPaper API Contract (v1)

Every request and response body shown here is the **plaintext** that goes
inside the secure envelope (`packages/protocol/secure-envelope.schema.json`)
unless the endpoint is in §1 (public). See `protocol.md` for envelope
construction and validation rules.

Defaults: `host=0.0.0.0`, `port=8080`. All endpoints are JSON, UTF-8.

---

## 1. Public endpoints

### `GET /api/public/health`

Response 200:
```json
{
  "ok": true,
  "device_id": "fp_a1b2c3d4",
  "version": "0.1.0",
  "uptime_seconds": 1234
}
```

### `GET /api/public/pairing-status`

Response 200:
```json
{
  "state": "unpaired" | "pairing_pending" | "paired",
  "device_id": "fp_a1b2c3d4",
  "device_name": "FlightPaper",
  "pairing_expires_at": 1710000600,
  "protocol_version": 1
}
```

`pairing_expires_at` is omitted when state is not `pairing_pending`.

### `POST /api/public/pair`

Request body is a secure envelope whose `key_id` is `pairing` and whose
ciphertext is:
```json
{
  "client_id": "iphone_93ab1f2c0e10",
  "client_pub": "<base64url X25519 public key>",
  "device_pub": "<base64url X25519 public key seen in QR>",
  "app_instance_name": "Amir's iPhone 16",
  "protocol_version": 1,
  "nonce_echo": "<base64url echo of QR nonce>",
  "ts": 1710000300
}
```

Response body is a secure envelope (still keyed `pairing`):
```json
{
  "ok": true,
  "device_id": "fp_a1b2c3d4",
  "client_id": "iphone_93ab1f2c0e10",
  "key_id": "main",
  "paired_at": 1710000305,
  "session_starts_at_seq": 1
}
```

On failure, the response envelope plaintext follows the error shape in
`protocol.md` §7.

---

## 2. Secure endpoints

All require a verified envelope. All return an envelope wrapping the JSON
shapes below. The `key_id` is `main`.

### `POST /api/secure/location`

Request:
```json
{
  "lat": 43.3255,
  "lon": -79.7990,
  "accuracy_m": 8.5,
  "altitude_m": 120.0,
  "heading_deg": 52.0,
  "speed_mps": 1.4,
  "timestamp": 1710000400,
  "source": "iphone_foreground" | "iphone_background"
}
```

Validation: lat ∈ [-90, 90], lon ∈ [-180, 180], `accuracy_m` ≥ 0,
`timestamp` within ±1 day of server clock. Heading and speed optional.

Response:
```json
{
  "accepted": true,
  "age_seconds": 0,
  "received_at": 1710000401
}
```

### `GET /api/secure/status`

Response (verbatim shape from `flightpod-plan.md` §16):
```json
{
  "device": {
    "id": "fp_a1b2c3d4",
    "name": "FlightPaper",
    "version": "0.1.0",
    "uptime_seconds": 1234
  },
  "network": {
    "wifi_ssid": "Amir-iPhone",
    "ip_address": "172.20.10.4",
    "internet_ok": true
  },
  "battery": {
    "percent": 82,
    "charging": false,
    "external_power": false,
    "battery_saver": false
  },
  "location": {
    "source": "iphone_background",
    "age_seconds": 14,
    "accuracy_m": 8.5,
    "fresh": true
  },
  "opensky": {
    "status": "ok" | "stale" | "rate_limited" | "error" | "no_location",
    "last_update_age_seconds": 12,
    "aircraft_count": 7,
    "rate_limit_remaining": null
  },
  "display": {
    "page": "radar",
    "last_refresh_age_seconds": 4
  }
}
```

Any nested object may carry `null` when data is unknown (e.g. battery if
PiSugar is missing).

### `GET /api/secure/aircraft`

Query parameters (optional):
- `limit` (1..50, default 20)
- `sort` (`distance` | `overhead` | `altitude`, default `distance`)

Response:
```json
{
  "aircraft": [
    {
      "icao24": "a1b2c3",
      "callsign": "ACA123",
      "origin_country": "Canada",
      "longitude": -79.81,
      "latitude": 43.33,
      "baro_altitude_ft": 31250,
      "geo_altitude_ft": 31300,
      "on_ground": false,
      "velocity_kt": 468,
      "true_track_deg": 82,
      "vertical_rate_fpm": 0,
      "squawk": "1234",
      "distance_km": 1.7,
      "bearing_deg": 51,
      "age_seconds": 8
    }
  ],
  "as_of_seconds": 12,
  "count": 7,
  "radius_km": 25
}
```

Units in this endpoint use **display units** (knots, feet, ft/min, km) so
the mobile app does not need conversion. `bearing_deg` is from user to
aircraft, 0=N, 90=E.

### `GET /api/secure/config`

Returns the current Pi config as a flat-ish JSON, mirroring
`config.example.yml`. The full canonical shape is in
`apps/pi/config.example.yml`.

### `PATCH /api/secure/config`

Request is a partial config with only the keys to change. Server validates
and rejects out-of-range values. Response is the merged effective config.
Pi persists the merged config atomically (`tmp -> rename`).

Patchable keys (whitelist):
```
opensky.update_interval_seconds
opensky.battery_saver_interval_seconds
opensky.max_aircraft_age_seconds
opensky.include_ground_aircraft
location.manual.enabled
location.manual.lat
location.manual.lon
location.manual.label
display.partial_refresh
display.full_refresh_every
display.default_page
ui.radius_km
ui.overhead_threshold_km
ui.distance_units
ui.altitude_units
ui.speed_units
battery.low_percent
battery.critical_percent
battery.battery_saver_below_percent
buttons.long_press_ms
buttons.very_long_press_ms
```

Not patchable over the network: `security.*`, `api.*`, `app.name`,
`app.version`.

### `POST /api/secure/display/page`

Request:
```json
{ "page": "radar" | "closest" | "list" | "status" }
```

Response:
```json
{ "ok": true, "page": "radar" }
```

### `POST /api/secure/refresh`

Forces a full ePaper refresh and an immediate OpenSky poll (subject to
the `min_interval_seconds` floor). Response: `{ "ok": true }`.

### `POST /api/secure/system/shutdown`

Request: `{ "confirm": true }`.

Response: `{ "ok": true, "shutdown_in_seconds": 5 }` then the process
spawns `systemctl poweroff` and exits.

### `POST /api/secure/system/reboot`

Same shape as shutdown but spawns `systemctl reboot`.

### `POST /api/secure/pairing/reset`

Request: `{ "confirm": true }`.

Effect: deletes all paired-client records and the current session keys.
Display jumps to the pairing page on next render. The calling client's
session is invalidated immediately.

Response: `{ "ok": true }` (sent before invalidation).

---

## 3. Error envelope

Errors use the envelope plaintext shape in `protocol.md` §7. HTTP status
mirrors the table in that section. Examples:

- 401 `bad_envelope` — envelope failed AEAD or schema check.
- 401 `replay` — sequence or nonce already used.
- 401 `expired` — timestamp drift outside replay window.
- 410 `pairing_expired` — one-time secret no longer valid.
- 429 `attempt_limit` — too many failed pair attempts.
- 503 `not_ready` — no location yet, OpenSky not initialized.
