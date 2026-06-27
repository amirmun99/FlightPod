# Pairing QR Scannability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the FlightPaper pairing QR reliably scannable from an iPhone by enlarging/cleaning up the ePaper render and enabling the scanner's autofocus.

**Architecture:** Two independent, render/UX-only changes. On the Pi: drop the page title, grow the QR to 112px with a spec-compliant 4-module quiet zone, keep `IP:`/`Code:` text to the right. On the iPhone: set `CameraView`'s `autofocus="on"` (it currently defaults to fixed focus) and guide the user on distance. No crypto, protocol, payload, or SDK changes.

**Tech Stack:** Python (Pillow, `qrcode`, pytest) for the Pi service; React Native / Expo SDK 51 (`expo-camera` 15) for the mobile app.

**Spec:** `docs/superpowers/specs/2026-06-27-pairing-qr-scannability-design.md`

---

## Prerequisites

The Pi-side tests need the `flightpaper` package importable. Run them either on the Pi (`/opt/flightpaper/.venv/bin/python -m pytest …`) or in a local venv:

```bash
cd apps/pi
python3 -m venv .venv-dev && . .venv-dev/bin/activate
pip install -e ".[dev]"
```

Mobile checks run from `apps/mobile` with `npm` (deps already installed).

## File Structure

- `apps/pi/flightpaper/display/qr.py` — QR image builder. Change: default quiet-zone border 1→4 modules; `TARGET_MAX_PX` 96→120.
- `apps/pi/tests/test_qr.py` — extend with assertions for the new border default, max size, and a 112px render.
- `apps/pi/flightpaper/display/layouts.py` — `render_pairing()` only: remove title, enlarge/reposition QR, reflow text, bounds-guard.
- `apps/mobile/src/components/PairingQrScanner.tsx` — `CameraView` autofocus + helper text.

---

## Task 1: Enlarge QR capacity + quiet zone (`qr.py`)

**Files:**
- Modify: `apps/pi/flightpaper/display/qr.py`
- Test: `apps/pi/tests/test_qr.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/pi/tests/test_qr.py`:

```python
import inspect

from flightpaper.display.qr import render_qr_image, render_pairing_qr, TARGET_MAX_PX


def test_target_max_is_120() -> None:
    assert TARGET_MAX_PX == 120


def test_default_quiet_zone_is_four_modules() -> None:
    # QR spec requires a 4-module quiet zone for reliable decoding.
    default = inspect.signature(render_qr_image).parameters["border_modules"].default
    assert default == 4


def test_renders_pairing_qr_at_112() -> None:
    img = render_pairing_qr("flightpaper://pair?p=" + "A" * 120, target_px=112)
    assert img.size == (112, 112)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/pi/tests/test_qr.py -v`
Expected: `test_target_max_is_120` and `test_default_quiet_zone_is_four_modules` FAIL (current values are 96 and 1).

- [ ] **Step 3: Apply the change**

In `apps/pi/flightpaper/display/qr.py`:

Change the module docstring's size line from:
```python
The Waveshare 2.13" is 250x122 pixels and the QR must share the screen
with text. We target ≤ 96x96 px, single-bit, no border padding beyond what
the QR spec strictly requires.
```
to:
```python
The Waveshare 2.13" is 250x122 pixels and the QR must share the screen
with text. We target ≤ 120x120 px, single-bit, with a 4-module quiet zone
(the QR-spec minimum) so close-up phone scans decode reliably.
```

Change the constant:
```python
TARGET_MAX_PX: int = 96
```
to:
```python
TARGET_MAX_PX: int = 120
```

Change the `render_qr_image` signature default:
```python
def render_qr_image(
    text: str,
    *,
    target_px: int = TARGET_MAX_PX,
    border_modules: int = 1,
) -> "PILImage":
```
to:
```python
def render_qr_image(
    text: str,
    *,
    target_px: int = TARGET_MAX_PX,
    border_modules: int = 4,
) -> "PILImage":
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest apps/pi/tests/test_qr.py -v`
Expected: PASS (all tests, including the pre-existing ones — `test_default_target` reads `TARGET_MAX_PX` so it adapts to 120).

- [ ] **Step 5: Commit**

```bash
git add apps/pi/flightpaper/display/qr.py apps/pi/tests/test_qr.py
git commit -m "QR: 4-module quiet zone + 120px max for scannability"
```

---

## Task 2: Pairing layout — drop title, grow QR (`layouts.py`)

**Files:**
- Modify: `apps/pi/flightpaper/display/layouts.py` (`render_pairing` function)
- Test: `apps/pi/tests/test_renderer.py` (existing coverage), plus manual preview

- [ ] **Step 1: Confirm the baseline is green**

Run: `python -m pytest apps/pi/tests/test_renderer.py -v`
Expected: PASS (these assert every page, including `pairing`, renders at 250×122).

- [ ] **Step 2: Replace the `render_pairing` body**

In `apps/pi/flightpaper/display/layouts.py`, replace the entire `render_pairing` function with:

