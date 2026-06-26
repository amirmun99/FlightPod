# iPhone background location

FlightPaper relies on the iPhone for GPS. Foreground delivery is easy;
background delivery is the part you have to handle carefully because
iOS aggressively suspends background tasks and the permission UX is
multi-step.

## Permission flow

iOS requires location permissions to escalate in this order:

1. **When-In-Use** (foreground only). The first prompt the user sees,
   triggered by the **Allow While Using App** button on the Location
   screen. Backed by `NSLocationWhenInUseUsageDescription`.
2. **Always** (background allowed). iOS only shows this dialog *after*
   step 1 was granted. Triggered by the **Allow Always (background)**
   button on the same screen. Backed by
   `NSLocationAlwaysAndWhenInUseUsageDescription`.

The flow is implemented in
[`apps/mobile/src/services/location/foregroundLocation.ts`](../apps/mobile/src/services/location/foregroundLocation.ts).
`requestForegroundPermission()` and `requestBackgroundPermission()` are
kept distinct so the user sees two separate prompts and understands
the upgrade is opt-in.

`readPermissions()` is special: it returns
`background: 'undetermined'` if foreground has not been granted,
because iOS will report `denied` for background even when the user
has never been asked. The Location screen uses this so a fresh
install renders a "ready to ask" state, not "denied".

## Why Always is required for background delivery

`expo-location`'s `startLocationUpdatesAsync` requires the **Always**
authorization to deliver fixes to your `TaskManager` task when the app
is suspended. Without it, the task is registered but never fires while
the app is in the background. The Live GPS toggle on the Location
screen is therefore disabled when `background !== 'granted'`.

`UIBackgroundModes = ["location"]` is declared in `app.config.ts` —
iOS won't grant the entitlement without it.

## Foreground vs background defaults

The defaults sit inside the spec's tunable window:

| Mode | Distance interval | Time interval | Accuracy |
|---|---|---|---|
| Foreground one-shot (Send Now) | n/a | n/a | `Accuracy.High` |
| Background task | 50 m | 45 s | `Accuracy.Balanced` |

Both numbers are in the spec-defined window
(foreground 10–20s, background 30–60s, distance 25–100m).
`Accuracy.Balanced` is the right tradeoff for background work — `High`
keeps GPS hardware spun up longer and tanks battery.

The task itself lives in
[`apps/mobile/src/services/location/backgroundLocationTask.ts`](../apps/mobile/src/services/location/backgroundLocationTask.ts).
It is registered at module-import time (from `App.tsx`) so iOS can
resume the JS runtime from a cold launch and find the handler.

## Retry queue

A background fix can fail to upload (Pi unreachable, hotspot dropped,
500 from a transient bug). The sender in
[`apps/mobile/src/services/location/locationSender.ts`](../apps/mobile/src/services/location/locationSender.ts)
enqueues the failed payload onto a zustand-backed retry queue:

- **Cap:** 20 items. Drop oldest when full.
- **Flush:** `flushLocationQueue()` is called automatically from the
  background task body after each successful send, and is exposed as
  a **Flush queue** button on the Location screen for forcing it
  from the foreground.
- **Volatility:** the queue lives in memory only — failed-while-killed
  batches are lost on purpose. The right semantic for "current location"
  is the freshest fix, not every fix.

## Force-quit caveat

iOS treats a user-initiated force-quit (swipe up from the app
switcher) as a strong signal that the user does not want the app
running. Background location delivery to a force-quit app is
**suspended permanently** until the user re-opens it. There is no
work-around; this is by design.

If you find Live GPS stopped delivering after a few hours, check
whether you force-quit the app — re-open it once to resume.

## Newest-wins batch handling

When iOS resumes the app after a long suspension, the
`LocationCallback` can hand the task a coalesced array of fixes
spanning minutes. The handler picks the freshest fix by `timestamp`
and discards the rest. Sending every entry would burn `seq` numbers
and Pi cycles for stale data, and the Pi's location manager only
keeps the latest anyway.

## CoreLocation sanitization

CoreLocation reports `-1` (or other invalid values) for heading,
speed, and accuracy when those readings aren't currently valid. The
Pi rejects negatives and `heading_deg >= 360`. The sender clamps
those to `null` before posting so a real-world fix never trips
`invalid_request`. See `cleanHeading` / `cleanNonNegative` in
`locationSender.ts`.

## Free Apple ID caveat

This is the biggest functional gap for a hobbyist who hasn't paid for
a developer account:

- A **free Apple ID** can sign a development build but with limited
  entitlements and a **7-day expiration** on the sideloaded app. You
  will need to re-install weekly.
- Background-mode delivery on a free-Apple-ID build is best-effort —
  iOS may suspend the task more aggressively, and the
  `expo-task-manager` callback is not guaranteed to fire in the
  background. Foreground location works fine.
- A **paid Apple Developer Program** account ($99/year) provides full
  entitlements, no 7-day expiration, and reliable background-task
  delivery. We recommend the paid account if you want real Live GPS
  during walks.

`Mock device mode` (Security → Mock device toggle) lets you exercise
all the rest of the app — Settings PATCHes, status pages, aircraft
list — without a real Pi, so a free-Apple-ID build is still useful
for everyday UI work.

## What to do when "permission insufficient" shows up

The Location screen surfaces these states explicitly. If the user has
denied a permission, neither the **Allow While Using App** nor the
**Allow Always** button can re-prompt — iOS only shows the dialog
once per state. The screen falls through to an **Open iOS Settings**
button (`Linking.openURL('app-settings:')`) so the user can fix it.

After flipping the permission in Settings, return to the Location
screen — `readPermissions()` runs on focus and re-syncs the store.

## Debugging

- Foreground send: tap **Send Now** on the Location screen.
- Background send: enable Live GPS, lock the phone, walk 100 m. Watch
  the Pi: `journalctl -u flightpaper -f` should show
  `POST /api/secure/location` requests at the 45-second cadence.
- Sequence: every send goes through `claimNextSeqOut` in
  [`apps/mobile/src/services/storage/secureStore.ts`](../apps/mobile/src/services/storage/secureStore.ts).
  If the Pi rejects with `replay`, you've likely got two app
  instances running (simulator + device); only one can be paired at a
  time.
