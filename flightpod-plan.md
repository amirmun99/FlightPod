# Coding Agent Prompt: Build FlightPaper — Raspberry Pi ePaper Flight Display + Expo iPhone Companion App

You are an expert full-stack embedded/mobile engineer. Build a complete project called **FlightPaper**.

FlightPaper is a portable Raspberry Pi Zero 2 W + ePaper device that shows nearby aircraft using the OpenSky API. It is controlled and configured by an Expo-based iPhone companion app. The iPhone app provides GPS location, background location updates, pairing, settings, and device control. The Raspberry Pi handles OpenSky polling, aircraft filtering, ePaper rendering, battery monitoring, and a secure local API.

The final output should be a clean project folder containing both the Raspberry Pi software and the Expo mobile app, organized as a single monorepo.

This is a personal proof-of-concept project and will not be published publicly. However, still implement the project with professional security, reliability, and maintainability.

---

# 1. High-Level Product Goal

Create a small portable device that a user can turn on, connect to their iPhone hotspot, pair with their iPhone by scanning a QR code on the ePaper screen, and immediately see aircraft around them.

The ePaper device should show:

* Nearby aircraft within a configurable radius.
* A simple radar-style overhead map.
* Closest / overhead aircraft.
* Aircraft callsign or ICAO24 fallback.
* Altitude.
* Speed.
* Direction / track.
* Distance and bearing from user.
* Last aircraft update age.
* Phone location age.
* Battery percentage.
* Wi-Fi / API / pairing status.

The iPhone app should handle:

* Pairing with the Pi using QR code.
* Sending GPS to the Pi, including background updates.
* Changing all configuration options.
* Viewing current Pi status.
* Viewing aircraft list/status from the Pi.
* Selecting display page.
* Triggering refresh.
* Safe shutdown/reboot.
* Wi-Fi configuration if reasonably possible.

The Pi should require minimal physical input. Physical buttons should be used only for simple emergency or convenience functions.

---

# 2. Hardware

Target Raspberry Pi hardware:

```text
Raspberry Pi Zero 2 W
Raspberry Pi OS Lite
PiSugar 3 1200mAh battery board
Waveshare 2.13-inch ePaper HAT
Mobile phone hotspot for internet
iPhone running the Expo companion app
```

The user referred to the Pi as “Raspberry Pi 2 Zero W.” Assume this means **Raspberry Pi Zero 2 W**, but keep the code lightweight enough that it may work on a slower Zero W if needed.

---

# 3. ePaper Display Specifications

The ePaper display is a Waveshare 2.13-inch ePaper HAT.

Known specs:

```text
Operating voltage: 3.3V / 5V
Interface: SPI
Resolution: 250 × 122
Display color: black / white
Grey level: 2
Partial refresh time: 0.3s
Full refresh time: 2s
Refresh power: 26.4mW typical
Standby power: <0.017mW
Viewing angle: >170°
Dot pitch: 0.194 × 0.194
Outline dimension: 65mm × 30.2mm
Display size: 23.71mm × 48.55mm
Driver board revision: Rev2.1 / Version 2.1
```

Interface pins:

```text
VCC  = 3.3V / 5V
GND  = Ground
NC   = No connect
DIN  = SPI MOSI
CLK  = SPI SCK
CS   = SPI chip select, active low
DC   = Data / command select
RST  = External reset, active low
BUSY = Busy status output, high active
```

Use landscape orientation by default:

```text
width: 250
height: 122
```

Important: Waveshare has multiple 2.13-inch variants. Implement a driver abstraction. Default to the Rev2.1-compatible 250×122 driver, but make the exact driver selectable in config.

---

# 4. PiSugar 3 1200mAh Requirements

Target battery board:

```text
PiSugar 3 1200mAh
```

Required battery features:

* Read battery percentage.
* Read charging/external power status if available.
* Display battery percentage on ePaper.
* Display charging indicator if available.
* Battery saver mode below configurable threshold.
* Low battery warning.
* Critical battery safe-shutdown.
* Optional PiSugar watchdog support if available and safe.
* Gracefully continue if PiSugar tools are not installed.
* Provide a test script for PiSugar communication.

Prefer using the PiSugar official software/server interface where available instead of writing raw I2C commands. Avoid raw I2C writes unless the command is documented and safe.

If PiSugar cannot be detected:

* Do not crash.
* Show `BAT --`.
* Log a single warning.
* Continue running normally.

---

# 5. Operating System

Target OS:

```text
Raspberry Pi OS Lite
No desktop environment
No GUI shell
SSH enabled
SPI enabled
I2C enabled
NetworkManager preferred for Wi-Fi management
systemd service for boot startup
```

The Pi app must run headlessly as a systemd service.

Suggested install locations:

```text
/opt/flightpaper
/etc/flightpaper/config.yml
/etc/flightpaper/secrets.env
/etc/flightpaper/secure/
/var/log/flightpaper/
/etc/systemd/system/flightpaper.service
```

---

# 6. Project Architecture

Use a monorepo:

