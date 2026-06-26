/** Mirrors a subset of ``apps/pi/flightpaper/utils/geo.py`` for radar drawing. */

const CARDINALS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'] as const;

export const cardinalDirection = (bearingDeg: number): string => {
  const normalized = ((bearingDeg % 360) + 360) % 360;
  const idx = Math.floor((normalized + 22.5) / 45) % 8;
  return CARDINALS[idx]!;
};
