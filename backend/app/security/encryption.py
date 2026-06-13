"""
AES-256-GCM envelope encryption for Aethelgard vault entries.

Two modes, selected by ENCRYPTION_MODE in config:

  local (default / development)
    Derives a 256-bit per-user key from LOCAL_MASTER_KEY + email using HKDF-SHA256.
    No AWS dependency. Rotating LOCAL_MASTER_KEY invalidates all existing ciphertext.
    TODO (production hardening): move LOCAL_MASTER_KEY to AWS Secrets Manager or
    Parameter Store so it is never stored on disk alongside the ciphertext.

  kms (production)
    Calls AWS KMS GenerateDataKey to produce a fresh 256-bit data key per operation.
    Encrypts plaintext with the plaintext data key, then discards it.
    Stores the KMS-encrypted data key next to the ciphertext so it can be retrieved
    at decrypt time (standard envelope encryption pattern).
    TODO (production hardening): implement _generate_kms_data_key() and
    _decrypt_kms_data_key() using boto3 KMS client once a CMK ARN is available.

Stored payload format
─────────────────────
  {
    "ciphertext": "<base64>",   # AES-256-GCM ciphertext (includes 16-byte auth tag)
    "nonce":      "<base64>",   # 12-byte random nonce (96-bit, GCM standard)
    "algorithm":  "AES-256-GCM",
    "mode":       "local" | "kms",
    # KMS mode only:
    "encrypted_data_key": "<base64>",
    "kms_key_id":          "<arn-or-alias>",
  }

Plaintext is never persisted anywhere.
"""

import base64
import secrets
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from app.core.config import settings

_ALGORITHM = "AES-256-GCM"
_NONCE_BYTES = 12   # 96-bit nonce — NIST recommendation for GCM
_KEY_BYTES = 32     # 256-bit key


# ── Internal helpers ──────────────────────────────────────────────────────────

def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _b64d(value: str) -> bytes:
    return base64.b64decode(value)


def _derive_local_key(user_email: str) -> bytes:
    """
    Deterministically derives a 256-bit AES key for `user_email` from
    LOCAL_MASTER_KEY using HKDF-SHA256.  Each user gets a unique key; rotating
    LOCAL_MASTER_KEY makes all existing ciphertext permanently unreadable.

    TODO (production): store LOCAL_MASTER_KEY in AWS Secrets Manager and fetch
    it at startup rather than reading from the environment.
    """
    master = settings.LOCAL_MASTER_KEY
    if not master:
        raise RuntimeError(
            "LOCAL_MASTER_KEY is not set. "
            "Add it to backend/.env for local encryption mode."
        )
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=_KEY_BYTES,
        salt=None,
        info=user_email.lower().strip().encode(),
    )
    return hkdf.derive(master.encode())


def _generate_local_data_key(user_email: str) -> tuple[bytes, dict[str, str]]:
    key = _derive_local_key(user_email)
    return key, {"mode": "local"}


def _generate_kms_data_key(user_email: str) -> tuple[bytes, dict[str, str]]:  # noqa: ARG001
    """
    TODO (production): call KMS GenerateDataKey and return the plaintext key +
    metadata dict containing encrypted_data_key and kms_key_id.

    import boto3
    kms = boto3.client("kms", region_name=settings.AWS_REGION)
    resp = kms.generate_data_key(KeyId=settings.KMS_KEY_ID, KeySpec="AES_256")
    return resp["Plaintext"], {
        "mode": "kms",
        "encrypted_data_key": _b64e(resp["CiphertextBlob"]),
        "kms_key_id": settings.KMS_KEY_ID,
    }
    """
    raise NotImplementedError(
        "KMS mode is not yet implemented. Set ENCRYPTION_MODE=local for development."
    )


def _decrypt_kms_data_key(payload: dict[str, Any]) -> bytes:
    """
    TODO (production): call KMS Decrypt to recover the plaintext data key.

    import boto3
    kms = boto3.client("kms", region_name=settings.AWS_REGION)
    resp = kms.decrypt(
        CiphertextBlob=_b64d(payload["encrypted_data_key"]),
        KeyId=settings.KMS_KEY_ID,
    )
    return resp["Plaintext"]
    """
    raise NotImplementedError(
        "KMS decryption is not yet implemented."
    )


# ── Public API ────────────────────────────────────────────────────────────────

def generate_data_key(user_email: str) -> tuple[bytes, dict[str, str]]:
    """
    Returns (plaintext_key_bytes, key_metadata_dict).

    The metadata dict is merged into the encrypted payload stored in DynamoDB.
    For local mode it only contains {"mode": "local"}.
    For KMS mode it additionally contains encrypted_data_key and kms_key_id.
    The plaintext key bytes are NEVER stored.
    """
    mode = settings.ENCRYPTION_MODE.lower()
    if mode == "local":
        return _generate_local_data_key(user_email)
    if mode == "kms":
        return _generate_kms_data_key(user_email)
    raise ValueError(
        f"Unknown ENCRYPTION_MODE: {settings.ENCRYPTION_MODE!r}. "
        "Supported values: 'local', 'kms'."
    )


def encrypt_text(plaintext: str, user_email: str) -> dict[str, Any]:
    """
    Encrypts a UTF-8 string with AES-256-GCM.
    Returns a dict that is safe to store directly in DynamoDB (no plaintext).

    A fresh 12-byte nonce is generated for every call — even identical plaintexts
    produce different ciphertexts.  The 16-byte GCM authentication tag is appended
    to the ciphertext by the cryptography library; no separate tag field is needed.
    """
    key, key_meta = generate_data_key(user_email)
    nonce = secrets.token_bytes(_NONCE_BYTES)
    aesgcm = AESGCM(key)
    # ciphertext here is ciphertext_bytes || auth_tag (16 bytes)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return {
        "ciphertext": _b64e(ciphertext),
        "nonce": _b64e(nonce),
        "algorithm": _ALGORITHM,
        **key_meta,
    }


def decrypt_text(payload: dict[str, Any], user_email: str) -> str:
    """
    Decrypts a payload produced by encrypt_text().
    Raises ValueError on tag-mismatch (tampered / corrupted data).
    """
    mode = payload.get("mode", "local")
    if mode == "local":
        key = _derive_local_key(user_email)
    elif mode == "kms":
        key = _decrypt_kms_data_key(payload)
    else:
        raise ValueError(f"Unknown encryption mode in payload: {mode!r}")

    nonce = _b64d(payload["nonce"])
    ciphertext = _b64d(payload["ciphertext"])
    aesgcm = AESGCM(key)
    # decrypt raises InvalidTag if auth tag verification fails
    return aesgcm.decrypt(nonce, ciphertext, None).decode()


def encrypt_vault_payload(payload: dict[str, Any], user_email: str) -> dict[str, Any]:
    """
    Encrypts every string value in `payload` individually.
    Non-string values (None, numbers, etc.) pass through unchanged.
    Returns a new dict; does not mutate the input.
    """
    return {
        k: (encrypt_text(v, user_email) if isinstance(v, str) else v)
        for k, v in payload.items()
    }


def decrypt_vault_payload(encrypted_payload: dict[str, Any], user_email: str) -> dict[str, Any]:
    """
    Decrypts every value in `encrypted_payload` that looks like an encrypted payload
    (dict with a "ciphertext" key).  Other values pass through unchanged.
    """
    return {
        k: (decrypt_text(v, user_email) if isinstance(v, dict) and "ciphertext" in v else v)
        for k, v in encrypted_payload.items()
    }
