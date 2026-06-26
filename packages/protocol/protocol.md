# FlightPaper Protocol (v1)

This document defines the wire protocol between the FlightPaper Pi service
and the FlightPaper iPhone companion app. Both implementations MUST conform
to this document. Schemas in this directory are normative for payload shape;
this document is normative for behavior, ordering, and security checks.

---

## 1. Goals

- Allow exactly one paired iPhone to control one Pi over a shared local
  network (typically the iPhone's hotspot).
- Protect every sensitive payload against passive observers, tampering,
  replay, and impersonation.
- Survive intermittent connectivity without losing the latest known
  location.
- Permit pairing reset without bricking the device.

Non-goals (v1): public-internet exposure, multi-tenant identity, multi-user
accounts, App Store distribution.

---

## 2. Identifiers

| Field | Format | Example | Notes |
|---|---|---|---|
| `device_id` | `fp_` + 8 lowercase hex | `fp_a1b2c3d4` | Pi-generated on first boot, persisted. |
| `client_id` | `iphone_` + 12 lowercase hex | `iphone_93ab1f2c0e10` | Phone-generated per app install. |
| `key_id` | short string | `main` | Identifies which session key encrypts a message. |
| `seq` | uint64 | `42` | Monotonic per (device_id, client_id, key_id, direction). |
| `ts` | unix seconds (int) | `1710000000` | Sender's clock at envelope creation. |
| `nonce` | 24-byte random, base64url | `9wQk…` | Required for AEAD construction; never reused with a key. |
| `v` | int | `1` | Protocol version. |

`device_id` and `client_id` are public, low-entropy identifiers. They do not
authenticate anything on their own — they exist so the Pi can look up the
right session key. Authentication comes from the AEAD tag.

---

## 3. Pairing

### 3.1 States

```
unpaired --------> pairing_pending --------> paired
   ^                     |
   |                     v
   +----- pairing_expired / reset
```

The Pi persists pairing state under `/etc/flightpaper/secure/`:

- `device_identity.json` — `device_id`, long-term X25519 keypair, created on
  first boot.
- `pairing_state.json` — current state, current one-time secret hash,
  expiration, attempt counter. Re-generated whenever entering
  `pairing_pending`.
- `paired_clients.json` — array of paired clients, each with `client_id`,
  client long-term public key, session key material, last-seen sequence
  numbers.

All three files MUST be owned by root with mode `0600` on a real device.

### 3.2 QR payload

The ePaper renders a QR encoding a `flightpaper://pair?…` URI. Payload is the
JSON object validated by `pairing-payload.schema.json`, base64url-encoded as
the `p` query parameter. Compact form is required to fit the QR on the
250×122 ePaper.

```
flightpaper://pair?p=<base64url(JSON pairing payload)>
```

The QR carries: protocol version, host, port, `device_id`, short device
name, the Pi's long-term X25519 public key, a one-time `pairing_secret`
(256 bits, base64url), and an `expires_at` unix-second deadline. The Pi
also renders a fallback `IP` and a short `Pair Code` (e.g. `123-456`),
derived from `HMAC(pairing_secret, "code")[:6 digits]`.

The QR MUST NEVER be transmitted over the network. It is a physical
out-of-band channel.

### 3.3 Handshake

The pairing handshake intentionally splits the trust roots so that
`client_pub` can travel *inside* the encrypted envelope (the natural place
for it). The pairing key is therefore symmetric — derived from the
out-of-band-only `pairing_secret` — and the session key is ECDH-derived
afterwards.

1. Pi enters `pairing_pending`, generates `pairing_secret` and a fresh
   X25519 keypair if rotating. Renders QR on ePaper.
2. Phone scans QR, learning `device_id`, `device_pub`, `pairing_secret`,
   and `expires_at`. Phone generates its own X25519 keypair (or reuses
   one from SecureStore) and a `client_id`.
3. Both sides derive the **pairing key** (symmetric):
   ```
   pairing_key = HKDF-SHA256(
       ikm  = pairing_secret,
       salt = utf8(device_id) || "|" || device_pub,
       info = "flightpaper/pair/v1",
       length = 32,
   )
   ```
   Binding to `device_id` + `device_pub` prevents a captured pairing
   secret from being replayed against a different physical device.
4. Phone sends `POST /api/public/pair` with a secure envelope whose
   `key_id` is `pairing` and whose plaintext is the `PairRequest` shape in
   `api-contract.md` — including the phone's `client_pub`.
5. Pi loads `pairing_key` and decrypts. If AEAD verification fails: the
   Pi increments the attempt counter; after `max_pairing_attempts`
   (default 5), the secret is invalidated. If decryption succeeds:
   - Pi reads `client_pub` from the plaintext.
   - Pi computes `shared = X25519(device_priv, client_pub)`.
   - Pi derives the long-term **session key**:
     ```
     session_key = HKDF-SHA256(
         ikm  = shared,
         salt = pairing_secret,
         info = "flightpaper/session/v1|" || device_id || "|" || client_id,
         length = 32,
     )
     ```
   - Pi creates the paired-client record.
6. Pi returns the `PairResponse` envelope still encrypted under
   `pairing_key`, then immediately invalidates `pairing_secret`. Pi MUST
   NOT accept a second handshake against the same secret.
7. Phone derives the same `session_key` using its own `client_priv` and
   the Pi's `device_pub`, stores the paired-device record (host, port,
   `device_id`, `client_id`, `session_key`, `key_id=main`) in SecureStore.
8. All subsequent traffic uses `session_key` and the secure envelope
   (§4).

If the phone never completes step 4 before `expires_at`, the Pi
transitions back to `unpaired` and shows the pairing page on next render.

`POST /api/secure/pairing/reset` (only callable by an already paired
client) returns the device to `unpaired` and triggers a fresh
`pairing_pending` state on the next boot or immediately.