```text
flightpaper/
  README.md
  LICENSE
  .gitignore
  .env.example
  docs/
    overview.md
    hardware.md
    security.md
    pairing.md
    iphone-background-location.md
    opensky.md
    display-layouts.md
    troubleshooting.md
    development.md

  apps/
    pi/
      README.md
      pyproject.toml
      requirements.txt
      config.example.yml
      install.sh
      uninstall.sh

      systemd/
        flightpaper.service

      scripts/
        enable_interfaces.sh
        test_display.py
        test_buttons.py
        test_battery.py
        test_opensky.py
        render_preview.py
        generate_pairing_qr.py
        mock_opensky_server.py
        reset_pairing.py

      flightpaper/
        __init__.py
        main.py
        app.py
        config.py
        logging_setup.py

        api/
          __init__.py
          server.py
          routes_pairing.py
          routes_secure.py
          routes_status.py
          schemas.py
          auth.py
          secure_envelope.py

        security/
          __init__.py
          device_identity.py
          pairing.py
          key_store.py
          crypto.py
          replay.py
          tokens.py

        opensky/
          __init__.py
          client.py
          models.py
          parser.py
          rate_limit.py
          provider.py

        location/
          __init__.py
          manager.py
          models.py
          providers.py
          phone_provider.py
          manual_provider.py

        aircraft/
          __init__.py
          processor.py
          filters.py
          sort.py

        display/
          __init__.py
          epaper.py
          waveshare_driver.py
          renderer.py
          layouts.py
          fonts.py
          symbols.py
          qr.py

        ui/
          __init__.py
          state.py
          pages.py
          input.py

        hardware/
          __init__.py
          buttons.py
          battery.py
          pisugar3.py
          wifi.py
          power.py
          system_info.py

        utils/
          __init__.py
          geo.py
          units.py
          time_utils.py
          cache.py
          validators.py

      tests/
        test_geo.py
        test_units.py
        test_opensky_parser.py
        test_aircraft_processor.py
        test_location_manager.py
        test_secure_envelope.py
        test_pairing.py
        test_replay.py
        test_renderer.py

    mobile/
      README.md
      package.json
      app.config.ts
      eas.json
      tsconfig.json
      babel.config.js

      src/
        App.tsx

        app/
          navigation/
            RootNavigator.tsx
          state/
            deviceStore.ts
            settingsStore.ts
            locationStore.ts
          theme/
            colors.ts
            spacing.ts
            typography.ts

        screens/
          PairingScreen.tsx
          DeviceHomeScreen.tsx
          RadarScreen.tsx
          AircraftListScreen.tsx
          SettingsScreen.tsx
          LocationScreen.tsx
          WifiScreen.tsx
          DeviceStatusScreen.tsx
          SecurityScreen.tsx
          LogsScreen.tsx
          AboutScreen.tsx

        components/
          StatusCard.tsx
          AircraftRow.tsx
          BatteryBadge.tsx
          ApiStatusBadge.tsx
          LocationStatusBadge.tsx
          SettingRow.tsx
          DangerButton.tsx
          PairingQrScanner.tsx

        services/
          api/
            client.ts
            endpoints.ts
            secureEnvelope.ts
            pairingClient.ts
            deviceClient.ts
          location/
            foregroundLocation.ts
            backgroundLocationTask.ts
            locationSender.ts
          storage/
            secureStore.ts
            deviceRegistry.ts
          crypto/
            keys.ts
            envelope.ts
            replay.ts
            random.ts
          network/
            discovery.ts
            connectivity.ts

        types/
          device.ts
          aircraft.ts
          config.ts
          location.ts
          security.ts

        utils/
          units.ts
          geo.ts
          time.ts
          validation.ts

      assets/
        icon.png
        splash.png

  packages/
    protocol/
      README.md
      protocol.md
      pairing-payload.schema.json
      secure-envelope.schema.json
      api-contract.md
```

The coding agent may adjust small details, but the final project should remain clearly separated into:

```text
apps/pi
apps/mobile
packages/protocol
docs
```

---

# 7. Main Technical Stack

## Raspberry Pi Side

Use:

```text
Python 3.11+
FastAPI or Flask for local API
Pydantic for validation if using FastAPI
requests or httpx for OpenSky API
Pillow for ePaper rendering
spidev for SPI
gpiozero or lgpio-compatible button handling
PyYAML for config
cryptography or PyNaCl for crypto
qrcode or segno for QR generation
systemd for service management
pytest for tests
```

Prefer FastAPI if it remains lightweight enough on the Pi Zero 2 W. Flask is also acceptable. Reliability is more important than framework preference.

## iPhone Companion App

Use:

```text
Expo
React Native
TypeScript
Expo development build / EAS build
expo-location
expo-task-manager
expo-camera or current Expo-supported barcode scanning
expo-secure-store
expo-network if helpful
react-native-safe-area-context
zustand or lightweight state management
```

Do not rely on Expo Go for the final app because background location and native config requirements need a development build.

Use a clean native-compatible Expo configuration with the required iOS permission strings and background mode.

---

# 8. iPhone App Background GPS Requirements

Background GPS sending is required.

Implement:

* Foreground location sending.
* Background location task.
* Live connection mode.
* Automatic background GPS updates while paired and enabled.
* Configurable background update interval/distance.
* Last successful send timestamp.
* Retry queue for failed location posts.
* Stop background updates from the app.
* Start background updates from the app.
* Clear warning if iOS permissions are not set to Always.
* Clear warning if the app has been force-quit and background delivery may stop.

Use `expo-location` and `expo-task-manager`.

Required app behavior:

