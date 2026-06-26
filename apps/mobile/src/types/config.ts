/**
 * Subset of the Pi config we surface in the Settings screen. The full
 * config dump is much larger; we only enumerate keys the app can patch
 * (see ``ConfigPatchRequest`` in ``apps/pi/flightpaper/api/schemas.py``).
 */

export type DistanceUnits = 'km' | 'nm';
export type AltitudeUnits = 'ft' | 'm';
export type SpeedUnits = 'kt' | 'mps' | 'kmh';
export type DisplayPage = 'radar' | 'closest' | 'list' | 'status';

export interface PiConfigSummary {
  ui: {
    radius_km: number;
    overhead_threshold_km: number;
    distance_units: DistanceUnits;
    altitude_units: AltitudeUnits;
    speed_units: SpeedUnits;
  };
  opensky: {
    update_interval_seconds: number;
    battery_saver_interval_seconds: number;
    max_aircraft_age_seconds: number;
    include_ground_aircraft: boolean;
  };
  display: {
    partial_refresh: boolean;
    full_refresh_every: number;
    default_page: DisplayPage;
  };
  battery: {
    low_percent: number;
    critical_percent: number;
    battery_saver_below_percent: number;
  };
  location: {
    manual: {
      enabled: boolean;
      lat: number | null;
      lon: number | null;
      label: string;
    };
  };
}

/** Flat shape PATCHed to ``/api/secure/config``. */
export interface ConfigPatch {
  ui_radius_km?: number;
  ui_overhead_threshold_km?: number;
  ui_distance_units?: DistanceUnits;
  ui_altitude_units?: AltitudeUnits;
  ui_speed_units?: SpeedUnits;
  opensky_update_interval_seconds?: number;
  opensky_battery_saver_interval_seconds?: number;
  opensky_max_aircraft_age_seconds?: number;
  opensky_include_ground_aircraft?: boolean;
  display_partial_refresh?: boolean;
  display_full_refresh_every?: number;
  display_default_page?: DisplayPage;
  location_manual_enabled?: boolean;
  location_manual_lat?: number;
  location_manual_lon?: number;
  location_manual_label?: string;
  battery_low_percent?: number;
  battery_critical_percent?: number;
  battery_battery_saver_below_percent?: number;
}
