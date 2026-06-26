/**
 * Home screen — at-a-glance summary of the paired FlightPaper plus a
 * grid of links to the rest of the app.
 *
 * The status block pulls from ``GET /api/secure/status`` (real or
 * mock). A pull-to-refresh + a 30s background interval keep it fresh.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { RootStackParamList } from '../app/navigation/RootNavigator';
import { useDeviceStore } from '../app/state';
import { useTheme } from '../app/theme';
import { Card, CardTitle, KeyValue, StatusBadge } from '../components/ui';
import { useDeviceClient } from '../hooks/useDeviceClient';
import { logEvent } from '../app/state/logStore';
import { formatAge } from '../utils/time';
import type { StatusResponse } from '../types';

type Nav = NativeStackNavigationProp<RootStackParamList, 'DeviceHome'>;

const REFRESH_INTERVAL_MS = 30_000;

const batteryTone = (
  pct: number | null,
  charging: boolean | null,
): 'good' | 'warn' | 'bad' | 'muted' => {
  if (pct === null) return 'muted';
  if (charging) return 'good';
  if (pct <= 10) return 'bad';
  if (pct <= 25) return 'warn';
  return 'good';
};

const locationTone = (
  state: StatusResponse['location']['state'],
): 'good' | 'warn' | 'bad' | 'muted' => {
  switch (state) {
    case 'fresh':
      return 'good';
    case 'stale':
      return 'warn';
    case 'expired':
      return 'bad';
    case 'none':
    default:
      return 'muted';
  }
};

export default function DeviceHomeScreen() {
  const navigation = useNavigation<Nav>();
  const theme = useTheme();
  const handle = useDeviceClient();
  const setStatusError = useDeviceStore((s) => s.setStatusError);
  const setStatus = useDeviceStore((s) => s.setStatus);
  const status = useDeviceStore((s) => s.lastStatus);
  const statusError = useDeviceStore((s) => s.lastStatusError);
  const isMockDevice = useDeviceStore((s) => s.mockDevice);

  const [refreshing, setRefreshing] = useState(false);

  const fetchStatus = useCallback(async () => {
    if (!handle.client) return;
    try {
      const next = await handle.client.fetchStatus();
      setStatus(next);
    } catch (err) {
      const reason = err instanceof Error ? err.message : 'unknown error';
      setStatusError(reason);
      logEvent('error', `status fetch failed: ${reason}`, 'api');
    }
  }, [handle.client, setStatus, setStatusError]);

  useEffect(() => {
    if (!handle.ready || !handle.client) return;
    void fetchStatus();
    const t = setInterval(() => {
      void fetchStatus();
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(t);
  }, [handle.ready, handle.client, fetchStatus]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchStatus();
    setRefreshing(false);
  }, [fetchStatus]);

  const batteryLabel =
    status?.battery.percent === null
      ? '--'
      : `${status?.battery.percent}%${status?.battery.charging ? ' ⚡' : ''}`;

  return (
    <SafeAreaView
      edges={['bottom']}
      style={[styles.root, { backgroundColor: theme.colors.background }]}
    >
      <ScrollView
        contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.lg }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <View style={{ gap: theme.spacing.xs }}>
          <Text style={[theme.typography.title, { color: theme.colors.textPrimary }]}>
            {status?.device.name ?? 'FlightPaper'}
          </Text>
          <Text style={[theme.typography.callout, { color: theme.colors.textSecondary }]}>
            {status?.device.id ?? '(no device id)'}
            {isMockDevice ? '  ·  mock device mode' : ''}
          </Text>
        </View>

        {statusError ? (
          <Card>
            <CardTitle>Couldn't reach the device</CardTitle>
            <Text style={[theme.typography.callout, { color: theme.colors.bad }]}>
              {statusError}
            </Text>
            <Button title="Retry now" onPress={onRefresh} />
          </Card>
        ) : null}

        <Card>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <CardTitle>Battery</CardTitle>
            {status ? (
              <StatusBadge
                label={batteryTone(status.battery.percent, status.battery.charging) === 'good' ? 'OK' : (batteryTone(status.battery.percent, status.battery.charging) === 'warn' ? 'LOW' : (batteryTone(status.battery.percent, status.battery.charging) === 'bad' ? 'CRITICAL' : '—'))}
                tone={batteryTone(status.battery.percent, status.battery.charging)}
              />
            ) : null}
          </View>
          <KeyValue label="Charge" value={batteryLabel} />
          <KeyValue
            label="External power"
            value={status?.battery.external_power ? 'Plugged in' : 'Not plugged'}
          />
          <KeyValue
            label="Battery saver"
            value={status?.battery.battery_saver ? 'On' : 'Off'}
          />
        </Card>

        <Card>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <CardTitle>Location</CardTitle>
            {status ? (
              <StatusBadge
                label={status.location.state}
                tone={locationTone(status.location.state)}
              />
            ) : null}
          </View>
          <KeyValue label="Source" value={status?.location.source ?? '--'} />
          <KeyValue
            label="Age"
            value={formatAge(status?.location.age_seconds ?? null)}
          />
          <KeyValue
            label="Accuracy"
            value={
              status?.location.accuracy_m == null
                ? '--'
                : `${status.location.accuracy_m.toFixed(0)} m`
            }
          />
        </Card>

        <Card>
          <CardTitle>OpenSky</CardTitle>
          <KeyValue label="Status" value={status?.opensky.status ?? '--'} />
          <KeyValue
            label="Aircraft nearby"
            value={String(status?.opensky.aircraft_count ?? '--')}
          />
          <KeyValue
            label="Last update"
            value={formatAge(status?.opensky.last_update_age_seconds ?? null)}
          />
          <KeyValue
            label="Rate-limit remaining"
            value={String(status?.opensky.rate_limit_remaining ?? '--')}
          />
        </Card>

        <Card>
          <CardTitle>Display</CardTitle>
          <KeyValue label="Page" value={status?.display.page ?? '--'} />
          <KeyValue
            label="Last refresh"
            value={formatAge(status?.display.last_refresh_age_seconds ?? null)}
          />
          <View style={{ marginTop: theme.spacing.sm, gap: theme.spacing.xs }}>
            <Button
              title="Force refresh"
              onPress={async () => {
                try {
                  await handle.client?.refreshDevice();
                  await fetchStatus();
                } catch (err) {
                  logEvent(
                    'error',
                    `refresh failed: ${err instanceof Error ? err.message : 'unknown'}`,
                    'api',
                  );
                }
              }}
              disabled={!handle.client}
            />
          </View>
        </Card>

        <View style={{ gap: theme.spacing.xs }}>
          <Text style={[theme.typography.bodyEmphasis, { color: theme.colors.textPrimary }]}>
            Browse
          </Text>
          <Button title="Radar" onPress={() => navigation.navigate('Radar')} />
          <Button title="Aircraft list" onPress={() => navigation.navigate('AircraftList')} />
          <Button title="Location" onPress={() => navigation.navigate('Location')} />
          <Button title="Device status" onPress={() => navigation.navigate('DeviceStatus')} />
          <Button title="Settings" onPress={() => navigation.navigate('Settings')} />
          <Button title="Security" onPress={() => navigation.navigate('Security')} />
          <Button title="Wi-Fi" onPress={() => navigation.navigate('Wifi')} />
          <Button title="Logs" onPress={() => navigation.navigate('Logs')} />
          <Button title="About" onPress={() => navigation.navigate('About')} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});
