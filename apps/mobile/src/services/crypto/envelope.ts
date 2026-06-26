/**
 * Build / open FlightPaper secure envelopes on the phone side.
 *
 * The AAD layout MUST match ``packages/protocol/protocol.md`` §4.2 and
 * ``apps/pi/flightpaper/api/secure_envelope.py::build_aad`` byte-for-byte:
 *
 *   v=<v>|m=<METHOD>|p=<path>|d=<device_id>|c=<client_id>|k=<key_id>|s=<seq>|t=<ts>
 */

import { XChaCha20Poly1305 } from '@stablelib/xchacha20poly1305';

import type { SecureEnvelope } from '../../types';
import { b64uDecode, b64uEncode, utf8Decode, utf8Encode } from './base64u';
import { AEAD_KEY_BYTES, AEAD_NONCE_BYTES } from './keys';
import { randomBytes } from './random';

export const ENVELOPE_VERSION = 1;
export const RESPONSE_METHOD = 'RES' as const;

export interface EnvelopeContext {
  method: 'GET' | 'POST' | 'PATCH' | typeof RESPONSE_METHOD;
  path: string;
  deviceId: string;
  clientId: string;
  keyId: 'pairing' | 'main';
  seq: number;
  ts: number;
  v?: number;
}

export class DecryptionError extends Error {}


// ---------------------------------------------------------------------------
// AAD
// ---------------------------------------------------------------------------

export const buildAad = (ctx: EnvelopeContext): Uint8Array => {
  const parts = [
    `v=${ctx.v ?? ENVELOPE_VERSION}`,
    `m=${ctx.method}`,
    `p=${ctx.path}`,
    `d=${ctx.deviceId}`,
    `c=${ctx.clientId}`,
    `k=${ctx.keyId}`,
    `s=${ctx.seq}`,
    `t=${ctx.ts}`,
  ];
  return utf8Encode(parts.join('|'));
};


// ---------------------------------------------------------------------------
// Seal / open
// ---------------------------------------------------------------------------

const requireKey = (key: Uint8Array): void => {
  if (key.length !== AEAD_KEY_BYTES) {
    throw new Error(`session key must be ${AEAD_KEY_BYTES} bytes (got ${key.length})`);
  }
};

export const sealEnvelopeBytes = (
  key: Uint8Array,
  plaintext: Uint8Array,
  ctx: EnvelopeContext,
  nonceOverride?: Uint8Array,
): SecureEnvelope => {
  requireKey(key);
  const nonce = nonceOverride ?? randomBytes(AEAD_NONCE_BYTES);
  if (nonce.length !== AEAD_NONCE_BYTES) {
    throw new Error('nonce length invalid');
  }
  const aead = new XChaCha20Poly1305(key);
  const aad = buildAad(ctx);
  const ciphertext = aead.seal(nonce, plaintext, aad);
  return {
    v: (ctx.v ?? ENVELOPE_VERSION) as 1,
    device_id: ctx.deviceId,
    client_id: ctx.clientId,
    key_id: ctx.keyId,
    seq: ctx.seq,
    ts: ctx.ts,
    nonce: b64uEncode(nonce),
    ciphertext: b64uEncode(ciphertext),
  };
};

export const sealEnvelopeJson = <T>(
  key: Uint8Array,
  payload: T,
  ctx: EnvelopeContext,
): SecureEnvelope => {
  return sealEnvelopeBytes(key, utf8Encode(JSON.stringify(payload)), ctx);
};

export const openEnvelopeBytes = (
  key: Uint8Array,
  envelope: SecureEnvelope,
  ctx: EnvelopeContext,
): Uint8Array => {
  requireKey(key);
  if (envelope.v !== ENVELOPE_VERSION) {
    throw new DecryptionError('unsupported envelope version');
  }
  const nonce = b64uDecode(envelope.nonce);
  const ciphertext = b64uDecode(envelope.ciphertext);
  if (nonce.length !== AEAD_NONCE_BYTES) {
    throw new DecryptionError('nonce length invalid');
  }
  const aead = new XChaCha20Poly1305(key);
  const aad = buildAad(ctx);
  const plaintext = aead.open(nonce, ciphertext, aad);
  if (plaintext === null) {
    throw new DecryptionError('AEAD verification failed');
  }
  return plaintext;
};

export const openEnvelopeJson = <T>(
  key: Uint8Array,
  envelope: SecureEnvelope,
  ctx: EnvelopeContext,
): T => {
  const plaintext = openEnvelopeBytes(key, envelope, ctx);
  return JSON.parse(utf8Decode(plaintext)) as T;
};