1. User pairs with FlightPaper.
2. User enables “Live GPS to FlightPaper.”
3. App requests foreground location permission.
4. App requests background location permission.
5. App registers a background location task.
6. When location updates arrive, app sends encrypted location payloads to the Pi.
7. If the Pi is unreachable, app queues the latest location update and retries.
8. If too many failures occur, app marks the device disconnected but keeps background task available.
9. When the app reopens, show a full status of background permission, last send, last failure, and paired device.

Suggested background defaults:

```text
Foreground live send interval: 10–20 seconds
Background send interval: 30–60 seconds
Distance trigger: 25–100 meters
Max queued location points: 20
Only send newest point if queue grows too large
```

The app should not try to upload an unlimited location history. The Pi only needs current location.

The mobile app should include a “developer/personal mode” assumption in documentation, but it should still behave safely and respectfully with permissions.

---

# 9. iOS App Configuration Requirements

Configure Expo app for:

```text
Location When In Use
Location Always / Background
Background location mode
Local network access
Camera access for QR scanning
ATS/local networking allowance if needed
```

Use `app.config.ts` rather than only static `app.json`.

Include iOS Info.plist entries conceptually equivalent to:

```text
NSLocationWhenInUseUsageDescription
NSLocationAlwaysAndWhenInUseUsageDescription
NSCameraUsageDescription
NSLocalNetworkUsageDescription
NSAppTransportSecurity / NSAllowsLocalNetworking if needed
UIBackgroundModes = location
```

If using Bonjour/mDNS discovery later, include relevant Bonjour service declarations. For MVP, manual IP + QR is enough.

---

# 10. Security Model

Security is important. The Pi and phone communicate over a local network, usually the iPhone hotspot. Assume the local network may still be observable by another device. Do not send raw secrets, raw GPS, or raw configuration payloads in plaintext after pairing.

Implement a practical, strong local pairing/security system.

## Security Goals

Protect against:

* Random devices on the same hotspot controlling the Pi.
* Passive LAN observers reading GPS payloads.
* Replay attacks.
* Accidental unpaired access.
* Stale pairing tokens.
* Unauthorized shutdown/reboot/config changes.
* Secret leakage in logs.

Not required for MVP:

* Public internet exposure.
* Cloud identity.
* Multi-user account system.
* App Store-level distribution.

## Required Security Design

Use physical QR pairing as the trust root.

The Pi generates:

```text
device_id
device_name
one-time pairing_secret
pairing_nonce
pairing_expires_at
optional device public key
optional certificate fingerprint
```

The ePaper displays a QR code containing a compact pairing URI:

```text
flightpaper://pair?...compact payload...
```

The QR payload should include enough information for the phone to connect and securely pair:

```text
host
port
device_id
device_name short
pairing_secret or pairing seed
pairing expiration timestamp
protocol version
```

The ePaper should also show manual fallback:

```text
IP: 172.20.10.4
Pair Code: 123-456
```

Manual fallback should still use a strong secret or a short-lived code that is exchanged safely. If using a short human-readable code, limit attempts and expire it quickly.

## Recommended Crypto Approach

Implement application-layer encryption and authentication for all sensitive endpoints.

Recommended approach:

* Use well-maintained crypto libraries.
* Do not invent cryptographic primitives.
* Use X25519 for key agreement if practical.
* Use HKDF for key derivation.
* Use ChaCha20-Poly1305 or AES-GCM for authenticated encryption.
* Use a monotonic sequence number or nonce per message.
* Use replay protection.
* Store keys securely.

If X25519 is too heavy for the mobile stack, a strong PSK-derived session key from the QR secret is acceptable for MVP, provided:

* QR secret is high entropy.
* Secret is at least 128 bits, preferably 256 bits.
* Secret is never transmitted over the network.
* Pairing expires quickly.
* Secret is single-use.
* All post-pairing messages use AEAD encryption.
* Replay protection is implemented.

Preferred MVP protocol:

1. Pi boots unpaired or pairing is reset.
2. Pi creates a high-entropy one-time pairing secret.
3. Pi displays QR with local host/IP, device ID, and pairing secret.
4. iPhone scans QR.
5. iPhone derives an initial pairing key using HKDF.
6. iPhone sends an encrypted pairing request containing:

   * phone client ID
   * phone public key if using ECDH
   * app instance name
   * timestamp
   * nonce
7. Pi decrypts and validates it.
8. Pi creates a paired-client record.
9. Pi and phone derive a persistent device-client session key.
10. Pi returns encrypted pairing success.
11. Pi invalidates the one-time pairing secret.
12. All future API calls use encrypted envelopes.

## Secure Envelope

All protected requests and responses should use a secure envelope.

Example conceptual JSON:

```json
{
  "v": 1,
  "device_id": "fp_a1b2c3d4",
  "client_id": "iphone_93ab...",
  "key_id": "main",
  "seq": 42,
  "ts": 1710000000,
  "nonce": "base64url...",
  "ciphertext": "base64url..."
}
```

Associated data should include:

```text
HTTP method
path
device_id
client_id
seq
timestamp
protocol version
```

Reject messages when:

* client is unknown
* timestamp is too old
* sequence number is replayed
* nonce was reused
* authentication tag is invalid
* device is locked
* endpoint requires a permission not granted to that client

For personal MVP, one paired iPhone is enough, but design the key store to allow multiple clients later.

## Storage

On Pi:

```text
/etc/flightpaper/secure/device_identity.json
/etc/flightpaper/secure/paired_clients.json
/etc/flightpaper/secure/pairing_state.json
```

Permissions:

