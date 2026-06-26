/**
 * Phone-side location types. ``LocationFix`` mirrors what we get from
 * ``expo-location``; ``LocationPayload`` matches the wire shape sent to
 * ``/api/secure/location`` (see ``apps/pi/flightpaper/api/schemas.py``).
 */

export type LocationSource = 'iphone_foreground' | 'iphone_background';

export interface LocationFix {
  lat: number;
  lon: number;
  accuracyM: number | null;
  altitudeM: number | null;
  headingDeg: number | null;
  speedMps: number | null;
  timestamp: number; // unix seconds
  source: LocationSource;
}

export interface LocationPayload {
  lat: number;
  lon: number;
  accuracy_m?: number | null;
  altitude_m?: number | null;
  heading_deg?: number | null;
  speed_mps?: number | null;
  source: LocationSource;
  timestamp: number;
}

export type PermissionStatus = 'undetermined' | 'denied' | 'granted';

export interface LocationPermissions {
  foreground: PermissionStatus;
  background: PermissionStatus;
}

export interface LocationSendOutcome {
  status: 'ok' | 'queued' | 'failed';
  attemptedAt: number;
  reason?: string;
}
