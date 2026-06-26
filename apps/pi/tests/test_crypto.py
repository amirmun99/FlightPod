"""Tests for flightpaper.security.crypto."""

from __future__ import annotations

import pytest

from flightpaper.security.crypto import (
    AEAD_KEY_BYTES,
    AEAD_NONCE_BYTES,
    AEAD_TAG_BYTES,
    CryptoError,
    DecryptionError,
    aead_decrypt,
    aead_encrypt,
    b64u_decode,
    b64u_encode,
    constant_time_eq,
    derive_pairing_key,
    derive_session_key,
    generate_x25519_keypair,
    hkdf_sha256,
    random_nonce,
    random_pairing_secret,
    x25519_shared_secret,
)


# ---------------------------------------------------------------------------
# Sizes
# ---------------------------------------------------------------------------


class TestSizes:
    def test_constants_match_xchacha20_poly1305(self) -> None:
        assert AEAD_KEY_BYTES == 32
        assert AEAD_NONCE_BYTES == 24
        assert AEAD_TAG_BYTES == 16

    def test_random_pairing_secret_is_32_bytes(self) -> None:
        assert len(random_pairing_secret()) == 32

    def test_random_nonce_is_24_bytes(self) -> None:
        assert len(random_nonce()) == 24


# ---------------------------------------------------------------------------
# HKDF (RFC 5869 Test Case 1)
# ---------------------------------------------------------------------------


class TestHkdf:
    def test_rfc5869_test_case_1(self) -> None:
        ikm = bytes.fromhex("0b" * 22)
        salt = bytes.fromhex("000102030405060708090a0b0c")
        info = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9")
        expected = bytes.fromhex(
            "3cb25f25faacd57a90434f64d0362f2a"
            "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
            "34007208d5b887185865"
        )
        okm = hkdf_sha256(ikm=ikm, salt=salt, info=info, length=42)
        assert okm == expected

    def test_zero_salt_uses_zero_hash_block(self) -> None:
        # When salt is empty, RFC 5869 specifies it's treated as a string of
        # HashLen zero bytes. Just check we don't crash and we get a key.
        out = hkdf_sha256(ikm=b"ikm", salt=b"", info=b"info", length=32)
        assert len(out) == 32

    def test_length_constraints(self) -> None:
        with pytest.raises(CryptoError):
            hkdf_sha256(ikm=b"x", salt=b"y", info=b"z", length=0)
        with pytest.raises(CryptoError):
            hkdf_sha256(ikm=b"x", salt=b"y", info=b"z", length=255 * 32 + 1)


# ---------------------------------------------------------------------------
# X25519 ECDH
# ---------------------------------------------------------------------------


class TestX25519:
    def test_roundtrip(self) -> None:
        a = generate_x25519_keypair()
        b = generate_x25519_keypair()
        s_ab = x25519_shared_secret(private_key=a.private_key, peer_public_key=b.public_key)
        s_ba = x25519_shared_secret(private_key=b.private_key, peer_public_key=a.public_key)
        assert s_ab == s_ba
        assert len(s_ab) == 32

    def test_rejects_bad_lengths(self) -> None:
        a = generate_x25519_keypair()
        with pytest.raises(CryptoError):
            x25519_shared_secret(private_key=b"\x00" * 31, peer_public_key=a.public_key)
        with pytest.raises(CryptoError):
            x25519_shared_secret(private_key=a.private_key, peer_public_key=b"\x00" * 31)


# ---------------------------------------------------------------------------
# Pairing + session key derivation
# ---------------------------------------------------------------------------


class TestKeyDerivation:
    def test_pairing_key_is_deterministic(self) -> None:
        secret = b"\x02" * 32
        device_pub = b"\x11" * 32
        k1 = derive_pairing_key(
            pairing_secret=secret, device_id="fp_aabbccdd", device_public_key=device_pub
        )
        k2 = derive_pairing_key(
            pairing_secret=secret, device_id="fp_aabbccdd", device_public_key=device_pub
        )
        assert k1 == k2
        assert len(k1) == 32

    def test_pairing_key_binds_to_device(self) -> None:
        # Same secret + different device identity must give a different key.
        secret = b"\x02" * 32
        k_a = derive_pairing_key(
            pairing_secret=secret,
            device_id="fp_aabbccdd",
            device_public_key=b"\x11" * 32,
        )
        k_b = derive_pairing_key(
            pairing_secret=secret,
            device_id="fp_aabbccdd",
            device_public_key=b"\x22" * 32,
        )
        k_c = derive_pairing_key(
            pairing_secret=secret,
            device_id="fp_99999999",
            device_public_key=b"\x11" * 32,
        )
        assert k_a != k_b
        assert k_a != k_c

    def test_pairing_key_rejects_bad_public_key_size(self) -> None:
        with pytest.raises(CryptoError):
            derive_pairing_key(
                pairing_secret=b"\x02" * 32,
                device_id="fp_aabbccdd",
                device_public_key=b"\x11" * 31,
            )

    def test_session_key_includes_device_and_client_id(self) -> None:
        shared = b"\x01" * 32
        secret = b"\x02" * 32
        k_a = derive_session_key(
            shared_secret=shared,
            pairing_secret=secret,
            device_id="fp_aabbccdd",
            client_id="iphone_aaaaaaaaaaaa",
        )
        k_b = derive_session_key(
            shared_secret=shared,
            pairing_secret=secret,
            device_id="fp_aabbccdd",
            client_id="iphone_bbbbbbbbbbbb",
        )
        assert k_a != k_b
        assert len(k_a) == 32

    def test_pairing_and_session_keys_diverge(self) -> None:
        secret = b"\x02" * 32
        device_pub = b"\x11" * 32
        pk = derive_pairing_key(
            pairing_secret=secret, device_id="fp_aabbccdd", device_public_key=device_pub
        )
        sk = derive_session_key(
            shared_secret=b"\x55" * 32,
            pairing_secret=secret,
            device_id="fp_aabbccdd",
            client_id="iphone_aaaaaaaaaaaa",
        )
        assert pk != sk


