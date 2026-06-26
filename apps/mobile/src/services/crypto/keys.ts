/**
 * X25519 keypair generation, HKDF-SHA256, and the two FlightPaper key
 * derivation functions. Mirrors ``apps/pi/flightpaper/security/crypto.py``
 * — both sides MUST agree byte-for-byte.
 *
 * Why ``@stablelib`` rather than ``tweetnacl``:
 *  - tweetnacl gives us X25519 but not XChaCha20-Poly1305.
 *  - stablelib is modular, audited, and pure JS so it works in Expo Go
 *    and dev clients alike.
 */

import { hash as sha256 } from '@stablelib/sha256';
import { generateKeyPair as x25519KeyPair, sharedKey as x25519SharedKey } from '@stablelib/x25519';

import { b64uDecode, b64uEncode, utf8Encode } from './base64u';

export const AEAD_KEY_BYTES = 32;
export const AEAD_NONCE_BYTES = 24;
export const PAIRING_SECRET_BYTES = 32;

const HKDF_PAIR_INFO = utf8Encode('flightpaper/pair/v1');
const HKDF_SESSION_INFO_PREFIX = utf8Encode('flightpaper/session/v1|');


// ---------------------------------------------------------------------------
// HMAC-SHA256 (used by HKDF)
// ---------------------------------------------------------------------------

const BLOCK_SIZE = 64;

const concat = (...chunks: Uint8Array[]): Uint8Array => {
  let len = 0;
  for (const c of chunks) len += c.length;
  const out = new Uint8Array(len);
  let off = 0;
  for (const c of chunks) {
    out.set(c, off);
    off += c.length;
  }
  return out;
};

const hmacSha256 = (key: Uint8Array, message: Uint8Array): Uint8Array => {
  let blockKey: Uint8Array;
  if (key.length > BLOCK_SIZE) {
    blockKey = new Uint8Array(BLOCK_SIZE);
    blockKey.set(sha256(key));
  } else {
    blockKey = new Uint8Array(BLOCK_SIZE);
    blockKey.set(key);
  }

  const inner = new Uint8Array(BLOCK_SIZE);
  const outer = new Uint8Array(BLOCK_SIZE);
  for (let i = 0; i < BLOCK_SIZE; i++) {
    inner[i] = blockKey[i]! ^ 0x36;
    outer[i] = blockKey[i]! ^ 0x5c;
  }

  const innerHash = sha256(concat(inner, message));
  return sha256(concat(outer, innerHash));
};


// ---------------------------------------------------------------------------
// HKDF-SHA256 (RFC 5869)
// ---------------------------------------------------------------------------

export const hkdfSha256 = (
  params: { ikm: Uint8Array; salt: Uint8Array; info: Uint8Array; length?: number },
): Uint8Array => {
  const length = params.length ?? AEAD_KEY_BYTES;
  if (length <= 0 || length > 255 * 32) {
    throw new Error('HKDF length out of range');
  }
  const salt = params.salt.length > 0 ? params.salt : new Uint8Array(32);
  const prk = hmacSha256(salt, params.ikm);

  const okm = new Uint8Array(length);
  let t = new Uint8Array(0);
  let written = 0;
  let counter = 1;
  while (written < length) {
    t = hmacSha256(prk, concat(t, params.info, new Uint8Array([counter])));
    const remaining = Math.min(t.length, length - written);
    okm.set(t.subarray(0, remaining), written);
    written += remaining;
    counter += 1;
  }
  return okm;
};


// ---------------------------------------------------------------------------
// X25519
// ---------------------------------------------------------------------------

export interface ClientKeyPair {
  publicKey: string; // base64url
  privateKey: string; // base64url
}

export const generateClientKeyPair = (): ClientKeyPair => {
  // stablelib pulls entropy from globalThis.crypto.getRandomValues, which the
  // ``react-native-get-random-values`` polyfill (imported in App.tsx) provides
  // on React Native. Under Node (Jest) it's built in to ``globalThis.crypto``.
  const kp = x25519KeyPair();
  return {
    publicKey: b64uEncode(kp.publicKey),
    privateKey: b64uEncode(kp.secretKey),
  };
};

const requireBytes = (name: string, b: Uint8Array, expected: number): void => {
  if (b.length !== expected) {
    throw new Error(`${name} must be ${expected} bytes (got ${b.length})`);
  }
};

export const x25519SharedSecret = (
  privateKey: Uint8Array,
  peerPublicKey: Uint8Array,
): Uint8Array => {
  requireBytes('private_key', privateKey, 32);
  requireBytes('peer_public_key', peerPublicKey, 32);
  return x25519SharedKey(privateKey, peerPublicKey);
};


// ---------------------------------------------------------------------------
// FlightPaper key derivation
// ---------------------------------------------------------------------------

/**
 * Derive the symmetric pairing-handshake AEAD key.
 *
 * Matches ``flightpaper.security.crypto.derive_pairing_key`` byte-for-byte:
 *   salt = utf8(device_id) || "|" || device_public_key
 *   info = "flightpaper/pair/v1"
 *   ikm  = pairing_secret
 */
export const derivePairingKey = (params: {
  pairingSecret: Uint8Array;
  deviceId: string;
  devicePublicKey: Uint8Array;
}): Uint8Array => {
  requireBytes('device_public_key', params.devicePublicKey, 32);
  const salt = concat(utf8Encode(params.deviceId), utf8Encode('|'), params.devicePublicKey);
  return hkdfSha256({
    ikm: params.pairingSecret,
    salt,
    info: HKDF_PAIR_INFO,
    length: AEAD_KEY_BYTES,
  });
};


/**
 * Derive the long-term session AEAD key.
 *
 * Matches ``flightpaper.security.crypto.derive_session_key``:
 *   salt = pairing_secret
 *   info = "flightpaper/session/v1|" || device_id || "|" || client_id
 *   ikm  = shared_secret  (X25519(client_priv, device_pub))
 */
export const deriveSessionKey = (params: {
  sharedSecret: Uint8Array;
  pairingSecret: Uint8Array;
  deviceId: string;
  clientId: string;
}): Uint8Array => {
  const info = concat(
    HKDF_SESSION_INFO_PREFIX,
    utf8Encode(params.deviceId),
    utf8Encode('|'),
    utf8Encode(params.clientId),
  );
  return hkdfSha256({
    ikm: params.sharedSecret,
    salt: params.pairingSecret,
    info,
    length: AEAD_KEY_BYTES,
  });
};


/**
 * High-level helper for the pairing flow: takes the inputs the phone has
 * after scanning the QR (and just-generated client keypair) and returns
 * everything the SecureStore needs to persist.
 */
export const deriveAllKeysForPairing = (params: {
  pairingSecret: string;
  devicePub: string;
  deviceId: string;
  clientId: string;
  clientPriv: string;
}): {
  pairingKey: Uint8Array;
  sessionKey: Uint8Array;
} => {
  const pairingSecret = b64uDecode(params.pairingSecret);
  const devicePub = b64uDecode(params.devicePub);
  const clientPriv = b64uDecode(params.clientPriv);

  const pairingKey = derivePairingKey({
    pairingSecret,
    deviceId: params.deviceId,
    devicePublicKey: devicePub,
  });

  const shared = x25519SharedSecret(clientPriv, devicePub);
  const sessionKey = deriveSessionKey({
    sharedSecret: shared,
    pairingSecret,
    deviceId: params.deviceId,
    clientId: params.clientId,
  });

  return { pairingKey, sessionKey };
};
