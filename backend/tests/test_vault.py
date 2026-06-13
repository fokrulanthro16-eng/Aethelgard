"""
Integration tests for vault CRUD endpoints.

DynamoDB is mocked with moto (via the `client` fixture in conftest.py).
Encryption runs in local mode (ENCRYPTION_MODE=local, LOCAL_MASTER_KEY set in conftest.py).
No real AWS credentials or network access are required.
"""

import base64

# ── Helpers ───────────────────────────────────────────────────────────────────

USER_EMAIL = "vaultowner@example.com"
SENSITIVE = "my-secret-password-do-not-store-in-plaintext"
ENTRY_PAYLOAD = {
    "entry_type": "credentials",
    "title": "My Bank Login",
    "sensitive_data": SENSITIVE,
    "notes": "Check quarterly",
}


def _register(client):
    """Create the test user and return the response JSON."""
    return client.post("/users", json={"email": USER_EMAIL}).json()


def _create_entry(client, payload=None):
    """Create a vault entry and return the response JSON."""
    return client.post(
        f"/users/{USER_EMAIL}/vault",
        json=payload or ENTRY_PAYLOAD,
    ).json()


# ── POST /users/{email}/vault ─────────────────────────────────────────────────


def test_create_vault_entry_returns_201(client):
    _register(client)
    response = client.post(f"/users/{USER_EMAIL}/vault", json=ENTRY_PAYLOAD)
    assert response.status_code == 201


def test_create_vault_entry_response_schema(client):
    _register(client)
    data = _create_entry(client)
    assert "entry_id" in data
    assert data["entry_type"] == "credentials"
    assert data["title"] == "My Bank Login"
    assert "created_at" in data
    assert "updated_at" in data
    # Sensitive data must NOT appear in the create response
    assert "sensitive_data" not in data
    assert "notes" not in data


def test_create_vault_entry_unknown_user_returns_404(client):
    response = client.post("/users/nobody@example.com/vault", json=ENTRY_PAYLOAD)
    assert response.status_code == 404


def test_create_vault_entry_missing_title_returns_422(client):
    _register(client)
    response = client.post(
        f"/users/{USER_EMAIL}/vault",
        json={"entry_type": "note", "sensitive_data": "secret"},
    )
    assert response.status_code == 422


def test_create_vault_entry_without_notes(client):
    _register(client)
    payload = {**ENTRY_PAYLOAD}
    del payload["notes"]
    data = client.post(f"/users/{USER_EMAIL}/vault", json=payload).json()
    assert "entry_id" in data


# ── GET /users/{email}/vault ──────────────────────────────────────────────────


def test_list_vault_entries_returns_200(client):
    _register(client)
    response = client.get(f"/users/{USER_EMAIL}/vault")
    assert response.status_code == 200


def test_list_vault_entries_empty_for_new_user(client):
    _register(client)
    data = client.get(f"/users/{USER_EMAIL}/vault").json()
    assert data == []


def test_list_vault_entries_reflects_created_entries(client):
    _register(client)
    _create_entry(client)
    _create_entry(client, {**ENTRY_PAYLOAD, "title": "Second entry"})
    data = client.get(f"/users/{USER_EMAIL}/vault").json()
    assert len(data) == 2


def test_list_vault_entries_no_sensitive_data_exposed(client):
    _register(client)
    _create_entry(client)
    items = client.get(f"/users/{USER_EMAIL}/vault").json()
    for item in items:
        assert "sensitive_data" not in item
        assert "notes" not in item


def test_list_vault_entries_unknown_user_returns_404(client):
    response = client.get("/users/nobody@example.com/vault")
    assert response.status_code == 404


# ── GET /users/{email}/vault/{entry_id} ───────────────────────────────────────


def test_get_vault_entry_returns_200(client):
    _register(client)
    entry = _create_entry(client)
    response = client.get(f"/users/{USER_EMAIL}/vault/{entry['entry_id']}")
    assert response.status_code == 200


def test_get_vault_entry_decrypts_sensitive_data(client):
    _register(client)
    entry = _create_entry(client)
    data = client.get(f"/users/{USER_EMAIL}/vault/{entry['entry_id']}").json()
    assert data["sensitive_data"] == SENSITIVE


def test_get_vault_entry_decrypts_notes(client):
    _register(client)
    entry = _create_entry(client)
    data = client.get(f"/users/{USER_EMAIL}/vault/{entry['entry_id']}").json()
    assert data["notes"] == ENTRY_PAYLOAD["notes"]


def test_get_vault_entry_response_schema(client):
    _register(client)
    entry = _create_entry(client)
    data = client.get(f"/users/{USER_EMAIL}/vault/{entry['entry_id']}").json()
    assert data["entry_id"] == entry["entry_id"]
    assert data["entry_type"] == "credentials"
    assert data["title"] == "My Bank Login"
    assert "created_at" in data
    assert "updated_at" in data


def test_get_vault_entry_not_found_returns_404(client):
    _register(client)
    response = client.get(f"/users/{USER_EMAIL}/vault/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_get_vault_entry_unknown_user_returns_404(client):
    response = client.get("/users/nobody@example.com/vault/any-id")
    assert response.status_code == 404


# ── DELETE /users/{email}/vault/{entry_id} ────────────────────────────────────


def test_delete_vault_entry_returns_200(client):
    _register(client)
    entry = _create_entry(client)
    response = client.delete(f"/users/{USER_EMAIL}/vault/{entry['entry_id']}")
    assert response.status_code == 200


def test_delete_vault_entry_response_schema(client):
    _register(client)
    entry = _create_entry(client)
    data = client.delete(f"/users/{USER_EMAIL}/vault/{entry['entry_id']}").json()
    assert data["deleted"] is True
    assert data["entry_id"] == entry["entry_id"]


def test_delete_vault_entry_removes_from_list(client):
    _register(client)
    entry = _create_entry(client)
    client.delete(f"/users/{USER_EMAIL}/vault/{entry['entry_id']}")
    items = client.get(f"/users/{USER_EMAIL}/vault").json()
    assert items == []


def test_delete_vault_entry_not_found_returns_404(client):
    _register(client)
    response = client.delete(f"/users/{USER_EMAIL}/vault/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_delete_vault_entry_unknown_user_returns_404(client):
    response = client.delete("/users/nobody@example.com/vault/any-id")
    assert response.status_code == 404


# ── Ciphertext-does-not-contain-plaintext guarantee ───────────────────────────


def test_stored_ciphertext_is_not_plaintext(client):
    """
    Verifies that the bytes stored in DynamoDB as `ciphertext` are not the
    plaintext bytes.  Calls the encryption layer directly to inspect the payload.
    """
    from app.security.encryption import encrypt_text

    payload = encrypt_text(SENSITIVE, USER_EMAIL)
    raw_ciphertext = base64.b64decode(payload["ciphertext"])

    assert raw_ciphertext != SENSITIVE.encode()
    assert SENSITIVE.encode() not in raw_ciphertext


def test_same_plaintext_produces_different_ciphertexts(client):
    """
    Each call to encrypt_text generates a fresh random nonce, so even identical
    plaintexts produce distinct ciphertexts.
    """
    from app.security.encryption import encrypt_text

    p1 = encrypt_text(SENSITIVE, USER_EMAIL)
    p2 = encrypt_text(SENSITIVE, USER_EMAIL)
    assert p1["ciphertext"] != p2["ciphertext"]
    assert p1["nonce"] != p2["nonce"]
