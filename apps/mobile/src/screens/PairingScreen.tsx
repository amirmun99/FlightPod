/**
 * Pair flow: scan QR → handshake → save session → device store transitions
 * to "paired".
 *
 * Manual fallback (typing IP + 6-digit code) is intentionally not wired
 * yet — the spec calls it a fallback after a failed QR, and the QR code
 * is the only path the Pi actively encourages. We'll add the fallback
 * form in Phase 10 alongside the rest of the settings.
 */

import { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Button,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useDeviceStore } from '../app/state';
import { useTheme } from '../app/theme';
import PairingQrScanner from '../components/PairingQrScanner';
import { ApiError } from '../services/api/client';
import { completePairing } from '../services/api/pairingClient';
import type { PairingQrPayload } from '../types';

type Phase = 'idle' | 'scanning' | 'handshake' | 'done' | 'error';

export default function PairingScreen() {
  const theme = useTheme();
  const setDevice = useDeviceStore((s) => s.setDevice);
  const setMockDevice = useDeviceStore((s) => s.setMockDevice);
  const [phase, setPhase] = useState<Phase>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleScan = async (qr: PairingQrPayload) => {
    setPhase('handshake');
    setErrorMessage(null);
    try {
      const { device } = await completePairing(qr, {
        appInstanceName: 'FlightPaper iPhone',
      });
      setDevice(device);
      setPhase('done');
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `${err.code}${err.message ? `: ${err.message}` : ''}`
          : err instanceof Error
            ? err.message
            : 'unknown error';
      setErrorMessage(message);
      setPhase('error');
    }
  };

  const dismissScanner = () => setPhase('idle');

  return (
    <SafeAreaView
      edges={['bottom']}
      style={[styles.container, { backgroundColor: theme.colors.background }]}
    >
      <ScrollView contentContainerStyle={[styles.body, { padding: theme.spacing.lg }]}>
        <Text style={[theme.typography.title, { color: theme.colors.textPrimary }]}>
          Pair your FlightPaper
        </Text>
        <Text
          style={[
            theme.typography.body,
            { color: theme.colors.textSecondary, marginTop: theme.spacing.sm },
          ]}
        >
          Tap below, then scan the QR code shown on your FlightPaper ePaper screen.
        </Text>

        {phase === 'error' ? (
          <Text
            style={[
              theme.typography.callout,
              {
                color: theme.colors.bad,
                marginTop: theme.spacing.md,
              },
            ]}
          >
            Pairing failed: {errorMessage}
          </Text>
        ) : null}

        <View style={{ marginTop: theme.spacing.xl }}>
          <Button title="Scan pairing QR" onPress={() => setPhase('scanning')} />
        </View>

        <View style={{ marginTop: theme.spacing.xl, gap: theme.spacing.sm }}>
          <Text style={[theme.typography.bodyEmphasis, { color: theme.colors.textPrimary }]}>
            No FlightPaper handy?
          </Text>
          <Text style={[theme.typography.callout, { color: theme.colors.textMuted }]}>
            Enable mock device mode to browse the app without a real Pi. The
            Security screen will also expose this toggle once we wire it
            (Phase 10).
          </Text>
          <Button
            title="Enter mock device mode"
            onPress={() => {
              Alert.alert(
                'Mock device mode',
                'Enable mock data so you can browse screens without a real Pi?',
                [
                  { text: 'Cancel', style: 'cancel' },
                  {
                    text: 'Enable',
                    onPress: () => setMockDevice(true),
                  },
                ],
              );
            }}
          />
        </View>
      </ScrollView>

      <Modal visible={phase === 'scanning'} animationType="slide" onRequestClose={dismissScanner}>
        <PairingQrScanner onScan={handleScan} onClose={dismissScanner} />
      </Modal>

      <Modal visible={phase === 'handshake'} animationType="fade" transparent>
        <View style={styles.modalOverlay}>
          <View
            style={[
              styles.modalCard,
              {
                backgroundColor: theme.colors.surface,
                borderRadius: theme.radius.lg,
              },
            ]}
          >
            <ActivityIndicator />
            <Text
              style={[
                theme.typography.body,
                {
                  color: theme.colors.textPrimary,
                  marginTop: theme.spacing.md,
                  textAlign: 'center',
                },
              ]}
            >
              Pairing with your FlightPaper…
            </Text>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  body: { flexGrow: 1 },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalCard: {
    paddingVertical: 32,
    paddingHorizontal: 28,
    minWidth: 260,
    alignItems: 'center',
  },
});
