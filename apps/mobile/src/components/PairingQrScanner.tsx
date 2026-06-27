/**
 * Pairing QR scanner.
 *
 * Uses react-native-vision-camera so we can select the ultra-wide (0.5x)
 * lens and get continuous autofocus for reliable close-up QR code scanning. Decoded payloads are
 * parsed by parsePairingUri and validated by isPairingQrPayload before
 * being handed to the caller. Successive scans of the same payload are
 * debounced.
 */

import { useCallback, useRef, useState } from 'react';
import { Button, StyleSheet, Text, View } from 'react-native';
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
