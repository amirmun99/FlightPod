/**
 * PATCHes the whitelisted subset of the Pi config (see
 * ``ConfigPatchRequest`` in ``apps/pi/flightpaper/api/schemas.py``).
 *
 * Pattern:
 *   - Fetch the current ``PiConfigSummary`` on mount.
 *   - Local editable copy in component state.
 *   - "Save" computes a diff and PATCHes only changed fields.
 *   - Pi returns the canonical summary which we re-set as ground truth.
 *
 * Range/unit validation lives in :func:`buildPatch` so the user never
 * tries to send (e.g.) ``radius_km = 0`` — the Pi would reject it.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Button,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useTheme } from '../app/theme';
import { Card, CardTitle, KeyValue } from '../components/ui';
import { useDeviceClient } from '../hooks/useDeviceClient';
import { logEvent } from '../app/state/logStore';
import type {
  AltitudeUnits,
  ConfigPatch,
  DisplayPage,
  DistanceUnits,
  PiConfigSummary,
  SpeedUnits,
} from '../types';

const DISTANCE_OPTS: DistanceUnits[] = ['km', 'nm'];
const ALTITUDE_OPTS: AltitudeUnits[] = ['ft', 'm'];
const SPEED_OPTS: SpeedUnits[] = ['kt', 'mps', 'kmh'];
const PAGE_OPTS: DisplayPage[] = ['radar', 'closest', 'list', 'status'];

/** Compute the minimal patch from ``orig`` → ``draft``. */
export const buildPatch = (
  orig: PiConfigSummary,
  draft: PiConfigSummary,
): ConfigPatch => {
  const patch: ConfigPatch = {};
  if (orig.ui.radius_km !== draft.ui.radius_km) {
    patch.ui_radius_km = draft.ui.radius_km;
  }
  if (orig.ui.overhead_threshold_km !== draft.ui.overhead_threshold_km) {
    patch.ui_overhead_threshold_km = draft.ui.overhead_threshold_km;
  }
  if (orig.ui.distance_units !== draft.ui.distance_units) {
    patch.ui_distance_units = draft.ui.distance_units;
  }
  if (orig.ui.altitude_units !== draft.ui.altitude_units) {
    patch.ui_altitude_units = draft.ui.altitude_units;
  }
  if (orig.ui.speed_units !== draft.ui.speed_units) {
    patch.ui_speed_units = draft.ui.speed_units;
  }
  if (orig.opensky.update_interval_seconds !== draft.opensky.update_interval_seconds) {
    patch.opensky_update_interval_seconds = draft.opensky.update_interval_seconds;
  }
  if (
    orig.opensky.battery_saver_interval_seconds !==
    draft.opensky.battery_saver_interval_seconds
  ) {
    patch.opensky_battery_saver_interval_seconds =
      draft.opensky.battery_saver_interval_seconds;
  }
  if (orig.opensky.max_aircraft_age_seconds !== draft.opensky.max_aircraft_age_seconds) {
    patch.opensky_max_aircraft_age_seconds = draft.opensky.max_aircraft_age_seconds;
  }
  if (orig.opensky.include_ground_aircraft !== draft.opensky.include_ground_aircraft) {
    patch.opensky_include_ground_aircraft = draft.opensky.include_ground_aircraft;
  }
  if (orig.display.partial_refresh !== draft.display.partial_refresh) {
    patch.display_partial_refresh = draft.display.partial_refresh;
  }
  if (orig.display.full_refresh_every !== draft.display.full_refresh_every) {
    patch.display_full_refresh_every = draft.display.full_refresh_every;
  }
  if (orig.display.default_page !== draft.display.default_page) {
    patch.display_default_page = draft.display.default_page;
  }
  if (orig.battery.low_percent !== draft.battery.low_percent) {
    patch.battery_low_percent = draft.battery.low_percent;
  }
  if (orig.battery.critical_percent !== draft.battery.critical_percent) {
    patch.battery_critical_percent = draft.battery.critical_percent;
  }
  if (
    orig.battery.battery_saver_below_percent !==
    draft.battery.battery_saver_below_percent
  ) {
    patch.battery_battery_saver_below_percent =
      draft.battery.battery_saver_below_percent;
  }
  if (orig.location.manual.enabled !== draft.location.manual.enabled) {
    patch.location_manual_enabled = draft.location.manual.enabled;
  }
  if (
    orig.location.manual.lat !== draft.location.manual.lat &&
    draft.location.manual.lat !== null
  ) {
    patch.location_manual_lat = draft.location.manual.lat;
  }
  if (
    orig.location.manual.lon !== draft.location.manual.lon &&
    draft.location.manual.lon !== null
  ) {
    patch.location_manual_lon = draft.location.manual.lon;
  }
  if (orig.location.manual.label !== draft.location.manual.label) {
    patch.location_manual_label = draft.location.manual.label;
  }
  return patch;
};

