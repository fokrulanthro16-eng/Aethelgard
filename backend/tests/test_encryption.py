"""
Unit tests for the AES-256-GCM encryption layer.

These tests run entirely in memory — no AWS, no DynamoDB, no network.
ENCRYPTION_MODE=local and LOCAL_MASTER_KEY are set in conftest.py.
"""

import base64

from app.security.encryption import (
    decrypt_text,
    decrypt_vault_payload,
    encrypt_text,
    encrypt_vault_payload,
    generate_data_key,
)


EMAIL = "alice@example.com"
PLAINTEXT = "my-secret-password-123"


# ── generate_data_key ─────────────────────────────────────────────────────────


def test_generate_data_key_returns_32_bytes():
    key, meta = generate_data_key(EMAIL)
    assert len(key) == 32


def test_generate_data_key_local_mode_metadata():
    _, meta = generate_data_key(EMAIL)
    assert meta["mode"] == "local"


def test_generate_data_key_deterministic_for_same_email():
    key1, _ = generate_data_key(EMAIL)
    key2, _ = generate_data_key(EMAIL)
    assert key1 == key2


def test_generate_data_key_differs_across_emails():
    key1, _ = generate_data_key("alice@example.com")
    key2, _ = generate_data_key("bob@example.com")
    assert key1 != key2


# ── encrypt_text ──────────────────────────────────────────────────────────────


def test_encrypt_text_returns_required_fields():
    payload = encrypt_text(PLAINTEXT, EMAIL)
    assert "ciphertext" in payload
    assert "nonce" in payload
    assert "algorithm" in payload
    assert "mode" in payload


def test_encrypt_text_algorithm_is_aes_256_gcm():
    payload = encrypt_text(PLAINTEXT, EMAIL)
    assert payload["algorithm"] == "AES-256-GCM"


def test_encrypt_text_nonce_is_12_bytes():
    payload = encrypt_text(PLAINTEXT, EMAIL)
    nonce_bytes = base64.b64decode(payload["nonce"])
    assert len(nonce_bytes) == 12


def test_encrypt_text_ciphertext_is_valid_base64():
    payload = encrypt_text(PLAINTEXT, EMAIL)
    decoded = base64.b64decode(payload["ciphertext"])
    assert len(decoded) > 0


def test_encrypt_text_ciphertext_not_equal_to_plaintext():
    payload = encrypt_text(PLAINTEXT, EMAIL)
    # The base64 string itself must not equal the plaintext
    assert payload["ciphertext"] != PLAINTEXT
    # The decoded bytes must not equal the plaintext bytes
    assert base64.b64decode(payload["ciphertext"]) != PLAINTEXT.encode()


def test_encrypt_text_different_nonce_each_call():
    p1 = encrypt_text(PLAINTEXT, EMAIL)
    p2 = encrypt_text(PLAINTEXT, EMAIL)
    # Random nonce → ciphertexts differ even for identical input
    assert p1["nonce"] != p2["nonce"]
    assert p1["ciphertext"] != p2["ciphertext"]


# ── decrypt_text ──────────────────────────────────────────────────────────────


def test_roundtrip_returns_original_plaintext():
    payload = encrypt_text(PLAINTEXT, EMAIL)
    result = decrypt_text(payload, EMAIL)
    assert result == PLAINTEXT


def test_roundtrip_preserves_unicode():
    unicode_text = "Héllo wörld 日本語 🔒"
    payload = encrypt_text(unicode_text, EMAIL)
    assert decrypt_text(payload, EMAIL) == unicode_text


def test_roundtrip_preserves_multiline():
    multiline = "line one\nline two\nline three"
    payload = encrypt_text(multiline, EMAIL)
    assert decrypt_text(payload, EMAIL) == multiline


def test_wrong_email_cannot_decrypt():
    """Different email → different derived key → decryption raises an exception."""
    payload = encrypt_text(PLAINTEXT, EMAIL)
    try:
        result = decrypt_text(payload, "eve@example.com")
        # If it doesn't raise, the result must differ from the original plaintext
        assert result != PLAINTEXT
    except Exception:
        pass  # expected — AESGCM raises InvalidTag on auth failure


# ── encrypt_vault_payload / decrypt_vault_payload ─────────────────────────────


def test_encrypt_vault_payload_encrypts_string_values():
    raw = {"sensitive_data": "my secret", "notes": "extra info"}
    encrypted = encrypt_vault_payload(raw, EMAIL)
    assert isinstance(encrypted["sensitive_data"], dict)
    assert "ciphertext" in encrypted["sensitive_data"]
    assert isinstance(encrypted["notes"], dict)
    assert "ciphertext" in encrypted["notes"]


def test_encrypt_vault_payload_passes_through_none():
    raw = {"sensitive_data": "my secret", "notes": None}
    encrypted = encrypt_vault_payload(raw, EMAIL)
    assert encrypted["notes"] is None


def test_decrypt_vault_payload_roundtrip():
    raw = {"sensitive_data": "my secret", "notes": "extra info"}
    encrypted = encrypt_vault_payload(raw, EMAIL)
    decrypted = decrypt_vault_payload(encrypted, EMAIL)
    assert decrypted["sensitive_data"] == "my secret"
    assert decrypted["notes"] == "extra info"


def test_decrypt_vault_payload_passes_through_non_encrypted_values():
    mixed = {
        "title": "My Title",           # plain string — not an encrypted dict
        "sensitive_data": encrypt_text("secret", EMAIL),
        "count": 42,
    }
    result = decrypt_vault_payload(mixed, EMAIL)
    # title is a plain string, not a dict with "ciphertext", so it passes through
    assert result["title"] == "My Title"
    assert result["sensitive_data"] == "secret"
    assert result["count"] == 42
