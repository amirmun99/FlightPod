/**
 * Thin wrapper over ``expo-secure-store``.
 *
 * SecureStore holds only:
 *  - the paired device (public identity + host/port + clientId + protocol version)
 *  - the session keys (X25519 client private key + the derived session key)
 *  - the outgoing sequence counter
 *
 * Everything else (queues, logs, mock-device flag) lives in zustand.
 *
 * Each value is JSON-encoded before storage. Keys are namespaced
 * ``flightpaper.*`` so other apps + future FlightPaper builds won't
 * stomp each other.
 */

import * as SecureStore from 'expo-secure-store';

import type { PairedDevice, SessionKeys } from '../../types';

const KEYS = {
  paired: 'flightpaper.paired_device',
  session: 'flightpaper.session_keys',
  seqOut: 'flightpaper.seq_out',
} as const;

const SECURE_OPTIONS: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const setItem = (key: string, value: string): Promise<void> =>
  SecureStore.setItemAsync(key, value, SECURE_OPTIONS);

const getItem = (key: string): Promise<string | null> =>
  SecureStore.getItemAsync(key, SECURE_OPTIONS);

const deleteItem = (key: string): Promise<void> =>
  SecureStore.deleteItemAsync(key, SECURE_OPTIONS);


// ---------------------------------------------------------------------------
// Paired device
// ---------------------------------------------------------------------------

export const loadPairedDevice = async (): Promise<PairedDevice | null> => {
  const raw = await getItem(KEYS.paired);
  if (raw === null) return null;
  try {
    return JSON.parse(raw) as PairedDevice;
  } catch {
    // Corrupt slot — drop it so we don't loop on errors.
    await deleteItem(KEYS.paired);
    return null;
  }
};

export const savePairedDevice = async (device: PairedDevice): Promise<void> => {
  await setItem(KEYS.paired, JSON.stringify(device));
};

export const clearPairedDevice = async (): Promise<void> => {
  await deleteItem(KEYS.paired);
  await deleteItem(KEYS.session);
  await deleteItem(KEYS.seqOut);
};


// ---------------------------------------------------------------------------
// Session keys
// ---------------------------------------------------------------------------

export const loadSessionKeys = async (): Promise<SessionKeys | null> => {
  const raw = await getItem(KEYS.session);
  if (raw === null) return null;
  try {
    return JSON.parse(raw) as SessionKeys;
  } catch {
    await deleteItem(KEYS.session);
    return null;
  }
};

export const saveSessionKeys = async (keys: SessionKeys): Promise<void> => {
  await setItem(KEYS.session, JSON.stringify(keys));
};


// ---------------------------------------------------------------------------
// Sequence counter (outgoing)
// ---------------------------------------------------------------------------
//
// We use a SecureStore-backed counter so a process restart doesn't reset
// the seq number — that would re-use values the Pi already accepted and
// the Pi would reject every request as ``replay``.
//
// Concurrent access is exceedingly unlikely (single phone, single
// background task), but we still serialize through a JS promise to
// avoid two simultaneous callers reading the same value.

let _seqMutex: Promise<number> = Promise.resolve(0);

export const claimNextSeqOut = async (): Promise<number> => {
  const next = _seqMutex.then(async () => {
    const raw = await getItem(KEYS.seqOut);
    const current = raw === null ? 0 : Number.parseInt(raw, 10);
    const allocated = Number.isFinite(current) ? current + 1 : 1;
    await setItem(KEYS.seqOut, String(allocated));
    return allocated;
  });
  _seqMutex = next;
  return next;
};

export const resetSeqOut = async (): Promise<void> => {
  _seqMutex = _seqMutex.then(async () => {
    await deleteItem(KEYS.seqOut);
    return 0;
  });
  await _seqMutex;
};


export const SECURE_STORE_KEYS = KEYS;