/** Each field carries its Pi-side range so client validation matches. */
export const validatePatch = (patch: ConfigPatch): string | null => {
  if (patch.ui_radius_km !== undefined) {
    if (!(patch.ui_radius_km > 0 && patch.ui_radius_km <= 500))
      return 'Radius must be > 0 and ≤ 500 km';
  }
  if (patch.ui_overhead_threshold_km !== undefined) {
    if (!(patch.ui_overhead_threshold_km > 0 && patch.ui_overhead_threshold_km <= 50))
      return 'Overhead threshold must be > 0 and ≤ 50 km';
  }
  if (patch.opensky_update_interval_seconds !== undefined) {
    if (
      patch.opensky_update_interval_seconds < 10 ||
      patch.opensky_update_interval_seconds > 600
    )
      return 'OpenSky interval must be 10–600 s';
  }
  if (patch.opensky_max_aircraft_age_seconds !== undefined) {
    if (
      patch.opensky_max_aircraft_age_seconds < 10 ||
      patch.opensky_max_aircraft_age_seconds > 3600
    )
      return 'Aircraft max age must be 10–3600 s';
  }
  if (patch.display_full_refresh_every !== undefined) {
    if (patch.display_full_refresh_every < 1 || patch.display_full_refresh_every > 200)
      return 'Full refresh interval must be 1–200';
  }
  for (const key of [
    'battery_low_percent',
    'battery_critical_percent',
    'battery_battery_saver_below_percent',
  ] as const) {
    const v = patch[key];
    if (v !== undefined && (v < 1 || v > 99)) {
      return `${key.replace(/_/g, ' ')} must be 1–99`;
    }
  }
  if (patch.location_manual_lat !== undefined) {
    if (patch.location_manual_lat < -90 || patch.location_manual_lat > 90)
      return 'Latitude must be between -90 and 90';
  }
  if (patch.location_manual_lon !== undefined) {
    if (patch.location_manual_lon < -180 || patch.location_manual_lon > 180)
      return 'Longitude must be between -180 and 180';
  }
  if (
    patch.location_manual_label !== undefined &&
    patch.location_manual_label.length > 32
  ) {
    return 'Manual location label must be ≤ 32 chars';
  }
  return null;
};

const parseNumber = (s: string): number | null => {
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
};

