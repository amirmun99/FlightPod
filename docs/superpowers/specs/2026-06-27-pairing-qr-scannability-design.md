# Pairing QR Scannability — Design Spec

- **Date:** 2026-06-27
- **Status:** Awaiting user approval
- **Scope:** Make the FlightPaper pairing QR reliably scannable from an iPhone. Two-sided, render + scan-UX only. No crypto/protocol changes.

## Problem

The pairing QR rendered on the Pi's 2.13" ePaper (250×122) is too small/dense to scan with the iPhone. Two independent causes:

1. **Pi side:** the QR is rendered at 80px in a layout that also carries a title and a 4-line text column, and uses only a 1-module quiet zone (below the QR-spec minimum of 4). Small modules + tight quiet zone = hard to decode.
2. **Mobile side:** `expo-camera`'s `CameraView` has `autofocus` defaulting to **`off`** (fixed focus) on iOS, so the scanner never focuses on a close target — the QR is blurry at the short distance a small code requires.

## Decisions (from brainstorming)

- **Scanning only** — no manual code-entry fallback. The 6-digit `code` is a one-way HMAC of the pairing secret and cannot complete a handshake under the symmetric-secret design; a secure manual flow would require a PAKE redesign, which is explicitly out of scope.
- **No SDK/library upgrade.** Stay on Expo SDK 51 / expo-camera 15. Physical lens selection (the 0.5× ultra-wide) is unavailable until expo-camera 16, so it is not used.
- **Layout direction (user):** remove the "PAIR FLIGHTPAPER" title to free vertical space; keep the `IP:` and `Code:` lines; do not let the QR clip.

## Non-goals

- Manual pairing / typed code / PAKE.
- Reducing the QR payload or any protocol/crypto change.
- Upgrading expo-camera or Expo SDK.

## Design

### Pi side — render only

**`apps/pi/flightpaper/display/qr.py`**
- Raise the default quiet zone: `border_modules` default `1` → `4` (QR-spec minimum). The border scales with the image, so the quiet zone is baked into the rendered PNG.
- Raise `TARGET_MAX_PX` `96` → `120` and update the module docstring (drop the "≤ 96" / title assumptions).
- Keep `error_correction = L` and the payload unchanged.
- Existing behavior preserved: if the raw module size exceeds the target, `render_qr_image` still raises `QrRenderError` and the layout falls back to the placeholder + text path.

**`apps/pi/flightpaper/display/layouts.py` → `render_pairing`**
- **Remove** the `draw.text((4, 0), "PAIR FLIGHTPAPER", ...)` title line.
- Enlarge and reposition the QR:
  - `qr_size = 112`, `qr_top = 5`, `qr_left = 4` → occupies y∈[5,117], x∈[4,116]. Within the 122×250 panel, so **not clipped**.
  - Add a bounds guard: clamp `qr_size` to `image.height - 2*qr_top` so a future config/panel change can't push it off-screen.
- Right-hand text column at `right_x = qr_left + qr_size + 10` (= 126), leaving ~120px of width:
  - `"Scan in app"` at y≈8 (label font)
  - `"IP: {host}"` at y≈34 (status font) — **required**
  - `"Code: {code}"` at y≈60 (status font) — kept per user
  - `"Expires: {ttl}s"` at y≈86 (status font)
- Update the `except` fallback branch to the same new coordinates (placeholder square at the new QR rect; text column unchanged).

Exact y-offsets to be finalized against actual font heights during implementation, verified visually (see Testing). The invariant that must hold: QR fully on-screen with a clear white margin, and all four text lines non-overlapping within the panel.

### Mobile side — `apps/mobile/src/components/PairingQrScanner.tsx`

- **Add `autofocus="on"` to `CameraView`** — the primary mobile fix (default is `off`/fixed focus). This makes the camera focus on the close QR.
- Enable digital zoom assistance (SDK 51-compatible substitute for the 0.5× lens):
  - Ensure pinch-to-zoom is available (it is on by default via the scanner settings) and optionally seed a small default `zoom` (e.g. `0.0`, user-adjustable) so users can fill the frame from a focusable distance.
- Update the helper text to guide distance: e.g. *"Hold the phone ~15 cm from the screen and let it focus. Pinch to zoom in."*
- No change to the parsing/validation/debounce logic.

## Testing

- **Pi:** `python apps/pi/scripts/render_preview.py --page pairing --output /tmp/pairing.png` and eyeball: QR large, uncropped, clear quiet zone, IP + Code + Expires legible. Extend a unit test to assert `render_pairing_qr(uri, target_px=112)` returns a 112×112 image and that rendering the pairing page does not raise and keeps the QR within panel bounds.
- **Mobile:** manual on-device scan against the real V4 panel (no automated camera test). Confirm focus + decode at a comfortable distance.

## Risks / notes

- `autofocus="on"` autofocuses once then locks; acceptable for a held-steady scan. If it locks at the wrong distance in testing, revisit (e.g. remount the camera or drop back to default).
- Larger QR + 4-module border slightly increases the rendered image; the graceful `QrRenderError` fallback already covers the unlikely overflow case.
- This is the best achievable scannability on SDK 51; a future SDK 52 upgrade could add true ultra-wide lens selection.

## Files touched

- `apps/pi/flightpaper/display/qr.py`
- `apps/pi/flightpaper/display/layouts.py`
- `apps/mobile/src/components/PairingQrScanner.tsx`
- Pi display/qr test (extend existing)
