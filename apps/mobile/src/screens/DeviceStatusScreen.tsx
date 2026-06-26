/**
 * Full ``/api/secure/status`` dump, broken up by block.
 *
 * Slightly noisier than DeviceHome — meant for "what is the device
 * actually doing right now" debugging. Tap-to-refresh + raw-JSON
 * dropdown so we can copy the body when filing issues.
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
import { Card, CardTitle, KeyValue, StatusBadge } from '../components/ui';
import { useDeviceClient } from '../hooks/useDeviceClient';
import { logEvent } from '../app/state/logStore';
import { formatAge } from '../utils/time';
import type { StatusResponse } from '../types';

export default function DeviceStatusScreen() {
  const theme = useTheme();
  const handle = useDeviceClient();

  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showJson, setShowJson] = useState(false);

  const fetchStatus = useCallback(async () => {
    if (!handle.client) return;
    try {
      const next = await handle.client.fetchStatus();
      setStatus(next);
      setError(null);
    } catch (err) {
      const reason = err instanceof Error ? err.message : 'unknown error';
      setError(reason);
      logEvent('error', `status fetch failed: ${reason}`, 'api');
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
          Device status
        </Text>

        <Card>
          <CardTitle>Device</CardTitle>
          <KeyValue label="ID" value={status.device.id} mono />
          <KeyValue label="Name" value={status.device.name} />
          <KeyValue label="Firmware" value={status.device.version} />
          <KeyValue label="Uptime" value={formatAge(status.device.uptime_seconds)} />
        </Card>

        <Card>
          <CardTitle>Network</CardTitle>
          <KeyValue label="Wi-Fi SSID" value={status.network.wifi_ssid ?? '--'} />
          <KeyValue label="IP" value={status.network.ip_address} mono />
          <KeyValue
            label="Internet"
            value={status.network.internet_ok ? 'OK' : 'Unreachable'}
            valueColor={status.network.internet_ok ? theme.colors.good : theme.colors.bad}
          />
        </Card>

        <Card>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <CardTitle>Battery</CardTitle>
            <StatusBadge
              label={status.battery.battery_saver ? 'SAVER' : 'OK'}
              tone={status.battery.battery_saver ? 'warn' : 'good'}
            />
          </View>
          <KeyValue
            label="Charge"
            value={status.battery.percent === null ? '--' : `${status.battery.percent}%`}
          />
          <KeyValue label="Charging" value={status.battery.charging ? 'Yes' : 'No'} />
          <KeyValue
            label="External power"
            value={status.battery.external_power ? 'Yes' : 'No'}
          />
        </Card>

        <Card>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <CardTitle>Location</CardTitle>
            <StatusBadge
              label={status.location.state}
              tone={
                status.location.state === 'fresh'
                  ? 'good'
                  : status.location.state === 'stale'
                    ? 'warn'
                    : status.location.state === 'expired'
                      ? 'bad'
                      : 'muted'
              }
            />
          </View>
          <KeyValue label="Source" value={status.location.source ?? '--'} />
          <KeyValue label="Age" value={formatAge(status.location.age_seconds)} />
          <KeyValue
            label="Accuracy"
            value={status.location.accuracy_m === null ? '--' : `${status.location.accuracy_m.toFixed(0)} m`}
          />
        </Card>

        <Card>
          <CardTitle>OpenSky</CardTitle>
          <KeyValue label="Status" value={status.opensky.status} />
          <KeyValue label="Aircraft" value={String(status.opensky.aircraft_count)} />
          <KeyValue label="Last update" value={formatAge(status.opensky.last_update_age_seconds)} />
          <KeyValue
            label="Rate-limit remaining"
            value={status.opensky.rate_limit_remaining === null ? '--' : String(status.opensky.rate_limit_remaining)}
          />
        </Card>

        <Card>
          <CardTitle>Display</CardTitle>
          <KeyValue label="Page" value={status.display.page} />
          <KeyValue label="Last refresh" value={formatAge(status.display.last_refresh_age_seconds)} />
        </Card>

        <Card>
          <CardTitle>Raw JSON</CardTitle>
          <Button
            title={showJson ? 'Hide' : 'Show'}
            onPress={() => setShowJson((v) => !v)}
          />
          {showJson ? (
            <Text
              selectable
              style={[
                theme.typography.mono,
                {
                  color: theme.colors.textPrimary,
                  marginTop: theme.spacing.sm,
                },
              ]}
            >
              {JSON.stringify(status, null, 2)}
            </Text>
          ) : null}
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});
