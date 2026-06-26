/** Lightweight runtime validation for inputs that don't go through Pydantic. */

import type { PairingQrPayload } from '../types';

export const isValidLat = (n: number): boolean => Number.isFinite(n) && n >= -90 && n <= 90;
export const isValidLon = (n: number): boolean => Number.isFinite(n) && n >= -180 && n <= 180;

const DEVICE_ID_RE = /^fp_[0-9a-f]{8}$/;
const B64U_43 = /^[A-Za-z0-9_-]{43}$/;

export const isPairingQrPayload = (value: unknown): value is PairingQrPayload => {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Partial<PairingQrPayload>;
  return (
    v.v === 1 &&
    typeof v.host === 'string' &&
    typeof v.port === 'number' &&
    typeof v.device_id === 'string' &&
    DEVICE_ID_RE.test(v.device_id) &&
    typeof v.device_name === 'string' &&
    typeof v.device_pub === 'string' &&
    B64U_43.test(v.device_pub) &&
    typeof v.pairing_secret === 'string' &&
    B64U_43.test(v.pairing_secret) &&
    typeof v.expires_at === 'number'
  );
};
