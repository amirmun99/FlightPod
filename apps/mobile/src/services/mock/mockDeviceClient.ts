/**
 * A :class:`DeviceClient` backed by the canned fixtures.
 *
 * Lets us exercise every screen, every PATCH-with-validation path, and
 * every "Live GPS" UI state without a Pi nearby. Selecting "Mock device
 * mode" on the Pairing or Security screen swaps this in transparently.
 *
 * Behavior we intentionally mimic:
 *   - The patch endpoint validates ranges + units before applying.
 *   - Display-page changes round-trip back to the status block.
 *   - Mutations are visible to subsequent fetches in the same session.
 */

import type {
  AircraftResponse,
  AircraftSort,
  ConfigPatch,
  DisplayPage,
  LocationPayload,
  PiConfigSummary,
  StatusResponse,
} from '../../types';
import type { DeviceClient } from '../api/deviceClient';
import {
  MOCK_AIRCRAFT,
  MOCK_CONFIG,
  MOCK_STATUS,
} from './fixtures';

// Hermes (RN 0.74) has no `structuredClone`. These fixtures are all
// JSON-shaped (no Dates, Maps, typed arrays), so a JSON round-trip is a
// correct, dependency-free deep clone.
const deepClone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

// In-process mutable state so PATCHes feel real for the rest of the
// session. Cleared by ``resetMockDevice``.
let config: PiConfigSummary = deepClone(MOCK_CONFIG);
let status: StatusResponse = deepClone(MOCK_STATUS);
let lastLocationReceivedAt: number | null = null;

const wait = (ms: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms));

export const resetMockDevice = (): void => {
  config = deepClone(MOCK_CONFIG);
  status = deepClone(MOCK_STATUS);
  lastLocationReceivedAt = null;
};

const applyPatch = (patch: ConfigPatch): PiConfigSummary => {
  // Mirror :class:`ConfigPatchRequest` on the Pi side — only patch what
  // is in-range; silently drop the rest. The Pi enforces the same.
  const next = deepClone(config);

  if (patch.ui_radius_km !== undefined && patch.ui_radius_km > 0 && patch.ui_radius_km <= 500) {
    next.ui.radius_km = patch.ui_radius_km;
  }
  if (
    patch.ui_overhead_threshold_km !== undefined &&
    patch.ui_overhead_threshold_km > 0 &&
    patch.ui_overhead_threshold_km <= 50
  ) {
    next.ui.overhead_threshold_km = patch.ui_overhead_threshold_km;
  }
  if (patch.ui_distance_units !== undefined) next.ui.distance_units = patch.ui_distance_units;
  if (patch.ui_altitude_units !== undefined) next.ui.altitude_units = patch.ui_altitude_units;
  if (patch.ui_speed_units !== undefined) next.ui.speed_units = patch.ui_speed_units;

  if (
    patch.opensky_update_interval_seconds !== undefined &&
    patch.opensky_update_interval_seconds >= 10 &&
    patch.opensky_update_interval_seconds <= 600
  ) {
    next.opensky.update_interval_seconds = patch.opensky_update_interval_seconds;
  }
  if (
    patch.opensky_battery_saver_interval_seconds !== undefined &&
    patch.opensky_battery_saver_interval_seconds >= 10 &&
    patch.opensky_battery_saver_interval_seconds <= 3600
  ) {
    next.opensky.battery_saver_interval_seconds =
      patch.opensky_battery_saver_interval_seconds;
  }
  if (
    patch.opensky_max_aircraft_age_seconds !== undefined &&
    patch.opensky_max_aircraft_age_seconds >= 10 &&
    patch.opensky_max_aircraft_age_seconds <= 3600
  ) {
    next.opensky.max_aircraft_age_seconds = patch.opensky_max_aircraft_age_seconds;
  }
  if (patch.opensky_include_ground_aircraft !== undefined) {
    next.opensky.include_ground_aircraft = patch.opensky_include_ground_aircraft;
  }

  if (patch.display_partial_refresh !== undefined) {
    next.display.partial_refresh = patch.display_partial_refresh;
  }
  if (
    patch.display_full_refresh_every !== undefined &&
    patch.display_full_refresh_every >= 1 &&
    patch.display_full_refresh_every <= 200
  ) {
    next.display.full_refresh_every = patch.display_full_refresh_every;
  }
  if (patch.display_default_page !== undefined) {
    next.display.default_page = patch.display_default_page;
  }

  if (patch.battery_low_percent !== undefined && between(patch.battery_low_percent, 1, 99)) {
    next.battery.low_percent = patch.battery_low_percent;
  }
  if (
    patch.battery_critical_percent !== undefined &&
    between(patch.battery_critical_percent, 1, 99)
  ) {
    next.battery.critical_percent = patch.battery_critical_percent;
  }
  if (
    patch.battery_battery_saver_below_percent !== undefined &&
    between(patch.battery_battery_saver_below_percent, 1, 99)
  ) {
    next.battery.battery_saver_below_percent = patch.battery_battery_saver_below_percent;
  }

  if (patch.location_manual_enabled !== undefined) {
    next.location.manual.enabled = patch.location_manual_enabled;
  }
  if (patch.location_manual_lat !== undefined && between(patch.location_manual_lat, -90, 90)) {
    next.location.manual.lat = patch.location_manual_lat;
  }
  if (
    patch.location_manual_lon !== undefined &&
    between(patch.location_manual_lon, -180, 180)
  ) {
    next.location.manual.lon = patch.location_manual_lon;
  }
  if (patch.location_manual_label !== undefined) {
    next.location.manual.label = patch.location_manual_label.slice(0, 32);
  }

  config = next;
  return next;
};