```text
owner: root
mode: 600
```

On iPhone:

* Store paired device identity and secrets using Expo SecureStore or the most secure practical storage available.
* Do not store secrets in plain AsyncStorage.
* Non-secret display preferences may use normal app storage.

## API Authentication

Unauthenticated endpoints allowed before pairing:

```text
GET  /api/public/health
GET  /api/public/pairing-status
POST /api/public/pair
```

Everything else must require secure envelope:

```text
POST /api/secure/location
GET  /api/secure/status
GET  /api/secure/aircraft
GET  /api/secure/config
PATCH /api/secure/config
POST /api/secure/display/page
POST /api/secure/refresh
POST /api/secure/system/shutdown
POST /api/secure/system/reboot
POST /api/secure/pairing/reset
```

Do not log:

* pairing secrets
* session keys
* decrypted GPS payloads beyond normal status summaries
* Wi-Fi passwords
* OpenSky secrets

Provide a security document explaining the threat model and what is/is not protected.

---

# 11. Pairing UX

On first boot or after pairing reset, the ePaper should show:

```text
PAIR FLIGHTPAPER

[ QR CODE ]

IP 172.20.10.4
Code 123-456
```

QR should fit on the 250×122 ePaper screen. Use a compact QR payload.

Suggested layout:

```text
+------------------------------------------------+
| PAIR FLIGHTPAPER                               |
| +----------------+  Scan in app                |
| |                |  IP: 172.20.10.4            |
| |      QR        |  Code: 123-456              |
| |                |  Expires: 10m               |
| +----------------+                             |
+------------------------------------------------+
```

Since the display is only 122 px tall, use:

* QR size around 86×86 to 96×96 px if readable.
* Text on the right.
* Keep payload short.
* Use low or medium error correction.
* Provide manual IP and code below/right of QR.

The mobile app flow:

1. Open app.
2. Tap “Pair Device.”
3. Scan ePaper QR.
4. App parses pairing URI.
5. App connects to Pi.
6. App completes encrypted pairing.
7. App shows “Paired.”
8. App requests location permissions.
9. App offers to start Live GPS.
10. Pi display changes to main radar/status page.

Manual pairing fallback:

* User enters IP.
* User enters pair code.
* App contacts Pi.
* Pi requires the short code plus additional challenge to avoid unlimited guessing.
* Rate limit attempts.
* Expire code.

---

# 12. Phone-to-Pi Connectivity

Normal mode:

```text
iPhone hotspot ON
Raspberry Pi connects to iPhone hotspot
iPhone app connects to Raspberry Pi over hotspot LAN
```

MVP device discovery:

* QR contains current Pi IP.
* App saves last known IP.
* App can manually reconnect.
* App can scan common hotspot subnet only if safe/reasonable.
* App can try `flightpaper.local` if mDNS works, but do not depend on it.

Do not require BLE.

Do not require a Pi-hosted setup AP for MVP.

If Pi has no IP, ePaper should show:

```text
NO WIFI
Connect hotspot or configure Wi-Fi
```

If Pi has Wi-Fi but no pairing:

```text
PAIR REQUIRED
Scan QR in app
IP: xxx.xxx.xxx.xxx
```

---

# 13. OpenSky API Requirements

Use OpenSky Network REST API for aircraft data.

Main endpoint conceptually:

```text
GET /api/states/all
```

Use bounding-box parameters:

```text
lamin
lomin
lamax
lomax
extended optional
```

Never request global state data. Always query a bounding box around the current phone-provided location.

Bounding-box calculation:

```text
lat_delta = radius_km / 111.0
lon_delta = radius_km / (111.0 * cos(latitude_radians))
lamin = lat - lat_delta
lamax = lat + lat_delta
lomin = lon - lon_delta
lomax = lon + lon_delta
```

After the API returns aircraft in the rectangular bounding box, filter using true Haversine distance.

Default radius:

```text
25 km
```

Allowed radius values:

```text
5 km
10 km
25 km
50 km
100 km
```

Default update interval:

```text
20 seconds
```

Battery saver interval:

```text
60 seconds
```

Minimum interval:

```text
10 seconds
```

Handle:

* Anonymous OpenSky mode.
* Optional authenticated OpenSky mode.
* Rate limits.
* HTTP 429.
* Network timeout.
* Missing data fields.
* Stale data.
* No aircraft.
* API outage.

Environment variables:

```text
OPENSKY_CLIENT_ID=
OPENSKY_CLIENT_SECRET=
```

If credentials are absent, run anonymous mode.

---

# 14. Aircraft Data Parsing

Parse OpenSky state vectors into a typed model.

Aircraft model:

```python
@dataclass
class Aircraft:
    icao24: str
    callsign: str | None
    origin_country: str | None
    time_position: int | None
    last_contact: int | None
    longitude: float | None
    latitude: float | None
    baro_altitude_m: float | None
    on_ground: bool
    velocity_mps: float | None
    true_track_deg: float | None
    vertical_rate_mps: float | None
    geo_altitude_m: float | None
    squawk: str | None
    spi: bool | None
    position_source: int | None
    category: int | None
    distance_km: float | None = None
    bearing_deg: float | None = None
    age_seconds: int | None = None
```

Filter rules:

* Exclude missing latitude/longitude.
* Exclude ground aircraft by default.
* Exclude aircraft older than configured max age.
* Default max aircraft age: 120 seconds.
* Keep missing altitude/speed aircraft but render missing values as `--`.
* Sort closest first.
* Prioritize overhead candidates.

