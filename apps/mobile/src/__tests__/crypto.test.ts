/**
 * Cross-language interop tests.
 *
 * The vectors in ``fixtures/vectors.json`` were produced by the Python
 * Pi-side crypto in ``apps/pi/flightpaper/security/crypto.py``. If the JS
 * side disagrees on any byte, pair handshakes between the phone and Pi
 * will fail in production.
 */

import vectors from './fixtures/vectors.json';

import { b64uDecode, b64uEncode, utf8Encode } from '../services/crypto/base64u';
import {
  derivePairingKey,
  deriveSessionKey,
  hkdfSha256,
  x25519SharedSecret,
} from '../services/crypto/keys';
import {
  buildAad,
  openEnvelopeBytes,
  sealEnvelopeBytes,
} from '../services/crypto/envelope';

describe('HKDF-SHA256', () => {
  it('matches RFC 5869 Test Case 1', () => {
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
    const hex = Array.from(okm)
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
    expect(hex).toBe(expectedHex);
  });
});

describe('Key derivation interop with Python', () => {
  const inputs = vectors.inputs;
  const expected = vectors.expected;

  it('pairing key matches the Pi side', () => {
    const pairingKey = derivePairingKey({
      pairingSecret: b64uDecode(inputs.pairing_secret_b64u),
      deviceId: inputs.device_id,
      devicePublicKey: b64uDecode(inputs.device_pub_b64u),
    });
    expect(b64uEncode(pairingKey)).toBe(expected.pairing_key_b64u);
  });

  it('X25519 shared secret + session key match the Pi side', () => {
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
    expect(b64uEncode(sessionKey)).toBe(expected.session_key_b64u);
  });
});

describe('AEAD interop with Python', () => {
  const inputs = vectors.inputs;
  const expected = vectors.expected;

  it('produces the same ciphertext for fixed key/nonce/AAD/plaintext', () => {
    const key = b64uDecode(inputs.aead_key_b64u);
    const nonce = b64uDecode(inputs.aead_nonce_b64u);
    const aad = utf8Encode(inputs.aead_aad_utf8);
    const plaintext = utf8Encode(inputs.aead_plaintext_utf8);

    // Use the raw AEAD from stablelib via sealEnvelopeBytes' helper.
    const { XChaCha20Poly1305 } = require('@stablelib/xchacha20poly1305');
    const aead = new XChaCha20Poly1305(key);
    const ciphertext = aead.seal(nonce, plaintext, aad);
    expect(b64uEncode(ciphertext)).toBe(expected.aead_ciphertext_b64u);
  });

  it('round-trips through sealEnvelopeBytes + openEnvelopeBytes', () => {
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
    const envelope = sealEnvelopeBytes(key, utf8Encode('hello'), ctx);
    const decrypted = openEnvelopeBytes(key, envelope, ctx);
    expect(new TextDecoder().decode(decrypted)).toBe('hello');
  });
});

describe('AAD layout', () => {
  it('matches Pi-side build_aad byte-for-byte', () => {
    const aad = buildAad({
      method: 'POST',
      path: '/api/secure/x',
      deviceId: 'fp_aabbccdd',
      clientId: 'iphone_aabbccddeeff',
      keyId: 'main',
      seq: 42,
      ts: 1_700_000_000,
    });
    const expected =
      'v=1|m=POST|p=/api/secure/x|d=fp_aabbccdd|c=iphone_aabbccddeeff|k=main|s=42|t=1700000000';
    expect(new TextDecoder().decode(aad)).toBe(expected);
  });
});

describe('Envelope tamper rejection', () => {
  const key = new Uint8Array(32).fill(3);
  const ctx = {
    method: 'POST' as const,
    path: '/x',
    deviceId: 'fp_aabbccdd',
    clientId: 'iphone_aabbccddeeff',
    keyId: 'main' as const,
    seq: 1,
    ts: 1_700_000_000,
  };

  it('rejects tampered ciphertext', () => {
    const envelope = sealEnvelopeBytes(key, utf8Encode('hi'), ctx);
    const ct = b64uDecode(envelope.ciphertext);
    ct[0] ^= 0x01;
    envelope.ciphertext = b64uEncode(ct);
    expect(() => openEnvelopeBytes(key, envelope, ctx)).toThrow();
  });

  it('rejects wrong method', () => {
    const envelope = sealEnvelopeBytes(key, utf8Encode('hi'), ctx);
    expect(() => openEnvelopeBytes(key, envelope, { ...ctx, method: 'GET' })).toThrow();
  });

  it('rejects wrong key', () => {
    const envelope = sealEnvelopeBytes(key, utf8Encode('hi'), ctx);
    const wrongKey = new Uint8Array(32).fill(9);
    expect(() => openEnvelopeBytes(wrongKey, envelope, ctx)).toThrow();
  });
});

describe('Envelope produced by Pi opens on JS', () => {
  // The vector envelope was sealed under ``session_key`` from the inputs.
  const inputs = vectors.inputs;
  const sample = vectors.envelope_sample;

  it('decrypts the Pi-sealed envelope', () => {
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
    const envelope: import('../types').SecureEnvelope = {
      ...sample.envelope,
      v: 1,
      key_id: 'main',
    };
    const plaintext = openEnvelopeBytes(sessionKey, envelope, {
      method: sample.method as 'POST',
      path: sample.path,
      deviceId: envelope.device_id,
      clientId: envelope.client_id,
      keyId: 'main',
      seq: envelope.seq,
      ts: envelope.ts,
    });
    const decoded = JSON.parse(new TextDecoder().decode(plaintext));
    expect(decoded).toEqual(sample.plaintext);
  });
});
