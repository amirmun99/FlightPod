/**
 * The currently paired FlightPaper device (or ``null`` if we're unpaired).
 *
 * Only the *public* identity fields live here. Session keys and
 * client private keys live in :mod:`services/storage/secureStore` —
 * those never enter the zustand state.
 *
 * The store also tracks a ``mockDevice`` flag so the rest of the app
 * can be exercised without a real Pi. Set it from the Security screen.
 */

import { create } from 'zustand';

import type { PairedDevice, StatusResponse } from '../../types';

interface DeviceState {
  device: PairedDevice | null;
  mockDevice: boolean;
  lastStatus: StatusResponse | null;
  lastStatusFetchedAt: number | null;
  lastStatusError: string | null;

  setDevice: (device: PairedDevice | null) => void;
  setMockDevice: (mock: boolean) => void;
  setStatus: (status: StatusResponse) => void;
  setStatusError: (error: string | null) => void;
  clear: () => void;
}

export const useDeviceStore = create<DeviceState>((set) => ({
  device: null,
  mockDevice: false,
  lastStatus: null,
  lastStatusFetchedAt: null,
  lastStatusError: null,

  setDevice: (device) =>
    set((s) => ({
      device,
      lastStatusError: null,
      lastSeenAt: device ? Date.now() / 1000 : s.lastStatusFetchedAt,
    })),

  setMockDevice: (mockDevice) => set({ mockDevice }),

  setStatus: (status) =>
    set({
      lastStatus: status,
      lastStatusFetchedAt: Date.now() / 1000,
      lastStatusError: null,
    }),

  setStatusError: (error) => set({ lastStatusError: error }),

  clear: () =>
    set({
      device: null,
      lastStatus: null,
      lastStatusFetchedAt: null,
      lastStatusError: null,
    }),
}));
