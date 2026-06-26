/** Time helpers — agree with the Pi-side ``utils/time_utils.py``. */

export const nowTs = (): number => Math.floor(Date.now() / 1000);

export const ageSeconds = (ts: number | null, now?: number): number | null => {
  if (ts === null) return null;
  const n = now ?? nowTs();
  return Math.max(0, n - ts);
};

export const formatAge = (seconds: number | null): string => {
  if (seconds === null) return '--';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
};
