/**
 * Vanilla CommonJS verification of the FlightPaper crypto stack.
 *
 * Re-implements the JS-side crypto inline (instead of importing the .ts
 * sources, which fight Node 25's ESM resolver). This still confirms that
 * the @stablelib primitives + AAD layout + HKDF derivation produce
 * byte-identical outputs to the Python Pi side — that's the actual
 * concern for cross-language interop.
 */

const fs = require('fs');
const path = require('path');

const { hash: sha256 } = require('@stablelib/sha256');
const { generateKeyPair, sharedKey } = require('@stablelib/x25519');
const { XChaCha20Poly1305 } = require('@stablelib/xchacha20poly1305');

const vectors = JSON.parse(
  fs.readFileSync(path.join(__dirname, '..', 'src', '__tests__', 'fixtures', 'vectors.json')),
);

// ---------- base64url ----------
const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
const decodeTable = new Int8Array(256).fill(-1);
for (let i = 0; i < ALPHABET.length; i++) decodeTable[ALPHABET.charCodeAt(i)] = i;

const b64uEncode = (data) => {
  let out = '';
  const len = data.length;
  let i = 0;
  for (; i + 3 <= len; i += 3) {
    const a = data[i], b = data[i + 1], c = data[i + 2];
    out += ALPHABET[a >> 2] + ALPHABET[((a & 3) << 4) | (b >> 4)] + ALPHABET[((b & 15) << 2) | (c >> 6)] + ALPHABET[c & 63];
  }
  if (i < len) {
    const a = data[i];
    if (i + 1 === len) {
      out += ALPHABET[a >> 2] + ALPHABET[(a & 3) << 4];
    } else {
      const b = data[i + 1];
      out += ALPHABET[a >> 2] + ALPHABET[((a & 3) << 4) | (b >> 4)] + ALPHABET[(b & 15) << 2];
    }
  }
  return out;
};

const b64uDecode = (s) => {
  s = s.replace(/=+$/g, '');
  const full = Math.floor(s.length / 4);
  const rem = s.length % 4;
  if (rem === 1) throw new Error('bad b64u');
  const out = new Uint8Array(full * 3 + (rem === 0 ? 0 : rem - 1));
  let o = 0, i = 0;
  for (let n = 0; n < full; n++, i += 4) {
    const a = decodeTable[s.charCodeAt(i)], b = decodeTable[s.charCodeAt(i + 1)];
    const c = decodeTable[s.charCodeAt(i + 2)], d = decodeTable[s.charCodeAt(i + 3)];
    out[o++] = (a << 2) | (b >> 4);
    out[o++] = ((b & 15) << 4) | (c >> 2);
    out[o++] = ((c & 3) << 6) | d;
  }
  if (rem === 2) {
    const a = decodeTable[s.charCodeAt(i)], b = decodeTable[s.charCodeAt(i + 1)];
    out[o++] = (a << 2) | (b >> 4);
  } else if (rem === 3) {
    const a = decodeTable[s.charCodeAt(i)], b = decodeTable[s.charCodeAt(i + 1)], c = decodeTable[s.charCodeAt(i + 2)];
    out[o++] = (a << 2) | (b >> 4);
    out[o++] = ((b & 15) << 4) | (c >> 2);
  }
  return out;
};

// ---------- HKDF + HMAC-SHA256 ----------
const concat = (...chunks) => {
  let n = 0; for (const c of chunks) n += c.length;
  const out = new Uint8Array(n); let off = 0;
  for (const c of chunks) { out.set(c, off); off += c.length; }
  return out;
};

const hmacSha256 = (key, message) => {
  let blockKey;
  if (key.length > 64) {
    blockKey = new Uint8Array(64); blockKey.set(sha256(key));
  } else {
    blockKey = new Uint8Array(64); blockKey.set(key);
  }
  const inner = new Uint8Array(64), outer = new Uint8Array(64);
  for (let i = 0; i < 64; i++) {
    inner[i] = blockKey[i] ^ 0x36;
    outer[i] = blockKey[i] ^ 0x5c;
  }
  return sha256(concat(outer, sha256(concat(inner, message))));
};

const hkdfSha256 = ({ ikm, salt, info, length }) => {
  const s = salt.length > 0 ? salt : new Uint8Array(32);
  const prk = hmacSha256(s, ikm);
  const okm = new Uint8Array(length);
  let t = new Uint8Array(0), written = 0, counter = 1;
  while (written < length) {
    t = hmacSha256(prk, concat(t, info, new Uint8Array([counter])));
    const r = Math.min(t.length, length - written);
    okm.set(t.subarray(0, r), written);
    written += r;
    counter += 1;
  }
  return okm;
};

const utf8 = (s) => new TextEncoder().encode(s);