---

## 4. Secure Envelope

Every protected request and response MUST use a secure envelope. The
envelope is JSON, validated against `secure-envelope.schema.json`.

### 4.1 Shape

```json
{
  "v": 1,
  "device_id": "fp_a1b2c3d4",
  "client_id": "iphone_93ab1f2c0e10",
  "key_id": "main",
  "seq": 42,
  "ts": 1710000000,
  "nonce": "<base64url, 24 bytes>",
  "ciphertext": "<base64url>"
}
```

### 4.2 Construction (sender)

```
key       = lookup_session_key(device_id, client_id, key_id)
plaintext = utf8(JSON body)
aad       = utf8(
  "v=" + v + "|" +
  "m=" + http_method + "|" +
  "p=" + http_path + "|" +
  "d=" + device_id + "|" +
  "c=" + client_id + "|" +
  "k=" + key_id + "|" +
  "s=" + seq + "|" +
  "t=" + ts
)
ciphertext = ChaCha20Poly1305(key).encrypt(nonce, plaintext, aad)
```

`http_method` is uppercase (`GET`, `POST`, `PATCH`). `http_path` is the
absolute path including query string, normalized to lowercase percent
escapes, with no fragment. For responses, `http_method` is `RES` and
`http_path` echoes the request's path so AAD is symmetric across the
exchange.

### 4.3 Verification (receiver)

The receiver MUST reject the message if any of the following is true:

- `v` is not `1`.
- `device_id` or `client_id` does not match a known paired pair.
- `key_id` does not identify a session key.
- `ts` is more than `replay_window_seconds` (default 120) outside the
  receiver's clock.
- `seq` is less than or equal to the highest accepted `seq` for this
  (device_id, client_id, key_id, direction). (Strictly monotonic.)
- `nonce` was used previously with the same key (kept in an LRU window).
- AEAD verification fails.
- The decrypted plaintext does not conform to the endpoint's request
  schema.

On rejection the receiver SHOULD return HTTP `401` for envelope-level
failures and `400` for schema-level failures, with a generic error body.
Specific reasons MUST NOT be returned (to avoid leaking which check
failed).

### 4.4 Sequence numbers

`seq` is unsigned, starts at `1` for the first message after pairing,
and is incremented by exactly `1` per sent message. Requests and
responses each have their own counter. Counters persist across restarts
(Pi: `paired_clients.json`; phone: SecureStore).

---

## 5. Public endpoints (no envelope)

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/api/public/health` | Liveness probe; returns version + uptime. |
| `GET`  | `/api/public/pairing-status` | Returns `{ state: "unpaired" \| "pairing_pending" \| "paired", device_id }`. |
| `POST` | `/api/public/pair` | Pairing handshake. Body is a secure envelope encrypted under the pairing key (see §3.3). |

These endpoints MUST NOT leak any session secret, GPS data, or
configuration. They MUST be rate-limited (default 30 req/min/IP).

---

## 6. Secure endpoints (envelope required)

See [`api-contract.md`](api-contract.md) for full request and response
shapes.

- `POST  /api/secure/location`
- `GET   /api/secure/status`
- `GET   /api/secure/aircraft`
- `GET   /api/secure/config`
- `PATCH /api/secure/config`
- `POST  /api/secure/display/page`
- `POST  /api/secure/refresh`
- `POST  /api/secure/system/shutdown`
- `POST  /api/secure/system/reboot`
- `POST  /api/secure/pairing/reset`

---

## 7. Error codes

Error responses carry an envelope whose plaintext is:

```json
{ "error": { "code": "<string>", "message": "<human readable>" } }
```

Defined codes:

| Code | HTTP | Meaning |
|---|---|---|
| `not_paired` | 401 | No paired client for the supplied IDs. |
| `bad_envelope` | 401 | Envelope failed verification. |
| `replay` | 401 | Sequence or nonce already used. |
| `expired` | 401 | Timestamp outside replay window. |
| `pairing_expired` | 410 | One-time pairing secret no longer valid. |
| `attempt_limit` | 429 | Too many pair attempts; rest the device. |
| `invalid_request` | 400 | Plaintext failed schema validation. |
| `not_ready` | 503 | Pi has no location yet, or boot is incomplete. |
| `forbidden_action` | 403 | Client lacks permission for the endpoint. |
| `internal` | 500 | Unhandled server error. |

The body MUST NOT include stack traces, OS paths, or secrets.

---

## 8. Time handling

Both sides use UNIX seconds (int). The Pi has no RTC by default — it
relies on the iPhone's hotspot DNS to reach NTP shortly after boot. If
the Pi's clock is more than the replay window away from the phone's, the
phone SHOULD show a "device clock is off" status and the Pi SHOULD log a
single warning per boot.

---

## 9. Logging redaction

Both sides MUST NOT log:

- `pairing_secret`, raw or hashed
- session keys
- decrypted location payloads (a one-line summary `lat=…, lon=…, age=…s`
  is acceptable; full payload is not)
- OpenSky credentials
- Wi-Fi passwords

Both sides MAY log: envelope verification verdicts ("ok", "replay",
"bad_tag"), aircraft counts, freshness ages, page transitions.

---

## 10. Limitations (called out for honesty)

- A reused or compromised pairing secret defeats the handshake. Protect
  the QR like any other root credential.
- A phone with a rooted OS or a tampered companion app can leak the
  session key. The Pi has no way to detect this.
- Plain HTTP over the local hotspot exposes envelope metadata
  (`device_id`, `client_id`, `seq`, `ts`) to a passive observer. Payloads
  are encrypted; traffic analysis is possible.
- The Pi is a single-tenant device. Multi-client expansion is supported
  by the schema but not exercised by v1.
