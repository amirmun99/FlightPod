# Vision-Camera Pairing Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the pairing QR scanner's camera with `react-native-vision-camera` so it uses the ultra-wide (0.5×) lens with continuous autofocus and zoom buttons.

**Architecture:** Two sequential tasks. Task 1 adds vision-camera and rewrites `PairingQrScanner.tsx` (keeping its public API), leaving `expo-camera` installed-but-unused so typecheck stays green. Task 2 removes `expo-camera` and swaps the Expo config plugin. Verification is `npm run typecheck` (no automated camera test); the real validation is an on-device scan after a native rebuild, done by the human.

**Tech Stack:** React Native 0.74 / Expo SDK 51, `react-native-vision-camera@~4.7.3`, TypeScript.

**Spec:** `docs/superpowers/specs/2026-06-27-vision-camera-scanner-design.md`

**Working dir for all commands:** `/Users/amirmun/Documents/code/rpi-flightpod/apps/mobile`

---

## Task 1: Add vision-camera + rewrite the scanner

**Files:**
- Modify: `apps/mobile/package.json` (via npm)
- Rewrite: `apps/mobile/src/components/PairingQrScanner.tsx`

- [ ] **Step 1: Install vision-camera (pinned to the RN 0.74-compatible v4 line)**

Run (in `apps/mobile`):
```bash
npm install react-native-vision-camera@~4.7.3
```
Expected: installs without ERESOLVE. Do NOT install `@shopify/react-native-skia` or `react-native-worklets-core` (not needed — frame processors are disabled).

- [ ] **Step 2: Replace the entire contents of `apps/mobile/src/components/PairingQrScanner.tsx`** with:

```tsx
/**
 * Pairing QR scanner.
 *
 * Uses react-native-vision-camera so we can select the ultra-wide (0.5x)
 * lens and get continuous autofocus — expo-camera (SDK 51) could do
 * neither, leaving close-up QR codes out of focus. Decoded payloads are
 * parsed by parsePairingUri and validated by isPairingQrPayload before
 * being handed to the caller. Successive scans of the same payload are
 * debounced.
 */

import { useCallback, useRef, useState } from 'react';
import { ActivityIndicator, Button, StyleSheet, Text, View } from 'react-native';
import {
  Camera,
  useCameraDevice,
  useCameraPermission,
  useCodeScanner,
} from 'react-native-vision-camera';

import { useTheme } from '../app/theme';
import { b64uDecode, utf8Decode } from '../services/crypto/base64u';
import { isPairingQrPayload } from '../utils/validation';
import type { PairingQrPayload } from '../types';

interface Props {
  onScan: (payload: PairingQrPayload) => void;
  onClose?: () => void;
}

export const parsePairingUri = (uri: string): PairingQrPayload | null => {
  try {
    if (!uri.startsWith('flightpaper://pair?')) return null;
    const url = new URL(uri.replace('flightpaper://pair', 'http://pair/'));
    const p = url.searchParams.get('p');
    if (!p) return null;
    const decoded = JSON.parse(utf8Decode(b64uDecode(p)));
    if (!isPairingQrPayload(decoded)) return null;
    return decoded;
  } catch {
    return null;
  }
};

export default function PairingQrScanner({ onScan, onClose }: Props) {
  const theme = useTheme();
  const { hasPermission, requestPermission } = useCameraPermission();
  const [lastError, setLastError] = useState<string | null>(null);
  const seenUriRef = useRef<string | null>(null);

  // Prefer the ultra-wide (0.5x) lens — it focuses far closer than the main
  // lens, which is what a small QR needs. Fall back to the default back
  // camera on phones without an ultra-wide. Both hooks always run (the ??
  // only selects the result), so the rules of hooks are satisfied.
  const ultraWide = useCameraDevice('back', {
    physicalDevices: ['ultra-wide-angle-camera'],
  });
  const defaultBack = useCameraDevice('back');
  const device = ultraWide ?? defaultBack;

  const minZoom = device?.minZoom ?? 1;
  const maxZoom = device?.maxZoom ?? 1;
  const [zoom, setZoom] = useState(1);

  const handleData = useCallback(
    (data: string) => {
      if (data === seenUriRef.current) return;
      seenUriRef.current = data;
      const parsed = parsePairingUri(data);
      if (parsed === null) {
        setLastError('Not a FlightPaper pairing QR.');
        // Allow re-scanning the same URI after a delay so the user can hold
        // steady while fixing aim.
        setTimeout(() => {
          seenUriRef.current = null;
        }, 1500);
        return;
      }
      setLastError(null);
      onScan(parsed);
    },
    [onScan],
  );

  const codeScanner = useCodeScanner({
    codeTypes: ['qr'],
    onCodeScanned: (codes) => {
      const value = codes[0]?.value;
      if (value) handleData(value);
    },
  });

  if (!hasPermission) {
    return (
      <View style={[styles.centered, { backgroundColor: theme.colors.background, padding: 24 }]}>
        <Text
          style={[theme.typography.body, { color: theme.colors.textPrimary, textAlign: 'center' }]}
        >
          The QR scanner needs camera access to read your FlightPaper pairing code.
        </Text>
        <View style={{ height: 16 }} />
        <Button
          title="Grant camera access"
          onPress={() => {
            void requestPermission();
          }}
        />
        {onClose ? (
          <View style={{ marginTop: 12 }}>
            <Button title="Cancel" onPress={onClose} />
          </View>
        ) : null}
      </View>
    );
  }

  if (!device) {
    return (
      <View style={[styles.centered, { backgroundColor: theme.colors.background, padding: 24 }]}>
        <Text
          style={[theme.typography.body, { color: theme.colors.textPrimary, textAlign: 'center' }]}
        >
          No camera is available on this device.
        </Text>
        {onClose ? (
          <View style={{ marginTop: 12 }}>
            <Button title="Cancel" onPress={onClose} />
          </View>
        ) : null}
      </View>
    );
  }

  const stepZoom = (delta: number) => {
    setZoom((z) => Math.min(maxZoom, Math.max(minZoom, z + delta)));
  };

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.background }}>
      <Camera
        style={StyleSheet.absoluteFillObject}
        device={device}
        isActive={true}
        codeScanner={codeScanner}
        zoom={zoom}
      />
      <View style={styles.overlay} pointerEvents="none">
        <View style={[styles.frame, { borderColor: theme.colors.accent }]} />
      </View>
      <View style={styles.zoomBar}>
        <Button title="–" onPress={() => stepZoom(-1)} />
        <Text style={styles.zoomLabel}>{`${zoom.toFixed(1)}x`}</Text>
        <Button title="+" onPress={() => stepZoom(1)} />
      </View>
      <View style={styles.bottomBar}>
        <Text style={[theme.typography.callout, styles.helper]}>
          {lastError ?? 'Point the camera at the QR. Move closer until it focuses; use –/+ to zoom.'}
        </Text>
        {onClose ? <Button title="Cancel" onPress={onClose} /> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
  },
  frame: {
    width: 240,
    height: 240,
    borderWidth: 2,
    borderRadius: 14,
  },
  zoomBar: {
    position: 'absolute',
    top: 48,
    alignSelf: 'center',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    backgroundColor: 'rgba(0,0,0,0.55)',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 12,
  },
  zoomLabel: {
    color: '#FFFFFF',
    minWidth: 44,
    textAlign: 'center',
  },
  bottomBar: {
    position: 'absolute',
    bottom: 32,
    left: 24,
    right: 24,
    padding: 14,
    backgroundColor: 'rgba(0,0,0,0.55)',
    borderRadius: 12,
    gap: 8,
  },
  helper: {
    color: '#FFFFFF',
    textAlign: 'center',
  },
});
```

