# Pairing

Pairing binds exactly one iPhone to one Pi. The QR-rooted handshake
gives both sides a long-term session key. See
[`packages/protocol/protocol.md`](../packages/protocol/protocol.md) §3
for the normative version of this flow.

## ePaper pairing page

```
┌──────────────────────────────────────────────────┐
│ FlightPaper                          v0.1.0      │
│                                                  │
│   ┌──────────┐   Pair this device                │
│   │          │   with the FlightPaper app.       │
│   │   QR     │                                   │
│   │  96 x 96 │   IP: 172.20.10.4:8080            │
│   │          │   Code: 421-983                   │
│   └──────────┘   Expires in 8m 02s               │
│                                                  │
│ unpaired                            BAT 78%      │
└──────────────────────────────────────────────────┘
```

The QR fits in 96×96 px at the ePaper's native 1-bit. The fallback
**IP** and **6-digit code** are for manual entry on the phone if the
QR fails to scan. The code is derived from
`HMAC(pairing_secret, "code")[:6 digits]` and is rate-limited the
same way as the QR.

A preview can be generated from a dev machine without hardware:

```bash
python apps/pi/scripts/render_preview.py --page pairing \
  --output /tmp/pair.png
open /tmp/pair.png
```

## QR payload

The QR encodes a `flightpaper://pair?p=<base64url(JSON)>` URI. The JSON
matches
[`packages/protocol/pairing-payload.schema.json`](../packages/protocol/pairing-payload.schema.json):

```json
{
  "v": 1,
  "host": "172.20.10.4",
  "port": 8080,
  "device_id": "fp_a1b2c3d4",
  "device_name": "FlightPaper",
  "device_pub": "<base64url, 32 bytes>",
  "pairing_secret": "<base64url, 32 bytes>",
  "expires_at": 1710000600
}
```

The phone parses this in
[`apps/mobile/src/components/PairingQrScanner.tsx`](../apps/mobile/src/components/PairingQrScanner.tsx)
via `parsePairingUri`, validates with the
`isPairingQrPayload` guard, then hands the payload to
`completePairing` in
[`apps/mobile/src/services/api/pairingClient.ts`](../apps/mobile/src/services/api/pairingClient.ts).

## End-to-end sequence

```
phone                                  Pi
-----                                  --
                                      [boots, sees no paired client]
                                      [enters pairing_pending]
                                      [renders QR on ePaper]
scan QR
parse payload
derive pairing_key
generate (client_priv, client_pub)
build PairRequest (client_pub, …)
seal envelope (key=pairing_key,
              key_id="pairing")
POST /api/public/pair --------------->
                                      decrypt + verify envelope
                                      shared = X25519(device_priv, client_pub)
                                      session_key = HKDF(shared, pairing_secret,
                                                         info=…|device_id|client_id)
                                      persist paired_client
                                      burn pairing_secret
                                  <--- PairResponse envelope (key=pairing_key)
decrypt PairResponse
derive matching session_key
save PairedDevice + SessionKeys
       in SecureStore
reset seq_out
[navigator switches to paired stack]
```

See the same sequence as code in
[`apps/mobile/scripts/e2e-pair.cjs`](../apps/mobile/scripts/e2e-pair.cjs)
— that script runs an actual round-trip against a `uvicorn` Pi server.

## Manual fallback (IP + code)

If the QR can't scan (bad camera, dim light, smudged ePaper), the user
can tap **Enter manually** on the pair screen, type the IP shown on
the ePaper, and the 6-digit code. The phone reconstructs the same
`pairing_secret` from the code via the protocol-defined HMAC
preimage, and the rest of the handshake is identical.

Manual entry is rate-limited server-side. After
`max_pairing_attempts` (default 5) bad attempts, the Pi invalidates
the current secret and re-enters `unpaired`. The user has to wait
for the next ePaper refresh + scan again.

## Failure modes

| Phone-side symptom | Cause | What to do |
|---|---|---|
| `bad_envelope` immediately on POST | Phone fell back to a stale pairing key. | Re-scan the QR. |
| `pairing_expired` | `expires_at` already past. | The Pi will rotate the QR; refresh the ePaper. |
| `attempt_limit` | 5 bad codes / 5 bad envelopes. | Wait for QR rotation. |
| `network_error` | Hotspot dropped or wrong IP. | Confirm `hostname -I` matches the QR. |
| The pair page never appears | The Pi already thinks it's paired (stale client record). | Reset pairing (see below). |

## Resetting pairing

Three options (same as the [`security.md`](security.md) reset
section):

1. **From the phone.** Security → `Reset pairing`. Best-effort calls
   `/api/secure/pairing/reset` then clears SecureStore.
2. **From the API.** Any paired client can post
   `POST /api/secure/pairing/reset`. The Pi drops its record and
   re-enters `pairing_pending`.
3. **From the Pi.** Long-press the PiSugar button (very-long press,
   ≥5 s), or shell in and run:
   ```bash
   sudo /opt/flightpaper/.venv/bin/python /opt/flightpaper/scripts/reset_pairing.py
   sudo systemctl restart flightpaper
   ```

A new QR appears on the next ePaper refresh.
