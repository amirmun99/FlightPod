/**
 * Phone-side location state — most recent fix, permission status, and
 * the (small, capped) retry queue for failed Pi sends.
 */

import { create } from 'zustand';

import type { LocationFix, LocationPermissions, LocationPayload } from '../../types';

interface LocationState {
  lastFix: LocationFix | null;
  permissions: LocationPermissions;
  // FIFO; spec §8 caps this at 20, keeping only the newest.
  pendingQueue: LocationPayload[];
  backgroundTaskRegistered: boolean;

  setLastFix: (fix: LocationFix | null) => void;
  setPermissions: (perms: LocationPermissions) => void;
  enqueuePending: (payload: LocationPayload, max?: number) => void;
  drainPending: () => LocationPayload[];
  setBackgroundTaskRegistered: (registered: boolean) => void;
  reset: () => void;
}

const DEFAULT_PERMISSIONS: LocationPermissions = {
  foreground: 'undetermined',
  background: 'undetermined',
};

export const useLocationStore = create<LocationState>((set, get) => ({
  lastFix: null,
  permissions: DEFAULT_PERMISSIONS,
  pendingQueue: [],
  backgroundTaskRegistered: false,

  setLastFix: (lastFix) => set({ lastFix }),
  setPermissions: (permissions) => set({ permissions }),

  enqueuePending: (payload, max = 20) =>
    set((s) => {
      const next = [...s.pendingQueue, payload];
      // Keep only the freshest ``max`` items.
      const trimmed = next.length > max ? next.slice(-max) : next;
      return { pendingQueue: trimmed };
    }),

  drainPending: () => {
    const { pendingQueue } = get();
    set({ pendingQueue: [] });
    return pendingQueue;
  },

  setBackgroundTaskRegistered: (backgroundTaskRegistered) =>
    set({ backgroundTaskRegistered }),

  reset: () =>
    set({
      lastFix: null,
      pendingQueue: [],
      backgroundTaskRegistered: false,
      permissions: DEFAULT_PERMISSIONS,
    }),
}));
