/**
 * Tabular list of aircraft visible to the paired FlightPaper.
 *
 * Backed by ``GET /api/secure/aircraft``. The user can pick a sort key
 * (distance / overhead / altitude) which is sent to the Pi — the Pi
 * resorts since it knows the ground-aircraft + radius config.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useTheme } from '../app/theme';
import { Card, CardTitle } from '../components/ui';
import { useDeviceClient } from '../hooks/useDeviceClient';
import { logEvent } from '../app/state/logStore';
import { formatAge } from '../utils/time';
import type { Aircraft, AircraftResponse, AircraftSort } from '../types';

const SORTS: { key: AircraftSort; label: string }[] = [
  { key: 'distance', label: 'Distance' },
  { key: 'overhead', label: 'Overhead' },
  { key: 'altitude', label: 'Altitude' },
];

const formatAltitude = (ft: number | null): string =>
  ft === null ? '--' : `${(ft / 1000).toFixed(1)}k ft`;

const formatBearing = (deg: number | null): string =>
  deg === null ? '--' : `${deg.toFixed(0)}°`;

const formatDistance = (km: number | null): string =>
  km === null ? '--' : `${km.toFixed(1)} km`;

export default function AircraftListScreen() {
  const theme = useTheme();
  const handle = useDeviceClient();

  const [sort, setSort] = useState<AircraftSort>('distance');
  const [data, setData] = useState<AircraftResponse | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAircraft = useCallback(async () => {
    if (!handle.client) return;
    try {
      const next = await handle.client.fetchAircraft({ sort });
      setData(next);
      setError(null);
    } catch (err) {
      const reason = err instanceof Error ? err.message : 'unknown error';
      setError(reason);
      logEvent('error', `aircraft fetch failed: ${reason}`, 'api');
    }
  }, [handle.client, sort]);

  useEffect(() => {
    if (!handle.ready || !handle.client) return;
    void fetchAircraft();
  }, [handle.ready, handle.client, fetchAircraft]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchAircraft();
    setRefreshing(false);
  }, [fetchAircraft]);

  const renderItem = ({ item }: { item: Aircraft }) => (
    <View
      style={[
        styles.row,
        {
          borderBottomColor: theme.colors.border,
          paddingVertical: theme.spacing.sm,
          paddingHorizontal: theme.spacing.lg,
        },
      ]}
    >
      <View style={{ flex: 1 }}>
        <Text style={[theme.typography.bodyEmphasis, { color: theme.colors.textPrimary }]}>
          {item.callsign?.trim() || item.icao24}
        </Text>
        <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>
          {item.icao24} · {item.origin_country ?? 'unknown origin'}
          {item.on_ground ? ' · on ground' : ''}
        </Text>
      </View>
      <View style={{ width: 80, alignItems: 'flex-end' }}>
        <Text style={[theme.typography.callout, { color: theme.colors.textPrimary }]}>
          {formatDistance(item.distance_km)}
        </Text>
        <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>
          {formatBearing(item.bearing_deg)}
        </Text>
      </View>
      <View style={{ width: 70, alignItems: 'flex-end' }}>
        <Text style={[theme.typography.callout, { color: theme.colors.textPrimary }]}>
          {formatAltitude(item.baro_altitude_ft)}
        </Text>
        <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>
          {item.velocity_kt === null ? '--' : `${item.velocity_kt.toFixed(0)} kt`}
        </Text>
      </View>
    </View>
  );

  const sortBar = (
    <View
      style={[
        styles.sortBar,
        { paddingHorizontal: theme.spacing.lg, paddingVertical: theme.spacing.sm, gap: theme.spacing.xs },
      ]}
    >
      {SORTS.map((s) => {
        const active = s.key === sort;
        return (
          <TouchableOpacity
            key={s.key}
            onPress={() => setSort(s.key)}
            style={[
              styles.pill,
              {
                backgroundColor: active ? theme.colors.accent : theme.colors.surface,
                borderColor: theme.colors.border,
              },
            ]}
          >
            <Text
              style={[
                theme.typography.callout,
                { color: active ? '#fff' : theme.colors.textPrimary, fontWeight: '600' },
              ]}
            >
              {s.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );

  return (
    <SafeAreaView
      edges={['bottom']}
      style={[styles.root, { backgroundColor: theme.colors.background }]}
    >
      <View
        style={{
          paddingHorizontal: theme.spacing.lg,
          paddingTop: theme.spacing.md,
          gap: theme.spacing.xs,
        }}
      >
        <Text style={[theme.typography.title, { color: theme.colors.textPrimary }]}>
          Nearby aircraft
        </Text>
        <Text style={[theme.typography.callout, { color: theme.colors.textSecondary }]}>
          {data ? `${data.count} within ${data.radius_km.toFixed(0)} km` : 'Loading…'}
        </Text>
      </View>
      {sortBar}
      {error ? (
        <View style={{ paddingHorizontal: theme.spacing.lg }}>
          <Card>
            <CardTitle>Couldn't fetch aircraft</CardTitle>
            <Text style={[theme.typography.callout, { color: theme.colors.bad }]}>
              {error}
            </Text>
          </Card>
        </View>
      ) : null}
      {data === null ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator />
        </View>
      ) : (
        <FlatList
          data={data.aircraft}
          keyExtractor={(ac) => ac.icao24}
          renderItem={renderItem}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          ListEmptyComponent={
            <View style={{ padding: theme.spacing.lg }}>
              <Text
                style={[
                  theme.typography.callout,
                  { color: theme.colors.textMuted, textAlign: 'center' },
                ]}
              >
                No aircraft in range.
              </Text>
            </View>
          }
          ListFooterComponent={
            <View style={{ padding: theme.spacing.lg }}>
              <Text
                style={[
                  theme.typography.caption,
                  { color: theme.colors.textMuted, textAlign: 'center' },
                ]}
              >
                Updated{' '}
                {formatAge(
                  data.as_of_seconds
                    ? Math.floor(Date.now() / 1000) - data.as_of_seconds
                    : null,
                )}{' '}
                ago
              </Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 12,
  },
  sortBar: {
    flexDirection: 'row',
  },
  pill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
  },
});