export default function SettingsScreen() {
  const theme = useTheme();
  const handle = useDeviceClient();

  const [original, setOriginal] = useState<PiConfigSummary | null>(null);
  const [draft, setDraft] = useState<PiConfigSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!handle.client) return;
    setLoading(true);
    try {
      const cfg = await handle.client.fetchConfig();
      setOriginal(cfg);
      setDraft(cfg);
      setFetchError(null);
    } catch (err) {
      const reason = err instanceof Error ? err.message : 'unknown error';
      setFetchError(reason);
      logEvent('error', `config fetch failed: ${reason}`, 'api');
    } finally {
      setLoading(false);
    }
  }, [handle.client]);

  useEffect(() => {
    if (!handle.ready) return;
    void load();
  }, [handle.ready, load]);

  const patch = useMemo<ConfigPatch>(() => {
    if (!original || !draft) return {};
    return buildPatch(original, draft);
  }, [original, draft]);

  const dirty = Object.keys(patch).length > 0;

  const onSave = async () => {
    if (!handle.client || !draft || !dirty) return;
    const validationError = validatePatch(patch);
    if (validationError) {
      Alert.alert('Invalid setting', validationError);
      return;
    }
    setSaving(true);
    try {
      const saved = await handle.client.patchConfig(patch);
      setOriginal(saved);
      setDraft(saved);
    } catch (err) {
      const reason = err instanceof Error ? err.message : 'unknown error';
      Alert.alert("Couldn't save", reason);
      logEvent('error', `config save failed: ${reason}`, 'api');
    } finally {
      setSaving(false);
    }
  };

  const onRevert = () => {
    if (original) setDraft(original);
  };

  if (loading || !draft) {
    return (
      <SafeAreaView
        edges={['bottom']}
        style={[styles.root, { backgroundColor: theme.colors.background, alignItems: 'center', justifyContent: 'center' }]}
      >
        {fetchError ? (
          <View style={{ padding: theme.spacing.lg, gap: theme.spacing.md }}>
            <Text style={[theme.typography.body, { color: theme.colors.bad }]}>
              Couldn't load config: {fetchError}
            </Text>
            <Button title="Retry" onPress={load} />
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
      <ScrollView contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.lg }}>
        <Text style={[theme.typography.title, { color: theme.colors.textPrimary }]}>
          Settings
        </Text>

        <Card>
          <CardTitle>Radar & units</CardTitle>
          <NumberRow
            label="Radius (km)"
            value={draft.ui.radius_km}
            onChange={(v) =>
              setDraft({ ...draft, ui: { ...draft.ui, radius_km: v } })
            }
          />
          <NumberRow
            label="Overhead threshold (km)"
            value={draft.ui.overhead_threshold_km}
            onChange={(v) =>
              setDraft({ ...draft, ui: { ...draft.ui, overhead_threshold_km: v } })
            }
          />
          <PillRow
            label="Distance units"
            value={draft.ui.distance_units}
            options={DISTANCE_OPTS}
            onChange={(v) =>
              setDraft({ ...draft, ui: { ...draft.ui, distance_units: v } })
            }
          />
          <PillRow
            label="Altitude units"
            value={draft.ui.altitude_units}
            options={ALTITUDE_OPTS}
            onChange={(v) =>
              setDraft({ ...draft, ui: { ...draft.ui, altitude_units: v } })
            }
          />
          <PillRow
            label="Speed units"
            value={draft.ui.speed_units}
            options={SPEED_OPTS}
            onChange={(v) =>
              setDraft({ ...draft, ui: { ...draft.ui, speed_units: v } })
            }
          />
        </Card>

        <Card>
          <CardTitle>OpenSky polling</CardTitle>
          <NumberRow
            label="Update interval (s)"
            value={draft.opensky.update_interval_seconds}
            onChange={(v) =>
              setDraft({
                ...draft,
                opensky: { ...draft.opensky, update_interval_seconds: Math.round(v) },
              })
            }
          />
          <NumberRow
            label="Battery-saver interval (s)"
            value={draft.opensky.battery_saver_interval_seconds}
            onChange={(v) =>
              setDraft({
                ...draft,
                opensky: { ...draft.opensky, battery_saver_interval_seconds: Math.round(v) },
              })
            }
          />
          <NumberRow
            label="Max aircraft age (s)"
            value={draft.opensky.max_aircraft_age_seconds}
            onChange={(v) =>
              setDraft({
                ...draft,
                opensky: { ...draft.opensky, max_aircraft_age_seconds: Math.round(v) },
              })
            }
          />
          <SwitchRow
            label="Include on-ground aircraft"
            value={draft.opensky.include_ground_aircraft}
            onChange={(v) =>
              setDraft({
                ...draft,
                opensky: { ...draft.opensky, include_ground_aircraft: v },
              })
            }
          />
        </Card>

        <Card>
          <CardTitle>Display</CardTitle>
          <PillRow
            label="Default page"
            value={draft.display.default_page}
            options={PAGE_OPTS}
            onChange={(v) =>
              setDraft({
                ...draft,
                display: { ...draft.display, default_page: v },
              })
            }
          />
          <SwitchRow
            label="Partial refresh"
            value={draft.display.partial_refresh}
            onChange={(v) =>
              setDraft({
                ...draft,
                display: { ...draft.display, partial_refresh: v },
              })
            }
          />
          <NumberRow
            label="Full refresh every (cycles)"
            value={draft.display.full_refresh_every}
            onChange={(v) =>
              setDraft({
                ...draft,
                display: { ...draft.display, full_refresh_every: Math.round(v) },
              })
            }
          />
        </Card>

        <Card>
          <CardTitle>Battery thresholds</CardTitle>
          <NumberRow
            label="Low (%)"
            value={draft.battery.low_percent}
            onChange={(v) =>
              setDraft({
                ...draft,
                battery: { ...draft.battery, low_percent: Math.round(v) },
              })
            }
          />
          <NumberRow
            label="Critical (%)"
            value={draft.battery.critical_percent}
            onChange={(v) =>
              setDraft({
                ...draft,
                battery: { ...draft.battery, critical_percent: Math.round(v) },
              })
            }
          />
          <NumberRow
            label="Battery saver below (%)"
            value={draft.battery.battery_saver_below_percent}
            onChange={(v) =>
              setDraft({
                ...draft,
                battery: { ...draft.battery, battery_saver_below_percent: Math.round(v) },
              })
            }
          />
        </Card>

        <Card>
          <CardTitle>Manual location</CardTitle>
          <SwitchRow
            label="Use manual override"
            value={draft.location.manual.enabled}
            onChange={(v) =>
              setDraft({
                ...draft,
                location: {
                  ...draft.location,
                  manual: { ...draft.location.manual, enabled: v },
                },
              })
            }
          />
          <NumberRow
            label="Latitude"
            value={draft.location.manual.lat ?? 0}
            onChange={(v) =>
              setDraft({
                ...draft,
                location: {
                  ...draft.location,
                  manual: { ...draft.location.manual, lat: v },
                },
              })
            }
            disabled={!draft.location.manual.enabled}
          />
          <NumberRow
            label="Longitude"
            value={draft.location.manual.lon ?? 0}
            onChange={(v) =>
              setDraft({
                ...draft,
                location: {
                  ...draft.location,
                  manual: { ...draft.location.manual, lon: v },
                },
              })
            }
            disabled={!draft.location.manual.enabled}
          />
          <TextRow
            label="Label"
            value={draft.location.manual.label ?? ''}
            onChange={(v) =>
              setDraft({
                ...draft,
                location: {
                  ...draft.location,
                  manual: { ...draft.location.manual, label: v },
                },
              })
            }
            disabled={!draft.location.manual.enabled}
          />
        </Card>

        <Card>
          <CardTitle>Pending changes</CardTitle>
          <KeyValue label="Changed fields" value={String(Object.keys(patch).length)} />
          <View style={{ flexDirection: 'row', gap: theme.spacing.sm, marginTop: theme.spacing.sm }}>
            <View style={{ flex: 1 }}>
              <Button title="Revert" onPress={onRevert} disabled={!dirty} />
            </View>
            <View style={{ flex: 1 }}>
              <Button title={saving ? 'Saving…' : 'Save'} onPress={onSave} disabled={!dirty || saving} />
            </View>
          </View>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

function NumberRow({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  disabled?: boolean;
}) {
  const theme = useTheme();
  const [text, setText] = useState(String(value));
  useEffect(() => setText(String(value)), [value]);
  return (
    <View style={styles.row}>
      <Text style={[theme.typography.callout, { color: theme.colors.textSecondary, flex: 1 }]}>
        {label}
      </Text>
      <TextInput
        style={[
          styles.input,
          {
            color: theme.colors.textPrimary,
            backgroundColor: theme.colors.surfaceElevated,
            borderColor: theme.colors.border,
            opacity: disabled ? 0.4 : 1,
          },
        ]}
        editable={!disabled}
        keyboardType="numeric"
        value={text}
        onChangeText={(s) => {
          setText(s);
          const n = parseNumber(s);
          if (n !== null) onChange(n);
        }}
      />
    </View>
  );
}

function TextRow({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  const theme = useTheme();
  return (
    <View style={styles.row}>
      <Text style={[theme.typography.callout, { color: theme.colors.textSecondary, flex: 1 }]}>
        {label}
      </Text>
      <TextInput
        style={[
          styles.input,
          {
            color: theme.colors.textPrimary,
            backgroundColor: theme.colors.surfaceElevated,
            borderColor: theme.colors.border,
            opacity: disabled ? 0.4 : 1,
          },
        ]}
        editable={!disabled}
        value={value}
        onChangeText={onChange}
      />
    </View>
  );
}

function SwitchRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  const theme = useTheme();
  return (
    <View style={[styles.row, { justifyContent: 'space-between' }]}>
      <Text style={[theme.typography.callout, { color: theme.colors.textSecondary }]}>
        {label}
      </Text>
      <Switch value={value} onValueChange={onChange} />
    </View>
  );
}

function PillRow<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: readonly T[];
  onChange: (v: T) => void;
}) {
  const theme = useTheme();
  return (
    <View style={{ gap: theme.spacing.xs }}>
      <Text style={[theme.typography.callout, { color: theme.colors.textSecondary }]}>
        {label}
      </Text>
      <View style={{ flexDirection: 'row', gap: theme.spacing.xs, flexWrap: 'wrap' }}>
        {options.map((opt) => {
          const active = opt === value;
          return (
            <TouchableOpacity
              key={opt}
              onPress={() => onChange(opt)}
              style={[
                styles.pill,
                {
                  backgroundColor: active ? theme.colors.accent : theme.colors.surfaceElevated,
                  borderColor: theme.colors.border,
                },
              ]}
            >
              <Text
                style={[
                  theme.typography.callout,
                  {
                    color: active ? '#fff' : theme.colors.textPrimary,
                    fontWeight: '600',
                  },
                ]}
              >
                {opt}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  input: {
    minWidth: 80,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    textAlign: 'right',
  },
  pill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
  },
});
