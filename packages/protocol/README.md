# @flightpaper/protocol

Shared protocol definitions for FlightPaper. Both the Pi service
(`apps/pi/`) and the mobile app (`apps/mobile/`) implement the contracts in
this package.

## Contents

- [`protocol.md`](protocol.md) — high-level protocol: pairing flow, secure
  envelope, sequence numbers, replay window, error codes.
- [`api-contract.md`](api-contract.md) — every HTTP route on the Pi with
  request and response shapes.
- [`pairing-payload.schema.json`](pairing-payload.schema.json) — JSON Schema
  for the QR-encoded pairing payload.
- [`secure-envelope.schema.json`](secure-envelope.schema.json) — JSON Schema
  for the AEAD envelope wrapping every protected request and response.

## Versioning

`v: 1` in every envelope. Bump when the AAD layout, the AEAD construction, or
the pairing handshake changes in a non-backwards-compatible way.
