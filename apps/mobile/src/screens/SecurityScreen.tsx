/**
 * Paired-device info, mock-device toggle, and the destructive
 * "Reset pairing" action.
 *
 * Reset is a two-step confirm: first an :func:`Alert`, then a separate
 * confirmation of the action. It calls ``POST /api/secure/pairing/reset``
 * (which blows away the Pi-side ``paired_clients.json``) and then
 * clears the phone-side SecureStore. On both, the navigator falls
 * back to the QR-pair screen because :state:`deviceStore.device` ends
 * up ``null``.
 */

import { useState } from 'react';
import {
  Alert,
  Button,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useDeviceStore } from '../app/state';
import { logEvent } from '../app/state/logStore';
import { useTheme } from '../app/theme';
import { Card, CardTitle, KeyValue } from '../components/ui';
import { useDeviceClient } from '../hooks/useDeviceClient';
import { resetMockDevice } from '../services/mock/mockDeviceClient';
import { clearPairedDevice } from '../services/storage/secureStore';
import { useLocationStore } from '../app/state/locationStore';

export default function SecurityScreen() {
  const theme = useTheme();
  const handle = useDeviceClient();
  const device = useDeviceStore((s) => s.device);
  const mockDevice = useDeviceStore((s) => s.mockDevice);
  const setMockDevice = useDeviceStore((s) => s.setMockDevice);
  const clearDevice = useDeviceStore((s) => s.clear);
  const resetLocation = useLocationStore((s) => s.reset);

  const [busy, setBusy] = useState(false);

  const doReset = async () => {
    setBusy(true);
    try {
      // Best-effort: tell the Pi to drop our client record so the
      // session key is invalidated server-side. If we can't reach it
      // we still clear locally.
      try {
        await handle.client?.resetPairing();
      } catch (err) {
        logEvent(
          'warn',
          `pairing reset: server unreachable (${err instanceof Error ? err.message : 'unknown'})`,
          'pair',
        );
      }
      await clearPairedDevice();
      resetLocation();
      clearDevice();
    } finally {
      setBusy(false);
    }
  };

  const confirmReset = () => {
    Alert.alert(
      'Reset pairing?',
      'This drops the session keys on this phone and asks your FlightPaper to forget this device. You will need to scan the QR again.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset',
          style: 'destructive',
          onPress: doReset,
        },
      ],
    );
  };

  const toggleMock = (next: boolean) => {
    if (!next) {
      // Reset the in-process mock state so a re-enable isn't sticky.
      resetMockDevice();
    }
    setMockDevice(next);
  };

  return (
    <SafeAreaView
      edges={['bottom']}
      style={[styles.root, { backgroundColor: theme.colors.background }]}
    >
      <ScrollView contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.lg }}>
        <Text style={[theme.typography.title, { color: theme.colors.textPrimary }]}>
          Security
        </Text>

        {device ? (
          <Card>
            <CardTitle>Paired device</CardTitle>
            <KeyValue label="Device ID" value={device.deviceId} mono />
            <KeyValue label="Name" value={device.name} />
            <KeyValue label="Host" value={`${device.host}:${device.port}`} mono />
            <KeyValue label="Client ID" value={device.clientId} mono />
            <KeyValue label="Protocol" value={`v${device.protocolVersion}`} />
            <KeyValue
              label="Paired at"
              value={new Date(device.pairedAt * 1000).toLocaleString()}
            />
          </Card>
        ) : (
          <Card>
            <CardTitle>Not paired</CardTitle>
            <Text style={[theme.typography.callout, { color: theme.colors.textMuted }]}>
              No FlightPaper is paired with this phone.
            </Text>
          </Card>
        )}

        <Card>
          <CardTitle>Mock device mode</CardTitle>
          <Text style={[theme.typography.callout, { color: theme.colors.textMuted }]}>
            Use canned data instead of a real FlightPaper. Useful while
            you're away from your device.
          </Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: theme.spacing.sm }}>
            <Text style={[theme.typography.body, { color: theme.colors.textPrimary }]}>
              Enabled
            </Text>
            <Switch value={mockDevice} onValueChange={toggleMock} />
          </View>
        </Card>

        <Card>
          <CardTitle>Reset pairing</CardTitle>
          <Text style={[theme.typography.callout, { color: theme.colors.textMuted }]}>
            Forget this phone's session with the FlightPaper. Asks the
            device to drop its record of this phone if it is reachable.
          </Text>
          <View style={{ marginTop: theme.spacing.sm }}>
            <Button
              title={busy ? 'Resetting…' : 'Reset pairing'}
              color={theme.colors.destructive}
              onPress={confirmReset}
              disabled={busy || (!device && !mockDevice)}
            />
          </View>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});
