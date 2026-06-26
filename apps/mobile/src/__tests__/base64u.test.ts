import { b64uDecode, b64uEncode, utf8Decode, utf8Encode } from '../services/crypto/base64u';

describe('base64url', () => {
  it('round-trips arbitrary bytes', () => {
    for (let n = 0; n < 256; n++) {
      const bytes = new Uint8Array(n);
      for (let i = 0; i < n; i++) bytes[i] = i & 0xff;
      const encoded = b64uEncode(bytes);
      expect(encoded).not.toContain('=');
      const decoded = b64uDecode(encoded);
      expect(Array.from(decoded)).toEqual(Array.from(bytes));
    }
  });

  it('rejects invalid characters', () => {
    expect(() => b64uDecode('hello!world')).toThrow(/base64url/);
  });

  it('tolerates standard base64 padding on input', () => {
    expect(Array.from(b64uDecode('aGk='))).toEqual([0x68, 0x69]);
    expect(Array.from(b64uDecode('aGk'))).toEqual([0x68, 0x69]);
  });

  it('utf8 round-trips', () => {
    const samples = ['', 'hello', 'γειά σου', '中文 🚀', 'foo|bar=baz'];
    for (const s of samples) {
      expect(utf8Decode(utf8Encode(s))).toBe(s);
    }
  });
});
