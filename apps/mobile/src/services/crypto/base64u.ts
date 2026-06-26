/**
 * Base64url encode/decode for Uint8Array. RFC 7515 — no padding on output,
 * tolerant of padding on input.
 *
 * Implemented inline so we don't depend on ``btoa``/``atob`` (which aren't
 * universally available on RN) or pull a 30 KB base64 library.
 */

import { decode as utf8DecodeBytes, encode as utf8EncodeBytes } from '@stablelib/utf8';

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';

const decodeTable = ((): Int8Array => {
  const t = new Int8Array(256).fill(-1);
  for (let i = 0; i < ALPHABET.length; i++) {
    t[ALPHABET.charCodeAt(i)] = i;
  }
  // Tolerate standard base64 too.
  t['+'.charCodeAt(0)] = 62;
  t['/'.charCodeAt(0)] = 63;
  return t;
})();

export const b64uEncode = (data: Uint8Array): string => {
  let out = '';
  const len = data.length;
  let i = 0;
  for (; i + 3 <= len; i += 3) {
    const a = data[i]!;
    const b = data[i + 1]!;
    const c = data[i + 2]!;
    out += ALPHABET[a >> 2]!;
    out += ALPHABET[((a & 0x03) << 4) | (b >> 4)]!;
    out += ALPHABET[((b & 0x0f) << 2) | (c >> 6)]!;
    out += ALPHABET[c & 0x3f]!;
  }
  if (i < len) {
    const a = data[i]!;
    if (i + 1 === len) {
      out += ALPHABET[a >> 2]!;
      out += ALPHABET[(a & 0x03) << 4]!;
    } else {
      const b = data[i + 1]!;
      out += ALPHABET[a >> 2]!;
      out += ALPHABET[((a & 0x03) << 4) | (b >> 4)]!;
      out += ALPHABET[(b & 0x0f) << 2]!;
    }
  }
  return out;
};

export const b64uDecode = (input: string): Uint8Array => {
  // Strip any padding and reject whitespace.
  const cleaned = input.replace(/=+$/g, '');
  for (let i = 0; i < cleaned.length; i++) {
    if ((decodeTable[cleaned.charCodeAt(i)] ?? -1) < 0) {
      throw new Error('invalid base64url character');
    }
  }
  const fullChunks = Math.floor(cleaned.length / 4);
  const remainder = cleaned.length % 4;
  if (remainder === 1) throw new Error('invalid base64url length');

  const outLen = fullChunks * 3 + (remainder === 0 ? 0 : remainder - 1);
  const out = new Uint8Array(outLen);
  let o = 0;
  let i = 0;
  for (let n = 0; n < fullChunks; n++, i += 4) {
    const a = decodeTable[cleaned.charCodeAt(i)]!;
    const b = decodeTable[cleaned.charCodeAt(i + 1)]!;
    const c = decodeTable[cleaned.charCodeAt(i + 2)]!;
    const d = decodeTable[cleaned.charCodeAt(i + 3)]!;
    out[o++] = (a << 2) | (b >> 4);
    out[o++] = ((b & 0x0f) << 4) | (c >> 2);
    out[o++] = ((c & 0x03) << 6) | d;
  }
  if (remainder === 2) {
    const a = decodeTable[cleaned.charCodeAt(i)]!;
    const b = decodeTable[cleaned.charCodeAt(i + 1)]!;
    out[o++] = (a << 2) | (b >> 4);
  } else if (remainder === 3) {
    const a = decodeTable[cleaned.charCodeAt(i)]!;
    const b = decodeTable[cleaned.charCodeAt(i + 1)]!;
    const c = decodeTable[cleaned.charCodeAt(i + 2)]!;
    out[o++] = (a << 2) | (b >> 4);
    out[o++] = ((b & 0x0f) << 4) | (c >> 2);
  }
  return out;
};

// Hermes (RN 0.74) ships only a partial `TextEncoder` and no `TextDecoder`,
// so we use @stablelib/utf8 — the same crypto family as our other deps — for
// UTF-8 conversion instead of the (missing) global Web APIs. Note: stablelib's
// decode throws on malformed UTF-8 rather than substituting U+FFFD, which is
// the safer behavior for decrypted-then-decoded plaintext on this path.
export const utf8Encode = (s: string): Uint8Array => utf8EncodeBytes(s);
export const utf8Decode = (b: Uint8Array): string => utf8DecodeBytes(b);
