/**
 * Pi-bound location delivery.
 *
 * - Builds a wire :class:`LocationPayload` from a :class:`LocationFix`.
 * - Posts via the secure-envelope client to ``/api/secure/location``.
 * - On failure, pushes the payload onto the location-store retry queue
 *   (capped at 20 items, newest-wins) so a future foreground tick can
 *   flush it.
 *
 * This module is the only place that knows the conversion from
 * ``LocationFix`` → ``LocationPayload``; the background task and the
 * foreground "Send Now" button share it.
 */

import { createApiClient } from '../api/client';
import { createDeviceClient } from '../api/deviceClient';
import { loadPairedDevice, loadSessionKeys } from '../storage/secureStore';
import { logEvent } from '../../app/state/logStore';
import { useLocationStore } from '../../app/state/locationStore';
import { nowTs } from '../../utils/time';
import type {
  LocationFix,
  LocationPayload,
  LocationSendOutcome,
  PairedDevice,
  SessionKeys,
} from '../../types';

export const MAX_RETRY_QUEUE = 20;

// CoreLocation reports ``-1`` (or other negative values) when heading /
// speed / accuracy aren't currently valid. The Pi rejects those — its
// schema requires ``heading_deg`` strictly in ``[0, 360)`` and the rest
// non-negative — so drop them to ``null`` before sending.
const cleanHeading = (h: number | null): number | null =>
  h === null || !Number.isFinite(h) || h < 0 || h >= 360 ? null : h;

const cleanNonNegative = (v: number | null): number | null =>
  v === null || !Number.isFinite(v) || v < 0 ? null : v;

/** Translate the phone-shaped fix to the snake_case wire payload. */
export const fixToPayload = (fix: LocationFix): LocationPayload => ({
  lat: fix.lat,
  lon: fix.lon,
  accuracy_m: cleanNonNegative(fix.accuracyM),
  altitude_m: fix.altitudeM,
  heading_deg: cleanHeading(fix.headingDeg),
  speed_mps: cleanNonNegative(fix.speedMps),
  source: fix.source,
  timestamp: fix.timestamp,
});

interface SendCtx {
  device: PairedDevice;
  session: SessionKeys;
}

const loadCtx = async (): Promise<SendCtx | null> => {
  const [device, session] = await Promise.all([
    loadPairedDevice(),
    loadSessionKeys(),
  ]);
  if (!device || !session) return null;
  return { device, session };
};

const baseUrlFor = (device: PairedDevice): string =>
  `http://${device.host}:${device.port}`;

const doPost = async (ctx: SendCtx, payload: LocationPayload): Promise<void> => {
  const client = createApiClient(baseUrlFor(ctx.device));
  const deviceClient = createDeviceClient({
    client,
    device: ctx.device,
    session: ctx.session,
  });
  await deviceClient.sendLocation(payload);
};

/**
 * Send a single fix. If the network or Pi rejects it, queue the payload
 * so a later flush can retry. The :class:`LocationSendOutcome` reflects
 * what happened from the caller's POV.
 */
export const sendLocationToPi = async (
  fix: LocationFix,
): Promise<LocationSendOutcome> => {
  const payload = fixToPayload(fix);
  const attemptedAt = nowTs();

  const ctx = await loadCtx();
  if (!ctx) {
    // No paired device — drop on the floor; the screen is the right
    // place to surface "not paired" rather than the queue.
    return { status: 'failed', attemptedAt, reason: 'not_paired' };
  }

  try {
    await doPost(ctx, payload);
    useLocationStore.getState().setLastFix(fix);
    return { status: 'ok', attemptedAt };
  } catch (err) {
    const reason = err instanceof Error ? err.message : 'unknown error';
    useLocationStore.getState().enqueuePending(payload, MAX_RETRY_QUEUE);
    logEvent('warn', `location send failed: ${reason}`, 'location');
    return { status: 'queued', attemptedAt, reason };
  }
};

/**
 * Drain the in-memory retry queue and re-send each item in FIFO order.
 * Returns the number of payloads that were successfully delivered.
 *
 * On the first failure we stop and re-enqueue every remaining item so
 * we don't busy-loop while offline.
 */
export const flushLocationQueue = async (): Promise<number> => {
  const store = useLocationStore.getState();
  const queue = store.drainPending();
  if (queue.length === 0) return 0;

  const ctx = await loadCtx();
  if (!ctx) {
    // Put the queue back so it isn't lost; we never reach the Pi.
    for (const item of queue) {
      store.enqueuePending(item, MAX_RETRY_QUEUE);
    }
    return 0;
  }

  let delivered = 0;
  for (let i = 0; i < queue.length; i++) {
    const payload = queue[i]!;
    try {
      await doPost(ctx, payload);
      delivered += 1;
    } catch {
      // Re-enqueue this item + every remaining one and stop.
      for (let j = i; j < queue.length; j++) {
        store.enqueuePending(queue[j]!, MAX_RETRY_QUEUE);
      }
      break;
    }
  }
  return delivered;
};