Overhead definition:

```text
Default: within 2 km horizontal distance
Configurable: 1 km / 2 km / 5 km
```

Units:

```text
Altitude: feet
Speed: knots
Distance: km by default, optional nautical miles
Vertical speed: ft/min
```

---

# 15. Location System

Primary location source is the paired iPhone companion app.

The Pi should maintain:

```text
current_location
location_source
location_accuracy_m
location_timestamp
location_age
last_location_receive_time
```

Location model:

```python
@dataclass
class Location:
    lat: float
    lon: float
    accuracy_m: float | None
    altitude_m: float | None
    heading_deg: float | None
    speed_mps: float | None
    source: str
    timestamp: int
    received_at: int
```

The mobile app should send:

```json
{
  "lat": 43.3255,
  "lon": -79.7990,
  "accuracy_m": 8.5,
  "altitude_m": 120.0,
  "heading_deg": 52.0,
  "speed_mps": 1.4,
  "timestamp": 1710000000,
  "source": "iphone_background"
}
```

Validate:

* Latitude range.
* Longitude range.
* Accuracy sanity.
* Timestamp sanity.
* Reject impossible values.
* Reject stale location unless explicitly allowed.

Location freshness:

```text
Fresh: < 2 minutes
Warning stale: > 15 minutes
Expired: > 60 minutes
```

If no valid location:

* Do not call OpenSky.
* Display location setup screen.
* Ask user to open the companion app.
* Show IP/pairing state.

Manual location fallback:

* App can set a manual location.
* Pi config can also contain a manual location.
* Manual location should be clearly labelled on display.

No IP geolocation is required for this version.

No external GPS is required for this version.

No ADS-B dongle is required for this version.

---

# 16. Raspberry Pi Local API

Implement a local API server on the Pi.

Default:

```text
host: 0.0.0.0
port: 8080
```

The security layer should protect sensitive payloads. If using HTTP, payloads must still be encrypted/authenticated at the application layer. Optional HTTPS can be added if practical.

Public routes:

```text
GET  /api/public/health
GET  /api/public/pairing-status
POST /api/public/pair
```

Secure routes:

```text
POST /api/secure/location
GET  /api/secure/status
GET  /api/secure/aircraft
GET  /api/secure/config
PATCH /api/secure/config
POST /api/secure/display/page
POST /api/secure/refresh
POST /api/secure/system/shutdown
POST /api/secure/system/reboot
POST /api/secure/pairing/reset
```

Suggested status response:

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
    "status": "ok",
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

---

# 17. Configuration Ownership

All normal configuration should be done from the iPhone app, not from the ePaper buttons.

The Pi still stores config locally.

Config file:

```text
/etc/flightpaper/config.yml
```

Settings controlled by iPhone app:

```text
radius_km
update_interval_seconds
battery_saver_update_interval_seconds
units
overhead_threshold_km
show_ground_aircraft
max_aircraft_age_seconds
display_page
partial_refresh_enabled
full_refresh_every
brightness not applicable
manual_location
OpenSky auth status
Wi-Fi config if implemented
safe shutdown threshold
```

Do not require deep menu navigation on the Pi.

The Pi physical controls should be minimal:

```text
short press: cycle display page
long press: force refresh
very long press: safe shutdown confirmation
```

If only PiSugar buttons are available, implement the simplest reliable mapping possible.

---

# 18. ePaper UI Pages

Required pages:

1. Pairing Page
2. Boot Page
3. Radar Page
4. Closest / Overhead Page
5. Aircraft List Page
6. Status Page
7. Error / Recovery Page
8. Shutdown Confirmation Page

## Global Status Bar

Show compact status:

```text
82% W API 12s LOC 14s
```

Status tokens:

```text
Battery percent
Wi-Fi connected indicator
API status
Aircraft update age
Location age
Pairing/lock status if relevant
```

## Pairing Page

Show:

* QR code.
* IP.
* Pair code.
* Expiration.

## Radar Page

Default page after pairing and location.

Requirements:

* Center dot = user.
* North-up map.
* Radius ring.
* Aircraft triangles.
* Aircraft labels for closest few only.
* Closest aircraft summary at bottom.

Aircraft projection:

```text
bearing = bearing from user to aircraft
distance_ratio = aircraft_distance / selected_radius
x = center_x + sin(bearing) * radius_px * distance_ratio
y = center_y - cos(bearing) * radius_px * distance_ratio
```

Draw only closest N aircraft:

```text
max aircraft drawn: 12
max labels: 3
```

## Closest / Overhead Page

Show:

```text
OVERHEAD / CLOSEST
ACA123
1.7 km NE  31,250 ft
468 kt  TRK 082°
Seen 8s ago
```

If no aircraft:

```text
NO AIRCRAFT
within 25 km
Updated 14s ago
```

## Aircraft List Page

Show compact closest list:

```text
NEARBY 25km
ACA123  1.7km 31250ft
WJA456  8.4km 28100ft
DAL89   12km  34000ft
UAL22   18km  11900ft
```

## Status Page

Show:

```text
STATUS
BAT 82% CHG no
WiFi Amir-iPhone
IP 172.20.10.4
APP paired
LOC iPhone 14s
API OK AC 7
```

## Error Pages

Handle:

