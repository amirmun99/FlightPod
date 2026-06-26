# FlightPaper

A portable Raspberry Pi Zero 2 W + Waveshare 2.13" ePaper device that
shows nearby aircraft using the OpenSky Network, controlled and
configured by an Expo iPhone companion app over the phone's hotspot.

> FlightPaper is informational only. Not for navigation, flight safety,
> emergency use, aircraft separation, or operational aviation decisions.
> Aircraft data may be delayed, incomplete, inaccurate, or unavailable.

**New here?** Start with [`docs/getting-started.md`](docs/getting-started.md)
— a guided walkthrough from an empty SD card and a fresh Mac to a working
device.

---

## Table of contents

1. [What FlightPaper is](#1-what-flightpaper-is)
2. [Hardware required](#2-hardware-required)
3. [System architecture](#3-system-architecture)
4. [Security architecture](#4-security-architecture)
5. [Pairing process](#5-pairing-process)
6. [Raspberry Pi install](#6-raspberry-pi-install)
7. [Expo app setup](#7-expo-app-setup)
8. [Building the iPhone development build](#8-building-the-iphone-development-build)
9. [Background location setup](#9-background-location-setup)
10. [iPhone hotspot workflow](#10-iphone-hotspot-workflow)
11. [OpenSky API setup](#11-opensky-api-setup)
12. [ePaper display testing](#12-epaper-display-testing)
13. [PiSugar testing](#13-pisugar-testing)
14. [Troubleshooting](#14-troubleshooting)
15. [Disclaimer](#15-disclaimer)

---

## 1. What FlightPaper is

FlightPaper polls OpenSky for state vectors in a bounded box around the
iPhone's GPS, filters and sorts them, and renders the result on a
250×122 1-bit ePaper. The iPhone app does the configuration, drives
GPS, and surfaces status. The Pi does the rendering, the OpenSky
query, and the battery / Wi-Fi housekeeping.

It is a **personal proof-of-concept**. It's not for navigation, traffic
separation, alerting, or any operational aviation use.

See [`docs/overview.md`](docs/overview.md) for the long version.

## 2. Hardware required

| Item | Notes |
|---|---|
| Raspberry Pi Zero 2 W | Wi-Fi + USB. |
| microSD (16 GB+) | Class 10 or better; flash Raspberry Pi OS Lite (Bookworm 64-bit). |
| PiSugar 3 1200 mAh | Battery + RTC + power button + soft-shutdown. |
| Waveshare 2.13" ePaper HAT V2 / Rev2.1 | 250×122 1-bit, SPI. |
| Micro-USB cable | First boot + charging. |
| iPhone with hotspot | Companion app is iOS-only. |

Full assembly + first-boot guide at [`docs/hardware.md`](docs/hardware.md).

## 3. System architecture

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
|  - OpenSky poller       |     (AEAD) over LAN ==>  - Background GPS    |
|  - Aircraft filter/sort |                      |  - Settings UI        |
|  - Pillow ePaper render |                      |  - Status / aircraft  |
|  - PiSugar battery      |                      |  - SecureStore keys   |
|  - Pairing state machine|                      |                       |
+-------------------------+                      +-----------------------+
            ▲                                                ▲
            │                                                │
            +-----------+ iPhone hotspot LAN +----------------+
```

The Pi listens on plain HTTP over the iPhone hotspot LAN. Every
protected message is wrapped in an application-layer encrypted
envelope. See [`docs/overview.md`](docs/overview.md) for more detail
and [`packages/protocol/protocol.md`](packages/protocol/protocol.md)
for the normative wire definition.

## 4. Security architecture

- Pairing is QR-rooted, one-shot. The QR carries a one-time
  `pairing_secret`; the Pi burns it after a successful handshake.
- Long-term session key is derived via X25519 ECDH + HKDF-SHA256.
- Every protected request/response is sealed with
  XChaCha20-Poly1305 (24-byte nonce, AEAD-bound to method + path).
- Replay defended by a monotonic per-client `seq` window + a 120-second
  `ts` skew tolerance.
- Pi keeps device + paired-client state under
  `/etc/flightpaper/secure/` (`0700 root:root`).
- iPhone keeps the session key in iOS Keychain via `expo-secure-store`.

Full threat model + limitations at [`docs/security.md`](docs/security.md).

## 5. Pairing process

1. The Pi boots. With no paired client it enters `pairing_pending`
   and renders a QR on the ePaper.
2. You scan the QR with the FlightPaper iPhone app.
3. The app derives the symmetric pairing key from the QR, generates
   its X25519 keypair, and posts `POST /api/public/pair` with an
   encrypted envelope.
4. The Pi verifies, derives the matching session key, persists the
   paired client, and replies (still encrypted under the pairing
   key).
5. Both sides now have identical long-term session keys. Every
   subsequent request travels in a secure envelope.

End-to-end flow with diagrams at [`docs/pairing.md`](docs/pairing.md).
Manual fallback (IP + 6-digit code) and reset procedure are documented
there too.

## 6. Raspberry Pi install

```bash
# On a fresh Pi running Raspberry Pi OS Lite (Bookworm):
git clone https://github.com/your-fork/rpi-flightpod.git
cd rpi-flightpod
sudo apps/pi/install.sh
sudo systemctl status flightpaper
sudo journalctl -u flightpaper -f
```

The installer:

- apt-installs Python 3.11+, libsodium, Pillow's JPEG2000 dep,
  fonts-dejavu-core, build essentials, i2c-tools, git.
- Enables SPI + I2C via `raspi-config nonint`.
- rsyncs the package to `/opt/flightpaper`, builds a venv, installs
  `flightpaper[hardware]`.
- Creates `/etc/flightpaper/` + `/etc/flightpaper/secure/` (`0700`).
- Seeds `/etc/flightpaper/config.yml` from `config.example.yml` (only if
  the file doesn't exist — re-installs preserve your config).
- Installs and enables the systemd unit.

Reinstalls are safe: they preserve `/etc/flightpaper/secure/` (device
identity + paired clients). Full purge:

```bash
sudo apps/pi/uninstall.sh --purge
```

See [`apps/pi/README.md`](apps/pi/README.md) for the Pi-side details.

## 7. Expo app setup

```bash
cd apps/mobile
npm install
npm run typecheck

# Run in the iOS Simulator via Expo Go (foreground GPS only):
npm run start:go
```

For non-trivial use you'll want a real device + a dev client (next
section). All the screens are exercisable in mock device mode
(`Security → Mock device toggle`) so a fresh install with no Pi
nearby is still useful.

## 8. Building the iPhone development build

```bash
cd apps/mobile
npx eas init             # one-time, against your Expo account
npm run build:dev:ios    # eas build --profile development --platform ios
```

The Expo dev client is required because:

- `expo-task-manager` background callbacks **never fire under Expo Go**.
- `NSLocalNetworkUsageDescription` must be in the binary's Info.plist.
- `UIBackgroundModes = ["location"]` must be embedded at build time.

A **free Apple ID** can sign a dev build but with a **7-day expiration**.
A **paid Apple Developer Program** account ($99/yr) removes the expiry
and unlocks reliable background-task delivery — see
[`docs/iphone-background-location.md`](docs/iphone-background-location.md)
for the caveats.

## 9. Background location setup

iPhone permissions are two-stage:

1. **Allow While Using App** (When-In-Use) — foreground only.
2. **Allow Always (background)** — Live GPS, only available after
   step 1.

Both buttons live on the Location screen. iOS will only show the
"Always" dialog *after* foreground has been granted; the screen
guides the user through the upgrade explicitly. Force-quitting the
app suspends background delivery permanently until re-open — this is
by design on iOS.

Full doc at
[`docs/iphone-background-location.md`](docs/iphone-background-location.md).

## 10. iPhone hotspot workflow

1. Turn on Personal Hotspot on the iPhone. Confirm the SSID + password.
2. Power on the Pi. It associates to the saved hotspot SSID set
   during SD-card imaging.
3. Confirm the IP printed on the pairing QR matches `hostname -I`
   over SSH.
4. Open the app and scan the QR.

The Pi listens only on the hotspot LAN. There is no port forwarding
or NAT punch-through. Anyone associated to the hotspot can *see* the
Pi but cannot decrypt protected payloads.

## 11. OpenSky API setup

Anonymous mode works for personal use. To raise the rate limit:

```bash
sudo bash -c 'cat >> /etc/flightpaper/env <<EOF
OPENSKY_CLIENT_ID=your-client-id
OPENSKY_CLIENT_SECRET=your-secret
EOF'
sudo chmod 0600 /etc/flightpaper/env
sudo systemctl restart flightpaper
```

The systemd unit reads `/etc/flightpaper/env` via `EnvironmentFile`.
Full polling-interval + bounding-box + backoff details at
[`docs/opensky.md`](docs/opensky.md).

## 12. ePaper display testing

Render any page to PNG from a dev machine (no hardware needed):

```bash
cd apps/pi
.venv/bin/python scripts/render_preview.py --page radar --output /tmp/r.png
open /tmp/r.png
```

Or every page at once:

```bash
.venv/bin/python scripts/render_preview.py --all \
  --output-dir ../../docs/img
```

On a real Pi:

```bash
sudo /opt/flightpaper/.venv/bin/python /opt/flightpaper/scripts/test_display.py
```

Page-by-page previews are embedded in
[`docs/display-layouts.md`](docs/display-layouts.md).

## 13. PiSugar testing

```bash
# Confirm the official server is running:
systemctl status pisugar-server

# Talk to it directly:
echo "get battery" | nc 127.0.0.1 8423
echo "get battery_charging" | nc 127.0.0.1 8423

# FlightPaper-side test (no battery → "no battery info" cleanly):
sudo /opt/flightpaper/.venv/bin/python /opt/flightpaper/scripts/test_battery.py
```

If `pisugar-server` is not installed, the device still works — the
status bar shows `BAT --` and nothing else breaks.

## 14. Troubleshooting

Common gotchas:

- Blank ePaper → wrong driver variant (`display.driver` in config).
- `BAT --` → `pisugar-server` not installed / not running.
- `NO WIFI` → hotspot SSID changed or off.
- `NO LOCATION` → open the app, start Live GPS.
- `API LIMITED` → OpenSky 429; auto-backoff in progress.
- Pair failure → re-scan the QR after the next rotation.
- Live GPS button greyed out → "Always" permission missing.

Full table at [`docs/troubleshooting.md`](docs/troubleshooting.md).

## 15. Disclaimer

FlightPaper is informational only. **Not for navigation, flight safety,
emergency use, aircraft separation, or operational aviation decisions.**
Aircraft data may be delayed, incomplete, inaccurate, or unavailable.

---

## What's in this repo

```
apps/pi/        Raspberry Pi service (Python, FastAPI, Pillow)
apps/mobile/    iPhone companion app (Expo, React Native, TypeScript)
packages/       Shared schemas and protocol docs
docs/           Architecture, security, pairing, hardware, troubleshooting
```

## License

MIT. See [LICENSE](LICENSE).