Note: `ActivityIndicator` is imported to match the prior file's import set, but if your linter flags it as unused, remove it from the import. Keep the exported `parsePairingUri` and the `{ onScan, onClose }` props exactly as above — `PairingScreen` depends on them.

- [ ] **Step 3: Typecheck**

Run: `npm run typecheck`
Expected: exits 0. vision-camera ships its own types, so `useCameraDevice`, `useCodeScanner`, `useCameraPermission`, and `<Camera>` resolve. If it errors that a name doesn't exist on vision-camera's exports, STOP and report BLOCKED with the exact error (do not guess alternative APIs).

- [ ] **Step 4: Commit**

```bash
git add apps/mobile/package.json apps/mobile/package-lock.json apps/mobile/src/components/PairingQrScanner.tsx
git commit -m "Scanner: rewrite on react-native-vision-camera (ultra-wide + autofocus + zoom)"
```

---

## Task 2: Remove expo-camera + swap the Expo config plugin

**Files:**
- Modify: `apps/mobile/package.json` (via npm)
- Modify: `apps/mobile/app.config.ts`

- [ ] **Step 1: Remove expo-camera (now unused)**

Run (in `apps/mobile`):
```bash
npm uninstall expo-camera
```

- [ ] **Step 2: Swap the config plugin in `apps/mobile/app.config.ts`**

Find this plugin entry (inside the `plugins: [ ... ]` array):
```ts
    [
      'expo-camera',
      {
        cameraPermission:
          'FlightPaper uses the camera to scan the pairing QR code shown on your FlightPaper device.',
      },
    ],
```
Replace it with:
```ts
    [
      'react-native-vision-camera',
      {
        cameraPermissionText:
          'FlightPaper uses the camera to scan the pairing QR code shown on your FlightPaper device.',
        enableMicrophonePermission: false,
        enableCodeScanner: true,
        enableFrameProcessors: false,
      },
    ],
```
Leave everything else in `app.config.ts` unchanged — in particular keep `NSCameraUsageDescription` in `infoPlist`.

- [ ] **Step 3: Typecheck**

Run: `npm run typecheck`
Expected: exits 0 (nothing imports `expo-camera` anymore — Task 1 removed the only import).

- [ ] **Step 4: Confirm no stray expo-camera references**

Run: `grep -rn "expo-camera" src app.config.ts`
Expected: no matches (an empty result). If anything prints, remove that reference and re-run typecheck.

- [ ] **Step 5: Commit**

```bash
git add apps/mobile/package.json apps/mobile/package-lock.json apps/mobile/app.config.ts
git commit -m "Remove expo-camera; add vision-camera config plugin"
```

---

## Self-Review

**Spec coverage:**
- vision-camera `~4.7.3` added (Task 1 ✓); expo-camera removed (Task 2 ✓).
- Ultra-wide device with fallback (Task 1 ✓); continuous autofocus (vision-camera default — no prop, ✓); zoom buttons (Task 1 ✓).
- Config plugin with `enableCodeScanner: true` + `enableFrameProcessors: false` (Task 2 ✓); `NSCameraUsageDescription` preserved (Task 2 note ✓).
- Public API unchanged: `parsePairingUri`, `{ onScan, onClose }` (Task 1 ✓).
- No skia/worklets-core installed (Task 1 Step 1 note ✓).
- Out of scope honored: no crypto/payload change, no SDK upgrade.

**Placeholder scan:** none — full file content and exact commands provided.

**Type/name consistency:** `useCameraDevice`, `useCameraPermission`, `useCodeScanner`, `Camera`, `device`, `zoom`, `parsePairingUri` used consistently and match vision-camera v4's API.
