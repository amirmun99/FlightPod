# Overview

FlightPaper is a Raspberry Pi Zero 2 W + Waveshare 2.13" ePaper device that
shows nearby aircraft using OpenSky. Configuration and GPS come from a
paired Expo iPhone companion app over the phone's hotspot.

> FlightPaper is informational only. Not for navigation, flight safety,
> emergency use, aircraft separation, or operational aviation decisions.
> Aircraft data may be delayed, incomplete, inaccurate, or unavailable.

## What it does

- Polls the OpenSky Network REST API for state vectors in a bounded box
  around the phone's GPS.
- Filters, sorts (closest / overhead / by altitude), and renders the
  result on a 250×122 ePaper at one of four pages (radar, closest, list,
  status).
- Exposes a local HTTPS-optional API on the Pi that the iPhone app drives
  for all configuration, status, refresh, and a "shutdown safely" button.
- Streams the phone's foreground + background GPS to the Pi as the
  authoritative location source.

## What it does **not** do

- It's a personal proof-of-concept, not a navigation aid.
- It does not authenticate against the public OpenSky tier beyond the
  optional client-id/secret env vars.
- It does not perform real-time traffic separation, alerting, or any
  ATC-related function.
- It does not expose itself to the public internet by default. Every
  protected message is application-layer encrypted, but the Pi only
  listens on the iPhone-hotspot LAN.

## Who it's for

Hobbyists who like aviation, ePaper, and Raspberry Pi. The whole system
fits in a pocket on battery, the iPhone supplies network + GPS, and the
device is silent + low-power.

## System diagram

```
                          OpenSky REST API
                          (bounded box around
                           phone GPS)
                                ▲
                                │ HTTPS
                                │
+-------------------------+      QR scan         +-----------------------+
|  ePaper Pi (Pi Zero 2W) | <------------------- |  iPhone Expo app      |
|                         |                      |                       |
|  - FastAPI local server | <== Secure envelopes |  - QR pairing         |
|  - OpenSky poller       |     (AEAD) over LAN==>  - Background GPS    |
|  - Aircraft filter/sort |                      |  - Settings UI        |
|  - Pillow ePaper render |                      |  - Status / aircraft  |
|  - PiSugar battery      |                      |  - SecureStore keys   |
|  - Pairing state machine|                      |                       |
+-------------------------+                      +-----------------------+
            ▲                                                ▲
            │                                                │
            +-----------+ iPhone hotspot LAN +----------------+
```

## How the pieces fit

1. The Pi boots and renders a pairing QR on the ePaper.
2. The iPhone scans the QR, which carries the device id, the Pi's
   long-term X25519 public key, a one-time `pairing_secret`, and the
   IP+port to reach the Pi on.
3. The iPhone runs the pairing handshake (`POST /api/public/pair`)
   under a symmetric pairing key derived from the QR. On success both
   sides derive a long-term ECDH session key, and the QR is invalidated.
4. The iPhone starts the `Live GPS` background task. The Pi receives
   POSTs to `/api/secure/location` and uses them as the lat/lon for the
   OpenSky bounding-box query.
5. The Pi polls OpenSky on a configurable interval, processes the state
   vectors into our `Aircraft` shape (distance, bearing, age), and
   renders the active ePaper page.
6. The iPhone polls `/api/secure/status` and `/api/secure/aircraft` to
   mirror what the device is doing, and PATCHes
   `/api/secure/config` to change behavior.

## Why the phone owns configuration and GPS

- The Pi has no realistic input method (one PiSugar button, no
  keyboard).
- iPhone GPS is more accurate and updates continuously even when the
  device is in a pocket.
- All editable configuration lives on the phone as a form; the Pi
  persists `config.yml` and reloads cleanly on save.

## Where to read more

- [`docs/security.md`](security.md) — threat model + crypto choices.
- [`docs/pairing.md`](pairing.md) — end-to-end QR-pair flow.
- [`docs/iphone-background-location.md`](iphone-background-location.md) —
  iOS perm flow + the free-Apple-ID caveat.
- [`docs/opensky.md`](opensky.md) — anon vs auth, rate limits, bbox math.
- [`docs/display-layouts.md`](display-layouts.md) — ePaper pages, with
  generated previews.
- [`docs/hardware.md`](hardware.md) — assembly + first boot.
- [`docs/troubleshooting.md`](troubleshooting.md) — common errors + fixes.
- [`docs/development.md`](development.md) — phased build plan + local
  dev workflow.
- [`packages/protocol/protocol.md`](../packages/protocol/protocol.md) —
  the normative wire protocol.
