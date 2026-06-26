/**
 * Symmetric-pairing-key handshake against ``POST /api/public/pair``.
 *
 * Mirrors ``apps/pi/flightpaper/api/routes_public.py``. We:
 *   1. Derive ``pairing_key`` from the QR's ``pairing_secret`` + device id
 *      + device pub.
 *   2. Generate (or reuse) a client X25519 keypair.
 *   3. Build the ``PairRequestBody`` with ``client_pub``, encrypt it under
 *      ``pairing_key`` with key_id="pairing".
 *   4. POST the envelope.
 *   5. Decrypt the response envelope under the same ``pairing_key`` (still
 *      valid until the server burns the secret).
 *   6. Derive the long-term ``session_key`` via ECDH + HKDF.
 *   7. Save (PairedDevice, SessionKeys) to SecureStore.
 *
 * The resulting :class:`PairedDevice` carries ``host``, ``port``, and
 * ``clientId`` so subsequent secure requests can be wired up immediately.
 */

import { b64uDecode, b64uEncode, utf8Decode, utf8Encode } from '../crypto/base64u';
import { openEnvelopeBytes, sealEnvelopeBytes } from '../crypto/envelope';
import {
  derivePairingKey,
  deriveSessionKey,
  generateClientKeyPair,
  x25519SharedSecret,
} from '../crypto/keys';
import { randomBytes } from '../crypto/random';
import {
  resetSeqOut,
  savePairedDevice,
  saveSessionKeys,
} from '../storage/secureStore';
import { nowTs } from '../../utils/time';
import type {
  PairRequestBody,
  PairResponseBody,
  PairedDevice,
  PairingQrPayload,
  SecureEnvelope,
  SessionKeys,
} from '../../types';
import { ApiClient, ApiError, createApiClient } from './client';

const PAIR_PATH = '/api/public/pair';

/** Build a ``iphone_<12 hex>`` client id. Used when the app first launches. */
export const newClientId = (): string => {
  const bytes = randomBytes(6);
  let hex = '';
  for (let i = 0; i < bytes.length; i++) {
    hex += bytes[i]!.toString(16).padStart(2, '0');
  }
  return `iphone_${hex}`;
};

export const baseUrlFromQr = (qr: PairingQrPayload): string =>
  `http://${qr.host}:${qr.port}`;

export interface CompletePairingOptions {
  appInstanceName?: string;
  clientId?: string;
  fetchImpl?: typeof fetch;
  /** Override the API client (mostly for tests). */
  client?: ApiClient;
  /** Skip SecureStore writes — only the smoke tests use this. */
  persist?: boolean;
}

export interface CompletePairingResult {
  device: PairedDevice;
  session: SessionKeys;
}

export const completePairing = async (
  qr: PairingQrPayload,
  options: CompletePairingOptions = {},
): Promise<CompletePairingResult> => {
  const clientId = options.clientId ?? newClientId();
  const persist = options.persist ?? true;

  const pairingSecretBytes = b64uDecode(qr.pairing_secret);
  const devicePubBytes = b64uDecode(qr.device_pub);

  // --- Derive symmetric pairing key ------------------------------------
  const pairingKey = derivePairingKey({
    pairingSecret: pairingSecretBytes,
    deviceId: qr.device_id,
    devicePublicKey: devicePubBytes,
  });

  // --- Generate phone keypair + assemble request body ------------------
  const phoneKp = generateClientKeyPair();
  const phonePrivBytes = b64uDecode(phoneKp.privateKey);

  const requestBody: PairRequestBody = {
    client_pub: phoneKp.publicKey,
    app_instance_name: options.appInstanceName ?? 'FlightPaper iPhone',
    protocol_version: 1,
  };

  const ts = nowTs();
  const envelope = sealEnvelopeBytes(
    pairingKey,
    utf8Encode(JSON.stringify(requestBody)),
    {
      method: 'POST',
      path: PAIR_PATH,
      deviceId: qr.device_id,
      clientId,
      keyId: 'pairing',
      seq: 0,
      ts,
    },
  );

  // --- POST to Pi -------------------------------------------------------
  const client = options.client ?? createApiClient(baseUrlFromQr(qr), {
    fetchImpl: options.fetchImpl,
  });
  let response;
  try {
    response = await client.request<SecureEnvelope>({
      method: 'POST',
      path: PAIR_PATH,
      body: envelope,
    });
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(
      0,
      'network_error',
      err instanceof Error ? err.message : 'unknown',
    );
  }

  // --- Decrypt response under the pairing key --------------------------
  const responseEnvelope = response.body;
  const responsePlaintext = openEnvelopeBytes(pairingKey, responseEnvelope, {
    method: 'RES',
    path: PAIR_PATH,
    deviceId: qr.device_id,
    clientId,
    keyId: 'pairing',
    seq: responseEnvelope.seq,
    ts: responseEnvelope.ts,
  });
  const responseBody = JSON.parse(utf8Decode(responsePlaintext)) as PairResponseBody;
  if (!responseBody.ok || responseBody.device_id !== qr.device_id || responseBody.client_id !== clientId) {
    throw new ApiError(0, 'pair_mismatch', 'response identity did not match request');
  }

  // --- Derive long-term session key (ECDH + HKDF) ----------------------
  const shared = x25519SharedSecret(phonePrivBytes, devicePubBytes);
  const sessionKeyBytes = deriveSessionKey({
    sharedSecret: shared,
    pairingSecret: pairingSecretBytes,
    deviceId: qr.device_id,
    clientId,
  });

  const session: SessionKeys = {
    clientPrivKey: phoneKp.privateKey,
    clientPubKey: phoneKp.publicKey,
    sessionKey: b64uEncode(sessionKeyBytes),
  };

  const device: PairedDevice = {
    deviceId: qr.device_id,
    name: qr.device_name,
    host: qr.host,
    port: qr.port,
    clientId,
    protocolVersion: qr.v,
    pairedAt: responseBody.paired_at,
  };

  // --- Persist + reset seq counter -------------------------------------
  if (persist) {
    await resetSeqOut();
    await savePairedDevice(device);
    await saveSessionKeys(session);
  }

  return { device, session };
};
