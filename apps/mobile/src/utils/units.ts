/** Unit conversions used by the display layer of the app. */

const METERS_PER_FOOT = 0.3048;
const METERS_PER_NM = 1852.0;
const KNOTS_PER_MPS = 1.9438444924406046;

export const metersToFeet = (m: number | null): number | null =>
  m === null ? null : m / METERS_PER_FOOT;

export const mpsToKnots = (mps: number | null): number | null =>
  mps === null ? null : mps * KNOTS_PER_MPS;

export const kmToNm = (km: number | null): number | null =>
  km === null ? null : (km * 1000) / METERS_PER_NM;
