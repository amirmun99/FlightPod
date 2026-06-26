/**
 * Secure RPC layer: builds a request envelope, sends it, opens the
 * response envelope, and returns the typed plaintext.
 *
 * Sequence numbers come from SecureStore (``claimNextSeqOut``) so a
 * process restart can't reuse a previously-accepted ``seq``.
 *
 * On any envelope-layer or HTTP error we surface :class:`ApiError` —
 * routes throw their decoded ``code`` field so callers can branch on
 * ``not_paired`` / ``expired`` / ``replay`` / etc.
 */

import { b64uDecode, b64uEncode, openEnvelopeJson, sealEnvelopeJson, utf8Encode } from '../crypto';
import { RESPONSE_METHOD } from '../crypto/envelope';
import { claimNextSeqOut } from '../storage/secureStore';
import { nowTs } from '../../utils/time';
import { ApiClient, ApiError } from './client';
import type { SecureEnvelope, SessionKeys } from '../../types';

export interface SecureCallContext {
  client: ApiClient;
  deviceId: string;
  clientId: string;
  sessionKey: Uint8Array | string; // Uint8Array or base64url
}

const asKey = (key: Uint8Array | string): Uint8Array =>
  typeof key === 'string' ? b64uDecode(key) : key;

export const secureRequest = async <TReq, TRes>(
  ctx: SecureCallContext,
  input: {
    method: 'GET' | 'POST' | 'PATCH';
    path: string;
    payload: TReq;
  },
): Promise<TRes> => {
  const key = asKey(ctx.sessionKey);
  const seq = await claimNextSeqOut();
  const ts = nowTs();

  const requestEnvelope = sealEnvelopeJson(key, input.payload, {
    method: input.method,
    path: input.path,
    deviceId: ctx.deviceId,
    clientId: ctx.clientId,
    keyId: 'main',
    seq,
    ts,
  });

  // Browsers + Node fetch refuse to send a body on GET, so for GET we
  // serialize the envelope into an ``?e=`` query parameter. The Pi
  // accepts both forms (see ``apps/pi/flightpaper/api/auth.py``). The
  // path used for AAD stays unchanged because the server reads
  // ``request.url.path`` (no query string).
  let response;
  if (input.method === 'GET') {
    const encoded = b64uEncode(utf8Encode(JSON.stringify(requestEnvelope)));
    const sep = input.path.includes('?') ? '&' : '?';
    response = await ctx.client.request<SecureEnvelope>({
      method: 'GET',
      path: `${input.path}${sep}e=${encoded}`,
    });
  } else {
    response = await ctx.client.request<SecureEnvelope>({
      method: input.method,
      path: input.path,
      body: requestEnvelope,
    });
  }

  // The server seals the response with method=RES and the same path.
  return openEnvelopeJson<TRes>(key, response.body, {
    method: RESPONSE_METHOD,
    path: input.path,
    deviceId: ctx.deviceId,
    clientId: ctx.clientId,
    keyId: 'main',
    seq: response.body.seq,
    ts: response.body.ts,
  });
};

/** Convenience: pull (deviceId, clientId, sessionKey) from a SessionKeys + PairedDevice. */
export const contextFromSession = (
  client: ApiClient,
  session: SessionKeys,
  deviceId: string,
  clientId: string,
): SecureCallContext => ({
  client,
  deviceId,
  clientId,
  sessionKey: session.sessionKey,
});

export { ApiError };
