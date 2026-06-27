# Vision-Camera Pairing Scanner — Design Spec

- **Date:** 2026-06-27
- **Status:** Awaiting user approval
- **Scope:** Replace the pairing QR scanner's camera library so it can use the iPhone's ultra-wide (0.5×) lens with continuous autofocus and zoom. Mobile-only.

## Problem

The pairing scanner uses `expo-camera` 15 (Expo SDK 51). That version has **no lens-selection API** (so no 0.5× ultra-wide) and **no continuous autofocus** (`FocusMode` is only `'on' | 'off'`; `'on'` focuses once at mount then locks). Result on device: the camera focuses on the far scene at open and stays locked, so a close QR is blurry, and pinch-to-zoom is unreliable. The enlarged Pi QR (already shipped) helps but isn't enough without focus.

## Decision (from this session)

Swap the scanner to **`react-native-vision-camera`**, which exposes physical lens selection, continuous autofocus, and zoom. Pin **`~4.7.3`** — the newest 4.x line, compatible with React Native 0.74 / Expo SDK 51. (v5 requires RN's new architecture and is incompatible.)

## Non-goals

- No Expo SDK / React Native upgrade.
- No frame processors / Skia / ML — we only need the built-in QR code scanner.
- No change to pairing crypto, the QR payload, or `PairingScreen` wiring.

## Design

### Dependencies

- **Add** `react-native-vision-camera@~4.7.3`.
- **Remove** `expo-camera` (used only by the scanner) and its `app.config.ts` plugin.
- **Do NOT add** `@shopify/react-native-skia` or `react-native-worklets-core`. They are optional peers only for *frame processors*, which we disable (see plugin config). `react-native-reanimated` is already installed and is sufficient.

### `app.config.ts`

- Remove the `'expo-camera'` plugin entry.
- Add the vision-camera plugin:
  ```ts
  [
    'react-native-vision-camera',
    {
      cameraPermissionText:
        'FlightPaper uses the camera to scan the pairing QR code shown on your FlightPaper device.',
      enableMicrophonePermission: false,
      enableCodeScanner: true,      // include the native QR scanner on iOS
      enableFrameProcessors: false, // avoids the react-native-worklets-core requirement
    },
  ],
  ```
- Keep `NSCameraUsageDescription` in `infoPlist` (already present, independent of the plugin).

### `apps/mobile/src/components/PairingQrScanner.tsx` (rewrite)

Keep the **public surface identical** so `PairingScreen` is untouched: the named export `parsePairingUri(uri)` and the default component with props `{ onScan, onClose }`. Reuse the existing `parsePairingUri` body and the `isPairingQrPayload` validation verbatim.

Replace the camera internals with vision-camera:
- **Permission:** `useCameraPermission()` → if not granted, `requestPermission()`; keep the existing "grant access" fallback UI.
- **Device (lens):** prefer the ultra-wide:
  ```ts
  const device =
    useCameraDevice('back', { physicalDevices: ['ultra-wide-angle-camera'] }) ??
    useCameraDevice('back');
  ```
  Falls back to the default back camera on phones without an ultra-wide (e.g. SE). If `device` is `undefined`, render a "no camera available" message.
- **Scanner:** `useCodeScanner({ codeTypes: ['qr'], onCodeScanned })`. Port the existing same-URI debounce (`seenUriRef`) + `parsePairingUri` + `setLastError` logic into `onCodeScanned` (codes arrive as `codes[].value`).
- **Camera element:** `<Camera style={StyleSheet.absoluteFillObject} device={device} isActive={true} codeScanner={codeScanner} zoom={zoom} />`. Continuous autofocus is vision-camera's default — no prop needed.
- **Zoom controls:** simple on-screen buttons (no Reanimated pinch worklet). Local `zoom` state initialized to `device.neutralZoom`; a `−` / `+` pair steps zoom within `[device.minZoom, device.maxZoom]`. Bind to the `zoom` prop.
- **Overlay + helper text:** keep the framing overlay and bottom bar. Update the helper copy to reflect that focus now works, e.g. *"Point the camera at the QR. Move closer until it focuses; use −/+ to zoom."*

### Native rebuild

This adds a native module, so after install + config the dev client must be rebuilt:
```bash
cd apps/mobile && npx expo run:ios --device
```
(`expo run:ios` runs prebuild + pod install automatically.)

## Testing

- **Static:** `npm run typecheck` clean.
- **On-device (human):** scan the real V4 panel. Confirm: wider field of view (ultra-wide), the preview **focuses continuously** as you move, the −/+ zoom buttons change zoom, and the QR decodes and pairs. Confirm the permission-denied path still works (deny once, then grant).

## Risks / notes

- **First native build** may need a clean `ios/` / pod reinstall (same class of issue as earlier native-dep changes). Mitigation: `enableFrameProcessors: false` keeps the build off the worklets-core path; if the build still complains, delete `apps/mobile/ios/Pods` and re-run.
- **Devices without an ultra-wide** fall back to the standard back lens (still gains continuous autofocus). The target iPhone 17 Pro has an ultra-wide.
- vision-camera 4.7.x targets old-architecture RN 0.74; do not bump to v5.

## Files touched

- `apps/mobile/package.json` (add vision-camera, remove expo-camera)
- `apps/mobile/app.config.ts` (swap plugin)
- `apps/mobile/src/components/PairingQrScanner.tsx` (rewrite internals; keep public API)
