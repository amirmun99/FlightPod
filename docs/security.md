# Security model

This document is the honest version of "how safe is this." The normative
wire-protocol definition is at
[`packages/protocol/protocol.md`](../packages/protocol/protocol.md); the
rest of this doc explains the assumptions behind that protocol and the
things it intentionally does not protect.

## Threat model

We consider four realistic threats for a personal POC operating on an
iPhone hotspot:

1. **Passive LAN observer.** Anyone able to associate to the same
   hotspot (e.g. a misclick on a guest account, an Android device the
   user forgot was joined). All on-the-wire payloads are AEAD-encrypted;
   the observer learns metadata (`device_id`, `client_id`, `seq`, `ts`,
   message size, request path) but not aircraft data, GPS, or settings.
2. **Accidental unpaired access.** A second phone scans the QR after the
   intended one. The Pi only accepts one pair handshake per
   `pairing_secret`. The second phone's request is rejected with
   `pairing_expired`.
3. **Replay attempts.** Captured envelopes replayed back at the Pi.
   Rejected by the monotonic `seq` window + the 120-second `ts` skew
   guard.
4. **Malicious paired phone.** Once paired, a phone has full control
   (settings, refresh, shutdown). The reset-pairing button on the
   device + `POST /api/secure/pairing/reset` are the recovery paths.

We do **not** model an attacker who has root on either device or
physical access to the Pi.

## What is protected

- **Every protected payload** is encrypted under a session key with
  XChaCha20-Poly1305 (libsodium) and bound to the request method +
  full path via AEAD `aad`. Tampering with the path or method
  invalidates the tag.
- **The pair handshake** uses a symmetric pairing key derived from the
  one-time `pairing_secret`, then derives a long-term session key via
  X25519 ECDH + HKDF-SHA256. The QR is single-use and burns after a
  successful handshake.
- **Replay** is blocked by a per-client, per-direction monotonic `seq`
  window + nonce cache. The skew tolerance is `replay_window_seconds`
  (default 120) on both sides.
- **Sequence numbers** are persisted across restarts (Pi in
  `/etc/flightpaper/secure/paired_clients.json`, phone in iOS
  SecureStore), so a process restart can't reuse a previously-accepted
  seq.

## What is **not** protected

- **Envelope metadata.** `device_id`, `client_id`, `key_id`, `seq`,
  `ts`, and the HTTP path travel in the clear. An observer learns
  *which* endpoint was called and approximately when. The path alone
  is enough to distinguish status pings from settings PATCHes.
- **Rooted phone.** iOS SecureStore is only as good as the device's
  Secure Enclave. If the phone is jailbroken, the session key is
  recoverable; treat that phone as compromised and reset pairing.
- **Physical access to the Pi.** Anyone with the microSD card can read
  the device identity + paired clients files. They cannot derive the
  phone's private key, but they *can* impersonate the Pi to a re-
  pairing phone. If you lose the Pi physically, burn the card.
- **The QR being photographed.** The QR is a session-bearer token until
  the handshake completes (typically a few seconds). After the
  handshake the `pairing_secret` is invalidated and a photograph is
  useless. Before the handshake completes, anyone with a clear photo
  can pair. Treat the pairing page as private until the phone is in
  hand.

## Crypto choices

| Use | Algorithm | Library |
|---|---|---|
| Random | OS CSPRNG (`os.urandom`, `react-native-get-random-values`) | stdlib / `@stablelib/random` |
| ECDH | X25519 | libsodium (`PyNaCl`, `@stablelib/x25519`) |
| KDF | HKDF-SHA256 (RFC 5869) | stdlib `hashlib` + `hmac`, `@stablelib/sha256` |
| AEAD | XChaCha20-Poly1305 (24-byte nonce) | libsodium (`PyNaCl`, `@stablelib/xchacha20poly1305`) |
| Encoding | base64url (no padding) | hand-rolled both sides |

These are the same primitives [Wireguard, Signal, age, etc] use. The
24-byte nonce of XChaCha lets us pick nonces at random with a
negligible collision risk for the entire device lifetime.

## Key storage

### On the Pi

Under `/etc/flightpaper/secure/` (`0700 root:root`):

- `device_identity.json` — `device_id`, long-term X25519 keypair.
  Created on first boot; preserved across reinstalls (unless
  `uninstall.sh --purge`).
- `pairing_state.json` — current `pairing_secret`, expiration, attempt
  counter. Rewritten on every entry to `pairing_pending`. Burned on
  successful handshake.
- `paired_clients.json` — array of `{client_id, client_pub, session_key,
  seq_in, seq_out, paired_at, last_seen_at}`. Updated on every accepted
  request.

### On the iPhone

Under iOS Keychain via `expo-secure-store` with
`WHEN_UNLOCKED_THIS_DEVICE_ONLY`:

- `flightpaper.paired_device` — public identity + host + port +
  clientId.
- `flightpaper.session_keys` — phone-side X25519 keypair + derived
  session key.
- `flightpaper.seq_out` — outgoing seq counter (mutex-protected, see
  `services/storage/secureStore.ts`).

Nothing else goes in SecureStore. The aircraft cache, retry queue, and
logs live in zustand (volatile).

## Pairing reset

Three ways to reset:

1. **From the phone.** Security screen → `Reset pairing`. Calls
   `POST /api/secure/pairing/reset` (best-effort), then clears
   SecureStore.
2. **From the API.** Any paired client can post to
   `/api/secure/pairing/reset`. The Pi drops the calling client record
   and re-enters `pairing_pending`.
3. **From the Pi.** Long-press the PiSugar button (very-long press, ≥5s
   by default) triggers `scripts/reset_pairing.py`, which deletes
   `pairing_state.json` and `paired_clients.json`.

Direct admin commands:

```bash
# Force reset from a shell on the Pi:
sudo /opt/flightpaper/.venv/bin/python /opt/flightpaper/scripts/reset_pairing.py
sudo systemctl restart flightpaper
```

A fresh QR renders on the next ePaper refresh.

## Logging redaction

Logs go to `journalctl -u flightpaper` and to
`/var/log/flightpaper/flightpaper.log` (rotated). A redaction filter in
`flightpaper/logging_setup.py` drops anything matching the known secret
keys (`pairing_secret`, `session_key`, `private_key`,
`Authorization`). The phone's in-app Logs screen only logs
connection-level events — paths, HTTP codes, error reasons — never
secrets, GPS, or callsigns.
