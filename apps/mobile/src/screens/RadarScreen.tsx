/**
 * Phone-side mirror of the FlightPaper ePaper radar page.
 *
 * Aircraft are fetched from ``GET /api/secure/aircraft`` every 5s and
 * plotted on concentric rings — phone heading is "up", distance is
 * proportional to ring radius up to the configured ``radius_km``.
 *
 * Plain ``<View>`` + transforms (no ``react-native-svg``) keeps the
 * dependency surface flat. Aircraft markers are small filled triangles
 * rotated by ``true_track_deg`` so direction of flight reads at a
 * glance.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useTheme } from '../app/theme';
import { Card, CardTitle, KeyValue } from '../components/ui';
import { useDeviceClient } from '../hooks/useDeviceClient';
import { logEvent } from '../app/state/logStore';
import { formatAge } from '../utils/time';
import type { Aircraft, AircraftResponse } from '../types';

const POLL_INTERVAL_MS = 5_000;
const RADAR_SIZE = 280;
const CENTER = RADAR_SIZE / 2;
const MARKER_SIZE = 12;

interface PlottedAircraft {
  ac: Aircraft;
  x: number;
  y: number;
}

const plot = (
  ac: Aircraft,
  radiusKm: number,
): PlottedAircraft | null => {
  if (ac.distance_km === null || ac.bearing_deg === null) return null;
  // Scale: distance 0..radiusKm → 0..(CENTER - margin)
  const margin = MARKER_SIZE;
  const r = (Math.min(ac.distance_km, radiusKm) / radiusKm) * (CENTER - margin);
  const theta = ((ac.bearing_deg - 90) * Math.PI) / 180; // 0deg = North = up
  // Math: bearing increases clockwise from north; in screen coords +x is east, -y is north.
  const x = CENTER + r * Math.cos(theta);
  const y = CENTER + r * Math.sin(theta);
  return { ac, x, y };
};

export default function RadarScreen() {
  const theme = useTheme();
  const handle = useDeviceClient();

  const [data, setData] = useState<AircraftResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchAircraft = useCallback(async () => {
    if (!handle.client) return;
    try {
      const next = await handle.client.fetchAircraft({ sort: 'distance' });
      setData(next);
      setError(null);
    } catch (err) {
      const reason = err instanceof Error ? err.message : 'unknown error';
      setError(reason);
      logEvent('error', `aircraft fetch failed: ${reason}`, 'api');
    }
  }, [handle.client]);

  useEffect(() => {
    if (!handle.ready || !handle.client) return;
    void fetchAircraft();
    const t = setInterval(() => void fetchAircraft(), POLL_INTERVAL_MS);
    return () => clearInterval(t);
  }, [handle.ready, handle.client, fetchAircraft]);

  const radiusKm = data?.radius_km ?? 40;

  const plots = useMemo<PlottedAircraft[]>(() => {
    if (!data) return [];
    return data.aircraft
      .map((ac) => plot(ac, radiusKm))
      .filter((p): p is PlottedAircraft => p !== null);
  }, [data, radiusKm]);

  return (
    <SafeAreaView
      edges={['bottom']}
      style={[styles.root, { backgroundColor: theme.colors.background }]}
    >
      <View style={{ padding: theme.spacing.lg, gap: theme.spacing.md }}>
        <Text style={[theme.typography.title, { color: theme.colors.textPrimary }]}>
          Radar
        </Text>
        <Text style={[theme.typography.callout, { color: theme.colors.textSecondary }]}>
          {data
            ? `${data.count} aircraft within ${radiusKm.toFixed(0)} km · updated ${formatAge((data.as_of_seconds ? Math.floor(Date.now() / 1000) - data.as_of_seconds : null))} ago`
            : 'Loading…'}
        </Text>

        <View style={{ alignItems: 'center' }}>
          <View
            style={[
              styles.radar,
              {
                width: RADAR_SIZE,
                height: RADAR_SIZE,
                borderRadius: RADAR_SIZE / 2,
                borderColor: theme.colors.border,
                backgroundColor: theme.colors.surface,
              },
            ]}
          >
            {[0.33, 0.66].map((ratio) => (
              <View
                key={ratio}
                style={[
                  styles.ring,
                  {
                    width: RADAR_SIZE * ratio,
                    height: RADAR_SIZE * ratio,
                    borderRadius: (RADAR_SIZE * ratio) / 2,
                    borderColor: theme.colors.border,
                    top: CENTER - (RADAR_SIZE * ratio) / 2,
                    left: CENTER - (RADAR_SIZE * ratio) / 2,
                  },
                ]}
              />
            ))}
            <View
              style={[
                styles.crosshairH,
                { backgroundColor: theme.colors.border, top: CENTER - 0.5 },
              ]}
            />
            <View
              style={[
                styles.crosshairV,
                { backgroundColor: theme.colors.border, left: CENTER - 0.5 },
              ]}
            />
            <View
              style={[
                styles.youDot,
                {
                  backgroundColor: theme.colors.accent,
                  left: CENTER - 4,
                  top: CENTER - 4,
                },
              ]}
            />
            {plots.map(({ ac, x, y }) => (
              <View
                key={ac.icao24}
                style={[
                  styles.marker,
                  {
                    left: x - MARKER_SIZE / 2,
                    top: y - MARKER_SIZE / 2,
                    transform: [{ rotate: `${ac.true_track_deg ?? 0}deg` }],
                  },
                ]}
              >
                <View
                  style={[
                    styles.markerTriangle,
                    { borderBottomColor: theme.colors.textPrimary },
                  ]}
                />
              </View>
            ))}
            <Text style={[styles.northLabel, { color: theme.colors.textMuted }]}>N</Text>
          </View>
        </View>

        {error ? (
          <Card>
            <CardTitle>Couldn't fetch aircraft</CardTitle>
            <Text style={[theme.typography.callout, { color: theme.colors.bad }]}>
              {error}
            </Text>
            <Button title="Retry" onPress={fetchAircraft} />
          </Card>
        ) : null}

        {data && data.aircraft.length === 0 ? (
          <Card>
            <CardTitle>No aircraft in range</CardTitle>
            <KeyValue label="Radius" value={`${radiusKm.toFixed(0)} km`} />
          </Card>
        ) : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  radar: {
    borderWidth: 1,
    position: 'relative',
  },
  ring: {
    position: 'absolute',
    borderWidth: 1,
    backgroundColor: 'transparent',
  },
  crosshairH: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 1,
  },
  crosshairV: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: 1,
  },
  youDot: {
    position: 'absolute',
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  marker: {
    position: 'absolute',
    width: MARKER_SIZE,
    height: MARKER_SIZE,
    alignItems: 'center',
    justifyContent: 'center',
  },
  markerTriangle: {
    width: 0,
    height: 0,
    borderLeftWidth: 5,
    borderRightWidth: 5,
    borderBottomWidth: 10,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
  },
  northLabel: {
    position: 'absolute',
    top: 4,
    left: CENTER - 6,
    fontSize: 11,
    fontWeight: '600',
  },
});
