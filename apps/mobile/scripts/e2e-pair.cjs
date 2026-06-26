/**
 * End-to-end pair against a real Pi (FastAPI uvicorn).
 *
 * Reads the pairing-state from disk (where the Pi just dropped it) to get
 * the symmetric pairing_secret, builds the encrypted pair envelope using
 * the same JS primitives the iPhone app uses, posts to /api/public/pair,
 * decrypts the response, derives the long-term session key, and verifies
 * the session key matches what the Pi persisted.
 */

const fs = require('fs');
const path = require('path');

const { sharedKey, generateKeyPair } = require('@stablelib/x25519');
const { hash: sha256 } = require('@stablelib/sha256');
const { XChaCha20Poly1305 } = require('@stablelib/xchacha20poly1305');
const { randomBytes } = require('@stablelib/random');

const SECURE_DIR = process.argv[2] || '/tmp/flightpaper_e2e/secure';
const HOST = process.argv[3] || '127.0.0.1';
const PORT = parseInt(process.argv[4] || '9077', 10);

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
const decodeTable = new Int8Array(256).fill(-1);
for (let i = 0; i < ALPHABET.length; i++) decodeTable[ALPHABET.charCodeAt(i)] = i;

const b64uEncode = (data) => {
  let out = '';
  const len = data.length; let i = 0;
  for (; i + 3 <= len; i += 3) {
    const a = data[i], b = data[i + 1], c = data[i + 2];
    out += ALPHABET[a >> 2] + ALPHABET[((a & 3) << 4) | (b >> 4)] + ALPHABET[((b & 15) << 2) | (c >> 6)] + ALPHABET[c & 63];
  }
  if (i < len) {
    const a = data[i];
    if (i + 1 === len) out += ALPHABET[a >> 2] + ALPHABET[(a & 3) << 4];
    else { const b = data[i + 1]; out += ALPHABET[a >> 2] + ALPHABET[((a & 3) << 4) | (b >> 4)] + ALPHABET[(b & 15) << 2]; }
  }
  return out;
};
const b64uDecode = (s) => {
  s = s.replace(/=+$/g, '');
  const full = Math.floor(s.length / 4), rem = s.length % 4;
  const out = new Uint8Array(full * 3 + (rem === 0 ? 0 : rem - 1));
  let o = 0, i = 0;
  for (let n = 0; n < full; n++, i += 4) {
    const a = decodeTable[s.charCodeAt(i)], b = decodeTable[s.charCodeAt(i + 1)], c = decodeTable[s.charCodeAt(i + 2)], d = decodeTable[s.charCodeAt(i + 3)];
    out[o++] = (a << 2) | (b >> 4); out[o++] = ((b & 15) << 4) | (c >> 2); out[o++] = ((c & 3) << 6) | d;
  }
  if (rem === 2) { const a = decodeTable[s.charCodeAt(i)], b = decodeTable[s.charCodeAt(i + 1)]; out[o++] = (a << 2) | (b >> 4); }
  else if (rem === 3) { const a = decodeTable[s.charCodeAt(i)], b = decodeTable[s.charCodeAt(i + 1)], c = decodeTable[s.charCodeAt(i + 2)]; out[o++] = (a << 2) | (b >> 4); out[o++] = ((b & 15) << 4) | (c >> 2); }
  return out;
};
const utf8 = (s) => new TextEncoder().encode(s);

const concat = (...chunks) => {
  let n = 0; for (const c of chunks) n += c.length;
  const out = new Uint8Array(n); let off = 0;
  for (const c of chunks) { out.set(c, off); off += c.length; }
  return out;
};
const hmacSha256 = (key, msg) => {
  let bk = new Uint8Array(64);
  bk.set(key.length > 64 ? sha256(key) : key);
  const inner = new Uint8Array(64), outer = new Uint8Array(64);
  for (let i = 0; i < 64; i++) { inner[i] = bk[i] ^ 0x36; outer[i] = bk[i] ^ 0x5c; }
  return sha256(concat(outer, sha256(concat(inner, msg))));
};
const hkdfSha256 = (ikm, salt, info, length) => {
  const s = salt.length > 0 ? salt : new Uint8Array(32);
  const prk = hmacSha256(s, ikm);
  const okm = new Uint8Array(length);
  let t = new Uint8Array(0), written = 0, counter = 1;
  while (written < length) {
    t = hmacSha256(prk, concat(t, info, new Uint8Array([counter])));
    const r = Math.min(t.length, length - written);
    okm.set(t.subarray(0, r), written);
    written += r; counter += 1;
  }
  return okm;
};

const aadFor = (method, path, deviceId, clientId, keyId, seq, ts) =>
  utf8(`v=1|m=${method}|p=${path}|d=${deviceId}|c=${clientId}|k=${keyId}|s=${seq}|t=${ts}`);

