/** Aircraft as returned by ``GET /api/secure/aircraft``. Units are display units. */

export type Aircraft = {
  icao24: string;
  callsign: string | null;
  origin_country: string | null;
  longitude: number | null;
  latitude: number | null;
  baro_altitude_ft: number | null;
  geo_altitude_ft: number | null;
  on_ground: boolean;
  velocity_kt: number | null;
  true_track_deg: number | null;
  vertical_rate_fpm: number | null;
  squawk: string | null;
  distance_km: number | null;
  bearing_deg: number | null;
  age_seconds: number | null;
};

export type AircraftResponse = {
  aircraft: Aircraft[];
  as_of_seconds: number | null;
  count: number;
  radius_km: number;
};

export type AircraftSort = 'distance' | 'overhead' | 'altitude';