```text
No Wi-Fi
No internet
No pairing
No location
OpenSky API error
Rate limited
Display driver error
Low battery
Critical battery
```

Each error screen must tell the user the next useful action.

---

# 19. Display Refresh Strategy

Use Pillow to render images.

Renderer function:

```python
render_page(app_state, page_name) -> PIL.Image
```

Support preview rendering on development machine:

```bash
python scripts/render_preview.py --page radar --output preview.png
```

Refresh rules:

```text
Full refresh on boot
Full refresh on pairing page
Full refresh on page change
Partial refresh for normal data update if stable
Full refresh every N partial updates
Full refresh on dense screen changes
Sleep display after update if supported
```

Defaults:

```yaml
display:
  partial_refresh: true
  full_refresh_every: 10
  update_interval_seconds: 20
  max_aircraft_drawn: 12
  max_labels_drawn: 3
```

If partial refresh causes ghosting, config must allow:

```yaml
display:
  partial_refresh: false
```

---

# 20. Expo App Screens

Build a polished but simple iPhone app.

## Pairing Screen

Features:

* Scan QR code from ePaper.
* Manual IP/code fallback.
* Show pairing status.
* Explain local network permission.
* Save paired device securely.

## Device Home Screen

Show:

* Connected/disconnected.
* Battery.
* Wi-Fi.
* Location freshness.
* API status.
* Aircraft count.
* Current radius.
* Current display page.
* Last GPS send.

Actions:

* Send location now.
* Start/stop Live GPS.
* Change display page.
* Refresh aircraft now.
* Open settings.
* Shutdown/reboot with confirmation.

## Location Screen

Show:

* Foreground permission status.
* Background permission status.
* Last phone GPS fix.
* Last successful Pi send.
* Background task status.
* Accuracy.
* Update interval/distance settings.

Controls:

* Request permissions.
* Start Live GPS.
* Stop Live GPS.
* Send one location now.
* Open iOS settings if permissions are insufficient.

## Settings Screen

Allow editing:

```text
Radius
Update interval
Battery saver interval
Units
Overhead threshold
Include ground aircraft
Max aircraft age
Display refresh mode
Default page
Manual location
Low battery threshold
Critical battery threshold
```

Use secure API calls to push settings to Pi.

## Aircraft List Screen

Show aircraft data pulled from Pi, not directly from OpenSky.

Show:

* Callsign/ICAO
* Distance
* Bearing
* Altitude
* Speed
* Track
* Age

## Device Status Screen

Show detailed status:

* Pi uptime.
* App version.
* IP.
* Wi-Fi SSID.
* Battery.
* Charging.
* OpenSky status.
* Rate limit status if known.
* Last display refresh.
* Last location age.
* Logs summary if available.

## Security Screen

Show:

* Paired device ID.
* Paired client ID.
* Pairing status.
* Last secure message.
* Reset pairing button.
* Rotate keys button if implemented.
* Explanation that QR pairing is local and physical.

## Wi-Fi Screen

MVP:

* Show current SSID/IP.
* Show known network if available.

Optional advanced:

* Scan SSIDs.
* Add Wi-Fi network through NetworkManager.
* Do not log passwords.
* Do not store Wi-Fi password in mobile app after sending.

## About Screen

Include disclaimer:

```text
FlightPaper is informational only.
Not for navigation, flight safety, emergency use, or aircraft separation.
Data may be delayed, incomplete, or unavailable.
```

---

# 21. Mobile App State Management

Use lightweight state management.

Required stored state:

```typescript
type PairedDevice = {
  deviceId: string;
  name: string;
  host: string;
  port: number;
  clientId: string;
  protocolVersion: number;
  pairedAt: number;
  lastSeenAt?: number;
};
```

Secrets must be stored in SecureStore or equivalent, not plain storage.

Store non-secret app preferences separately.

The app should support one active paired device for MVP, but design for multiple later.

---

# 22. Background Location Sender

Implement a service layer:

```text
startBackgroundLocation(deviceId)
stopBackgroundLocation(deviceId)
sendCurrentLocationNow(deviceId)
handleBackgroundLocationTask(event)
queueFailedLocation(payload)
flushLocationQueue()
```

When a background location update arrives:

1. Load active paired device.
2. Load secure key material.
3. Build location payload.
4. Encrypt secure envelope.
5. POST to Pi.
6. Store result.
7. If fail, queue latest update.
8. Trim queue.

Do not keep unlimited GPS history.

The Pi only needs the newest current location.

---

# 23. OpenSky Polling Logic

The Pi should poll OpenSky only when:

* Device is paired or allowed in config.
* Valid location exists.
* Update interval has elapsed.
* API is not in backoff.
* Battery is not critical.
* Network appears available.

Polling should be independent from ePaper refresh but coordinated.

On successful poll:

* Update aircraft cache.
* Recompute sorted aircraft list.
* Re-render display if needed.
* Update API status.

On failure:

* Keep last successful aircraft cache.
* Mark stale.
* Show stale age.
* Back off appropriately.

---

# 24. Geospatial Utilities

Implement and test:

```text
haversine_km
bearing_deg
cardinal_direction
latlon_bbox
project_aircraft_to_screen
meters_to_feet
mps_to_knots
km_to_nm
mps_to_fpm
```

Cardinal directions:

```text
N
NE
E
SE
S
SW
W
NW
```

---

# 25. Button Handling

Keep button support minimal.

Configurable mapping.

Default:

