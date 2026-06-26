/**
 * Cryptographic randomness via ``@stablelib/random``.
 *
 * On React Native, ``crypto.getRandomValues`` is provided by the
 * ``react-native-get-random-values`` polyfill, which we import at the
 * App entry point so the global is set before any crypto runs.
 */

import { randomBytes as stablelibRandom } from '@stablelib/random';

import { b64uEncode } from './base64u';

export const randomBytes = (n: number): Uint8Array => {
  if (!Number.isInteger(n) || n < 1) {
    throw new Error('randomBytes: n must be a positive integer');
  }
  return stablelibRandom(n);
};

/** 24-byte XChaCha20-Poly1305 nonce, base64url. */
export const randomNonceB64u = (): string => b64uEncode(randomBytes(24));