const derivePairingKey = ({ pairingSecret, deviceId, devicePub }) =>
  hkdfSha256({
    ikm: pairingSecret,
    salt: concat(utf8(deviceId), utf8('|'), devicePub),
    info: utf8('flightpaper/pair/v1'),
    length: 32,
  });

const deriveSessionKey = ({ shared, pairingSecret, deviceId, clientId }) =>
  hkdfSha256({
    ikm: shared,
    salt: pairingSecret,
    info: concat(utf8('flightpaper/session/v1|'), utf8(deviceId), utf8('|'), utf8(clientId)),
    length: 32,
  });

// ---------- runner ----------
let pass = 0, fail = 0;
const eq = (a, b, name) => {
  const sa = JSON.stringify(a), sb = JSON.stringify(b);
  if (sa === sb) { pass++; console.log(`  ok   ${name}`); }
  else { fail++; console.log(`  FAIL ${name}: expected ${sb}, got ${sa}`); }
};

// RFC 5869 Test Case 1
const rfcIkm = new Uint8Array(22).fill(0x0b);
const rfcSalt = new Uint8Array([0,1,2,3,4,5,6,7,8,9,0x0a,0x0b,0x0c]);
const rfcInfo = new Uint8Array([0xf0,0xf1,0xf2,0xf3,0xf4,0xf5,0xf6,0xf7,0xf8,0xf9]);
const rfcExp = '3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865';
const rfcOkm = hkdfSha256({ ikm: rfcIkm, salt: rfcSalt, info: rfcInfo, length: 42 });
const rfcHex = Array.from(rfcOkm).map(b => b.toString(16).padStart(2, '0')).join('');
eq(rfcHex, rfcExp, 'HKDF-SHA256 RFC 5869 Test Case 1');

// b64u round-trip
const sample = new Uint8Array(200);
for (let i = 0; i < sample.length; i++) sample[i] = i & 0xff;
eq(Array.from(b64uDecode(b64uEncode(sample))), Array.from(sample), 'base64url round-trip (200 bytes)');

// Pi-side vectors
const I = vectors.inputs, E = vectors.expected;
const pk = derivePairingKey({
  pairingSecret: b64uDecode(I.pairing_secret_b64u),
  deviceId: I.device_id,
  devicePub: b64uDecode(I.device_pub_b64u),
});
eq(b64uEncode(pk), E.pairing_key_b64u, 'pairing key matches Pi side');

const shared = sharedKey(b64uDecode(I.phone_priv_b64u), b64uDecode(I.device_pub_b64u));
const sk = deriveSessionKey({
  shared, pairingSecret: b64uDecode(I.pairing_secret_b64u),
  deviceId: I.device_id, clientId: I.client_id,
});
eq(b64uEncode(sk), E.session_key_b64u, 'X25519 + session key matches Pi side');

// AEAD fixed-vector
const aead = new XChaCha20Poly1305(b64uDecode(I.aead_key_b64u));
const ct = aead.seal(b64uDecode(I.aead_nonce_b64u), utf8(I.aead_plaintext_utf8), utf8(I.aead_aad_utf8));
eq(b64uEncode(ct), E.aead_ciphertext_b64u, 'XChaCha20-Poly1305 fixed vector matches Pi side');

// Pi-sealed envelope opens on JS
const env = vectors.envelope_sample.envelope;
const path_ = vectors.envelope_sample.path;
const aad =
  `v=1|m=POST|p=${path_}|d=${env.device_id}|c=${env.client_id}|k=main|s=${env.seq}|t=${env.ts}`;
const opener = new XChaCha20Poly1305(sk);
const ptOpened = opener.open(b64uDecode(env.nonce), b64uDecode(env.ciphertext), utf8(aad));
if (ptOpened === null) {
  fail++; console.log('  FAIL Pi-sealed envelope: AEAD open returned null');
} else {
  const json = JSON.parse(new TextDecoder().decode(ptOpened));
  eq(json, vectors.envelope_sample.plaintext, 'Pi-sealed envelope decrypts on JS side');
}

// JS-sealed → JS-open round-trip
{
  const k = new Uint8Array(32).fill(7);
  const a = new XChaCha20Poly1305(k);
  const nonce = new Uint8Array(24).fill(9);
  const aadStr = 'v=1|m=POST|p=/x|d=fp_aabbccdd|c=iphone_aabbccddeeff|k=main|s=42|t=1700000000';
  const c = a.seal(nonce, utf8('hello'), utf8(aadStr));
  const p = a.open(nonce, c, utf8(aadStr));
  eq(new TextDecoder().decode(p), 'hello', 'JS sealEnvelope round-trip');
  // Wrong AAD must fail
  const p2 = a.open(nonce, c, utf8(aadStr.replace('POST', 'GET')));
  eq(p2, null, 'JS AAD mismatch rejected (open returns null)');
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