```text
short press: next page
long press: force refresh
very long press: safe shutdown prompt
```

If multiple buttons are available:

```text
button 1: next page
button 2: previous page
button 3: force refresh
button 4: safe shutdown prompt
```

All advanced configuration belongs in the iPhone app.

---

# 26. Wi-Fi Handling

The Pi is normally connected to the iPhone hotspot.

MVP Wi-Fi requirements:

* Detect current SSID.
* Detect IP address.
* Show IP on ePaper.
* Expose network status to app.
* Try reconnect if disconnected.
* Document how to preconfigure hotspot credentials.

Optional Wi-Fi config through app:

* Use NetworkManager via safe subprocess calls.
* Never log Wi-Fi passwords.
* Validate SSID/password.
* Avoid shell interpolation.

Do not build Pi AP/captive portal mode for MVP unless easy. It is optional.

---

# 27. Logging

Pi logs:

```text
/var/log/flightpaper/flightpaper.log
/var/log/flightpaper/flightpaper.err
```

Log:

* startup
* display init
* battery init
* pairing state
* API status
* location updates summarized
* OpenSky fetch status
* refresh events
* errors

Do not log:

* precise GPS history in detail
* pairing secrets
* session keys
* decrypted secure payloads
* Wi-Fi passwords
* OpenSky client secret

Mobile app logs:

* Keep local debug logs.
* Do not store secrets.
* Do not store large location history.
* Provide log screen for recent connection errors.

---

# 28. Config Example

Create `apps/pi/config.example.yml`.

```yaml
app:
  name: FlightPaper
  version: "0.1.0"
  log_level: INFO
  timezone: America/Toronto

api:
  host: "0.0.0.0"
  port: 8080
  require_pairing: true
  secure_envelopes_required: true

security:
  pairing_enabled: true
  pairing_expires_seconds: 600
  max_pairing_attempts: 5
  replay_window_seconds: 120
  allow_unencrypted_debug: false

opensky:
  enabled: true
  base_url: "https://opensky-network.org/api"
  auth_enabled: false
  update_interval_seconds: 20
  battery_saver_interval_seconds: 60
  timeout_seconds: 8
  max_aircraft_age_seconds: 120
  include_ground_aircraft: false
  request_extended: false
  min_interval_seconds: 10

location:
  primary_source: "iphone"
  stale_warning_seconds: 900
  expired_seconds: 3600
  manual:
    enabled: false
    lat: null
    lon: null
    label: "Manual"

display:
  width: 250
  height: 122
  rotation: 0
  driver: "waveshare_2in13_rev2_1"
  partial_refresh: true
  full_refresh_every: 10
  max_aircraft_drawn: 12
  max_labels_drawn: 3
  default_page: "radar"

ui:
  radius_km: 25
  radius_options_km: [5, 10, 25, 50, 100]
  overhead_threshold_km: 2
  distance_units: "km"
  altitude_units: "ft"
  speed_units: "kt"
  north_up: true
  show_status_bar: true

battery:
  enabled: true
  provider: "pisugar3"
  low_percent: 15
  critical_percent: 5
  battery_saver_below_percent: 30
  safe_shutdown_enabled: true

buttons:
  enabled: true
  debounce_ms: 80
  long_press_ms: 800
  very_long_press_ms: 3000
  mapping_profile: "minimal"
```

---

# 29. Environment Example

Create `.env.example`.

```text
OPENSKY_CLIENT_ID=
OPENSKY_CLIENT_SECRET=
FLIGHTPAPER_CONFIG=/etc/flightpaper/config.yml
```

---

# 30. Systemd Service

Create:

```ini
[Unit]
Description=FlightPaper ePaper Flight Display
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/flightpaper
EnvironmentFile=-/etc/flightpaper/secrets.env
ExecStart=/opt/flightpaper/.venv/bin/python -m flightpaper.main
Restart=always
RestartSec=5
StandardOutput=append:/var/log/flightpaper/flightpaper.log
StandardError=append:/var/log/flightpaper/flightpaper.err

[Install]
WantedBy=multi-user.target
```

Root is acceptable for MVP because of GPIO/SPI/network control. If a safer user/group model is practical, document it.

---

# 31. Install Script

Create `apps/pi/install.sh`.

It should:

1. Check OS.
2. Install apt dependencies.
3. Enable SPI.
4. Enable I2C.
5. Install Python dependencies in venv.
6. Create `/opt/flightpaper`.
7. Copy app files.
8. Create `/etc/flightpaper`.
9. Create secure storage directory.
10. Set file permissions.
11. Install systemd unit.
12. Enable service.
13. Start service.
14. Print status and useful commands.

Useful commands to document:

```bash
sudo systemctl status flightpaper
sudo systemctl restart flightpaper
journalctl -u flightpaper -f
hostname -I
ls /dev/spi*
i2cdetect -y 1
nmcli dev wifi list
```

---

# 32. Testing Requirements

Pi tests:

```text
geo calculations
unit conversions
OpenSky parsing
aircraft filtering
aircraft sorting
location validation
secure envelope encryption/decryption
replay protection
pairing expiry
renderer smoke tests
QR generation
config patch validation
```

Mobile tests where practical:

```text
pairing URI parser
secure envelope builder
location payload validation
settings validation
device state reducer/store
```

Also include mock data:

```text
no aircraft
one overhead aircraft
many aircraft
missing callsign
missing altitude
stale aircraft
ground aircraft
API rate limit
network offline
no location
low battery
```

