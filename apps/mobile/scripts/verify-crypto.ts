/**
 * Verifies the JS-side crypto matches Pi-generated vectors. Skips Jest
 * because ts-jest hangs on this host (Node 25 + ts-jest interaction).
 *
 * Run:
 *   npx ts-node scripts/verify-crypto.ts
 * or
 *   npx tsx scripts/verify-crypto.ts
 */

import vectors from '../src/__tests__/fixtures/vectors.json' with { type: 'json' };

import {
  b64uDecode,
  b64uEncode,
  utf8Decode,
  utf8Encode,
} from '../src/services/crypto/base64u';
import {
  derivePairingKey,
  deriveSessionKey,
  hkdfSha256,
  x25519SharedSecret,
} from '../src/services/crypto/keys';
import {
  buildAad,
  openEnvelopeBytes,
  sealEnvelopeBytes,
} from '../src/services/crypto/envelope';

let passed = 0;
let failed = 0;

const check = (name: string, fn: () => void) => {
  try {
    fn();
    passed += 1;
    console.log(`  ok  ${name}`);
  } catch (err) {
    failed += 1;
    console.log(`  FAIL ${name}: ${err instanceof Error ? err.message : err}`);
  }
};

const eq = (actual: unknown, expected: unknown, msg = 'mismatch') => {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${msg}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
};

console.log('base64url:');
check('round-trip 0..255', () => {
  for (let n = 0; n < 256; n++) {
    const b = new Uint8Array(n);
    for (let i = 0; i < n; i++) b[i] = i & 0xff;
    const out = b64uDecode(b64uEncode(b));
    eq(Array.from(out), Array.from(b));
  }
});
check('utf8 round-trip', () => {
  for (const s of ['', 'hello', '中文 🚀', 'foo|bar=baz']) {
    eq(utf8Decode(utf8Encode(s)), s);
  }
});

console.log('HKDF-SHA256 (RFC 5869 Test Case 1):');
check('matches expected OKM', () => {
  const ikm = new Uint8Array(22).fill(0x0b);
  const salt = new Uint8Array([
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c,
  ]);
  const info = new Uint8Array([0xf0, 0xf1, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7, 0xf8, 0xf9]);
  const expectedHex =
    '3cb25f25faacd57a90434f64d0362f2a' +
    '2d2d0a90cf1a5a4c5db02d56ecc4c5bf' +
    '34007208d5b887185865';
  const okm = hkdfSha256({ ikm, salt, info, length: 42 });
  const hex = Array.from(okm).map((b) => b.toString(16).padStart(2, '0')).join('');
  eq(hex, expectedHex);
});

console.log('Pairing + session key interop:');
check('pairing key matches Pi', () => {
  const k = derivePairingKey({
    pairingSecret: b64uDecode(vectors.inputs.pairing_secret_b64u),
    deviceId: vectors.inputs.device_id,
    devicePublicKey: b64uDecode(vectors.inputs.device_pub_b64u),
  });
  eq(b64uEncode(k), vectors.expected.pairing_key_b64u);
});
check('X25519 + session key matches Pi', () => {
  const shared = x25519SharedSecret(
    b64uDecode(vectors.inputs.phone_priv_b64u),
    b64uDecode(vectors.inputs.device_pub_b64u),
  );
  const sk = deriveSessionKey({
    sharedSecret: shared,
    pairingSecret: b64uDecode(vectors.inputs.pairing_secret_b64u),
    deviceId: vectors.inputs.device_id,
    clientId: vectors.inputs.client_id,
  });
  eq(b64uEncode(sk), vectors.expected.session_key_b64u);
});

