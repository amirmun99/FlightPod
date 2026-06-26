/**
 * Foreground (When-In-Use) and Background (Always) location permissions
 * plus one-shot fix capture.
 *
 * Wraps :mod:`expo-location` so the rest of the app only knows about our
 * own ``LocationFix`` / ``LocationPermissions`` shapes. The iOS
 * permission flow is two-step: When-In-Use first, then upgrade to
 * Always. We never call the background prompt before the foreground
 * prompt — iOS doesn't show it.
 */

import * as Location from 'expo-location';

import type {
  LocationFix,
  LocationPermissions,
  LocationSource,
  PermissionStatus,
} from '../../types';

const mapStatus = (status: Location.PermissionStatus | string): PermissionStatus => {
  if (status === Location.PermissionStatus.GRANTED || status === 'granted') return 'granted';
  if (status === Location.PermissionStatus.DENIED || status === 'denied') return 'denied';
  return 'undetermined';
};

const buildPermissions = (
  foreground: Location.PermissionStatus | string,
  background: Location.PermissionStatus | string,
): LocationPermissions => ({
  foreground: mapStatus(foreground),
  background: mapStatus(background),
});

/** Snapshot the current permission state without prompting the user. */
export const readPermissions = async (): Promise<LocationPermissions> => {
  const fg = await Location.getForegroundPermissionsAsync();
  // iOS won't let us read background unless foreground is already granted —
  // calling it before that point returns ``denied``, which is misleading
  // since the user has never been asked.
  let bg: Location.PermissionResponse | { status: Location.PermissionStatus } = {
    status: Location.PermissionStatus.UNDETERMINED,
  };
  if (fg.status === Location.PermissionStatus.GRANTED) {
    bg = await Location.getBackgroundPermissionsAsync();
  }
  return buildPermissions(fg.status, bg.status);
};

/** Prompt for foreground (When-In-Use) permission. */
export const requestForegroundPermission = async (): Promise<LocationPermissions> => {
  const fg = await Location.requestForegroundPermissionsAsync();
  let bgStatus: Location.PermissionStatus = Location.PermissionStatus.UNDETERMINED;
  if (fg.status === Location.PermissionStatus.GRANTED) {
    // Re-read background without prompting — it may already be granted
    // from a previous session.
    const bg = await Location.getBackgroundPermissionsAsync();
    bgStatus = bg.status;
  }
  return buildPermissions(fg.status, bgStatus);
};

/**
 * Prompt for background (Always) permission. Requires foreground to be
 * granted first — iOS won't show the dialog otherwise.
 */
export const requestBackgroundPermission = async (): Promise<LocationPermissions> => {
  const fg = await Location.getForegroundPermissionsAsync();
  if (fg.status !== Location.PermissionStatus.GRANTED) {
    return buildPermissions(fg.status, Location.PermissionStatus.UNDETERMINED);
  }
  const bg = await Location.requestBackgroundPermissionsAsync();
  return buildPermissions(fg.status, bg.status);
};

/** Convert an :mod:`expo-location` ``LocationObject`` to our ``LocationFix``. */
export const toLocationFix = (
  raw: Location.LocationObject,
  source: LocationSource,
): LocationFix => ({
  lat: raw.coords.latitude,
  lon: raw.coords.longitude,
  accuracyM: raw.coords.accuracy ?? null,
  altitudeM: raw.coords.altitude ?? null,
  headingDeg: raw.coords.heading ?? null,
  speedMps: raw.coords.speed ?? null,
  timestamp: Math.floor(raw.timestamp / 1000),
  source,
});

/** Get a single foreground fix. Throws if permission has not been granted. */
export const getCurrentFix = async (): Promise<LocationFix> => {
  const raw = await Location.getCurrentPositionAsync({
    accuracy: Location.Accuracy.High,
  });
  return toLocationFix(raw, 'iphone_foreground');
};
