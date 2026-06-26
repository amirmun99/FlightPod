/**
 * Returns the appropriate :class:`DeviceClient` for the current
 * pairing state.
 *
 *   - Mock device mode → :func:`createMockDeviceClient`.
 *   - Real paired device + session in SecureStore → real client over
 *     the secure envelope.
 *   - Otherwise → ``null``; the caller renders an "unpaired" hint.
 *
 * The hook only memoizes on device identity + a session-key cache key
 * so a re-render doesn't churn the underlying ``ApiClient``.
 */

import { useEffect, useMemo, useState } from 'react';

import { useDeviceStore } from '../app/state';
import { createApiClient } from '../services/api/client';
import {
  createDeviceClient,
  type DeviceClient,
} from '../services/api/deviceClient';
import { createMockDeviceClient } from '../services/mock/mockDeviceClient';
import { loadSessionKeys } from '../services/storage/secureStore';
import type { PairedDevice, SessionKeys } from '../types';

export interface DeviceClientHandle {
  client: DeviceClient | null;
  device: PairedDevice | null;
  isMock: boolean;
  ready: boolean;
}

const buildRealClient = (
  device: PairedDevice,
  session: SessionKeys,
): DeviceClient => {
  const apiClient = createApiClient(`http://${device.host}:${device.port}`);
  return createDeviceClient({ client: apiClient, device, session });
};

export const useDeviceClient = (): DeviceClientHandle => {
  const device = useDeviceStore((s) => s.device);
  const mockDevice = useDeviceStore((s) => s.mockDevice);
  const [session, setSession] = useState<SessionKeys | null>(null);
  const [sessionLoaded, setSessionLoaded] = useState<boolean>(false);

  // Hydrate session key from SecureStore whenever the paired device id
  // changes (also covers the post-pair handoff).
  useEffect(() => {
    if (device === null) {
      setSession(null);
      setSessionLoaded(true);
      return;
    }
    let cancelled = false;
    setSessionLoaded(false);
    (async () => {
      try {
        const s = await loadSessionKeys();
        if (!cancelled) {
          setSession(s);
          setSessionLoaded(true);
        }
      } catch {
        if (!cancelled) {
          setSession(null);
          setSessionLoaded(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [device]);

  return useMemo<DeviceClientHandle>(() => {
    if (mockDevice) {
      return {
        client: createMockDeviceClient(),
        device: null,
        isMock: true,
        ready: true,
      };
    }
    if (device !== null && session !== null) {
      return {
        client: buildRealClient(device, session),
        device,
        isMock: false,
        ready: true,
      };
    }
    return {
      client: null,
      device,
      isMock: false,
      ready: sessionLoaded,
    };
  }, [device, session, sessionLoaded, mockDevice]);
};
