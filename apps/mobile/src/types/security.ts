/**
 * Phone-side security types: parsed pairing payload (post-QR decode) and
 * the secure envelope.
 */

export interface PairingQrPayload {
  v: 1;
  host: string;
  port: number;
  device_id: string;
  device_name: string;
  /** Base64url X25519 public key, 32 bytes. */
  device_pub: string;
  /** Base64url 32-byte one-time pairing secret. */
  pairing_secret: string;
  expires_at: number;
  /** Optional human-readable fallback code, e.g. ``"123-456"``. */
  code?: string;
}

export type EnvelopeKeyId = 'pairing' | 'main';

export interface SecureEnvelope {
  v: 1;
  device_id: string;
  client_id: string;
  key_id: EnvelopeKeyId;
  seq: number;
  ts: number;
  nonce: string; // base64url
  ciphertext: string; // base64url
}

export interface SessionKeys {
  /** 32-byte X25519 client private key, base64url. Never leaves SecureStore. */
  clientPrivKey: string;
  /** 32-byte X25519 client public key, base64url. */
  clientPubKey: string;
  /** 32-byte session key derived after the pair handshake, base64url. */
  sessionKey: string;
}

/** Wire shape from POST ``/api/public/pair`` (inside the envelope). */
export interface PairRequestBody {
  client_pub: string;
  app_instance_name?: string | null;
  protocol_version: 1;
}

export interface PairResponseBody {
  ok: boolean;
  device_id: string;
  client_id: string;
  key_id: 'main';
  paired_at: number;
  session_starts_at_seq: number;
}

/** Error envelope plaintext. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}
