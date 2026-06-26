/**
 * High-level RPC layer over the secure-envelope client.
 *
 * Each method wraps :func:`secureRequest` and parameterizes the path +
 * payload + response type. The actual envelope / AAD construction lives
 * in :mod:`services/api/secureEnvelope` and :mod:`services/crypto`.
 */

import type {
  AircraftResponse,
  AircraftSort,
  ConfigPatch,
  DisplayPage,
  LocationPayload,
  PairedDevice,
  PiConfigSummary,
  SessionKeys,
  StatusResponse,
} from '../../types';
import { ApiClient } from './client';
import { ApiEndpoints } from './endpoints';
import { SecureCallContext, secureRequest } from './secureEnvelope';

export interface DeviceClient {
  fetchStatus(): Promise<StatusResponse>;
  fetchAircraft(opts?: { limit?: number; sort?: AircraftSort }): Promise<AircraftResponse>;
  fetchConfig(): Promise<PiConfigSummary>;
  patchConfig(patch: ConfigPatch): Promise<PiConfigSummary>;
  sendLocation(payload: LocationPayload): Promise<{ accepted: boolean; age_seconds: number; received_at: number }>;
  setDisplayPage(page: DisplayPage): Promise<{ ok: boolean; page: DisplayPage }>;
  refreshDevice(): Promise<{ ok: boolean }>;
  shutdown(): Promise<{ ok: boolean; shutdown_in_seconds: number }>;
  reboot(): Promise<{ ok: boolean; reboot_in_seconds: number }>;
  resetPairing(): Promise<{ ok: boolean }>;
}

const QUERY = (path: string, query?: Record<string, string | number | undefined>): string => {
  if (!query) return path;
  const parts: string[] = [];
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined) continue;
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  }
  return parts.length ? `${path}?${parts.join('&')}` : path;
};


export const createDeviceClient = (params: {
  client: ApiClient;
  device: PairedDevice;
  session: SessionKeys;
}): DeviceClient => {
  const ctx: SecureCallContext = {
    client: params.client,
    deviceId: params.device.deviceId,
    clientId: params.device.clientId,
    sessionKey: params.session.sessionKey,
  };

  return {
    fetchStatus: () =>
      secureRequest<Record<string, never>, StatusResponse>(ctx, {
        method: 'GET',
        path: ApiEndpoints.status.path,
        payload: {},
      }),

    fetchAircraft: (opts) =>
      secureRequest<Record<string, never>, AircraftResponse>(ctx, {
        method: 'GET',
        path: QUERY(ApiEndpoints.aircraft.path, opts as Record<string, string | number | undefined>),
        payload: {},
      }),

    fetchConfig: () =>
      secureRequest<Record<string, never>, PiConfigSummary>(ctx, {
        method: 'GET',
        path: ApiEndpoints.getConfig.path,
        payload: {},
      }),

    patchConfig: (patch) =>
      secureRequest<ConfigPatch, PiConfigSummary>(ctx, {
        method: 'PATCH',
        path: ApiEndpoints.patchConfig.path,
        payload: patch,
      }),

    sendLocation: (payload) =>
      secureRequest<LocationPayload, { accepted: boolean; age_seconds: number; received_at: number }>(ctx, {
        method: 'POST',
        path: ApiEndpoints.location.path,
        payload,
      }),

    setDisplayPage: (page) =>
      secureRequest<{ page: DisplayPage }, { ok: boolean; page: DisplayPage }>(ctx, {
        method: 'POST',
        path: ApiEndpoints.displayPage.path,
        payload: { page },
      }),

    refreshDevice: () =>
      secureRequest<Record<string, never>, { ok: boolean }>(ctx, {
        method: 'POST',
        path: ApiEndpoints.refresh.path,
        payload: {},
      }),

    shutdown: () =>
      secureRequest<{ confirm: true }, { ok: boolean; shutdown_in_seconds: number }>(ctx, {
        method: 'POST',
        path: ApiEndpoints.shutdown.path,
        payload: { confirm: true },
      }),

    reboot: () =>
      secureRequest<{ confirm: true }, { ok: boolean; reboot_in_seconds: number }>(ctx, {
        method: 'POST',
        path: ApiEndpoints.reboot.path,
        payload: { confirm: true },
      }),

    resetPairing: () =>
      secureRequest<{ confirm: true }, { ok: boolean }>(ctx, {
        method: 'POST',
        path: ApiEndpoints.resetPairing.path,
        payload: { confirm: true },
      }),
  };
};