---

# 33. Development Preview Tools

Create tools that allow development without hardware:

```bash
# Render display previews
python apps/pi/scripts/render_preview.py --page radar --output radar.png

# Mock OpenSky API
python apps/pi/scripts/mock_opensky_server.py

# Test display
python apps/pi/scripts/test_display.py

# Test battery
python apps/pi/scripts/test_battery.py

# Test QR page
python apps/pi/scripts/generate_pairing_qr.py
```

Mobile app should support a mock device mode:

```text
Use mock status
Use mock aircraft
Use mock pairing
```

This allows UI development without the physical Pi.

---

# 34. README Requirements

The root README should explain:

1. What FlightPaper is.
2. Hardware required.
3. System architecture.
4. Security architecture.
5. Pairing process.
6. Raspberry Pi install.
7. Expo app setup.
8. Building iPhone development build.
9. Background location setup.
10. iPhone hotspot workflow.
11. OpenSky API setup.
12. ePaper display testing.
13. PiSugar testing.
14. Troubleshooting.
15. Disclaimer.

Pi README should include:

* OS Lite setup.
* SSH setup.
* SPI/I2C enable.
* Install script.
* systemd commands.
* Config file.
* Display driver notes.
* PiSugar notes.
* Troubleshooting.

Mobile README should include:

* npm install.
* Expo/EAS development build.
* Required iOS permissions.
* QR pairing.
* Background GPS.
* Local network permission.
* Debugging connection issues.

Security doc should include:

* Threat model.
* Pairing design.
* Key storage.
* Secure envelope.
* Replay protection.
* Pairing reset.
* Limitations.

---

# 35. Important UX Requirements

The device must always show the next useful action.

Examples:

No Wi-Fi:

```text
NO WIFI
Connect hotspot
or check saved SSID
```

Wi-Fi but unpaired:

```text
PAIR DEVICE
Scan QR in app
IP 172.20.10.4
```

Paired but no location:

```text
NO LOCATION
Open app
Start Live GPS
```

API limited:

```text
API LIMITED
Showing cached
Retry later
```

No aircraft:

```text
NO AIRCRAFT
within 25 km
Updated 14s ago
```

Low battery:

```text
LOW BATTERY
15%
Battery saver on
```

Critical battery:

```text
CRITICAL BAT
Shutting down
```

---

# 36. Suggested Implementation Order

Build the entire project, but follow this order internally:

1. Create monorepo structure.
2. Implement shared protocol docs/schemas.
3. Implement Pi config/logging/app state.
4. Implement Pi display preview renderer.
5. Implement ePaper hardware abstraction.
6. Implement PiSugar battery abstraction.
7. Implement OpenSky client/parser/filter/sorter.
8. Implement location manager.
9. Implement pairing QR page.
10. Implement secure pairing and envelope crypto.
11. Implement Pi API routes.
12. Implement systemd/install scripts.
13. Implement Expo app skeleton.
14. Implement Expo pairing QR scanner.
15. Implement mobile secure storage and secure API client.
16. Implement mobile background location task.
17. Implement mobile settings/status screens.
18. Connect mobile app to Pi API.
19. Add tests and mock modes.
20. Write complete documentation.
21. Ensure project can run end-to-end.

Do not stop at a partial skeleton. Generate as much complete, working code as possible.

---

# 37. Acceptance Criteria

The project is complete when:

1. The repo contains both Pi and Expo app code.
2. Pi app can install and run as a systemd service.
3. ePaper can render boot, pairing, radar, list, status, and error pages.
4. Pairing QR is generated and displayed on ePaper.
5. Expo app can scan QR.
6. Expo app can pair securely.
7. Secure API calls work after pairing.
8. Expo app can send current GPS.
9. Expo app can send background GPS updates.
10. Pi stores and validates phone location.
11. Pi calls OpenSky using bounding box around current location.
12. Pi displays nearby aircraft on ePaper.
13. Mobile app can change radius/update/settings.
14. Mobile app can select display page.
15. Mobile app can show Pi status and aircraft list.
16. API errors do not crash the Pi app.
17. Network loss does not crash the Pi app.
18. Missing location does not crash the Pi app.
19. PiSugar missing/unavailable does not crash the Pi app.
20. Battery saver behavior works.
21. Logs are useful but do not leak secrets.
22. README is detailed enough to install from scratch.
23. Security documentation explains limitations honestly.

---

# 38. Explicit Non-Goals

Do not implement:

* ADS-B dongle support.
* Local dump1090/readsb support.
* Public cloud backend.
* User accounts.
* App Store distribution.
* Complex map tiles.
* Aircraft photos.
* Airline logo database.
* Desktop GUI on the Pi.
* Deep ePaper button menus.
* Unsafe unauthenticated local control.

---

# 39. Final Reminder

Prioritize reliability, secure local control, and practical usability.

The iPhone app owns configuration and GPS.

The Pi owns aircraft data, display rendering, battery state, and local API.

The ePaper screen should be glanceable, not interactive-heavy.

All sensitive communication after pairing must be authenticated and encrypted at the application layer.

The device is informational only and must include a clear disclaimer:

```text
FlightPaper is for informational use only.
Not for navigation, flight safety, emergency use, aircraft separation, or operational aviation decisions.
Aircraft data may be delayed, incomplete, inaccurate, or unavailable.
```

Now create the full project.
