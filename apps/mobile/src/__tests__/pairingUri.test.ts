import vectors from './fixtures/vectors.json';

import { isPairingQrPayload } from '../utils/validation';
import { b64uDecode, utf8Decode } from '../services/crypto/base64u';

const parsePairUri = (uri: string): unknown => {
  if (!uri.startsWith('flightpaper://pair?')) {
    throw new Error('not a flightpaper pair URI');
  }
  const url = new URL(uri.replace('flightpaper://pair', 'http://pair/'));
  const p = url.searchParams.get('p');
  if (!p) throw new Error('missing p param');
  const raw = b64uDecode(p);
  return JSON.parse(utf8Decode(raw));
};

describe('pairing URI parser', () => {
  it('parses the Pi-generated URI back to the original payload', () => {
    const sample = vectors.pair_uri_sample;
    const decoded = parsePairUri(sample.uri);
    expect(decoded).toEqual(sample.payload);
  });

  it('isPairingQrPayload accepts valid payload', () => {
    expect(isPairingQrPayload(vectors.pair_uri_sample.payload)).toBe(true);
  });

  it('isPairingQrPayload rejects garbage', () => {
    expect(isPairingQrPayload(null)).toBe(false);
    expect(isPairingQrPayload({ ...vectors.pair_uri_sample.payload, v: 2 })).toBe(false);
    expect(isPairingQrPayload({ ...vectors.pair_uri_sample.payload, device_id: 'bad' })).toBe(false);
    expect(
      isPairingQrPayload({ ...vectors.pair_uri_sample.payload, device_pub: 'too-short' }),
    ).toBe(false);
  });
});