```python
def render_pairing(draw: "ImageDraw", image: "PILImage", state: "AppState") -> None:
    from .qr import QrRenderError, render_pairing_qr  # local import to avoid cycle

    label = label_font()
    status = status_font()

    # No page title — the 250x122 panel can't spare the rows. The QR fills
    # the left of the panel; pairing details sit in a column to its right.
    qr_left = 4
    qr_top = 5
    # Clamp so the QR can never run off the bottom of the panel.
    qr_size = min(112, image.height - 2 * qr_top)

    try:
        uri = state.pairing.qr_uri()
        qr_img = render_pairing_qr(uri, target_px=qr_size)
        image.paste(qr_img, (qr_left, qr_top))
        payload = state.pairing.qr_payload()
        host_text = f"IP: {payload['host']}"
        code_text = f"Code: {payload['code']}"
        ttl = max(0, payload["expires_at"] - now_ts())
        ttl_text = f"Expires: {ttl}s"
    except (QrRenderError, Exception) as exc:  # noqa: BLE001
        log.warning("pairing render fallback (%s)", exc)
        host_text = f"IP: {state.primary_ip}"
        code_text = "Code: --"
        ttl_text = "Open app"
        # Placeholder square where the QR would go.
        draw.rectangle(
            (qr_left, qr_top, qr_left + qr_size, qr_top + qr_size),
            outline=symbols.BLACK,
        )

    right_x = qr_left + qr_size + 10
    draw.text((right_x, 8), "Scan in app", font=label, fill=symbols.BLACK)
    draw.text((right_x, 34), host_text, font=status, fill=symbols.BLACK)
    draw.text((right_x, 60), code_text, font=status, fill=symbols.BLACK)
    draw.text((right_x, 86), ttl_text, font=status, fill=symbols.BLACK)
```

Note: this removes the local `title = title_font()` line (the title text is gone). `title_font` is still imported/used by `render_error`, so leave the import alone.

- [ ] **Step 3: Run tests + lint**

Run: `python -m pytest apps/pi/tests/test_renderer.py -v`
Expected: PASS (pairing page still renders at 250×122, no exception).

Run: `ruff check apps/pi/flightpaper/display/layouts.py`
Expected: clean (catches any now-unused variable like a stray `title`).

- [ ] **Step 4: Visual check (manual)**

Run: `python apps/pi/scripts/render_preview.py --page pairing --output /tmp/pairing.png`
Open `/tmp/pairing.png` and confirm: the QR is large (~112px) and fully on-screen with white margin around it; no title; `Scan in app`, `IP: …`, `Code: …`, `Expires: …s` are legible and non-overlapping to the right.

- [ ] **Step 5: Commit**

```bash
git add apps/pi/flightpaper/display/layouts.py
git commit -m "Pairing page: drop title, enlarge QR to 112px, reflow text"
```

---

## Task 3: Scanner autofocus + distance guidance (`PairingQrScanner.tsx`)

**Files:**
- Modify: `apps/mobile/src/components/PairingQrScanner.tsx`

No automated test (camera UI). Verification is typecheck + manual on-device scan.

- [ ] **Step 1: Add `autofocus` to the camera**

In `apps/mobile/src/components/PairingQrScanner.tsx`, change the `<CameraView …>` element from:

```tsx
      <CameraView
        style={StyleSheet.absoluteFillObject}
        facing="back"
        barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
        onBarcodeScanned={handleScan}
      />
```
to:
```tsx
      <CameraView
        style={StyleSheet.absoluteFillObject}
        facing="back"
        autofocus="on"
        barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
        onBarcodeScanned={handleScan}
      />
```

(`autofocus` defaults to `off`/fixed focus on iOS; `"on"` makes the camera focus on the close QR. Pinch-to-zoom is enabled by default, so no extra prop is needed.)

- [ ] **Step 2: Update the helper text for distance**

In the same file, change the default helper string from:

```tsx
          {lastError ?? 'Point the camera at the QR shown on your FlightPaper device.'}
```
to:
```tsx
          {lastError ??
            'Hold the phone ~15 cm from your FlightPaper screen and let it focus. Pinch to zoom in.'}
```

- [ ] **Step 3: Typecheck**

Run: `cd apps/mobile && npm run typecheck`
Expected: exits 0, no errors (`autofocus="on"` is valid — `FocusMode` is `'on' | 'off'`).

- [ ] **Step 4: Manual on-device check**

Rebuild/reload the dev client, open the scanner, and scan the real V4 panel. Confirm the camera focuses and the QR decodes at a comfortable distance.

- [ ] **Step 5: Commit**

```bash
git add apps/mobile/src/components/PairingQrScanner.tsx
git commit -m "Scanner: enable autofocus + distance guidance for close QR"
```

---

## Self-Review

**Spec coverage:**
- Pi: drop title (Task 2 ✓), 112px QR (Task 2 ✓), 4-module quiet zone (Task 1 ✓), keep IP + Code (Task 2 ✓), no-clip bounds guard (Task 2 ✓), payload/EC unchanged (no task touches them ✓).
- Mobile: autofocus on (Task 3 ✓), distance guidance (Task 3 ✓), pinch-to-zoom default (Task 3 note ✓), no lens selection / SDK bump (none performed ✓).
- Testing: qr size/border tests (Task 1 ✓), pairing render + preview (Task 2 ✓), typecheck + manual scan (Task 3 ✓).
- Out of scope honored: no manual entry, no crypto/payload change, no SDK upgrade.

**Placeholder scan:** No TBD/TODO; every code step shows complete code.

**Type/name consistency:** `render_qr_image`, `render_pairing_qr`, `TARGET_MAX_PX`, `border_modules`, `qr_size`, `qr_left`, `qr_top`, `right_x`, `autofocus` used consistently across tasks and match the existing source.