# ---------------------------------------------------------------------------
# AEAD round-trip + tamper detection
# ---------------------------------------------------------------------------


class TestAead:
    def setup_method(self) -> None:
        self.key = b"k" * 32
        self.nonce = b"n" * 24
        self.aad = b"associated|data"
        self.pt = b"plaintext payload"

    def test_round_trip(self) -> None:
        ct = aead_encrypt(key=self.key, nonce=self.nonce, plaintext=self.pt, aad=self.aad)
        out = aead_decrypt(key=self.key, nonce=self.nonce, ciphertext=ct, aad=self.aad)
        assert out == self.pt

    def test_includes_tag_in_ciphertext(self) -> None:
        ct = aead_encrypt(key=self.key, nonce=self.nonce, plaintext=self.pt, aad=self.aad)
        assert len(ct) == len(self.pt) + AEAD_TAG_BYTES

    def test_tamper_ciphertext_rejected(self) -> None:
        ct = bytearray(aead_encrypt(key=self.key, nonce=self.nonce, plaintext=self.pt, aad=self.aad))
        ct[0] ^= 0x01
        with pytest.raises(DecryptionError):
            aead_decrypt(key=self.key, nonce=self.nonce, ciphertext=bytes(ct), aad=self.aad)

    def test_tamper_tag_rejected(self) -> None:
        ct = bytearray(aead_encrypt(key=self.key, nonce=self.nonce, plaintext=self.pt, aad=self.aad))
        ct[-1] ^= 0x80
        with pytest.raises(DecryptionError):
            aead_decrypt(key=self.key, nonce=self.nonce, ciphertext=bytes(ct), aad=self.aad)

    def test_wrong_aad_rejected(self) -> None:
        ct = aead_encrypt(key=self.key, nonce=self.nonce, plaintext=self.pt, aad=self.aad)
        with pytest.raises(DecryptionError):
            aead_decrypt(key=self.key, nonce=self.nonce, ciphertext=ct, aad=b"other")

    def test_wrong_key_rejected(self) -> None:
        ct = aead_encrypt(key=self.key, nonce=self.nonce, plaintext=self.pt, aad=self.aad)
        with pytest.raises(DecryptionError):
            aead_decrypt(key=b"x" * 32, nonce=self.nonce, ciphertext=ct, aad=self.aad)

    def test_wrong_nonce_rejected(self) -> None:
        ct = aead_encrypt(key=self.key, nonce=self.nonce, plaintext=self.pt, aad=self.aad)
        with pytest.raises(DecryptionError):
            aead_decrypt(key=self.key, nonce=b"o" * 24, ciphertext=ct, aad=self.aad)

    def test_short_ciphertext_rejected(self) -> None:
        with pytest.raises(DecryptionError):
            aead_decrypt(key=self.key, nonce=self.nonce, ciphertext=b"shrt", aad=self.aad)

    def test_invalid_sizes_raise(self) -> None:
        with pytest.raises(CryptoError):
            aead_encrypt(key=b"\x00" * 31, nonce=self.nonce, plaintext=self.pt, aad=self.aad)
        with pytest.raises(CryptoError):
            aead_encrypt(key=self.key, nonce=b"\x00" * 12, plaintext=self.pt, aad=self.aad)


# ---------------------------------------------------------------------------
# base64url helpers + constant-time comparison
# ---------------------------------------------------------------------------


class TestB64u:
    def test_round_trip(self) -> None:
        data = bytes(range(256))
        encoded = b64u_encode(data)
        # No padding characters in the output.
        assert "=" not in encoded
        assert b64u_decode(encoded) == data

    def test_decode_handles_missing_padding(self) -> None:
        s = b64u_encode(b"hi")
        # Decoder must accept both with and without padding.
        assert b64u_decode(s) == b"hi"
        assert b64u_decode(s + "=") == b"hi"

    def test_invalid_string_rejected(self) -> None:
        with pytest.raises(CryptoError):
            b64u_decode("not valid base64!!!")

    def test_constant_time_eq(self) -> None:
        assert constant_time_eq(b"abc", b"abc")
        assert not constant_time_eq(b"abc", b"abd")
        assert not constant_time_eq(b"abc", b"abcd")