console.log('AEAD interop:');
check('XChaCha20-Poly1305 fixed nonce matches Pi', () => {
  const { XChaCha20Poly1305 } = require('@stablelib/xchacha20poly1305');
  const key = b64uDecode(vectors.inputs.aead_key_b64u);
  const nonce = b64uDecode(vectors.inputs.aead_nonce_b64u);
  const aad = utf8Encode(vectors.inputs.aead_aad_utf8);
  const plaintext = utf8Encode(vectors.inputs.aead_plaintext_utf8);
  const aead = new XChaCha20Poly1305(key);
  const ct = aead.seal(nonce, plaintext, aad);
  eq(b64uEncode(ct), vectors.expected.aead_ciphertext_b64u);
});

console.log('AAD layout:');
check('matches Pi build_aad byte-for-byte', () => {
  const aad = buildAad({
    method: 'POST',
    path: '/api/secure/x',
    deviceId: 'fp_aabbccdd',
    clientId: 'iphone_aabbccddeeff',
    keyId: 'main',
    seq: 42,
    ts: 1_700_000_000,
  });
  eq(
    utf8Decode(aad),
    'v=1|m=POST|p=/api/secure/x|d=fp_aabbccdd|c=iphone_aabbccddeeff|k=main|s=42|t=1700000000',
  );
});

console.log('Envelope:');
check('JS-sealed envelope opens with same JS key', () => {
  const key = new Uint8Array(32).fill(7);
  const ctx = {
    method: 'POST' as const,
    path: '/api/secure/x',
    deviceId: 'fp_aabbccdd',
    clientId: 'iphone_aabbccddeeff',
    keyId: 'main' as const,
    seq: 42,
    ts: 1_700_000_000,
  };
  const env = sealEnvelopeBytes(key, utf8Encode('hello'), ctx);
  const pt = openEnvelopeBytes(key, env, ctx);
  eq(utf8Decode(pt), 'hello');
});
check('Pi-sealed envelope opens on JS side', () => {
  const inputs = vectors.inputs;
  const sample = vectors.envelope_sample;
  const shared = x25519SharedSecret(
    b64uDecode(inputs.phone_priv_b64u),
    b64uDecode(inputs.device_pub_b64u),
  );
  const sessionKey = deriveSessionKey({
    sharedSecret: shared,
    pairingSecret: b64uDecode(inputs.pairing_secret_b64u),
    deviceId: inputs.device_id,
    clientId: inputs.client_id,
  });
  const pt = openEnvelopeBytes(sessionKey, sample.envelope, {
    method: sample.method as 'POST',
    path: sample.path,
    deviceId: sample.envelope.device_id,
    clientId: sample.envelope.client_id,
    keyId: 'main',
    seq: sample.envelope.seq,
    ts: sample.envelope.ts,
  });
  const decoded = JSON.parse(utf8Decode(pt));
  eq(decoded, sample.plaintext);
});

console.log('Tamper rejection:');
check('flipped ciphertext byte rejected', () => {
  const key = new Uint8Array(32).fill(3);
  const ctx = {
    method: 'POST' as const, path: '/x',
    deviceId: 'fp_aabbccdd', clientId: 'iphone_aabbccddeeff',
    keyId: 'main' as const, seq: 1, ts: 1_700_000_000,
  };
  const env = sealEnvelopeBytes(key, utf8Encode('hi'), ctx);
  const ct = b64uDecode(env.ciphertext);
  ct[0] ^= 0x01;
  env.ciphertext = b64uEncode(ct);
  let threw = false;
  try { openEnvelopeBytes(key, env, ctx); } catch { threw = true; }
  if (!threw) throw new Error('tamper not detected');
});
check('wrong method rejected', () => {
  const key = new Uint8Array(32).fill(3);
  const ctx = {
    method: 'POST' as const, path: '/x',
    deviceId: 'fp_aabbccdd', clientId: 'iphone_aabbccddeeff',
    keyId: 'main' as const, seq: 1, ts: 1_700_000_000,
  };
  const env = sealEnvelopeBytes(key, utf8Encode('hi'), ctx);
  let threw = false;
  try { openEnvelopeBytes(key, env, { ...ctx, method: 'GET' }); } catch { threw = true; }
  if (!threw) throw new Error('AAD mismatch not detected');
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
