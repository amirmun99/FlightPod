/**
 * Read-only Wi-Fi summary (MVP per spec §20).
 *
 * Shows the SSID + IP from the latest ``/api/secure/status`` response.
 * Editing Wi-Fi from the app is intentionally deferred until we have
 * a working ``nmcli add`` flow on the Pi side.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Button,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useTheme } from '../app/theme';
import { Card, CardTitle, KeyValue } from '../components/ui';
import { useDeviceClient } from '../hooks/useDeviceClient';
import { logEvent } from '../app/state/logStore';
import type { StatusResponse } from '../types';

export default function WifiScreen() {
  const theme = useTheme();
  const handle = useDeviceClient();

  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    if (!handle.client) return;
    try {
      const s = await handle.client.fetchStatus();
      setStatus(s);
      setError(null);
    } catch (err) {
      const reason = err instanceof Error ? err.message : 'unknown error';
      setError(reason);
      logEvent('error', `wifi fetch failed: ${reason}`, 'api');
    }
  }, [handle.client]);

  useEffect(() => {
    if (!handle.ready) return;
    void fetchStatus();
  }, [handle.ready, fetchStatus]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchStatus();
    setRefreshing(false);
  }, [fetchStatus]);

  if (!status) {
    return (
      <SafeAreaView
        edges={['bottom']}
        style={[styles.root, { backgroundColor: theme.colors.background, alignItems: 'center', justifyContent: 'center' }]}
      >
        {error ? (
          <View style={{ padding: theme.spacing.lg, gap: theme.spacing.md }}>
            <Text style={[theme.typography.body, { color: theme.colors.bad }]}>
              {error}
            </Text>
            <Button title="Retry" onPress={onRefresh} />
          </View>
        ) : (
          <ActivityIndicator />
        )}
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView
      edges={['bottom']}
      style={[styles.root, { backgroundColor: theme.colors.background }]}
    >
      <ScrollView
        contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.lg }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <Text style={[theme.typography.title, { color: theme.colors.textPrimary }]}>
          Wi-Fi
        </Text>

        <Card>
          <CardTitle>Current connection</CardTitle>
          <KeyValue label="SSID" value={status.network.wifi_ssid ?? '--'} />
          <KeyValue label="IP address" value={status.network.ip_address} mono />
          <KeyValue
            label="Internet"
            value={status.network.internet_ok ? 'Reachable' : 'Unreachable'}
            valueColor={status.network.internet_ok ? theme.colors.good : theme.colors.bad}
          />
        </Card>

        <Card>
          <CardTitle>Adding a new network</CardTitle>
          <Text style={[theme.typography.callout, { color: theme.colors.textMuted }]}>
            Editing Wi-Fi from the app is not in the MVP. To switch
            networks, plug a keyboard + monitor into the FlightPaper and
            use ``nmcli`` or rebuild with the desired hotspot in
            ``wpa_supplicant.conf``.
          </Text>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});