const main = async () => {
  // Read Pi state from disk.
  const identity = JSON.parse(fs.readFileSync(path.join(SECURE_DIR, 'device_identity.json')));
  const pairingState = JSON.parse(fs.readFileSync(path.join(SECURE_DIR, 'pairing_state.json')));
  const deviceId = identity.device_id;
  const devicePub = b64uDecode(identity.public_key);
  const pairingSecret = b64uDecode(pairingState.pairing_secret);

  console.log(`device_id=${deviceId}`);

  // Phone-side: derive pairing key.
  const pairingKey = hkdfSha256(
    pairingSecret,
    concat(utf8(deviceId), utf8('|'), devicePub),
    utf8('flightpaper/pair/v1'),
    32,
  );

  // Generate client keypair.
  const kp = generateKeyPair();
  const clientPub = kp.publicKey;
  const clientPriv = kp.secretKey;

  // Allocate a client_id.
  const idBytes = randomBytes(6);
  let hex = ''; for (let i = 0; i < idBytes.length; i++) hex += idBytes[i].toString(16).padStart(2, '0');
  const clientId = `iphone_${hex}`;
  console.log(`client_id=${clientId}`);

  // Build pair request envelope.
  const requestBody = {
    client_pub: b64uEncode(clientPub),
    app_instance_name: 'FlightPaper E2E',
    protocol_version: 1,
  };
  const plaintext = utf8(JSON.stringify(requestBody));
  const ts = Math.floor(Date.now() / 1000);
  const nonce = randomBytes(24);
  const aead = new XChaCha20Poly1305(pairingKey);
  const ct = aead.seal(nonce, plaintext, aadFor('POST', '/api/public/pair', deviceId, clientId, 'pairing', 0, ts));
  const envelope = {
    v: 1, device_id: deviceId, client_id: clientId, key_id: 'pairing', seq: 0, ts,
    nonce: b64uEncode(nonce), ciphertext: b64uEncode(ct),
  };

  // POST.
  const response = await fetch(`http://${HOST}:${PORT}/api/public/pair`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(envelope),
  });
  if (!response.ok) {
    console.error(`HTTP ${response.status}: ${await response.text()}`);
    process.exit(1);
  }
  const respEnv = await response.json();
  console.log(`pair response seq=${respEnv.seq} ts=${respEnv.ts}`);

  // Decrypt the response under the same pairing key.
  const respAad = aadFor('RES', '/api/public/pair', deviceId, clientId, 'pairing', respEnv.seq, respEnv.ts);
  const respPt = aead.open(b64uDecode(respEnv.nonce), b64uDecode(respEnv.ciphertext), respAad);
  if (respPt === null) {
    console.error('FAIL response AEAD verification');
    process.exit(1);
  }
  const respBody = JSON.parse(new TextDecoder().decode(respPt));
  console.log(`server confirmed: ok=${respBody.ok} device_id=${respBody.device_id} client_id=${respBody.client_id}`);

  // Derive the long-term session key.
  const shared = sharedKey(clientPriv, devicePub);
  const sessionKey = hkdfSha256(
    shared,
    pairingSecret,
    concat(utf8('flightpaper/session/v1|'), utf8(deviceId), utf8('|'), utf8(clientId)),
    32,
  );

  // Read the Pi's paired_clients.json and confirm session_key matches.
  const stored = JSON.parse(fs.readFileSync(path.join(SECURE_DIR, 'paired_clients.json')));
  const piClient = stored.clients.find((c) => c.client_id === clientId);
  if (!piClient) { console.error('FAIL: client not persisted by Pi'); process.exit(1); }
  const piSessionKey = b64uDecode(piClient.session_key);
  const piHex = Array.from(piSessionKey).map(b => b.toString(16).padStart(2, '0')).join('');
  const jsHex = Array.from(sessionKey).map(b => b.toString(16).padStart(2, '0')).join('');
  if (piHex !== jsHex) {
    console.error(`FAIL session_key mismatch\n  Pi: ${piHex}\n  JS: ${jsHex}`);
    process.exit(1);
  }
  console.log('OK session_key matches Pi side');

  // Now make a secure request: GET /api/secure/status.
  const seq = 1;
  const ts2 = Math.floor(Date.now() / 1000);
  const nonce2 = randomBytes(24);
  const sessionAead = new XChaCha20Poly1305(sessionKey);
  const aad2 = aadFor('GET', '/api/secure/status', deviceId, clientId, 'main', seq, ts2);
  const ct2 = sessionAead.seal(nonce2, utf8('{}'), aad2);
  const env2 = {
    v: 1, device_id: deviceId, client_id: clientId, key_id: 'main', seq, ts: ts2,
    nonce: b64uEncode(nonce2), ciphertext: b64uEncode(ct2),
  };
  const encoded = b64uEncode(utf8(JSON.stringify(env2)));
  const r2 = await fetch(`http://${HOST}:${PORT}/api/secure/status?e=${encoded}`, {
    method: 'GET',
  });
  if (!r2.ok) { console.error(`status HTTP ${r2.status}: ${await r2.text()}`); process.exit(1); }
  const re2 = await r2.json();
  const aadR = aadFor('RES', '/api/secure/status', deviceId, clientId, 'main', re2.seq, re2.ts);
  const pt2 = sessionAead.open(b64uDecode(re2.nonce), b64uDecode(re2.ciphertext), aadR);
  if (pt2 === null) { console.error('FAIL status response AEAD'); process.exit(1); }
  const status = JSON.parse(new TextDecoder().decode(pt2));
  console.log(`status OK: device.id=${status.device.id} page=${status.display.page}`);
  console.log('\nE2E PAIR + SECURE STATUS round-trip successful.');
};

main().catch((err) => { console.error(err); process.exit(1); });