const between = (n: number, lo: number, hi: number): boolean => n >= lo && n <= hi;

const cloneStatus = (): StatusResponse => {
  // Age the moving counters so successive fetches feel alive.
  const out = deepClone(status);
  out.device.uptime_seconds += Math.floor(Math.random() * 10);
  out.opensky.last_update_age_seconds =
    Math.floor(Math.random() * config.opensky.update_interval_seconds);
  out.display.last_refresh_age_seconds = Math.floor(Math.random() * 30);
  if (lastLocationReceivedAt !== null) {
    out.location.age_seconds = Math.max(
      0,
      Math.floor(Date.now() / 1000) - lastLocationReceivedAt,
    );
    out.location.fresh = out.location.age_seconds < 60;
    out.location.state = out.location.fresh ? 'fresh' : 'stale';
  }
  return out;
};

const cloneAircraft = (sort?: AircraftSort, limit?: number): AircraftResponse => {
  const out = deepClone(MOCK_AIRCRAFT);
  if (!config.opensky.include_ground_aircraft) {
    out.aircraft = out.aircraft.filter((a) => !a.on_ground);
  }
  out.radius_km = config.ui.radius_km;
  switch (sort) {
    case 'altitude':
      out.aircraft.sort((a, b) => (b.baro_altitude_ft ?? 0) - (a.baro_altitude_ft ?? 0));
      break;
    case 'overhead':
      out.aircraft.sort((a, b) => (a.distance_km ?? 1e6) - (b.distance_km ?? 1e6));
      break;
    case 'distance':
    default:
      out.aircraft.sort((a, b) => (a.distance_km ?? 1e6) - (b.distance_km ?? 1e6));
  }
  if (limit !== undefined) out.aircraft = out.aircraft.slice(0, limit);
  out.count = out.aircraft.length;
  return out;
};

export const createMockDeviceClient = (): DeviceClient => ({
  fetchStatus: async () => {
    await wait(120);
    return cloneStatus();
  },
  fetchAircraft: async (opts) => {
    await wait(150);
    return cloneAircraft(opts?.sort, opts?.limit);
  },
  fetchConfig: async () => {
    await wait(100);
    return deepClone(config);
  },
  patchConfig: async (patch) => {
    await wait(180);
    return applyPatch(patch);
  },
  sendLocation: async (payload: LocationPayload) => {
    await wait(80);
    lastLocationReceivedAt = payload.timestamp;
    return { accepted: true, age_seconds: 0, received_at: payload.timestamp };
  },
  setDisplayPage: async (page: DisplayPage) => {
    await wait(60);
    status.display.page = page;
    return { ok: true, page };
  },
  refreshDevice: async () => {
    await wait(80);
    status.display.last_refresh_age_seconds = 0;
    return { ok: true };
  },
  shutdown: async () => {
    await wait(50);
    return { ok: true, shutdown_in_seconds: 30 };
  },
  reboot: async () => {
    await wait(50);
    return { ok: true, reboot_in_seconds: 30 };
  },
  resetPairing: async () => {
    await wait(60);
    return { ok: true };
  },
});
