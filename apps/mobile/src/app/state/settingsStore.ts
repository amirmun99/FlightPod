/**
 * App-local preferences. Non-secret. Pi-side config (radius, intervals, etc.)
 * is fetched/PATCHed via the API and reflected separately.
 */

import { create } from 'zustand';

import type { LocationSource } from '../../types';

interface SettingsState {
  // Foreground/background tick cadence. Defaults from spec §8.
  foregroundIntervalSec: number;
  backgroundIntervalSec: number;
  distanceTriggerMeters: number;

  // Whether Live GPS is enabled (i.e. background task should run).
  liveGpsEnabled: boolean;

  // Last successful send / last failure summary.
  lastSendAt: number | null;
  lastSendOutcome: 'ok' | 'queued' | 'failed' | null;
  lastSendReason: string | null;
  lastSendSource: LocationSource | null;

  setLiveGps: (on: boolean) => void;
  setForegroundInterval: (sec: number) => void;
  setBackgroundInterval: (sec: number) => void;
  setDistanceTrigger: (m: number) => void;
  recordSend: (outcome: {
    at: number;
    status: 'ok' | 'queued' | 'failed';
    reason?: string;
    source?: LocationSource;
  }) => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  foregroundIntervalSec: 15,
  backgroundIntervalSec: 45,
  distanceTriggerMeters: 50,

  liveGpsEnabled: false,
  lastSendAt: null,
  lastSendOutcome: null,
  lastSendReason: null,
  lastSendSource: null,

  setLiveGps: (on) => set({ liveGpsEnabled: on }),
  setForegroundInterval: (foregroundIntervalSec) => set({ foregroundIntervalSec }),
  setBackgroundInterval: (backgroundIntervalSec) => set({ backgroundIntervalSec }),
  setDistanceTrigger: (distanceTriggerMeters) => set({ distanceTriggerMeters }),

  recordSend: ({ at, status, reason, source }) =>
    set({
      lastSendAt: at,
      lastSendOutcome: status,
      lastSendReason: reason ?? null,
      lastSendSource: source ?? null,
    }),
}));
