# FlightPaper — iPhone companion app

Expo + React Native + TypeScript companion that pairs with a FlightPaper
Pi over the iPhone's hotspot, streams GPS, and surfaces aircraft /
status / settings.

> See the **[root README](../../README.md)** for the system-level
> overview. This file is the mobile-specific install + dev + operate
> guide.

## Quick start

```bash
cd apps/mobile
npm install
npm run typecheck
npm run start:go        # iOS Simulator via Expo Go (foreground only)
```

For background location + the QR scanner you need a real device + an
[Expo dev client](#building-a-dev-client). All other screens are
exercisable in mock device mode without a Pi.

## Required iOS permissions

All declared in [`app.config.ts`](app.config.ts):

| Plist key | Why |
|-----------|-----|
| `NSLocationWhenInUseUsageDescription` | Foreground GPS (initial permission prompt) |
| `NSLocationAlwaysAndWhenInUseUsageDescription` | Background GPS (Live GPS toggle) |
| `NSLocationAlwaysUsageDescription` | Legacy iOS 10 fallback |
| `NSCameraUsageDescription` | QR scanner during pairing |
| `NSLocalNetworkUsageDescription` | Talking to the Pi on the iPhone hotspot |
| `NSAppTransportSecurity.NSAllowsLocalNetworking` | Plain HTTP under app-layer encryption |
| `UIBackgroundModes = ["location"]` | Background task delivery |
| Plugin: `expo-location` `locationAlwaysAndWhenInUsePermission` | Expo's autoconfig path |

## QR pairing

The pair screen (`src/screens/PairingScreen.tsx`) opens a camera
preview, parses `flightpaper://pair?p=<base64url>` URIs via
`parsePairingUri` in `components/PairingQrScanner.tsx`, runs the
symmetric-pairing-key handshake, and persists the resulting
`PairedDevice` + session key to SecureStore.

Full sequence at [`docs/pairing.md`](../../docs/pairing.md). The
companion script [`scripts/e2e-pair.cjs`](scripts/e2e-pair.cjs) runs
the same handshake against a live `uvicorn` Pi from bare Node — useful
for protocol regression testing.

## Background GPS

The TaskManager task is defined in
[`src/services/location/backgroundLocationTask.ts`](src/services/location/backgroundLocationTask.ts)
and registered at module-import time from `App.tsx` so iOS can resume
the JS runtime from a cold launch. Cadence defaults: 50 m / 45 s,
`Accuracy.Balanced`. Failed sends queue (max 20, drop-oldest) and are
flushed opportunistically on the next foreground send.

Free-Apple-ID caveat: a sideloaded dev build expires after 7 days and
background-mode delivery is best-effort. A paid Apple Developer
account ($99/year) unlocks reliable background delivery. See
[`docs/iphone-background-location.md`](../../docs/iphone-background-location.md).

## Local network permission

`NSLocalNetworkUsageDescription` triggers an iOS dialog the first time
the app contacts an LAN host. Accept it; the app cannot reach the Pi
without it. If you ever revoke it, re-enable from iOS Settings →
FlightPaper → Local Network.

## Building a dev client

```bash
cd apps/mobile
npx eas init                 # one-time, links to your Expo account
npm run build:dev:ios        # eas build --profile development --platform ios
```

Why a dev client (not Expo Go):

- `expo-task-manager` background callbacks don't fire under Expo Go.
- `NSLocalNetworkUsageDescription` + `UIBackgroundModes` must be in
  the binary's Info.plist.
- The QR scanner uses `expo-camera`'s native module.

Install the resulting `.ipa` via TestFlight (paid account) or via
direct device install with Xcode (free Apple ID, 7-day expiry).

## Debugging connection issues

The Logs screen (`src/screens/LogsScreen.tsx`) shows the most recent
connection-level events from `app/state/logStore.ts`. No location, no
secrets, no aircraft data — just HTTP code + error message.

When troubleshooting:

1. **Hotspot up?** Confirm the iPhone hotspot is on and the Pi is
   associated (`hostname -I` on Pi).
2. **Right IP?** Open Settings → Wi-Fi → tap (i) next to your hotspot
   to see your IP. The Pi's IP comes from `status.network.ip_address`.
3. **Pairing intact?** Security screen shows the paired device. If
   it's null, something cleared SecureStore — re-pair.
4. **Replay errors?** Means two phone instances share a `client_id`
   (simulator + device against the same Pi). Reset pairing.

For non-network UI work, flip **Security → Mock device mode** to
render every screen against canned data.

## Mock device mode

Toggleable from the Security screen. Swaps the real
[`createDeviceClient`](src/services/api/deviceClient.ts) for
[`createMockDeviceClient`](src/services/mock/mockDeviceClient.ts) —
returns canned status, aircraft, and config; PATCHes actually mutate
the in-process state so the UI feels real. Useful for offline iteration
and demos.

## Test matrix

```bash
node node_modules/typescript/bin/tsc --noEmit    # mobile typecheck
node scripts/verify-crypto.cjs                   # 8 crypto interop vs. Pi
node scripts/verify-location.cjs                 # 17 queue / sanitizer checks
node scripts/verify-stores.cjs                   # 34 store + validator checks
node scripts/e2e-pair.cjs                        # live pair + secure GET (needs running Pi)
```

The CJS scripts are used because Node 25 + ts-jest + tsx hang on this
dev host. The protocol guarantees are exercised through the
verification scripts and the live `e2e-pair.cjs`. Jest tests run fine
on any normal Node 22/24 setup.

## Project layout

```
apps/mobile/
├── app.config.ts              ← iOS perms, plugins, bundle id
├── eas.json                   ← dev / preview / production profiles
├── package.json
├── tsconfig.json
├── babel.config.js
├── index.ts                   ← registerRootComponent(App)
└── src/
    ├── App.tsx                ← SafeAreaProvider + ThemeContext + StatusBar
    │                             + SecureStore rehydrate + bg-task register
    ├── app/
    │   ├── navigation/
    │   │   └── RootNavigator.tsx
    │   ├── state/             ← zustand: device / settings / location / log
    │   └── theme/             ← colors / spacing / typography
    ├── components/
    │   ├── PairingQrScanner.tsx
    │   ├── PlaceholderScreen.tsx
    │   └── ui.tsx             ← Card / CardTitle / KeyValue / StatusBadge
    ├── hooks/
    │   └── useDeviceClient.ts ← real vs mock client switch
    ├── screens/               ← Pairing + 9 paired screens
    ├── services/
    │   ├── api/               ← client / endpoints / secureEnvelope / device / pairing
    │   ├── crypto/            ← keys / envelope / replay / random / base64u
    │   ├── location/          ← foreground / background task / sender
    │   ├── mock/              ← fixtures + mockDeviceClient
    │   ├── network/           ← discovery / connectivity
    │   └── storage/           ← SecureStore wrappers + mutex-protected seq
    ├── types/                 ← device / aircraft / config / location / security
    └── utils/                 ← geo / time / validation
```

## Disclaimer

FlightPaper is informational only. **Not for navigation, flight safety,
emergency use, aircraft separation, or operational aviation decisions.**
Aircraft data may be delayed, incomplete, inaccurate, or unavailable.
