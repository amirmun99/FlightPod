/**
 * Pairing QR scanner.
 *
 * Wraps ``expo-camera``'s ``CameraView`` with a barcode filter limited to
 * QR. Decoded payloads are parsed by :func:`parsePairingUri` and validated
 * by :func:`isPairingQrPayload` before being handed to the caller.
 *
 * The scanner debounces successive scans of the same payload — without
 * this iOS will fire ``onBarcodeScanned`` continuously while a QR is in
 * view.
 */

import { CameraView, useCameraPermissions } from 'expo-camera';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Button, StyleSheet, Text, View } from 'react-native';

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
  const [permission, requestPermission] = useCameraPermissions();
  const [lastError, setLastError] = useState<string | null>(null);
  const seenUriRef = useRef<string | null>(null);

  useEffect(() => {
    if (permission && !permission.granted && permission.canAskAgain) {
      void requestPermission();
    }
  }, [permission, requestPermission]);

  const handleScan = useCallback(
    ({ data }: { data: string }) => {
      if (data === seenUriRef.current) return;
      seenUriRef.current = data;
      const parsed = parsePairingUri(data);
      if (parsed === null) {
        setLastError('Not a FlightPaper pairing QR.');
        // Allow re-scanning the same URI after a delay so the user can
        // hold the device steady while fixing aim.
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

  if (!permission) {
    return (
      <View style={[styles.centered, { backgroundColor: theme.colors.background }]}>
        <ActivityIndicator />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={[styles.centered, { backgroundColor: theme.colors.background, padding: 24 }]}>
        <Text style={[theme.typography.body, { color: theme.colors.textPrimary, textAlign: 'center' }]}>
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

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.background }}>
      <CameraView
        style={StyleSheet.absoluteFillObject}
        facing="back"
        autofocus="on"
        barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
        onBarcodeScanned={handleScan}
      />
      <View style={styles.overlay} pointerEvents="none">
        <View style={[styles.frame, { borderColor: theme.colors.accent }]} />
      </View>
      <View style={styles.bottomBar}>
        <Text style={[theme.typography.callout, styles.helper]}>
          {lastError ??
            'Hold the phone ~15 cm from your FlightPaper screen and let it focus. Pinch to zoom in.'}
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
