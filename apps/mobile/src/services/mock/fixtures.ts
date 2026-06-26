/**
 * Canned data for "mock device mode". The Settings screen and the
 * pairing-fallback both flip this on so the app can be browsed end-to-
 * end without a real Pi nearby.
 *
 * Numbers come from a flight south of SFO at 10:13 local — picked to
 * exercise every status badge (close-overhead aircraft, intermediate,
 * far, on-ground), every battery branch, and a non-empty radar.
 */

import type {
  Aircraft,
  AircraftResponse,
  PairedDevice,
  PiConfigSummary,
  StatusResponse,
} from '../../types';

export const MOCK_DEVICE: PairedDevice = {
  deviceId: 'fp_mock0001',
  name: 'FlightPaper (Mock)',
  host: '127.0.0.1',
  port: 9077,
  clientId: 'iphone_mock00000001',
  protocolVersion: 1,
  pairedAt: 1_750_000_000,
};

export const MOCK_STATUS: StatusResponse = {
  device: {
    id: MOCK_DEVICE.deviceId,
    name: MOCK_DEVICE.name,
    version: '0.1.0-mock',
    uptime_seconds: 9_312,
  },
  network: {
    wifi_ssid: 'iPhone Hotspot',
    ip_address: '172.20.10.4',
    internet_ok: true,
  },
  battery: {
    percent: 82,
    charging: false,
    external_power: false,
    battery_saver: false,
  },
  location: {
    source: 'iphone_foreground',
    age_seconds: 12,
    accuracy_m: 8.4,
    fresh: true,
    state: 'fresh',
  },
  opensky: {
    status: 'ok',
    last_update_age_seconds: 6,
    aircraft_count: 5,
    rate_limit_remaining: 372,
  },
  display: {
    page: 'radar',
    last_refresh_age_seconds: 18,
  },
};

const MOCK_AIRCRAFT_LIST: Aircraft[] = [
  {
    icao24: 'a1b2c3',
    callsign: 'UAL2731',
    origin_country: 'United States',
    longitude: -122.401,
    latitude: 37.62,
    baro_altitude_ft: 14_200,
    geo_altitude_ft: 14_320,
    on_ground: false,
    velocity_kt: 312,
    true_track_deg: 215,
    vertical_rate_fpm: -1_400,
    squawk: '4521',
    distance_km: 6.2,
    bearing_deg: 195,
    age_seconds: 3,
  },
  {
    icao24: 'a4d5e6',
    callsign: 'SWA1499',
    origin_country: 'United States',
    longitude: -122.31,
    latitude: 37.78,
    baro_altitude_ft: 8_300,
    geo_altitude_ft: 8_450,
    on_ground: false,
    velocity_kt: 244,
    true_track_deg: 28,
    vertical_rate_fpm: 1_200,
    squawk: '4731',
    distance_km: 9.8,
    bearing_deg: 32,
    age_seconds: 4,
  },
  {
    icao24: 'c0ffee',
    callsign: 'N812JC',
    origin_country: 'United States',
    longitude: -122.51,
    latitude: 37.55,
    baro_altitude_ft: 2_100,
    geo_altitude_ft: 2_200,
    on_ground: false,
    velocity_kt: 142,
    true_track_deg: 90,
    vertical_rate_fpm: 0,
    squawk: '1200',
    distance_km: 16.4,
    bearing_deg: 248,
    age_seconds: 7,
  },
  {
    icao24: 'beef01',
    callsign: 'ASA12',
    origin_country: 'United States',
    longitude: -122.2,
    latitude: 37.5,
    baro_altitude_ft: 22_800,
    geo_altitude_ft: 23_010,
    on_ground: false,
    velocity_kt: 410,
    true_track_deg: 170,
    vertical_rate_fpm: -800,
    squawk: '4502',
    distance_km: 31.2,
    bearing_deg: 137,
    age_seconds: 9,
  },
  {
    icao24: '7777a1',
    callsign: 'AAL1112',
    origin_country: 'United States',
    longitude: -122.39,
    latitude: 37.61,
    baro_altitude_ft: null,
    geo_altitude_ft: null,
    on_ground: true,
    velocity_kt: 12,
    true_track_deg: 282,
    vertical_rate_fpm: 0,
    squawk: '4502',
    distance_km: 5.1,
    bearing_deg: 188,
    age_seconds: 11,
  },
];

export const MOCK_AIRCRAFT: AircraftResponse = {
  aircraft: MOCK_AIRCRAFT_LIST,
  as_of_seconds: 1_750_000_100,
  count: MOCK_AIRCRAFT_LIST.length,
  radius_km: 40,
};

export const MOCK_CONFIG: PiConfigSummary = {
  ui: {
    radius_km: 40,
    overhead_threshold_km: 3,
    distance_units: 'km',
    altitude_units: 'ft',
    speed_units: 'kt',
  },
  opensky: {
    update_interval_seconds: 30,
    battery_saver_interval_seconds: 120,
    max_aircraft_age_seconds: 90,
    include_ground_aircraft: false,
  },
  display: {
    partial_refresh: true,
    full_refresh_every: 20,
    default_page: 'radar',
  },
  battery: {
    low_percent: 25,
    critical_percent: 10,
    battery_saver_below_percent: 30,
  },
  location: {
    manual: {
      enabled: false,
      lat: null,
      lon: null,
      label: '',
    },
  },
};
