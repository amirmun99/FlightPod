# Development guide

This doc tracks the **phased build** and the day-to-day development
workflow. The full product/engineering spec is at `flightpod-plan.md`
in the repo root.

## Phased build (complete)

| # | Phase | Goal | Status |
|---|---|---|---|
| 0 | Monorepo & protocol | Directory tree, root files, `packages/protocol` | done |
| 1 | Pi skeleton + utilities | `flightpaper` package, config, logging, geo/units | done |
| 2 | OpenSky + aircraft pipeline | Client, parser, filter, sort, mock server | done |
| 3 | Location system | Phone provider, manager, freshness | done |
| 4 | Security: crypto, pairing, envelope | PyNaCl, ECDH, HKDF, AEAD, replay | done |
| 5 | Pi local API server | FastAPI, public + secure routes, background tasks | done |
| 6 | Display stack | Renderer + Waveshare Rev2.1 + PiSugar | done |
| 7 | Mobile: Expo skeleton | Expo TS template, perms, navigation, state | done |
| 8 | Mobile: secure client + pairing | QR scanner, envelope, SecureStore, live E2E pair | done |
| 9 | Mobile: background location | `expo-task-manager` task + retry queue | done |
| 10 | Mobile: remaining screens | Settings PATCH, status, aircraft list, etc. | done |
| 11 | Install + docs | `install.sh`, systemd, full docs | done |

## Locked decisions

- ePaper variant: Waveshare 2.13" V2 / Rev2.1, 250×122, B/W
- PiSugar 3 via official `pisugar-server` on `127.0.0.1:8423`
- iOS dev: free Apple ID only — real background-location E2E deferred
- Build cadence: phase-by-phase checkpoints (delivered as 12
  checkpoints 0–11)
- API framework: FastAPI
- Crypto: X25519 ECDH + HKDF-SHA256 + XChaCha20-Poly1305 (libsodium
  both sides) — note we ended up at **XChaCha20** (24-byte nonce) not
  ChaCha20 (12-byte), because the 24-byte nonce lets both sides pick
  nonces at random with no risk of collision
- Pairing key: **symmetric** (HKDF over `pairing_secret + device_id +
  device_pub`) — refactored away from ECDH to avoid the
  chicken-and-egg with `client_pub` living inside the encrypted
  envelope
- OpenSky: anonymous default; `OPENSKY_CLIENT_ID/SECRET` enable auth
- Mobile state: zustand
- Mobile background location defaults: distanceInterval 50 m,
  timeInterval 45 s, `Accuracy.Balanced`
- License: MIT

## Working on the Pi side from macOS

The Pi package is designed to run on macOS for development. SPI,
GPIO, and the Waveshare driver are import-guarded. Use the dev
scripts:

```bash
cd apps/pi
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                                  # 315 tests, ~2 s

# Render any ePaper page:
python scripts/render_preview.py --page radar --output /tmp/radar.png
open /tmp/radar.png

# Render all pages (used by docs/display-layouts.md):
python scripts/render_preview.py --all --output-dir ../../docs/img

# Run the server against the OpenSky mock:
python scripts/mock_opensky_server.py &
uvicorn flightpaper.api.server:app --reload --port 9077
```

## Working on the mobile side

```bash
cd apps/mobile
npm install

# Typecheck — passes on Node 18+, 22+, 24+. Node 25 + tsx hangs;
# the helper scripts below use bare Node CJS to work around it.
node node_modules/typescript/bin/tsc --noEmit

# Pure-logic verifiers (no RN runtime needed):
node scripts/verify-crypto.cjs          # 8 crypto interop checks vs. Pi
node scripts/verify-location.cjs        # 17 location queue + sanitizer checks
node scripts/verify-stores.cjs          # 34 store + validator checks

# Live E2E pair against a running uvicorn Pi:
node scripts/e2e-pair.cjs
```

### Mock device mode

Toggle **Security → Mock device mode** in the app to swap the real
device client for a canned one
([`apps/mobile/src/services/mock/mockDeviceClient.ts`](../apps/mobile/src/services/mock/mockDeviceClient.ts)).
Mock mode lets you exercise every screen without a Pi nearby, and
PATCH-with-validation actually mutates the in-process mock state so
the UI feels real.

### `expo start` workflow

```bash
npm run start         # dev-client (needs an installed dev build)
npm run start:go      # Expo Go (foreground-only; background task won't fire)
```

You'll want a dev client + a paid Apple Developer Program account for
real background-location testing. See
[`iphone-background-location.md`](iphone-background-location.md) for
the free-Apple-ID caveat.

## Cross-language interop

The crypto invariant for FlightPaper is that the JS-side
`deriveSessionKey()` and the Python-side `derive_session_key()` must
return identical bytes for identical inputs. `verify-crypto.cjs`
catches drift:

- HKDF-SHA256 matches RFC 5869 Test Case 1
- Pi-sealed envelope opens on JS
- JS-sealed envelope opens on the Pi (round-tripped through
  `scripts/e2e-pair.cjs` against a live server)

Touching either side's crypto module requires re-running both
`verify-crypto.cjs` and the Pi-side `pytest`.

## Layout

```
rpi-flightpod/
  README.md       LICENSE     .gitignore     .env.example
  docs/           overview, hardware, security, pairing, …
  apps/
    pi/           Python service (FastAPI + Pillow + PyNaCl)
      flightpaper/                      ← package
      scripts/                          ← dev + ops tools
      systemd/flightpaper.service
      tests/                            ← 315 pytest cases
      install.sh  uninstall.sh
    mobile/       Expo + RN + TypeScript companion
      src/                              ← screens, components, services
      scripts/                          ← CJS verifiers + E2E pair
  packages/
    protocol/                           ← protocol.md + JSON schemas
```

## Test matrix

| Side | Command | Coverage |
|---|---|---|
| Pi  | `pytest` (`apps/pi/tests`) | 315 tests: crypto, envelope, replay, pairing, OpenSky, aircraft pipeline, location manager, layouts, hardware drivers |
| Mobile typecheck | `tsc --noEmit` | every file in `apps/mobile/src` |
| Mobile interop | `node scripts/verify-crypto.cjs` | 8 crypto-interop checks against Python output |
| Mobile location | `node scripts/verify-location.cjs` | 17 queue / sanitizer / batch checks |
| Mobile stores | `node scripts/verify-stores.cjs` | 34 store + validator checks |
| Live E2E | `node scripts/e2e-pair.cjs` | Full pair + secure `GET /status` against uvicorn |

## Releasing

For the Pi: tag the commit, push to your fork, ssh into the device,
`git pull && sudo apps/pi/install.sh`. The installer re-syncs the
package, restarts the service, and preserves
`/etc/flightpaper/secure/`.

For the iPhone app: bump `expo.version` in `apps/mobile/app.config.ts`,
`npm run build:production:ios` against a paid Apple Developer account.
