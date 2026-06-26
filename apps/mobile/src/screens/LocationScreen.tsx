/**
 * Location screen — permission status, last fix summary, live-GPS
 * toggle, manual one-shot send, and a "open iOS Settings" CTA when
 * permissions are missing.
 *
 * The screen subscribes to the global location store so any background
 * task delivery is reflected immediately.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Button,
  Linking,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useLocationStore } from '../app/state';
import { useTheme } from '../app/theme';
import {
  getCurrentFix,
  readPermissions,
  requestBackgroundPermission,
  requestForegroundPermission,
} from '../services/location/foregroundLocation';
import {
  flushLocationQueue,
  sendLocationToPi,
} from '../services/location/locationSender';
import {
  isBackgroundLocationRunning,
  startBackgroundLocation,
  stopBackgroundLocation,
} from '../services/location/backgroundLocationTask';
import { ageSeconds, formatAge, nowTs } from '../utils/time';
import type { LocationSendOutcome, PermissionStatus } from '../types';

const statusLabel: Record<PermissionStatus, string> = {
  granted: 'Granted',
  denied: 'Denied',
  undetermined: 'Not asked',
};

const outcomeLabel = (outcome: LocationSendOutcome | null): string => {
  if (outcome === null) return '--';
  switch (outcome.status) {
    case 'ok':
      return 'Sent';
    case 'queued':
      return `Queued${outcome.reason ? ` (${outcome.reason})` : ''}`;
    case 'failed':
      return `Failed${outcome.reason ? ` (${outcome.reason})` : ''}`;
  }
};

export default function LocationScreen() {
  const theme = useTheme();
  const permissions = useLocationStore((s) => s.permissions);
  const setPermissions = useLocationStore((s) => s.setPermissions);
  const lastFix = useLocationStore((s) => s.lastFix);
  const pendingQueueSize = useLocationStore((s) => s.pendingQueue.length);
  const backgroundTaskRegistered = useLocationStore(
    (s) => s.backgroundTaskRegistered,
  );
  const setBackgroundTaskRegistered = useLocationStore(
    (s) => s.setBackgroundTaskRegistered,
  );

  const [busy, setBusy] = useState<
    | 'reading'
    | 'requesting-fg'
    | 'requesting-bg'
    | 'sending'
    | 'starting'
    | 'stopping'
    | 'flushing'
    | null
  >(null);
  const [lastOutcome, setLastOutcome] = useState<LocationSendOutcome | null>(null);

  // On mount: read perms + actual background-task state so the UI
  // reflects reality (the OS may have stopped the task while we were
  // away).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setBusy('reading');
      try {
        const [perms, running] = await Promise.all([
          readPermissions(),
          isBackgroundLocationRunning(),
        ]);
        if (cancelled) return;
        setPermissions(perms);
        setBackgroundTaskRegistered(running);
      } catch {
        // Non-fatal — keep the existing store state.
      } finally {
        if (!cancelled) setBusy(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setPermissions, setBackgroundTaskRegistered]);

  const onRequestForeground = useCallback(async () => {
    setBusy('requesting-fg');
    try {
      const next = await requestForegroundPermission();
      setPermissions(next);
    } catch (err) {
      Alert.alert('Permission error', err instanceof Error ? err.message : 'unknown');
    } finally {
      setBusy(null);
    }
  }, [setPermissions]);

  const onRequestBackground = useCallback(async () => {
    setBusy('requesting-bg');
    try {
      const next = await requestBackgroundPermission();
      setPermissions(next);
    } catch (err) {
      Alert.alert('Permission error', err instanceof Error ? err.message : 'unknown');
    } finally {
      setBusy(null);
    }
  }, [setPermissions]);

  const onSendOnce = useCallback(async () => {
    setBusy('sending');
    try {
      const fix = await getCurrentFix();
      const outcome = await sendLocationToPi(fix);
      setLastOutcome(outcome);
    } catch (err) {
      setLastOutcome({
        status: 'failed',
        attemptedAt: nowTs(),
        reason: err instanceof Error ? err.message : 'unknown error',
      });
    } finally {
      setBusy(null);
    }
  }, []);

  const onStartLive = useCallback(async () => {
    setBusy('starting');
    try {
      await startBackgroundLocation();
    } catch (err) {
      Alert.alert(
        'Could not start Live GPS',
        err instanceof Error ? err.message : 'unknown',
      );
    } finally {
      setBusy(null);
    }
  }, []);

  const onStopLive = useCallback(async () => {
    setBusy('stopping');
    try {
      await stopBackgroundLocation();
    } catch (err) {
      Alert.alert(
        'Could not stop Live GPS',
        err instanceof Error ? err.message : 'unknown',
      );
    } finally {
      setBusy(null);
    }
  }, []);

  const onFlushQueue = useCallback(async () => {
    setBusy('flushing');
    try {
      const sent = await flushLocationQueue();
      setLastOutcome({
        status: sent > 0 ? 'ok' : 'failed',
        attemptedAt: nowTs(),
        reason: sent > 0 ? `flushed ${sent}` : 'nothing flushed',
      });
    } finally {
      setBusy(null);
    }
  }, []);

  const onOpenSettings = useCallback(() => {
    if (Platform.OS === 'ios') {
      Linking.openURL('app-settings:');
    } else {
      Linking.openSettings();
    }
  }, []);

  const fixAge = ageSeconds(lastFix?.timestamp ?? null);
  const fgGranted = permissions.foreground === 'granted';
  const bgGranted = permissions.background === 'granted';

  return (
    <SafeAreaView
      edges={['bottom']}
      style={[styles.root, { backgroundColor: theme.colors.background }]}
    >
      <ScrollView
        contentContainerStyle={{
          padding: theme.spacing.lg,
          gap: theme.spacing.lg,
        }}
      >
        <View style={{ gap: theme.spacing.xs }}>
          <Text style={[theme.typography.title, { color: theme.colors.textPrimary }]}>
            Location
          </Text>
          <Text style={[theme.typography.body, { color: theme.colors.textSecondary }]}>
            FlightPaper uses your iPhone's GPS as the device's source of truth.
          </Text>
        </View>

        {/* Permission summary */}
        <View
          style={[
            styles.card,
            {
              backgroundColor: theme.colors.surface,
              borderRadius: theme.radius.md,
              padding: theme.spacing.md,
              gap: theme.spacing.sm,
            },
          ]}
        >
          <Text style={[theme.typography.bodyEmphasis, { color: theme.colors.textPrimary }]}>
            Permissions
          </Text>
          <KeyValue
            label="Foreground (When-In-Use)"
            value={statusLabel[permissions.foreground]}
            valueColor={
              fgGranted ? theme.colors.good : theme.colors.warn
            }
          />
          <KeyValue
            label="Background (Always)"
            value={statusLabel[permissions.background]}
            valueColor={
              bgGranted ? theme.colors.good : theme.colors.warn
            }
          />
          <View style={{ gap: theme.spacing.xs, marginTop: theme.spacing.sm }}>
            {!fgGranted ? (
              <Button title="Allow While Using App" onPress={onRequestForeground} />
            ) : !bgGranted ? (
              <Button title="Allow Always (background)" onPress={onRequestBackground} />
            ) : null}
            {(permissions.foreground === 'denied' || permissions.background === 'denied') ? (
              <Button title="Open iOS Settings" onPress={onOpenSettings} />
            ) : null}
          </View>
        </View>

        {/* Last fix */}
        <View
          style={[
            styles.card,
            {
              backgroundColor: theme.colors.surface,
              borderRadius: theme.radius.md,
              padding: theme.spacing.md,
              gap: theme.spacing.sm,
            },
          ]}
        >
          <Text style={[theme.typography.bodyEmphasis, { color: theme.colors.textPrimary }]}>
            Last fix
          </Text>
          {lastFix ? (
            <>
              <KeyValue
                label="Coords"
                value={`${lastFix.lat.toFixed(5)}, ${lastFix.lon.toFixed(5)}`}
              />
              <KeyValue
                label="Accuracy"
                value={lastFix.accuracyM === null ? '--' : `${lastFix.accuracyM.toFixed(0)} m`}
              />
              <KeyValue label="Source" value={lastFix.source} />
              <KeyValue label="Age" value={formatAge(fixAge)} />
            </>
          ) : (
            <Text style={[theme.typography.callout, { color: theme.colors.textMuted }]}>
              No fix yet. Use Send Now or start Live GPS.
            </Text>
          )}
        </View>

        {/* Live GPS controls */}
        <View
          style={[
            styles.card,
            {
              backgroundColor: theme.colors.surface,
              borderRadius: theme.radius.md,
              padding: theme.spacing.md,
              gap: theme.spacing.sm,
            },
          ]}
        >
          <Text style={[theme.typography.bodyEmphasis, { color: theme.colors.textPrimary }]}>
            Live GPS
          </Text>
          <KeyValue
            label="Background task"
            value={backgroundTaskRegistered ? 'Running' : 'Stopped'}
            valueColor={
              backgroundTaskRegistered ? theme.colors.good : theme.colors.textMuted
            }
          />
          <KeyValue label="Queued sends" value={String(pendingQueueSize)} />
          <View style={{ gap: theme.spacing.xs, marginTop: theme.spacing.sm }}>
            {!backgroundTaskRegistered ? (
              <Button
                title="Start Live GPS"
                onPress={onStartLive}
                disabled={!bgGranted}
              />
            ) : (
              <Button title="Stop Live GPS" onPress={onStopLive} />
            )}
            <Button
              title="Send Now"
              onPress={onSendOnce}
              disabled={!fgGranted}
            />
            <Button
              title="Flush queue"
              onPress={onFlushQueue}
              disabled={pendingQueueSize === 0}
            />
          </View>
          {!bgGranted ? (
            <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>
              Live GPS needs the "Always" permission so your FlightPaper keeps
              receiving updates while the app is in the background.
            </Text>
          ) : null}
        </View>

        {/* Last send */}
        <View
          style={[
            styles.card,
            {
              backgroundColor: theme.colors.surface,
              borderRadius: theme.radius.md,
              padding: theme.spacing.md,
              gap: theme.spacing.sm,
            },
          ]}
        >
          <Text style={[theme.typography.bodyEmphasis, { color: theme.colors.textPrimary }]}>
            Last send
          </Text>
          <KeyValue
            label="Outcome"
            value={outcomeLabel(lastOutcome)}
            valueColor={
              lastOutcome?.status === 'ok'
                ? theme.colors.good
                : lastOutcome?.status === 'queued'
                  ? theme.colors.warn
                  : lastOutcome?.status === 'failed'
                    ? theme.colors.bad
                    : theme.colors.textMuted
            }
          />
          <KeyValue
            label="Attempted"
            value={
              lastOutcome === null
                ? '--'
                : formatAge(ageSeconds(lastOutcome.attemptedAt)) + ' ago'
            }
          />
        </View>

        {busy ? (
          <View style={{ alignItems: 'center', gap: theme.spacing.xs }}>
            <ActivityIndicator />
            <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>
              {busy}…
            </Text>
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

function KeyValue({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  const theme = useTheme();
  return (
    <View style={styles.kv}>
      <Text style={[theme.typography.callout, { color: theme.colors.textSecondary }]}>
        {label}
      </Text>
      <Text
        style={[
          theme.typography.bodyEmphasis,
          { color: valueColor ?? theme.colors.textPrimary },
        ]}
        numberOfLines={1}
      >
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  card: {
    shadowColor: 'rgba(0,0,0,0.04)',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 1,
    shadowRadius: 2,
  },
  kv: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    gap: 8,
  },
});
